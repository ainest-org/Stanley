import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.security import decrypt_token
from app.db.session import get_db
from app.models.organization import Organization
from app.models.synced_project import SyncedProject
from app.models.user import User
from app.models.work_item import WorkItem
from app.services.team_board import build_team_board
from app.sync.mutations import update_work_item_assignee

router = APIRouter(prefix="/api", tags=["team-board"])


@router.get("/team-board")
async def get_team_board(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    organization = await db.get(Organization, current_user.organization_id)
    return await build_team_board(db, organization)


class ReassignRequest(BaseModel):
    assignee_user_id: uuid.UUID


@router.patch("/work-items/{work_item_id}/assignee")
async def reassign_work_item(
    work_item_id: uuid.UUID,
    body: ReassignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Write-through reassignment (PRD Section 7.5): a real PATCH to GitLab, executed as the
    acting user, so it can never succeed beyond what their own GitLab permission allows
    (Section 13.3: GitLab's rejection is surfaced as-is, never silently swallowed)."""
    if not current_user.encrypted_access_token:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign in with GitLab again to enable write actions")

    work_item = await db.get(WorkItem, work_item_id)
    if work_item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work item not found")

    project = await db.get(SyncedProject, work_item.synced_project_id)
    assignee = await db.get(User, body.assignee_user_id)
    if project is None or assignee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project or assignee not found")

    access_token = decrypt_token(current_user.encrypted_access_token)

    try:
        await update_work_item_assignee(work_item, project, assignee.gitlab_user_id, access_token)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"GitLab rejected the reassignment ({exc.response.status_code}): {exc.response.text}",
        ) from exc

    # Optimistic local update — the next reconciliation/webhook will confirm it either way.
    work_item.assignee_user_id = assignee.id
    await db.commit()

    return {"work_item_id": str(work_item.id), "assignee_user_id": str(assignee.id)}
