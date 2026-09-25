"""GitLab access levels as synced into ProjectMembership (PRD Section 12: GitLab permission is
the hard ceiling; Stanley may only add stricter rules on top, never grant more)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import GitLabAccessLevel
from app.models.project_membership import ProjectMembership
from app.models.user import User

MILESTONE_MANAGER_LEVELS = {GitLabAccessLevel.MAINTAINER, GitLabAccessLevel.OWNER}


async def project_access_level(db: AsyncSession, user: User, project_id: uuid.UUID) -> GitLabAccessLevel | None:
    return (
        await db.execute(
            select(ProjectMembership.access_level)
            .where(ProjectMembership.synced_project_id == project_id)
            .where(ProjectMembership.user_id == user.id)
        )
    ).scalar_one_or_none()


async def can_manage_milestones(db: AsyncSession, user: User, project_id: uuid.UUID) -> bool:
    return await project_access_level(db, user, project_id) in MILESTONE_MANAGER_LEVELS
