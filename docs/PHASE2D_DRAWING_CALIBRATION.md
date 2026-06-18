# Phase 2D-M2 Drawing Calibration + Visual Regression

## 1. One-Line Implementation Result

Phase 2D-M2 adds deterministic SVG/metadata regression helpers and tests for the current DX/Header 1 review-aid drawing path, plus drawing calibration documentation for MVP testing, without enabling production drawing approval, PDF export, Direct Coil final export, OCR, raw ingestion, active approval workflow, approval persistence, or final quote generation.

## 2. Files Changed

- `src/coilforge/drawing/svg_regression.py`
- `tests/test_phase2d_drawing_visual_regression.py`
- `docs/PHASE2D_DRAWING_CALIBRATION.md`

## 3. Drawing Calibration Scope

Current drawing calibration is limited to the existing review-aid DX/Header 1 path:

- sanitized submittal fixture
- DirectCoilInputDraft mapping
- DrawingParameterSet with explicit sanitized default preview values for required drawing parameters
- DrawingIntent bridge
- Phase 2A SVG renderer adapter
- ReviewPacket drawing summary

The calibration is for MVP testing only. It does not create a released drawing, final Direct Coil export payload, quote-ready output, PDF, or manufacturing-approved artifact.

## 4. SVG Regression Strategy

`normalize_svg_for_regression()` parses the SVG and returns a deterministic text representation for tests. It:

- normalizes whitespace
- sorts element attributes
- preserves meaningful element text
- preserves meaningful labels and metadata text
- preserves watermark, dimensions, title block, and review panel content
- masks timestamp-like values as `<TIMESTAMP>`
- masks UUID-like values as `<UUID>`

`normalize_svg_metadata_for_regression()` sorts metadata keys and applies the same timestamp/UUID normalization to metadata values.

This keeps tests stable without weakening checks for drawing meaning.

## 5. Parameters Covered

The Phase 2D-M2 regression tests cover:

- `coil_name` title block impact
- `finned_height` / FH visual or metadata impact
- `finned_length` / FL visual or metadata impact
- `airflow_direction` visibility under the current review-required preview policy
- unsupported `header_type` blocked behavior
- CD/BF/TF/CH unresolved or blocked review status
- review watermark visibility
- export-disabled status
- ReviewPacket drawing summary visibility

## 6. Watermark / Review-Aid Status

The rendered SVG must keep:

- `REVIEW AID - NOT FOR MANUFACTURING`
- `release_status=review_aid_only`
- `john_review_required=true`

ReviewPacket and SVG metadata continue to report review-only status. Production drawing approval is not claimed.

## 7. CD/BF/TF/CH Status

CD, BF, TF, and CH remain drawing-baseline review fields.

In the ReviewPacket they are reported under `cd_bf_tf_ch_status` with:

- `drawing_impact = true`
- `review_status = review_required_or_blocked`
- `production_approved = false`

In the default sanitized workflow, these values are supplied as explicit sanitized default preview values only for rendering the review aid. They are not approved engineering rules.

## 8. Airflow / OAL / Title Block Status

Airflow:

- Visible in the SVG review surface.
- Current default path renders `AIRFLOW left to right`.
- Airflow remains review-required policy context until John/engineering confirms the convention.

OAL:

- Remains `REVIEW REQUIRED`.
- No OAL formula is introduced.
- OAL is not derived from current fixture values.

Title block:

- `coil_name` affects rendered title block output.
- The title block remains review-aid wording, not a released drawing title block.
- Existing Phase 2A wording still requires John/engineering review before wider drawing use.

## 9. Drawing-Impacting Field Summary

Phase 2D continues to track 22 drawing-impacting fields:

- Drawing Parameter fields from the Direct Coil field registry.
- DrawingIntent-driving fields such as header type, airflow, finned dimensions, rows, FPI, coil hand, and return connection size.

The ReviewPacket exposes `drawing_impacting_field_summary` and keeps `production_drawing_approval_claimed = false`.

## 10. ReviewPacket Drawing Summary Behavior

ReviewPacket exposes drawing-related status without embedding raw SVG:

- `drawing_intent_summary.available = true` when the preview path is available
- `drawing_intent_summary.preview_allowed = true` for the default sanitized preview path with explicit default drawing parameters
- `drawing_intent_summary.export_allowed = false`
- `svg_metadata_summary.available = true`
- `svg_metadata_summary.raw_svg_included = false`
- `export_status.export_allowed = false`
- `quote_prep_status.final_quote = false`

Unresolved drawing items remain visible in `unresolved_review_items`.

## 11. Demo-only Adjustment UI Decision

Recommendation: keep engineering adjustments model/API-only for MVP testing.

Reason:

- CD/BF/TF/CH semantics remain unresolved.
- The 22 drawing-impacting fields require John/engineering review.
- Adding UI now could make review-required adjustments look more operational than they are.
- Phase 2D already captures adjustment records and review packet summaries without applying downstream behavior.

A disabled/demo-only adjustment UI can be considered later after John confirms which adjustment entry workflow is useful for review.

## 12. Known Drawing Limitations

- DX/Header 1 only.
- Uses current Phase 2A SVG layout.
- CD/BF/TF/CH semantics are not final.
- Sanitized default preview values are review aids only.
- No PDF export.
- No Direct Coil final export.
- No final quote generation.
- No OCR or broad PDF parser.
- No raw customer/project data ingestion.
- No production drawing approval.
- No approval persistence.
- OAL remains review-required.

## 13. Remaining John/Engineering Review Items

- Confirm CD/BF/TF/CH drawing semantics.
- Review all 22 drawing-impacting fields.
- Confirm whether sanitized default preview values are acceptable for MVP drawing review.
- Confirm airflow direction convention.
- Confirm OAL policy and whether any future formula may be used.
- Confirm title block and review watermark wording.
- Decide whether POs-supported field adoption should remain review-only or become a later approved mapping task.
- Decide whether a disabled/demo-only adjustment UI is worth adding after MVP review.

## 14. Tests / Validation Results

Validation completed during implementation:

- `python -m pytest tests\test_phase2d_drawing_visual_regression.py`
- Result: `11 passed`
- `python -m compileall src`
- Result: passed
- `python -m pytest`
- Result: `253 passed, 1 warning`
- `git diff --check`
- Result: passed

The warning is the existing FastAPI/Starlette TestClient deprecation warning.

## 15. Next Recommended Task

Run John/engineering review on the Phase 2D-M2 drawing calibration output and decide whether Phase 2D-M3 should add a read-only MVP drawing review packet snapshot or keep the next slice limited to documentation and tests until CD/BF/TF/CH semantics are reviewed.
