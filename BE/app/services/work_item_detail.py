"""Side-panel detail for one work item (PRD Section 7.4): a read-only mirror of the real GitLab
item. Description and comments are read live with the acting user's own token (Section 11.3 /
12: full threads are never cached, and the read can't exceed that person's GitLab access). If
GitLab can't be reached or refuses, the cached fields still render (Section 13.1) with a note."""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blocked_flag import BlockedFlag
from app.models.label import Label
from app.models.merge_request import MergeRequest, merge_request_work_items
from app.models.milestone import Milestone
from app.models.synced_project import SyncedProject
from app.models.user import User
from app.models.work_item import WorkItem, work_item_labels
from app.services.access import can_manage_milestones
from app.services.health import mr_status_badge
from app.sync.gitlab_client import GitLabClient
from app.sync.mutations import STANLEY_FOOTER

MAX_COMMENTS = 50


async def build_work_item_detail(db: AsyncSession, item: WorkItem, access_token: str, viewer: User) -> dict:
    project = await db.get(SyncedProject, item.synced_project_id)
    assignee = await db.get(User, item.assignee_user_id) if item.assignee_user_id else None
    milestone = await db.get(Milestone, item.milestone_id) if item.milestone_id else None

    label_names = (
        (
            await db.execute(
                select(Label.name)
                .join(work_item_labels, work_item_labels.c.label_id == Label.id)
                .where(work_item_labels.c.work_item_id == item.id)
            )
        )
        .scalars()
        .all()
    )
    merge_requests = (
        (
            await db.execute(
                select(MergeRequest)
                .join(merge_request_work_items, merge_request_work_items.c.merge_request_id == MergeRequest.id)
                .where(merge_request_work_items.c.work_item_id == item.id)
                .order_by(MergeRequest.last_activity_at.desc())
            )
        )
        .scalars()
        .all()
    )
    blocked_reason = (
        await db.execute(
            select(BlockedFlag.reason)
            .where(BlockedFlag.work_item_id == item.id)
            .where(BlockedFlag.resolved_at.is_(None))
            .order_by(BlockedFlag.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    may_set_milestone = await can_manage_milestones(db, viewer, item.synced_project_id)
    available_milestones = []
    if may_set_milestone:
        available_milestones = [
            {"id": str(m.id), "title": m.title}
            for m in (
                await db.execute(
                    select(Milestone)
                    .where(Milestone.synced_project_id == item.synced_project_id)
                    .where(Milestone.state == "active")
                )
            )
            .scalars()
            .all()
        ]

    description = item.description
    due_date = None
    comments: list[dict] = []
    live_error = None

    if project is not None:
        client = GitLabClient(access_token=access_token)
        base = f"/projects/{project.gitlab_project_id}/issues/{item.gitlab_iid}"
        try:
            issue = (await client.rest_get(base)).json()
            notes = (await client.rest_get(f"{base}/notes", {"sort": "asc", "per_page": MAX_COMMENTS})).json()
            description = issue.get("description")
            due_date = issue.get("due_date")
            comments = [
                {
                    "id": str(note["id"]),
                    "author": (note.get("author") or {}).get("name", "Unknown"),
                    "body": note["body"].removesuffix(STANLEY_FOOTER).rstrip(),
                    "via_stanley": note["body"].rstrip().endswith(STANLEY_FOOTER),
                    "created_at": note["created_at"],
                }
                for note in notes
                if not note.get("system")
            ]
        except httpx.HTTPStatusError as exc:
            live_error = f"GitLab returned {exc.response.status_code}; showing the last synced copy."
        except httpx.HTTPError:
            live_error = "GitLab couldn't be reached; showing the last synced copy."

    return {
        "id": str(item.id),
        "title": item.title,
        "project_name": project.name if project else "Unknown project",
        "web_url": item.web_url,
        "state": item.state.value,
        "item_type": item.item_type,
        "assignee": {"id": str(assignee.id), "name": assignee.name} if assignee else None,
        "milestone_id": str(milestone.id) if milestone else None,
        "milestone_title": milestone.title if milestone else None,
        "can_set_milestone": may_set_milestone,
        "available_milestones": available_milestones,
        "labels": list(label_names),
        "due_date": due_date,
        "description": description,
        "comments": comments,
        "merge_requests": [
            {
                "id": str(mr.id),
                "title": mr.title,
                "status": mr_status_badge(mr),
                "pipeline_status": mr.pipeline_status.value if mr.pipeline_status else None,
                "web_url": mr.web_url,
            }
            for mr in merge_requests
        ],
        "blocked_reason": blocked_reason,
        "live_error": live_error,
    }
