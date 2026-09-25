import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import WorkItemState
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

work_item_labels = Table(
    "work_item_labels",
    Base.metadata,
    Column("work_item_id", UUID(as_uuid=True), ForeignKey("work_items.id"), primary_key=True),
    Column("label_id", UUID(as_uuid=True), ForeignKey("labels.id"), primary_key=True),
)


class WorkItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Mirrors a GitLab work item / issue (PRD Section 11.2). GitLab is authoritative; this
    row is a read cache plus a foreign key for the few locally-owned records that hang off it
    (BlockedFlag, per Section 11.4)."""

    __tablename__ = "work_items"

    synced_project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("synced_projects.id"))

    # GitLab's GraphQL global ID — stable across REST/GraphQL and across renames (Section 13.6).
    gitlab_global_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    gitlab_iid: Mapped[str] = mapped_column(String(32))

    title: Mapped[str] = mapped_column(String(1024))
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    item_type: Mapped[str] = mapped_column(String(32), default="issue")
    state: Mapped[WorkItemState] = mapped_column(Enum(WorkItemState, name="work_item_state"))
    web_url: Mapped[str] = mapped_column(String(1024))

    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    milestone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("milestones.id"), nullable=True
    )

    gitlab_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    gitlab_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Last real activity from GitLab's side (comment, state change, etc.) — the basis for the
    # "no activity > N days" stale/blocked health rules (Section 6.3, 13.4).
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
