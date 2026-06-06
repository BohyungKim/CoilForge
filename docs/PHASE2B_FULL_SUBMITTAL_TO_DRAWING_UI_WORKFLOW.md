# Phase 2B.12 Full Submittal-to-Drawing UI Workflow

## One-line implementation result

Phase 2B.12 connects the design-based web shell to the full sanitized submittal-to-drawing backend workflow.

## Files changed

- `web/index.html`
- `web/app.js`
- `web/style.css`
- `tests/test_phase2b_full_ui_workflow.py`
- `docs/PHASE2B_FULL_SUBMITTAL_TO_DRAWING_UI_WORKFLOW.md`

## Full UI workflow

The UI now follows this flow:

```text
sanitized default demo
-> analyze current UI values
-> DirectCoilInputDraft
-> Direct Coil readiness report
-> DrawingParameterSet
-> DrawingIntent
-> SVG review preview
-> validation and source evidence display
```

The workflow continues to use sanitized demo input only. No raw PDF, OCR, broad parser, supplier integration, final Direct Coil export, or PDF export is added.

## API routes used

- `GET /api/workflow/default-demo`
- `POST /api/workflow/submittal-to-drawing`
- `GET /api/ui/default`

`POST /api/workflow/submittal-to-direct-draft` remains available, but the UI drawing path uses the drawing workflow route because it returns draft, readiness, drawing intent, SVG, and validation in one response.

## UI behavior

The page loads the sanitized demo state and renders:

- Import and candidate summary.
- Source evidence summary and field evidence references.
- Direct Coil-like field groups from the draft registry.
- Ready, review-required, blocked, and unmapped counts.
- Blocked fields list with labels and reasons.
- Drawing parameters.
- Backend SVG preview when preview is allowed.
- Validation status.

The UI exposes editable driving values:

- `coil_name`
- `finned_height`
- `finned_length`
- `airflow_direction`
- Drawing parameter preview values when manual drawing parameter mode is enabled.

The Update Drawing and Analyze actions send the current sanitized workflow payload to the backend and refresh the displayed draft, readiness, drawing parameters, SVG, validation, and source evidence state.

## Drawing behavior

Drawing preview still uses the existing Phase 2A SVG renderer through the Phase 2B DrawingIntent bridge. Editing `finned_height`, `finned_length`, or `coil_name` changes the submitted workflow payload and can change the returned SVG or drawing metadata.

All generated SVG output remains a review aid. The review watermark remains visible when SVG is returned.

## Validation behavior

The UI surfaces the backend validation state:

- Workflow status.
- Preview allowed or blocked.
- Drawing status.
- Export status.
- Blocked field count and field list.

Required drawing baseline parameters `CD`, `BF`, `TF`, and `CH` remain visible as blocked readiness fields even when sanitized preview defaults allow a review-required preview.

## SourceEvidence behavior

SourceEvidence remains visible in the import/source panel. The UI displays evidence counts and field evidence ids from the readiness report; no raw private source text is returned or rendered.

## Export disabled policy

Export remains disabled:

- No PDF export route is added.
- No final Direct Coil export route is added.
- Export PDF is disabled in the UI.
- Backend export status remains `not_implemented`.
- DrawingIntent `export_allowed` remains `false`.

## Manual demo checklist

1. Start the web app.
2. Open the root UI.
3. Confirm the default sanitized demo loads.
4. Confirm candidate summary, source evidence, Direct Coil fields, counts, blocked fields, drawing parameters, validation, and drawing preview are visible.
5. Change `finned_height` and click Update Drawing.
6. Confirm the draft field and SVG/metadata refresh.
7. Change `coil_name` and click Update Drawing.
8. Confirm title-block output changes when SVG is returned.
9. Confirm Export and Export PDF remain disabled.

## Known limitations

- Manual drawing parameter values are preview-only and review-required.
- No persistent draft save is implemented.
- No production drawing approval is claimed.
- No final Direct Coil or PDF export is implemented.
- No raw PDF upload, OCR, broad parser, supplier integration, or quote package workflow is implemented.

## Remaining John review items

- Confirm drawing semantics and airflow convention before any production drawing claim.
- Review whether UI manual drawing parameter inputs should become durable manual overrides in a later phase.
- Review Direct Coil field display grouping and label order against John’s preferred working flow.

## Next recommended phase

Phase 2B.13 should add a controlled review/override persistence layer for UI-edited values while preserving SourceEvidence, review-required state, blocked state, and export-disabled policy.
