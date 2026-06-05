# Phase 2A Review Packet

Status: Ready for John and ChatGPT review.

Created: 2026-06-05.

Scope: Review packet only. This document does not add features, expand Phase 2A scope, touch raw `Case/` data, or touch `outputs/` data.

## 1. One-Line Implementation Result

Phase 2A now has a local FastAPI plus vanilla HTML/CSS/JS MVP for the sanitized DX Header 1 / EZC-0001 slice, with editable parameters, visible validation, responsive SVG review-aid rendering, checklist snapshot generation, and drawing metadata generation.

## 2. Branch And Commit Hash

- Branch: `phase2a/local-web-mvp`
- Implementation commit: `5d46597 feat: add phase 2A local web DX Header 1 MVP`
- Remote branch: `origin/phase2a/local-web-mvp`

## 3. Startup Command

Primary startup command:

```bash
python -m uvicorn coilforge.phase2a.app:app --app-dir src --reload
```

Compatibility startup command:

```bash
python -m uvicorn coilforge.web_app:app --app-dir src --reload
```

Default local URL:

```text
http://127.0.0.1:8000
```

## 4. API Routes Implemented

- `GET /`
  - Serves the local browser UI from `web/index.html`.
- `GET /api/default-state`
  - Loads only `examples/sanitized/dx_header1_ezc0001_default.json`.
  - Returns `DxHeader1ParameterState` plus fixture metadata.
- `POST /api/validate`
  - Returns a structured `ValidationReport`.
  - Unsupported category/header edits return visible blocked checks.
- `POST /api/render-svg`
  - Returns `SvgRenderResponse` with SVG text, metadata, warnings, and blocked fields.
- `POST /api/generate-snapshot`
  - Returns `ChecklistSnapshot` and `DrawingMetadata`.

## 5. UI Behavior Summary

The UI provides four local panels:

- Parameter editor
  - Loads the sanitized default state on page load.
  - Supports editing Phase 2A parameter values.
  - Marks validation stale when a value changes.
- Validation panel
  - Runs validation on demand.
  - Shows overall status, status counts, and individual check rows.
- SVG preview panel
  - Renders the current parameter state into an SVG review-aid preview.
  - Updates visible title, dimensions, panel values, notes, warnings, and blocked state from current values.
- Snapshot / metadata panel
  - Generates and displays checklist snapshot plus drawing metadata JSON.

## 6. Parameter Fields Supported

The editable Phase 2A state supports:

- `coil_name`
- `model_number`
- `source_case_id`
- `coil_category`
- `header_type`
- `rows`
- `fin_height`
- `fin_length`
- `fin_density_fpi`
- `casing_height`
- `casing_length`
- `casing_depth`
- `top_flange`
- `bottom_flange`
- `return_bend_allowance`
- `coil_hand`
- `airflow_direction`
- `return_connection_size`
- `circuiting_display`
- `release_status`
- `drawing_status`
- `notes`

Default safety values:

- `coil_category = DX`
- `header_type = Header 1`
- `release_status = review_aid_only`
- `drawing_status = not_generated`

## 7. Validation Rules Implemented

Implemented validation checks:

- `phase2a_required_coil_name`
  - Fails when `coil_name` is missing.
- Required field checks for the remaining first-slice required fields.
  - Missing `airflow_direction` is blocked.
  - Other missing required values fail.
- `phase2a_category_dx`
  - Passes only for `DX`.
  - Blocks unsupported categories such as `HGRH`.
- `phase2a_header1_only`
  - Passes only for `Header 1`.
  - Blocks unsupported headers such as `Header 2`.
- `phase2a_required_airflow_direction`
  - Requires explicit airflow direction.
  - Does not infer direction silently.
- `phase2a_oal_not_approved`
  - Warns by default that OAL is not generated and must render as review-required.
  - Blocks explicit OAL generation requests or supplied OAL-like fields.
- `phase2a_release_status_safe`
  - Passes only for `review_aid_only`.
  - Blocks manufacturing-like release statuses.
- `phase2a_drawing_status_safe`
  - Allows `not_generated`, `generated_review_aid`, and `generated_with_warnings`.
  - Blocks or fails unsafe drawing statuses.
- `phase2a_full_json_adapter_not_applicable`
  - Marks the full JSON import/export adapter as out of scope.

Validation status values supported:

- `pass`
- `warn`
- `fail`
- `blocked`
- `not_applicable`

## 8. SVG Renderer Behavior

The SVG renderer:

- Uses fixed `viewBox="0 0 1600 1200"`.
- Includes review text: `REVIEW AID - NOT FOR MANUFACTURING`.
- Keeps text as SVG text.
- Includes required stable zone IDs:
  - `zone.sheet_frame`
  - `zone.title_block`
  - `zone.front_view`
  - `zone.side_header_view`
  - `zone.right_panel`
  - `zone.bottom_dimension_table`
  - `zone.review_metadata`
  - `markup.review`
- Updates visible values from the current state, including:
  - `coil_name`
  - `model_number`
  - `rows`
  - `fin_height`
  - `fin_length`
  - `fin_density_fpi`
  - `casing_height`
  - `casing_length`
  - `casing_depth`
  - `top_flange`
  - `bottom_flange`
  - `return_bend_allowance`
  - `coil_hand`
  - `airflow_direction`
  - `return_connection_size`
  - `circuiting_display`
  - `notes`
- Shows `OAL: REVIEW REQUIRED`.
- Marks blocked validation cases with `GENERATION BLOCKED - REVIEW REQUIRED`.
- Keeps `release_status=review_aid_only` in renderer metadata.

## 9. Snapshot And Metadata Behavior

Checklist snapshot includes:

- `snapshot_id`
- `snapshot_status = draft_review_aid`
- `source_fixture = sanitized_dx_header1_ezc0001_default`
- current `state`
- `validation_status`
- `created_by = coilforge_local_mvp`

Drawing metadata includes:

- `drawing_generation_run_id`
- `drawing_status`
- `release_status = review_aid_only`
- `template_id = phase2a_dx_header1_review_svg`
- `viewBox = 0 0 1600 1200`
- `source_case_id = EZC-0001`
- `warnings`
- `blocked_fields`
- `john_review_required = true`

No external files are created by snapshot or metadata generation.

## 10. Acceptance Criteria Checklist

| Criteria | Status | Evidence |
| --- | --- | --- |
| Local app starts | Passed | Uvicorn server was started locally on `127.0.0.1:8000`. |
| Browser UI loads | Passed | Edge headless screenshot captured initial UI. |
| Default sanitized DX Header 1 state loads | Passed | `/api/default-state` returned `source_case_id = EZC-0001`. |
| User can edit parameters | Passed | UI fields are editable; route tests edit `coil_name`; renderer tests edit many parameters. |
| Validation panel updates | Passed | `web/app.js` renders validation summary and checks after `/api/validate`. |
| SVG preview updates from current values | Passed | Renderer and route tests verify edited values appear in SVG. |
| Unsupported category/header is blocked | Passed | Tests cover `HGRH` and `Header 2` blockers. |
| Missing `airflow_direction` is blocked or visibly warned | Passed | Validation test confirms missing `airflow_direction` is blocked. |
| OAL is blocked or visibly marked review-required | Passed | Default render shows `REVIEW REQUIRED`; explicit OAL generation request is blocked. |
| Drawing includes review watermark | Passed | Renderer and route tests assert review watermark. |
| Drawing release status remains review aid only | Passed | Renderer and metadata set `release_status = review_aid_only`. |
| Checklist snapshot can be generated | Passed | Route and unit tests cover snapshot generation. |
| Drawing metadata can be generated | Passed | Route and unit tests cover metadata generation. |
| No raw Case/output/source files are committed | Passed for implementation commit | Commit staged only `README.md`, `src/coilforge`, `web`, and `tests`; current untracked `outputs/` remains unstaged. |
| Tests or validation commands documented | Passed | README and this packet list startup and validation commands. |

## 11. Tests / Validation Results

Validation commands run after implementation:

```bash
python -m compileall src
python -m pytest
```

Observed results:

- `python -m compileall src`: passed.
- `python -m pytest`: 25 passed, 1 warning.
- Warning: FastAPI TestClient emitted a Starlette deprecation warning about `httpx`.

Additional local smoke verification:

- `GET /api/default-state` returned `EZC-0001`.
- Edited API state with `coil_name = API_EDITED_COIL`.
- SVG response contained edited coil name.
- SVG response contained `REVIEW AID - NOT FOR MANUFACTURING`.
- SVG response contained `REVIEW REQUIRED`.
- Snapshot response returned `snapshot_status = draft_review_aid`.
- Drawing metadata returned `release_status = review_aid_only`.
- Unsupported `coil_category = HGRH` returned `validation_status = blocked`.

## 12. Known Placeholders

- SVG geometry is a review-aid MVP layout, not a CAD-grade or manufacturing drawing.
- OAL is intentionally not calculated.
- Airflow arrow convention is a simple display convention and still needs John visual review.
- Right-panel content is limited to first-slice values, notes, warnings, and blocked fields.
- Full JSON import/export adapter is explicitly marked `not_applicable`.
- No PDF export is implemented.
- No selection calculation engine is implemented.
- No multi-case manager is implemented.

## 13. Known Risks

- The SVG may visually differ from the exact desired Oxygen8/CoilMaster drawing standard until John reviews layout, placement, and wording.
- Airflow orientation may need correction after John confirms the convention.
- Header/connection position and side-view geometry may need revision before expansion to Header 2, Header 3, HGBP, or non-DX categories.
- OAL remains unresolved by design; adding a formula without approval would violate Phase 2A boundaries.
- Allowing validation to display unsupported edited values is useful for UI review, but blocked states must remain visible before any future generation workflow.
- Current status should be reported as validated for technical review, not completed for business/engineering approval.

## 14. Remaining John Review Items

John or engineering should review:

- First generated SVG visual layout.
- Airflow arrow convention and mirroring behavior.
- OAL continued review-required handling.
- Header/connection side-view placement.
- Right-panel requiredness and wording.
- Review watermark and title-block wording.
- Whether `generated_with_warnings` is acceptable for default Phase 2A render while OAL remains review-required.

## 15. Screenshots Or Manual Verification Notes

Manual/browser verification notes from implementation closeout:

- Local server responded at `http://127.0.0.1:8000`.
- Edge headless screenshot showed the CoilForge Phase 2A UI with:
  - header review-aid boundary
  - parameter editor
  - validation panel
  - default sanitized values loaded
- Browser plugin was not available in the session.
- Node REPL Playwright was attempted but blocked by incomplete bundled `playwright-core` resolution.
- API smoke verification was used to confirm edited-value SVG updates, watermark, OAL review-required text, snapshot, metadata, and unsupported category blocking.

Local screenshot artifact from implementation closeout:

```text
C:\Users\JohnKim\AppData\Local\Temp\coilforge-phase2a-edge.png
```

This screenshot is local verification evidence only and is not committed.

## 16. Next Recommended Phase

Recommended next task: John / ChatGPT Phase 2A review.

Suggested scope:

- Review the generated SVG from the default DX Header 1 / EZC-0001 state.
- Run the manual demo checklist below.
- Decide whether the current Phase 2A MVP is accepted as technically validated for review-aid workflow testing.
- Capture John decisions on airflow, OAL, title block wording, right-panel requiredness, and SVG visual changes before Phase 2B.

Do not start Phase 2B expansion until the Phase 2A review items are resolved or explicitly deferred.

## Required Manual Demo Checklist

- [ ] Start local app.
- [ ] Open browser.
- [ ] Load default fixture.
- [ ] Change `fin_height`.
- [ ] Confirm SVG updates.
- [ ] Change `coil_name`.
- [ ] Confirm title block updates.
- [ ] Clear `airflow_direction`.
- [ ] Confirm validation warning/block.
- [ ] Try unsupported `header_type`.
- [ ] Confirm blocked state.
- [ ] Confirm review watermark is visible.
- [ ] Generate snapshot.
- [ ] Generate metadata.

## Review Packet Safety Notes

- Raw `Case/` data was not inspected for this review packet.
- `outputs/` data was not touched for this review packet.
- No raw PDFs, Excel files, raw JSON/TXT exports, rendered pages, customer/project source data, or `.env` files are required for the Phase 2A local MVP demo.
- The only intended file change for this review task is `docs/PHASE2A_REVIEW_PACKET.md`.
