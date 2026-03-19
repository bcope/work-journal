"""Tests for work_journal.dates."""

import re

from work_journal.dates import midnight_iso


def test_midnight_iso_format():
    """Output matches ISO 8601 with timezone offset."""
    result = midnight_iso("2026-03-17")
    # Should match YYYY-MM-DDTHH:MM:SS+HH:MM or similar offset format
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", result)


def test_midnight_iso_time_is_midnight():
    """Time component is always T00:00:00."""
    result = midnight_iso("2026-03-17")
    assert "T00:00:00" in result


def test_midnight_iso_preserves_date():
    """Date portion matches the input."""
    result = midnight_iso("2026-01-15")
    assert result.startswith("2026-01-15T")


def test_midnight_iso_different_dates():
    """Works for various valid date strings."""
    for date_str in ["2025-12-31", "2026-01-01", "2026-06-15"]:
        result = midnight_iso(date_str)
        assert result.startswith(f"{date_str}T00:00:00")
