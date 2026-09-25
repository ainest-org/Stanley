from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Single org per deployment (PRD: not multi-tenant in v1). Root of the sync hierarchy
    described in Section 11.5: Organization -> SyncedProject -> WorkItem/MergeRequest -> User."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255))
    gitlab_instance_url: Mapped[str] = mapped_column(String(512))

    # Health-rule thresholds, admin-tunable with these as the shipped defaults (PRD Section
    # 5.2 step 5 / 13.4 two-speed escalation: stale items re-surface frequently since they
    # usually just need a nudge; blocked items re-alert infrequently since pinging more often
    # rarely unblocks a real blocker).
    stale_threshold_days: Mapped[int] = mapped_column(default=5)
    stale_recheck_days: Mapped[int] = mapped_column(default=2)
    blocked_recheck_days: Mapped[int] = mapped_column(default=5)
    review_sla_days: Mapped[int] = mapped_column(default=2)
    overloaded_item_threshold: Mapped[int] = mapped_column(default=5)

    # A GitLab label (e.g. "status::doing") that marks a work item as in progress. Lets My Work's
    # "Doing now" reflect work that has no draft MR yet (PRD 5.2 step 4, label mapping).
    in_progress_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
