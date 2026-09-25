from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.organization import Organization
from app.models.user import User
from app.services.radar import build_radar

router = APIRouter(prefix="/api", tags=["radar"])


@router.get("/radar")
async def get_radar(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    organization = await db.get(Organization, current_user.organization_id)
    return await build_radar(db, organization)
