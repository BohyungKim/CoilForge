# JSON Import / Export Contract

Status: Phase 1D design draft.

This document defines a draft JSON import/export contract for repeatable CoilForge Direct Coil checklist, canonical model, drawing, validation, and review workflows. It is not an implementation and does not finalize Phase 1B field names.

## Source Basis

Inspected inputs:

- `docs/PLAN.md`
- `docs/IMPLEMENTATION.md`
- `docs/REFERENCE_CASE_SET.md`
- `outputs/phase0_reference_lock`

Phase 1B dependency:

- `outputs/phase1b_model_design` exists but had no canonical model draft files at inspection time.
- Section names and field keys below are proposed placeholders until Phase 1B is reviewed.

## Goals

- Support repeatable checklist-to-drawing workflows.
- Preserve source values, normalized values, derived values, review state, and validation status.
- Allow JSON export/import without silently approving or changing engineering meaning.
- Support future comparison between CoilForge Direct Coil workflows and historical EZ Coil / CoilMaster references.
- Make compatibility limits explicit.

## Non-Goals

- No selection calculation engine.
- No drawing approval or manufacturing release.
- No raw EZ Coil JSON mutation.
- No PDF extraction implementation.
- No final schema lock before Phase 1B review.

## Package Envelope

Draft package type:

```json
{
  "schema_name": "coilforge.direct_coil.workflow_package",
  "schema_version": "0.1-phase1d-draft",
  "payload_kind": "export",
  "package_id": "pkg_example",
  "workflow_id": "wf_example",
  "created_at": "2026-06-05T00:00:00Z",
  "created_by": "coilforge",
  "source_context": {},
  "checklist": {},
  "canonical_model": {},
  "drawing_generation": {},
  "validation_report": {},
  "review": {},
  "compatibility": {}
}
```

Required envelope fields:

| Field | Required | Purpose |
| --- | --- | --- |
| `schema_name` | yes | Identifies the package contract. |
| `schema_version` | yes | Enables import compatibility checks. |
| `payload_kind` | yes | `export`, `import`, `checklist_draft`, or `comparison_package`. |
| `package_id` | yes | Unique package id. |
| `workflow_id` | yes | Stable workflow id across checklist, model, drawing, validation, and exports. |
| `created_at` | yes | Package creation timestamp. |
| `created_by` | yes | Creating system or user id. |
| `source_context` | yes | Source evidence and workflow origin. |
| `checklist` | conditional | Required for normal workflow packages. |
| `canonical_model` | conditional | Required once canonical generation has occurred. |
| `drawing_generation` | conditional | Required once drawing generation has occurred. |
| `validation_report` | conditional | Required once validation has run. |
| `review` | yes | Review state and approval boundary. |
| `compatibility` | yes | Import/export and workflow comparison limits. |

## Repeatability Rules

JSON export should preserve enough information to repeat or audit a generation run:

- `workflow_id`
- `checklist_snapshot_id`
- `canonical_model_id`
- `drawing_generation_run_id`
- `generator_version`
- `validator_version`
- `contract_version`
- `input_snapshot_hash`
- `export_snapshot_hash`
- Source references for every non-derived value.
- Rule references for every derived value.
- Validation status for every generated drawing value.

Re-importing an exported package should not automatically regenerate drawings. Import should create an imported workflow package marked `requires_revalidation = true`.

## Source Context

`source_context` identifies where the workflow came from:

```json
{
  "source_type": "manual_entry",
  "source_ids": [],
  "reference_case_id": null,
  "reference_case_bucket": null,
  "raw_source_preserved": true,
  "notes": []
}
```

Allowed `source_type` values:

- `manual_entry`
- `excel_checklist_import`
- `submittal_pdf_extraction_draft`
- `coilforge_json_import`
- `historical_ez_coil_reference`
- `mixed`

For historical reference cases, preserve Phase 0C classifications:

- `coil_category`
- `header_type`
- `feed_type`
- `special_feature`
- `source_feature`, when source evidence differs from normalized interpretation.
- `john_confirmed`
- `reference_status`

## Checklist Object

Draft structure:

```json
{
  "checklist_schema_version": "0.1-phase1d-draft",
  "checklist_snapshot_id": "chk_example",
  "template_id": "direct_coil_checklist",
  "template_version": "0.1-draft",
  "entry_mode": "manual_entry",
  "sections": []
}
```

Each checklist section should contain fields:

```json
{
  "section_key": "coil_classification",
  "fields": [
    {
      "field_key": "coil_category",
      "label": "Coil Category",
      "requiredness": "required",
      "value_raw": "DX",
      "value_normalized": "DX",
      "unit": null,
      "source_type": "manual_entry",
      "source_ref": null,
      "entry_status": "entered",
      "review_status": "accepted",
      "validation_status": "unchecked",
      "confidence": null,
      "notes": []
    }
  ]
}
```

Allowed `requiredness` values:

- `required`
- `optional`
- `derived`
- `review_only`
- `future`

Allowed `entry_status` values:

- `blank`
- `entered`
- `imported`
- `extracted_candidate`
- `derived_candidate`
- `unknown`
- `not_applicable`

Allowed field `review_status` values:

- `unreviewed`
- `accepted`
- `edited`
- `rejected`
- `unknown`
- `not_applicable`
- `needs_john_review`

## Canonical Model Object

Draft structure:

```json
{
  "canonical_schema_version": "0.1-phase1d-draft",
  "canonical_model_id": "cm_example",
  "model_status": "draft",
  "source_checklist_snapshot_id": "chk_example",
  "sections": {}
}
```

Proposed draft sections:

- `identity`
- `workflow_context`
- `coil_classification`
- `geometry`
- `connections`
- `headers`
- `materials`
- `performance_inputs`
- `drawing_bindings`
- `source_evidence`
- `derived_values`
- `unresolved_values`
- `review_state`

Each canonical field should preserve:

- `field_key`
- `source_value`
- `reviewed_value`
- `normalized_value`
- `unit`
- `source_refs`
- `derived_rule_id`, when applicable.
- `review_status`
- `validation_status`
- `schema_dependency`

No canonical field should be treated as final until Phase 1B review is complete.

## Drawing Generation Object

Draft structure:

```json
{
  "drawing_generation_run_id": "draw_run_example",
  "drawing_status": "generated_review_aid",
  "drawing_template_id": "direct_coil_template_draft",
  "generator_version": "0.1-draft",
  "generated_at": "2026-06-05T00:00:00Z",
  "input_snapshot_hash": "hash_example",
  "drawing_outputs": [],
  "field_bindings": []
}
```

Allowed `drawing_status` values:

- `not_generated`
- `generated_review_aid`
- `generated_with_warnings`
- `generation_blocked`
- `rejected_after_review`
- `engineer_reviewed`

`engineer_reviewed` means reviewed for workflow purposes only. It does not mean manufacturing release.

Each `field_bindings` entry should preserve:

```json
{
  "drawing_element_id": "label_FH",
  "drawing_label": "FH",
  "canonical_field_key": "geometry.face_height",
  "display_value": "12.00",
  "unit": "in",
  "source_value_ref": "checklist.geometry.face_height",
  "normalized_value_ref": "canonical.geometry.face_height",
  "derived_rule_id": null,
  "review_status": "accepted",
  "validation_status": "unchecked"
}
```

## Validation Report Object

Draft structure:

```json
{
  "validation_report_id": "val_example",
  "validator_version": "0.1-draft",
  "validation_status": "unchecked",
  "summary": {
    "pass_count": 0,
    "warn_count": 0,
    "fail_count": 0,
    "blocked_count": 0
  },
  "checks": []
}
```

The status contract is defined in `docs/VALIDATION_CONTRACT.md`.

## Review Object

Draft structure:

```json
{
  "workflow_review_status": "needs_engineer_review",
  "drawing_release_status": "not_approved",
  "reviewed_by": null,
  "reviewed_at": null,
  "review_notes": [],
  "john_review_required": true
}
```

Allowed `workflow_review_status` values:

- `draft`
- `needs_engineer_review`
- `engineer_reviewed`
- `needs_john_review`
- `rejected`
- `validated_for_next_step`

Allowed `drawing_release_status` values:

- `not_approved`
- `review_aid_only`
- `requires_markup_review`
- `approved_outside_coilforge`

CoilForge generation, validation, import, and export must not set `approved_outside_coilforge`.

## Compatibility Object

Draft structure:

```json
{
  "phase1b_dependency": "canonical_schema_not_present_at_phase1d_inspection",
  "phase1a_dependency": "mapping_rules_not_required_for_this_contract",
  "round_trip_expected": false,
  "requires_revalidation_on_import": true,
  "unsupported_fields": [],
  "warnings": [],
  "reference_case_constraints": []
}
```

Compatibility rules:

- Missing, unknown, unsupported, and not-applicable values must be represented explicitly.
- A value that cannot be mapped should be exported as unresolved, not dropped.
- Import must warn when schema versions differ.
- Import must fail when required envelope fields are missing.
- Import must mark validation stale when canonical or drawing payloads were generated by a different contract version.

## Import Modes

Allowed import modes:

- `resume_workflow_from_export`
- `create_workflow_from_checklist_draft`
- `compare_payload_to_current_contract`
- `compare_payload_to_reference_case`

Import must:

- Preserve original package metadata.
- Create a new import event id.
- Mark imported validation as stale unless the same validator and input hash are confirmed.
- Avoid auto-generating drawings.
- Avoid auto-approving checklist fields.
- Produce an import report with warnings and blocked items.

## Export Modes

Allowed export modes:

- `full_review_package`
- `checklist_only`
- `canonical_model_only`
- `drawing_review_package`
- `validation_report_only`
- `comparison_package`

The default export for Phase 1D design should be `full_review_package` when all artifacts exist.

## Direct Coil Workflow Comparison

Comparison packages should support:

- Current package vs historical Phase 0C reference case.
- Current package vs future Direct Coil workflow standard.
- Imported package vs current contract version.
- Generated drawing bindings vs Phase 1A linkage rules when available.

Comparison statuses:

- `exact_match`
- `normalized_match`
- `derived_match`
- `source_difference`
- `missing_current_value`
- `missing_reference_value`
- `unsupported_bucket`
- `requires_review`

Known reference constraints:

- DX Header 4 is missing or uncertain.
- HGRH Single Connection is missing or uncertain.
- HGRH Header 3 and Header 4 are missing or uncertain.
- HGRH Single Feed is not Single Connection.
- EZC-0013 should preserve `source_feature = ASC` and normalized `special_feature = HGBP`.

## John Review Required

John review is required before implementation for:

- Final package schema name and versioning convention.
- Required import failure vs warning rules.
- Final canonical model section names after Phase 1B.
- Whether checklist-only import can trigger canonical generation after review.
- Drawing release vocabulary.
- How strict round-trip expectations should be for historical EZ Coil / CoilMaster JSON.
