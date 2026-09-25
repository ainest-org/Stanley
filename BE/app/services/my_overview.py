"""Personal dashboard numbers for the signed-in engineer: stats, "needs me now", recent activity
and the pre-filled daily check-in. Private to that person by design (no rankings, no hours or
points; only counts, ages and turnaround times, per PRD Non-Goals).
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MergeRequestState, PipelineStatus, ReviewState, WorkItemState
from app.models.merge_request import MergeRequest
from app.models.merge_request_reviewer import MergeRequestReviewer
from app.models.organization import Organization
from app.models.user import User
from app.models.user_item_preference import UserItemPreference
from app.models.work_item import WorkItem
from app.services.health import days_since, is_overdue_for_review, is_stale
from app.services.radar import _week_start

TREND_WEEKS = 8
ATTENTION_LIMIT = 5


async def _stats(db: AsyncSession, user: User) -> dict:
    now = datetime.now(timezone.utc)
    trend_start = _week_start(now) - timedelta(weeks=TREND_WEEKS - 1)
    this_week = _week_start(now)

    my_mrs = (await db.execute(select(MergeRequest).where(MergeRequest.author_user_id == user.id))).scalars().all()
    my_open_items = (
        (
            await db.execute(
                select(WorkItem).where(WorkItem.assignee_user_id == user.id).where(WorkItem.state == WorkItemState.OPENED)
            )
        )
        .scalars()
        .all()
    )
    my_closed_items = (
        (
            await db.execute(
                select(WorkItem)
                .where(WorkItem.assignee_user_id == user.id)
                .where(WorkItem.closed_at >= trend_start)
            )
        )
        .scalars()
        .all()
    )

    merged_by_week: dict = defaultdict(int)
    closed_by_week: dict = defaultdict(int)
    for mr in my_mrs:
        if mr.merged_at and mr.merged_at >= trend_start:
            merged_by_week[_week_start(mr.merged_at)] += 1
    for item in my_closed_items:
        closed_by_week[_week_start(item.closed_at)] += 1

    weeks = [trend_start + timedelta(weeks=i) for i in range(TREND_WEEKS)]
    trend = [
        {"week_start": w.date().isoformat(), "merged": merged_by_week.get(w, 0), "closed": closed_by_week.get(w, 0)}
        for w in weeks
    ]

    ninety_days_ago = now - timedelta(days=90)
    cycle_days = [
        (mr.merged_at - mr.gitlab_created_at).total_seconds() / 86400
        for mr in my_mrs
        if mr.merged_at and mr.merged_at >= ninety_days_ago
    ]

    thirty_days_ago = now - timedelta(days=30)
    pipeline_mrs = [
        mr
        for mr in my_mrs
        if mr.pipeline_status in (PipelineStatus.SUCCESS, PipelineStatus.FAILED)
        and (mr.state == MergeRequestState.OPENED or (mr.merged_at and mr.merged_at >= thirty_days_ago))
    ]
    passing = sum(1 for mr in pipeline_mrs if mr.pipeline_status == PipelineStatus.SUCCESS)

    waiting_rows = (
        await db.execute(
            select(MergeRequest)
            .join(MergeRequestReviewer, MergeRequestReviewer.merge_request_id == MergeRequest.id)
            .where(MergeRequestReviewer.user_id == user.id)
            .where(MergeRequestReviewer.state == ReviewState.REQUESTED)
            .where(MergeRequest.state == MergeRequestState.OPENED)
        )
    ).scalars().all()
    approved_rows = (
        await db.execute(
            select(MergeRequest)
            .join(MergeRequestReviewer, MergeRequestReviewer.merge_request_id == MergeRequest.id)
            .where(MergeRequestReviewer.user_id == user.id)
            .where(MergeRequestReviewer.state == ReviewState.APPROVED)
        )
    ).scalars().all()
    approved_recent = [
        mr for mr in approved_rows if mr.state == MergeRequestState.OPENED or (mr.merged_at and mr.merged_at >= thirty_days_ago)
    ]

    return {
        "merged_this_week": merged_by_week.get(this_week, 0),
        "merged_last_week": merged_by_week.get(this_week - timedelta(weeks=1), 0),
        "closed_this_week": closed_by_week.get(this_week, 0),
        "trend": trend,
        "median_cycle_days": round(median(cycle_days), 1) if cycle_days else None,
        "pipeline_pass_rate": round(100 * passing / len(pipeline_mrs)) if pipeline_mrs else None,
        "open_items": len(my_open_items),
        "oldest_open_item_days": round(max(days_since(i.gitlab_created_at) for i in my_open_items)) if my_open_items else None,
        "reviews_waiting": len(waiting_rows),
        "oldest_review_waiting_days": round(max(days_since(mr.gitlab_created_at) for mr in waiting_rows))
        if waiting_rows
        else None,
        "reviews_approved_recent": len(approved_recent),
    }


async def _attention(db: AsyncSession, user: User, org: Organization, snoozed_ids: set) -> dict:
    review_mrs = (
        await db.execute(
            select(MergeRequest)
            .join(MergeRequestReviewer, MergeRequestReviewer.merge_request_id == MergeRequest.id)
            .where(MergeRequestReviewer.user_id == user.id)
            .where(MergeRequestReviewer.state == ReviewState.REQUESTED)
            .where(MergeRequest.state == MergeRequestState.OPENED)
            .order_by(MergeRequest.gitlab_created_at.asc())
        )
    ).scalars().all()

    failing = (
        await db.execute(
            select(MergeRequest)
            .where(MergeRequest.author_user_id == user.id)
            .where(MergeRequest.state == MergeRequestState.OPENED)
            .where(MergeRequest.pipeline_status == PipelineStatus.FAILED)
        )
    ).scalars().all()

    stale = [
        item
        for item in (
            await db.execute(
                select(WorkItem).where(WorkItem.assignee_user_id == user.id).where(WorkItem.state == WorkItemState.OPENED)
            )
        ).scalars().all()
        if item.id not in snoozed_ids and is_stale(item.last_activity_at, org)
    ]

    return {
        "reviews_waiting": [
            {
                "id": str(mr.id),
                "title": mr.title,
                "web_url": mr.web_url,
                "days_waiting": round(days_since(mr.gitlab_created_at)),
                "overdue": is_overdue_for_review(mr, org),
            }
            for mr in review_mrs[:ATTENTION_LIMIT]
        ],
        "failing_pipelines": [
            {"id": str(mr.id), "title": mr.title, "web_url": mr.web_url, "pipeline_url": f"{mr.web_url}/pipelines"}
            for mr in failing[:ATTENTION_LIMIT]
        ],
        "stale_items": [
            {
                "id": str(item.id),
                "title": item.title,
                "web_url": item.web_url,
                "days_inactive": round(days_since(item.last_activity_at)),
            }
            for item in sorted(stale, key=lambda i: i.last_activity_at)[:ATTENTION_LIMIT]
        ],
    }


async def recent_activity(db: AsyncSession, user: User, since: datetime, limit: int = 15) -> list[dict]:
    events: list[dict] = []
    my_mrs = (await db.execute(select(MergeRequest).where(MergeRequest.author_user_id == user.id))).scalars().all()
    for mr in my_mrs:
        if mr.merged_at and mr.merged_at >= since:
            events.append({"kind": "merged", "title": mr.title, "web_url": mr.web_url, "at": mr.merged_at})
        if mr.gitlab_created_at >= since:
            events.append({"kind": "opened", "title": mr.title, "web_url": mr.web_url, "at": mr.gitlab_created_at})
    closed = (
        await db.execute(
            select(WorkItem).where(WorkItem.assignee_user_id == user.id).where(WorkItem.closed_at >= since)
        )
    ).scalars().all()
    for item in closed:
        events.append({"kind": "closed", "title": item.title, "web_url": item.web_url, "at": item.closed_at})

    events.sort(key=lambda e: e["at"], reverse=True)
    return [{**e, "at": e["at"].isoformat()} for e in events[:limit]]


async def build_overview(db: AsyncSession, user: User, org: Organization) -> dict:
    now = datetime.now(timezone.utc)
    snoozed_ids = {
        row[0]
        for row in (
            await db.execute(
                select(UserItemPreference.work_item_id)
                .where(UserItemPreference.user_id == user.id)
                .where(UserItemPreference.snoozed_until > now)
            )
        ).all()
    }
    return {
        "stats": await _stats(db, user),
        "attention": await _attention(db, user, org, snoozed_ids),
        "activity": await recent_activity(db, user, now - timedelta(days=14)),
    }

