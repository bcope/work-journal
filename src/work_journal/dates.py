"""Date utilities for anchoring bare dates to local midnight."""

from datetime import datetime, timedelta


def midnight_iso(date_str: str) -> str:
    """Convert YYYY-MM-DD to an ISO 8601 timestamp at local midnight.

    Git and GitHub interpret bare dates relative to the current wall-clock
    time. This function anchors them to 00:00:00 in the system's local
    timezone so that date-range queries cover full calendar days.
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    local_dt = dt.astimezone()
    return local_dt.isoformat()


def resolve_window_bound(value: str, *, end: bool = False) -> datetime:
    """Parse a window bound (YYYY-MM-DD or ISO 8601 datetime) to an aware datetime.

    Bare dates anchor to local midnight; an *end* date rolls to the next
    day's midnight so the named day is fully included when used in a
    half-open [since, until) window. Naive datetimes are assumed local.
    """
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.astimezone()
    if end:
        d += timedelta(days=1)
    return d.astimezone()
