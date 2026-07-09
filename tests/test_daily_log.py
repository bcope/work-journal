"""Tests for src/work_journal/daily_log.py."""

from datetime import date

from work_journal.daily_log import compute_window, parse_coverage

STANDUP_HEADER = (
    "# Stand-up — Thursday, 2026-07-09\n\n"
    "## What I did since the last working day (Wednesday, 2026-07-08)\n"
)


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


def test_parse_coverage_reads_since_date_from_header() -> None:
    assert parse_coverage(STANDUP_HEADER, date(2026, 7, 9)) == (
        date(2026, 7, 8),
        date(2026, 7, 9),
    )


def test_parse_coverage_spans_weekend() -> None:
    text = "## What I did since the last working day (Friday, 2026-07-03)\n"
    assert parse_coverage(text, date(2026, 7, 6)) == (date(2026, 7, 3), date(2026, 7, 6))


def test_parse_coverage_falls_back_when_header_missing() -> None:
    assert parse_coverage("# Stand-up — malformed\n", date(2026, 7, 9)) == (
        date(2026, 7, 6),
        date(2026, 7, 9),
    )
