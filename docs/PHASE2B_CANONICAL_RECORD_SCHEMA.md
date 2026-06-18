# Phase 2B Canonical Coil Record Schema

Status: Phase 2B.3B schema/test baseline.

Scope: Canonical schema and validation rules only. This phase does not implement a PDF parser, OCR, UI, Direct Coil export, PDF export, drawing workflow, or raw data changes.

## 1. Implementation Result

Phase 2B.3B adds the first code-level `CanonicalCoilRecord` baseline and canonical validation rules so future submittal candidates and sanitized EZ JSON imports can normalize into one shared CoilForge core.

## 2. Canonical Schema Summary

`CanonicalCoilRecord` includes:

- `record_id`
- `project`
- `coil_identity`
- `product_type`
- `coil_type`
- `header_type`
- `geometry`
- `airside_conditions`
- `refrigerant_conditions`
- `materials_construction`
- `connections`
- `manufacturing_options`
- `drawing_parameters`
- `performance`
- `source_evidence`
- `unmapped_fields`
- `review_required_fields`
- `blocked_fields`
- `manual_overrides`
- `validation_status`

The model reuses Phase 2B.3A `FieldValue` and `SourceEvidence` and preserves unmapped fields from submittal candidate records.

## 3. Field Group Mapping

The validation layer maps Direct Coil field keys into canonical record paths:

- Coil Geometry -> `geometry.*`
- Materials & Construction -> `materials_construction.*` or `connections.*`
- Airside Conditions -> `airside_conditions.*`
- Refrigerant Conditions -> `refrigerant_conditions.*`
- Manufacturing Options -> `manufacturing_options.*`
- Drawing Parameters -> `drawing_parameters.*`
- Header type -> top-level `header_type`
- Product and coil classification -> top-level `product_type` and `coil_type`

All current required Direct Coil registry fields are representable in the canonical path map.

## 4. Source Evidence Usage

Imported or prepopulated canonical values use `FieldValue.source_evidence`. `FieldValue` continues to reject imported/prepopulated values that do not include source evidence.

Canonical source evidence remains sanitized and separate from normalized interpretation. Raw customer/project text, raw PDFs, rendered pages, spreadsheets, and raw exports remain out of scope.

## 5. Validation Rules

`coilforge.validation.canonical_rules` provides:

- `CANONICAL_REQUIRED_GROUPS`
- `CANONICAL_DIRECT_COIL_FIELD_MAP`
- `validate_canonical_record`
- `apply_canonical_validation`

Rules currently check:

- Missing required Direct Coil fields are blocked.
- Required fields that need source evidence are blocked when evidence is absent.
- Unsupported `header_type` values are blocked.
- Inferred or unreviewed `product_type`, `coil_type`, and `header_type` remain review-required.
- Numeric/dimensional fields with expected units are blocked when required and unitless, or review-required when optional and unitless.
- Existing review-required and blocked field states are preserved.

## 6. Review-Required Policy

Submittal-derived and inferred values remain review-required unless a future deterministic approved rule sets a stronger status. Inferred `product_type`, `coil_type`, and `header_type` are not final engineering values.

## 7. Blocked Policy

Missing required fields from the Direct Coil registry are blockable. Unsupported headers are blockable. Required unit-bearing numeric values are blocked when units are missing.

Blocked fields prevent the canonical record from being considered validated for downstream adapter work.

## 8. Unmapped Policy

Unknown or unmapped source fields are preserved in `unmapped_fields`. They must not be silently dropped during canonical normalization, future Direct Coil draft creation, drawing intent generation, or JSON import/export.

## 9. Known Placeholders

- No parser exists in this phase.
- No OCR exists in this phase.
- No UI is added in this phase.
- No Direct Coil draft mapper exists yet.
- No Direct Coil export exists in this phase.
- No drawing workflow changes are included.
- Canonical path names are baseline paths for representability and may need engineering review before production-like adapter use.
- Manual override reviewer identity should use sanitized IDs until John approves a durable reviewer metadata policy.

## 10. Next Recommended Phase

Recommended next phase: Phase 2B.3C candidate-to-canonical normalization helper.

Scope:

- Convert a sanitized `SubmittalCoilCandidate` into `CanonicalCoilRecord`.
- Preserve evidence, review-required state, blockers, and unmapped fields.
- Keep parser, OCR, UI, Direct Coil export, and drawing generation out of scope.
