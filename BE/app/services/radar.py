"""Builds the Exec Radar (PRD Section 8): the screen that has to answer "what's everyone doing"
in ~30 seconds. Deliberately narrow — no story points, no velocity/burndown (Section 8's
"deliberately excluded by default" list).
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import asc, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blocked_flag import BlockedFlag
from app.models.enums import MergeRequestState, WorkItemState
from app.models.merge_request import MergeRequest, merge_request_work_items
from app.models.milestone import Milestone
from app.models.organization import Organization
from app.models.synced_project import SyncedProject
from app.models.user import InToolRole, User, is_placeholder_username
from app.models.work_item import WorkItem
from app.services.health import days_since

TREND_WEEKS = 8


def _week_start(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    monday = moment - timedelta(days=moment.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


async def _build_summary(db: AsyncSession) -> dict:
    open_items_with_mr = await db.execute(
        select(WorkItem.id)
        .join(merge_request_work_items, merge_request_work_items.c.work_item_id == WorkItem.id)
        .join(MergeRequest, MergeRequest.id == merge_request_work_items.c.merge_request_id)
        .where(WorkItem.state == WorkItemState.OPENED)
        .where(MergeRequest.state == MergeRequestState.OPENED)
        .distinct()
    )
    in_progress = len(open_items_with_mr.all())

    blocked_result = await db.execute(
        select(BlockedFlag.work_item_id).where(BlockedFlag.resolved_at.is_(None)).distinct()
    )
    blocked = len(blocked_result.all())

    in_review_result = await db.execute(
        select(MergeRequest.id)
        .where(MergeRequest.state == MergeRequestState.OPENED)
        .where(MergeRequest.is_draft.is_(False))
    )
    in_review = len(in_review_result.all())

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    shipped_result = await db.execute(select(MergeRequest.id).where(MergeRequest.merged_at >= week_ago))
    shipped_this_week = len(shipped_result.all())

    return {
        "in_progress": in_progress,
        "blocked": blocked,
        "in_review": in_review,
        "shipped_this_week": shipped_this_week,
    }


async def _build_delivery_trend(db: AsyncSession) -> list[dict]:
    window_start = _week_start(datetime.now(timezone.utc)) - timedelta(weeks=TREND_WEEKS - 1)

    merged_result = await db.execute(select(MergeRequest.merged_at).where(MergeRequest.merged_at >= window_start))
    closed_result = await db.execute(select(WorkItem.closed_at).where(WorkItem.closed_at >= window_start))

    merged_by_week: dict = defaultdict(int)
    for (merged_at,) in merged_result.all():
        if merged_at:
            merged_by_week[_week_start(merged_at)] += 1

    closed_by_week: dict = defaultdict(int)
    for (closed_at,) in closed_result.all():
        if closed_at:
            closed_by_week[_week_start(closed_at)] += 1

    weeks = [window_start + timedelta(weeks=i) for i in range(TREND_WEEKS)]
    return [
        {
            "week_start": week.date().isoformat(),
            "merged_count": merged_by_week.get(week, 0),
            "closed_count": closed_by_week.get(week, 0),
        }
        for week in weeks
    ]


async def _build_project_health(db: AsyncSession) -> list[dict]:
    projects = (
        (await db.execute(select(SyncedProject).where(SyncedProject.is_active.is_(True)))).scalars().all()
    )

    health = []
    for project in projects:
        milestone_result = await db.execute(
            select(Milestone)
            .where(Milestone.synced_project_id == project.id)
            .where(Milestone.state == "active")
            .order_by(nulls_last(asc(Milestone.due_at)))
            .limit(1)
        )
        milestone = milestone_result.scalar_one_or_none()

        if milestone is None:
            health.append(
                {"project_id": str(project.id), "name": project.name, "status": "no_active_milestone", "milestone_title": None, "percent_done": None}
            )
            continue

        items_result = await db.execute(select(WorkItem.state).where(WorkItem.milestone_id == milestone.id))
        states = [s for (s,) in items_result.all()]
        total = len(states)
        done = sum(1 for s in states if s == WorkItemState.CLOSED)
        percent_done = (done / total) if total else 0.0

        status = "green"
        if milestone.starts_at and milestone.due_at:
            today = datetime.now(timezone.utc).date()
            total_days = max((milestone.due_at - milestone.starts_at).days, 1)
            elapsed_days = max((today - milestone.starts_at).days, 0)
            elapsed_ratio = min(elapsed_days / total_days, 1.0)
            gap = elapsed_ratio - percent_done
            status = "green" if gap < 0.1 else "yellow" if gap < 0.25 else "red"
        else:
            status = "green" if percent_done >= 0.7 else "yellow" if percent_done >= 0.4 else "red"

        health.append(
            {
                "project_id": str(project.id),
                "name": project.name,
                "status": status,
                "milestone_title": milestone.title,
                "percent_done": round(percent_done * 100),
            }
        )

    return health


async def _build_blockers(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(BlockedFlag, WorkItem, SyncedProject, User)
        .join(WorkItem, WorkItem.id == BlockedFlag.work_item_id)
        .join(SyncedProject, SyncedProject.id == WorkItem.synced_project_id)
        .join(User, User.id == WorkItem.assignee_user_id, isouter=True)
        .where(BlockedFlag.resolved_at.is_(None))
        .order_by(BlockedFlag.created_at.asc())
    )

    return [
        {
            "work_item_id": str(work_item.id),
            "title": work_item.title,
            "project_name": project.name,
            "web_url": work_item.web_url,
            "blocked_days": round(days_since(flag.created_at)),
            "reason": flag.reason,
            "assignee_name": assignee.name if assignee else None,
        }
        for flag, work_item, project, assignee in result.all()
    ]


async def _build_people(db: AsyncSession, org: Organization) -> list[dict]:
    users = [
        u
        for u in (await db.execute(select(User).where(User.organization_id == org.id))).scalars().all()
        if not is_placeholder_username(u.gitlab_username)
    ]

    open_items = (await db.execute(select(WorkItem).where(WorkItem.state == WorkItemState.OPENED))).scalars().all()
    active_blocked_item_ids = set(
        row[0]
        for row in (
            await db.execute(select(BlockedFlag.work_item_id).where(BlockedFlag.resolved_at.is_(None)))
        ).all()
    )

    active_count_by_user: dict = defaultdict(int)
    blocked_count_by_user: dict = defaultdict(int)
    for item in open_items:
        if item.assignee_user_id is None:
            continue
        active_count_by_user[item.assignee_user_id] += 1
        if item.id in active_blocked_item_ids:
            blocked_count_by_user[item.assignee_user_id] += 1

    return [
        {
            "user_id": str(user.id),
            "name": user.name,
            "active_count": active_count_by_user.get(user.id, 0),
            "blocked_count": blocked_count_by_user.get(user.id, 0),
        }
        for user in users
        if user.in_tool_role == InToolRole.ENGINEER or active_count_by_user.get(user.id, 0) > 0
    ]


async def build_radar(db: AsyncSession, org: Organization) -> dict:
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "summary": await _build_summary(db),
        "delivery_trend": await _build_delivery_trend(db),
        "project_health": await _build_project_health(db),
        "blockers": await _build_blockers(db),
        "people": await _build_people(db, org),
    }
