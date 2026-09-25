import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class BlockedFlag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The one piece of custom data My Work stores locally, since GitLab has no clean
    equivalent (PRD Section 6.4 / 11.4). Visible to the flagged person's manager and surfaced
    on Team Board / Radar."""

    __tablename__ = "blocked_flags"

    work_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_items.id"))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    reason: Mapped[str] = mapped_column(String(2048))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
