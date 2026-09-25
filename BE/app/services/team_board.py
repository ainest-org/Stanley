"""Builds the Team Board (PRD Section 7): swimlanes per team member instead of status
columns — the deliberate anti-pattern to GitLab's board-overwhelm complaint.

Simplification: the data model has no explicit "manages" relationship (Section 3's roles don't
define team membership), so for now every org member gets a swimlane rather than only a given
manager's direct reports. Revisit once a team/reporting-line concept exists.

Filters (Section 7.3) narrow the swimlane items and chip counts. Idle/overloaded are always
computed from each person's *unfiltered* load, otherwise filtering to one project would make
everyone else look idle.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blocked_flag import BlockedFlag
from app.models.enums import MergeRequestState, ReviewState, WorkItemState
from app.models.label import Label
from app.models.merge_request import MergeRequest, merge_request_work_items
from app.models.merge_request_reviewer import MergeRequestReviewer
from app.models.milestone import Milestone
from app.models.organization import Organization
from app.models.synced_project import SyncedProject
from app.models.user import User, is_placeholder_username
from app.models.work_item import WorkItem, work_item_labels
from app.services.health import days_since, is_stale, is_work_item_flagged


@dataclass
class TeamBoardFilters:
    project_id: uuid.UUID | None = None
    milestone: str | None = None
    label: str | None = None
    flagged_only: bool = False

    @property
    def item_filters_active(self) -> bool:
        return bool(self.project_id or self.milestone or self.label or self.flagged_only)


async def build_filter_options(db: AsyncSession) -> dict:
    projects = (
        (await db.execute(select(SyncedProject).where(SyncedProject.is_active.is_(True)).order_by(SyncedProject.name)))
        .scalars()
        .all()
    )
    milestone_titles = (
        (await db.execute(select(Milestone.title).where(Milestone.state == "active").distinct().order_by(Milestone.title)))
        .scalars()
        .all()
    )
    label_names = (await db.execute(select(Label.name).distinct().order_by(Label.name))).scalars().all()
    return {
        "projects": [{"id": str(p.id), "name": p.name} for p in projects],
        "milestones": list(milestone_titles),
        "labels": list(label_names),
    }


async def build_team_board(db: AsyncSession, org: Organization, filters: TeamBoardFilters | None = None) -> dict:
    filters = filters or TeamBoardFilters()

    project_names = dict(
        (row[0], row[1]) for row in (await db.execute(select(SyncedProject.id, SyncedProject.name))).all()
    )

    users = [
        u
        for u in (await db.execute(select(User).where(User.organization_id == org.id))).scalars().all()
        if not is_placeholder_username(u.gitlab_username)
    ]
    users_by_id = {u.id: u for u in users}

    open_items = (
        (await db.execute(select(WorkItem).where(WorkItem.state == WorkItemState.OPENED))).scalars().all()
    )
    item_ids = [i.id for i in open_items]

    active_blocked_item_ids = set(
        row[0]
        for row in (
            await db.execute(select(BlockedFlag.work_item_id).where(BlockedFlag.resolved_at.is_(None)))
        ).all()
    )

    label_names_by_item: dict = defaultdict(set)
    linked_mr_by_item: dict = {}
    milestone_title_by_id: dict = {}
    if item_ids:
        for item_id, name in (
            await db.execute(
                select(work_item_labels.c.work_item_id, Label.name)
                .join(Label, Label.id == work_item_labels.c.label_id)
                .where(work_item_labels.c.work_item_id.in_(item_ids))
            )
        ).all():
            label_names_by_item[item_id].add(name)

        for mr, linked_item_id in (
            await db.execute(
                select(MergeRequest, merge_request_work_items.c.work_item_id)
                .join(merge_request_work_items, merge_request_work_items.c.merge_request_id == MergeRequest.id)
                .where(merge_request_work_items.c.work_item_id.in_(item_ids))
                .order_by(MergeRequest.last_activity_at.desc())
            )
        ).all():
            linked_mr_by_item.setdefault(linked_item_id, mr)

        milestone_title_by_id = dict((await db.execute(select(Milestone.id, Milestone.title))).all())

    def is_flagged(item: WorkItem) -> bool:
        return is_work_item_flagged(
            item.last_activity_at, linked_mr_by_item.get(item.id), org, item.id in active_blocked_item_ids
        )

    def passes(item: WorkItem) -> bool:
        if filters.project_id and item.synced_project_id != filters.project_id:
            return False
        if filters.milestone and milestone_title_by_id.get(item.milestone_id) != filters.milestone:
            return False
        if filters.label and filters.label not in label_names_by_item.get(item.id, set()):
            return False
        if filters.flagged_only and not is_flagged(item):
            return False
        return True

    all_by_assignee: dict = defaultdict(list)
    filtered_by_assignee: dict = defaultdict(list)
    unassigned_items: list[WorkItem] = []
    for item in open_items:
        if item.assignee_user_id is None:
            if not filters.project_id or item.synced_project_id == filters.project_id:
                unassigned_items.append(item)
            continue
        all_by_assignee[item.assignee_user_id].append(item)
        if passes(item):
            filtered_by_assignee[item.assignee_user_id].append(item)

    swimlanes = []
    idle_engineers = []
    overloaded_engineers = []

    for user in users:
        items = sorted(filtered_by_assignee.get(user.id, []), key=lambda i: i.last_activity_at, reverse=True)
        total_active = len(all_by_assignee.get(user.id, []))

        if total_active == 0:
            idle_engineers.append({"user_id": str(user.id), "name": user.name})
        elif total_active > org.overloaded_item_threshold:
            overloaded_engineers.append({"user_id": str(user.id), "name": user.name, "active_count": total_active})

        if filters.item_filters_active and not items:
            continue  # with filters on, hide lanes that have nothing matching

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
                        "is_flagged": is_flagged(item),
                    }
                    for item in items[:3]
                ],
            }
        )

    def in_project(project_id) -> bool:
        return not filters.project_id or project_id == filters.project_id

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
        if in_project(mr.synced_project_id) and is_stale(mr.last_activity_at, org)
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
        if in_project(mr.synced_project_id) and days_since(mr.last_activity_at) > org.review_sla_days
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
