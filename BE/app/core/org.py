from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.organization import Organization

settings = get_settings()


async def get_or_create_default_organization(db: AsyncSession) -> Organization:
    """Single-tenant deployment (PRD: not multi-tenant in v1) — there is exactly one
    Organization row, bootstrapped lazily the first time it's needed."""
    result = await db.execute(select(Organization).limit(1))
    organization = result.scalar_one_or_none()
    if organization is None:
        organization = Organization(name="Default Organization", gitlab_instance_url=settings.gitlab_instance_url)
        db.add(organization)
        await db.flush()
    return organization
