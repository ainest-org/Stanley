from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.synced_project import SyncedProject
from app.models.user import User
from app.workers.coalesce import enqueue_all_active

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/status")
async def sync_status(_: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """How fresh the data is. `oldest` is the least recently synced active project, which is the
    honest "as of" time for anything that spans projects."""
    synced_at = (
        await db.execute(select(SyncedProject.last_synced_at).where(SyncedProject.is_active.is_(True)))
    ).scalars().all()
    known = [t for t in synced_at if t is not None]
    return {
        "projects": len(synced_at),
        "never_synced": len(synced_at) - len(known),
        "oldest": min(known).isoformat() if known and len(known) == len(synced_at) else None,
        "newest": max(known).isoformat() if known else None,
    }


@router.post("/refresh")
async def refresh(_: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    """Re-read every active project now (PRD Section 11.1, on-demand refresh). Repeated clicks are
    harmless: a project that already has a refresh pending isn't queued again."""
    queued = await enqueue_all_active(db)
    return {"queued": queued, "requested_at": datetime.now(timezone.utc).isoformat()}
