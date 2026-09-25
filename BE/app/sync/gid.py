def extract_id(value: str | int) -> str:
    """Normalize a GitLab identifier to a plain string, whether it came back as a GraphQL
    global ID (e.g. "gid://gitlab/WorkItem/123") or a plain REST integer id."""
    text = str(value)
    if "/" in text:
        return text.rsplit("/", 1)[-1]
    return text
