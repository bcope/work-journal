"""Tests for src/work_journal/daily_log.py."""

from datetime import date

from work_journal.daily_log import compute_window


def _sprint_info(start: str, end: str, complete: str | None = None) -> dict:
    info = {
        "startDate": f"{start}T13:49:25.185Z",
        "endDate": f"{end}T17:00:00.000Z",
    }
    if complete is not None:
        info["completeDate"] = f"{complete}T17:29:47.656Z"
    return info


def test_window_starts_on_prior_sprint_close_day() -> None:
    sprint = _sprint_info("2026-07-01", "2026-07-14")
    prior = _sprint_info("2026-06-12", "2026-06-30", complete="2026-06-30")
    assert compute_window(sprint, prior) == (date(2026, 6, 30), date(2026, 7, 14))


def test_window_falls_back_to_sprint_start_without_prior() -> None:
    sprint = _sprint_info("2026-07-01", "2026-07-14")
    assert compute_window(sprint, None) == (date(2026, 7, 1), date(2026, 7, 14))
