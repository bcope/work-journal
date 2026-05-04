---
name: draft-progress-brief
description: Draft a quarterly progress brief or performance review self-assessment from sprint notes, OKRs, and work artifacts. Use when the user says "draft progress brief", "progress brief", or "/draft-progress-brief".
---

# Skill: Draft Progress Brief

## When to use

Use this skill when the user asks to draft a quarterly progress brief, performance review, or similar self-assessment document.

## Prerequisites

Before running this skill, the user should have:

1. Scaffolded the progress brief directory: `uv run python3 src/work_journal/scaffold.py progress-brief {YEAR}-{QUARTER}`
2. Collected the quarterly rollup: `uv run python3 src/work_journal/collect_progress_brief.py {YEAR}-{QUARTER}`
3. Copied form PDF screenshots to `work/progress-briefs/{YEAR}-{QUARTER}/format/`

If the rollup hasn't been collected yet, offer to run the collection script first.

## Process

### Phase 1: Read the form questions

Read the form PDFs in `work/progress-briefs/{YEAR}-{QUARTER}/format/` to understand what questions need to be answered and any specific instructions.

### Phase 2: Read the evidence

Read sources in this priority order:

1. **`work/progress-briefs/{YEAR}-{QUARTER}/rollup.md`** -- Primary input. Contains accomplishments organized by project with value category annotations, impact metrics, summary statistics, and key documents. This is the most important source.
2. **`work/progress-briefs/{YEAR}-{QUARTER}/impact-metrics.yaml`** -- Direct access to quantified outcomes (percentages, dollar amounts, time savings) extracted during sprint note drafting. Lead with these.
3. **Individual sprint notes** -- Read `work/sprint-notes/{sprint}/final.md` or `draft.md` for sprints in the quarter when the rollup summary is too compressed and you need the full narrative for a key accomplishment. The rollup tells you which sprints have which accomplishments; dip into the full notes for richer detail.
4. **Cleaned insights reports** -- files in `work/shared/insights/cleaned/` named `{start}-to-{end}.md`. Read each file whose date range overlaps any sprint in the quarter (the /insights tool reports on a rolling 30-day window, so files often span multiple sprints). Treat these as **pattern-level commentary** about working style, productivity trends, and friction across the quarter -- not as sprint-specific accomplishment evidence. Missing files are expected for periods before this feature was added.
5. **Supplementary documents** -- `work/progress-briefs/{YEAR}-{QUARTER}/docs/`. Authored memos, investigation notes, and other artifacts that demonstrate depth of work. Note: some files may contain embedded base64 images making them very large. Use `cut -c1-2000` via Bash to truncate long lines when the Read tool fails.
6. **Jira CSV exports** -- `work/progress-briefs/{YEAR}-{QUARTER}/jira-issues/`. Reference for total issue counts and project distribution. No longer the primary source; the rollup has this data pre-aggregated.

### Phase 3: Synthesize into form answers

Use the evidence to answer each form question. Key principles:

**Organize by business value, not by project.** Use the value category annotations from the rollup to group accomplishments into themes that matter to the audience:

- Process improvements and efficiency gains
- Risk reduction and compliance
- Stakeholder enablement and leadership
- Knowledge capture and documentation
- Revenue enablement and strategic work

**Lead with impact metrics.** Every major theme should open with a quantified outcome when available. Prefer "75% reduction in FXecute repair queue time" over "implemented payment file code changes."

**Show sustained effort and momentum.** Use the rollup's project-by-sprint view to demonstrate consistent delivery across the quarter, not just isolated wins.

**Reference leadership evidence.** The rollup's Key Documents Produced section and enrichment highlights show stakeholder coordination, documents authored, and decisions driven. Use these as evidence of initiative and cross-functional work.

**Be honest and concise.** Use bullet points for clarity (the forms request this). Focus on impactful accomplishments, challenges, and learnings.

Additional guidelines:

- Highlight completed goals, major deliverables, and wins
- Include collaboration, teamwork, and leadership examples
- Share how challenges or setbacks were handled
- Note skills or knowledge developed
- Quantify impact wherever possible (percentages, dollar amounts, issue counts)

### Phase 4: Save the draft

Save the draft as a Markdown file in `work/progress-briefs/{YEAR}-{QUARTER}/`.

## Form structure (as of Q4 2025)

There are two forms in Paylocity:

### Form 1: Brief overview of where things stand

- **What is working for you?**
- **What isn't working for you?**
- **Where do you need support to meet your OKRs?**
- **Additional Comments (Employee):** (optional)

### Form 2: Professional Development

- **Professional Development / Training** (1-3 focus areas, with resources to be utilized)

## Directory structure

```
work/progress-briefs/
  {YEAR}-{QUARTER}/
    format/                  # PDF screenshots of the web forms
    jira-issues/             # Jira exports (CSV, XML, RSS XML) -- reference
    docs/                    # Authored documents from the period
    rollup.md                # Quarterly rollup (from collect_progress_brief.py)
    impact-metrics.yaml      # Tracked impact metrics (accumulated during sprint drafting)
    <draft output>.md        # The generated draft
```

## Tips

- The rollup is the single best source for this skill. If it exists, start there.
- Sprint notes docs contain the most curated narrative of accomplishments. Dip into them for the full story when the rollup's one-line summaries aren't enough.
- Memos and investigation notes (in `docs/`) demonstrate leadership, analytical thinking, and initiative. Reference them when answering "what is working."
- The "What isn't working" section benefits from honesty and specificity. Reference concrete blockers from sprint notes (incomplete/carrying forward sections) rather than vague complaints.
- Count total completed issues from the rollup's Summary Statistics table as a quantitative data point.
- If the rollup doesn't exist yet, fall back to reading sprint notes directly and Jira CSV exports. The skill still works without the rollup, just with more manual synthesis.
