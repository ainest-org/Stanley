"""Builds the Team Board (PRD Section 7): swimlanes per team member instead of status
columns — the deliberate anti-pattern to GitLab's board-overwhelm complaint.

Simplification: the data model has no explicit "manages" relationship (Section 3's roles don't
define team membership), so for now every org member gets a swimlane rather than only a given
manager's direct reports. Revisit once a team/reporting-line concept exists.
"""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blocked_flag import BlockedFlag
from app.models.enums import MergeRequestState, ReviewState, WorkItemState
from app.models.merge_request import MergeRequest
from app.models.merge_request_reviewer import MergeRequestReviewer
from app.models.organization import Organization
from app.models.synced_project import SyncedProject
from app.models.user import User
from app.models.work_item import WorkItem
from app.services.health import days_since, is_stale


async def build_team_board(db: AsyncSession, org: Organization) -> dict:
    project_names = dict(
        (row[0], row[1]) for row in (await db.execute(select(SyncedProject.id, SyncedProject.name))).all()
    )

    users = (await db.execute(select(User).where(User.organization_id == org.id))).scalars().all()
    users_by_id = {u.id: u for u in users}

    open_items = (
        (await db.execute(select(WorkItem).where(WorkItem.state == WorkItemState.OPENED))).scalars().all()
    )

    active_blocked_item_ids = set(
        row[0]
        for row in (
            await db.execute(select(BlockedFlag.work_item_id).where(BlockedFlag.resolved_at.is_(None)))
        ).all()
    )

    items_by_assignee: dict = defaultdict(list)
    unassigned_items: list[WorkItem] = []
    for item in open_items:
        if item.assignee_user_id is None:
            unassigned_items.append(item)
        else:
            items_by_assignee[item.assignee_user_id].append(item)

    swimlanes = []
    idle_engineers = []
    overloaded_engineers = []

    for user in users:
        items = sorted(items_by_assignee.get(user.id, []), key=lambda i: i.last_activity_at, reverse=True)
        blocked_count = sum(1 for i in items if i.id in active_blocked_item_ids)
        stale_count = sum(1 for i in items if is_stale(i.last_activity_at, org) and i.id not in active_blocked_item_ids)

        swimlanes.append(
            {
                "user_id": str(user.id),
                "name": user.name,
                "avatar_url": user.avatar_url,
                "active_count": len(items),
                "blocked_count": blocked_count,
                "stale_count": stale_count,
                "items": [
                    {
                        "id": str(item.id),
                        "title": item.title,
                        "project_name": project_names.get(item.synced_project_id, "Unknown project"),
                        "web_url": item.web_url,
                        "is_blocked": item.id in active_blocked_item_ids,
                        "is_stale": is_stale(item.last_activity_at, org) and item.id not in active_blocked_item_ids,
                    }
                    for item in items[:3]
                ],
            }
        )

        if len(items) == 0:
            idle_engineers.append({"user_id": str(user.id), "name": user.name})
        elif len(items) > org.overloaded_item_threshold:
            overloaded_engineers.append({"user_id": str(user.id), "name": user.name, "active_count": len(items)})

    stalled_mrs_result = await db.execute(select(MergeRequest).where(MergeRequest.state == MergeRequestState.OPENED))
    stalled_mrs = [
        {
            "id": str(mr.id),
            "title": mr.title,
            "project_name": project_names.get(mr.synced_project_id, "Unknown project"),
            "web_url": mr.web_url,
            "days_inactive": round(days_since(mr.last_activity_at), 1),
        }
        for mr in stalled_mrs_result.scalars().all()
        if is_stale(mr.last_activity_at, org)
    ]

    reviews_pending_result = await db.execute(
        select(MergeRequest, MergeRequestReviewer)
        .join(MergeRequestReviewer, MergeRequestReviewer.merge_request_id == MergeRequest.id)
        .where(MergeRequest.state == MergeRequestState.OPENED)
        .where(MergeRequestReviewer.state == ReviewState.REQUESTED)
    )
    reviews_pending_sla = [
        {
            "id": str(mr.id),
            "title": mr.title,
            "reviewer_name": users_by_id[reviewer.user_id].name if reviewer.user_id in users_by_id else "Unknown",
            "web_url": mr.web_url,
            "days_pending": round(days_since(mr.last_activity_at), 1),
        }
        for mr, reviewer in reviews_pending_result.all()
        if days_since(mr.last_activity_at) > org.review_sla_days
    ]

    return {
        "swimlanes": swimlanes,
        "attention": {
            "stalled_mrs": stalled_mrs,
            "unassigned_items": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "project_name": project_names.get(item.synced_project_id, "Unknown project"),
                    "web_url": item.web_url,
                }
                for item in unassigned_items
            ],
            "reviews_pending_sla": reviews_pending_sla,
            "idle_engineers": idle_engineers,
            "overloaded_engineers": overloaded_engineers,
        },
    }
