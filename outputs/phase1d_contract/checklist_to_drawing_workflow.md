# Phase 1D Checklist To Drawing Workflow

Status: design contract draft.

## One-Line Result

Phase 1D defines a reviewable Direct Coil workflow where checklist drafts become reviewed canonical model snapshots, generated drawing review aids, validation reports, and repeatable JSON import/export packages without auto-approval.

## Inputs Inspected

- `docs/PLAN.md`
- `docs/IMPLEMENTATION.md`
- `docs/REFERENCE_CASE_SET.md`
- `docs/PHASE1_PARALLEL_EXECUTION_PLAN.md`
- `outputs/phase0_reference_lock/locked_reference_case_set.csv`
- `outputs/phase0_reference_lock/john_review_decisions.md`
- `outputs/phase0_reference_lock/phase0c_chatgpt_review_packet.md`

Phase 1B note:

- `outputs/phase1b_model_design` exists but no canonical model draft files were present at inspection time.
- Final canonical field names remain a Phase 1B dependency.

## Workflow Diagram

```text
Manual checklist entry
Excel checklist import
Submittal PDF extracted checklist draft
    -> checklist draft
    -> engineer review / edit
    -> reviewed checklist snapshot
    -> canonical model generation
    -> canonical model snapshot
    -> drawing generation trigger
    -> generated drawing review aid + checklist snapshot
    -> validation report
    -> JSON export
    -> JSON import
    -> revalidation
    -> future Direct Coil workflow comparison
```

## Workflow Contract

| Step | Contract |
| --- | --- |
| Manual checklist entry | Creates checklist fields with manual provenance and unreviewed status until accepted or edited. |
| Excel checklist import | Creates the same checklist draft structure using workbook template and cell mapping metadata. |
| Submittal PDF draft | Future-only interface that proposes values with citations and confidence; no extraction is implemented in Phase 1D. |
| Engineer review/edit | Preserves source values while recording accepted, edited, rejected, unknown, not applicable, or needs John review states. |
| Canonical model generation | Converts reviewed values into draft canonical model sections while preserving source, normalized, derived, and unresolved values. |
| Drawing generation trigger | Generates drawing review aid and checklist snapshot together from the same canonical model snapshot. |
| Validation report | Reports pass, warn, fail, blocked, unchecked, and not applicable evidence without approving the drawing. |
| JSON export | Exports a repeatable workflow package with checklist, canonical, drawing, validation, review, and compatibility metadata. |
| JSON import | Imports package as requiring revalidation; it cannot bypass review or auto-trigger approval. |
| Future comparison | Compares current/imported packages to locked references and future Direct Coil workflow outputs. |

## Required Shared Identifiers

The checklist, canonical model, drawing output, validation report, and JSON package should share:

- `workflow_id`
- `checklist_snapshot_id`
- `canonical_model_id`
- `drawing_generation_run_id`
- `validation_report_id`
- `input_snapshot_hash`
- `schema_version`
- `generator_version`
- `validator_version`

## Drawing Package Requirements

Every generated drawing package should preserve:

- Drawing template id.
- Generator version.
- Checklist snapshot id.
- Canonical model id.
- Drawing element ids.
- Drawing label names.
- Display values.
- Source value references.
- Normalized value references.
- Derived rule ids, when applicable.
- Field-level review status.
- Field-level validation status.
- `drawing_status = generated_review_aid` or `generated_with_warnings`.
- `drawing_release_status = not_approved` or `review_aid_only`.

## Validation Status Summary

Use these field validation statuses:

- `unchecked`
- `pass`
- `warn`
- `fail`
- `blocked`
- `not_applicable`

Use these workflow validation statuses:

- `not_started`
- `pass`
- `pass_with_warnings`
- `fail`
- `blocked`
- `stale`

## Phase 0C Reference Constraints

Future workflow comparison must preserve the locked reference decisions:

- HGRH header type and feed type are separate.
- Single Feed is not Single Connection.
- DX Header 4 is missing or uncertain.
- HGRH Single Connection is missing or uncertain.
- HGRH Header 3 and Header 4 are missing or uncertain.
- EZC-0013 source evidence is ASC, while normalized CoilForge special feature is HGBP by John-confirmed company standard.

## Implementation Boundary

This contract does not implement:

- Web app UI.
- Excel parser.
- Submittal PDF extractor.
- Drawing populator.
- JSON import/export adapter.
- Selection calculations.
- Drawing approval or manufacturing release.

## Dependencies

- Phase 1A must define drawing label mappings and derived-value rules before label-level validation can be fully active.
- Phase 1B must define the final Canonical Coil Model and checklist schema before implementation.
- Phase 1C must define drawing template and populator behavior before generation package fields are final.
- John review is required for gating rules and approval vocabulary.

