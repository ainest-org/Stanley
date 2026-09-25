import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.tokens import get_valid_access_token, get_write_access_token
from app.db.session import get_db
from app.models.organization import Organization
from app.models.synced_project import SyncedProject
from app.models.user import User
from app.models.work_item import WorkItem
from app.services.team_board import TeamBoardFilters, build_filter_options, build_team_board
from app.services.work_item_detail import build_work_item_detail
from app.sync.gitlab_client import GitLabGraphQLError
from app.sync.mutations import update_work_item_assignee

router = APIRouter(prefix="/api", tags=["team-board"])


@router.get("/team-board")
async def get_team_board(
    project_id: uuid.UUID | None = None,
    milestone: str | None = None,
    label: str | None = None,
    flagged_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    organization = await db.get(Organization, current_user.organization_id)
    filters = TeamBoardFilters(project_id=project_id, milestone=milestone, label=label, flagged_only=flagged_only)
    return await build_team_board(db, organization, filters)


@router.get("/team-board/filters")
async def get_team_board_filters(_: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return await build_filter_options(db)


@router.get("/work-items/{work_item_id}/detail")
async def get_work_item_detail(
    work_item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = await db.get(WorkItem, work_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This item no longer exists in Stanley (it may have been deleted in GitLab)")
    access_token, _ = await get_valid_access_token(db, current_user)
    return await build_work_item_detail(db, item, access_token, current_user)


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
    work_item = await db.get(WorkItem, work_item_id)
    if work_item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work item not found")

    project = await db.get(SyncedProject, work_item.synced_project_id)
    assignee = await db.get(User, body.assignee_user_id)
    if project is None or assignee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project or assignee not found")

    access_token = await get_write_access_token(db, current_user)

    try:
        await update_work_item_assignee(work_item, project, assignee.gitlab_user_id, access_token)
    except GitLabGraphQLError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"GitLab rejected the reassignment: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"GitLab rejected the reassignment ({exc.response.status_code}): {exc.response.text}",
        ) from exc

    # Optimistic local update — the next reconciliation/webhook will confirm it either way.
    work_item.assignee_user_id = assignee.id
    await db.commit()

    return {"work_item_id": str(work_item.id), "assignee_user_id": str(assignee.id)}
