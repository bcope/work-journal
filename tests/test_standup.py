"""Tests for src/work_journal/standup.py."""

from datetime import date

import work_journal.standup as standup
from work_journal.standup import (
    completion_date,
    format_jira_issue,
    resolve_dates,
    with_weekday,
)


def _patch_today(monkeypatch, today: date) -> None:
    """Pin date.today() inside the standup module to a fixed date."""

    class _FixedDate(date):
        @classmethod
        def today(cls):
            return today

    monkeypatch.setattr(standup, "date", _FixedDate)


def _make_completed_issue(
    key: str = "TEST-1",
    summary: str = "Do the thing",
    status: str = "Closed",
    status_category_changed: str | None = None,
    resolution_date: str | None = None,
) -> dict:
    fields: dict = {"summary": summary, "status": {"name": status}}
    if status_category_changed is not None:
        fields["statuscategorychangedate"] = status_category_changed
    if resolution_date is not None:
        fields["resolutiondate"] = resolution_date
    return {"key": key, "fields": fields}


def test_completion_date_prefers_status_category_change() -> None:
    issue = _make_completed_issue(
        status_category_changed="2026-05-29T11:59:48.376-0400",
        resolution_date="2026-05-28T09:00:00.000-0400",
    )
    assert completion_date(issue) == "2026-05-29"


def test_completion_date_falls_back_to_resolution_date() -> None:
    issue = _make_completed_issue(resolution_date="2026-05-28T09:00:00.000-0400")
    assert completion_date(issue) == "2026-05-28"


def test_completion_date_missing_returns_none() -> None:
    assert completion_date(_make_completed_issue()) is None


def _partition(issues: list[dict], yesterday: str, today: str) -> tuple[list, list]:
    """Mirror the split logic in collect_data."""
    completed, recently_closed = [], []
    for issue in issues:
        changed = completion_date(issue)
        if changed is not None and not (yesterday <= changed < today):
            recently_closed.append(issue)
        else:
            completed.append(issue)
    return completed, recently_closed


def test_partition_separates_stale_done_from_true_completion() -> None:
    true_completion = _make_completed_issue(
        key="TRUE-1", status_category_changed="2026-06-02T10:00:00.000-0400"
    )
    stale = _make_completed_issue(
        key="STALE-1", status_category_changed="2026-05-29T11:59:48.376-0400"
    )
    unknown = _make_completed_issue(key="UNK-1")  # no date — keep in completed

    completed, recently_closed = _partition(
        [true_completion, stale, unknown], "2026-06-02", "2026-06-03"
    )

    assert [i["key"] for i in completed] == ["TRUE-1", "UNK-1"]
    assert [i["key"] for i in recently_closed] == ["STALE-1"]


def test_partition_monday_window_spans_weekend() -> None:
    # On Monday, yesterday=Friday and today=Monday; a Saturday completion counts.
    saturday = _make_completed_issue(
        key="SAT-1", status_category_changed="2026-05-30T10:00:00.000-0400"
    )
    completed, recently_closed = _partition([saturday], "2026-05-29", "2026-06-01")
    assert [i["key"] for i in completed] == ["SAT-1"]
    assert recently_closed == []


def _completed_today(issues: list[dict], today: str) -> list[dict]:
    """Mirror the completed-today filter in collect_data."""
    return [i for i in issues if completion_date(i) == today]


def test_completed_today_keeps_only_todays_done_transitions() -> None:
    closed_today = _make_completed_issue(
        key="TODAY-1", status_category_changed="2026-06-24T10:05:23.783-0400"
    )
    touched_today_done_earlier = _make_completed_issue(
        key="STALE-1", status_category_changed="2026-06-20T11:00:00.000-0400"
    )
    no_date = _make_completed_issue(key="UNK-1")  # excluded — can't confirm today

    result = _completed_today([closed_today, touched_today_done_earlier, no_date], "2026-06-24")
    assert [i["key"] for i in result] == ["TODAY-1"]


def test_format_jira_issue_appends_completion_date_when_requested() -> None:
    issue = _make_completed_issue(
        key="COMPLY-723",
        summary="Send redesignation emails",
        status="Closed",
        status_category_changed="2026-05-29T11:59:48.376-0400",
    )
    line = format_jira_issue(issue, {"COMPLY": "Compliance"}, show_completion_date=True)
    assert line == "- [COMPLY-723] (Compliance) Send redesignation emails — Closed 2026-05-29"


def test_format_jira_issue_omits_date_by_default() -> None:
    issue = _make_completed_issue(
        key="COMPLY-723",
        summary="Send redesignation emails",
        status="Closed",
        status_category_changed="2026-05-29T11:59:48.376-0400",
    )
    line = format_jira_issue(issue, {"COMPLY": "Compliance"})
    assert line == "- [COMPLY-723] (Compliance) Send redesignation emails — Closed"


def test_with_weekday_computes_correct_day() -> None:
    assert with_weekday("2026-06-10") == "Wednesday, 2026-06-10"
    assert with_weekday("2026-06-09") == "Tuesday, 2026-06-09"


def test_resolve_dates_weekday_uses_prior_day(monkeypatch) -> None:
    # Tuesday -> last working day is Monday.
    _patch_today(monkeypatch, date(2026, 6, 9))
    since, today = resolve_dates(None)
    assert (since, today) == (date(2026, 6, 8), date(2026, 6, 9))


def test_resolve_dates_monday_skips_back_to_friday(monkeypatch) -> None:
    # Monday -> last working day is the previous Friday; window spans the weekend.
    _patch_today(monkeypatch, date(2026, 6, 8))
    since, today = resolve_dates(None)
    assert (since, today) == (date(2026, 6, 5), date(2026, 6, 8))


def test_resolve_dates_weekend_run_skips_to_friday(monkeypatch) -> None:
    # Run on Sunday -> Saturday is skipped, last working day is Friday.
    _patch_today(monkeypatch, date(2026, 6, 7))
    since, today = resolve_dates(None)
    assert (since, today) == (date(2026, 6, 5), date(2026, 6, 7))


def test_resolve_dates_override_is_verbatim(monkeypatch) -> None:
    # An explicit --since wins regardless of weekday (e.g. returning from PTO).
    _patch_today(monkeypatch, date(2026, 6, 10))
    since, today = resolve_dates("2026-06-01")
    assert (since, today) == (date(2026, 6, 1), date(2026, 6, 10))
