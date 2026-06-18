# Phase 2B Direct Coil Readiness Report

Status: Phase 2B.6 readiness report packet.

Scope: review packet/report model only. This phase does not implement final Direct Coil export, UI, drawing generation, PDF parser, OCR, PDF export, supplier integration, or raw data changes.

## 1. One-Line Implementation Result

Phase 2B.6 adds a Direct Coil readiness report built from `DirectCoilInputDraft`, listing ready, review-required, blocked, and unmapped fields with requiredness and source evidence metadata.

## 2. Files Changed

- `src/coilforge/direct_coil/readiness.py`
- `tests/test_phase2b_direct_coil_readiness_report.py`
- `docs/PHASE2B_DIRECT_COIL_READINESS_REPORT.md`
- `examples/sanitized/direct_coil_readiness_dx_header1_default.json`

## 3. Readiness Report Shape

`DirectCoilReadinessReport` includes:

- `draft_id`
- `source_canonical_record_id`
- `total_fields`
- `summary_counts`
- `ready_fields`
- `review_required_fields`
- `blocked_fields`
- `unmapped_fields`
- `required_missing_fields`
- `source_evidence_summary`
- `drawing_parameter_summary`
- `export_status`

Each field entry preserves `field_key`, `label`, `group`, `required`, `value`, `unit`, `status`, `blocked_reason`, `review_required`, `manual_override`, and `source_evidence`.

## 4. Summary Count Behavior

The report copies draft status counts and verifies the full Direct Coil registry surface remains visible. For the sanitized DX/Header 1 fixture, the expected counts are:

- `ready = 0`
- `review_required = 12`
- `blocked = 4`
- `unmapped = 36`
- `manual_override = 0`

## 5. Ready/Review-Required/Blocked/Unmapped Policy

Ready fields appear only when a mapped canonical value is present, sourced, supported, and not review-required.

Review-required fields preserve candidate/inferred/unreviewed status and source evidence where available.

Blocked fields include required fields missing from the canonical record or fields with explicit blockers.

Unmapped fields include optional Direct Coil registry fields that do not yet have values in the canonical record. They are not hidden.

## 6. Drawing Parameter Blocked Summary

The sanitized fixture does not yet provide the required drawing baseline parameters `CD`, `BF`, `TF`, and `CH`. These fields remain visible in `blocked_fields`, `required_missing_fields`, and `drawing_parameter_summary.blocked_fields`.

## 7. SourceEvidence Behavior

Mapped review-required fields retain `SourceEvidence` from the draft. The report includes `SourceEvidenceSummary` with field-level evidence id lists and total evidence reference counts.

## 8. Export Status Policy

`export_status` remains `not_implemented`. The readiness report is a review packet, not a Direct Coil export payload.

## 9. Tests / Validation Results

Validation results:

- `python -m compileall src`: passed.
- `python -m pytest`: passed, 76 tests passed with 1 existing FastAPI/Starlette deprecation warning.
- `git status --short --branch`: checked before staging; existing `outputs/` remains unstaged.
- `git diff --check`: passed before staging.
- `git diff --cached --check`: passed after staging the Phase 2B.6 artifact set.
- `git diff --cached --name-only`: confirmed only the intended Phase 2B.6 artifact files were staged.

## 10. Known Limitations

- No final Direct Coil export is implemented.
- No UI is added.
- No drawing generation changes are included.
- No PDF parser or OCR is implemented.
- No PDF export or supplier integration is implemented.
- The report does not decide engineering approval; it only exposes readiness state.

## 11. Remaining John/Engineering Review Items

- Confirm whether blocked drawing parameters should remain blocking before any future draft export work.
- Confirm whether optional unmapped fields should be grouped or filtered differently in future UI/report surfaces.
- Confirm required evidence display format for engineering review packets.

## 12. Next Recommended Phase

Recommended next phase: Phase 2B.7 Direct Coil readiness packet serialization.

Scope:

- Serialize the readiness report into a stable JSON or markdown review artifact.
- Keep final export, UI, drawing generation, parser, OCR, PDF export, supplier integration, and raw data changes out of scope.
