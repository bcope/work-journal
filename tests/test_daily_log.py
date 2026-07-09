"""Tests for src/work_journal/daily_log.py."""

from datetime import date

from work_journal.daily_log import (
    compute_window,
    extract_completed_sections,
    parse_coverage,
)

STANDUP_HEADER = (
    "# Stand-up — Thursday, 2026-07-09\n\n"
    "## What I did since the last working day (Wednesday, 2026-07-08)\n"
)

FULL_STANDUP = """\
# Stand-up — Thursday, 2026-07-09

## What I did since the last working day (Wednesday, 2026-07-08)

### Jira

- [BSR-2435] (BSR) Expedited - Generate HSBC Remittance File — Closed

### Recently closed (recent activity)

- [BSR-2000] (BSR) Old thing — Closed 2026-06-01

### Jira (work logged, not closed)

- [BSR-2474] (BSR) Time Tracking — In Progress

### Commits

# Git Commits (2026-07-08 to 2026-07-09)

Author: `bcope`

## docker-time-tracking (4 commits)

- 6917cbc BSR-2474: align build script image name

### Claude Code

- **Totals:** 5 sessions, 6h 28m thinking

| Repo | Sessions |
| --- | --- |
| docker-time-tracking | 2 |

## What I'm doing today

### Completed today

- [GGL-48333] (GGL) IT Security Training — Closed

### Jira

- [COMPLY-690] (Compliance) Fix bug — In Progress

## Injected into sprint

- [AGILE-469] (Agile) Widget — Closed

## Blockers

- [VAST-5572] (VAST) Sync — In Progress
"""


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


def test_extract_keeps_what_i_did_and_completed_today() -> None:
    result = extract_completed_sections(FULL_STANDUP)
    assert "BSR-2435" in result
    assert "BSR-2474" in result  # work logged counts as work done
    assert "6917cbc" in result  # embedded commit log survives
    assert "GGL-48333" in result  # Completed today


def test_extract_drops_noise_sections() -> None:
    result = extract_completed_sections(FULL_STANDUP)
    assert "BSR-2000" not in result  # Recently closed
    assert "Totals:" not in result  # Claude Code stats
    assert "COMPLY-690" not in result  # doing-today false positives
    assert "AGILE-469" not in result  # Injected into sprint
    assert "VAST-5572" not in result  # Blockers


def test_extract_keeps_title_and_section_headers() -> None:
    result = extract_completed_sections(FULL_STANDUP)
    assert result.startswith("# Stand-up — Thursday, 2026-07-09")
    assert "## What I did since the last working day (Wednesday, 2026-07-08)" in result
    assert "### Completed today" in result


def test_extract_without_completed_today_section() -> None:
    text = FULL_STANDUP.split("### Completed today")[0]
    result = extract_completed_sections(text)
    assert "Completed today" not in result
    assert "BSR-2435" in result
