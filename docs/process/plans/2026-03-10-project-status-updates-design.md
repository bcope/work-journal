# Project Status Updates — Design

## Purpose

A reusable pipeline for generating project status update documents. Each
"project" is a cross-contributor initiative tracked across GitHub repos, Jira
issues, and calendar events. The pipeline collects raw data, then drafts a
markdown report tailored to a target audience (SLT/executive or engineering).

## Audience Modes

- **SLT** — Outcomes, milestones, risks, decisions needed. Minimal links.
  Short and high-level.
- **Engineering** — Detailed PR activity per repo, issue status breakdowns,
  blockers, technical decisions, inline links throughout.

Same underlying data, different drafting lens.

## Invocation Modes

- **Date-range mode** — `--since YYYY-MM-DD` collects activity from that date
  to today.
- **Overview mode** — No `--since` flag. GitHub uses `default_days` from the
  project config. Jira pulls all matching issues regardless of date. Calendar
  is skipped.

## Directory Structure

```text
work/project-status/
├── config.yaml                          # repo-level defaults
├── project-configs/
│   ├── your-repo-name.yaml
│   └── bsr.yaml
└── your-repo-name/
    └── 2026-03-10/
        ├── run.yaml                     # invocation metadata + resolved dates
        ├── jira/
        │   └── issues.json
        ├── github/
        │   └── prs.md
        ├── calendar/
        │   └── events.json
        └── draft.md
```

If multiple runs happen on the same date, directories get a `-2`, `-3` suffix.

## Project Configuration

Per-project config at `work/project-status/project-configs/<name>.yaml`:

```yaml
name: "GGDisburse Migration"
description: "Migration from legacy disbursement system"

github:
  repos:
    - your-org/your-repo-name
    - your-org/your-repo-name-legacy
  default_days: 30

jira:
  queries:
    default: "project = GGDM ORDER BY updated DESC"
    slt: "project = GGDM AND type in (Epic, Story) ORDER BY priority DESC"
    engineering: "project = GGDM ORDER BY updated DESC"

calendar:
  calendar_ids:
    - primary
  keywords:
    - "GGDisburse"
    - "disbursement migration"

audience_modes:
  slt:
    tone: "executive summary — outcomes, risks, decisions needed"
  engineering:
    tone: "detailed — PRs, issue breakdowns, blockers, technical decisions"
```

Repo-level defaults (Jira credentials, GitHub org, Google Drive settings) live
in `work/project-status/config.yaml`, mirroring the sprint notes pattern.

## Components

| Component | Location | Purpose |
| --- | --- | --- |
| Repo-level config | `work/project-status/config.yaml` | Shared defaults |
| Project configs | `work/project-status/project-configs/<name>.yaml` | Per-project definition |
| Collection script | `src/collect_project_status.py` | Orchestrates data collection |
| Calendar script | `src/calendar/query_events.py` | Queries Google Calendar API |
| Run output | `work/project-status/<project>/<date>[-n]/` | Collected data + draft |
| Drafting skill | `~/git/ai-toolkit/claude-code/skills/project-status/SKILL.md` | Invokes collection, drafts markdown |

## Collection Script

`src/collect_project_status.py`

```bash
# Date-range mode
uv run python3 src/collect_project_status.py your-repo-name --since 2026-02-01

# Overview mode
uv run python3 src/collect_project_status.py your-repo-name
```

Steps:

1. Load `work/project-status/config.yaml` and the project config.
2. Resolve dates from `--since` or `default_days`.
3. Create run directory (with `-n` suffix if needed).
4. Write `run.yaml` with parameters and resolved dates.
5. Collect GitHub PRs per repo via `gh` CLI (reuses `src/github/query_github_prs.py`).
6. Collect Jira issues via JQL (reuses `src/jira/query_issues.py`).
7. Collect calendar events via `src/calendar/query_events.py`.

Calendar is skipped in overview mode.

## Calendar Script

`src/calendar/query_events.py` — new script that queries the Google Calendar
API directly using OAuth credentials from the gdocs-mcp setup. Accepts
calendar IDs, keywords, and a date range. Returns matching events as JSON.

## Drafting Skill

Located at `~/git/ai-toolkit/claude-code/skills/project-status/SKILL.md`.

Invocation:

```text
/project-status your-repo-name --since 2026-02-01 --audience slt
/project-status your-repo-name --audience engineering
/project-status your-repo-name
```

The skill:

1. Parses arguments (project name required, `--since` and `--audience` optional).
2. Runs `collect_project_status.py` via shell.
3. Reads all files from the run directory.
4. Filters calendar events — drops results clearly unrelated to the project.
5. Drafts `draft.md` tailored to audience mode.
6. Cites the date range covered and generation timestamp in the draft.

The skill does not upload to Google Docs. After editing the draft, use the
existing `md-to-gdoc.js` pipeline.

## Workflow

1. Invoke `/project-status your-repo-name --since 2026-02-01 --audience slt`
2. Collection script gathers data into `work/project-status/your-repo-name/2026-03-10/`
3. Skill reads data, filters calendar noise, drafts `draft.md`
4. Edit `draft.md` as needed
5. Upload via `md-to-gdoc.js`

## Not in Scope

- MCP enrichment phase (email threads, Google Docs summaries)
- Automatic upload to Google Docs
- Cross-project rollup reports

These can be added later following the sprint notes enrichment pattern.
