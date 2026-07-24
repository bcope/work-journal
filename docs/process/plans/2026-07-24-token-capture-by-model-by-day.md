# Token Capture by Model by Day Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Capture Claude Code token usage per model per day at sprint-collection time, before session transcripts rotate out of local retention.

**Architecture:** `collect_activity.py` already reads each session's transcript JSONL in `analyze_conversation`. Extend that single pass to accumulate token usage from assistant entries (`message.usage`, `message.model`, deduplicated on `message.id`), attributed to the UTC date of each entry. Aggregate across sessions and write a `tokens-by-day.json` artifact per collection window (sprint and between-sprints), plus a human-readable summary line in `sessions.md`. The rollup script reads the JSON artifacts (exact integers, canonical store) and adds token rows to Summary Statistics.

**Tech Stack:** Python stdlib only (json, datetime, collections). pytest for tests.

---

## Background for the implementer

- Transcripts live at `~/.claude/projects/{project-slug}/{session_id}.jsonl`. Assistant
  entries carry `message.model` (e.g. `claude-opus-4-8`) and `message.usage` with
  `input_tokens`, `output_tokens`, `cache_read_input_tokens`,
  `cache_creation_input_tokens`. Streaming writes the same API message across multiple
  JSONL lines: dedup on `message.id` (verified: up to 6 lines per id, usage identical
  across them).
- Transcripts rotate out after ~30 days, which is why capture must happen during sprint
  collection. The old source (`~/.claude/stats-cache.json`) has a 7-week hole
  (2026-04-09 to 2026-05-31) and is not trusted.
- A session can span midnight, so attribute tokens to each entry's own UTC timestamp
  date, not the session start date.
- Dedup is per transcript file. A resumed session that copies history into a new file
  could double-count; the existing tool/document metrics accept the same limitation.
- Known non-issues: entries without `usage` or `model` are skipped; a defensive skip for
  the `<synthetic>` placeholder model is included.

## Artifact schema

`claude-code/tokens-by-day.json` (and `claude-code/between-sprints-tokens-by-day.json`):

```json
{
  "since": "2026-06-12",
  "until": "2026-06-30",
  "days": [
    {
      "date": "2026-06-15",
      "models": {
        "claude-opus-4-8": {
          "input_tokens": 12829,
          "output_tokens": 605,
          "cache_read_input_tokens": 16018,
          "cache_creation_input_tokens": 3812
        }
      }
    }
  ]
}
```

---

### Task 1: Token accumulation in `analyze_conversation`

**Files:**

- Create: `tests/test_collect_activity.py`
- Modify: `src/work_journal/claude_code/collect_activity.py` (`ConversationMetrics` ~line 138, `analyze_conversation` ~line 153)

**Step 1: Write the failing test**

```python
"""Tests for claude_code/collect_activity.py."""

import json

from work_journal.claude_code.collect_activity import analyze_conversation


def _assistant_line(msg_id, model, ts, usage):
    return json.dumps(
        {
            "type": "assistant",
            "timestamp": ts,
            "message": {"id": msg_id, "model": model, "usage": usage, "content": []},
        }
    )


def _write_transcript(projects_path, project_path, session_id, lines):
    slug = project_path.replace("/", "-")
    session_dir = projects_path / slug
    session_dir.mkdir(parents=True)
    (session_dir / f"{session_id}.jsonl").write_text("\n".join(lines) + "\n")


def test_analyze_conversation_tokens_by_model_by_date(tmp_path):
    usage_a = {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_input_tokens": 1000,
        "cache_creation_input_tokens": 200,
    }
    usage_b = {
        "input_tokens": 10,
        "output_tokens": 5,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    lines = [
        # Same message id repeated: must count once
        _assistant_line("msg_1", "claude-opus-4-8", "2026-06-15T10:00:00.000Z", usage_a),
        _assistant_line("msg_1", "claude-opus-4-8", "2026-06-15T10:00:01.000Z", usage_a),
        # Different model, next UTC day
        _assistant_line("msg_2", "claude-haiku-4-5", "2026-06-16T00:30:00.000Z", usage_b),
        # No usage: skipped
        json.dumps(
            {
                "type": "assistant",
                "timestamp": "2026-06-16T01:00:00.000Z",
                "message": {"id": "msg_3", "model": "claude-opus-4-8", "content": []},
            }
        ),
        # Synthetic model: skipped
        _assistant_line("msg_4", "<synthetic>", "2026-06-16T02:00:00.000Z", usage_b),
        # Non-assistant entry: ignored
        json.dumps({"type": "user", "timestamp": "2026-06-16T03:00:00.000Z"}),
    ]
    _write_transcript(tmp_path, "/Users/x/git/repo", "sess1", lines)

    metrics = analyze_conversation(str(tmp_path), "/Users/x/git/repo", "sess1")

    assert metrics["tokens"] == {
        "2026-06-15": {"claude-opus-4-8": usage_a},
        "2026-06-16": {"claude-haiku-4-5": usage_b},
    }


def test_analyze_conversation_missing_file_has_empty_tokens(tmp_path):
    metrics = analyze_conversation(str(tmp_path), "/Users/x/git/repo", "nope")
    assert metrics["tokens"] == {}
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_collect_activity.py -v`
Expected: FAIL with `KeyError: 'tokens'`

**Step 3: Write minimal implementation**

In `ConversationMetrics`, add:

```python
    tokens: dict[str, dict[str, dict[str, int]]]
```

In `analyze_conversation`: add `"tokens": {}` to the `result` initializer and
`seen_message_ids: set[str] = set()` beside `seen_tool_uses`. Inside the
`elif entry_type == "assistant":` branch (after `message = entry.get("message", {})`):

```python
                usage = message.get("usage")
                model = message.get("model")
                message_id = message.get("id", "")
                if (
                    usage
                    and model
                    and not model.startswith("<")
                    and message_id not in seen_message_ids
                ):
                    seen_message_ids.add(message_id)
                    ts_ms = _parse_timestamp_ms(timestamp_str)
                    if ts_ms is not None:
                        date = datetime.fromtimestamp(ts_ms / 1000, tz=UTC).strftime("%Y-%m-%d")
                        day = result["tokens"].setdefault(date, {})
                        totals = day.setdefault(
                            model,
                            {
                                "input_tokens": 0,
                                "output_tokens": 0,
                                "cache_read_input_tokens": 0,
                                "cache_creation_input_tokens": 0,
                            },
                        )
                        for field in totals:
                            totals[field] += usage.get(field, 0)
```

Update the docstring's `Returns` list with
`tokens: {date: {model: {input/output/cache_read/cache_creation token totals}}}`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_collect_activity.py -v`
Expected: 2 PASS

**Step 5: Commit**

```bash
git add tests/test_collect_activity.py src/work_journal/claude_code/collect_activity.py
git commit -m "extract per-day per-model token usage from transcripts"
```

### Task 2: Aggregate tokens across sessions

**Files:**

- Modify: `src/work_journal/claude_code/collect_activity.py` (new function after `format_duration`, ~line 307)
- Test: `tests/test_collect_activity.py`

**Step 1: Write the failing test**

```python
from work_journal.claude_code.collect_activity import aggregate_tokens_by_day


def test_aggregate_tokens_by_day_merges_sessions():
    def usage(n):
        return {
            "input_tokens": n,
            "output_tokens": n,
            "cache_read_input_tokens": n,
            "cache_creation_input_tokens": n,
        }

    sessions_by_project = {
        "/Users/x/git/a": [
            {"metrics": {"tokens": {"2026-06-15": {"claude-opus-4-8": usage(10)}}}},
            {"metrics": {"tokens": {"2026-06-15": {"claude-opus-4-8": usage(5)}}}},
        ],
        "/Users/x/git/b": [
            {"metrics": {"tokens": {"2026-06-15": {"claude-haiku-4-5": usage(1)}}}},
        ],
    }
    days = aggregate_tokens_by_day(sessions_by_project)
    assert days == {
        "2026-06-15": {
            "claude-opus-4-8": usage(15),
            "claude-haiku-4-5": usage(1),
        }
    }
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_collect_activity.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
def aggregate_tokens_by_day(
    sessions_by_project: dict[str, list[dict]],
) -> dict[str, dict[str, dict[str, int]]]:
    """Merge per-session token metrics into {date: {model: totals}}."""
    days: dict[str, dict[str, dict[str, int]]] = {}
    for sessions in sessions_by_project.values():
        for s in sessions:
            for date, models in s["metrics"].get("tokens", {}).items():
                day = days.setdefault(date, {})
                for model, usage in models.items():
                    totals = day.setdefault(model, dict.fromkeys(usage, 0))
                    for field, value in usage.items():
                        totals[field] = totals.get(field, 0) + value
    return days
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_collect_activity.py -v`
Expected: 3 PASS

**Step 5: Commit**

```bash
git add tests/test_collect_activity.py src/work_journal/claude_code/collect_activity.py
git commit -m "aggregate token usage across sessions by day and model"
```

### Task 3: Token summary line in sessions.md

**Files:**

- Modify: `src/work_journal/claude_code/collect_activity.py` (`_format_chars` ~line 325, `format_markdown` ~line 334)
- Test: `tests/test_collect_activity.py`

**Step 1: Write the failing test**

```python
from work_journal.claude_code.collect_activity import _format_count, format_markdown


def test_format_count_suffixes():
    assert _format_count(1_500_000_000) == "1.5B"
    assert _format_count(4_224_400) == "4.2M"
    assert _format_count(361_000) == "361.0K"
    assert _format_count(532) == "532"


def test_format_markdown_token_line():
    def usage(n):
        return {
            "input_tokens": n,
            "output_tokens": 2 * n,
            "cache_read_input_tokens": 3 * n,
            "cache_creation_input_tokens": 4 * n,
        }

    session = {
        "session_id": "s1",
        "timestamp": 1750000000000,
        "display": "hello",
        "metrics": {
            "duration_ms": 0,
            "user_messages": 1,
            "assistant_messages": 1,
            "tool_calls": {},
            "tool_categories": {},
            "first_timestamp": None,
            "last_timestamp": None,
            "thinking_time_ms": 60000,
            "turn_count": 1,
            "documents": {},
            "tokens": {"2026-06-15": {"claude-opus-4-8": usage(1000)}},
        },
    }
    md = format_markdown({"/Users/x/git/a": [session]}, "2026-06-12", "2026-06-30")
    assert "- **Token usage:** 1.0K in / 2.0K out / 3.0K cache read / 4.0K cache write" in md


def test_format_markdown_no_token_line_when_absent():
    md = format_markdown({}, "2026-06-12", "2026-06-30")
    assert "Token usage" not in md
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_collect_activity.py -v`
Expected: FAIL with ImportError (`_format_count`)

**Step 3: Write minimal implementation**

Add below `_format_chars`:

```python
def _format_count(n: int) -> str:
    """Format a large count with K/M/B suffix."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    return _format_chars(n)
```

In `format_markdown`, after the `Total chars written` line:

```python
    token_totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    for days in aggregate_tokens_by_day(sessions_by_project).values():
        for usage in days.values():
            for field in token_totals:
                token_totals[field] += usage.get(field, 0)
    if any(token_totals.values()):
        lines.append(
            f"- **Token usage:** {_format_count(token_totals['input_tokens'])} in"
            f" / {_format_count(token_totals['output_tokens'])} out"
            f" / {_format_count(token_totals['cache_read_input_tokens'])} cache read"
            f" / {_format_count(token_totals['cache_creation_input_tokens'])} cache write"
        )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_collect_activity.py -v`
Expected: 6 PASS

**Step 5: Commit**

```bash
git add tests/test_collect_activity.py src/work_journal/claude_code/collect_activity.py
git commit -m "add token usage summary line to sessions report"
```

### Task 4: `--tokens-output` CLI flag writing the JSON artifact

**Files:**

- Modify: `src/work_journal/claude_code/collect_activity.py` (new function after `aggregate_tokens_by_day`; `main` argparse ~line 632 and output block ~line 698)
- Test: `tests/test_collect_activity.py`

**Step 1: Write the failing test**

```python
from work_journal.claude_code.collect_activity import write_tokens_json


def test_write_tokens_json(tmp_path):
    def usage(n):
        return {
            "input_tokens": n,
            "output_tokens": n,
            "cache_read_input_tokens": n,
            "cache_creation_input_tokens": n,
        }

    sessions_by_project = {
        "/Users/x/git/a": [
            {
                "metrics": {
                    "tokens": {
                        "2026-06-16": {"claude-opus-4-8": usage(2)},
                        "2026-06-15": {"claude-opus-4-8": usage(1)},
                    }
                }
            }
        ]
    }
    out = tmp_path / "sub" / "tokens-by-day.json"
    write_tokens_json(out, sessions_by_project, "2026-06-12", "2026-06-30")
    data = json.loads(out.read_text())
    assert data["since"] == "2026-06-12"
    assert data["until"] == "2026-06-30"
    assert [d["date"] for d in data["days"]] == ["2026-06-15", "2026-06-16"]
    assert data["days"][0]["models"] == {"claude-opus-4-8": usage(1)}
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_collect_activity.py -v`
Expected: FAIL with ImportError (`write_tokens_json`)

**Step 3: Write minimal implementation**

```python
def write_tokens_json(
    path: Path,
    sessions_by_project: dict[str, list[dict]],
    since: str,
    until: str,
) -> None:
    """Write the tokens-by-day artifact for a collection window."""
    days = aggregate_tokens_by_day(sessions_by_project)
    payload = {
        "since": since,
        "until": until,
        "days": [{"date": date, "models": days[date]} for date in sorted(days)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
```

In `main`, add the argument:

```python
    parser.add_argument(
        "--tokens-output",
        metavar="PATH",
        help="Write per-day per-model token usage JSON to this file",
    )
```

And next to the `--documents-output` handling block:

```python
    if args.tokens_output:
        tokens_path = Path(args.tokens_output)
        write_tokens_json(tokens_path, sessions_by_project, args.since, args.until)
        print(f"Wrote token usage to {tokens_path}", file=sys.stderr)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_collect_activity.py -v`
Expected: 7 PASS

**Step 5: Commit**

```bash
git add tests/test_collect_activity.py src/work_journal/claude_code/collect_activity.py
git commit -m "write tokens-by-day.json artifact via --tokens-output"
```

### Task 5: Wire `--tokens-output` into collect.py

**Files:**

- Modify: `src/work_journal/collect.py` (`collect_claude_code_activity` ~line 196; between-sprints call ~line 418)

**Step 1: Implement**

In `collect_claude_code_activity`, next to `docs_output_file`:

```python
    tokens_output_file = cc_config.get("tokens_output", "claude-code/tokens-by-day.json")
    tokens_output_path = sprint_dir / tokens_output_file
```

And in `helper_args`, after the `--documents-output` pair:

```python
        "--tokens-output",
        str(tokens_output_path),
```

In the between-sprints call (~line 418), add to the config override dict:

```python
                    "tokens_output": "claude-code/between-sprints-tokens-by-day.json",
```

**Step 2: Smoke test against real data**

Run:

```bash
uv run python3 src/work_journal/claude_code/collect_activity.py \
  --since 2026-07-01 --until 2026-07-24 \
  --tokens-output /tmp-scratch/tokens-smoke.json > /dev/null
```

(Use the session scratchpad directory for the output file.)
Expected: stderr reports `Wrote token usage to ...`; the JSON contains multiple days
with model keys like `claude-opus-4-8`; sessions markdown on stdout includes the
`Token usage:` line.

**Step 3: Run full checks**

Run: `uv run pytest -q && uv run ruff check . && uv run mypy src/`
Expected: all pass

**Step 4: Commit**

```bash
git add src/work_journal/collect.py
git commit -m "collect token usage during sprint and between-sprints windows"
```

### Task 6: Rollup pickup in collect_progress_brief.py

**Files:**

- Modify: `src/work_journal/collect_progress_brief.py` (new loader after `parse_claude_code_stats`; `format_rollup` params and Summary Statistics block; `main` totals loop)
- Test: `tests/test_collect_progress_brief.py`

**Step 1: Write the failing test**

```python
import json

from work_journal.collect_progress_brief import load_token_usage


def test_load_token_usage_sums_files_days_models(tmp_path):
    cc_dir = tmp_path / "claude-code"
    cc_dir.mkdir()

    def usage(n):
        return {
            "input_tokens": n,
            "output_tokens": n,
            "cache_read_input_tokens": n,
            "cache_creation_input_tokens": n,
        }

    (cc_dir / "tokens-by-day.json").write_text(
        json.dumps(
            {
                "days": [
                    {"date": "2026-06-15", "models": {"claude-opus-4-8": usage(10)}},
                    {"date": "2026-06-16", "models": {"claude-haiku-4-5": usage(1)}},
                ]
            }
        )
    )
    (cc_dir / "between-sprints-tokens-by-day.json").write_text(
        json.dumps({"days": [{"date": "2026-06-11", "models": {"claude-opus-4-8": usage(5)}}]})
    )
    totals = load_token_usage(tmp_path)
    assert totals == {
        "input_tokens": 16,
        "output_tokens": 16,
        "cache_read_input_tokens": 16,
        "cache_creation_input_tokens": 16,
    }


def test_load_token_usage_missing_files(tmp_path):
    assert load_token_usage(tmp_path) == {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_collect_progress_brief.py -v`
Expected: FAIL with ImportError (`load_token_usage`)

**Step 3: Write minimal implementation**

```python
def load_token_usage(sprint_dir: Path) -> dict[str, int]:
    """Sum token usage across a sprint's tokens-by-day artifacts."""
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    for filename in (
        "claude-code/tokens-by-day.json",
        "claude-code/between-sprints-tokens-by-day.json",
    ):
        path = sprint_dir / filename
        if not path.exists():
            continue
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for day in data.get("days", []):
            for usage in day.get("models", {}).values():
                for field in totals:
                    totals[field] += usage.get(field, 0)
    return totals
```

In `format_rollup`, add a `cc_tokens: dict[str, int]` parameter and, after the
chars-written row:

```python
    if any(cc_tokens.values()):
        lines.append(f"| Claude Code tokens (input) | {cc_tokens['input_tokens']:,} |")
        lines.append(f"| Claude Code tokens (output) | {cc_tokens['output_tokens']:,} |")
        lines.append(
            f"| Claude Code tokens (cache read) | {cc_tokens['cache_read_input_tokens']:,} |"
        )
        lines.append(
            f"| Claude Code tokens (cache write) | {cc_tokens['cache_creation_input_tokens']:,} |"
        )
```

In `main`: initialize `cc_token_totals = {...four zeros...}` beside `cc_totals`, and in
the per-sprint loop:

```python
        sprint_tokens = load_token_usage(sprint_dir)
        for key in cc_token_totals:
            cc_token_totals[key] += sprint_tokens[key]
```

Pass `cc_tokens=cc_token_totals` in the `format_rollup` call.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_collect_progress_brief.py -v`
Expected: PASS

**Step 5: Regression check on real Q2 data**

Run: `uv run python3 src/work_journal/collect_progress_brief.py 2026-Q2`
Expected: rollup regenerates with no token rows (Q2 sprints have no token artifacts —
the rows appear only once sprints are collected with the new pipeline), and the
existing sessions/thinking/turns/chars rows are unchanged.

**Step 6: Run full checks and commit**

Run: `uv run pytest -q && uv run ruff check . && uv run mypy src/`
Expected: all pass

```bash
git add tests/test_collect_progress_brief.py src/work_journal/collect_progress_brief.py
git commit -m "include token usage totals in quarterly rollup"
```

### Task 7: Document the new artifact

**Files:**

- Modify: `src/work_journal/claude_code/collect_activity.py` (module docstring)
- Modify: `CLAUDE.md` (project structure note for `daily_log.py` area is untouched; no CLAUDE.md change needed unless directory docs list artifacts — they don't. Skip if nothing fits.)

**Step 1: Update the module docstring** to mention token capture:

Add to the docstring metrics list:

```text
- Token usage: per-day, per-model input/output/cache token totals (deduplicated
  by message id), written to tokens-by-day.json via --tokens-output
```

**Step 2: Commit**

```bash
git add src/work_journal/claude_code/collect_activity.py
git commit -m "document token capture in collect_activity docstring"
```
