# Phase 2B.11 Design-Based Web UI Shell + JSON State

## One-line implementation result

Phase 2B.11 adds a design-based CoilForge web UI shell and a sanitized `/api/ui/default` JSON state that represents the Direct Coil draft, readiness, source evidence, drawing preview, drawing parameters, performance summary, and validation state.

## Files changed

- `web/index.html`
- `web/app.js`
- `web/style.css`
- `src/coilforge/phase2a/ui_state.py`
- `src/coilforge/web_app.py`
- `tests/test_phase2b_design_ui_state.py`
- `docs/PHASE2B_DESIGN_WEB_UI_STATE.md`

## UI layout summary

The shell follows the Phase 2B design target:

- Dark navy left sidebar with CoilForge branding, project search, project tree, and section navigation.
- Top header with breadcrumb, saved status, revision selector, calculate placeholder, and disabled export placeholder.
- Main tab strip for Checklist / Input, Performance, Drawing, and Review & Export.
- Left working column that renders Direct Coil registry groups and field rows from draft data.
- Right inspector column for import summary, source evidence, drawing preview, drawing parameters, performance summary, and validation.
- Bottom sticky action bar with Save Draft placeholder, Analyze, Apply to Direct Coil Draft, Update Drawing, and disabled Export PDF.

## UI state shape

`build_phase2b_default_ui_state()` returns:

- `project`: sanitized project name, coil tag, revision, saved status, and breadcrumb.
- `import_summary`: sanitized source type, candidate count, selected candidate summary, and explicit parser/OCR/raw-data flags.
- `direct_coil_draft`: draft id, canonical source id, registry groups, 52 field records, summary counts, and export status.
- `readiness_report`: full Direct Coil readiness packet.
- `drawing_intent`: DrawingIntent data from the existing bridge.
- `drawing_parameters`: DrawingParameterSet data from the resolver.
- `performance_summary`: compact performance-facing subset of mapped draft fields.
- `validation`: workflow status, preview/export state, blocked fields, review-required fields, and readiness counts.
- `source_evidence`: source evidence summary and field-level evidence references.
- `drawing_preview`: backend SVG when preview is allowed, metadata, preview flag, and export flag.
- `actions`: UI action availability and placeholder metadata.

## API routes

- `GET /api/ui/default`: returns the sanitized Phase 2B.11 UI state.
- `GET /api/workflow/default-demo`: existing sanitized workflow input and summary route reused by the shell.

## Placeholder behavior

The UI includes non-final placeholders for:

- Calculate
- Save Draft
- Export
- Export PDF

Analyze, Apply to Direct Coil Draft, and Update Drawing operate only against the sanitized backend workflow route. They do not produce final exports.

## Export disabled policy

Export remains disabled in the UI state and visual shell:

- `actions.export_pdf.enabled` is `false`.
- Direct Coil draft `export_status` remains `not_implemented`.
- Drawing preview `export_allowed` remains `false`.
- No PDF export or final Direct Coil export route is added.

## Known limitations

- No production drawing approval is claimed.
- No broad PDF parser, OCR, supplier integration, or raw data ingestion is added.
- The UI uses sanitized demo state only.
- Field editing is visual/state-oriented only; persistent save and final export are not implemented.
- Drawing output remains a review-required preview from the existing backend.

## Manual demo checklist

1. Start the web app.
2. Open the root web UI.
3. Confirm the dark sidebar, header, tabs, input field groups, right inspector panels, and sticky action bar render.
4. Confirm counts show ready `0`, review-required `12`, blocked `4`, and unmapped `36`.
5. Confirm source evidence rows appear in the import/source panel.
6. Confirm the drawing preview shows the backend SVG when preview defaults are available.
7. Confirm Export and Export PDF controls are disabled.

## Next recommended phase

Phase 2B.12 should add controlled UI interactions for reviewing and applying manual field overrides while preserving SourceEvidence, review-required state, blocked state, and export-disabled policy.
