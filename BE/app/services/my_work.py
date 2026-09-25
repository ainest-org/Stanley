"""Builds the My Work feed (PRD Section 6): one unified view per engineer, bucketed into
Doing now / Up next / Waiting on someone else / Review requests, plus the person's own
Watching and Snoozed lists. Status is always inferred from real GitLab state (Section 6.5).

Where an item lands (assigned to me, open), first match wins:
  1. Has my open MR that's a draft or has a failing pipeline      -> Doing now  (still my move)
  2. Has my open MR that's ready for review                       -> Waiting    (someone else's move)
  3. Carries the org's "in progress" label                        -> Doing now
  4. Has an active blocked flag                                   -> Waiting
  5. Otherwise                                                    -> Up next
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blocked_flag import BlockedFlag
from app.models.enums import MergeRequestState, PipelineStatus, ReviewState, WorkItemState
from app.models.label import Label
from app.models.merge_request import MergeRequest, merge_request_work_items
from app.models.merge_request_reviewer import MergeRequestReviewer
from app.models.milestone import Milestone
from app.models.organization import Organization
from app.models.synced_project import SyncedProject
from app.models.user import User
from app.models.user_item_preference import UserItemPreference
from app.models.work_item import WorkItem, work_item_labels
from app.services.health import is_work_item_flagged, mr_status_badge


def _work_item_card(
    item: WorkItem,
    project_name: str,
    linked_mr: MergeRequest | None,
    blocked_reason: str | None,
    org: Organization,
    *,
    labels: list[str],
    milestone_title: str | None,
    pref: UserItemPreference | None,
) -> dict:
    return {
        "kind": "work_item",
        "id": str(item.id),
        "title": item.title,
        "project_name": project_name,
        "web_url": item.web_url,
        "mr_status": mr_status_badge(linked_mr),
        "linked_mr_id": str(linked_mr.id) if linked_mr else None,
        "pipeline_url": f"{linked_mr.web_url}/pipelines" if linked_mr and linked_mr.pipeline_status else None,
        "labels": labels,
        "milestone_title": milestone_title,
        "watching": bool(pref and pref.watching),
        "snoozed_until": pref.snoozed_until.isoformat() if pref and pref.snoozed_until else None,
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
        "linked_mr_id": str(mr.id),
        "pipeline_url": f"{mr.web_url}/pipelines" if mr.pipeline_status else None,
        "labels": [],
        "milestone_title": None,
        "watching": False,
        "snoozed_until": None,
        "last_activity_at": mr.last_activity_at.isoformat(),
        "is_flagged": mr.pipeline_status == PipelineStatus.FAILED,
        "blocked_reason": None,
    }


def _my_mr_needs_me(mr: MergeRequest) -> bool:
    return mr.is_draft or mr.pipeline_status == PipelineStatus.FAILED


async def build_my_work(db: AsyncSession, user: User, org: Organization) -> dict:
    now = datetime.now(timezone.utc)
    project_names = dict(
        (row[0], row[1]) for row in (await db.execute(select(SyncedProject.id, SyncedProject.name))).all()
    )

    prefs = {
        p.work_item_id: p
        for p in (await db.execute(select(UserItemPreference).where(UserItemPreference.user_id == user.id)))
        .scalars()
        .all()
    }

    def is_snoozed(item_id) -> bool:
        pref = prefs.get(item_id)
        return bool(pref and pref.snoozed_until and pref.snoozed_until > now)

    my_open_items = list(
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
    my_ids = {i.id for i in my_open_items}

    watched_ids = [wid for wid, p in prefs.items() if p.watching and wid not in my_ids]
    watched_items: list[WorkItem] = []
    if watched_ids:
        watched_items = list(
            (
                await db.execute(
                    select(WorkItem).where(WorkItem.id.in_(watched_ids)).where(WorkItem.state == WorkItemState.OPENED)
                )
            )
            .scalars()
            .all()
        )

    all_items = my_open_items + watched_items
    all_ids = [i.id for i in all_items]

    labels_by_item: dict = {}
    milestone_title_by_id: dict = {}
    blocked_reason_by_item: dict = {}
    mrs_by_item: dict = {}  # item id -> MRs linked to it, most recently active first
    my_linked_mr_ids: set = set()

    if all_ids:
        for item_id, name in (
            await db.execute(
                select(work_item_labels.c.work_item_id, Label.name)
                .join(Label, Label.id == work_item_labels.c.label_id)
                .where(work_item_labels.c.work_item_id.in_(all_ids))
            )
        ).all():
            labels_by_item.setdefault(item_id, []).append(name)

        milestone_title_by_id = dict((await db.execute(select(Milestone.id, Milestone.title))).all())

        for work_item_id, reason in (
            await db.execute(
                select(BlockedFlag.work_item_id, BlockedFlag.reason)
                .where(BlockedFlag.work_item_id.in_(all_ids))
                .where(BlockedFlag.resolved_at.is_(None))
                .order_by(BlockedFlag.created_at.desc())
            )
        ).all():
            blocked_reason_by_item.setdefault(work_item_id, reason)

        for mr, linked_item_id in (
            await db.execute(
                select(MergeRequest, merge_request_work_items.c.work_item_id)
                .join(merge_request_work_items, merge_request_work_items.c.merge_request_id == MergeRequest.id)
                .where(merge_request_work_items.c.work_item_id.in_(all_ids))
                .order_by(MergeRequest.last_activity_at.desc())
            )
        ).all():
            mrs_by_item.setdefault(linked_item_id, []).append(mr)
            if mr.author_user_id == user.id:
                my_linked_mr_ids.add(mr.id)

    in_progress_label = (org.in_progress_label or "").strip().lower()

    def card_for(item: WorkItem, linked_mr: MergeRequest | None) -> dict:
        return _work_item_card(
            item,
            project_names.get(item.synced_project_id, "Unknown project"),
            linked_mr,
            blocked_reason_by_item.get(item.id),
            org,
            labels=labels_by_item.get(item.id, []),
            milestone_title=milestone_title_by_id.get(item.milestone_id),
            pref=prefs.get(item.id),
        )

    doing_now: list[dict] = []
    up_next: list[dict] = []
    waiting_on_others: list[dict] = []
    watching: list[dict] = []
    snoozed: list[dict] = []

    for item in my_open_items:
        my_open_mrs = [
            mr
            for mr in mrs_by_item.get(item.id, [])
            if mr.author_user_id == user.id and mr.state == MergeRequestState.OPENED
        ]
        # A draft / failing MR outranks a ready one: if any MR still needs my hands, it's "doing".
        needs_me = next((mr for mr in my_open_mrs if _my_mr_needs_me(mr)), None)
        ready = next((mr for mr in my_open_mrs if not _my_mr_needs_me(mr)), None)
        shown_mr = needs_me or ready or next(iter(mrs_by_item.get(item.id, [])), None)
        card = card_for(item, shown_mr)

        has_progress_label = bool(in_progress_label) and in_progress_label in [
            n.lower() for n in labels_by_item.get(item.id, [])
        ]

        if is_snoozed(item.id):
            snoozed.append(card)
        elif needs_me is not None:
            doing_now.append(card)
        elif ready is not None:
            waiting_on_others.append(card)
        elif has_progress_label:
            doing_now.append(card)
        elif item.id in blocked_reason_by_item:
            waiting_on_others.append(card)
        else:
            up_next.append(card)

    for item in watched_items:
        mrs = mrs_by_item.get(item.id, [])
        card = card_for(item, mrs[0] if mrs else None)
        (snoozed if is_snoozed(item.id) else watching).append(card)

    # MRs I authored that aren't linked to any of my own work items (e.g. a quick fix with no
    # issue) still belong in "waiting" once they're open and ready for review.
    for mr in (
        (
            await db.execute(
                select(MergeRequest)
                .where(MergeRequest.author_user_id == user.id)
                .where(MergeRequest.state == MergeRequestState.OPENED)
                .where(MergeRequest.is_draft.is_(False))
            )
        )
        .scalars()
        .all()
    ):
        if mr.id in my_linked_mr_ids:
            continue
        waiting_on_others.append(_mr_card(mr, project_names.get(mr.synced_project_id, "Unknown project")))

    review_requests = [
        _mr_card(mr, project_names.get(mr.synced_project_id, "Unknown project"))
        for mr, _ in (
            await db.execute(
                select(MergeRequest, MergeRequestReviewer)
                .join(MergeRequestReviewer, MergeRequestReviewer.merge_request_id == MergeRequest.id)
                .where(MergeRequestReviewer.user_id == user.id)
                .where(MergeRequestReviewer.state == ReviewState.REQUESTED)
                .where(MergeRequest.state == MergeRequestState.OPENED)
            )
        ).all()
    ]

    return {
        "doing_now": doing_now,
        "up_next": up_next,
        "waiting_on_others": waiting_on_others,
        "review_requests": review_requests,
        "watching": watching,
        "snoozed": snoozed,
    }
