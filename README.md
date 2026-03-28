# Work Journal

Tools and workflows for tracking, collecting, and summarizing work output — sprint notes, quarterly progress briefs, and OKRs.

## What this repo does

- **Collects** data from Jira, GitHub, and local git repos into structured sprint directories
- **Drafts** sprint notes by analyzing collected data and enriching it via Google Docs and Jira MCP tools
- **Drafts** quarterly progress briefs from Jira exports and authored documents
- **Stores** OKRs and progress brief artifacts for reference

## Directory structure

```
src/                              # Python scripts
  collect.py                      # Orchestrates all data collection for a sprint
  jira/
    query_sprint_info.py          # Sprint metadata via Jira Agile API
    query_issues.py               # Jira issues via JQL
    parse_jira_csv.py             # Parse Jira CSV exports
  github/
    query_github_prs.py           # GitHub PRs via gh CLI
  git/
    query_git_log.py              # Local git commits
work/                             # Working data and outputs
  shared/                         # Cross-process inputs
    insights/                     # Claude Code /insights reports
      raw/                        # Raw HTML (manual copy)
      parsed/                     # Classified JSON (from parse script)
      cleaned/                    # Cleaned markdown (from /clean-insights skill)
  sprint-notes/                   # Biweekly sprint notes (see work/sprint-notes/README.md)
    config.yaml                   # Repo-level collection config
    template-dir-sprint-name/     # Template for new sprints
    2026-02-A/                    # Example sprint with collected data + draft
  progress-briefs/                # Quarterly self-assessments
    template-dir-quarter/         # Template for new quarters
    2025-Q4/                      # Example quarter
  okrs/                           # OKR tracking
docs/                             # Plans and design documents
.claude/
  skills/                         # Claude Code skills
    draft-sprint-notes.md         # Analyze collected data and draft sprint notes
    draft-progress-brief.md       # Draft quarterly progress brief from evidence
```

## Sprint notes workflow

```bash
# 1. Create sprint directory
uv run python3 src/work_journal/scaffold.py sprint 2026-02-B \
  --var sprint_name="2026-02-B-Product-February"

# 2. Prepare insights report (collect.py requires this)
#    Run /insights in Claude Code, then:
cp ~/path/to/insights-report.html work/shared/insights/raw/2026-02-B.html
uv run python3 src/work_journal/insights/cli.py 2026-02-B
#    Then run /clean-insights 2026-02-B in Claude Code

# 3. Collect data
uv run python3 src/work_journal/collect.py 2026-02-B

# 4. Add manual context (Slack links, meeting notes, etc.)
#    Edit work/sprint-notes/2026-02-B/manual-notes.md

# 5. Draft sprint notes via Claude skill
#    /draft-sprint-notes 2026-02-B
```

See `work/sprint-notes/README.md` for full documentation.

## Setup

### Python

Requires Python 3.12+. Dependencies managed via [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

### Environment variables

| Variable | Used by | Purpose |
|---|---|---|
| `JIRA_USER` | Jira scripts | Jira account email |
| `JIRA_API_TOKEN` | Jira scripts | Jira API token |

### External tools

- **`gh` CLI** — GitHub PR queries (authenticate via `gh auth login`)
- **`git` CLI** — local commit log scanning
- **Claude Code MCP servers** — Google Docs and Jira (used by drafting skills)
