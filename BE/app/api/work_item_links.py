"""Connect work items to merge requests (many MRs per item) and to milestones."""

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.tokens import get_valid_access_token, get_write_access_token
from app.db.session import get_db
from app.models.enums import MergeRequestState
from app.models.merge_request import MergeRequest, merge_request_work_items
from app.models.milestone import Milestone
from app.models.synced_project import SyncedProject
from app.models.user import User
from app.models.work_item import WorkItem
from app.services.access import can_manage_milestones
from app.sync.gitlab_client import GitLabClient
from app.sync.mr_link_store import set_links
from app.sync.link_mutations import set_issue_milestone, update_merge_request_references
from app.sync.mr_links import referenced_issue_iids

router = APIRouter(prefix="/api", tags=["work-item-links"])


def _gitlab_rejected(exc: httpx.HTTPStatusError) -> HTTPException:
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY, f"GitLab rejected this ({exc.response.status_code}): {exc.response.text}"
    )


async def _item_project_and_mr(db: AsyncSession, work_item_id: uuid.UUID, merge_request_id: uuid.UUID):
    item = await db.get(WorkItem, work_item_id)
    mr = await db.get(MergeRequest, merge_request_id)
    if item is None or mr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work item or merge request not found")
    if item.synced_project_id != mr.synced_project_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "The merge request must be in the same project as the work item"
        )
    project = await db.get(SyncedProject, item.synced_project_id)
    return item, mr, project


async def _relink(db: AsyncSession, project: SyncedProject, mr: MergeRequest, title: str, description: str) -> set:
    """Recompute the MR's links from its new text, exactly as the next reconciliation will."""
    iids = referenced_issue_iids(title, description)
    ids: list = []
    if iids:
        rows = (
            await db.execute(
                select(WorkItem.id, WorkItem.gitlab_iid)
                .where(WorkItem.synced_project_id == project.id)
                .where(WorkItem.gitlab_iid.in_(iids))
            )
        ).all()
        by_iid = {iid: wid for wid, iid in rows}
        ids = [by_iid[i] for i in iids if i in by_iid]
    await set_links(db, mr.id, ids)
    await db.commit()
    return set(ids)


async def _local_linkable(db: AsyncSession, item: WorkItem, current_user: User) -> list[dict]:
    """Fallback when GitLab can't be reached: the synced open MRs not yet linked to this item."""
    rows = (
        await db.execute(
            select(MergeRequest, User.name, User.gitlab_user_id)
            .join(User, User.id == MergeRequest.author_user_id, isouter=True)
            .where(MergeRequest.synced_project_id == item.synced_project_id)
            .where(MergeRequest.state == MergeRequestState.OPENED)
            .where(
                ~exists()
                .where(merge_request_work_items.c.merge_request_id == MergeRequest.id)
                .where(merge_request_work_items.c.work_item_id == item.id)
            )
            .order_by(MergeRequest.last_activity_at.desc())
            .limit(50)
        )
    ).all()
    return [
        {
            "iid": mr.gitlab_iid,
            "title": mr.title,
            "author": author_name,
            "mine": mr.author_user_id == current_user.id,
            "web_url": mr.web_url,
            "synced": True,
        }
        for mr, author_name, _ in rows
    ]


@router.get("/work-items/{work_item_id}/linkable-merge-requests")
async def linkable_merge_requests(
    work_item_id: uuid.UUID,
    search: str = "",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Open merge requests in the item's project that the signed-in user can see in GitLab (read
    live with their own token), minus the ones that already reference this item. Falls back to the
    synced copy if GitLab can't be reached."""
    item = await db.get(WorkItem, work_item_id)
    project = await db.get(SyncedProject, item.synced_project_id) if item else None
    if item is None or project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work item not found")

    access_token, _ = await get_valid_access_token(db, current_user)

    synced_iids = set(
        (await db.execute(select(MergeRequest.gitlab_iid).where(MergeRequest.synced_project_id == project.id)))
        .scalars()
        .all()
    )
    linked_iids = set(
        (
            await db.execute(
                select(MergeRequest.gitlab_iid)
                .join(merge_request_work_items, merge_request_work_items.c.merge_request_id == MergeRequest.id)
                .where(merge_request_work_items.c.work_item_id == item.id)
            )
        )
        .scalars()
        .all()
    )

    live_error = None
    rows: list[dict] = []
    try:
        params: dict = {"state": "opened", "scope": "all", "order_by": "updated_at", "per_page": 50}
        if search.strip():
            params["search"] = search.strip()
        merge_requests = (
            await GitLabClient(access_token=access_token).rest_get(
                f"/projects/{project.gitlab_project_id}/merge_requests", params
            )
        ).json()
        for mr in merge_requests:
            iid = str(mr["iid"])
            if iid in linked_iids or item.gitlab_iid in referenced_issue_iids(mr.get("title"), mr.get("description")):
                continue
            author = mr.get("author") or {}
            rows.append(
                {
                    "iid": iid,
                    "title": mr["title"],
                    "author": author.get("name"),
                    "mine": str(author.get("id")) == current_user.gitlab_user_id,
                    "web_url": mr["web_url"],
                    "synced": iid in synced_iids,
                }
            )
    except httpx.HTTPStatusError as exc:
        live_error = f"GitLab returned {exc.response.status_code} when listing merge requests; showing the synced copy."
        rows = await _local_linkable(db, item, current_user)
    except httpx.HTTPError:
        live_error = "GitLab couldn't be reached; showing the synced copy."
        rows = await _local_linkable(db, item, current_user)

    return {
        "project_name": project.name,
        "live_error": live_error,
        "merge_requests": sorted(rows, key=lambda r: not r["mine"]),
    }


class LinkMergeRequestRequest(BaseModel):
    gitlab_iid: str
    closes: bool = False


@router.post("/work-items/{work_item_id}/merge-requests")
async def link_merge_request(
    work_item_id: uuid.UUID,
    body: LinkMergeRequestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = await db.get(WorkItem, work_item_id)
    project = await db.get(SyncedProject, item.synced_project_id) if item else None
    if item is None or project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work item not found")

    access_token = await get_write_access_token(db, current_user)
    try:
        title, description = await update_merge_request_references(
            project, body.gitlab_iid, item.gitlab_iid, access_token, link=True, closes=body.closes
        )
    except httpx.HTTPStatusError as exc:
        raise _gitlab_rejected(exc) from exc

    mr = (
        await db.execute(
            select(MergeRequest)
            .where(MergeRequest.synced_project_id == project.id)
            .where(MergeRequest.gitlab_iid == body.gitlab_iid)
        )
    ).scalar_one_or_none()

    if mr is not None:
        linked_ids = await _relink(db, project, mr, title, description)
        linked = item.id in linked_ids
        return {
            "ok": True,
            "linked_to_this_item": linked,
            "note": None
            if linked
            else "GitLab accepted the change but the link was not detected; it will appear after the next sync.",
        }

    # Not synced into Stanley yet: the reference is already in GitLab, so pull just that merge
    # request in right away.
    from app.workers.coalesce import enqueue_targeted

    try:
        await enqueue_targeted(str(project.id), "merge_request", body.gitlab_iid, delay=0)
    except Exception:  # noqa: BLE001 - best effort; the periodic sync will catch it anyway
        pass
    return {
        "ok": True,
        "linked_to_this_item": False,
        "note": "Linked in GitLab. This merge request wasn't in Stanley yet; it's being pulled in now, so reload in a few seconds.",
    }


@router.delete("/work-items/{work_item_id}/merge-requests/{merge_request_id}")
async def unlink_merge_request(
    work_item_id: uuid.UUID,
    merge_request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item, mr, project = await _item_project_and_mr(db, work_item_id, merge_request_id)
    access_token = await get_write_access_token(db, current_user)
    try:
        title, description = await update_merge_request_references(
            project, mr.gitlab_iid, item.gitlab_iid, access_token, link=False
        )
    except httpx.HTTPStatusError as exc:
        raise _gitlab_rejected(exc) from exc

    linked_ids = await _relink(db, project, mr, title, description)
    still_linked = item.id in linked_ids
    return {
        "ok": True,
        "still_linked": still_linked,
        "note": (
            "The merge request title or description still mentions this item elsewhere. "
            "Edit it in GitLab to remove the link."
        )
        if still_linked
        else None,
    }


class SetMilestoneRequest(BaseModel):
    milestone_id: uuid.UUID | None = None


@router.patch("/work-items/{work_item_id}/milestone")
async def set_work_item_milestone(
    work_item_id: uuid.UUID,
    body: SetMilestoneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Only project Maintainers and Owners can (re)assign milestones. That's checked against the
    GitLab access level Stanley synced, on top of GitLab's own enforcement (PRD Section 12)."""
    item = await db.get(WorkItem, work_item_id)
    project = await db.get(SyncedProject, item.synced_project_id) if item else None
    if item is None or project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work item not found")

    if not await can_manage_milestones(db, current_user, project.id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only project Maintainers and Owners can change a work item's milestone."
        )

    milestone = None
    if body.milestone_id:
        milestone = await db.get(Milestone, body.milestone_id)
        if milestone is None or milestone.synced_project_id != project.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "That milestone is not in this item's project")

    access_token = await get_write_access_token(db, current_user)
    try:
        await set_issue_milestone(
            project, item.gitlab_iid, int(milestone.gitlab_milestone_id) if milestone else None, access_token
        )
    except httpx.HTTPStatusError as exc:
        raise _gitlab_rejected(exc) from exc

    item.milestone_id = milestone.id if milestone else None
    await db.commit()
    return {"ok": True, "milestone_id": str(milestone.id) if milestone else None}
