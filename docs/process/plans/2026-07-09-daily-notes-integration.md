# Daily Notes Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Snapshot daily notes and standup completed-work sections into each sprint directory, merge them into a curated per-day log, and make that log a required input for enrichment and drafting.

**Architecture:** A deterministic snapshot script (`src/work_journal/daily_log.py`) copies daily notes and extracts completed-work sections from saved standups into `work/sprint-notes/{sprint}/daily-log/raw/`. A new `/merge-daily-log` skill applies precedence rules (daily note wins; standup fills gaps) and writes `merged-raw.md` + `merged-edited.md`. The enrich and draft skills gate on `merged-edited.md`.

**Tech Stack:** Python 3 (stdlib only — argparse, json, re, shutil, datetime, pathlib), pytest, Claude Code skills (markdown).

**Design doc:** `docs/process/plans/2026-07-09-daily-notes-integration-design.md` — read it first; it is the authority on precedence rules and formats.

**Conventions (read before starting):**

- Run everything with `uv run` (`uv run pytest`, `uv run mypy src/`, `uv run ruff check .`).
- Commit messages: single line, lowercase, imperative, no prefixes, no attribution (e.g. `add daily log window computation`). Never multi-line.
- All functions in `src/` need type annotations — mypy is gated in CI.
- Tests live flat in `tests/` (`tests/test_daily_log.py`), self-contained, no fixtures in conftest (it is empty). Use `tmp_path` for filesystem tests.

---

## Reference: input formats

**Sprint info** (`work/sprint-notes/{sprint}/jira/sprint-info.json`, written by collect.py):

```json
{
  "name": "2026-06-B-Product-June",
  "startDate": "2026-06-12T13:49:25.185Z",
  "endDate": "2026-06-30T17:00:00.000Z",
  "completeDate": "2026-06-30T17:29:47.656Z"
}
```

`prior-sprint-info.json` sits next to it, same shape. Date part is always the first 10 chars (see `extract_dates` in `src/work_journal/collect.py:85`).

**Standup file** (`work/standup/{YYYY-MM-DD}.md`, written by `src/work_journal/standup.py`). Top-level section headers are exact literals:

```markdown
# Stand-up — Thursday, 2026-07-09

## What I did since the last working day (Wednesday, 2026-07-08)

### Jira
### Recently closed (recent activity)      <- drop (reached Done before window)
### Jira (work logged, not closed)
### Pull requests (merged)
### Pull requests (closed, not merged)
### Commits
### Claude Code                            <- drop (usage stats, not work items)

## What I'm doing today

### Completed today                        <- keep
### Jira                                   <- drop (false positives)
### Open PRs                               <- drop

## Injected into sprint                    <- drop
## Status check (In Progress, not in active sprint)   <- drop
## Blockers                                <- drop
## Data collection warnings                <- drop
```

**CRITICAL GOTCHA:** the `### Commits` subsection embeds the raw git-log
report, which contains its own `# Git Commits (...)` and `## {repo} (N
commits)` headers. Never treat "any `##` line" as a section boundary — match
only the known top-level literals above. Subsection boundaries inside a kept
section are lines starting with `###`.

**Daily note** (`work/shared/daily-note/{YYYY-MM-DD}.md`): freeform markdown
bullets, may be zero bytes.

---

### Task 1: Window computation

**Files:**

- Create: `src/work_journal/daily_log.py`
- Create: `tests/test_daily_log.py`

**Step 1: Write the failing tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_daily_log.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError` (module doesn't exist yet)

**Step 3: Write minimal implementation**

```python
"""Snapshot daily notes and standup completed-work sections for a sprint.

Copies work/shared/daily-note/ files and extracts completed-work sections
from work/standup/ files into work/sprint-notes/{sprint}/daily-log/raw/.
See docs/process/plans/2026-07-09-daily-notes-integration-design.md.

Usage: uv run python3 src/work_journal/daily_log.py 2026-07-A
"""

from datetime import date


def compute_window(sprint_info: dict, prior_sprint_info: dict | None) -> tuple[date, date]:
    """Window from prior sprint's close day (inclusive — sprints close midway
    into a day, so the rest of that day is sprintless) through sprint end."""
    if prior_sprint_info is not None:
        start = date.fromisoformat(prior_sprint_info["completeDate"][:10])
    else:
        start = date.fromisoformat(sprint_info["startDate"][:10])
    end = date.fromisoformat(sprint_info["endDate"][:10])
    return start, end
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_daily_log.py -v`
Expected: 2 PASS

**Step 5: Commit**

```bash
git add src/work_journal/daily_log.py tests/test_daily_log.py
git commit -m "add daily log window computation"
```

---

### Task 2: Standup coverage-window parsing

**Files:**

- Modify: `src/work_journal/daily_log.py`
- Modify: `tests/test_daily_log.py`

**Step 1: Write the failing tests**

```python
from work_journal.daily_log import parse_coverage

STANDUP_HEADER = (
    "# Stand-up — Thursday, 2026-07-09\n\n"
    "## What I did since the last working day (Wednesday, 2026-07-08)\n"
)


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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_daily_log.py -v`
Expected: new tests FAIL with `ImportError: cannot import name 'parse_coverage'`

**Step 3: Write minimal implementation**

Add to `daily_log.py`:

```python
import re
from datetime import timedelta

SINCE_RE = re.compile(
    r"^## What I did since the last working day \(\w+, (\d{4}-\d{2}-\d{2})\)",
    re.MULTILINE,
)


def parse_coverage(text: str, file_date: date) -> tuple[date, date]:
    """Coverage window of a standup file: [since-date, file-date].

    The 'since' date comes from the section header the standup script emits.
    If the header can't be parsed, fall back to a 3-day lookback rather than
    dropping the file.
    """
    match = SINCE_RE.search(text)
    if match:
        return date.fromisoformat(match.group(1)), file_date
    return file_date - timedelta(days=3), file_date
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_daily_log.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add src/work_journal/daily_log.py tests/test_daily_log.py
git commit -m "parse standup coverage window from since header"
```

---

### Task 3: Completed-work section extraction

**Files:**

- Modify: `src/work_journal/daily_log.py`
- Modify: `tests/test_daily_log.py`

**Step 1: Write the failing tests**

Use a realistic fixture including the embedded-commit-log gotcha:

```python
from work_journal.daily_log import extract_completed_sections

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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_daily_log.py -v`
Expected: new tests FAIL with ImportError

**Step 3: Write the implementation**

Add to `daily_log.py`. State machine keyed on **exact literals** — do not
match generic `##` lines (the Commits body embeds `#`/`##` headers):

```python
WHAT_I_DID_PREFIX = "## What I did since the last working day"
TOP_SECTION_PREFIXES = (
    WHAT_I_DID_PREFIX,
    "## What I'm doing today",
    "## Injected into sprint",
    "## Status check",
    "## Blockers",
    "## Data collection warnings",
)
DROP_SUBSECTIONS = ("### Recently closed (recent activity)", "### Claude Code")
COMPLETED_TODAY = "### Completed today"


def extract_completed_sections(text: str) -> str:
    """Keep only completed-work evidence from a standup markdown file.

    Keeps the title, the 'What I did' section (minus the Recently-closed and
    Claude Code subsections), and the 'Completed today' subsection. Drops
    everything else. Boundaries are the exact section literals the standup
    script emits — the Commits body embeds its own #/## headers, so generic
    header matching would truncate it.
    """
    out: list[str] = []
    current_top: str | None = None
    keeping = False
    for line in text.splitlines():
        if line.startswith("# Stand-up"):
            out.append(line)
            continue
        top = next((p for p in TOP_SECTION_PREFIXES if line.startswith(p)), None)
        if top is not None:
            current_top = top
            keeping = top == WHAT_I_DID_PREFIX
            if keeping:
                out.append(line)
            continue
        if current_top == WHAT_I_DID_PREFIX:
            if line.startswith("### "):
                keeping = not line.startswith(DROP_SUBSECTIONS)
            if keeping:
                out.append(line)
        elif current_top == "## What I'm doing today":
            if line.startswith("### "):
                keeping = line.startswith(COMPLETED_TODAY)
            if keeping:
                out.append(line)
    return "\n".join(out).strip() + "\n"
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_daily_log.py -v`
Expected: all PASS

**Step 5: Sanity-check against a real file**

```bash
uv run python3 -c "
from pathlib import Path
from work_journal.daily_log import extract_completed_sections
print(extract_completed_sections(Path('work/standup/2026-07-09.md').read_text()))"
```

Expected: Jira closures, worklog line, and commits present; no Claude Code
table, no Blockers, no doing-today Jira list.

**Step 6: Commit**

```bash
git add src/work_journal/daily_log.py tests/test_daily_log.py
git commit -m "extract completed-work sections from standup files"
```

---

### Task 4: Snapshot orchestration + CLI + coverage summary

**Files:**

- Modify: `src/work_journal/daily_log.py`
- Modify: `tests/test_daily_log.py`

**Step 1: Write the failing tests**

Filesystem test with `tmp_path`; `snapshot()` takes explicit dirs so tests
don't touch real paths:

```python
import json
from pathlib import Path

from work_journal.daily_log import snapshot


def _write_sprint_info(sprint_dir: Path) -> None:
    jira = sprint_dir / "jira"
    jira.mkdir(parents=True)
    (jira / "sprint-info.json").write_text(
        json.dumps(_sprint_info("2026-07-01", "2026-07-14"))
    )
    (jira / "prior-sprint-info.json").write_text(
        json.dumps(_sprint_info("2026-06-12", "2026-06-30", complete="2026-06-30"))
    )


def test_snapshot_copies_window_files(tmp_path: Path) -> None:
    sprint_dir = tmp_path / "2026-07-A"
    _write_sprint_info(sprint_dir)
    notes = tmp_path / "daily-note"
    notes.mkdir()
    (notes / "2026-06-30.md").write_text("# 2026-06-30\n\n- close sprint\n")
    (notes / "2026-07-01.md").write_text("# 2026-07-01\n\n- new sprint\n")
    (notes / "2026-06-26.md").write_text("# 2026-06-26\n\n- before window\n")
    standups = tmp_path / "standup"
    standups.mkdir()
    (standups / "2026-07-02.md").write_text(
        "# Stand-up — Thursday, 2026-07-02\n\n"
        "## What I did since the last working day (Wednesday, 2026-07-01)\n\n"
        "### Jira\n\n- [X-1] (X) Thing — Closed\n"
    )
    (standups / "2026-06-15.md").write_text(
        "# Stand-up — Monday, 2026-06-15\n\n"
        "## What I did since the last working day (Friday, 2026-06-12)\n\n"
        "### Jira\n\n- [X-0] (X) Out of window — Closed\n"
    )

    summary = snapshot(sprint_dir, notes, standups)

    raw = sprint_dir / "daily-log" / "raw"
    assert (raw / "daily-notes" / "2026-06-30.md").exists()
    assert (raw / "daily-notes" / "2026-07-01.md").exists()
    assert not (raw / "daily-notes" / "2026-06-26.md").exists()
    assert (raw / "standups" / "2026-07-02.md").exists()
    assert not (raw / "standups" / "2026-06-15.md").exists()
    assert "X-1" in (raw / "standups" / "2026-07-02.md").read_text()
    assert "2026-07-04" in summary  # a no-record weekend day appears


def test_snapshot_is_idempotent(tmp_path: Path) -> None:
    sprint_dir = tmp_path / "2026-07-A"
    _write_sprint_info(sprint_dir)
    (tmp_path / "daily-note").mkdir()
    (tmp_path / "standup").mkdir()
    stale = sprint_dir / "daily-log" / "raw" / "daily-notes"
    stale.mkdir(parents=True)
    (stale / "1999-01-01.md").write_text("stale")

    snapshot(sprint_dir, tmp_path / "daily-note", tmp_path / "standup")

    assert not (stale / "1999-01-01.md").exists()


def test_snapshot_requires_sprint_info(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(SystemExit):
        snapshot(tmp_path / "nope", tmp_path, tmp_path)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_daily_log.py -v`
Expected: new tests FAIL with ImportError

**Step 3: Write the implementation**

Add to `daily_log.py`:

```python
import argparse
import json
import shutil
import sys

from work_journal.paths import SHARED_DIR, SPRINT_NOTES_DIR, STANDUP_DIR

DAILY_NOTE_DIR = SHARED_DIR / "daily-note"


def _iter_days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def snapshot(sprint_dir: Path, daily_note_dir: Path, standup_dir: Path) -> str:
    """Snapshot window-relevant daily notes and standup extracts into
    {sprint_dir}/daily-log/raw/. Returns the per-day coverage summary."""
    info_path = sprint_dir / "jira" / "sprint-info.json"
    if not info_path.exists():
        sys.exit(
            f"Error: {info_path} not found.\n"
            f"Run collect.py for this sprint first: "
            f"uv run python3 src/work_journal/collect.py {sprint_dir.name}"
        )
    sprint_info = json.loads(info_path.read_text())
    prior_path = sprint_dir / "jira" / "prior-sprint-info.json"
    prior_info = json.loads(prior_path.read_text()) if prior_path.exists() else None
    start, end = compute_window(sprint_info, prior_info)

    raw_dir = sprint_dir / "daily-log" / "raw"
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    notes_out = raw_dir / "daily-notes"
    standups_out = raw_dir / "standups"
    notes_out.mkdir(parents=True)
    standups_out.mkdir(parents=True)

    days = _iter_days(start, end)
    note_days: dict[date, str] = {}  # day -> "note" | "empty"
    for day in days:
        src = daily_note_dir / f"{day.isoformat()}.md"
        if src.exists():
            shutil.copy2(src, notes_out / src.name)
            note_days[day] = "note" if src.stat().st_size > 0 else "empty"

    standup_days: set[date] = set()
    for path in sorted(standup_dir.glob("*.md")):
        try:
            file_date = date.fromisoformat(path.stem)
        except ValueError:
            continue
        text = path.read_text()
        cov_start, cov_end = parse_coverage(text, file_date)
        if cov_start <= end and cov_end >= start:
            (standups_out / path.name).write_text(extract_completed_sections(text))
            standup_days.update(d for d in _iter_days(cov_start, cov_end) if d in days)

    lines = [f"Coverage for {sprint_dir.name} ({start} to {end}):"]
    for day in days:
        weekday = day.strftime("%A")
        sources = []
        if note_days.get(day) == "note":
            sources.append("daily note")
        elif note_days.get(day) == "empty":
            sources.append("empty note")
        if day in standup_days:
            sources.append("standup")
        label = " + ".join(sources) if sources else (
            "no record (weekend)" if day.weekday() >= 5 else "NO RECORD"
        )
        lines.append(f"  {day.isoformat()} {weekday:<9} {label}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sprint", help="Sprint directory name, e.g. 2026-07-A")
    args = parser.parse_args()
    summary = snapshot(SPRINT_NOTES_DIR / args.sprint, DAILY_NOTE_DIR, STANDUP_DIR)
    print(summary)


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_daily_log.py -v`
Expected: all PASS

**Step 5: Run lint and type checks**

Run: `uv run ruff check . && uv run ruff format . && uv run mypy src/`
Expected: clean (fix anything flagged before committing)

**Step 6: Sanity-check the CLI error path**

Run: `uv run python3 src/work_journal/daily_log.py 1999-01-A`
Expected: exits with the "Run collect.py for this sprint first" error.

**Step 7: Commit**

```bash
git add src/work_journal/daily_log.py tests/test_daily_log.py
git commit -m "add daily log snapshot script with coverage summary"
```

---

### Task 5: /merge-daily-log skill

**Files:**

- Create: `.claude/skills/merge-daily-log/SKILL.md`

No tests — skills are prose. Model the frontmatter on
`.claude/skills/draft-sprint-notes/SKILL.md`.

**Step 1: Write the skill**

Content requirements (see the design doc for the full rules; the skill must
encode all of them):

- **Frontmatter:** `name: merge-daily-log`; description triggers on "merge
  daily log", "/merge-daily-log"; notes it requires the snapshot script to
  have been run first.
- **Phase 1 — load:** read `daily-log/raw/daily-notes/` and
  `daily-log/raw/standups/` plus `jira/sprint-info.json` /
  `prior-sprint-info.json` for the window. If `raw/` is missing, stop and
  tell the user to run `uv run python3 src/work_journal/daily_log.py {sprint}`.
- **Phase 2 — merge, one `##` section per day** across the window, headers
  in standup style (`## Wednesday, 2026-07-08`), weekday taken from
  filenames/headers, never inferred (run `date` if ever needed):
  - Day with daily note: note bullets verbatim as the day's record. Standup
    completed-items attributed to that day that are **not already covered by
    the note even in different words** go under
    `**Also completed (from standup YYYY-MM-DD):**`. Judging "already
    covered" is semantic (e.g. "closed BSR-2461" is covered by "Produce
    Blackbaud bulk import files" when they describe the same work).
  - Day without note: standup items become the record; heading suffixed
    `(from standup — no daily note)`.
  - Multi-day standup coverage (Monday covering Fri–Sun): one combined
    section spanning those days.
  - No source at all: `— no record` (note weekends as such).
  - Zero-byte note: flag "note exists but empty", then standup fallback.
  - A standup's "Completed today" items belong to the standup's own date;
    its "What I did" items belong to the coverage window before it.
- **Phase 3 — write two files:** always overwrite
  `daily-log/merged-raw.md`; write `daily-log/merged-edited.md` only if it
  does not exist, and if it does exist, leave it untouched and tell the user
  to reconcile via `diff merged-raw.md merged-edited.md`. Both start with a
  provenance line (sprint, window, generated date) and a note that
  `merged-edited.md` is the copy to edit.

**Step 2: Lint**

Run: `markdownlint --fix --disable MD013 MD036 .claude/skills/merge-daily-log/SKILL.md`

**Step 3: Commit**

```bash
git add .claude/skills/merge-daily-log/SKILL.md
git commit -m "add merge-daily-log skill"
```

---

### Task 6: Gates in enrich and draft skills

**Files:**

- Modify: `.claude/skills/enrich-sprint-data/SKILL.md`
- Modify: `.claude/skills/draft-sprint-notes/SKILL.md`

**Step 1: Edit enrich-sprint-data**

- Add a gate at the top of the process: require
  `work/sprint-notes/{sprint}/daily-log/merged-edited.md`; if missing, stop
  with instructions (snapshot script, then `/merge-daily-log {sprint}`).
  Exemption: sprints before 2026-07-A predate daily notes — proceed without.
- Add `merged-edited.md` to the inputs read for names/topics/links to target
  in Gmail/Docs/Calendar searches (alongside the existing `manual-notes.md`
  item, which is unchanged).

**Step 2: Edit draft-sprint-notes**

- Phase 1 file list: add `daily-log/merged-edited.md` as a **required**
  input with the same gate + pre-2026-07-A exemption. Describe it as the
  primary record of what actually happened per day: other sources
  corroborate and add links/metrics; on conflict the daily log wins and the
  disagreement gets a `TODO:` marker. Never read `merged-raw.md` (it exists
  only for diffing against the edited copy).
- Phase 2: replace "If enrichment files don't exist, proceed with available
  data" with: pause and ask the user whether to proceed without enrichment
  (recommend running `/enrich-sprint-data {sprint}` first).
- Directory-structure diagram: add the `daily-log/` subtree (raw/,
  merged-raw.md, merged-edited.md).

**Step 3: Verify no stale references**

Run: `grep -rn "merged.md\|daily-log" .claude/skills/ CLAUDE.md README.md`
Expected: only `merged-raw.md` / `merged-edited.md` references; nothing
pointing at a bare `merged.md`.

**Step 4: Commit**

```bash
git add .claude/skills/enrich-sprint-data/SKILL.md .claude/skills/draft-sprint-notes/SKILL.md
git commit -m "gate enrich and draft skills on merged daily log"
```

---

### Task 7: Workflow docs (CLAUDE.md, README.md)

**Files:**

- Modify: `CLAUDE.md` (project) — "Sprint notes workflow" section and
  "Project structure" section
- Modify: `README.md` — only if it describes the sprint workflow steps
  (check first)

**Step 1: Update CLAUDE.md**

- Sprint notes workflow: insert after the collect step (current step 3):

  ```markdown
  4. Snapshot daily log: `uv run python3 src/work_journal/daily_log.py {sprint}` (review the printed coverage summary)
  5. Merge: `/merge-daily-log {sprint}`, then optionally edit `work/sprint-notes/{sprint}/daily-log/merged-edited.md`
  ```

  Renumber the following steps. Change the "Steps 4 and 5 are optional"
  sentence: enrichment (`/enrich-sprint-data`) is now a required step;
  `manual-notes.md` editing remains optional.
- Project structure: add `work/shared/daily-note/` (manual daily notes, one
  file per day) and `src/work_journal/daily_log.py` entries.

**Step 2: Check and update README.md**

Read README.md; if it lists sprint workflow steps or the project structure,
mirror the CLAUDE.md changes. If it doesn't mention them, leave it alone.

**Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "document daily log steps in sprint workflow"
```

---

### Task 8: Full verification and live dry run

**Step 1: Run the full check suite**

Run: `uv run pre-commit run --all-files && uv run mypy src/ && uv run pytest`
Expected: all pass. Fix and amend/commit as needed.

**Step 2: Live dry run against a real sprint**

The current sprint dir with collected data is the newest under
`work/sprint-notes/` that has `jira/sprint-info.json`. If one exists for the
current sprint (2026-07-A or later):

```bash
uv run python3 src/work_journal/daily_log.py {sprint}
ls work/sprint-notes/{sprint}/daily-log/raw/daily-notes/ work/sprint-notes/{sprint}/daily-log/raw/standups/
```

Expected: coverage summary prints; copied notes match
`work/shared/daily-note/`; standup extracts contain no "Blockers" or
"Claude Code" sections. Do **not** commit `work/` outputs unless the repo
already tracks that sprint's data (check `git status` — `work/` sprint data
is committed in this repo, so include it if the user confirms).

**Step 3: Report** — summarize what was built, test counts, and any
deviations from this plan.
