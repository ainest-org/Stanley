"""Personal dashboard endpoints: overview stats, watch/snooze, GitLab To-Dos, daily check-in."""

import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.tokens import get_valid_access_token, get_write_access_token
from app.db.session import get_db
from app.models.check_in import CheckIn
from app.models.merge_request import MergeRequest
from app.models.organization import Organization
from app.models.synced_project import SyncedProject
from app.models.user import User
from app.models.user_item_preference import UserItemPreference
from app.models.work_item import WorkItem
from app.services.my_overview import build_overview, recent_activity
from app.services.my_work import build_my_work
from app.sync.gitlab_client import GitLabClient

router = APIRouter(prefix="/api", tags=["my-dashboard"])


@router.get("/my-work/overview")
async def get_overview(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    organization = await db.get(Organization, current_user.organization_id)
    return await build_overview(db, current_user, organization)


# ---------------------------------------------------------------------------
# Watch / snooze (private to the person, never written to GitLab)
# ---------------------------------------------------------------------------


class PreferenceUpdate(BaseModel):
    watching: bool | None = None
    snoozed_until: datetime | None = None


@router.put("/work-items/{work_item_id}/preferences")
async def update_preferences(
    work_item_id: uuid.UUID,
    body: PreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send only what changes: `watching`, and/or `snoozed_until` (null clears a snooze)."""
    if await db.get(WorkItem, work_item_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work item not found")

    pref = (
        await db.execute(
            select(UserItemPreference)
            .where(UserItemPreference.user_id == current_user.id)
            .where(UserItemPreference.work_item_id == work_item_id)
        )
    ).scalar_one_or_none()
    if pref is None:
        pref = UserItemPreference(user_id=current_user.id, work_item_id=work_item_id, watching=False)
        db.add(pref)

    if "watching" in body.model_fields_set and body.watching is not None:
        pref.watching = body.watching
    if "snoozed_until" in body.model_fields_set:
        pref.snoozed_until = body.snoozed_until
    await db.commit()
    return {
        "watching": pref.watching,
        "snoozed_until": pref.snoozed_until.isoformat() if pref.snoozed_until else None,
    }


# ---------------------------------------------------------------------------
# GitLab To-Dos inbox, read live as the user (mentions, replies, review requests...)
# ---------------------------------------------------------------------------


@router.get("/todos")
async def list_todos(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    access_token, _ = await get_valid_access_token(db, current_user)
    client = GitLabClient(access_token=access_token)
    try:
        todos = (await client.rest_get("/todos", {"state": "pending", "per_page": 30})).json()
    except httpx.HTTPStatusError as exc:
        return {"todos": [], "live_error": f"GitLab returned {exc.response.status_code} for your To-Do list."}
    except httpx.HTTPError:
        return {"todos": [], "live_error": "GitLab couldn't be reached."}

    projects = {p.gitlab_project_id: p for p in (await db.execute(select(SyncedProject))).scalars().all()}
    result = []
    for todo in todos:
        target = todo.get("target") or {}
        project = projects.get(str((todo.get("project") or {}).get("id")))
        target_type = todo.get("target_type")
        iid = str(target.get("iid")) if target.get("iid") is not None else None

        work_item_id = merge_request_id = None
        if project and iid:
            if target_type in ("Issue", "WorkItem"):
                work_item_id = (
                    await db.execute(
                        select(WorkItem.id)
                        .where(WorkItem.synced_project_id == project.id)
                        .where(WorkItem.gitlab_iid == iid)
                    )
                ).scalar_one_or_none()
            elif target_type == "MergeRequest":
                merge_request_id = (
                    await db.execute(
                        select(MergeRequest.id)
                        .where(MergeRequest.synced_project_id == project.id)
                        .where(MergeRequest.gitlab_iid == iid)
                    )
                ).scalar_one_or_none()

        result.append(
            {
                "id": str(todo["id"]),
                "action": todo.get("action_name", ""),
                "target_type": target_type,
                "title": target.get("title") or todo.get("body", ""),
                "body": todo.get("body", ""),
                "author": (todo.get("author") or {}).get("name"),
                "project": (todo.get("project") or {}).get("name_with_namespace"),
                "url": todo.get("target_url"),
                "created_at": todo.get("created_at"),
                "work_item_id": str(work_item_id) if work_item_id else None,
                "merge_request_id": str(merge_request_id) if merge_request_id else None,
            }
        )
    return {"todos": result, "live_error": None}


@router.post("/todos/{todo_id}/done")
async def mark_todo_done(
    todo_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    access_token = await get_write_access_token(db, current_user)
    try:
        await GitLabClient(access_token=access_token).rest_post(f"/todos/{todo_id}/mark_as_done")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"GitLab rejected this ({exc.response.status_code})") from exc
    return {"ok": True}


@router.post("/todos/done-all")
async def mark_all_todos_done(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    access_token = await get_write_access_token(db, current_user)
    try:
        await GitLabClient(access_token=access_token).rest_post("/todos/mark_as_done")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"GitLab rejected this ({exc.response.status_code})") from exc
    return {"ok": True}


# ---------------------------------------------------------------------------
# Daily check-in: opt-in, pre-filled from real GitLab activity (PRD Section 10.1)
# ---------------------------------------------------------------------------


class CheckInBody(BaseModel):
    did: str = ""
    doing: str = ""
    blockers: str = ""


def _today() -> date:
    return datetime.now(timezone.utc).date()


async def _prefill(db: AsyncSession, user: User) -> dict:
    org = await db.get(Organization, user.organization_id)
    today = datetime.now(timezone.utc)
    lookback_days = 3 if today.weekday() == 0 else 1  # Monday covers the weekend
    since = today - timedelta(days=lookback_days)

    labels = {"merged": "Merged", "opened": "Opened MR", "closed": "Closed"}
    did = "\n".join(f"- {labels[e['kind']]}: {e['title']}" for e in await recent_activity(db, user, since, limit=10))

    buckets = await build_my_work(db, user, org)
    doing = "\n".join(f"- {c['title']}" for c in [*buckets["doing_now"], *buckets["waiting_on_others"]][:8])
    blockers = "\n".join(
        f"- {c['title']}: {c['blocked_reason']}" for c in buckets["waiting_on_others"] if c.get("blocked_reason")
    )
    return {"did": did, "doing": doing, "blockers": blockers}


@router.get("/check-ins/today")
async def get_today_check_in(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    existing = (
        await db.execute(
            select(CheckIn).where(CheckIn.user_id == current_user.id).where(CheckIn.check_in_date == _today())
        )
    ).scalar_one_or_none()
    return {
        "date": _today().isoformat(),
        "submitted": existing is not None and not existing.skipped,
        "skipped": existing is not None and existing.skipped,
        "saved": {"did": existing.did_text, "doing": existing.doing_text, "blockers": existing.blockers_text}
        if existing and not existing.skipped
        else None,
        "prefill": await _prefill(db, current_user),
    }


async def _upsert_check_in(db: AsyncSession, user: User, **fields) -> CheckIn:
    check_in = (
        await db.execute(select(CheckIn).where(CheckIn.user_id == user.id).where(CheckIn.check_in_date == _today()))
    ).scalar_one_or_none()
    if check_in is None:
        check_in = CheckIn(user_id=user.id, check_in_date=_today())
        db.add(check_in)
    for key, value in fields.items():
        setattr(check_in, key, value)
    await db.commit()
    return check_in


@router.put("/check-ins/today")
async def save_today_check_in(
    body: CheckInBody, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    await _upsert_check_in(
        db, current_user, did_text=body.did, doing_text=body.doing, blockers_text=body.blockers, skipped=False
    )
    return {"ok": True}


@router.post("/check-ins/today/skip")
async def skip_today_check_in(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Skipping never blocks or flags anyone (PRD Section 10.1)."""
    await _upsert_check_in(db, current_user, skipped=True, did_text=None, doing_text=None, blockers_text=None)
    return {"ok": True}
