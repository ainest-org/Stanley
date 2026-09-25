import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.blocked_flag import BlockedFlag
from app.models.organization import Organization
from app.models.user import User
from app.models.work_item import WorkItem
from app.services.my_work import build_my_work

router = APIRouter(prefix="/api", tags=["my-work"])


@router.get("/my-work")
async def get_my_work(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    organization = await db.get(Organization, current_user.organization_id)
    return await build_my_work(db, current_user, organization)


class MarkBlockedRequest(BaseModel):
    reason: str


@router.post("/work-items/{work_item_id}/blocked", status_code=status.HTTP_201_CREATED)
async def mark_blocked(
    work_item_id: uuid.UUID,
    body: MarkBlockedRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Mark blocked + reason (PRD Section 6.4) — the one piece of data this tool owns locally
    for a work item, since GitLab has no clean equivalent. Visible to the person's manager and
    surfaced on Team Board / Radar."""
    work_item = await db.get(WorkItem, work_item_id)
    if work_item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work item not found")

    flag = BlockedFlag(work_item_id=work_item_id, created_by_user_id=current_user.id, reason=body.reason)
    db.add(flag)
    await db.commit()
    await db.refresh(flag)

    return {"id": str(flag.id), "work_item_id": str(work_item_id), "reason": flag.reason}


@router.post("/work-items/{work_item_id}/unblock")
async def unmark_blocked(
    work_item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import datetime, timezone

    from sqlalchemy import select

    result = await db.execute(
        select(BlockedFlag)
        .where(BlockedFlag.work_item_id == work_item_id)
        .where(BlockedFlag.resolved_at.is_(None))
    )
    flags = result.scalars().all()
    for flag in flags:
        flag.resolved_at = datetime.now(timezone.utc)
    await db.commit()

    return {"resolved_count": len(flags)}
