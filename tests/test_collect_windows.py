"""Tests for collect.compute_windows."""

from datetime import UTC, datetime

from work_journal.collect import compute_windows

SPRINT = {
    "startDate": "2026-07-15T14:11:10.534Z",
    "endDate": "2026-07-30T17:00:00.000Z",
}
PRIOR = {
    "completeDate": "2026-07-14T17:30:48.893Z",
    "endDate": "2026-07-14T17:00:00.000Z",
}


def test_sprint_window_spans_start_day_midnight_to_close():
    since, until, _, _ = compute_windows(SPRINT, PRIOR)
    local = since.astimezone()
    assert (local.hour, local.minute) == (0, 0)
    assert local.date().isoformat() == "2026-07-15"
    assert until == datetime(2026, 7, 30, 17, 0, tzinfo=UTC)


def test_sprint_window_prefers_complete_date():
    closed = {**SPRINT, "completeDate": "2026-07-30T17:42:00.000Z"}
    _, until, _, _ = compute_windows(closed, PRIOR)
    assert until == datetime(2026, 7, 30, 17, 42, tzinfo=UTC)


def test_between_window_runs_from_prior_close_to_start_day_midnight():
    since, _, b_since, b_until = compute_windows(SPRINT, PRIOR)
    assert b_since == datetime(2026, 7, 14, 17, 30, 48, 893000, tzinfo=UTC)
    assert b_until == since


def test_between_window_empty_when_prior_closes_after_start_midnight():
    late_prior = {"completeDate": "2026-07-15T12:00:00.000Z"}
    _, _, b_since, b_until = compute_windows(SPRINT, late_prior)
    assert b_since is None and b_until is None


def test_no_prior_sprint():
    _, _, b_since, b_until = compute_windows(SPRINT, None)
    assert b_since is None and b_until is None


def test_prior_sprint_without_dates():
    _, _, b_since, b_until = compute_windows(SPRINT, {"name": "x"})
    assert b_since is None and b_until is None
