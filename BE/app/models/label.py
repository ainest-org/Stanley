import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Label(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Raw GitLab label, plus an optional normalized mapping (PRD Section 5.2 step 4).
    Unmapped labels render as-is — mapping is optional, never required (Section 13.6)."""

    __tablename__ = "labels"

    synced_project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("synced_projects.id"))

    gitlab_label_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # e.g. mapped_concept="priority", mapped_value="high" for a raw label like "priority::high"
    mapped_concept: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mapped_value: Mapped[str | None] = mapped_column(String(64), nullable=True)
