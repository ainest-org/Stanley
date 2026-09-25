import uuid

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import ReviewState
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class MergeRequestReviewer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A requested reviewer on an MR, and their review state — drives My Work's
    'Review requests' bucket (PRD Section 6.2) and 'reviews pending past SLA' (Section 7.2)."""

    __tablename__ = "merge_request_reviewers"
    __table_args__ = (UniqueConstraint("merge_request_id", "user_id", name="uq_mr_reviewer"),)

    merge_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("merge_requests.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    state: Mapped[ReviewState] = mapped_column(Enum(ReviewState, name="review_state"), default=ReviewState.REQUESTED)
