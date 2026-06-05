# Validation Contract

Status: Phase 1D design draft.

This document defines validation statuses and validation report behavior for CoilForge checklist, canonical model, drawing generation, and JSON import/export workflows. Validation produces evidence. It does not approve drawings for manufacturing release.

## Source Basis

Inspected inputs:

- `docs/PLAN.md`
- `docs/IMPLEMENTATION.md`
- `docs/REFERENCE_CASE_SET.md`
- `outputs/phase0_reference_lock`

Phase 1B dependency:

- Final canonical fields and checklist requiredness depend on Phase 1B review.
- This contract defines validation behavior and status vocabulary that can be mapped to the final Phase 1B schema later.

## Validation Scope

Validation may check:

- Checklist completeness.
- Checklist type, enum, and unit compatibility.
- Field provenance.
- Engineer review state.
- Canonical model generation readiness.
- Drawing label and feature bindings.
- Rule-derived values where explicit rules exist.
- JSON import/export compatibility.
- Future Direct Coil workflow comparison.

Validation must not:

- Auto-approve drawings.
- Invent missing engineering values.
- Hide missing evidence.
- Treat historical EZ Coil values as automatically authoritative product logic.
- Perform unapproved selection calculations.

## Status Vocabulary

### Field Validation Status

| Status | Meaning |
| --- | --- |
| `unchecked` | Validation has not run or the current value changed after validation. |
| `pass` | The value passed the applicable validation checks. |
| `warn` | The value is usable for review but has uncertainty, missing evidence, or compatibility notes. |
| `fail` | The value conflicts with required checks or expected evidence. |
| `blocked` | Validation could not run because required inputs, mappings, or rules are missing. |
| `not_applicable` | The check does not apply to this coil category, header type, feed type, or workflow stage. |

### Review Status

| Status | Meaning |
| --- | --- |
| `unreviewed` | A value was entered, imported, or extracted but has not been reviewed. |
| `accepted` | The reviewer accepts the value as usable for the next workflow step. |
| `edited` | The reviewer changed the value; both source and edited values must be preserved. |
| `rejected` | The reviewer rejected the value. |
| `unknown` | The value cannot currently be confirmed. |
| `not_applicable` | The field does not apply to the current workflow context. |
| `needs_john_review` | The field or rule needs John or engineering decision before implementation or use. |

### Workflow Validation Status

| Status | Meaning |
| --- | --- |
| `not_started` | No validation run exists. |
| `pass` | All required checks passed and no warnings or failures exist. |
| `pass_with_warnings` | Blocking checks passed, but warnings remain. |
| `fail` | One or more required checks failed. |
| `blocked` | Validation could not complete because required data, schema, mapping, or rules are missing. |
| `stale` | Validation was run against an earlier package version, imported payload, or prior value snapshot. |

### Drawing Status

| Status | Meaning |
| --- | --- |
| `not_generated` | No drawing output exists. |
| `generated_review_aid` | Drawing was generated for engineering review only. |
| `generated_with_warnings` | Drawing was generated but validation warnings remain. |
| `generation_blocked` | Drawing generation should not proceed because required inputs are missing or failed. |
| `rejected_after_review` | Engineer rejected the generated drawing or material parts of it. |
| `engineer_reviewed` | Drawing was reviewed for workflow purposes, not released. |

The default generated drawing release status must remain `not_approved` or `review_aid_only`.

## Severity Levels

| Severity | Intended Use |
| --- | --- |
| `info` | Evidence or trace notes that do not require action. |
| `warning` | Reviewable issue that may allow generation but must be visible. |
| `error` | Failed check that should prevent claiming validation success. |
| `blocking_error` | Missing or contradictory input that should block generation or import acceptance. |

## Check Types

| Check Type | Purpose |
| --- | --- |
| `required_field` | Required checklist or canonical field is present or explicitly unknown/not applicable. |
| `type_check` | Value has expected type. |
| `unit_check` | Value unit is supported or converted by an explicit rule. |
| `enum_check` | Value is within allowed values such as coil category, header type, feed type, or special feature. |
| `provenance_check` | Source value, import origin, manual entry, extraction citation, or derived rule is preserved. |
| `review_state_check` | Required fields have acceptable review status before canonical or drawing generation. |
| `normalization_check` | Normalized value preserves source distinction and known John decisions. |
| `drawing_binding_check` | Drawing label or feature is bound to a canonical field or explicit derived rule. |
| `derived_rule_check` | Derived value can be reproduced from named rule inputs. |
| `reference_case_check` | Workflow classification is compatible with Phase 0C locked reference constraints. |
| `json_contract_check` | JSON import/export envelope, version, required fields, and compatibility metadata are valid. |
| `staleness_check` | Validation matches current checklist, canonical model, and drawing generation hashes. |

## Report Structure

Draft validation report:

```json
{
  "validation_report_id": "val_example",
  "workflow_id": "wf_example",
  "validator_version": "0.1-phase1d-draft",
  "validated_at": "2026-06-05T00:00:00Z",
  "input_snapshot_hash": "hash_example",
  "workflow_validation_status": "pass_with_warnings",
  "summary": {
    "pass_count": 10,
    "warn_count": 1,
    "fail_count": 0,
    "blocked_count": 0,
    "not_applicable_count": 2
  },
  "checks": []
}
```

Each check should include:

```json
{
  "check_id": "chk_required_coil_category",
  "check_type": "required_field",
  "target": "canonical.coil_classification.coil_category",
  "severity": "error",
  "status": "pass",
  "message": "Coil category is present.",
  "evidence_refs": [],
  "source_value": "DX",
  "normalized_value": "DX",
  "expected_value": null,
  "actual_value": "DX",
  "requires_review": false
}
```

## Validation Timing

Validation should run or be marked stale after:

- Checklist draft creation.
- Engineer review/edit.
- Canonical model generation.
- Drawing generation.
- JSON export.
- JSON import.
- Any change to a source value, reviewed value, normalized value, field mapping, rule, generator version, validator version, or schema version.

## Generation Gating Draft

Until John approves final gating, use conservative defaults:

- Drawing generation should be blocked when required fields are blank, rejected, or failed.
- Drawing generation may be allowed with warnings only when the warnings are visible in the drawing package and validation report.
- Unknown or not-applicable required fields must be explicit and reviewed.
- Imported payloads require revalidation before regeneration.
- Future PDF-extracted values cannot trigger generation until reviewed.

## Source And Normalization Checks

Validation should preserve known Phase 0C decisions:

- `coil_category` identifies DX, HGRH, CWC, or HWC.
- `header_type` identifies Header 1, Header 2, Header 3, Header 4, or UNKNOWN.
- `feed_type` identifies Single Feed, Non-Single Feed, UNKNOWN, or NOT_APPLICABLE.
- `special_feature` identifies HGBP, ASC, None, or UNKNOWN.
- HGRH Single Feed is not HGRH Single Connection.
- EZC-0013 source evidence is ASC, while normalized `special_feature` is HGBP by John-confirmed internal standard.

If source and normalized values differ, validation should confirm both are preserved rather than treating the difference as an error by default.

## Drawing Validation

Drawing validation should check:

- Required labels exist when applicable, such as FH, FL, CH, CL, CD, HD, SL, I, S, O, and R when Phase 1A mappings define them.
- Each label has a source or derived rule.
- Display units match expected drawing units.
- Connection/header features match canonical classification where rules exist.
- Unknown or unmapped labels are explicitly reported.
- Drawing package references the checklist and canonical model snapshots used for generation.

When Phase 1A mappings are not available, affected checks should be `blocked`, not `pass`.

## JSON Import / Export Validation

Import validation should:

- Check package envelope fields.
- Check schema version compatibility.
- Check required objects for the requested import mode.
- Mark imported validation stale unless hashes and validator version match.
- Preserve original source and review metadata.
- Warn on unsupported fields instead of dropping them silently.
- Block import when required envelope fields are missing or malformed.

Export validation should:

- Confirm required package sections exist for the selected export mode.
- Confirm unresolved values are represented explicitly.
- Confirm generated drawing values include validation status.
- Confirm approval status is not auto-set.

## Future Submittal PDF Extraction Validation

Future extracted checklist drafts should be validated for:

- Extractor metadata presence.
- Source PDF identity.
- Citation availability.
- Field candidate structure.
- Confidence metadata presence.
- Required engineer review status.

Extraction confidence is separate from validation. A high-confidence candidate can still fail validation or require review.

## John Review Required

John review is required before implementation for:

- Final validation gating rules for drawing generation.
- Whether warnings should allow drawing generation in Phase 1C.
- Exact vocabulary for workflow review vs drawing release.
- Required field list after Phase 1B.
- Label-level checks after Phase 1A.
- Handling of imported payloads with older contract versions.
