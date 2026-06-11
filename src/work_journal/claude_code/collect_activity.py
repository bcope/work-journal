"""Collect Claude Code activity data for a sprint date range.

Reads the Claude history file (path configured via CLAUDE_HISTORY_PATH env var),
filters to work projects
in the date range, reads conversation JSONL files for metrics, and outputs
a markdown session inventory and documents-generated report.

Metrics extracted per session:
- Thinking time: sum of turn_duration system entries (actual Claude compute)
- Tool usage: tool calls by category
- Documents: files created/modified via Write/Edit tool calls

Usage:
    uv run python3 src/work_journal/claude_code/collect_activity.py \
        --since 2026-02-13 --until 2026-02-26
    uv run python3 src/work_journal/claude_code/collect_activity.py \
        --since 2026-02-13 --until 2026-02-26 --copy-raw DIR
"""

import argparse
import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

DEFAULT_HISTORY_PATH = os.path.expanduser(
    os.environ.get("CLAUDE_HISTORY_PATH", "~/.claude/history.jsonl")
)
DEFAULT_STATS_CACHE_PATH = os.path.expanduser(
    os.environ.get("CLAUDE_STATS_CACHE_PATH", "~/.claude/stats-cache.json")
)
DEFAULT_PROJECTS_PATH = os.path.expanduser(
    os.environ.get("CLAUDE_PROJECTS_PATH", "~/.claude/projects")
)
DEFAULT_WORK_DIRS = [os.path.expanduser(os.environ.get("CLAUDE_WORK_DIRS", "~/git"))]

# Tool call categories for Tier 2 breakdown
TOOL_CATEGORIES = {
    "File operations": {"Read", "Write", "Edit", "Glob", "Grep"},
    "Shell": {"Bash"},
    "MCP - Jira": "mcp__jira__",
    "MCP - Google": "mcp__gdocs__",
    "MCP - Miro": "mcp__miro__",
    "Agent": {"Task", "TaskCreate", "TaskUpdate", "TaskGet", "TaskList"},
    "Web": {"WebSearch", "WebFetch"},
}


def is_work_project(project_path: str, work_dirs: list[str]) -> bool:
    """Check if a project path is under one of the configured work directories."""
    return any(project_path.startswith(work_dir) for work_dir in work_dirs)


def project_slug(project_path: str) -> str:
    """Convert a project path to the Claude projects directory slug."""
    return project_path.replace("/", "-")


def repo_name(project_path: str) -> str:
    """Extract the repo directory name from a project path."""
    return os.path.basename(project_path)


def load_history(
    history_path: str,
    start_date: str,
    end_date: str,
    work_dirs: list[str],
) -> dict[str, dict]:
    """Load history.jsonl and return work sessions grouped by session ID.

    Each session ID maps to a list of history entries (there can be multiple
    entries per session in history.jsonl). Returns only the first entry per
    session (used for display text and timestamp).
    """
    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() * 1000)
    end_ts = int(
        datetime.strptime(end_date, "%Y-%m-%d")
        .replace(hour=23, minute=59, second=59, tzinfo=UTC)
        .timestamp()
        * 1000
    )

    sessions: dict[str, dict] = {}

    with open(history_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            ts = entry.get("timestamp", 0)
            project = entry.get("project", "")
            session_id = entry.get("sessionId", "")

            if not (start_ts <= ts <= end_ts):
                continue
            if not is_work_project(project, work_dirs):
                continue
            if not session_id:
                continue

            # Keep the first entry per session (earliest timestamp)
            if session_id not in sessions or ts < sessions[session_id]["timestamp"]:
                sessions[session_id] = entry

    return sessions


def categorize_tool(tool_name: str) -> str:
    """Categorize a tool call by name."""
    for category, matcher in TOOL_CATEGORIES.items():
        if isinstance(matcher, set):
            if tool_name in matcher:
                return category
        elif isinstance(matcher, str) and tool_name.startswith(matcher):
            return category
    return "Other"


def _parse_timestamp_ms(timestamp_str) -> int | None:
    """Parse a timestamp (ISO string or epoch ms) to milliseconds."""
    if isinstance(timestamp_str, str):
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            return int(ts.timestamp() * 1000)
        except ValueError:
            return None
    elif isinstance(timestamp_str, int | float):
        return int(timestamp_str)
    return None


class ConversationMetrics(TypedDict):
    """Metrics extracted from a single conversation JSONL file."""

    duration_ms: int
    user_messages: int
    assistant_messages: int
    tool_calls: defaultdict[str, int]
    tool_categories: defaultdict[str, int]
    first_timestamp: str | None
    last_timestamp: str | None
    thinking_time_ms: int
    turn_count: int
    documents: dict[str, dict[str, Any]]


def analyze_conversation(
    projects_path: str, project_path: str, session_id: str
) -> ConversationMetrics:
    """Read a conversation JSONL file and extract all metrics in a single pass.

    Returns dict with:
        duration_ms: gap between first and last timestamp (wall clock)
        user_messages: count of user-type entries (includes tool results)
        assistant_messages: count of assistant entries
        tool_calls: dict of tool_name -> count
        tool_categories: dict of category -> count
        first_timestamp: ISO string
        last_timestamp: ISO string
        thinking_time_ms: sum of turn_duration system entries
        turn_count: number of turns (turn_duration entries)
        documents: dict of file_path -> {operations, write_chars,
            edit_net_chars, first_op, first_op_ts}
    """
    slug = project_slug(project_path)
    conversation_file = os.path.join(projects_path, slug, f"{session_id}.jsonl")

    result: ConversationMetrics = {
        "duration_ms": 0,
        "user_messages": 0,
        "assistant_messages": 0,
        "tool_calls": defaultdict(int),
        "tool_categories": defaultdict(int),
        "first_timestamp": None,
        "last_timestamp": None,
        "thinking_time_ms": 0,
        "turn_count": 0,
        "documents": {},
    }

    if not os.path.exists(conversation_file):
        return result

    first_ts = None
    last_ts = None
    seen_tool_uses = set()

    with open(conversation_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type")
            timestamp_str = entry.get("timestamp")

            # Track first/last timestamps
            if timestamp_str:
                ts_ms = _parse_timestamp_ms(timestamp_str)
                if ts_ms is not None:
                    if first_ts is None or ts_ms < first_ts:
                        first_ts = ts_ms
                        result["first_timestamp"] = timestamp_str
                    if last_ts is None or ts_ms > last_ts:
                        last_ts = ts_ms
                        result["last_timestamp"] = timestamp_str

            # Count messages and extract tool/document metrics
            if entry_type == "user":
                result["user_messages"] += 1

            elif entry_type == "assistant":
                result["assistant_messages"] += 1
                message = entry.get("message", {})
                content = message.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") != "tool_use":
                            continue

                        tool_id = block.get("id", "")
                        if tool_id and tool_id in seen_tool_uses:
                            continue
                        if tool_id:
                            seen_tool_uses.add(tool_id)

                        tool_name = block.get("name", "unknown")
                        result["tool_calls"][tool_name] += 1
                        result["tool_categories"][categorize_tool(tool_name)] += 1

                        # Extract document metrics from Write/Edit
                        inp = block.get("input", {})
                        file_path = inp.get("file_path", "")
                        if not file_path:
                            continue

                        if tool_name == "Write":
                            content_str = inp.get("content", "")
                            doc = result["documents"].setdefault(
                                file_path,
                                {
                                    "operations": [],
                                    "write_chars": 0,
                                    "edit_net_chars": 0,
                                    "first_op": None,
                                    "first_op_ts": None,
                                },
                            )
                            doc["operations"].append("write")
                            doc["write_chars"] += len(content_str)
                            if doc["first_op"] is None:
                                doc["first_op"] = "write"
                                doc["first_op_ts"] = timestamp_str

                        elif tool_name == "Edit":
                            old = inp.get("old_string", "")
                            new = inp.get("new_string", "")
                            doc = result["documents"].setdefault(
                                file_path,
                                {
                                    "operations": [],
                                    "write_chars": 0,
                                    "edit_net_chars": 0,
                                    "first_op": None,
                                    "first_op_ts": None,
                                },
                            )
                            doc["operations"].append("edit")
                            doc["edit_net_chars"] += len(new) - len(old)
                            if doc["first_op"] is None:
                                doc["first_op"] = "edit"
                                doc["first_op_ts"] = timestamp_str

            elif entry_type == "system" and entry.get("subtype") == "turn_duration":
                duration = entry.get("durationMs", 0)
                result["thinking_time_ms"] += duration
                result["turn_count"] += 1

    if first_ts is not None and last_ts is not None:
        result["duration_ms"] = last_ts - first_ts

    return result


def format_duration(ms: int) -> str:
    """Format milliseconds as a human-readable duration."""
    if ms <= 0:
        return "< 1m"
    total_minutes = ms // 60000
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _count_documents(metrics: dict) -> tuple[int, int, int]:
    """Count created files, modified files, and total write chars from doc metrics."""
    created = 0
    modified = 0
    total_write_chars = 0
    for file_path, doc in metrics.get("documents", {}).items():
        if _is_noise_path(file_path):
            continue
        total_write_chars += doc["write_chars"]
        if doc["first_op"] == "write":
            created += 1
        else:
            modified += 1
    return created, modified, total_write_chars


def _format_chars(chars: int) -> str:
    """Format character count with K/M suffix."""
    if chars >= 1_000_000:
        return f"{chars / 1_000_000:.1f}M"
    if chars >= 1_000:
        return f"{chars / 1_000:.1f}K"
    return str(chars)


def format_markdown(
    sessions_by_project: dict[str, list[dict]],
    start_date: str,
    end_date: str,
) -> str:
    """Format session inventory and tool usage as markdown."""
    lines: list[str] = []
    lines.append(f"# Claude Code Sessions ({start_date} to {end_date})")
    lines.append("")

    # Aggregate stats
    total_sessions = sum(len(s) for s in sessions_by_project.values())
    total_thinking_ms = sum(
        s["metrics"]["thinking_time_ms"]
        for sessions in sessions_by_project.values()
        for s in sessions
    )
    total_turns = sum(
        s["metrics"]["turn_count"] for sessions in sessions_by_project.values() for s in sessions
    )
    total_tool_calls = sum(
        sum(s["metrics"]["tool_calls"].values())
        for sessions in sessions_by_project.values()
        for s in sessions
    )
    total_created = 0
    total_modified = 0
    total_write_chars = 0
    for sessions in sessions_by_project.values():
        for s in sessions:
            c, m, w = _count_documents(s["metrics"])
            total_created += c
            total_modified += m
            total_write_chars += w

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total sessions:** {total_sessions}")
    lines.append(f"- **Claude thinking time:** {format_duration(total_thinking_ms)}")
    lines.append(f"- **Total turns:** {total_turns}")
    lines.append(f"- **Projects touched:** {len(sessions_by_project)}")
    lines.append(f"- **Total tool calls:** {total_tool_calls}")
    lines.append(f"- **Files created:** {total_created}")
    lines.append(f"- **Files modified:** {total_modified}")
    lines.append(f"- **Total chars written:** {_format_chars(total_write_chars)}")
    lines.append("")

    # Aggregate tool categories
    agg_categories: dict[str, int] = defaultdict(int)
    for sessions in sessions_by_project.values():
        for s in sessions:
            for cat, count in s["metrics"]["tool_categories"].items():
                agg_categories[cat] += count

    if agg_categories:
        lines.append("### Tool usage by category")
        lines.append("")
        for cat in sorted(agg_categories, key=lambda c: agg_categories[c], reverse=True):
            lines.append(f"- **{cat}:** {agg_categories[cat]}")
        lines.append("")

    # Sessions by project
    lines.append("## By project")
    lines.append("")

    for project_path in sorted(sessions_by_project):
        sessions = sessions_by_project[project_path]
        name = repo_name(project_path)
        project_thinking = sum(s["metrics"]["thinking_time_ms"] for s in sessions)
        lines.append(
            f"### {name} ({len(sessions)} sessions, thinking: {format_duration(project_thinking)})"
        )
        lines.append("")

        sessions.sort(key=lambda s: s["timestamp"])

        for s in sessions:
            metrics = s["metrics"]
            ts = datetime.fromtimestamp(s["timestamp"] / 1000, tz=UTC)
            ts_str = ts.strftime("%Y-%m-%d %H:%M")
            thinking = format_duration(metrics["thinking_time_ms"])
            turns = metrics["turn_count"]
            tools = sum(metrics["tool_calls"].values())
            display = s.get("display", "").strip()

            # Truncate display to first line, max 120 chars
            if display:
                first_line = display.split("\n")[0]
                if len(first_line) > 120:
                    first_line = first_line[:117] + "..."
                display = first_line

            lines.append(
                f"- **{ts_str} UTC** (thinking: {thinking}, {turns} turns, {tools} tool calls)"
            )
            if display:
                lines.append(f"  {display}")

            # Per-session tool breakdown
            if metrics["tool_categories"]:
                cats = sorted(
                    metrics["tool_categories"].items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
                cat_parts = [f"{cat}: {count}" for cat, count in cats]
                lines.append(f"  Tools: {', '.join(cat_parts)}")

            # Per-session document summary
            created, modified, write_chars = _count_documents(metrics)
            if created or modified:
                parts = []
                if created:
                    parts.append(f"{created} created")
                if modified:
                    parts.append(f"{modified} modified")
                if write_chars:
                    parts.append(f"{_format_chars(write_chars)} chars written")
                lines.append(f"  Files: {', '.join(parts)}")

        lines.append("")

    if not sessions_by_project:
        lines.append("No Claude Code sessions found for work projects in this date range.")
        lines.append("")

    return "\n".join(lines)


def _is_noise_path(file_path: str) -> bool:
    """Check if a file path is internal noise that should be excluded."""
    home = os.path.expanduser("~")
    claude_dir = os.path.join(home, ".claude")
    # Exclude ~/.claude/ internals (plans, projects/memory, etc.)
    # but keep files under the project's own .claude/ (skills, etc.)
    if file_path.startswith(claude_dir + "/"):
        return True
    # Exclude /tmp/ files
    return bool(file_path.startswith("/tmp/"))


def _make_relative(file_path: str, project_path: str) -> str:
    """Make a file path relative to its project root."""
    if file_path.startswith(project_path + "/"):
        return file_path[len(project_path) + 1 :]
    return file_path


def format_documents_markdown(
    sessions_by_project: dict[str, list[dict]],
    start_date: str,
    end_date: str,
) -> str:
    """Format a documents-generated report as markdown."""
    lines: list[str] = []
    lines.append(f"# Documents Generated ({start_date} to {end_date})")
    lines.append("")

    # Collect all documents across sessions, grouped by project
    docs_by_project: dict[str, dict[str, dict]] = defaultdict(dict)
    for project_path, sessions in sessions_by_project.items():
        for s in sessions:
            for file_path, doc in s["metrics"].get("documents", {}).items():
                if _is_noise_path(file_path):
                    continue
                display_path = _make_relative(file_path, project_path)

                existing = docs_by_project[project_path].get(display_path)
                if existing:
                    # Merge: accumulate across sessions
                    existing["operations"].extend(doc["operations"])
                    existing["write_chars"] += doc["write_chars"]
                    existing["edit_net_chars"] += doc["edit_net_chars"]
                    # Keep earliest first_op
                    if doc["first_op_ts"] and (
                        not existing["first_op_ts"] or doc["first_op_ts"] < existing["first_op_ts"]
                    ):
                        existing["first_op"] = doc["first_op"]
                        existing["first_op_ts"] = doc["first_op_ts"]
                else:
                    docs_by_project[project_path][display_path] = {
                        "operations": list(doc["operations"]),
                        "write_chars": doc["write_chars"],
                        "edit_net_chars": doc["edit_net_chars"],
                        "first_op": doc["first_op"],
                        "first_op_ts": doc["first_op_ts"],
                    }

    # Split into created and modified
    all_created: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    all_modified: dict[str, list[tuple[str, dict]]] = defaultdict(list)

    for project_path, docs in docs_by_project.items():
        name = repo_name(project_path)
        for display_path, doc in sorted(docs.items()):
            if doc["first_op"] == "write":
                all_created[name].append((display_path, doc))
            else:
                all_modified[name].append((display_path, doc))

    total_created = sum(len(v) for v in all_created.values())
    total_modified = sum(len(v) for v in all_modified.values())

    lines.append(f"**{total_created} files created, {total_modified} files modified**")
    lines.append("")

    # Created files
    if all_created:
        lines.append(f"## Created ({total_created} files)")
        lines.append("")
        for name in sorted(all_created):
            entries = all_created[name]
            lines.append(f"### {name}")
            lines.append("")
            for display_path, doc in entries:
                ts = ""
                if doc["first_op_ts"]:
                    ts_parsed = _parse_timestamp_ms(doc["first_op_ts"])
                    if ts_parsed:
                        dt = datetime.fromtimestamp(ts_parsed / 1000, tz=UTC)
                        ts = f" — {dt.strftime('%Y-%m-%d')}"
                chars = _format_chars(doc["write_chars"]) if doc["write_chars"] else "0"
                edits = doc["operations"].count("edit")
                edit_note = f", {edits} edits" if edits else ""
                lines.append(f"- `{display_path}` ({chars} chars{edit_note}{ts})")
            lines.append("")

    # Modified files
    if all_modified:
        lines.append(f"## Modified ({total_modified} files)")
        lines.append("")
        for name in sorted(all_modified):
            entries = all_modified[name]
            lines.append(f"### {name}")
            lines.append("")
            for display_path, doc in entries:
                edits = doc["operations"].count("edit")
                writes = doc["operations"].count("write")
                net = doc["edit_net_chars"]
                parts = []
                if writes:
                    parts.append(f"{writes} rewrites")
                if edits:
                    parts.append(f"{edits} edits")
                if net > 0:
                    parts.append(f"+{_format_chars(net)} chars")
                elif net < 0:
                    parts.append(f"-{_format_chars(abs(net))} chars")
                lines.append(f"- `{display_path}` ({', '.join(parts)})")
            lines.append("")

    if not all_created and not all_modified:
        lines.append("No documents created or modified in this date range.")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Collect Claude Code activity data. Outputs markdown to stdout.",
    )
    parser.add_argument(
        "--since",
        required=True,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--until",
        required=True,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--history-path",
        default=DEFAULT_HISTORY_PATH,
        help=f"Path to history.jsonl (default: {DEFAULT_HISTORY_PATH})",
    )
    parser.add_argument(
        "--stats-cache-path",
        default=DEFAULT_STATS_CACHE_PATH,
        help=f"Path to stats-cache.json (default: {DEFAULT_STATS_CACHE_PATH})",
    )
    parser.add_argument(
        "--projects-path",
        default=DEFAULT_PROJECTS_PATH,
        help=f"Path to projects directory (default: {DEFAULT_PROJECTS_PATH})",
    )
    parser.add_argument(
        "--work-dirs",
        nargs="+",
        default=DEFAULT_WORK_DIRS,
        help=f"Work directories to filter by (default: {DEFAULT_WORK_DIRS})",
    )
    parser.add_argument(
        "--copy-raw",
        metavar="DIR",
        help="Copy raw source files (stats-cache.json, filtered history.jsonl) to this directory",
    )
    parser.add_argument(
        "--documents-output",
        metavar="PATH",
        help="Write documents-generated markdown to this file",
    )

    args = parser.parse_args()

    if not os.path.exists(args.history_path):
        print(f"Error: {args.history_path} not found.", file=sys.stderr)
        sys.exit(1)

    # Load and filter history
    sessions = load_history(args.history_path, args.since, args.until, args.work_dirs)

    if not sessions:
        print(
            f"No work sessions found between {args.since} and {args.until}.",
            file=sys.stderr,
        )
        # Still output valid markdown
        print(format_markdown({}, args.since, args.until))
        return

    print(
        f"Found {len(sessions)} work sessions in date range.",
        file=sys.stderr,
    )

    # Analyze each session's conversation file
    sessions_by_project: dict[str, list[dict]] = defaultdict(list)
    for session_id, entry in sessions.items():
        project_path = entry["project"]
        metrics = analyze_conversation(args.projects_path, project_path, session_id)
        sessions_by_project[project_path].append(
            {
                "session_id": session_id,
                "timestamp": entry["timestamp"],
                "display": entry.get("display", ""),
                "metrics": metrics,
            }
        )

    # Copy raw files if requested
    if args.copy_raw:
        raw_dir = Path(args.copy_raw)
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Copy stats cache snapshot
        if os.path.exists(args.stats_cache_path):
            shutil.copy2(args.stats_cache_path, raw_dir / "stats-cache-snapshot.json")
            print(
                f"Copied stats cache to {raw_dir / 'stats-cache-snapshot.json'}",
                file=sys.stderr,
            )

        # Write filtered history excerpt
        excerpt_path = raw_dir / "history-excerpt.jsonl"
        with open(excerpt_path, "w") as f:
            for _session_id, entry in sorted(sessions.items(), key=lambda x: x[1]["timestamp"]):
                f.write(json.dumps(entry) + "\n")
        print(
            f"Wrote {len(sessions)} entries to {excerpt_path}",
            file=sys.stderr,
        )

    # Write documents report if requested
    if args.documents_output:
        docs_path = Path(args.documents_output)
        docs_path.parent.mkdir(parents=True, exist_ok=True)
        docs_md = format_documents_markdown(sessions_by_project, args.since, args.until)
        with open(docs_path, "w") as f:
            f.write(docs_md)
        print(f"Wrote documents report to {docs_path}", file=sys.stderr)

    # Output sessions markdown to stdout
    print(format_markdown(sessions_by_project, args.since, args.until))


if __name__ == "__main__":
    main()
