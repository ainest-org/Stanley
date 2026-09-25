import uuid
from datetime import date
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.tokens import get_write_access_token
from app.core import idempotency
from app.db.session import get_db
from app.models.enums import WorkItemState
from app.models.label import Label
from app.models.merge_request import MergeRequest
from app.models.merge_request_reviewer import MergeRequestReviewer
from app.models.milestone import Milestone
from app.models.project_membership import ProjectMembership
from app.models.synced_project import SyncedProject
from app.models.user import User, is_placeholder_username
from app.models.work_item import WorkItem, work_item_labels
from app.sync.gid import parse_dt
from app.sync.mutations import add_note, create_issue, set_merge_request_reviewers

router = APIRouter(prefix="/api", tags=["work-item-actions"])


def _gitlab_rejected(exc: httpx.HTTPStatusError) -> HTTPException:
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY, f"GitLab rejected this ({exc.response.status_code}): {exc.response.text}"
    )


# ---------------------------------------------------------------------------
# Lookups that feed the create form and the review-request picker
# ---------------------------------------------------------------------------


@router.get("/projects")
async def list_projects(_: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(
        select(SyncedProject).where(SyncedProject.is_active.is_(True)).order_by(SyncedProject.name)
    )
    return [{"id": str(p.id), "name": p.name} for p in result.scalars().all()]


@router.get("/members")
async def list_all_members(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    result = await db.execute(
        select(User).where(User.organization_id == current_user.organization_id).order_by(User.name)
    )
    return [
        {"id": str(u.id), "name": u.name}
        for u in result.scalars().all()
        if not is_placeholder_username(u.gitlab_username)
    ]


@router.get("/projects/{project_id}/create-options")
async def create_options(
    project_id: uuid.UUID, _: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Only that project's current members, active milestones and labels (PRD Section 13.3)."""
    members = (
        (
            await db.execute(
                select(User)
                .join(ProjectMembership, ProjectMembership.user_id == User.id)
                .where(ProjectMembership.synced_project_id == project_id)
                .order_by(User.name)
            )
        )
        .scalars()
        .all()
    )
    milestones = (
        (
            await db.execute(
                select(Milestone).where(Milestone.synced_project_id == project_id).where(Milestone.state == "active")
            )
        )
        .scalars()
        .all()
    )
    labels = (
        (await db.execute(select(Label).where(Label.synced_project_id == project_id).order_by(Label.name)))
        .scalars()
        .all()
    )

    return {
        "members": [
            {"id": str(u.id), "name": u.name} for u in members if not is_placeholder_username(u.gitlab_username)
        ],
        "milestones": [{"id": str(m.id), "title": m.title} for m in milestones],
        "labels": [{"id": str(label.id), "name": label.name, "color": label.color} for label in labels],
    }


# ---------------------------------------------------------------------------
# Create work item (PRD Section 9.3)
# ---------------------------------------------------------------------------


class CreateWorkItemRequest(BaseModel):
    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=1024)
    idempotency_key: str = Field(min_length=8, max_length=100)
    item_type: Literal["issue", "task", "incident"] = "issue"
    description: str | None = None
    assignee_user_id: uuid.UUID | None = None
    milestone_id: uuid.UUID | None = None
    label_ids: list[uuid.UUID] = []
    due_date: date | None = None


@router.post("/work-items", status_code=status.HTTP_201_CREATED)
async def create_work_item(
    body: CreateWorkItemRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    project = await db.get(SyncedProject, body.project_id)
    if project is None or not project.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found or not synced")

    access_token = await get_write_access_token(db, current_user)

    existing = await idempotency.claim(body.idempotency_key)
    if existing == idempotency.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "This work item is already being created")
    if existing:
        duplicate = await db.get(WorkItem, uuid.UUID(existing))
        if duplicate:
            return {"id": str(duplicate.id), "web_url": duplicate.web_url, "duplicate": True}

    fields: dict = {"title": body.title, "issue_type": body.item_type}
    if body.description:
        fields["description"] = body.description
    if body.due_date:
        fields["due_date"] = body.due_date.isoformat()

    assignee = await db.get(User, body.assignee_user_id) if body.assignee_user_id else None
    if assignee:
        fields["assignee_ids"] = [int(assignee.gitlab_user_id)]

    milestone = await db.get(Milestone, body.milestone_id) if body.milestone_id else None
    if milestone:
        fields["milestone_id"] = int(milestone.gitlab_milestone_id)

    labels = []
    if body.label_ids:
        labels = (await db.execute(select(Label).where(Label.id.in_(body.label_ids)))).scalars().all()
        fields["labels"] = ",".join(label.name for label in labels)

    try:
        issue = await create_issue(project, fields, access_token)
    except httpx.HTTPStatusError as exc:
        await idempotency.release(body.idempotency_key)
        raise _gitlab_rejected(exc) from exc

    # Reflect it immediately as a normal synced item; the next reconciliation overwrites it.
    values = dict(
        synced_project_id=project.id,
        gitlab_global_id=str(issue["id"]),
        gitlab_iid=str(issue["iid"]),
        title=issue["title"],
        description=issue.get("description"),
        item_type=body.item_type,
        state=WorkItemState.OPENED,
        web_url=issue["web_url"],
        assignee_user_id=assignee.id if assignee else None,
        author_user_id=current_user.id,
        milestone_id=milestone.id if milestone else None,
        gitlab_created_at=parse_dt(issue["created_at"]),
        gitlab_updated_at=parse_dt(issue["updated_at"]),
        closed_at=None,
        last_activity_at=parse_dt(issue["updated_at"]),
    )
    work_item_id = (
        await db.execute(
            pg_insert(WorkItem)
            .values(**values)
            .on_conflict_do_update(index_elements=[WorkItem.gitlab_global_id], set_=values)
            .returning(WorkItem.id)
        )
    ).scalar_one()
    if labels:
        await db.execute(work_item_labels.delete().where(work_item_labels.c.work_item_id == work_item_id))
        await db.execute(
            work_item_labels.insert(), [{"work_item_id": work_item_id, "label_id": label.id} for label in labels]
        )
    await db.commit()

    await idempotency.complete(body.idempotency_key, str(work_item_id))
    return {"id": str(work_item_id), "web_url": issue["web_url"], "duplicate": False}


# ---------------------------------------------------------------------------
# Comment + request review (PRD Section 6.4)
# ---------------------------------------------------------------------------


class CommentRequest(BaseModel):
    body: str = Field(min_length=1)


@router.post("/work-items/{work_item_id}/comment", status_code=status.HTTP_201_CREATED)
async def comment_on_work_item(
    work_item_id: uuid.UUID,
    body: CommentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = await db.get(WorkItem, work_item_id)
    project = await db.get(SyncedProject, item.synced_project_id) if item else None
    if item is None or project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work item not found")

    access_token = await get_write_access_token(db, current_user)
    try:
        await add_note(project, "issues", item.gitlab_iid, body.body, access_token)
    except httpx.HTTPStatusError as exc:
        raise _gitlab_rejected(exc) from exc
    return {"ok": True}


@router.post("/merge-requests/{merge_request_id}/comment", status_code=status.HTTP_201_CREATED)
async def comment_on_merge_request(
    merge_request_id: uuid.UUID,
    body: CommentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    mr = await db.get(MergeRequest, merge_request_id)
    project = await db.get(SyncedProject, mr.synced_project_id) if mr else None
    if mr is None or project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merge request not found")

    access_token = await get_write_access_token(db, current_user)
    try:
        await add_note(project, "merge_requests", mr.gitlab_iid, body.body, access_token)
    except httpx.HTTPStatusError as exc:
        raise _gitlab_rejected(exc) from exc
    return {"ok": True}


class RequestReviewRequest(BaseModel):
    reviewer_user_id: uuid.UUID


@router.post("/merge-requests/{merge_request_id}/reviewers")
async def request_review(
    merge_request_id: uuid.UUID,
    body: RequestReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    mr = await db.get(MergeRequest, merge_request_id)
    project = await db.get(SyncedProject, mr.synced_project_id) if mr else None
    reviewer = await db.get(User, body.reviewer_user_id)
    if mr is None or project is None or reviewer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merge request or reviewer not found")

    existing_ids = (
        (
            await db.execute(
                select(User.gitlab_user_id)
                .join(MergeRequestReviewer, MergeRequestReviewer.user_id == User.id)
                .where(MergeRequestReviewer.merge_request_id == mr.id)
            )
        )
        .scalars()
        .all()
    )
    reviewer_ids = sorted({int(g) for g in existing_ids} | {int(reviewer.gitlab_user_id)})

    access_token = await get_write_access_token(db, current_user)
    try:
        await set_merge_request_reviewers(project, mr.gitlab_iid, reviewer_ids, access_token)
    except httpx.HTTPStatusError as exc:
        raise _gitlab_rejected(exc) from exc

    await db.execute(
        pg_insert(MergeRequestReviewer)
        .values(merge_request_id=mr.id, user_id=reviewer.id)
        .on_conflict_do_nothing(index_elements=[MergeRequestReviewer.merge_request_id, MergeRequestReviewer.user_id])
    )
    await db.commit()
    return {"ok": True}
