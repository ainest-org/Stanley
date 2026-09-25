import enum


class WorkItemState(str, enum.Enum):
    OPENED = "opened"
    CLOSED = "closed"


class MergeRequestState(str, enum.Enum):
    OPENED = "opened"
    CLOSED = "closed"
    MERGED = "merged"


class PipelineStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"
    PENDING = "pending"
    CANCELED = "canceled"
    SKIPPED = "skipped"


class GitLabAccessLevel(str, enum.Enum):
    """Mirrors GitLab's own permission levels (PRD Section 12) — the hard ceiling on what
    a user's OAuth-scoped API calls can do, independent of their in-tool role."""

    GUEST = "guest"
    REPORTER = "reporter"
    DEVELOPER = "developer"
    MAINTAINER = "maintainer"
    OWNER = "owner"


class ReviewState(str, enum.Enum):
    REQUESTED = "requested"
    REVIEWED = "reviewed"
    APPROVED = "approved"
