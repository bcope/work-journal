"""Tests for work_journal.dates."""

import re
from datetime import UTC

from work_journal.dates import midnight_iso, resolve_window_bound, window_bounds_iso


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


def test_resolve_window_bound_bare_date_is_local_midnight():
    """A bare date anchors to local midnight of that day."""
    dt = resolve_window_bound("2026-07-15")
    assert (dt.hour, dt.minute) == (0, 0)
    assert dt.tzinfo is not None
    assert dt.date().isoformat() == "2026-07-15"


def test_resolve_window_bound_end_date_rolls_to_next_midnight():
    """An end-bound bare date rolls to the next day's midnight (half-open)."""
    dt = resolve_window_bound("2026-07-15", end=True)
    assert dt.date().isoformat() == "2026-07-16"
    assert (dt.hour, dt.minute) == (0, 0)


def test_resolve_window_bound_iso_datetime_passthrough():
    """ISO datetimes pass through unchanged, including Z-suffixed UTC."""
    dt = resolve_window_bound("2026-07-14T17:30:48.893Z")
    assert dt.tzinfo is not None
    assert dt.astimezone(UTC).hour == 17


def test_resolve_window_bound_iso_datetime_ignores_end_flag():
    """The end flag only affects bare dates, not explicit datetimes."""
    dt = resolve_window_bound("2026-07-14T17:30:48.893Z", end=True)
    assert dt.astimezone(UTC).day == 14
    assert dt.astimezone(UTC).hour == 17


def test_resolve_window_bound_naive_datetime_assumed_local():
    """A naive datetime is interpreted in the system local timezone."""
    dt = resolve_window_bound("2026-07-14T13:00:00")
    assert dt.tzinfo is not None
    assert (dt.hour, dt.day) == (13, 14)


def test_window_bounds_iso_bare_dates_include_full_days():
    """A bare-date pair covers both named days entirely."""
    since, until = window_bounds_iso("2026-07-15", "2026-07-30")
    assert since.startswith("2026-07-15T00:00:00")
    assert until.startswith("2026-07-31T00:00:00")


def test_window_bounds_iso_datetimes_pass_through():
    """Explicit datetimes are preserved exactly."""
    since, until = window_bounds_iso("2026-07-14T17:30:48+00:00", "2026-07-30T17:00:00+00:00")
    assert since == "2026-07-14T17:30:48+00:00"
    assert until == "2026-07-30T17:00:00+00:00"
