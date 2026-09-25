"""Targeted sync: refresh ONE issue or merge request from GitLab instead of re-reading the whole
project. This is what makes "sync on every event" affordable: a webhook, or one of Stanley's own
write actions, costs one or two API calls. Full reconciliation stays the safety net that fixes
anything this misses (PRD Section 11.1).

Uses the REST API for both kinds so it works on every GitLab version.
"""

from datetime import datetime, timezone

import httpx
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import MergeRequestState, PipelineStatus, ReviewState
from app.models.label import Label
from app.models.merge_request import MergeRequest
from app.models.merge_request_reviewer import MergeRequestReviewer
from app.models.milestone import Milestone
from app.models.synced_project import SyncedProject
from app.models.work_item import WorkItem
from app.sync.gid import parse_dt
from app.sync.gitlab_client import GitLabClient
from app.sync.mr_link_store import set_links
from app.sync.mr_links import linked_work_item_ids, referenced_issue_iids
from app.sync.reconciliation import _get_or_create_user_stub
from app.sync.reconciliation_rest import _rest_user_to_graphql_shape, _upsert_issues_rest

settings = get_settings()


async def _sync_issue(db: AsyncSession, project: SyncedProject, client: GitLabClient, iid: str) -> bool:
    issue = (await client.rest_get(f"/projects/{project.gitlab_project_id}/issues/{iid}")).json()

    milestone_id_by_gid = {
        gid: local_id
        for gid, local_id in (
            await db.execute(
                select(Milestone.gitlab_milestone_id, Milestone.id).where(Milestone.synced_project_id == project.id)
            )
        ).all()
    }
    label_id_by_name = {
        name: local_id
        for name, local_id in (
            await db.execute(select(Label.name, Label.id).where(Label.synced_project_id == project.id))
        ).all()
    }
    await _upsert_issues_rest(db, project, [issue], milestone_id_by_gid, label_id_by_name)
    return True


async def _sync_merge_request(db: AsyncSession, project: SyncedProject, client: GitLabClient, iid: str) -> bool:
    base = f"/projects/{project.gitlab_project_id}/merge_requests/{iid}"
    mr = (await client.rest_get(base)).json()

    approved_by: list[dict] = []
    try:
        approved_by = (await client.rest_get(f"{base}/approvals")).json().get("approved_by", [])
    except httpx.HTTPError:
        pass  # approvals are a nicety; the MR itself is what matters
    approved_ids = {str((entry.get("user") or {}).get("id")) for entry in approved_by}

    referenced = referenced_issue_iids(mr.get("title"), mr.get("description"))
    work_item_id_by_iid = {}
    if referenced:
        work_item_id_by_iid = {
            gitlab_iid: wid
            for wid, gitlab_iid in (
                await db.execute(
                    select(WorkItem.id, WorkItem.gitlab_iid)
                    .where(WorkItem.synced_project_id == project.id)
                    .where(WorkItem.gitlab_iid.in_(referenced))
                )
            ).all()
        }

    author = await _get_or_create_user_stub(db, project.organization_id, _rest_user_to_graphql_shape(mr.get("author")))

    state = mr["state"]
    mr_state = (
        MergeRequestState.MERGED
        if state == "merged"
        else MergeRequestState.CLOSED
        if state == "closed"
        else MergeRequestState.OPENED
    )
    pipeline = mr.get("head_pipeline") or mr.get("pipeline") or {}
    try:
        pipeline_status = PipelineStatus(pipeline["status"].lower()) if pipeline.get("status") else None
    except ValueError:
        pipeline_status = None

    values = dict(
        synced_project_id=project.id,
        gitlab_global_id=str(mr["id"]),
        gitlab_iid=str(mr["iid"]),
        title=mr["title"],
        state=mr_state,
        is_draft=bool(mr.get("draft") or mr.get("work_in_progress")),
        web_url=mr["web_url"],
        author_user_id=author.id if author else None,
        pipeline_status=pipeline_status,
        has_unresolved_threads=False,
        approvals_required=None,
        approvals_received=1 if approved_ids else 0,
        gitlab_created_at=parse_dt(mr["created_at"]),
        gitlab_updated_at=parse_dt(mr["updated_at"]),
        merged_at=parse_dt(mr.get("merged_at")),
        last_activity_at=parse_dt(mr["updated_at"]),
    )
    merge_request_id = (
        await db.execute(
            pg_insert(MergeRequest)
            .values(**values)
            .on_conflict_do_update(index_elements=[MergeRequest.gitlab_global_id], set_=values)
            .returning(MergeRequest.id)
        )
    ).scalar_one()

    await set_links(db, merge_request_id, linked_work_item_ids(mr.get("title"), mr.get("description"), work_item_id_by_iid))

    current_reviewer_ids = []
    for reviewer_json in mr.get("reviewers") or []:
        reviewer = await _get_or_create_user_stub(db, project.organization_id, _rest_user_to_graphql_shape(reviewer_json))
        if not reviewer:
            continue
        current_reviewer_ids.append(reviewer.id)
        reviewer_state = ReviewState.APPROVED if reviewer.gitlab_user_id in approved_ids else ReviewState.REQUESTED
        await db.execute(
            pg_insert(MergeRequestReviewer)
            .values(merge_request_id=merge_request_id, user_id=reviewer.id, state=reviewer_state)
            .on_conflict_do_update(
                index_elements=[MergeRequestReviewer.merge_request_id, MergeRequestReviewer.user_id],
                set_={"state": reviewer_state},
            )
        )
    await db.execute(
        delete(MergeRequestReviewer)
        .where(MergeRequestReviewer.merge_request_id == merge_request_id)
        .where(MergeRequestReviewer.user_id.notin_(current_reviewer_ids))
    )
    return True


async def sync_single_item(db: AsyncSession, project: SyncedProject, kind: str, iid: str) -> bool:
    """Refresh one issue ("issue") or merge request ("merge_request"). Returns False if GitLab no
    longer has it (deleted or not visible); the next reconciliation deals with that."""
    client = GitLabClient(access_token=settings.gitlab_sync_service_token)
    try:
        if kind == "issue":
            await _sync_issue(db, project, client, iid)
        elif kind == "merge_request":
            await _sync_merge_request(db, project, client, iid)
        else:
            raise ValueError(f"Unknown sync target kind: {kind}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            await db.rollback()
            return False
        raise

    project.last_synced_at = datetime.now(timezone.utc)
    await db.commit()
    return True
