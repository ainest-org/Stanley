"""Builds the My Work feed (PRD Section 6): one unified view per engineer, bucketed into
Doing now / Up next / Waiting on someone else / Review requests — never a manually-set status,
always inferred from real GitLab state (Section 6.5).

Simplification, since GitLab issues have no native "in progress" state: a work item counts as
"doing now" only via a linked in-progress MR of mine; there's no label-based in-progress
inference yet (that would need the label-mapping engine from Section 5.2 step 4, not built).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blocked_flag import BlockedFlag
from app.models.enums import MergeRequestState, ReviewState, WorkItemState
from app.models.enums import PipelineStatus
from app.models.merge_request import MergeRequest
from app.models.merge_request_reviewer import MergeRequestReviewer
from app.models.organization import Organization
from app.models.synced_project import SyncedProject
from app.models.user import User
from app.models.work_item import WorkItem
from app.services.health import is_work_item_flagged, mr_status_badge


def _work_item_card(item: WorkItem, project_name: str, linked_mr: MergeRequest | None, blocked_reason: str | None, org: Organization) -> dict:
    return {
        "kind": "work_item",
        "id": str(item.id),
        "title": item.title,
        "project_name": project_name,
        "web_url": item.web_url,
        "mr_status": mr_status_badge(linked_mr),
        "last_activity_at": item.last_activity_at.isoformat(),
        "is_flagged": is_work_item_flagged(item.last_activity_at, linked_mr, org, blocked_reason is not None),
        "blocked_reason": blocked_reason,
    }


def _mr_card(mr: MergeRequest, project_name: str) -> dict:
    return {
        "kind": "merge_request",
        "id": str(mr.id),
        "title": mr.title,
        "project_name": project_name,
        "web_url": mr.web_url,
        "mr_status": mr_status_badge(mr),
        "last_activity_at": mr.last_activity_at.isoformat(),
        "is_flagged": mr.pipeline_status == PipelineStatus.FAILED,
        "blocked_reason": None,
    }


async def build_my_work(db: AsyncSession, user: User, org: Organization) -> dict:
    project_names = dict(
        (row[0], row[1])
        for row in (await db.execute(select(SyncedProject.id, SyncedProject.name))).all()
    )

    my_open_items = (
        (
            await db.execute(
                select(WorkItem)
                .where(WorkItem.assignee_user_id == user.id)
                .where(WorkItem.state == WorkItemState.OPENED)
            )
        )
        .scalars()
        .all()
    )

    active_blocked_reason_by_item_id: dict = {}
    if my_open_items:
        result = await db.execute(
            select(BlockedFlag.work_item_id, BlockedFlag.reason)
            .where(BlockedFlag.work_item_id.in_([i.id for i in my_open_items]))
            .where(BlockedFlag.resolved_at.is_(None))
            .order_by(BlockedFlag.created_at.desc())
        )
        for work_item_id, reason in result.all():
            active_blocked_reason_by_item_id.setdefault(work_item_id, reason)

    mrs_by_work_item_id: dict = {}
    if my_open_items:
        result = await db.execute(
            select(MergeRequest)
            .where(MergeRequest.work_item_id.in_([i.id for i in my_open_items]))
            .where(MergeRequest.author_user_id == user.id)
            .order_by(MergeRequest.last_activity_at.desc())
        )
        for mr in result.scalars().all():
            mrs_by_work_item_id.setdefault(mr.work_item_id, mr)

    doing_now: list[dict] = []
    up_next: list[dict] = []
    waiting_on_others: list[dict] = []

    for item in my_open_items:
        project_name = project_names.get(item.synced_project_id, "Unknown project")
        linked_mr = mrs_by_work_item_id.get(item.id)
        blocked_reason = active_blocked_reason_by_item_id.get(item.id)
        card = _work_item_card(item, project_name, linked_mr, blocked_reason, org)

        if linked_mr is not None and linked_mr.state == MergeRequestState.OPENED and not linked_mr.is_draft:
            waiting_on_others.append(card)
        elif linked_mr is not None and linked_mr.state == MergeRequestState.OPENED and linked_mr.is_draft:
            doing_now.append(card)
        elif blocked_reason is not None:
            waiting_on_others.append(card)
        else:
            up_next.append(card)

    # MRs I authored that aren't linked to one of my own assigned work items (e.g. a quick fix
    # with no issue) still belong in "waiting on someone else" once they're open for review.
    linked_work_item_ids = {i.id for i in my_open_items}
    result = await db.execute(
        select(MergeRequest)
        .where(MergeRequest.author_user_id == user.id)
        .where(MergeRequest.state == MergeRequestState.OPENED)
        .where(MergeRequest.is_draft.is_(False))
    )
    for mr in result.scalars().all():
        if mr.work_item_id in linked_work_item_ids:
            continue  # already represented via its work item card above
        project_name = project_names.get(mr.synced_project_id, "Unknown project")
        waiting_on_others.append(_mr_card(mr, project_name))

    result = await db.execute(
        select(MergeRequest, MergeRequestReviewer)
        .join(MergeRequestReviewer, MergeRequestReviewer.merge_request_id == MergeRequest.id)
        .where(MergeRequestReviewer.user_id == user.id)
        .where(MergeRequestReviewer.state == ReviewState.REQUESTED)
        .where(MergeRequest.state == MergeRequestState.OPENED)
    )
    review_requests = [
        _mr_card(mr, project_names.get(mr.synced_project_id, "Unknown project")) for mr, _ in result.all()
    ]

    return {
        "doing_now": doing_now,
        "up_next": up_next,
        "waiting_on_others": waiting_on_others,
        "review_requests": review_requests,
    }
