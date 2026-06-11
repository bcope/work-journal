# Plan: Claude Thinking Time and Documents Generated Metrics

Extends the Claude Code activity collection (see `plan-claude-code-activity.md`)
with two new metrics derived from conversation JSONL files:

1. **Claude thinking time** — how long Claude spent actively working per session
2. **Documents generated** — which files Claude created or modified, with sizes

## Data sources

All data comes from `~/.claude/projects/{project-slug}/{session-id}.jsonl`.
No new external data sources are needed.

### Conversation JSONL entry types

Each line in a conversation JSONL file is one of:

| Type | What it represents |
|---|---|
| `user` (human) | A human-typed prompt. Has `message.content` as text. |
| `user` (tool_result) | A tool execution result. Has `message.content` as `[{type: "tool_result", ...}]`. |
| `assistant` | One content block from a streaming API response. Shares `message.id` with other blocks from the same API call. |
| `progress` | Hook execution or sub-agent progress. |
| `system` | System events including `turn_duration` entries. |
| `file-history-snapshot` | Cumulative snapshot of files modified so far. |

### Key timing properties

- Every entry has a top-level `timestamp` (ISO 8601), except
  `file-history-snapshot` which has `snapshot.timestamp`.
- Multiple `assistant` entries share the same `message.id` when they come
  from a single API call (one entry per content block: text, thinking,
  tool_use).
- Local tool execution (Read, Glob, Edit, Write, Grep) is effectively
  instant (< 0.05s). Bash and MCP tools take measurable time.

### The file-history directory

`~/.claude/file-history/{session-id}/` contains actual file content snapshots.
Each file is named `{hash}@v{N}` where:

- `{hash}` identifies the file path (deterministic across versions)
- `v{N}` is the version number within the session

Version 1 is the backup of the file *before* Claude's first edit. If
`backupFileName` is `None` for v1 in the snapshot entry, the file was
*created* (no prior content existed).

These snapshots are referenced from `file-history-snapshot` entries in the
conversation JSONL via `trackedFileBackups.{path}.backupFileName`.

## Metric 1: Claude thinking time

### What we mean

"Claude thinking time" = the total time Claude spent actively working during
a session. This excludes idle time (user away, session left open overnight)
but includes API latency, model thinking, output generation, and tool
execution.

### Detection strategy: turn_duration system entries

Each autonomous turn ends with a system entry:

```json
{
  "type": "system",
  "subtype": "turn_duration",
  "durationMs": 237739,
  "timestamp": "2026-02-19T23:00:41.094Z"
}
```

This is the **authoritative turn duration** computed by Claude Code itself. It
measures from the moment the user submits a message to the moment Claude
finishes responding (including all chained tool calls in the autonomous
sequence).

**Claude thinking time per session = sum of all `turn_duration` values.**

### Example from session c6d35017 (performance, Feb 17)

This session had 7 human-initiated turns:

| Turn | Human prompt (abbreviated) | durationMs | As time |
|---|---|---|---|
| 1 | "I have implemented the Gmail..." | 166,188 | 2m 46s |
| 2 | "I don't think the qualitative..." | 123,511 | 2m 04s |
| 3 | "What's the best next step..." | 157,730 | 2m 38s |
| 4 | "enrich skill please" | 237,739 | 3m 58s |
| 5 | "I think I'd like to focus next..." | 110,420 | 1m 50s |
| 6 | "write it up as a plan doc..." | 90,106 | 1m 30s |
| 7 | "I've updated the Open questions..." | 107,535 | 1m 48s |
| **Total** | | **993,229** | **16m 33s** |

Wall-clock duration of this session was 15h 42m. Claude thinking time was
16m 33s. The rest was idle time between turns.

### Where turn_duration comes from

Empirical analysis of the turn structure shows Claude's time breaks down as:

| Category | % of turn time | Notes |
|---|---|---|
| API calls (network + model) | ~97% | Includes extended thinking and output generation |
| Local tool execution | ~1-2% | Read/Write/Edit/Glob/Grep are < 0.05s each |
| Hook processing | ~1-2% | PostToolUse and Stop hooks |

So "Claude thinking time" is almost entirely API time. This is the right
metric for "how much compute did Claude use on my behalf."

### Decomposition (optional, for richer analysis)

If we want to break thinking time into sub-components, we can use the
streaming entry timestamps:

1. **Initial API latency**: gap from `user` (human) to first `assistant`
   entry (the `"\n\n"` sentinel). Consistently 2.5-3.1s.
2. **Per-API-call time**: gap from preceding `tool_result` to the first
   `assistant` entry of a new `message.id`. Varies from 2.5s (quick
   continuation) to 72s (generating a large file).
3. **Extended thinking time**: the `thinking` content block contains the
   model's chain-of-thought. The gap between the thinking block and the next
   block approximates thinking duration.

These sub-components are useful for understanding *what* Claude spent time on
(thinking vs generating output vs tool chaining) but are not needed for the
headline metric.

### Sub-agent time

When Claude spawns sub-agents via the `Task` tool, the sub-agent's
`tool_result` includes:

```
<usage>total_tokens: 58308
tool_uses: 33
duration_ms: 195033</usage>
```

This time is already included in the parent turn's `turn_duration`. The
sub-agent metadata is useful for decomposition but not needed for the total.

### Fallback: active time estimation

If `turn_duration` entries are missing (older Claude Code versions), we can
estimate active time by summing inter-entry gaps that are below an idle
threshold (e.g., 5 minutes). This was the approach considered in the earlier
research but is inferior to `turn_duration` which is already computed for us.

## Metric 2: Documents generated

### What we mean

"Documents generated" = files that Claude created or substantially modified
during a session, with metadata about what was written and how much.

### Detection strategy: Write and Edit tool_use blocks

Scan `assistant` entries for `tool_use` content blocks where
`name` is `Write` or `Edit`.

**Write tool calls** contain:

```json
{
  "type": "tool_use",
  "name": "Write",
  "input": {
    "file_path": "/Users/bcope/git/performance/.claude/skills/enrich-sprint-data.md",
    "content": "... full file content (12,530 chars) ..."
  }
}
```

**Edit tool calls** contain:

```json
{
  "type": "tool_use",
  "name": "Edit",
  "input": {
    "file_path": "/Users/bcope/git/performance/docs/plan-qualitative-gaps.md",
    "old_string": "... text being replaced ...",
    "new_string": "... replacement text ..."
  }
}
```

### Classification logic

For each unique `file_path` touched by Write or Edit:

1. **Created**: first operation on this path in the session is a `Write`.
   Claude generated this file from scratch.
2. **Modified**: first operation is an `Edit`, or the file appeared in a
   prior `file-history-snapshot` with a v1 backup. Claude changed an
   existing file.
3. **Rewritten**: a `Write` to a path that already had content (v1 backup
   exists and is non-empty in file-history). Claude replaced the file
   entirely.

### Size metrics

For each file:

- **Write content size**: `len(input.content)` in characters
- **Edit delta size**: `len(input.new_string) - len(input.old_string)` per
  edit, summed across all edits to that file
- **Total edits**: count of Edit operations on the file
- **Final size**: from the last `file-history-snapshot` backup, or from the
  Write content if it was the last operation

### Supplementary: file-history snapshots

The final `file-history-snapshot` entry in a session provides the definitive
list of all files modified, including files changed via Bash commands (e.g.,
`cp`, `mv`, shell scripts) that don't appear as Write/Edit tool calls.

Use the snapshot's `trackedFileBackups` to:

- Catch files modified outside Write/Edit (rare but possible)
- Get version counts (number of times each file was backed up)
- Access the actual file content on disk at
  `~/.claude/file-history/{session-id}/{backupFileName}`

### Example from session c6d35017 (performance, Feb 17)

**3 files created (via Write):**

| File | Content size | Timestamp |
|---|---|---|
| `template-dir-sprint-name/calendar/.gitkeep` | 0 chars | 16:36:43 |
| `.claude/skills/enrich-sprint-data.md` | 12,530 chars | 22:59:29 |
| `docs/plan-claude-code-activity.md` | 11,188 chars | 15:27:13+1d |

**7 files modified (via Edit):**

| File | Edits | Net chars added |
|---|---|---|
| `.claude/skills/draft-sprint-notes.md` | 8 | +3,690 |
| `docs/plans/plan-claude-code-activity.md` | 8 | (renamed from above, then refined) |
| `docs/plan-qualitative-gaps.md` | 3 | +519 |
| `docs/plan-tighten-pipeline.md` | 2 | +418 |
| `work/sprint-notes/config.yaml` | 1 | +1,619 |
| `src/collect.py` | 2 | +303 |
| `CLAUDE.md` | 1 | +496 |

**Totals for the session:**

- 10 unique files touched
- 23,718 characters written (Write calls)
- ~7,045 net characters added (Edit calls)
- 3 documents created, 7 modified

### Filtering

Not all file operations are "documents generated." Filter out:

- `.gitkeep` files (empty placeholders)
- Files under `.claude/` (internal config, unless it's a skill file)
- Very small edits (< 50 chars) that are likely typo fixes

Configurable in `config.yaml` via include/exclude patterns.

## Implementation

### Changes to collect_activity.py

Add two new analysis functions alongside the existing `analyze_conversation`:

```
analyze_thinking_time(projects_path, project_path, session_id) -> dict
    Returns:
        total_thinking_ms: int        # sum of turn_duration entries
        turn_count: int               # number of human-initiated turns
        turns: list[dict]             # per-turn breakdown (optional)

analyze_documents(projects_path, project_path, session_id) -> dict
    Returns:
        files_created: list[dict]     # path, content_size, timestamp
        files_modified: list[dict]    # path, edit_count, net_chars_added
        total_write_chars: int
        total_edit_net_chars: int
```

These are called for each session during collection, and the results are
added to the session dict alongside the existing metrics.

### Output format changes to sessions.md

Update the per-session line to include thinking time:

```markdown
- **2026-02-17 02:27 UTC** (thinking: 16m 33s, 7 turns, 229 tool calls)
  Built sprint notes pipeline, enrichment skill, and Claude Code activity plan
  Tools: File operations: 115, Shell: 51, Agent: 39, ...
  Files: 3 created, 7 modified (30,763 chars written)
```

Update the summary section:

```markdown
## Summary

- **Total sessions:** 64
- **Total Claude thinking time:** ~4h 12m
- **Total turns:** 287
- **Projects touched:** 11
- **Files created:** 47
- **Files modified:** 83
- **Total characters written:** 482,091
```

### New output: documents.md

Write a separate `claude-code/documents.md` listing all files created and
modified across all sessions in the sprint:

```markdown
# Documents Generated (2026-02-13 to 2026-02-26)

## Created (47 files)

### performance (12 files)
- `.claude/skills/enrich-sprint-data.md` (12,530 chars) — 2026-02-19
- `docs/plan-claude-code-activity.md` (11,188 chars) — 2026-02-20
- ...

### ggdisburse-resources (28 files)
- `docs/migration/legacy-module-analysis/send-donor-reports.md` (8,421 chars) — 2026-02-18
- ...

## Modified (83 files)

### performance (7 files)
- `src/collect.py` — 2 edits, +303 chars
- ...
```

### Configuration

Add to the `claude_code` section in `config.yaml`:

```yaml
claude_code:
  # ... existing fields ...
  documents_output: "claude-code/documents.md"
  documents_filter:
    exclude_paths:
      - "*.gitkeep"
    min_write_chars: 50
```

### Implementation steps

| Step | What | Effort |
|---|---|---|
| 1 | Add `analyze_thinking_time` — scan for `turn_duration` system entries | Small |
| 2 | Add `analyze_documents` — scan for Write/Edit tool_use blocks | Small |
| 3 | Update `format_markdown` to include new metrics in sessions.md | Small |
| 4 | Add `format_documents_markdown` for the new documents.md output | Small |
| 5 | Wire documents_output into collect.py | Small |
| 6 | Update existing sessions for 2026-02-B by re-running collection | Small |

All steps can be done together. No changes to collect.py's orchestration
logic are needed beyond passing the documents output path.
