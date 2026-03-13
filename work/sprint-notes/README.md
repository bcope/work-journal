# Sprint Notes

Automated workflow for collecting data and drafting biweekly sprint notes.

## Quick start

```bash
# 1. Create sprint directory and set the sprint name
cp -r work/sprint-notes/template-dir-sprint-name work/sprint-notes/2026-02-A
# Edit work/sprint-notes/2026-02-A/sprint.yaml — set sprint_name

# 2. Collect all data (derives dates from sprint API automatically)
uv run python3 src/collect.py 2026-02-A

# 3. Optionally add manual notes
#    Edit work/sprint-notes/2026-02-A/manual-notes.md

# 4. Draft sprint notes using the Claude skill
#    /draft-sprint-notes 2026-02-A
```

## Configuration

### Repo-level config (`work/sprint-notes/config.yaml`)

Set once, applies to all sprints. Contains:

- **Jira:** account ID, board ID, JQL query templates with placeholders
- **GitHub:** org name, output format
- **Git:** repos directory, author name
- **Project names:** mapping from Jira project keys to readable names

JQL templates support these placeholders (resolved automatically from the sprint):

- `{account_id}` — Jira account ID from config
- `{start_date}` — Sprint start date (YYYY-MM-DD)
- `{end_date}` — Sprint end date (YYYY-MM-DD)
- `{sprint_id}` — Jira sprint ID

To add a new Jira query, add a block under `jira.queries` in the config:

```yaml
jira:
  queries:
    my_new_query:
      jql: "reporter = '{account_id}' AND created >= '{start_date}'"
      output: "jira/reported-issues.json"
```

### Sprint-level config (`work/sprint-notes/{sprint}/sprint.yaml`)

One field — the sprint name used to look up dates via the Jira API:

```yaml
sprint_name: "2026-02-A-Product-February"
```

## Directory structure

```
work/
  sprint-notes/
    config.yaml                   # Repo-level config (set once)
    template-dir-sprint-name/     # Copy this to create a new sprint
      sprint.yaml                 # Sprint config (set sprint_name)
      jira/                       # Jira data
      github/                     # GitHub PR activity
      git/                        # Local git commit logs
      google-docs/                # Reserved for future automation
      email/                      # Reserved for future automation
      manual-notes.md             # Starter file for manual context
    2026-02-A/                    # Example sprint directory
      sprint.yaml
      jira/
        sprint-info.json          # Sprint metadata (dates, name, state)
        assigned-issues.json      # Issues assigned to you
        sprint-issues.json        # All issues in the sprint
      github/
        prs.md                    # PRs authored and reviewed
      git/
        commit-log.md             # Commits by author
      manual-notes.md             # User-curated notes
      draft.md                    # Output from the drafting skill
    README.md
```

## Data collection

### Automated (via collect.py)

The collect script reads both config files, resolves the sprint name to dates,
and runs all collection steps:

```bash
# Collect everything
uv run python3 src/collect.py 2026-02-A

# Preview what would be collected without running queries
uv run python3 src/collect.py 2026-02-A --dry-run
```

The script will:

1. Resolve the sprint name to dates and ID via the Jira Agile API
2. Run each configured JQL query (templated with dates/account ID)
3. Search GitHub for authored and reviewed PRs
4. Scan local git repos for commits
5. Report what was collected

### Manual fallback

Individual helper scripts can still be run directly:

```bash
# Sprint info
uv run python3 src/jira/query_sprint_info.py --sprint-name "2026-02-A" --pretty

# Jira issues (use account ID from $JIRA_ACCOUNT_ID env var)
uv run python3 src/jira/query_issues.py \
  "assignee = '$JIRA_ACCOUNT_ID' AND updated >= '2026-01-30' AND updated <= '2026-02-12'" \
  --pretty

# GitHub PRs
uv run python3 src/github/query_github_prs.py \
  --since 2026-01-30 --until 2026-02-12 --org $GITHUB_ORG --format markdown

# Git commits
uv run python3 src/git/query_git_log.py \
  --since 2026-01-30 --until 2026-02-12 --repos-dir ~/git
```

### Manual notes

Edit `work/sprint-notes/{sprint}/manual-notes.md` to add context not captured by
automated collection:

- Slack message links showing impact or sharing results
- Notable email threads
- Key meeting decisions or 1:1 discussion points
- Context that makes an accomplishment more meaningful

## Drafting

Use the Claude skill to analyze collected data and produce a draft:

```
/draft-sprint-notes 2026-02-A
```

The skill reads all collected data, enriches via MCP (Google Docs, Jira issue
details), categorizes work into themes, and saves a draft to
`work/sprint-notes/{sprint}/draft.md`.

## Scripts reference

| Script | Location | Purpose |
|---|---|---|
| `collect.py` | `src/` | Run all collection steps from config |
| `query_sprint_info.py` | `src/jira/` | Sprint metadata (dates, name, state) |
| `query_issues.py` | `src/jira/` | Jira issues via JQL query |
| `query_github_prs.py` | `src/github/` | GitHub PRs authored and reviewed |
| `query_git_log.py` | `src/git/` | Local git commits by author |

## Dependencies

- **Python packages:** `requests`, `pyyaml` (managed via `uv`)
- **Jira scripts:** `JIRA_USER` and `JIRA_API_TOKEN` env vars
- **GitHub script:** `gh` CLI (authenticated via `gh auth login`)
- **Git script:** `git` CLI (no auth needed, local only)
- **Drafting skill:** Claude Code with MCP servers configured (Google Docs, Jira)
