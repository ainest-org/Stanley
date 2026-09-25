import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class StandupFollow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A manager choosing to follow a person in the standup digest. Lets managers narrow the
    digest to their own team while the default stays "everyone" (no reporting-line data yet)."""

    __tablename__ = "standup_follows"
    __table_args__ = (UniqueConstraint("manager_user_id", "person_user_id", name="uq_standup_follow"),)

    manager_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    person_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
