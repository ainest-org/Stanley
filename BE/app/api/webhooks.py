import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.synced_project import SyncedProject
from app.sync.webhook_targets import webhook_target

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/gitlab/{synced_project_id}")
async def gitlab_webhook(
    synced_project_id: uuid.UUID,
    request: Request,
    x_gitlab_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receives GitLab's webhook events (PRD Section 11.1 primary sync path). Verifies the
    per-project secret token, then hands off to the background worker immediately — webhook
    receivers are expected to ack fast, so no sync processing happens on this request thread."""
    project = await db.get(SyncedProject, synced_project_id)
    if project is None or not project.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown or unsynced project")

    if not project.webhook_secret_token or x_gitlab_token != project.webhook_secret_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook token")

    payload = await request.json()
    object_kind = payload.get("object_kind", "unknown")

    # Deferred import: avoids pulling the Huey/Redis stack into every process that imports this module.
    from app.workers.coalesce import enqueue_project, enqueue_targeted

    target = webhook_target(payload)
    if target is not None:
        await enqueue_targeted(str(project.id), *target)
    elif object_kind not in ("pipeline", "push", "tag_push"):
        # An event we don't know how to narrow down: fall back to a (batched) project refresh.
        await enqueue_project(str(project.id), delay=2)

    return {"ok": True}
