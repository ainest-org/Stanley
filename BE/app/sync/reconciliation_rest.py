"""Classic Issues API fallback reconciliation, for self-hosted GitLab instances too old to
support the Work Items API (PRD Section 5.2 step 1 / 13.1 last row). Mirrors
`reconciliation.py`'s GraphQL path field-for-field but reads REST v4 responses, which are
flatter (e.g. labels come back as plain name strings, not label objects)."""

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import GitLabAccessLevel, MergeRequestState, PipelineStatus, WorkItemState
from app.models.label import Label
from app.models.merge_request import MergeRequest
from app.models.merge_request_reviewer import MergeRequestReviewer
from app.models.milestone import Milestone
from app.models.project_membership import ProjectMembership
from app.models.synced_project import SyncedProject
from app.models.work_item import WorkItem, work_item_labels
from app.core.config import get_settings
from app.sync.gid import parse_date, parse_dt
from app.sync.mr_link_store import set_links
from app.sync.mr_links import linked_work_item_ids
from app.sync.gitlab_client import GitLabClient
from app.sync.reconciliation import _get_or_create_user_stub

settings = get_settings()

REST_ACCESS_LEVEL_BY_INT = {
    10: GitLabAccessLevel.GUEST,
    20: GitLabAccessLevel.REPORTER,
    30: GitLabAccessLevel.DEVELOPER,
    40: GitLabAccessLevel.MAINTAINER,
    50: GitLabAccessLevel.OWNER,
}


def _rest_user_to_graphql_shape(user: dict | None) -> dict | None:
    """REST user objects use snake_case (avatar_url) and plain integer ids; normalize to the
    shape `_get_or_create_user_stub` expects so both sync paths can share it."""
    if not user:
        return None
    return {
        "id": user["id"],
        "username": user.get("username", ""),
        "name": user.get("name", ""),
        "publicEmail": user.get("public_email") or user.get("email"),
        "avatarUrl": user.get("avatar_url"),
    }


async def _upsert_milestones_rest(db: AsyncSession, project: SyncedProject, items: list[dict]) -> dict[str, object]:
    id_map: dict[str, object] = {}
    for item in items:
        gitlab_id = str(item["id"])
        stmt = (
            pg_insert(Milestone)
            .values(
                synced_project_id=project.id,
                gitlab_milestone_id=gitlab_id,
                title=item["title"],
                state=item.get("state", "active"),
                starts_at=parse_date(item.get("start_date")),
                due_at=parse_date(item.get("due_date")),
            )
            .on_conflict_do_update(
                index_elements=[Milestone.gitlab_milestone_id],
                set_={
                    "title": item["title"],
                    "state": item.get("state", "active"),
                    "starts_at": parse_date(item.get("start_date")),
                    "due_at": parse_date(item.get("due_date")),
                },
            )
            .returning(Milestone.id)
        )
        result = await db.execute(stmt)
        id_map[gitlab_id] = result.scalar_one()
    return id_map


async def _upsert_labels_rest(db: AsyncSession, project: SyncedProject, items: list[dict]) -> dict[str, object]:
    """Keyed by label name, since REST issues/MRs reference labels by name only."""
    id_map: dict[str, object] = {}
    for item in items:
        gitlab_id = str(item["id"])
        stmt = (
            pg_insert(Label)
            .values(
                synced_project_id=project.id,
                gitlab_label_id=gitlab_id,
                name=item["name"],
                color=item.get("color"),
            )
            .on_conflict_do_update(
                index_elements=[Label.gitlab_label_id],
                set_={"name": item["name"], "color": item.get("color")},
            )
            .returning(Label.id)
        )
        result = await db.execute(stmt)
        id_map[item["name"]] = result.scalar_one()
    return id_map


async def _upsert_members_rest(db: AsyncSession, project: SyncedProject, items: list[dict]) -> None:
    for item in items:
        user = await _get_or_create_user_stub(db, project.organization_id, _rest_user_to_graphql_shape(item))
        if not user:
            continue
        access_level = REST_ACCESS_LEVEL_BY_INT.get(item.get("access_level", 0))
        if access_level is None:
            continue
        stmt = (
            pg_insert(ProjectMembership)
            .values(synced_project_id=project.id, user_id=user.id, access_level=access_level)
            .on_conflict_do_update(
                index_elements=[ProjectMembership.synced_project_id, ProjectMembership.user_id],
                set_={"access_level": access_level},
            )
        )
        await db.execute(stmt)


async def _upsert_issues_rest(
    db: AsyncSession, project: SyncedProject, items: list[dict], milestone_id_by_gid: dict, label_id_by_name: dict
) -> dict[str, object]:
    work_item_id_by_iid: dict[str, object] = {}
    for item in items:
        gitlab_id = str(item["id"])
        author = await _get_or_create_user_stub(db, project.organization_id, _rest_user_to_graphql_shape(item.get("author")))
        assignees = item.get("assignees") or []
        assignee = (
            await _get_or_create_user_stub(db, project.organization_id, _rest_user_to_graphql_shape(assignees[0]))
            if assignees
            else None
        )
        milestone = item.get("milestone")
        milestone_id = milestone_id_by_gid.get(str(milestone["id"])) if milestone else None

        values = dict(
            synced_project_id=project.id,
            gitlab_global_id=gitlab_id,
            gitlab_iid=str(item["iid"]),
            title=item["title"],
            description=item.get("description"),
            item_type=(item.get("issue_type") or "issue").lower(),
            state=WorkItemState.CLOSED if item["state"] == "closed" else WorkItemState.OPENED,
            web_url=item["web_url"],
            assignee_user_id=assignee.id if assignee else None,
            author_user_id=author.id if author else None,
            milestone_id=milestone_id,
            gitlab_created_at=parse_dt(item["created_at"]),
            gitlab_updated_at=parse_dt(item["updated_at"]),
            closed_at=parse_dt(item.get("closed_at")),
            last_activity_at=parse_dt(item["updated_at"]),
        )
        stmt = (
            pg_insert(WorkItem)
            .values(**values)
            .on_conflict_do_update(index_elements=[WorkItem.gitlab_global_id], set_=values)
            .returning(WorkItem.id)
        )
        result = await db.execute(stmt)
        work_item_id = result.scalar_one()
        work_item_id_by_iid[str(item["iid"])] = work_item_id

        label_ids = [label_id_by_name[name] for name in item.get("labels", []) if name in label_id_by_name]
        await db.execute(work_item_labels.delete().where(work_item_labels.c.work_item_id == work_item_id))
        if label_ids:
            await db.execute(
                work_item_labels.insert(),
                [{"work_item_id": work_item_id, "label_id": lid} for lid in label_ids],
            )

    return work_item_id_by_iid


async def _upsert_merge_requests_rest(
    db: AsyncSession, project: SyncedProject, items: list[dict], work_item_id_by_iid: dict
) -> None:
    for item in items:
        gitlab_id = str(item["id"])
        author = await _get_or_create_user_stub(db, project.organization_id, _rest_user_to_graphql_shape(item.get("author")))

        state = item["state"]
        mr_state = (
            MergeRequestState.MERGED
            if state == "merged"
            else MergeRequestState.CLOSED
            if state == "closed"
            else MergeRequestState.OPENED
        )
        pipeline_status_raw = (item.get("head_pipeline") or {}).get("status")
        try:
            pipeline_status = PipelineStatus(pipeline_status_raw.lower()) if pipeline_status_raw else None
        except ValueError:
            pipeline_status = None

        values = dict(
            synced_project_id=project.id,
            gitlab_global_id=gitlab_id,
            gitlab_iid=str(item["iid"]),
            title=item["title"],
            state=mr_state,
            is_draft=bool(item.get("draft") or item.get("work_in_progress")),
            web_url=item["web_url"],
            author_user_id=author.id if author else None,
            pipeline_status=pipeline_status,
            has_unresolved_threads=False,  # TODO: GET .../discussions to populate accurately
            approvals_required=None,
            approvals_received=0,
            gitlab_created_at=parse_dt(item["created_at"]),
            gitlab_updated_at=parse_dt(item["updated_at"]),
            merged_at=parse_dt(item.get("merged_at")),
            last_activity_at=parse_dt(item["updated_at"]),
        )
        stmt = (
            pg_insert(MergeRequest)
            .values(**values)
            .on_conflict_do_update(index_elements=[MergeRequest.gitlab_global_id], set_=values)
            .returning(MergeRequest.id)
        )
        result = await db.execute(stmt)
        merge_request_id = result.scalar_one()
        await set_links(
            db,
            merge_request_id,
            linked_work_item_ids(item.get("title"), item.get("description"), work_item_id_by_iid),
        )

        for reviewer_item in item.get("reviewers", []):
            reviewer = await _get_or_create_user_stub(db, project.organization_id, _rest_user_to_graphql_shape(reviewer_item))
            if not reviewer:
                continue
            stmt = (
                pg_insert(MergeRequestReviewer)
                .values(merge_request_id=merge_request_id, user_id=reviewer.id)
                .on_conflict_do_nothing(
                    index_elements=[MergeRequestReviewer.merge_request_id, MergeRequestReviewer.user_id]
                )
            )
            await db.execute(stmt)


async def reconcile_project_via_rest(db: AsyncSession, project: SyncedProject) -> None:
    """REST v4 counterpart to `reconciliation.reconcile_project`, used when
    `project.uses_work_items_api` is False."""
    client = GitLabClient(access_token=settings.gitlab_sync_service_token)
    project_id = project.gitlab_project_id

    milestones = (await client.rest_get(f"/projects/{project_id}/milestones", {"per_page": 100})).json()
    labels = (await client.rest_get(f"/projects/{project_id}/labels", {"per_page": 100})).json()
    members = (await client.rest_get(f"/projects/{project_id}/members/all", {"per_page": 100})).json()
    issues = (await client.rest_get(f"/projects/{project_id}/issues", {"scope": "all", "per_page": 100})).json()
    merge_requests = (
        await client.rest_get(f"/projects/{project_id}/merge_requests", {"scope": "all", "per_page": 100})
    ).json()

    milestone_id_by_gid = await _upsert_milestones_rest(db, project, milestones)
    label_id_by_name = await _upsert_labels_rest(db, project, labels)
    await _upsert_members_rest(db, project, members)
    work_item_id_by_iid = await _upsert_issues_rest(db, project, issues, milestone_id_by_gid, label_id_by_name)
    await _upsert_merge_requests_rest(db, project, merge_requests, work_item_id_by_iid)
