import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.synced_project import SyncedProject

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

    # Deferred import: avoids importing the Huey/Redis stack into every request-handling
    # process path that merely imports app.api.webhooks.
    from app.workers.tasks import process_gitlab_webhook

    process_gitlab_webhook(str(project.id), object_kind)

    return {"ok": True}
