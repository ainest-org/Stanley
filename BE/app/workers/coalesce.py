"""Batches bursts of sync requests. Ten webhook events for the same merge request arriving
together should cost ONE fetch, not ten. The first event schedules the sync a moment later; the
rest see that a run is already pending and drop out. The task fetches fresh state when it runs
and clears the marker just before, so an event that lands mid-fetch schedules one more run.
"""

import logging

import redis
import redis.asyncio as aredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.synced_project import SyncedProject

logger = logging.getLogger(__name__)
MARKER_TTL_SECONDS = 60  # safety net so a lost task can't block syncs forever


def targeted_key(project_id: str, kind: str, iid: str) -> str:
    return f"sync:{project_id}:{kind}:{iid}"


def project_key(project_id: str) -> str:
    return f"sync:{project_id}:all"


def clear_marker(key: str) -> None:
    try:
        redis.Redis.from_url(get_settings().redis_url).delete(key)
    except redis.RedisError:
        pass


async def _claim(key: str) -> bool:
    """True if nobody already has a run pending for this key. Fails open if Redis is down."""
    try:
        client = aredis.from_url(get_settings().redis_url)
        return bool(await client.set(key, "1", nx=True, ex=MARKER_TTL_SECONDS))
    except redis.RedisError:
        return True


async def enqueue_targeted(project_id: str, kind: str, iid: str, delay: float = 2) -> bool:
    """Queue a refresh of one issue / merge request. Returns False if one was already pending."""
    from app.workers.tasks import sync_single_item_task

    try:
        if not await _claim(targeted_key(project_id, kind, iid)):
            return False
        sync_single_item_task.schedule(args=(project_id, kind, str(iid)), delay=delay)
        return True
    except Exception:  # noqa: BLE001 - never fail a write that already succeeded in GitLab
        logger.warning("Could not queue a sync for %s %s; the periodic sync will catch it", kind, iid)
        return False


async def enqueue_project(project_id: str, delay: float = 1) -> bool:
    """Queue a full re-read of one project. Returns False if one was already pending."""
    from app.workers.tasks import reconcile_one_project

    try:
        if not await _claim(project_key(project_id)):
            return False
        reconcile_one_project.schedule(args=(project_id,), delay=delay)
        return True
    except Exception:  # noqa: BLE001
        logger.warning("Could not queue a sync for project %s", project_id)
        return False


async def enqueue_all_active(db: AsyncSession) -> int:
    ids = (await db.execute(select(SyncedProject.id).where(SyncedProject.is_active.is_(True)))).scalars().all()
    queued = 0
    for project_id in ids:
        if await enqueue_project(str(project_id)):
            queued += 1
    return queued
