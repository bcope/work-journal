"""Tests for src/work_journal/standup.py."""

from work_journal.standup import completion_date, format_jira_issue, with_weekday


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
