# Phase 2D-M1 POs-Based Intake Review Workflow

## 1. One-Line Implementation Result

Phase 2D-M1 adds a review-safe MVP workflow slice that combines safe summarized POs-derived intake signals, engineering adjustment records, and quote-prep review packet generation while keeping all export, PDF export, final quote, and production drawing approval paths disabled.

## 2. Files Changed

- `src/coilforge/submittal/po_based_intake.py`
- `src/coilforge/review/__init__.py`
- `src/coilforge/review/adjustments.py`
- `src/coilforge/review/packet.py`
- `src/coilforge/web_app.py`
- `tests/test_phase2d_pos_based_intake_review_workflow.py`
- `docs/PHASE2D_POS_BASED_INTAKE_REVIEW_WORKFLOW.md`

## 3. POs-Based Intake Behavior

`build_po_based_intake()` builds a POs-aware intake result over the existing sanitized submittal intake path. It consumes only the safe rule summaries from `po_logic_bridge.py`; it does not import sibling POs code, read raw PDFs, run OCR, or ingest raw customer/project data.

The intake result preserves:

- `SubmittalCoilCandidate`
- `SourceEvidence` IDs and field evidence objects
- `review_required_fields`
- `blocked_fields`
- `unmapped_fields`
- export-disabled metadata

## 4. Fallback Behavior If POs Final Selection Logic Is Unavailable

Application-team final selection logic and BTO/final selection workflow remain `not_found` in the Phase 2C-M2 POs logic summary. Phase 2D therefore sets:

- `final_selection_logic_available = false`
- `fallback_used = true`
- fallback source = existing sanitized submittal intake candidate

No final selection behavior is invented.

## 5. POs Logic Used vs Not Used

Used as review-safe signals:

- `po_unit_tag_normalization`
- `po_review_before_export_gate`
- `po_cover_table_product_detection`
- `po_component_coil_detection`

Not used as approved CoilForge logic:

- `po_bom_linestring_decisions`
- `po_pdf_extraction_pipeline`
- `po_application_team_selection`
- `po_bto_selection_workflow`

BOM/linestring Required/Inventory/Manufactured/N/A logic remains a John/engineering review item and is not applied as Direct Coil, drawing, quote, or manufacturing approval logic.

## 6. EngineeringAdjustment Model

`EngineeringAdjustment` records manual engineering changes without mutating source evidence or downstream draft values. Each adjustment includes:

- adjustment identity
- field key and field group
- original value
- adjusted value
- unit
- reason
- adjusted by
- preserved `SourceEvidence`
- review status
- drawing, Direct Coil, and quote impact flags
- created phase
- downstream applied flag

`downstream_applied` must remain `false` in Phase 2D-M1.

## 7. Manual Override Behavior

Manual overrides default to `review_required`. They are not engineering approved, do not update DirectCoilInputDraft readiness, do not update DrawingIntent approval, and do not enable final export.

Same-field conflicting adjusted values are marked `blocked` by `resolve_conflicting_adjustments()`.

## 8. SourceEvidence Preservation

POs intake and EngineeringAdjustment preserve existing sanitized `SourceEvidence`. The review packet summarizes evidence IDs and counts rather than returning raw/private source text.

## 9. Review Packet Shape

`ReviewPacket` includes:

- project and coil identity
- input source summary
- POs-based intake summary
- DirectCoilInputDraft summary
- readiness report summary
- SourceEvidence summary
- DrawingIntent summary
- SVG metadata summary when available
- EngineeringAdjustment summary
- review-required fields
- blocked fields
- unmapped fields
- CD/BF/TF/CH status
- drawing-impacting field summary
- POs-supported field summary
- unresolved John/engineering review items
- export status
- quote-prep status

## 10. Quote-Prep/Review-Only Policy

The packet is a quote-prep and review aid only. It is not a final quote, not a manufacturing release, not a production drawing approval, and not a Direct Coil final export payload.

## 11. Export Disabled Policy

Phase 2D-M1 keeps:

- `export_allowed = false`
- `pdf_export_enabled = false`
- `direct_coil_final_export_available = false`
- `production_drawing_approval_claimed = false`
- `quote_finalization_available = false`

## 12. CD/BF/TF/CH Status

CD, BF, TF, and CH remain drawing-baseline review fields. In the default sanitized workflow they are reported as blocked because required canonical values are missing. The review packet marks them as drawing-impacting and not production approved.

## 13. Drawing-Impacting Field Handling

Phase 2D tracks 22 drawing-impacting fields:

- 13 Drawing Parameters
- 9 DrawingIntent-driving fields

Drawing-impacting adjustments are flagged for John/engineering review and are not applied downstream.

## 14. Remaining John/Engineering Review Items

- CD/BF/TF/CH drawing semantics
- 22 drawing-impacting field review
- POs-supported field adoption
- future unit conversion approval
- BOM/linestring Required/Inventory/Manufactured/N/A policy
- application-team/BTO final selection workflow

## 15. Tests / Validation Results

Validation completed:

- `python -m pytest tests\test_phase2d_pos_based_intake_review_workflow.py`
- Result: `18 passed, 1 warning`
- `python -m compileall src`
- Result: passed
- `python -m pytest`
- Result: `242 passed, 1 warning`

The warning is the existing FastAPI/Starlette TestClient deprecation warning.

## 16. Next Recommended Task

Run John/engineering review on the Phase 2D packet output and decide whether the next implementation slice should expose a demo-only adjustment entry surface or remain API/model-only until CD/BF/TF/CH semantics are reviewed.
