---
name: upload-sprint-notes
description: Upload a draft.md sprint notes file to Google Docs with company styles applied. Use after drafting sprint notes. Invoke whenever the user says "upload sprint notes", "upload to docs", "push to drive", "/upload-sprint-notes", or wants to get their sprint notes into Google Docs.
---

# Upload Sprint Notes

Upload a finalized `draft.md` to Google Docs with company styles applied. The user will specify a sprint directory name (e.g., `2026-02-B`).

## Prerequisites

- `work/sprint-notes/{sprint}/draft.md` must exist
- The `md-to-gdoc.js` script must be available (path configured in `work/sprint-notes/config.yaml` under `google_drive.md_to_gdoc_script`)

## Process

### Step 1: Read configuration

Read `work/sprint-notes/config.yaml` and extract:

- `google_drive.md_to_gdoc_script` -- path to the upload script
- `google_drive.sprint_notes_folder` -- target Google Drive folder URL

### Step 2: Determine document title

The document title follows the pattern:

```
{sprint} - Sprint Notes & Demo - Shared
```

For example: `2026-02-B - Sprint Notes & Demo - Shared`

### Step 3: Upload

Run the script:

```bash
node {md_to_gdoc_script} upload work/sprint-notes/{sprint}/draft.md \
  --title "{sprint} - Sprint Notes & Demo - Shared" \
  --folder "{sprint_notes_folder}"
```

### Step 4: Report result

Print the Google Doc URL returned by the script so the user can open it directly.

## Re-uploading after edits

If the user edits `draft.md` after the initial upload and wants to update the Google Doc, the simplest approach is to upload again as a new document. The script creates a new doc each time -- it does not update in place. Let the user know this so they can delete the old version if desired, or keep both for comparison.

If the user wants to update the existing doc in place, they should edit the Google Doc directly rather than re-uploading.
