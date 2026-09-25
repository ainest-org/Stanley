"""Registers/unregisters the GitLab project webhook a synced project relies on for the
near-real-time sync path (PRD Section 11.1). Called from the admin "select projects to sync"
flow (Section 5.2 step 2) when a project is added or removed from sync — that admin-facing
endpoint isn't built yet, but this is the piece it will call.
"""

import secrets

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.synced_project import SyncedProject
from app.sync.gitlab_client import GitLabClient

settings = get_settings()


async def register_webhook(db: AsyncSession, project: SyncedProject) -> None:
    client = GitLabClient(access_token=settings.gitlab_sync_service_token)
    secret_token = secrets.token_urlsafe(32)

    try:
        response = await client.rest_post(
            f"/projects/{project.gitlab_project_id}/hooks",
            json={
                "url": f"{settings.backend_base_url}/api/webhooks/gitlab/{project.id}",
                "token": secret_token,
                "issues_events": True,
                "merge_requests_events": True,
                "pipeline_events": True,
                "enable_ssl_verification": settings.app_env != "development",
            },
        )
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"GitLab returned {exc.response.status_code}: {exc.response.text}") from exc
    hook = response.json()

    project.gitlab_webhook_id = str(hook["id"])
    project.webhook_secret_token = secret_token
    await db.commit()


async def unregister_webhook(db: AsyncSession, project: SyncedProject) -> None:
    if not project.gitlab_webhook_id:
        return

    client = GitLabClient(access_token=settings.gitlab_sync_service_token)
    await client.rest_delete(f"/projects/{project.gitlab_project_id}/hooks/{project.gitlab_webhook_id}")

    project.gitlab_webhook_id = None
    project.webhook_secret_token = None
    await db.commit()
