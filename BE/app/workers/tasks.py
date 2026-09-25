import logging
import uuid

from huey import crontab
from sqlalchemy import select

from app.models.synced_project import SyncedProject
from app.sync.gitlab_client import GitLabRateLimited
from app.sync.reconciliation import reconcile_project
from app.workers.async_utils import run_async, worker_session
from app.workers.huey_app import huey

logger = logging.getLogger(__name__)

# Staggering window for the periodic tick (PRD Section 13.1: "staggers polling windows rather
# than hammering all projects on the same tick"). Spreads N projects evenly across ~10 minutes
# of the 15-minute cycle, leaving headroom before the next tick fires.
STAGGER_WINDOW_SECONDS = 600
MAX_BACKOFF_SECONDS = 3600


@huey.periodic_task(crontab(minute="*/15"))
def reconcile_synced_projects() -> None:
    """Fan-out entrypoint for the 15-minute reconciliation fallback (PRD Section 11.1). Reads
    the list of active projects synchronously and schedules one `reconcile_one_project` task
    per project, staggered, so a rate limit on one project's poll doesn't couple to another's."""
    run_async(_enqueue_reconciliation_for_active_projects())


async def _enqueue_reconciliation_for_active_projects() -> None:
    async with worker_session() as db:
        result = await db.execute(select(SyncedProject.id).where(SyncedProject.is_active.is_(True)))
        project_ids = [str(row) for row in result.scalars().all()]

    if not project_ids:
        return

    stagger_step = STAGGER_WINDOW_SECONDS / len(project_ids)
    for index, project_id in enumerate(project_ids):
        reconcile_one_project.schedule(args=(project_id,), delay=index * stagger_step)


@huey.task()
def reconcile_one_project(project_id: str, attempt: int = 0) -> None:
    """Reconciles a single project (PRD Section 11.1). On a 429 from GitLab, backs off
    exponentially per-project (Section 13.1) instead of retrying immediately or failing the
    whole batch."""
    try:
        run_async(_reconcile_one_project_async(project_id))
    except GitLabRateLimited as exc:
        backoff = min(exc.retry_after_seconds * (2**attempt), MAX_BACKOFF_SECONDS)
        logger.warning("GitLab rate-limited reconciliation for project %s; retrying in %ss", project_id, backoff)
        run_async(_record_backoff(project_id, backoff))
        reconcile_one_project.schedule(args=(project_id, attempt + 1), delay=backoff)


async def _reconcile_one_project_async(project_id: str) -> None:
    async with worker_session() as db:
        project = await db.get(SyncedProject, uuid.UUID(project_id))
        if project is None or not project.is_active:
            return
        await reconcile_project(db, project)


async def _record_backoff(project_id: str, backoff_seconds: int) -> None:
    async with worker_session() as db:
        project = await db.get(SyncedProject, uuid.UUID(project_id))
        if project is None:
            return
        project.reconciliation_backoff_seconds = backoff_seconds
        await db.commit()


@huey.task()
def process_gitlab_webhook(synced_project_id: str, object_kind: str) -> None:
    """Handle an inbound GitLab webhook event (PRD Section 11.1 primary path). Rather than
    hand-parsing every event shape (work item / issue / MR / pipeline) into a partial update,
    this triggers an immediate full reconciliation of the one project the event came from —
    correctness over micro-efficiency; Section 13.1 already treats reconciliation as the
    ground truth, so routing webhooks through the same path can't introduce drift.

    TODO: once volume warrants it, add a lighter-weight targeted upsert per `object_kind`
    instead of a full project re-pull.
    """
    logger.info("Processing GitLab webhook (%s) for project %s", object_kind, synced_project_id)
    run_async(_reconcile_one_project_async(synced_project_id))


@huey.periodic_task(crontab(minute="0", hour="9", day_of_week="1"))
def send_weekly_digest() -> None:
    """Weekly digest email/Slack push (PRD Section 10.2). TODO: implement once Radar/report
    data assembly (Section 8, 10.2) is built."""
