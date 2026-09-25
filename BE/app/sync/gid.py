def extract_id(value: str | int) -> str:
    """Normalize a GitLab identifier to a plain string, whether it came back as a GraphQL
    global ID (e.g. "gid://gitlab/WorkItem/123") or a plain REST integer id."""
    text = str(value)
    if "/" in text:
        return text.rsplit("/", 1)[-1]
    return text


def parse_dt(value: str | None):
    """GitLab returns ISO-8601 strings ("2026-09-25T05:55:35Z"); asyncpg needs real datetimes."""
    from datetime import datetime

    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_date(value: str | None):
    from datetime import date

    if not value:
        return None
    return date.fromisoformat(value[:10])
