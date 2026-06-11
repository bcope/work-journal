# Between-Sprints Data Collection

Extend sprint notes collection to capture work done between the previous
sprint's close and the current sprint's start. This work currently falls
through the cracks.

## Approach

Mirror the existing pattern for non-sprint work: separate data files,
separate category in analysis, own section in the draft.

## Changes

### 1. `src/work_journal/jira/query_sprint_info.py`

Add `find_previous_sprint(session, board_id, current_sprint)` that returns the
most recent closed sprint ending before the current sprint's start. Sorts
closed sprints by `endDate` descending and picks the first one before
`current_sprint["startDate"]`.

### 2. `src/work_journal/collect.py`

After resolving the current sprint:

- Call `find_previous_sprint()` to get the prior sprint
- Extract `prior_sprint_end` from its `completeDate` (the actual close time,
  not planned `endDate`)
- Fall back to `endDate` if `completeDate` is absent (sprint was never formally
  closed)
- Add `prior_sprint_end` to JQL template variables
- Save prior sprint info to `jira/prior-sprint-info.json`

Collect between-sprints data separately (gap = `prior_sprint_end` to
`start_date`):

- GitHub PRs: `github/between-sprints-prs.md`
- Git commits: `git/between-sprints-commit-log.md`
- Claude Code: `claude-code/between-sprints-sessions.md`

Skip between-sprints collection if no prior sprint found or gap is zero/negative.

### 3. `config/sprint-notes.yaml`

Add JQL query:

```yaml
between_sprints_completed:
  description: "Issues resolved between previous sprint close and current sprint start"
  jql: "assignee = {account_id} AND statusCategory = Done AND resolved >= \"{prior_sprint_end}\" AND resolved < \"{start_date}\""
  output: "jira/between-sprints-completed.json"
```

### 4. `.claude/skills/draft-sprint-notes/SKILL.md`

- Add `jira/between-sprints-completed.json` and the between-sprints GitHub/git/
  Claude Code files to the data loading list
- Add `jira/prior-sprint-info.json` to the metadata files
- Add "Between sprints" as a category in Phase 3 analysis alongside planned,
  added, and non-sprint
- Add guidance: this section appears after the main sprint themes, titled
  "Between Sprints" with a date range subtitle

### 5. `docs/TODO.md`

Remove the item about extending scraping to prior sprint close.
