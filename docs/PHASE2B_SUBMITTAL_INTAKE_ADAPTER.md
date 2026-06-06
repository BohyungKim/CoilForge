# Phase 2B Submittal Intake Adapter

Status: Phase 2B.9 narrow intake adapter MVP.

Scope: sanitized text or sanitized structured input only. This phase does not implement broad PDF parsing, OCR, UI, Direct Coil export, PDF export, drawing generation, or raw data changes.

## 1. One-Line Implementation Result

Phase 2B.9 adds a narrow submittal intake adapter that converts sanitized key/value text or structured sanitized input into review-first `SubmittalCoilCandidate` objects with source evidence.

## 2. Files Changed

- `src/coilforge/submittal/extract.py`
- `src/coilforge/submittal/rules.py`
- `src/coilforge/submittal/__init__.py`
- `examples/sanitized/submittal_text_dx_header1_default.txt`
- `tests/test_phase2b_submittal_intake_adapter.py`
- `docs/PHASE2B_SUBMITTAL_INTAKE_ADAPTER.md`

## 3. Supported Input Assumptions

Supported inputs are sanitized key/value text lines or sanitized structured dictionaries. The adapter does not read PDFs and does not add a PDF text extraction dependency.

Example supported text line:

```text
ROWS_DEEP: 4 rows
```

## 4. Extractor Rules

The rule table supports a narrow DX/Header 1 candidate shape:

- `COIL_TAG`
- `PRODUCT_TYPE`
- `COIL_TYPE`
- `HEADER_TYPE`
- `ROWS_DEEP`
- `FINS_PER_INCH`
- `FINNED_HEIGHT`
- `FINNED_LENGTH`
- `AIRFLOW_DIRECTION`
- `TOTAL_AIR_FLOW_CFM`
- `ENTERING_DRY_BULB_F`
- `REFRIGERANT`
- `COIL_HAND`
- `RETURN_CONNECTION_SIZE`
- `TOTAL_CAPACITY_MBH`

Unknown keys are preserved as unmapped fields.

## 5. Candidate Output Shape

The adapter returns one `SubmittalCoilCandidate` for the sanitized fixture. It populates candidate classification, representative geometry, airside, refrigerant, connection, and performance fields.

## 6. SourceEvidence Behavior

Every extracted value receives `SourceEvidence` with:

- `source_type = submittal_pdf_candidate`
- sanitized `source_id`
- sanitized text line location
- source key and source value
- normalized value and unit when available

Unknown fields also carry source evidence in `unmapped_fields`.

## 7. Review-Required Behavior

Extracted and inferred candidate values default to `review_required`. Product type, coil type, header type, airflow direction, return connection role, and performance values are not treated as final engineering values.

## 8. Blocked Behavior

Missing required tag blocks the candidate. Unsupported `header_type` blocks the candidate through the existing `SubmittalCoilCandidate` policy.

Missing header type is preserved as review-required because this adapter does not infer or approve header semantics without explicit source text.

## 9. Unmapped Behavior

Unknown sanitized keys are preserved in `unmapped_fields` with source key, source value, reason, and evidence. The adapter does not silently drop unmatched lines.

## 10. Known Limitations

- No broad PDF parser is implemented.
- No OCR is implemented.
- No UI is added.
- No Direct Coil export is implemented.
- No PDF export is implemented.
- No drawing generation is implemented.
- Only sanitized key/value text or structured sanitized dictionaries are supported.
- The adapter currently returns one candidate per sanitized input payload.

## 11. Next Recommended Phase

Recommended next phase: Phase 2B.10 intake-to-canonical smoke pipeline.

Scope:

- Run sanitized intake output through the existing candidate-to-canonical and Direct Coil draft readiness pipeline.
- Keep broad PDF parsing, OCR, UI, export, PDF output, drawing generation, and raw data out of scope.
