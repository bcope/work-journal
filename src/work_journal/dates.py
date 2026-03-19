"""Date utilities for anchoring bare dates to local midnight."""

from datetime import datetime


def midnight_iso(date_str: str) -> str:
    """Convert YYYY-MM-DD to an ISO 8601 timestamp at local midnight.

    Git and GitHub interpret bare dates relative to the current wall-clock
    time. This function anchors them to 00:00:00 in the system's local
    timezone so that date-range queries cover full calendar days.
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    local_dt = dt.astimezone()
    return local_dt.isoformat()
