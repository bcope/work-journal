---
name: clean-insights
description: Clean a parsed insights report by making judgment calls on flagged content. Use when the user says "clean insights", "clean-insights", or "/clean-insights". Requires the parsing script to have been run first.
---

# Clean Insights Report

Transform a parsed Claude Code insights JSON file into a cleaned markdown document
suitable for use in sprint notes and progress briefs. The parsing script has already
classified items as `keep`, `drop`, `review`, or `stats` -- this skill handles the
judgment calls.

## Input

Read `work/shared/insights/parsed/{sprint}.json` where `{sprint}` is the argument
provided by the user (e.g., `2026-03-A`).

## Rules

### Classification handling

- **`keep` items** -- convert to markdown as-is.
- **`drop` items** -- exclude entirely. Do not mention them.
- **`review` items** -- read the content and decide:
  - **Drop** if entirely about personal projects with no transferable takeaway.
  - **Keep as-is** if actually work-relevant and the script just could not tell.
  - **Reframe** if there is a useful technique or learning embedded in personal
    project context. Extract the takeaway and frame it in terms of the skill,
    tool, or methodology -- not the personal domain. Example: "Built a reliable
    multi-phase automated research pipeline with structured output" rather than
    "Evaluated 12 companies using the evaluation skill."
- **`stats` items** -- include only if the metric is exceptional or trend-worthy.
  "Top tool was Read" is not interesting. Unusually high throughput, notable
  shifts in usage patterns, or strong outcome rates are worth a one-sentence
  callout.

### Content boundaries

Personal projects include: company evaluations, product category assessments,
audience profiles, conversation strategies, and any work in repos outside of
`~/git/`. Work projects include: anything referencing Jira, compliance,
disbursements, sprint notes, standup, developer productivity tooling, or repos
under `~/git/`.

When reframing, the goal is to capture **what was learned or built** without
exposing **what domain it was applied to**. Do not mention company names from
personal evaluations. Do not reference Obsidian or personal knowledge management
unless the technique is directly relevant to work tooling.

### Narrative and at-a-glance blocks

These always mix personal and work content. Rewrite them to:

- Remove personal project references entirely
- Preserve observations about work tools, workflows, and productivity
- Keep the tone factual and first-person-appropriate for sprint notes
- Be concise -- these are inputs to a draft, not the final document

## Output format

Save to `work/shared/insights/cleaned/{sprint}.md`:

```markdown
# Claude Code Insights: {sprint}

## Summary

(Rewritten at-a-glance content -- 2-4 sentences covering what worked,
what hindered, and any notable patterns. Work-relevant only.)

## Work Areas

- **Area Name** (~N sessions) -- Description.
- ...

## Accomplishments

- **Title** -- Description.
- ...

## Friction Points

- **Title** -- Description. Examples if useful.
- ...

## Usage Notes

(Only include this section if aggregate stats revealed something exceptional.
Otherwise omit the section entirely.)
```

## After saving

Print: "Cleaned insights saved. Ready for use by collect.py and draft skills."
