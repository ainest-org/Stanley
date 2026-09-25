"""Which single item a GitLab webhook payload is about, so we refresh just that."""


def webhook_target(payload: dict) -> tuple[str, str] | None:
    """(kind, iid) of the issue or merge request the event concerns, or None when there's nothing
    specific to refresh (e.g. a pipeline on a plain branch)."""
    kind = payload.get("object_kind")
    attributes = payload.get("object_attributes") or {}

    if kind in ("issue", "work_item") and attributes.get("iid") is not None:
        return "issue", str(attributes["iid"])
    if kind == "merge_request" and attributes.get("iid") is not None:
        return "merge_request", str(attributes["iid"])
    if kind == "pipeline":
        merge_request = payload.get("merge_request") or {}
        if merge_request.get("iid") is not None:
            return "merge_request", str(merge_request["iid"])
    return None
