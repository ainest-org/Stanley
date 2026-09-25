import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CheckIn(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Async, opt-in standup response (PRD Section 10.1 / 11.4). Skipping doesn't block
    anything or flag the person — `skipped` just records that the day was skipped."""

    __tablename__ = "check_ins"
    __table_args__ = (UniqueConstraint("user_id", "check_in_date", name="uq_check_in_per_day"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    check_in_date: Mapped[date] = mapped_column(Date)

    did_text: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    doing_text: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    blockers_text: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
