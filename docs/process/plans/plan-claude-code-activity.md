# Plan: Claude Code Activity as Sprint Notes Input

## Problem

Work done via Claude Code — building tools, writing scripts, researching
approaches, iterating on designs — often doesn't appear in Jira, GitHub, or
Google Docs. This repo itself is a good example: the entire sprint notes
pipeline was built through Claude Code conversations with no corresponding Jira
ticket. That work is invisible to the current collection process.

Claude Code stores structured activity data locally. Incorporating it into the
sprint notes pipeline captures a category of work that would otherwise require
manual recall.

## Data sources

### `~/.claude/stats-cache.json`

Aggregate metrics, pre-computed by Claude Code.

```json
{
  "dailyActivity": [
    { "date": "2026-02-09", "messageCount": 1701, "sessionCount": 6, "toolCallCount": 348 }
  ],
  "dailyModelTokens": [
    { "date": "2026-02-09", "tokensByModel": { "claude-opus-4-6": 35363 } }
  ],
  "modelUsage": { "claude-opus-4-6": { "inputTokens": 129216, "outputTokens": 260424, ... } },
  "totalSessions": 59,
  "totalMessages": 18353,
  "hourCounts": { "10": 6, "11": 5, "14": 5, ... },
  "longestSession": { "sessionId": "...", "duration": 96027011, "messageCount": 859 }
}
```

**Useful fields:**

- `dailyActivity` — sessions, messages, and tool calls per day. Filter by sprint
  date range for sprint-scoped metrics.
- `hourCounts` — hour-of-day distribution (UTC). Shows working patterns.
- `totalSessions`, `totalMessages` — overall volume.
- `longestSession` — duration in ms, message count.

**Limitations:**

- The cache covers a rolling window (currently Feb 9-16). Assume at least two
  weeks of data will be present. The collection script should copy the file (or
  the relevant date range) to the sprint directory so the data is preserved even
  if the cache rolls forward.
- No per-project breakdown — all projects are aggregated together.
- `costUSD` is 0 (Pro plan), so cost analysis isn't possible from this source.

### `~/.claude/history.jsonl`

One line per session start. 618 entries as of Feb 20, covering Jan 6 to Feb 20.

```json
{
  "display": "I have to write a quarterly progress brief...",
  "timestamp": 1767755174100,
  "project": "/Users/bcope/git/performance",
  "sessionId": "cf803b52-172b-4c22-91e2-97b198b6f5c5"
}
```

**Useful fields:**

- `display` — first user message. Shows intent and what was being worked on.
- `timestamp` — ms epoch. Filterable by sprint date range.
- `project` — absolute path to working directory. Maps to repo/project.
- `sessionId` — links to the full conversation transcript.

**Key property:** This is the session index. It tells you *what* was worked on
and *when*, scoped by project. Filtering by date range and project path gives a
session inventory for any sprint.

**Current distribution (work projects, Feb 9-20):**

| Project path | Sessions | Conversation entries |
|---|---|---|
| `git/ai-toolkit` | 60 | 2,550 |
| `git/ca-ab-488-data-etl` | 51 | 5,219 |
| `git/ggdisburse-resources` | 99 | 4,966 |
| `git/jira-admin` | 21 | 376 |
| `git/performance` | 27 | 1,768 |
| `git/redesignation` | 17 | 433 |
| `git/atlas` | 2 | 34 |
| `git/work` | 5 | 53 |

### `~/.claude/projects/{project-slug}/*.jsonl`

Full conversation transcripts. One JSONL file per session, one line per event.

Entry types:

- **`user`** — user messages with `message.content` (text), `timestamp`,
  `sessionId`, `cwd`, `gitBranch`
- **`assistant`** — assistant responses. `message.content` is an array of blocks;
  blocks with `type: "tool_use"` include `name` (tool name) and `input`
- **`progress`** — tool execution progress events
- **`system`** — system events (hook execution, stop reasons)
- **`file-history-snapshot`** — file state snapshots

**Useful extractions:**

- **Session duration:** gap between first and last timestamp in the file
- **Tool usage:** count tool_use blocks by `name` per session. Reveals whether
  the session was coding (Write/Edit), research (Read/Grep/Glob), or MCP
  integration (mcp__* tools)
- **User messages:** the sequence of user prompts tells the story of what was
  accomplished, similar to commit messages
- **Files touched:** from file-history-snapshot entries and Write/Edit tool inputs

## What to extract

### Tier 1: Session inventory (low effort, high value)

For each sprint, produce a list of Claude Code sessions scoped to work projects
in the date range. For each session:

- Project (repo name, mapped to readable name)
- First prompt (from `history.jsonl` `display` field)
- Timestamp
- Duration (from conversation file first/last timestamps)
- Message count (user + assistant entries in conversation file)
- Tool call count (tool_use blocks in assistant entries)

This is the "what did I use Claude for this sprint?" view. It surfaces work that
has no Jira ticket, like tooling, automation, and exploratory analysis.

**Output:** `work/sprint-notes/{sprint}/claude-code/sessions.md`

```markdown
# Claude Code Sessions

**Sprint dates:** 2026-02-17 to 2026-02-28

## By project

### Performance (git/performance)
- **2026-02-17 11:27** (4h 12m, 53 messages, 44 tool calls)
  Updated MCP server config and restructured Jira query categories
- **2026-02-19 17:47** (2h 30m, 28 messages, 31 tool calls)
  Created enrichment skill for sprint data pipeline

### CA AB 488 (git/ca-ab-488-data-etl)
- ...

## Summary
- **Total sessions:** 12
- **Total duration:** ~18 hours
- **Projects touched:** 4
```

Session descriptions should be short summaries of intent, not direct quotes from
prompts. If a direct quote is included for a specific reason, mark it explicitly
as such.

### Tier 2: Tool usage patterns (medium effort, medium value)

Aggregate tool calls by category per project per sprint. Categories:

- **File operations:** Read, Write, Edit, Glob, Grep
- **Shell:** Bash
- **MCP - Jira:** mcp__jira__*
- **MCP - Google:** mcp__gdocs__*
- **MCP - Miro:** mcp__miro__*
- **Agent:** Task, TaskCreate, TaskUpdate
- **Other:** WebSearch, WebFetch, etc.

This shows the *nature* of work. A session dominated by MCP Jira calls is
different from one dominated by Write/Edit. Patterns across a sprint reveal
whether the period was more about building, researching, or integrating.

**Output:** Append to `claude-code/sessions.md` or separate
`claude-code/tool-usage.md`

### Tier 3: Conversation summarization (higher effort, highest value)

For key sessions (long duration, high tool count, or touching important
projects), extract user messages and produce a narrative summary of what was
accomplished.

This is inherently qualitative — it requires reading conversation content and
synthesizing. Two approaches:

**Option A: Extract user messages only.** Save the sequence of user prompts from
a session as a readable log. The draft skill can read these as context.

**Option B: Summarize during enrichment.** The `/enrich-sprint-data` skill
reads conversation files for sessions in the sprint date range and writes
summaries. This happens alongside Gmail/Calendar/Docs enrichment.

Option A is simpler and deterministic (a script can do it). Option B produces
better summaries but adds to enrichment time. In either case, the output should
summarize rather than quote — avoid including verbatim user prompts in the
analysis output unless there is a specific reason, and mark any direct quotes
explicitly.

### What to skip

- **Personal project data.** Filter to `~/git/` paths only (or a configurable
  list of work directories).
- **Token cost analysis.** `costUSD` is 0 on the Pro plan.
- **Exact timeline reconstruction.** Timestamps are precise enough for
  duration estimates but not for "I spent 20 minutes on this specific subtask."
- **Assistant message content.** Too verbose for collection. If specific
  conversation content is needed, the enrichment skill can read it selectively.
- **Verbatim prompt quoting.** Analysis output should summarize intent, not
  reproduce user prompts. Direct quotes only when specifically justified and
  clearly marked.

## Implementation

### Option 1: Python script in `src/` (fits existing pattern)

A new `src/claude_code/collect_activity.py` that:

1. Copies `~/.claude/stats-cache.json` to
   `claude-code/stats-cache-snapshot.json` in the sprint directory (preserving
   the full file — it's small, and having the complete snapshot avoids guessing
   which fields will be useful later)
2. Reads `~/.claude/history.jsonl` and extracts entries for work projects in the
   sprint date range. Writes the filtered entries to
   `claude-code/history-excerpt.jsonl`, preserving the original JSONL format
3. For each session in the excerpt, reads the conversation JSONL to extract
   duration, message count, tool counts
4. Writes `claude-code/sessions.md` to the sprint directory (summarized, not
   verbatim)

Called from `collect.py` alongside the Jira/GitHub/git steps.

**Pros:** Deterministic, fast, runs with `collect.py`.
**Cons:** Can only do Tier 1 and 2. Summarization (Tier 3) needs the AI.

### Option 2: Enrichment skill phase

Add a "Claude Code activity" phase to `/enrich-sprint-data`. The skill reads
`history.jsonl`, filters by date range, reads conversation files, and produces
both the session inventory and narrative summaries.

**Pros:** Can do all three tiers. Summaries are high quality.
**Cons:** Slower, requires running enrichment.

### Recommended: Both

- **Tier 1 + 2 via script** — add to `collect.py`. Session inventory and tool
  usage are mechanical extraction, no AI needed.
- **Tier 3 via enrichment** — add a phase to the enrich skill for conversation
  summarization. Only runs when enrichment is invoked.

### Pipeline integration

The session inventory becomes another input to `draft-sprint-notes`:

```
collect.py
  ├── jira/ (sprint issues by category)
  ├── github/ (PRs)
  ├── git/ (commits)
  └── claude-code/ (sessions, tool usage)    ← new

/enrich-sprint-data
  ├── email/ (Gmail highlights)
  ├── calendar/ (meeting activity)
  ├── google-docs/ (doc summaries)
  ├── jira/ (issue details)
  └── claude-code/ (conversation summaries)  ← new

/draft-sprint-notes
  └── reads all of the above
```

Update `draft-sprint-notes.md` to read `claude-code/sessions.md` and
`claude-code/summaries.md` (if enrichment was run) as additional context for
identifying accomplishments that don't appear in Jira.

### Configuration

Add to `work/sprint-notes/config.yaml`:

```yaml
claude_code:
  stats_cache_path: ~/.claude/stats-cache.json
  history_path: ~/.claude/history.jsonl
  projects_path: ~/.claude/projects
  work_dirs:
    - ~/git
  output: "claude-code/sessions.md"
  raw_outputs:
    stats_snapshot: "claude-code/stats-cache-snapshot.json"
    history_excerpt: "claude-code/history-excerpt.jsonl"
```

The `work_dirs` list controls which project paths are considered "work" vs.
personal. Only sessions under these directories are included. Raw source files
are copied to the sprint directory so the data is preserved for re-analysis
even if the upstream files roll forward or change.

### Template directory

Add `claude-code/.gitkeep` to `work/sprint-notes/template-dir-sprint-name/`.

## Implementation order

| Step | What | Effort |
|---|---|---|
| 1 | `src/claude_code/collect_activity.py` — copy raw files + Tier 1 session inventory | Small |
| 2 | Wire into `collect.py` and add config | Small |
| 3 | Add Tier 2 tool usage breakdown | Small |
| 4 | Add enrichment phase for Tier 3 conversation summaries | Medium |
| 5 | Update `draft-sprint-notes.md` to read claude-code inputs | Small |

Steps 1-3 can be done together. Step 4 depends on the enrich skill working
well for other phases first. Step 5 is a small edit once the data exists.

## Resolved decisions

- **Stats cache longevity.** Assume at least two weeks of data will be present.
  The collection script copies the entire `stats-cache.json` to the sprint
  directory as a snapshot. The file is small, and preserving the whole thing
  avoids premature decisions about which fields matter.
- **Session boundaries.** Sessions are somewhat arbitrary and the optimal
  interpretation isn't clear yet. The collection script copies the relevant
  portion of `history.jsonl` to the sprint directory in its original JSONL
  format, preserving the raw data. How sessions are grouped or interpreted can
  be iterated on later without re-collecting.
- **Privacy/quoting.** All analysis output (sessions.md, summaries, draft notes)
  should summarize intent rather than reproduce verbatim prompts. Direct quotes
  are only included when there is a specific reason, and must be clearly marked
  as quotes. This applies to all tiers — Tier 1 session descriptions are
  summaries, not first-prompt excerpts.
