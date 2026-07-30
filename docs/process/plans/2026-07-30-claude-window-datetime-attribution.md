# Claude Code Window Attribution Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.
> After approval, save a copy of this plan to `docs/process/plans/2026-07-30-claude-window-datetime-attribution.md` before starting Task 1 (per global CLAUDE.md).

**Goal:** Make sprint / between-sprints activity windows datetime-precise and filter every per-entry metric to its window, so no session activity is counted in more than one window and no out-of-window activity leaks in.

**Architecture:** Windows become half-open aware-datetime intervals `[since_dt, until_dt)` chained with no gaps or overlaps: sprint = local midnight of start day → sprint close instant; between-sprints = prior sprint close instant → local midnight of next sprint's start day. `collect_activity.py` filters each transcript entry (turns, tool calls, docs, tokens, message counts) by timestamp, the way tokens already are filtered by date. `collect.py` computes the datetime windows from Jira sprint info and passes ISO datetimes to the Claude, git, and GitHub collectors.

**Tech Stack:** Python 3 via `uv run`, pytest, argparse. No new dependencies.

---

## Context

Diagnosed in sprint 2026-07-B data: `collect_activity.py` pulls a session into a window if *any* `history.jsonl` prompt falls inside it (`load_history`), then aggregates the **entire transcript** with no date filter (`analyze_conversation`) — only tokens are date-filtered. Verified effects:

- Session `e12713da` (`ggdisburse-resources`) worked 7/6–7/13, got a lone `/exit` on 7/16, and its full 5h33m / 283 tool calls were counted in 2026-07-B (zero in-window activity) *and* in 2026-07-A. Recomputed in-window thinking for 07-B: 10h43m vs 17h00m reported (~37% inflation).
- All windows are inclusive-day and chained end-to-start, so boundary days double count even tokens: the 7/15 row is byte-identical in `between-sprints-tokens-by-day.json` and `tokens-by-day.json`, and the quarterly rollup sums both files.
- Two sessions appear with identical full metrics in both `between-sprints-sessions.md` and `sessions.md` of the same sprint.
- Both collection passes write `--copy-raw` to the same dir, so the between-sprints pass overwrites `history-excerpt.jsonl`.

## Agreed window model (Barrett, 2026-07-30)

Sprints typically end 1pm Eastern; the next starts the following business day 9–10am. Using aware datetimes, half-open `[since, until)`:

- **Sprint window:** local midnight (system timezone = Eastern) of the sprint start *date* → sprint `completeDate` (fall back to `endDate`) instant. Pre-start-time activity on the start day (midnight–10am) belongs to the sprint. Activity on the final day *after* close belongs to the next between-window.
- **Between window:** prior sprint `completeDate`/`endDate` instant → local midnight of current sprint's start date. Captures the prior-close afternoon and any full gap days (weekends). Empty (skipped) when close instant ≥ start-day midnight.
- Chain: `[midnight(start_A), close_A) → [close_A, midnight(start_B)) → [midnight(start_B), close_B) → …` — no overlap, no gap.
- Bare `YYYY-MM-DD` CLI args stay supported: `--since D` → local midnight of D; `--until D` → local midnight of D+1 (i.e., D fully included — matches current inclusive behavior).

Files: `src/work_journal/dates.py`, `src/work_journal/claude_code/collect_activity.py`, `src/work_journal/collect.py`, `src/work_journal/git/query_git_log.py`, `src/work_journal/github/query_github_prs.py`, `tests/test_collect_activity.py`, `tests/test_dates.py`, new `tests/test_collect_windows.py`.

---

### Task 1: Window-bound parsing helper in `dates.py`

**Files:**

- Modify: `src/work_journal/dates.py`
- Test: `tests/test_dates.py`

**Step 1: Write failing tests** (append to `tests/test_dates.py`, follow its existing style):

```python
def test_resolve_window_bound_bare_date_is_local_midnight():
    dt = resolve_window_bound("2026-07-15")
    assert (dt.hour, dt.minute) == (0, 0)
    assert dt.tzinfo is not None
    assert dt.date().isoformat() == "2026-07-15"

def test_resolve_window_bound_end_date_rolls_to_next_midnight():
    dt = resolve_window_bound("2026-07-15", end=True)
    assert dt.date().isoformat() == "2026-07-16"
    assert (dt.hour, dt.minute) == (0, 0)

def test_resolve_window_bound_iso_datetime_passthrough():
    dt = resolve_window_bound("2026-07-14T17:30:48.893Z")
    assert dt.tzinfo is not None
    assert dt.astimezone(UTC).hour == 17

def test_resolve_window_bound_naive_datetime_assumed_local():
    dt = resolve_window_bound("2026-07-14T13:00:00")
    assert dt.tzinfo is not None
```

**Step 2:** Run `uv run pytest tests/test_dates.py -v` — expect FAIL (ImportError).

**Step 3: Implement** in `dates.py` (alongside `midnight_iso`, which stays for other callers):

```python
def resolve_window_bound(value: str, *, end: bool = False) -> datetime:
    """Parse a window bound (YYYY-MM-DD or ISO 8601 datetime) to an aware datetime.

    Bare dates anchor to local midnight; an *end* date rolls to the next
    day's midnight so the named day is fully included (half-open windows).
    Naive datetimes are assumed local.
    """
    try:
        d = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.astimezone()
    if end:
        d += timedelta(days=1)
    return d.astimezone()
```

**Step 4:** `uv run pytest tests/test_dates.py -v` — PASS.

**Step 5:** Commit: `add resolve_window_bound datetime parsing helper`

---

### Task 2: Datetime windows in `collect_activity.py` CLI and `load_history`

**Files:**

- Modify: `src/work_journal/claude_code/collect_activity.py` (`main`, `load_history`)
- Test: `tests/test_collect_activity.py`

**Step 1: Failing test** — `load_history` gains aware-datetime params and half-open comparison:

```python
def test_load_history_filters_by_datetime_window(tmp_path):
    hist = tmp_path / "history.jsonl"
    base = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    entries = [
        {"display": "in", "timestamp": int(base.timestamp() * 1000),
         "project": "/Users/x/git/repo", "sessionId": "s1"},
        {"display": "before", "timestamp": int((base - timedelta(days=2)).timestamp() * 1000),
         "project": "/Users/x/git/repo", "sessionId": "s2"},
        {"display": "at-until", "timestamp": int(datetime(2026, 7, 16, tzinfo=UTC).timestamp() * 1000),
         "project": "/Users/x/git/repo", "sessionId": "s3"},  # == until → excluded
    ]
    hist.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    sessions = load_history(
        str(hist),
        datetime(2026, 7, 15, tzinfo=UTC),
        datetime(2026, 7, 16, tzinfo=UTC),
        ["/Users/x/git"],
    )
    assert set(sessions) == {"s1"}
```

**Step 2:** Run it — FAIL (signature takes date strings).

**Step 3: Implement.**

- `load_history(history_path, since_dt: datetime, until_dt: datetime, work_dirs)`: `since_ms = int(since_dt.timestamp() * 1000)`, same for `until_ms`; keep entry when `since_ms <= ts < until_ms`.
- In `main()`: `since_dt = resolve_window_bound(args.since)`, `until_dt = resolve_window_bound(args.until, end=True)` — note `end=True` only changes bare dates; ISO datetimes pass through. Update `--since/--until` help text: "Start (YYYY-MM-DD or ISO datetime)".
- Report headers (`format_markdown`, `format_documents_markdown`) take the datetimes and render local time: `f"({since_dt.astimezone():%Y-%m-%d %H:%M} to {until_dt.astimezone():%Y-%m-%d %H:%M} {until_dt.astimezone():%Z})"`.

**Step 4:** `uv run pytest tests/test_collect_activity.py -v` — new test PASS; fix any existing tests broken by signatures.

**Step 5:** Commit: `accept datetime window bounds in collect_activity`

---

### Task 3: Per-entry window filtering in `analyze_conversation` (the core fix)

**Files:**

- Modify: `src/work_journal/claude_code/collect_activity.py` (`analyze_conversation`, `aggregate_tokens_by_day`, `write_tokens_json`)
- Test: `tests/test_collect_activity.py`

**Step 1: Failing tests.** Build a transcript with entries before, inside, and after the window; every metric family must count only in-window entries:

```python
WIN_SINCE = datetime(2026, 7, 15, tzinfo=UTC)
WIN_UNTIL = datetime(2026, 7, 16, tzinfo=UTC)

def _turn(ts, ms):
    return json.dumps({"type": "system", "subtype": "turn_duration", "timestamp": ts, "durationMs": ms})

def _tool_line(msg_id, ts, tool_id, name="Bash", inp=None):
    block = {"type": "tool_use", "id": tool_id, "name": name, "input": inp or {}}
    return json.dumps({"type": "assistant", "timestamp": ts,
                       "message": {"id": msg_id, "model": "claude-fable-5",
                                   "usage": _usage(1), "content": [block]}})

def test_analyze_conversation_filters_all_metrics_to_window(tmp_path):
    lines = [
        _turn("2026-07-10T10:00:00Z", 300_000),          # out
        _turn("2026-07-15T10:00:00Z", 60_000),           # in
        _tool_line("m1", "2026-07-10T10:01:00Z", "t1",   # out: tool + Write doc + tokens
                   "Write", {"file_path": "/Users/x/git/repo/a.md", "content": "xy"}),
        _tool_line("m2", "2026-07-15T10:01:00Z", "t2",   # in
                   "Write", {"file_path": "/Users/x/git/repo/b.md", "content": "xyz"}),
        json.dumps({"type": "user", "timestamp": "2026-07-10T10:02:00Z"}),  # out
        json.dumps({"type": "user", "timestamp": "2026-07-15T10:02:00Z"}),  # in
    ]
    _write_transcript(tmp_path, "/Users/x/git/repo", "s1", lines)
    m = analyze_conversation(str(tmp_path), "/Users/x/git/repo", "s1", WIN_SINCE, WIN_UNTIL)
    assert m["thinking_time_ms"] == 60_000
    assert m["turn_count"] == 1
    assert sum(m["tool_calls"].values()) == 1
    assert list(m["documents"]) == ["/Users/x/git/repo/b.md"]
    assert m["user_messages"] == 1
    assert list(m["tokens"]) == ["2026-07-15"]  # only in-window usage

def test_analyze_conversation_fully_out_of_window_is_empty(tmp_path):
    lines = [_turn("2026-07-10T10:00:00Z", 300_000)]
    _write_transcript(tmp_path, "/Users/x/git/repo", "s1", lines)
    m = analyze_conversation(str(tmp_path), "/Users/x/git/repo", "s1", WIN_SINCE, WIN_UNTIL)
    assert m["turn_count"] == 0 and m["thinking_time_ms"] == 0
```

**Step 2:** Run — FAIL (extra args).

**Step 3: Implement.**

- Signature: `analyze_conversation(projects_path, project_path, session_id, since_dt, until_dt)` (required params — no silent unfiltered path). Precompute `since_ms`/`until_ms`; per entry compute `in_window = ts_ms is not None and since_ms <= ts_ms < until_ms`.
- Gate on `in_window`: `user_messages`, `assistant_messages`, token accumulation, `tool_use` counting + document ops, `turn_duration`/`turn_count`.
- Keep `seen_tool_uses`/`seen_message_ids` dedup across the *whole* file (an out-of-window first occurrence marks the id seen, so a streamed repeat inside the window isn't miscounted — the call happened out of window).
- First/last timestamps and `duration_ms`: track from in-window entries only.
- Token day bucketing: replace the UTC `strftime` with `datetime.fromtimestamp(ts_ms / 1000, tz=UTC).astimezone(day_tz).strftime("%Y-%m-%d")` where `day_tz` is a new optional param defaulting to the system local zone (tests pass `timezone.utc` or a fixed offset to stay deterministic). Days now match Barrett's calendar.
- `aggregate_tokens_by_day`: delete the `since`/`until` date-string filtering (now redundant — entries are pre-filtered); it becomes a pure merge. Update its callers (`format_markdown`, `write_tokens_json`) and tests.
- `write_tokens_json`: payload `"since"`/`"until"` become the window datetimes (`.isoformat()`).

**Step 4:** `uv run pytest tests/test_collect_activity.py -v` — PASS (update `test_aggregate_tokens_by_day_clamps_to_window` → merge-only semantics; update existing `analyze_conversation` tests to pass a wide window).

**Step 5:** Commit: `filter all transcript metrics to the collection window`

---

### Task 4: Drop sessions with no in-window activity

**Files:**

- Modify: `src/work_journal/claude_code/collect_activity.py` (new `has_activity`, used in `main`)
- Test: `tests/test_collect_activity.py`

**Step 1: Failing test:**

```python
def test_has_activity():
    empty = {"turn_count": 0, "tool_calls": {}, "tokens": {}}
    assert not has_activity(empty)
    assert has_activity({**empty, "turn_count": 1})
    assert has_activity({**empty, "tokens": {"2026-07-15": {}}})
```

**Step 2:** FAIL. **Step 3: Implement:**

```python
def has_activity(metrics: ConversationMetrics) -> bool:
    """True when a session has any in-window activity worth reporting."""
    return bool(
        metrics["turn_count"] or metrics["tokens"] or any(metrics["tool_calls"].values())
    )
```

In `main()`'s analyze loop, `continue` when `not has_activity(metrics)` (this drops the `/exit`-only case), and print a stderr note: `Skipped N sessions with no in-window activity.` A tool-less Q&A session still has `turn_duration` entries, so it's kept.

**Step 4:** PASS. **Step 5:** Commit: `skip sessions with no in-window activity`

---

### Task 5: `--copy-raw` collision fix

**Files:**

- Modify: `src/work_journal/claude_code/collect_activity.py` (args + copy block)

**Step 1:** Add `--raw-prefix` (default `""`) and `--skip-stats-cache` (store_true) args. Excerpt path becomes `raw_dir / f"{args.raw_prefix}history-excerpt.jsonl"`; stats-cache copy is skipped when `--skip-stats-cache`. (Thin argparse wiring — no unit test; verified end-to-end in Task 7.)

**Step 2:** Commit: `add raw-prefix and skip-stats-cache options to copy-raw`

---

### Task 6: Compute datetime windows in `collect.py` and wire them through

**Files:**

- Modify: `src/work_journal/collect.py` (new `compute_windows`; `main`; `collect_claude_code_activity`)
- Modify: `src/work_journal/git/query_git_log.py:40-41`, `src/work_journal/github/query_github_prs.py` (the five `midnight_iso(...)` range call sites)
- Test: new `tests/test_collect_windows.py`

**Step 1: Failing tests** for the pure function:

```python
from work_journal.collect import compute_windows

SPRINT = {"startDate": "2026-07-15T14:11:10.534Z", "endDate": "2026-07-30T17:00:00.000Z"}
PRIOR = {"completeDate": "2026-07-14T17:30:48.893Z", "endDate": "2026-07-14T17:00:00.000Z"}

def test_sprint_window_spans_start_day_midnight_to_close():
    since, until, _, _ = compute_windows(SPRINT, PRIOR)
    local = since.astimezone()
    assert (local.hour, local.minute) == (0, 0)
    assert local.date().isoformat() == "2026-07-15"
    assert until == datetime(2026, 7, 30, 17, 0, tzinfo=UTC)

def test_between_window_runs_from_prior_close_to_start_day_midnight():
    since, _, b_since, b_until = compute_windows(SPRINT, PRIOR)
    assert b_since == datetime(2026, 7, 14, 17, 30, 48, 893000, tzinfo=UTC)
    assert b_until == since

def test_between_window_empty_when_prior_closes_after_start_midnight():
    late_prior = {"completeDate": "2026-07-15T12:00:00.000Z"}  # after start-day local midnight
    _, _, b_since, b_until = compute_windows(SPRINT, late_prior)
    assert b_since is None and b_until is None

def test_no_prior_sprint():
    _, _, b_since, b_until = compute_windows(SPRINT, None)
    assert b_since is None and b_until is None
```

**Step 2:** FAIL. **Step 3: Implement** in `collect.py`:

```python
def compute_windows(
    sprint_info: dict, prior_sprint: dict | None
) -> tuple[datetime, datetime, datetime | None, datetime | None]:
    """Datetime collection windows, half-open [since, until).

    Sprint: local midnight of the start day -> sprint close instant
    (completeDate, falling back to endDate). Between: prior sprint close
    instant -> local midnight of the start day; None/None when empty.
    """
    start_dt = resolve_window_bound(sprint_info["startDate"])
    sprint_since = start_dt.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    sprint_until = resolve_window_bound(
        sprint_info.get("completeDate") or sprint_info["endDate"]
    )
    between_since = between_until = None
    if prior_sprint:
        raw = prior_sprint.get("completeDate") or prior_sprint.get("endDate")
        if raw:
            prior_close = resolve_window_bound(raw)
            if prior_close < sprint_since:
                between_since, between_until = prior_close, sprint_since
    return sprint_since, sprint_until, between_since, between_until
```

Wiring in `main()`:

- Replace the `prior_sprint_end` / `has_gap` date-string logic (`collect.py:319-343`) with `compute_windows(sprint_info, prior_sprint)`; `has_gap = between_since is not None`. Keep `start_date`/`end_date` date strings for the Jira JQL `variables` (JQL stays day-based; `prior_sprint_end` variable keeps its `raw[:10]` derivation).
- Git/GitHub/Claude calls take `.isoformat()` strings of the window datetimes for both the sprint pass and the between pass.
- `collect_claude_code_activity`: pass ISO datetimes through as `--since`/`--until`; between pass adds `"--raw-prefix", "between-sprints-", "--skip-stats-cache"` (add a `raw_prefix`/`skip_stats_cache` kwarg or config entry mirroring the existing `output` override pattern at `collect.py:423-431`).
- In `query_git_log.py` and `query_github_prs.py`, replace `midnight_iso(since)` → `resolve_window_bound(since).isoformat()` and `midnight_iso(until)` → `resolve_window_bound(until, end=True).isoformat()`. Behavior note: bare-date `--until` becomes *inclusive* of that day (previously the final day was silently excluded — the old code cut sprint-final-day commits). ISO datetimes pass through exactly. `midnight_iso` itself stays for any other callers.
- Update the dry-run print block (`collect.py:345-371`) to show the datetime windows.

**Step 4:** `uv run pytest -v` — all tests PASS.

**Step 5:** Commit: `compute datetime collection windows and wire through collectors`

---

### Task 7: Full-suite verification and docs touch-up

**Step 1:** `uv run ruff check . && uv run ruff format . && uv run mypy src/ && uv run pytest`

**Step 2: End-to-end dry run + real run against 07-B:**

```bash
uv run python3 src/work_journal/collect.py 2026-07-B --dry-run
uv run python3 src/work_journal/collect.py 2026-07-B
```

Verify in `work/sprint-notes/2026-07-B/claude-code/`:

- `sessions.md` no longer lists the `ggdisburse-resources` `/exit` session; total thinking ≈ 10h45m (in-window figure), not ~17h.
- No session appears in both `sessions.md` and `between-sprints-sessions.md` with identical metrics (the `redesignation` and `referrals` 57m duplicates split at the window boundary instead).
- `tokens-by-day.json` and `between-sprints-tokens-by-day.json` share no duplicated day/model rows; the between file covers only 7/14 after 17:30Z (+ 7/15 pre-midnight-ET spillover under local-day bucketing).
- `between-sprints-history-excerpt.jsonl` exists alongside the sprint `history-excerpt.jsonl`.

**Step 3:** Update the docstring at the top of `collect_activity.py` (window semantics: half-open datetimes, per-entry filtering) and the `collect.py` module docstring if it mentions dates.

**Step 4:** Commit: `document datetime window semantics`

---

### Task 8 (after code fix — restatement)

Per Barrett: do this after the fix lands.

1. **07-B:** rerun `collect.py 2026-07-B` after sprint close (~1pm ET today) so `completeDate` exists and late sessions are captured; then correct the numbers in `draft.md`'s "Claude Code Activity" and "Between Sprints" sections (remove the defect narrative or condense it to a one-line note).
2. **07-A:** regenerate only the Claude artifacts (don't rerun full collect — it would overwrite Jira snapshots). Windows from `work/sprint-notes/2026-07-A/jira/sprint-info.json` (+ its prior-sprint info for the between window), e.g.:

   ```bash
   uv run python3 src/work_journal/claude_code/collect_activity.py \
     --since 2026-07-01 --until 2026-07-14T17:30:48.893Z \
     --copy-raw work/sprint-notes/2026-07-A/claude-code \
     --documents-output work/sprint-notes/2026-07-A/claude-code/documents.md \
     --tokens-output work/sprint-notes/2026-07-A/claude-code/tokens-by-day.json \
     > work/sprint-notes/2026-07-A/claude-code/sessions.md
   ```

   (plus the between-sprints variant), then restate the 07-A draft's Claude numbers (reported 15h thinking is inflated by the same ggdisburse session). Flag to Barrett if the 07-A doc was already uploaded to Google Docs.
3. Out of scope (note only): sprints before 07-A and the already-delivered Q2 progress brief carry the same inflation; restating them is a separate decision.

---

## Verification (overall)

- `uv run pytest` / `uv run ruff check .` / `uv run mypy src/` all clean.
- Independent check: rerun the scratchpad recomputation script (per-entry windowed totals) against the regenerated `sessions.md` — totals must match.
- Boundary invariant: for 07-B artifacts, sum(sprint) + sum(between) token/thinking totals must equal a single-pass run over `[close_A, close_B)` (spot-check thinking minutes).
