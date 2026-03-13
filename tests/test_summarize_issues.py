"""Tests for src/work_journal/jira/summarize_issues.py."""

import json
from pathlib import Path

from work_journal.jira.summarize_issues import summarize


def _write_issues(path: Path, issues: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(issues))


def _make_issue(
    key: str = "TEST-1",
    summary: str = "Do the thing",
    priority: str = "Medium",
    issuetype: str = "Story",
    status: str = "Done",
    reporter: str = "Alice",
    description: str | None = None,
) -> dict:
    fields: dict = {
        "summary": summary,
        "priority": {"name": priority},
        "issuetype": {"name": issuetype},
        "status": {"name": status},
        "reporter": {"displayName": reporter},
    }
    if description is not None:
        fields["description"] = description
    return {"key": key, "fields": fields}


def test_basic_output(tmp_path: Path, capsys) -> None:
    _write_issues(
        tmp_path / "jira/sprint-planned-completed.json",
        [_make_issue(key="PROJ-1", summary="Ship feature")],
    )
    summarize(tmp_path)
    out = capsys.readouterr().out

    assert "=== planned-completed (1 issues) ===" in out
    assert "PROJ-1: [Story/Medium] Ship feature (status: Done, reporter: Alice)" in out
    # Missing files should say "file not found"
    assert "=== planned-incomplete (file not found) ===" in out


def test_doc_urls_flag(tmp_path: Path, capsys) -> None:
    desc = "See https://docs.google.com/document/d/abc123/edit for details"
    _write_issues(
        tmp_path / "jira/sprint-planned-completed.json",
        [_make_issue(description=desc)],
    )

    # Without --doc-urls, no URL line
    summarize(tmp_path, doc_urls=False)
    out_no_urls = capsys.readouterr().out
    assert "Doc URLs:" not in out_no_urls

    # With --doc-urls, URL line present
    summarize(tmp_path, doc_urls=True)
    out_urls = capsys.readouterr().out
    assert "Doc URLs:" in out_urls
    assert "https://docs.google.com/document/d/abc123/edit" in out_urls


def test_missing_files_handled(tmp_path: Path, capsys) -> None:
    """All files missing should produce 7 'file not found' headers."""
    summarize(tmp_path)
    out = capsys.readouterr().out
    assert out.count("file not found") == 7


def test_empty_issue_list(tmp_path: Path, capsys) -> None:
    _write_issues(tmp_path / "jira/sprint-planned-completed.json", [])
    summarize(tmp_path)
    out = capsys.readouterr().out
    assert "=== planned-completed (0 issues) ===" in out
