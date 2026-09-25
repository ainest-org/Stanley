import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Milestone(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "milestones"

    synced_project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("synced_projects.id"))

    gitlab_milestone_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(32), default="active")
    starts_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)
