# Phase 2B MVP Demo Runbook

## Purpose

Use this runbook to demonstrate the Phase 2B sanitized submittal-to-drawing MVP workflow for John and the application team.

The demo is a review workflow only. It does not approve production drawings, export PDFs, export final Direct Coil data, parse raw PDFs, run OCR, or connect to supplier systems.

## 1. Startup command

From the repository root:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python -m uvicorn coilforge.web_app:app --host 127.0.0.1 --port 8012
```

If port `8012` is already in use, choose another local port and use that port in the browser URL.

## 2. Browser open step

Open:

```text
http://127.0.0.1:8012/
```

Expected result:

- CoilForge web shell loads.
- Left navigation and workflow panels are visible.
- Export and Export PDF controls are disabled.

## 3. Load demo submittal

The UI loads the sanitized demo on page load.

Confirm:

- Project shows `Sanitized CoilForge Demo`.
- Coil tag shows `COIL-TAG-001`.
- Raw data is reported as excluded.
- PDF parser and OCR are not enabled.

## 4. Analyze

Click `Analyze`.

Expected result:

- Sanitized workflow runs through the backend.
- Direct Coil draft data refreshes.
- Readiness and validation panels update.

## 5. Apply to Direct Coil draft

Click `Apply to Direct Coil Draft`.

Expected result:

- The UI confirms the draft was refreshed from the sanitized workflow.
- No final Direct Coil export is created.

## 6. Review source evidence

In `Import Summary / Source Evidence`, confirm:

- Evidence fields are listed.
- Evidence ids are visible.
- Raw/private source text is not displayed.

Expected current count:

- SourceEvidence fields: `12`
- SourceEvidence refs: `12`

## 7. Review blocked fields

In `Blocked Fields`, confirm the required drawing baseline parameters remain visible:

- `BF`
- `CD`
- `CH`
- `TF`

Expected reason:

- Required canonical field missing.

## 8. Update drawing

Click `Update Drawing`.

Expected result:

- Backend drawing workflow runs.
- SVG preview refreshes when preview defaults are available.
- Validation stays review-required/blocked as applicable.

## 9. Edit driving parameters

Edit one or more driving values:

- `Coil name`
- `Finned height`
- `Finned length`
- `Airflow`

Then click `Update Drawing`.

Expected result:

- Direct Coil draft values update for edited sanitized fields.
- DrawingIntent and SVG metadata update when supported.
- The drawing remains a review aid.

## 10. Confirm SVG/metadata update

When SVG is returned, confirm:

- SVG preview is visible.
- Drawing metadata reports `generated_with_warnings`.
- `preview_allowed` is true only because sanitized preview defaults are available.
- `export_allowed` remains false.

If preview is blocked, confirm:

- SVG is not returned.
- Validation lists blocked preview fields.
- Export remains disabled.

## 11. Confirm watermark/review-required

When SVG is returned, confirm the watermark remains visible:

```text
REVIEW AID - NOT FOR MANUFACTURING
```

Confirm:

- Review status remains `review_required`.
- John drawing semantics review is still required.
- No production drawing approval is claimed.

## 12. Confirm export disabled

Confirm:

- Top Export button is disabled.
- Bottom Export PDF button is disabled.
- Backend export status is `not_implemented`.
- DrawingIntent `export_allowed` is false.

## 13. Report-back format

Use this format after a manual demo:

```text
One-line result:
Demo date/time:
Repo commit:
Browser/URL:
Workflow result:
Direct Coil field counts:
Blocked fields:
SourceEvidence result:
Drawing preview result:
Watermark result:
Export disabled result:
Observed issues:
John review required:
Next recommended task:
```

## Current expected baseline

- Direct Coil fields: `52`
- Ready: `0`
- Review-required: `12`
- Blocked: `4`
- Unmapped: `36`
- Blocked drawing fields: `BF`, `CD`, `CH`, `TF`
- SourceEvidence fields: `12`
- Export: disabled / `not_implemented`

## Known limitations

- Sanitized DX Header 1 demo only.
- No raw PDF upload.
- No OCR.
- No supplier integration.
- No final Direct Coil export.
- No PDF export.
- No production drawing approval.

## Remaining review items

- John review of drawing semantics and airflow convention.
- Application team review of UI field grouping and demo ergonomics.
- Decision on whether manual drawing parameter entries become persisted review overrides in a later phase.
