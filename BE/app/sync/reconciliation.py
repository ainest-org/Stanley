"""Reconciliation: the periodic fallback pull that re-derives a synced project's state directly
from GitLab and overwrites the local cache (PRD Section 11.1). Per Section 13.1, when a webhook
event and a reconciliation pass disagree, reconciliation always wins — this module IS that
"ground truth" path, so it always writes straight from GitLab's response rather than merging
with whatever a webhook handler wrote in between.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import GitLabAccessLevel, MergeRequestState, PipelineStatus, WorkItemState
from app.models.label import Label
from app.models.merge_request import MergeRequest
from app.models.merge_request_reviewer import MergeRequestReviewer
from app.models.milestone import Milestone
from app.models.project_membership import ProjectMembership
from app.models.synced_project import SyncedProject
from app.models.user import User
from app.models.work_item import WorkItem, work_item_labels
from app.sync.gid import extract_id
from app.sync.gitlab_client import GitLabClient
from app.sync.queries import PROJECT_RECONCILE_QUERY

settings = get_settings()


def _normalize_work_item_state(raw: str) -> WorkItemState:
    return WorkItemState.CLOSED if raw.upper() == "CLOSED" else WorkItemState.OPENED


def _normalize_mr_state(raw: str) -> MergeRequestState:
    value = raw.upper()
    if value == "MERGED":
        return MergeRequestState.MERGED
    if value in ("CLOSED",):
        return MergeRequestState.CLOSED
    # GitLab's "locked" state means discussion is locked but the MR is still open.
    return MergeRequestState.OPENED


def _normalize_pipeline_status(raw: str | None) -> PipelineStatus | None:
    if not raw:
        return None
    try:
        return PipelineStatus(raw.lower())
    except ValueError:
        return None


async def _get_or_create_user_stub(db: AsyncSession, organization_id, gitlab_user: dict | None) -> User | None:
    """Ensures a User row exists for someone GitLab reports as an assignee/author/member, even
    if they've never signed into this tool themselves (Section 11.4 — role assignment happens
    separately; this just gives us an FK target for work items/MRs/memberships)."""
    if not gitlab_user:
        return None

    gitlab_user_id = extract_id(gitlab_user["id"])
    result = await db.execute(select(User).where(User.gitlab_user_id == gitlab_user_id))
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        organization_id=organization_id,
        gitlab_user_id=gitlab_user_id,
        gitlab_username=gitlab_user.get("username", ""),
        email=gitlab_user.get("publicEmail") or "",
        name=gitlab_user.get("name") or gitlab_user.get("username", ""),
        avatar_url=gitlab_user.get("avatarUrl"),
    )
    db.add(user)
    await db.flush()
    return user


async def _upsert_milestones(db: AsyncSession, project: SyncedProject, nodes: list[dict]) -> dict[str, object]:
    id_map: dict[str, object] = {}
    for node in nodes:
        gitlab_id = extract_id(node["id"])
        stmt = (
            pg_insert(Milestone)
            .values(
                synced_project_id=project.id,
                gitlab_milestone_id=gitlab_id,
                title=node["title"],
                state=(node.get("state") or "active").lower(),
                starts_at=node.get("startDate"),
                due_at=node.get("dueDate"),
            )
            .on_conflict_do_update(
                index_elements=[Milestone.gitlab_milestone_id],
                set_={
                    "title": node["title"],
                    "state": (node.get("state") or "active").lower(),
                    "starts_at": node.get("startDate"),
                    "due_at": node.get("dueDate"),
                },
            )
            .returning(Milestone.id)
        )
        result = await db.execute(stmt)
        id_map[gitlab_id] = result.scalar_one()
    return id_map


async def _upsert_labels(db: AsyncSession, project: SyncedProject, nodes: list[dict]) -> dict[str, object]:
    id_map: dict[str, object] = {}
    for node in nodes:
        gitlab_id = extract_id(node["id"])
        stmt = (
            pg_insert(Label)
            .values(
                synced_project_id=project.id,
                gitlab_label_id=gitlab_id,
                name=node["title"],
                color=node.get("color"),
            )
            .on_conflict_do_update(
                index_elements=[Label.gitlab_label_id],
                set_={"name": node["title"], "color": node.get("color")},
            )
            .returning(Label.id)
        )
        result = await db.execute(stmt)
        id_map[gitlab_id] = result.scalar_one()
    return id_map


async def _upsert_members(db: AsyncSession, project: SyncedProject, nodes: list[dict]) -> dict[str, object]:
    id_map: dict[str, object] = {}
    for node in nodes:
        user = await _get_or_create_user_stub(db, project.organization_id, node.get("user"))
        if not user:
            continue
        id_map[user.gitlab_user_id] = user.id

        raw_level = (node.get("accessLevel") or {}).get("stringValue", "").lower()
        try:
            access_level = GitLabAccessLevel(raw_level)
        except ValueError:
            continue  # e.g. "no access" / "minimal access" — not a role we track

        stmt = (
            pg_insert(ProjectMembership)
            .values(synced_project_id=project.id, user_id=user.id, access_level=access_level)
            .on_conflict_do_update(
                index_elements=[ProjectMembership.synced_project_id, ProjectMembership.user_id],
                set_={"access_level": access_level},
            )
        )
        await db.execute(stmt)
    return id_map


def _widget(node: dict, type_name: str) -> dict:
    for widget in node.get("widgets", []):
        if widget.get("__typename") == type_name:
            return widget
    return {}


async def _upsert_work_items(
    db: AsyncSession,
    project: SyncedProject,
    nodes: list[dict],
    milestone_id_by_gid: dict,
    label_id_by_gid: dict,
) -> dict[str, object]:
    """Returns {gitlab_iid: local work_item_id} so merge requests can be linked to the work
    item GitLab links them to (Section 11.5)."""
    work_item_id_by_iid: dict[str, object] = {}

    for node in nodes:
        gitlab_id = extract_id(node["id"])
        author = await _get_or_create_user_stub(db, project.organization_id, node.get("author"))

        assignees_widget = _widget(node, "WorkItemWidgetAssignees")
        assignee_nodes = (assignees_widget.get("assignees") or {}).get("nodes", [])
        assignee = await _get_or_create_user_stub(db, project.organization_id, assignee_nodes[0]) if assignee_nodes else None

        description = _widget(node, "WorkItemWidgetDescription").get("description")
        milestone_gid = (_widget(node, "WorkItemWidgetMilestone").get("milestone") or {}).get("id")
        milestone_id = milestone_id_by_gid.get(extract_id(milestone_gid)) if milestone_gid else None

        values = dict(
            synced_project_id=project.id,
            gitlab_global_id=gitlab_id,
            gitlab_iid=str(node["iid"]),
            title=node["title"],
            description=description,
            item_type=(node.get("workItemType") or {}).get("name", "Issue").lower(),
            state=_normalize_work_item_state(node["state"]),
            web_url=node["webUrl"],
            assignee_user_id=assignee.id if assignee else None,
            author_user_id=author.id if author else None,
            milestone_id=milestone_id,
            gitlab_created_at=node["createdAt"],
            gitlab_updated_at=node["updatedAt"],
            closed_at=node.get("closedAt"),
            last_activity_at=node["updatedAt"],
        )

        stmt = (
            pg_insert(WorkItem)
            .values(**values)
            .on_conflict_do_update(index_elements=[WorkItem.gitlab_global_id], set_=values)
            .returning(WorkItem.id)
        )
        result = await db.execute(stmt)
        work_item_id = result.scalar_one()
        work_item_id_by_iid[str(node["iid"])] = work_item_id

        label_nodes = (_widget(node, "WorkItemWidgetLabels").get("labels") or {}).get("nodes", [])
        label_ids = [label_id_by_gid[extract_id(n["id"])] for n in label_nodes if extract_id(n["id"]) in label_id_by_gid]
        await db.execute(work_item_labels.delete().where(work_item_labels.c.work_item_id == work_item_id))
        if label_ids:
            await db.execute(
                work_item_labels.insert(),
                [{"work_item_id": work_item_id, "label_id": lid} for lid in label_ids],
            )

    return work_item_id_by_iid


async def _upsert_merge_requests(
    db: AsyncSession,
    project: SyncedProject,
    nodes: list[dict],
    work_item_id_by_iid: dict,
) -> None:
    for node in nodes:
        gitlab_id = extract_id(node["id"])
        author = await _get_or_create_user_stub(db, project.organization_id, node.get("author"))

        approvals_required = node.get("approvalsRequired")
        approvals_left = node.get("approvalsLeft")
        approvals_received = (
            max(0, approvals_required - approvals_left)
            if approvals_required is not None and approvals_left is not None
            else 0
        )

        values = dict(
            synced_project_id=project.id,
            work_item_id=work_item_id_by_iid.get(str(node["iid"])),
            gitlab_global_id=gitlab_id,
            gitlab_iid=str(node["iid"]),
            title=node["title"],
            state=_normalize_mr_state(node["state"]),
            is_draft=bool(node.get("draft")),
            web_url=node["webUrl"],
            author_user_id=author.id if author else None,
            pipeline_status=_normalize_pipeline_status((node.get("headPipeline") or {}).get("status")),
            has_unresolved_threads=False,  # TODO: not covered by this pass's query yet
            approvals_required=approvals_required,
            approvals_received=approvals_received,
            gitlab_created_at=node["createdAt"],
            gitlab_updated_at=node["updatedAt"],
            merged_at=node.get("mergedAt"),
            last_activity_at=node["updatedAt"],
        )

        stmt = (
            pg_insert(MergeRequest)
            .values(**values)
            .on_conflict_do_update(index_elements=[MergeRequest.gitlab_global_id], set_=values)
            .returning(MergeRequest.id)
        )
        result = await db.execute(stmt)
        merge_request_id = result.scalar_one()

        reviewer_nodes = (node.get("reviewers") or {}).get("nodes", [])
        for reviewer_node in reviewer_nodes:
            reviewer = await _get_or_create_user_stub(db, project.organization_id, reviewer_node)
            if not reviewer:
                continue
            stmt = (
                pg_insert(MergeRequestReviewer)
                .values(merge_request_id=merge_request_id, user_id=reviewer.id)
                .on_conflict_do_nothing(index_elements=[MergeRequestReviewer.merge_request_id, MergeRequestReviewer.user_id])
            )
            await db.execute(stmt)


async def _reconcile_project_via_graphql(db: AsyncSession, project: SyncedProject) -> None:
    client = GitLabClient(access_token=settings.gitlab_sync_service_token)

    data = await client.graphql(PROJECT_RECONCILE_QUERY, {"fullPath": project.gitlab_full_path})
    project_data = data["project"]
    if project_data is None:
        # Project no longer reachable with this token — leave it as-is rather than guessing;
        # an admin-visible sync error should surface here in a future pass.
        return

    milestone_id_by_gid = await _upsert_milestones(db, project, project_data["milestones"]["nodes"])
    label_id_by_gid = await _upsert_labels(db, project, project_data["labels"]["nodes"])
    await _upsert_members(db, project, project_data["projectMembers"]["nodes"])
    work_item_id_by_iid = await _upsert_work_items(
        db, project, project_data["workItems"]["nodes"], milestone_id_by_gid, label_id_by_gid
    )
    await _upsert_merge_requests(db, project, project_data["mergeRequests"]["nodes"], work_item_id_by_iid)


async def reconcile_project(db: AsyncSession, project: SyncedProject) -> None:
    """Full re-pull + diff-and-overwrite for one synced project (PRD Section 11.1). Called on
    the 15-minute periodic tick and available for a manual "refresh now" (Section 11.1).

    Dispatches to the Work Items (GraphQL) or classic Issues (REST) path depending on what was
    detected for this project at setup time (Section 5.2 step 1 / 13.1)."""
    if project.uses_work_items_api:
        await _reconcile_project_via_graphql(db, project)
    else:
        from app.sync.reconciliation_rest import reconcile_project_via_rest

        await reconcile_project_via_rest(db, project)

    now = datetime.now(timezone.utc)
    project.last_synced_at = now
    project.last_reconciled_at = now
    project.reconciliation_backoff_seconds = 0

    await db.commit()
