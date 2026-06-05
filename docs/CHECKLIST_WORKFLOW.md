# Checklist Workflow Contract

Status: Phase 1D design draft.

This document defines how checklist generation, manual value entry, validation, drawing generation, and JSON import/export should work together for CoilForge Direct Coil workflows. It is contract/design only and does not implement a web app, parser, drawing populator, or PDF extractor.

## Source Basis

Inspected inputs:

- `docs/PLAN.md`
- `docs/IMPLEMENTATION.md`
- `docs/REFERENCE_CASE_SET.md`
- `outputs/phase0_reference_lock/locked_reference_case_set.csv`
- `outputs/phase0_reference_lock/john_review_decisions.md`
- `outputs/phase0_reference_lock/phase0c_chatgpt_review_packet.md`

Phase 1B dependency:

- `outputs/phase1b_model_design` exists at inspection time.
- No Phase 1B canonical model draft files were present at inspection time.
- This document therefore proposes a Phase 1D-compatible draft contract and marks final field names as dependent on Phase 1B review.

## Contract Principles

- Checklist values are the near-term user input layer.
- The Canonical Coil Model is the internal source of truth once generated.
- Source evidence and normalized interpretation must remain separate.
- Manual entry, Excel import, and future submittal PDF extraction all create checklist drafts, not approved engineering data.
- Checklist and drawing outputs should eventually be generated together from the same reviewed canonical model snapshot.
- Every generated drawing must preserve source values, normalized values, field provenance, and validation status.
- JSON import/export must support repeatable review, regeneration, and comparison.
- Drawings are engineering review aids until formally approved outside this contract.
- No drawing should be auto-approved by generation, validation, import, or export.

## Primary Artifacts

| Artifact | Purpose | Approval Boundary |
| --- | --- | --- |
| Checklist draft | Captures user-entered, imported, or extracted values before engineering review. | Never approved by default. |
| Reviewed checklist | Checklist after engineer review/edit decisions are recorded. | Approved only for canonical generation, not for manufacturing release. |
| Canonical model payload | Normalized Direct Coil representation with source, derived, reviewed, and unknown values separated. | Draft until Phase 1B schema is approved. |
| Generated drawing package | Drawing output plus field bindings, source values, and validation status. | Review aid only. |
| Validation report | Explicit pass/warn/fail evidence for checklist, canonical model, drawing labels, rules, and import/export compatibility. | Does not approve drawings. |
| JSON package | Portable import/export envelope for repeatability and workflow comparison. | May resume review but cannot bypass review. |

## Workflow Stages

```text
Manual checklist entry
Excel checklist import
Submittal PDF extracted checklist draft
    -> Engineer review / edit
    -> Canonical model generation
    -> Drawing generation trigger
    -> Validation report generation
    -> JSON export
    -> JSON import
    -> Future Direct Coil workflow comparison
```

## Stage Contract

| Stage | Entry Condition | Output | Required Status |
| --- | --- | --- | --- |
| Manual checklist entry | Engineer or operator enters values directly into checklist fields. | Checklist draft with `source_type = manual_entry`. | `review_status = unreviewed` until explicitly reviewed. |
| Excel checklist import | A future checklist workbook is parsed against a versioned template. | Checklist draft with workbook mapping metadata. | Imported values require engineer review. |
| Submittal PDF extracted checklist draft | Future extractor proposes checklist values from a submittal PDF. | Checklist draft with citations and confidence flags. | Extracted values require engineer review and cannot trigger drawing generation by themselves. |
| Engineer review/edit | User inspects draft values, edits values, accepts/rejects candidates, and records notes. | Reviewed checklist snapshot. | Field-level `review_status` must be captured. |
| Canonical model generation | Reviewed checklist has enough required fields for the selected Direct Coil workflow. | Canonical model payload with field provenance and unresolved values preserved. | `model_status = draft` unless John approves final schema. |
| Drawing generation trigger | Canonical model snapshot is selected for drawing generation. | Checklist package and generated drawing package from the same snapshot. | `drawing_status = generated_review_aid`. |
| Validation report generation | Checklist/canonical/drawing package exists. | Validation report with explicit checks and evidence. | Report may be pass, warn, fail, or blocked. It is not approval. |
| JSON export | Reviewable workflow package exists. | Versioned JSON package preserving checklist, canonical, drawing, validation, and review metadata. | Export must preserve unresolved and non-applicable fields. |
| JSON import | CoilForge receives a versioned JSON package or checklist-only draft. | Imported workflow package or import error report. | Imported content must be revalidated before drawing regeneration. |
| Future Direct Coil workflow comparison | Imported/current workflow package is compared to locked references or future Direct Coil outputs. | Comparison report identifying exact matches, warnings, gaps, and unsupported fields. | Comparison is evidence, not approval. |

## Manual Checklist Entry

Manual entry should produce the same checklist field structure as Excel import and future PDF extraction. Each field should record:

- `field_key`
- `label`
- `value_raw`
- `value_normalized`
- `unit`
- `source_type = manual_entry`
- `source_ref`
- `entry_status`
- `review_status`
- `validation_status`
- `review_notes`

Manual entry may populate required values, optional values, and review-only notes. It must not fabricate derived values. Derived values should be calculated only by explicit rules after the canonical model is generated.

## Excel Checklist Import

Excel import should be treated as a structured checklist draft source. The parser contract should require:

- Workbook template identifier.
- Workbook template version.
- Worksheet name.
- Cell or named-range mapping for each imported field.
- Raw cell value.
- Parsed value and unit.
- Import warning list for blank, ambiguous, unsupported, or malformed values.

Excel import may prefill checklist fields, but imported fields remain unreviewed until an engineer accepts or edits them.

## Future Submittal PDF Extracted Draft

Phase 1D does not implement PDF extraction. The future extractor interface should return a checklist draft with:

- Source PDF identifier.
- Extractor version.
- Extracted field candidates.
- Source citation for each candidate, such as page, bounding region, text snippet, or extraction rule id.
- Confidence score or confidence band.
- Extraction warnings.
- `review_status = unreviewed`.

Extraction confidence is not validation. A high-confidence extraction still requires engineer review before canonical model generation.

## Engineer Review And Edit

The engineer review layer should allow each checklist field to be:

- accepted as entered or imported.
- edited with the edited value recorded separately from the source value.
- rejected as not applicable, unsupported, or incorrect.
- marked unknown when the value cannot be confirmed.
- annotated with review notes.

The reviewed checklist should preserve both the original source value and the reviewed value. Review should not destroy source evidence.

Recommended field-level review statuses:

- `unreviewed`
- `accepted`
- `edited`
- `rejected`
- `unknown`
- `not_applicable`
- `needs_john_review`

## Canonical Model Generation

Canonical model generation converts the reviewed checklist into a normalized Direct Coil model. It should:

- Use only reviewed, accepted, edited, explicitly unknown, or explicitly not-applicable values.
- Preserve source values and review decisions.
- Separate source fields, normalized fields, derived values, and unresolved values.
- Mark fields that depend on missing Phase 1A linkage or Phase 1B canonical schema decisions.
- Avoid selection calculations unless explicitly approved in a later phase.

Until Phase 1B is complete, canonical sections should be treated as draft sections:

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
- `review_state`

## Drawing Generation Trigger

Drawing generation should be triggered from a canonical model snapshot, not directly from raw checklist input. The trigger should produce:

- A generated drawing package.
- A checklist snapshot used for generation.
- A canonical model snapshot used for generation.
- A validation report request.

Checklist and drawing should eventually be generated together, meaning they should share:

- `workflow_id`
- `checklist_snapshot_id`
- `canonical_model_id`
- `generation_run_id`
- `generator_version`
- `input_snapshot_hash`

Each generated drawing label or feature should store:

- Drawing element id.
- Canonical field key.
- Display value.
- Source value reference.
- Normalized value reference.
- Derived rule id, when applicable.
- Validation status.
- Review status.

Drawing generation must set `drawing_status = generated_review_aid` by default. It must not set approval or release status.

## Validation Report Generation

Validation should run after canonical generation, drawing generation, JSON import, and engineer edits. The validation report should:

- Check required field presence.
- Check type, unit, and enum compatibility.
- Check provenance is preserved.
- Check drawing label bindings.
- Check rule-derived values where rules are available.
- Check import/export compatibility.
- Mark unavailable checks as blocked or not applicable rather than passing them silently.

The detailed validation status definitions live in `docs/VALIDATION_CONTRACT.md`.

## JSON Export

JSON export should create a repeatable workflow package containing:

- Checklist snapshot.
- Canonical model snapshot.
- Drawing generation metadata.
- Drawing field bindings.
- Validation report summary or full report reference.
- Review metadata.
- Compatibility limits.

Export must preserve unknown, unsupported, unreviewed, failed, and warning states. It must not flatten those states into blank strings or assume engineering values.

## JSON Import

JSON import should support:

- Reopening a prior CoilForge export.
- Importing a checklist-only draft.
- Importing a canonical-model draft for review.
- Comparing an external or historical payload against the current Direct Coil contract.

Imported packages should be marked `imported` and `requires_revalidation`. Import should not bypass engineer review, canonical generation, or drawing validation.

The detailed payload contract lives in `docs/JSON_IMPORT_EXPORT_CONTRACT.md`.

## Future Direct Coil Workflow Comparison

Future comparison should compare workflow packages against:

- Phase 0C locked reference case classifications.
- Phase 1A JSON-to-drawing mappings, when available.
- Phase 1B canonical fields, when available.
- Phase 1C drawing populator outputs, when available.
- Future Direct Coil standard workflow exports.

Comparison reports should distinguish:

- exact match.
- normalized match with source difference.
- derived match.
- missing source value.
- missing mapping.
- unsupported bucket.
- requires John or engineering review.

Known Phase 0C constraints must be preserved:

- DX Header 4 is missing or uncertain.
- HGRH Single Connection is missing or uncertain and must not be inferred from Single Feed.
- HGRH Header 3 and Header 4 are missing or uncertain.
- EZC-0013 source evidence is ASC, but normalized `special_feature` is HGBP by John-confirmed company standard.

## John Review Required

John review is required before implementation for:

- Final canonical field names and sections after Phase 1B.
- Required vs optional checklist field lists.
- Drawing generation gating rules when validation has warnings or failures.
- Whether `accepted` checklist values are enough for generation or whether every required field must be explicitly `engineer_reviewed`.
- The exact approval vocabulary for engineering review vs manufacturing release.
- JSON import compatibility limits for historical EZ Coil / CoilMaster payloads.
