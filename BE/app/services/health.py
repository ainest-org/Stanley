"""Shared status/health computations used by My Work, Team Board, and Exec Radar (PRD Section
6.3, 7.2, 13.4). Every rule here is a simple, visible threshold check on synced data — never a
black-box score (Section 4: "Transparent inference")."""

from datetime import datetime, timezone

from app.models.enums import MergeRequestState, PipelineStatus
from app.models.merge_request import MergeRequest
from app.models.organization import Organization


def days_since(moment: datetime) -> float:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - moment).total_seconds() / 86400


def mr_status_badge(mr: MergeRequest | None) -> str | None:
    """Card badge per PRD Section 6.3: Draft / Open / Approved / Pipeline failing / Merged."""
    if mr is None:
        return None
    if mr.state == MergeRequestState.MERGED:
        return "merged"
    if mr.is_draft:
        return "draft"
    if mr.pipeline_status == PipelineStatus.FAILED:
        return "pipeline_failing"
    if mr.approvals_received > 0:
        return "approved"
    return "open"


def is_stale(last_activity_at: datetime, org: Organization) -> bool:
    """No activity for longer than the org's configured threshold (Section 5.2 step 5 / 13.4)."""
    return days_since(last_activity_at) > org.stale_threshold_days


def is_overdue_for_review(mr: MergeRequest, org: Organization) -> bool:
    """Review pending past the org's SLA (Section 6.3 / 7.2)."""
    if mr.state != MergeRequestState.MERGED and not mr.is_draft:
        return days_since(mr.last_activity_at) > org.review_sla_days
    return False


def is_work_item_flagged(
    last_activity_at: datetime,
    linked_mr: MergeRequest | None,
    org: Organization,
    has_active_blocked_flag: bool,
) -> bool:
    """The card-level "Blocked" flag (Section 6.3): any of — no activity past the stale
    threshold, the linked MR's pipeline is failing, or a manager/self already flagged it
    blocked (Section 6.4, the one locally-owned field)."""
    if has_active_blocked_flag:
        return True
    if is_stale(last_activity_at, org):
        return True
    if linked_mr is not None and linked_mr.pipeline_status == PipelineStatus.FAILED:
        return True
    return False
