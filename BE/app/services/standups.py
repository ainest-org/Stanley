"""Manager standup digest (PRD Section 10.1): everyone's opt-in check-ins for a day on one page,
instead of a live meeting. Skipping is never flagged: people without a check-in are listed
quietly, and no GitLab activity is shown for them (that would undercut the opt-in).
"""

import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blocked_flag import BlockedFlag
from app.models.check_in import CheckIn
from app.models.standup_follow import StandupFollow
from app.models.synced_project import SyncedProject
from app.models.user import InToolRole, User, is_placeholder_username
from app.models.work_item import WorkItem

BULLET = re.compile(r"^\s*(?:[-*•]\s*)?")


def _blocker_lines(text: str | None) -> list[str]:
    lines = [BULLET.sub("", line).strip() for line in (text or "").splitlines()]
    return [line for line in lines if line]


async def build_standups(db: AsyncSession, viewer: User, day: date, scope: str) -> dict:
    follows = {
        row[0]
        for row in (
            await db.execute(select(StandupFollow.person_user_id).where(StandupFollow.manager_user_id == viewer.id))
        ).all()
    }

    everyone = [
        u
        for u in (
            await db.execute(select(User).where(User.organization_id == viewer.organization_id).order_by(User.name))
        ).scalars().all()
        if u.id != viewer.id
        and u.in_tool_role != InToolRole.EXEC
        and not is_placeholder_username(u.gitlab_username)
        and u.is_active
    ]
    people = [u for u in everyone if u.id in follows] if scope == "following" else everyone
    person_ids = [u.id for u in people]
    users_by_id = {u.id: u for u in people}

    check_ins = {}
    if person_ids:
        for check_in in (
            await db.execute(
                select(CheckIn)
                .where(CheckIn.check_in_date == day)
                .where(CheckIn.user_id.in_(person_ids))
                .where(CheckIn.skipped.is_(False))
            )
        ).scalars().all():
            check_ins[check_in.user_id] = check_in

    submitted = []
    blockers: list[dict] = []
    for user in people:
        check_in = check_ins.get(user.id)
        if check_in is None:
            continue
        submitted.append(
            {
                "user_id": str(user.id),
                "name": user.name,
                "avatar_url": user.avatar_url,
                "following": user.id in follows,
                "did": check_in.did_text or "",
                "doing": check_in.doing_text or "",
                "blockers": check_in.blockers_text or "",
                "submitted_at": check_in.updated_at.isoformat(),
            }
        )
        for line in _blocker_lines(check_in.blockers_text):
            blockers.append({"source": "check_in", "person": user.name, "text": line})

    # Items someone marked blocked in Stanley also belong in the roll-up, whether or not their
    # owner checked in. Under "following" only the followed people's items are included.
    flag_rows = (
        await db.execute(
            select(BlockedFlag, WorkItem, SyncedProject, User)
            .join(WorkItem, WorkItem.id == BlockedFlag.work_item_id)
            .join(SyncedProject, SyncedProject.id == WorkItem.synced_project_id)
            .join(User, User.id == WorkItem.assignee_user_id, isouter=True)
            .where(BlockedFlag.resolved_at.is_(None))
            .order_by(BlockedFlag.created_at.asc())
        )
    ).all()
    for flag, item, project, assignee in flag_rows:
        if scope == "following" and (assignee is None or assignee.id not in users_by_id):
            continue
        blockers.append(
            {
                "source": "flag",
                "person": assignee.name if assignee else None,
                "text": flag.reason,
                "title": item.title,
                "project_name": project.name,
                "web_url": item.web_url,
                "work_item_id": str(item.id),
            }
        )

    return {
        "date": day.isoformat(),
        "scope": scope,
        "following_count": len(follows),
        "submitted": submitted,
        "no_check_in": [
            {"user_id": str(u.id), "name": u.name, "following": u.id in follows}
            for u in people
            if u.id not in check_ins
        ],
        "blockers": blockers,
    }
