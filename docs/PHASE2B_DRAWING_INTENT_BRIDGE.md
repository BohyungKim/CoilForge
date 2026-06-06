# Phase 2B Drawing Intent Bridge

Status: Phase 2B.8 SVG preview backend bridge.

Scope: Direct Coil draft to drawing intent bridge and Phase 2A renderer adapter only. This phase does not implement PDF export, Direct Coil final export, UI, parser/OCR, new coil/header types, or production drawing approval.

## 1. One-Line Implementation Result

Phase 2B.8 adds a `DrawingIntent` bridge that converts `DirectCoilInputDraft` plus `DrawingParameterSet` into a Phase 2A renderer-compatible preview input and returns SVG review-aid output with review-required metadata.

## 2. Files Changed

- `src/coilforge/drawing/__init__.py`
- `src/coilforge/drawing/intent.py`
- `src/coilforge/drawing/from_direct_coil.py`
- `src/coilforge/phase2a/drawing_populator.py`
- `tests/test_phase2b_drawing_intent_bridge.py`
- `docs/PHASE2B_DRAWING_INTENT_BRIDGE.md`

## 3. DrawingIntent Shape

`DrawingIntent` includes:

- `coil_name`
- `product_type`
- `coil_type`
- `header_type`
- `airflow_direction`
- `finned_height`
- `finned_length`
- `rows_deep`
- `fins_per_inch`
- `tubes_high`
- `coil_hand`
- `return_connection_size`
- `drawing_parameters`
- `title_block`
- `notes`
- `source_evidence_summary`
- `review_status`
- `preview_allowed`
- `export_allowed`
- `blocked_reasons`

## 4. DirectCoilInputDraft To DrawingIntent Flow

The bridge reads only explicit Direct Coil draft fields and an explicit `DrawingParameterSet`. Title-block metadata such as `coil_name`, `model_number`, and `source_case_id` may be supplied as explicit metadata because those values are not Direct Coil drawing fields.

Mapped values are passed into a Phase 2A `DxHeader1ParameterState` by `src/coilforge/phase2a/drawing_populator.py`.

## 5. SVG Renderer Behavior

When `preview_allowed` is true, the bridge calls the existing Phase 2A SVG renderer. Changing `finned_height`, `finned_length`, or `coil_name` affects the rendered SVG output.

When `preview_allowed` is false, the bridge returns a blocked preview result with no SVG string.

## 6. Preview Allowed Behavior

Preview is allowed only when the drawing parameter resolver says required preview parameters are present and the Direct Coil draft has no critical blockers such as unsupported `header_type`.

Required drawing parameters can be provided only through mapped draft values, manual review-required values, or explicit sanitized default preview values.

## 7. Export Blocked Behavior

`export_allowed` remains false for both `DrawingIntent` and preview metadata. The bridge does not create Direct Coil export, PDF export, or released drawing output.

## 8. Review Watermark Policy

Rendered previews use the existing Phase 2A renderer, which keeps `REVIEW AID - NOT FOR MANUFACTURING` visible. John drawing semantics review remains pending.

## 9. Known Limitations

- No PDF export is implemented.
- No Direct Coil final export is implemented.
- No UI is added.
- No parser or OCR is implemented.
- No new coil/header types are added.
- Unsupported headers remain blocked.
- No production drawing approval is claimed.
- OAL remains review-required and is not derived.

## 10. Remaining John Review Items

- Confirm Phase 2A SVG layout and title block wording.
- Confirm drawing semantics for `CD`, `BF`, `TF`, and `CH`.
- Confirm whether sanitized default preview values are acceptable for review-aid rendering.
- Confirm any future manual override approval workflow before export-like behavior.

## 11. Next Recommended Phase

Recommended next phase: Phase 2B.9 drawing preview review packet serialization.

Scope:

- Serialize `DrawingIntent` and SVG preview metadata into a stable local review packet.
- Keep PDF export, Direct Coil final export, UI, parser/OCR, new coil/header types, and production approval out of scope.
