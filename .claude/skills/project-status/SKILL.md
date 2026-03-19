---
name: project-status
description: Generate a project status update from collected GitHub, Jira, and Calendar data. Use when the user says "project status", "project update", or "/project-status".
---

# Skill: Project Status Update

## When to use

Use this skill when the user asks to generate a project status update. The
user will specify a project name that corresponds to a config file in
`work/project-status/project-configs/` in the work-journal repo.

## Arguments

- **project** (required): Project config name (e.g., `ggdisburse` -- matches `project-configs/ggdisburse.yaml`)
- **--since YYYY-MM-DD** (optional): Start date for activity. If omitted, uses the project's `default_days` setting (overview mode).
- **--audience slt|engineering** (optional): Drafting lens. Defaults to `engineering`.

## Process

### Phase 1: Collect data

Run the collection script:

```bash
uv run python3 src/work_journal/collect_project_status.py {project} --since {since}
```

Or without `--since` for overview mode:

```bash
uv run python3 src/work_journal/collect_project_status.py {project}
```

The script prints the run directory path. Note it for Phase 2.

### Phase 2: Load collected data

Read all files from the run directory
(`work/project-status/{project}/{date}[-n]/`):

1. **`run.yaml`** -- Run metadata: project name, mode, date range, generation timestamp. Cite these dates in the draft.
2. **`jira/*.json`** -- Jira issues from each configured query. The query name (filename stem) maps to an audience mode or "default".
3. **`github/prs.md`** -- GitHub PR activity across the project's repos. All contributors, not just one person.
4. **`calendar/events.json`** -- Calendar events matching project keywords. Only present in date-range mode.

If a file is missing, note it and continue with available data.

### Phase 3: Filter and analyze

#### Select the right Jira query results

If the `--audience` flag was provided, prefer the Jira query matching that
audience (e.g., `jira/slt.json` for `--audience slt`). Fall back to
`jira/default.json` if no audience-specific file exists.

#### Filter calendar events

Review `calendar/events.json` and drop events that are clearly unrelated to
the project despite matching keywords. For example, if a keyword is
"migration" and an event is "Bird Migration Documentary Watch Party," drop it.
Keep events where:

- The title clearly relates to the project
- Attendees overlap with contributors in the Jira/GitHub data
- The event description references project artifacts

Flag recurring events as lower signal than non-recurring ones.

#### Identify themes

Group the data by theme or workstream. Look for:

- Related Jira issues and PRs that form a coherent narrative
- Milestones reached or approaching
- Blockers and risks
- Decisions made (visible in PR merges, issue transitions, calendar meetings)

### Phase 4: Draft

Read the project config to get the `audience_modes` tone guidance for the
selected audience.

#### SLT / Executive audience

Write a concise status update. Structure:

```markdown
# {today} - {Project Name} -- Status Update

**Period:** {since} to {until}
**Updated:** {today}

## Summary

2-3 sentence executive summary: where the project stands, key milestone
reached or approaching, top risk if any.

## Key Progress

### Milestone or outcome headline

1-2 sentence description of what was accomplished and why it matters.
Business impact, not technical detail.

### Another milestone

...

## Risks & Blockers

- Risk description and mitigation status
- ...

## Upcoming

- What's next in the near term
- Key decisions pending
```

Guidelines:

- No PR links or Jira issue keys unless they represent major milestones
- Lead with outcomes and business impact
- Keep the whole document under 1 page
- Use specific numbers when available

#### Engineering audience

Write a detailed status update. Structure:

```markdown
# {today} - {Project Name} -- Status Update

**Period:** {since} to {until}
**Updated:** {today}

## Summary

2-3 sentence summary of project status and key activity.

## {Workstream or Theme}

### What happened

Narrative paragraphs with inline links to Jira issues
(`$JIRA_URL/browse/{KEY}`), GitHub PRs, and other
artifacts.

Cover:

- PRs merged and their significance
- Issues completed, in progress, blocked
- Technical decisions made
- Calendar meetings that drove decisions

### Status

Current state of this workstream: on track, at risk, blocked.

## {Another Workstream}

...

## Open Issues & Blockers

| Issue | Status | Owner | Notes |
| --- | --- | --- | --- |
| [KEY-123](url) | Blocked | @person | Waiting on X |

## Upcoming

- Next steps with expected dates if known
- PRs in review
- Decisions needed
```

Guidelines:

- Include Jira links and PR links throughout
- Attribute work to contributors where visible
- Be specific about what's blocked and why
- Include a table for open blockers

### Phase 5: Save

Save the draft to `{run_dir}/draft.md`.

Tell the user:

1. The draft is at `{run_dir}/draft.md`
2. Edit as needed, then upload via:
   `node $MD_TO_GDOC_SCRIPT upload {run_dir}/draft.md --title "{Project Name} Status Update {date}" --folder "{upload_folder}"`
   where `{upload_folder}` comes from the project config's `google_drive.upload_folder`.
   If `upload_folder` is empty, omit the `--folder` flag.

## Tips

- For the SLT audience, less is more. Executives want to know: is this on
  track, what's the top risk, what do I need to do.
- For the engineering audience, thoroughness matters. Include links to
  everything so readers can dig deeper.
- If the Jira data is sparse but GitHub shows lots of PR activity, lean on
  the GitHub data for the narrative.
- If calendar events show a key meeting, mention the decision or outcome from
  that meeting if it's visible in subsequent Jira/GitHub activity.
- Cross-reference: if a PR references a Jira issue, connect them in the
  narrative. If a calendar meeting preceded a burst of PR activity, note the
  connection.
- The `project_names` mapping in `config/shared.yaml` translates
  Jira project keys to readable names.
