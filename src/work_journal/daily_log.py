"""Snapshot daily notes and standup completed-work sections for a sprint.

Copies work/shared/daily-note/ files and extracts completed-work sections
from work/standup/ files into work/sprint-notes/{sprint}/daily-log/raw/.
See docs/process/plans/2026-07-09-daily-notes-integration-design.md.

Usage: uv run python3 src/work_journal/daily_log.py 2026-07-A
"""

import argparse
import json
import re
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

from work_journal.paths import SHARED_DIR, SPRINT_NOTES_DIR, STANDUP_DIR

DAILY_NOTE_DIR = SHARED_DIR / "daily-note"

SINCE_RE = re.compile(
    r"^## What I did since the last working day \(\w+, (\d{4}-\d{2}-\d{2})\)",
    re.MULTILINE,
)

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


def compute_window(sprint_info: dict, prior_sprint_info: dict | None) -> tuple[date, date]:
    """Window from prior sprint's close day (inclusive — sprints close midway
    into a day, so the rest of that day is sprintless) through sprint end."""
    if prior_sprint_info is not None:
        start = date.fromisoformat(prior_sprint_info["completeDate"][:10])
    else:
        start = date.fromisoformat(sprint_info["startDate"][:10])
    end = date.fromisoformat(sprint_info["endDate"][:10])
    return start, end


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
        label = (
            " + ".join(sources)
            if sources
            else ("no record (weekend)" if day.weekday() >= 5 else "NO RECORD")
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
