import uuid

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import GitLabAccessLevel
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ProjectMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cached GitLab project membership + access level (PRD Section 11.2 / 12). Used to render
    the People directory (Section 9.2) and to know which members are valid assignees for a
    given project when creating a work item (Section 13.3: dropdown filtered to current members)."""

    __tablename__ = "project_memberships"
    __table_args__ = (UniqueConstraint("synced_project_id", "user_id", name="uq_project_membership"),)

    synced_project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("synced_projects.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    access_level: Mapped[GitLabAccessLevel] = mapped_column(Enum(GitLabAccessLevel, name="gitlab_access_level"))
