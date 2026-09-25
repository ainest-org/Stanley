import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.models.synced_project import SyncedProject
from app.models.user import InToolRole, User
from app.sync.gitlab_client import GitLabClient
from app.sync.webhook_registration import register_webhook, unregister_webhook

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])
settings = get_settings()


def _service_client() -> GitLabClient:
    if not settings.gitlab_sync_service_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "GITLAB_SYNC_SERVICE_TOKEN is not configured — set it in BE/.env before connecting projects.",
        )
    return GitLabClient(access_token=settings.gitlab_sync_service_token)


# ---------------------------------------------------------------------------
# Step 1 (Section 5.2): connection status for the configured GitLab instance
# ---------------------------------------------------------------------------


@router.get("/gitlab/status")
async def gitlab_status() -> dict:
    if not settings.gitlab_sync_service_token:
        return {
            "connected": False,
            "instance_url": settings.gitlab_instance_url,
            "error": "GITLAB_SYNC_SERVICE_TOKEN is not set",
        }

    client = GitLabClient(access_token=settings.gitlab_sync_service_token)
    try:
        response = await client.rest_get("/version")
    except Exception as exc:  # noqa: BLE001 — surfaced as a status field, not a 500
        return {"connected": False, "instance_url": settings.gitlab_instance_url, "error": str(exc)}

    body = response.json()
    return {
        "connected": True,
        "instance_url": settings.gitlab_instance_url,
        "version": body.get("version"),
    }


# ---------------------------------------------------------------------------
# Step 2 (Section 5.2): browse GitLab projects, pick which ones to sync
# ---------------------------------------------------------------------------


@router.get("/gitlab/projects")
async def list_gitlab_projects(search: str = "", db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Projects visible to the sync service account (Section 5.2 step 2's checklist source)."""
    client = _service_client()
    response = await client.rest_get(
        "/projects", {"membership": "true", "search": search, "per_page": 50, "order_by": "name", "simple": "true"}
    )

    result = await db.execute(select(SyncedProject.gitlab_project_id))
    synced_ids = {row for row in result.scalars().all()}

    return [
        {
            "gitlab_project_id": str(item["id"]),
            "name": item["name"],
            "full_path": item["path_with_namespace"],
            "web_url": item["web_url"],
            "already_synced": str(item["id"]) in synced_ids,
        }
        for item in response.json()
    ]


def _serialize_synced_project(project: SyncedProject) -> dict:
    return {
        "id": str(project.id),
        "gitlab_project_id": project.gitlab_project_id,
        "name": project.name,
        "full_path": project.gitlab_full_path,
        "web_url": project.web_url,
        "is_active": project.is_active,
        "uses_work_items_api": project.uses_work_items_api,
        "webhook_registered": project.gitlab_webhook_id is not None,
        "last_synced_at": project.last_synced_at.isoformat() if project.last_synced_at else None,
        "last_reconciled_at": project.last_reconciled_at.isoformat() if project.last_reconciled_at else None,
    }


@router.get("/synced-projects")
async def list_synced_projects(
    current_user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    result = await db.execute(
        select(SyncedProject).where(SyncedProject.organization_id == current_user.organization_id)
    )
    return [_serialize_synced_project(p) for p in result.scalars().all()]


class SyncProjectRequest(BaseModel):
    gitlab_project_id: str


@router.post("/synced-projects", status_code=status.HTTP_201_CREATED)
async def sync_project(
    body: SyncProjectRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Adds a GitLab project to sync (PRD Section 5.2 step 2). Fetches the project, detects
    Work Items API support (Section 13.1 last row), registers a webhook (best-effort — sync
    still works via the 15-min reconciliation fallback if this fails, Section 11.1), and kicks
    off an immediate first reconciliation."""
    client = _service_client()

    result = await db.execute(
        select(SyncedProject).where(SyncedProject.gitlab_project_id == body.gitlab_project_id)
    )
    project = result.scalar_one_or_none()
    if project and project.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "This project is already synced")

    try:
        gitlab_project = (await client.rest_get(f"/projects/{body.gitlab_project_id}")).json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Could not fetch project from GitLab: {exc}") from exc

    if project is None:
        project = SyncedProject(
            organization_id=current_user.organization_id,
            gitlab_project_id=body.gitlab_project_id,
            gitlab_full_path=gitlab_project["path_with_namespace"],
            name=gitlab_project["name"],
            web_url=gitlab_project["web_url"],
        )
        db.add(project)
    else:
        # Re-syncing a previously unsynced project (Section 13.1: "Project/group unsynced by
        # admin mid-use" — its cached history isn't purged, just reactivated).
        project.is_active = True
        project.gitlab_full_path = gitlab_project["path_with_namespace"]
        project.name = gitlab_project["name"]
        project.web_url = gitlab_project["web_url"]

    await db.flush()
    project.uses_work_items_api = await client.supports_work_items_api(project.gitlab_full_path)
    await db.commit()
    await db.refresh(project)

    warnings: list[str] = []
    try:
        await register_webhook(db, project)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Webhook registration failed (sync will still work via periodic polling): {exc}")

    try:
        from app.workers.tasks import reconcile_one_project

        reconcile_one_project(str(project.id))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Could not queue the initial sync — is Redis running? ({exc})")

    return {"project": _serialize_synced_project(project), "warnings": warnings}


class UpdateSyncedProjectRequest(BaseModel):
    is_active: bool


@router.patch("/synced-projects/{project_id}")
async def update_synced_project(
    project_id: uuid.UUID,
    body: UpdateSyncedProjectRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    project = await db.get(SyncedProject, project_id)
    if project is None or project.organization_id != current_user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Synced project not found")

    was_active = project.is_active
    project.is_active = body.is_active
    await db.commit()
    await db.refresh(project)

    warnings: list[str] = []
    if was_active and not body.is_active:
        try:
            await unregister_webhook(db, project)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Could not remove the GitLab webhook (harmless if the project was already deleted): {exc}")
    elif not was_active and body.is_active:
        try:
            await register_webhook(db, project)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Webhook registration failed (sync will still work via periodic polling): {exc}")
        try:
            from app.workers.tasks import reconcile_one_project

            reconcile_one_project(str(project.id))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Could not queue the initial sync — is Redis running? ({exc})")

    return {"project": _serialize_synced_project(project), "warnings": warnings}


# ---------------------------------------------------------------------------
# Step 3 (Section 5.2): import members, assign in-tool roles
# ---------------------------------------------------------------------------


@router.get("/members")
async def list_members(current_user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Members auto-pulled from synced projects (via reconciliation's membership upsert) plus
    anyone who has already signed in (Section 5.2 step 3)."""
    result = await db.execute(select(User).where(User.organization_id == current_user.organization_id))
    users = result.scalars().all()

    return [
        {
            "id": str(user.id),
            "name": user.name,
            "gitlab_username": user.gitlab_username,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "in_tool_role": user.in_tool_role.value,
            "has_logged_in": user.encrypted_access_token is not None,
        }
        for user in users
    ]


class UpdateMemberRoleRequest(BaseModel):
    in_tool_role: InToolRole


@router.patch("/members/{user_id}")
async def update_member_role(
    user_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Sets a person's in-tool role explicitly (Section 5.2 step 3 / Section 3) — independent
    of whatever GitLab permission they happen to hold; never grants extra GitLab access."""
    user = await db.get(User, user_id)
    if user is None or user.organization_id != current_user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    user.in_tool_role = body.in_tool_role
    await db.commit()
    await db.refresh(user)

    return {
        "id": str(user.id),
        "name": user.name,
        "in_tool_role": user.in_tool_role.value,
    }


# ---------------------------------------------------------------------------
# Step 5 (Section 5.2): health-rule thresholds
# ---------------------------------------------------------------------------


def _serialize_settings(organization) -> dict:
    return {
        "stale_threshold_days": organization.stale_threshold_days,
        "stale_recheck_days": organization.stale_recheck_days,
        "blocked_recheck_days": organization.blocked_recheck_days,
        "review_sla_days": organization.review_sla_days,
        "overloaded_item_threshold": organization.overloaded_item_threshold,
    }


@router.get("/settings")
async def get_org_settings(current_user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> dict:
    from app.models.organization import Organization

    organization = await db.get(Organization, current_user.organization_id)
    return _serialize_settings(organization)


class UpdateSettingsRequest(BaseModel):
    stale_threshold_days: int | None = None
    stale_recheck_days: int | None = None
    blocked_recheck_days: int | None = None
    review_sla_days: int | None = None
    overloaded_item_threshold: int | None = None


@router.patch("/settings")
async def update_org_settings(
    body: UpdateSettingsRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.organization import Organization

    organization = await db.get(Organization, current_user.organization_id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(organization, field, value)

    await db.commit()
    await db.refresh(organization)
    return _serialize_settings(organization)
