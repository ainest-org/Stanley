import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SyncedProject(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A GitLab project the admin has chosen to sync (PRD Section 5.2 step 2). Identified by
    GitLab's stable project ID, never by path/name, so a group restructure or rename doesn't
    orphan synced data (Section 13.6)."""

    __tablename__ = "synced_projects"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"))

    gitlab_project_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    gitlab_full_path: Mapped[str] = mapped_column(String(512))
    name: Mapped[str] = mapped_column(String(255))
    web_url: Mapped[str] = mapped_column(String(1024))

    # Detected during setup (Section 5.2 step 1 / 13.1 last row): self-hosted instances on an
    # older GitLab version fall back to the classic Issues API.
    uses_work_items_api: Mapped[bool] = mapped_column(Boolean, default=True)

    # Webhook registered on this GitLab project for near-real-time sync (Section 11.1 primary path).
    gitlab_webhook_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    webhook_secret_token: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Admin can unsync a project without deleting its history (Section 13.1: "Project/group
    # unsynced by admin mid-use" — items disappear from dashboards but aren't purged).
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Backoff state for rate-limited reconciliation polling (Section 13.1: exponential backoff
    # per project, staggered rather than hammering every project on the same tick).
    reconciliation_backoff_seconds: Mapped[int] = mapped_column(default=0)
