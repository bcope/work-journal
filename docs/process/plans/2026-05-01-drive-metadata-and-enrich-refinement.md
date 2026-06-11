# 2026-05-01 — Drive metadata expansion + enrich-sprint-data refinement

## Motivation

The enrichment skill currently elevates Google Docs to "key documents" based on `modifiedTime` falling inside the sprint window. That over-includes docs whose substantive authoring happened earlier and whose 4/30 timestamp reflects a permission tweak or a doc just being opened. Today's symptom: the "Executive Summary - Jira Future State" doc, authored 3/20, surfaced as a 2026-04-B accomplishment because Drive reported `modifiedTime: 2026-04-30`.

The Drive Files resource already returns enough metadata to discriminate — we just aren't requesting the right fields.

## Field list to add to Drive `files.list` calls

```
id, name, mimeType,
createdTime, modifiedTime, modifiedByMeTime, viewedByMeTime,
lastModifyingUser(displayName, emailAddress),
owners(displayName, emailAddress),
version, trashed, parents, shared, starred, description,
driveId, webViewLink, size
```

`size` is kept where present; `mimeType` is added everywhere (currently only `searchFiles` returns it). `webViewLink` continues to populate the existing `url` key in the response.

## Changes

### 1. `~/git/ai-toolkit/mcp/gdocs-mcp/src/index.js`

Six `drive.files.list` call sites updated with the field list above and the
return-mapping object extended to expose all of them by name. Existing keys
(`url`, `modifiedTime`) preserved for backwards compatibility.

| Line | Function |
|---|---|
| 1057 | `searchDocs` |
| 1114 | `listRecentDocs` |
| 1131 | `searchFiles` |
| 1561 | `searchSheets` |
| 2307 | `searchPresentations` |
| 2323 | `listRecentPresentations` |

Two per-file metadata fetches inside `readDoc` updated similarly (lines 1072, 1085 — regular Drive and shared-drive code paths). The returned `modifiedTime` field stays; we add `createdTime`, `modifiedByMeTime`, `lastModifyingUser`, `version`.

Tool descriptions for `search_files`, `search_docs`, `search_presentations`,
`search_sheets` updated to mention the new metadata fields.

`README.md` gets a one-paragraph note describing the metadata fields and what
each is useful for.

### 2. `.claude/skills/enrich-sprint-data/SKILL.md`

Phase 4 (Google Docs) rewritten around a three-bucket triage:

- **Bucket A — Created in sprint window.** `createdTime` ∈ `[start, end]`. Primary content for `google-docs/doc-summaries.md`. Read in full, summarize, link to Jira issues.
- **Bucket B — Edited by user during sprint, but created earlier.** `createdTime < start` AND `modifiedByMeTime` ∈ `[start, end]`. Logged in `google-docs/modified-not-created.md` for manual review. Skill does NOT auto-summarize these.
- **Bucket C — Touched during sprint by someone else (or by metadata-only changes).** `modifiedTime` ∈ `[start, end]` but `modifiedByMeTime` outside window or missing. Logged in `google-docs/modified-not-created.md` under a separate section ("not modified by me"). Useful for collaborator-activity audit; not pulled into the draft.

Files where `trashed: true` are dropped outright.

`google-docs/modified-not-created.md` format:

```markdown
# Documents modified during sprint but not created in sprint

Review whether any of these represent real sprint-period work that should
be folded into doc-summaries.md (and the draft).

## Modified by me (likely real carry-forward edits)

- **{name}** (created {createdTime} → modifiedByMeTime {ts})
  - URL, mimeType, size
  - one-line description

## Touched in window but not by me (collaborator / metadata-only changes)

- **{name}** (created {createdTime}, modifiedTime {ts}, modifiedBy {name})
  - URL
```

Data Quality table gains rows counting how many files landed in each bucket.

### 3. `.claude/skills/draft-sprint-notes/SKILL.md`

Phase 1 ("Load collected data") updated with a one-paragraph note that
`google-docs/modified-not-created.md` is intentionally NOT loaded by this skill
unless the user has manually moved items from it into `doc-summaries.md`.

## Out of scope (Phase 2)

- New `get_revisions` MCP tool wrapping the Drive Revisions API for "was this
  substantively edited?" beyond what `version` + `modifiedByMeTime` answer.
- Per-file `permissions` field — too heavy for list view.
- Drive Activity API integration.

## Operational note

After editing `~/git/ai-toolkit/mcp/gdocs-mcp/src/index.js`, the gdocs MCP must
be restarted for the field changes to take effect (restart Claude Code or
restart the MCP server explicitly). Skill changes are picked up automatically
on next invocation.
