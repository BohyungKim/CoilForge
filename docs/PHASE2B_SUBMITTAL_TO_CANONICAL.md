# Phase 2B Submittal To Canonical Mapper

Status: Phase 2B.4 mapper/test baseline.

Scope: sanitized `SubmittalCoilCandidate` to `CanonicalCoilRecord` mapping only. This phase does not implement a PDF parser, OCR, UI, Direct Coil export, PDF export, drawing generation, or raw data changes.

## 1. Implementation Result

Phase 2B.4 adds a mapper that converts a sanitized submittal candidate into a canonical CoilForge record while preserving source evidence, review-required fields, blockers, and unmapped fields.

## 2. Mapper Flow

1. Accept a validated `SubmittalCoilCandidate`.
2. Create a `CanonicalCoilRecord`.
3. Map candidate tag into `coil_identity.tag`.
4. Map product, coil, and header classification to top-level canonical fields.
5. Copy supported candidate field groups into their canonical groups.
6. Preserve all candidate evidence and unmapped fields.
7. Translate candidate `tag` blocker to `coil_identity.tag`.
8. Apply canonical validation rules and return the validated record or result summary.

## 3. Field Mapping Summary

- `tag` -> `coil_identity.tag`
- `product_type` -> `product_type`
- `coil_type` -> `coil_type`
- `header_type` -> `header_type`
- `geometry` -> `geometry`
- `airside_conditions` -> `airside_conditions`
- `refrigerant_conditions` -> `refrigerant_conditions`
- `materials_construction` -> `materials_construction`
- `connections` -> `connections`
- `performance` -> `performance`
- `drawing_parameters` -> `drawing_parameters`

`manufacturing_options` remains empty unless a future candidate or EZ import contract supplies supported fields.

## 4. SourceEvidence Behavior

Mapped values retain their original `FieldValue.source_evidence`. The mapper also collects candidate-level, mapped-field, and unmapped-field evidence into `CanonicalCoilRecord.source_evidence` by evidence id.

No raw customer/project text, raw PDFs, rendered pages, spreadsheets, or raw exports are introduced.

## 5. Review-Required Behavior

Candidate `review_required_fields` are copied forward. Inferred or unreviewed `product_type`, `coil_type`, and `header_type` remain `review_required` unless a future approved deterministic rule changes them.

Canonical validation may add additional review-required fields such as optional unit-bearing numeric values that are missing units.

## 6. Blocked Behavior

Candidate blockers are preserved. Missing candidate tag is translated to `coil_identity.tag`.

Canonical validation blocks:

- missing required Direct Coil fields,
- unsupported `header_type`,
- missing source evidence on required imported values,
- missing units on required unit-bearing numeric values.

The mapper does not create `DirectCoilInputDraft` and does not render drawings.

## 7. Unmapped Behavior

Candidate `unmapped_fields` are copied into the canonical record. Unknown source fields remain visible for future review and must not be silently dropped.

## 8. Known Limitations

- No PDF parser exists in this phase.
- No OCR exists in this phase.
- No UI is added.
- No Direct Coil export or draft mapper is produced.
- No drawing generation changes are included.
- The sanitized fixture does not yet provide every required Direct Coil drawing parameter, so canonical validation can correctly report blockers.
- Manufacturing options remain empty until a supported source contract supplies those fields.

## 9. Next Phase

Recommended next phase: Phase 2B.5 Direct Coil draft readiness report.

Scope:

- Read a `CanonicalCoilRecord`.
- Report Direct Coil required-field coverage, blockers, and review-required fields.
- Do not export to Direct Coil.
- Do not parse PDFs or render drawings.
