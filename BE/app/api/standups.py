import uuid
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_manager
from app.db.session import get_db
from app.models.standup_follow import StandupFollow
from app.models.user import User
from app.services.standups import build_standups

router = APIRouter(prefix="/api/standups", tags=["standups"])


@router.get("")
async def get_standups(
    day: date | None = None,
    scope: Literal["all", "following"] = "all",
    viewer: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await build_standups(db, viewer, day or datetime.now(timezone.utc).date(), scope)


class FollowBody(BaseModel):
    following: bool


@router.put("/follows/{person_id}")
async def set_follow(
    person_id: uuid.UUID,
    body: FollowBody,
    viewer: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> dict:
    person = await db.get(User, person_id)
    if person is None or person.organization_id != viewer.organization_id or person.id == viewer.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")

    existing = (
        await db.execute(
            select(StandupFollow)
            .where(StandupFollow.manager_user_id == viewer.id)
            .where(StandupFollow.person_user_id == person_id)
        )
    ).scalar_one_or_none()

    if body.following and existing is None:
        db.add(StandupFollow(manager_user_id=viewer.id, person_user_id=person_id))
    elif not body.following and existing is not None:
        await db.execute(delete(StandupFollow).where(StandupFollow.id == existing.id))
    await db.commit()
    return {"following": body.following}
