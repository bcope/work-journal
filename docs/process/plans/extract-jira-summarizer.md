# Extract Jira Issue Summarizer Script

## Context

Two Claude skills (`draft-sprint-notes` and `enrich-sprint-data`) contain nearly identical inline Python code blocks that summarize Jira JSON exports. The code is embedded as a `uv run python3 -c "..."` one-liner that Claude runs via Bash. This is fragile (duplicated, untestable, not linted) and should be a proper script in `src/work_journal/jira/`.

The two variants differ only in that the enrich version also extracts Google Doc URLs from issue descriptions via regex.

## Plan

### 1. Create `src/work_journal/jira/summarize_issues.py`

A standalone script following the same pattern as `query_issues.py` and `query_sprint_info.py` (argparse, runnable via `uv run python3`).

**CLI:**

```bash
# Basic (for draft-sprint-notes)
uv run python3 src/work_journal/jira/summarize_issues.py work/sprint-notes/2026-02-A

# With doc URL extraction (for enrich-sprint-data)
uv run python3 src/work_journal/jira/summarize_issues.py work/sprint-notes/2026-02-A --doc-urls
```

**Behavior:**

- Takes a sprint directory path as positional arg
- Reads the 7 standard Jira JSON files (hardcoded list matching `config.yaml` query outputs)
- For each file: prints `=== {label} ({N} issues) ===` header, then one line per issue with key, type, priority, summary, status, reporter
- With `--doc-urls`: also extracts Google Doc/Sheet URLs from issue description fields and prints them
- Skips files that don't exist (prints `=== {label} (file not found) ===`)
- Prints to stdout -- no file output

**Files map (filename -> label):**

| File | Label |
| --- | --- |
| `jira/sprint-planned-completed.json` | `planned-completed` |
| `jira/sprint-planned-incomplete.json` | `planned-incomplete` |
| `jira/sprint-added-completed.json` | `added-completed` |
| `jira/sprint-added-incomplete.json` | `added-incomplete` |
| `jira/non-sprint-completed.json` | `non-sprint-completed` |
| `jira/non-sprint-incomplete.json` | `non-sprint-incomplete` |
| `jira/non-sprint-non-assigned-with-worklog.json` | `non-sprint-worklog` |

### 2. Write test `tests/test_summarize_issues.py`

- Test basic output format with a temp dir containing small JSON fixtures
- Test `--doc-urls` flag extracts URLs from description
- Test missing files are handled gracefully

### 3. Update skill files

Replace the inline Python code block in both skills with a reference to the script:

**`.claude/skills/draft-sprint-notes/SKILL.md`** (lines 43-69): Replace with:

```bash
uv run python3 src/work_journal/jira/summarize_issues.py work/sprint-notes/{sprint}
```

**`.claude/skills/enrich-sprint-data/SKILL.md`** (lines 35-65): Replace with:

```bash
uv run python3 src/work_journal/jira/summarize_issues.py work/sprint-notes/{sprint} --doc-urls
```

### 4. Lint and verify

```bash
uv run ruff check src/work_journal/jira/summarize_issues.py
uv run ruff format src/work_journal/jira/summarize_issues.py
uv run pytest tests/test_summarize_issues.py -v
```

## Files

- **Create:** `src/work_journal/jira/summarize_issues.py`
- **Create:** `tests/test_summarize_issues.py`
- **Modify:** `.claude/skills/draft-sprint-notes/SKILL.md` (replace inline code block)
- **Modify:** `.claude/skills/enrich-sprint-data/SKILL.md` (replace inline code block)
