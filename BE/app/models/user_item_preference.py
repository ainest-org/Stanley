import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class UserItemPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A person's own view settings for a work item: watching it, or snoozing it off My Work
    until a date. Locally owned and private to that person; never written to GitLab."""

    __tablename__ = "user_item_preferences"
    __table_args__ = (UniqueConstraint("user_id", "work_item_id", name="uq_user_item_preference"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    work_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_items.id"))

    watching: Mapped[bool] = mapped_column(Boolean, default=False)
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
