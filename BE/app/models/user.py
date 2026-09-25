import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class InToolRole(str, enum.Enum):
    """In-tool role (PRD Section 3/12) — governs screens/views, never grants GitLab access
    beyond what the user's own GitLab permission already allows."""

    ENGINEER = "engineer"
    MANAGER = "manager"
    EXEC = "exec"
    ADMIN = "admin"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"))

    # GitLab identity — always the source of truth for who this person is (PRD 5.1)
    gitlab_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    gitlab_username: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320))
    name: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # OAuth token, encrypted at rest (PRD Section 14) — used to call GitLab's API as this user
    # so permission-mirroring is automatic (Section 5.1 / 12). Null until the person's first
    # login: reconciliation can create a User stub for a synced project member (e.g. to hang an
    # assignee/author FK off of) before they've ever signed into this tool themselves.
    encrypted_access_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    token_expires_at: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # In-tool role, set explicitly by an Admin during onboarding (Section 5.2 step 3) —
    # independent from whatever GitLab permission this person happens to hold.
    in_tool_role: Mapped[InToolRole] = mapped_column(
        Enum(InToolRole, name="in_tool_role"), default=InToolRole.ENGINEER
    )

    is_active: Mapped[bool] = mapped_column(default=True)
