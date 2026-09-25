import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import MergeRequestState, PipelineStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


# A work item can have many merge requests, and one merge request can serve several work items.
merge_request_work_items = Table(
    "merge_request_work_items",
    Base.metadata,
    Column("merge_request_id", UUID(as_uuid=True), ForeignKey("merge_requests.id"), primary_key=True),
    Column("work_item_id", UUID(as_uuid=True), ForeignKey("work_items.id"), primary_key=True),
)


class MergeRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Mirrors a GitLab MR (PRD Section 11.2). Diffs/code content are never cached — always
    deep-linked to GitLab (Section 11.3); only review/pipeline/thread-resolution state lives here."""

    __tablename__ = "merge_requests"

    synced_project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("synced_projects.id"))

    gitlab_global_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    gitlab_iid: Mapped[str] = mapped_column(String(32))

    title: Mapped[str] = mapped_column(String(1024))
    state: Mapped[MergeRequestState] = mapped_column(Enum(MergeRequestState, name="merge_request_state"))
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    web_url: Mapped[str] = mapped_column(String(1024))

    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    pipeline_status: Mapped[PipelineStatus | None] = mapped_column(
        Enum(PipelineStatus, name="pipeline_status"), nullable=True
    )
    # Counts only, never full thread content (Section 11.3) — full threads are read live via
    # API when a detail panel is opened (Section 7.4).
    has_unresolved_threads: Mapped[bool] = mapped_column(Boolean, default=False)
    approvals_required: Mapped[int | None] = mapped_column(nullable=True)
    approvals_received: Mapped[int] = mapped_column(default=0)

    gitlab_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    gitlab_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
