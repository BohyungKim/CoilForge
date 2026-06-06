# Phase 2B Submittal Candidate Schema

Status: Phase 2B.3A schema/test baseline.

Scope: Code-level schema baseline, sanitized fixture, and tests only. This phase does not implement a PDF parser, OCR, UI, Direct Coil export, PDF export, supplier integration, raw data changes, or drawing generation changes.

## 1. One-Line Implementation Result

Phase 2B.3A adds review-first `SourceEvidence`, `FieldValue`, and `SubmittalCoilCandidate` models plus one sanitized DX/Header 1 candidate fixture.

## 2. Files Changed

- `src/coilforge/contracts/__init__.py`
- `src/coilforge/contracts/evidence.py`
- `src/coilforge/contracts/field_value.py`
- `src/coilforge/submittal/__init__.py`
- `src/coilforge/submittal/candidate.py`
- `examples/sanitized/submittal_candidate_dx_header1_default.json`
- `tests/test_phase2b_submittal_candidate_schema.py`
- `docs/PHASE2B_SUBMITTAL_CANDIDATE_SCHEMA.md`

## 3. Schema Summary

The schema converts the Phase 2B.2 mapping contract object shapes into Pydantic models. It keeps source evidence separate from normalized field interpretation, requires evidence for imported or prepopulated field values, and preserves review-required, blocked, and unmapped states for future extractor and mapping phases.

## 4. SourceEvidence Model

`SourceEvidence` records sanitized trace metadata:

- `evidence_id`
- `source_type`
- `source_id`
- `source_location`
- `source_page`
- `source_section`
- `source_table`
- `source_key`
- `source_value`
- `normalized_value`
- `unit`
- `confidence`
- `review_status`
- `evidence_status`
- `notes`

Committed fixtures use sanitized identifiers and sanitized source locations only.

## 5. FieldValue Model

`FieldValue` wraps a candidate field value with:

- `value`
- `unit`
- `source_evidence`
- `confidence`
- `status`
- `review_required`
- `blocked_reason`
- `manual_override`
- `notes`

Allowed statuses are `ready`, `review_required`, `blocked`, `unmapped`, and `manual_override`. Allowed confidence values are `confirmed`, `inferred`, `ambiguous`, and `missing`.

Imported or prepopulated values require `source_evidence`. Blocked fields require a `blocked_reason`.

## 6. SubmittalCoilCandidate Model

`SubmittalCoilCandidate` includes:

- `candidate_id`
- `tag`
- `product_type`
- `coil_type`
- `header_type`
- `geometry`
- `airside_conditions`
- `refrigerant_conditions`
- `materials_construction`
- `connections`
- `performance`
- `drawing_parameters`
- `source_evidence`
- `review_required_fields`
- `blocked_fields`
- `unmapped_fields`
- `notes`
- `review_status`

The model applies lightweight blocking policy for missing tags and unsupported header types. It does not parse PDFs or generate downstream Direct Coil or drawing artifacts.

## 7. Sanitized Fixture Summary

`examples/sanitized/submittal_candidate_dx_header1_default.json` contains one sanitized DX/Header 1 candidate using demo identifiers only. It includes representative geometry, airside, refrigerant, connection, and performance values, all with `SourceEvidence` attached. It also includes one preserved unmapped field.

## 8. Review-Required Default Policy

The fixture and models keep extracted or inferred submittal values as `review_required` with candidate evidence. Candidate-level `review_status` defaults to `unreviewed`.

Inferred `product_type`, `coil_type`, and `header_type` are not final engineering values.

## 9. Blocked Policy

Missing required `tag` can be blocked. Unsupported `header_type` values can be blocked using the current Direct Coil registry support policy, which allows `Header 1` only in this baseline.

Blocked `FieldValue` instances require `blocked_reason`.

## 10. Unmapped Field Policy

Unknown source fields are preserved in `unmapped_fields` with sanitized `source_key`, `source_value`, reason, and evidence. They are not silently dropped.

## 11. Raw/Private Data Exclusion Policy

The sanitized fixture must not include raw customer names, real project names, project numbers, raw PDF text, private source documents, raw rendered pages, spreadsheets, raw JSON/TXT exports, or environment data.

`Case/` and `outputs/` are out of scope and must remain unstaged.

## 12. Tests / Validation Results

Validation results:

- `python -m compileall src`: passed.
- `python -m pytest`: passed, 42 tests passed with 1 existing FastAPI/Starlette deprecation warning.
- `git diff --check`: passed before staging.
- `git diff --cached --check`: passed after staging the Phase 2B.3A artifact set.
- `git diff --cached --name-only`: confirmed only the intended Phase 2B.3A artifact files were staged.

## 13. Known Placeholders

- No PDF parser exists in this phase.
- No OCR exists in this phase.
- No UI is added in this phase.
- No Direct Coil export exists in this phase.
- No PDF export exists in this phase.
- Candidate field groups remain intentionally broad until extractor and canonical mapping phases refine them.
- Source locations are sanitized placeholders, not real PDF regions.

## 14. Remaining John/Engineering Review Items

- Confirm whether the field grouping is sufficient for the next extractor fixture.
- Confirm acceptable source location naming conventions for sanitized PDF candidates.
- Confirm whether `reviewed` and `rejected` review statuses are sufficient for future engineering review metadata.
- Confirm how manual overrides should reference reviewer identity without committing private names.

## 15. Next Recommended Phase

Recommended next phase: Phase 2B.3B sanitized extractor input contract.

Scope:

- Define the narrow sanitized input shape that a future PDF/text extractor must produce.
- Keep parsing, OCR, UI, Direct Coil export, and drawing generation out of scope.
- Add tests that extractor-like payloads can become `SubmittalCoilCandidate` only with evidence and review-required defaults.
