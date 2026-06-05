# CoilForge Phase 1 Merged Specification

Status: Phase 1 merged review draft.

Created: 2026-06-05.

Scope: Merge Phase 1A, 1B, 1C, and 1D outputs into one coherent Phase 1 specification for the next implementation decision. This document does not implement a drawing populator, does not modify raw JSON or PDF files, and does not approve generated drawings for manufacturing.

## Evidence Used

- `outputs/phase1a_json_drawing_linkage`
- `outputs/phase1b_model_design`
- `outputs/phase1c_drawing_spec`
- `outputs/phase1d_contract`
- `schemas/canonical_coil_model.schema.json`
- `schemas/checklist_schema_draft.json`
- `docs/CANONICAL_COIL_MODEL.md`
- `docs/CHECKLIST_SCHEMA.md`
- `docs/DRAWING_LABEL_DICTIONARY.md`
- `docs/DRAWING_TEMPLATE_SPEC.md`
- `docs/CHECKLIST_WORKFLOW.md`
- `docs/JSON_IMPORT_EXPORT_CONTRACT.md`
- `docs/VALIDATION_CONTRACT.md`
- `docs/REFERENCE_CASE_SET.md`
- `outputs/phase0_reference_lock`

## Current Merge Baseline

Phase 1A now exists in this checkout. Some Phase 1B, Phase 1C, and Phase 1D documents contain stale dependency notes saying Phase 1A or Phase 1B files were absent at the time those drafts were created. This merged spec uses the current repository state:

- Phase 1A mapping outputs are present and should supersede "Phase 1A absent" assumptions in older drafts.
- Phase 1B canonical and checklist schema outputs are present and should supersede "Phase 1B schema absent" assumptions in Phase 1D drafts.
- Existing Phase 1B/1C/1D design principles remain valid where they do not conflict with current Phase 1A evidence.

## Locked Reference Coverage

| Category | Locked coverage | Merge disposition |
| --- | --- | --- |
| DX | Header 1: EZC-0001, EZC-0003, EZC-0009. Header 2: EZC-0011. Header 3: EZC-0007. HGBP/ASC: EZC-0013. | Recommended Phase 2 MVP scope. |
| DX Header 4 | No locked reference case. | `PHASE2_BLOCKER` for Header 4 generation. Keep out of MVP. |
| HGRH | Header 1 and Header 2 cases exist, but JSON header geometry is limited and John-confirmed classifications are required. | Defer from Phase 2 MVP. |
| CWC | Header 1: EZC-0014. | Defer from Phase 2 MVP. |
| HWC | Header 1: EZC-0005, EZC-0006, EZC-0015. | Defer from Phase 2 MVP. |

## Merged Architecture

The Phase 1 architecture is:

```text
Manual checklist entry / future Excel import / future PDF extracted draft
    -> checklist draft with source trace
    -> engineer review or John review
    -> reviewed checklist snapshot
    -> canonical model snapshot
    -> generated SVG drawing review aid
    -> validation report
    -> JSON export/import package
    -> revalidation and comparison
```

Required boundaries:

- Raw EZ Coil / CoilMaster JSON and raw PDF files remain reference inputs only.
- The checklist is the near-term user input layer.
- The Canonical Coil Model is the internal source of truth once generated.
- Drawing output is a review aid and must default to `not_approved` or `review_aid_only`.
- JSON import/export preserves workflow repeatability and review state. It must not bypass review or validation.
- Selection calculations are out of scope.

## Field Merge Rules

### Identity And Project Context

| Concern | Merged decision |
| --- | --- |
| Case identity | Use Phase 1B canonical paths under `/case_identity/*` and checklist field IDs such as `coilforge_case_id`, `source_case_id`, `coil_name`, `model_number`, and `item_number`. |
| Title block labels | Map drawing title block labels to reviewed checklist/canonical values: `Coil ID`, `Tag`, `WO #`, `Qty`, `Item`, `Rev`, and model number. |
| Project metadata | Keep `project_name`, `customer_name`, and job/quote metadata optional or future for the DX MVP unless John explicitly requires them. |
| JSON package IDs | Preserve Phase 1D identifiers: `workflow_id`, `checklist_snapshot_id`, `canonical_model_id`, `drawing_generation_run_id`, `validation_report_id`, and package hashes. |

### Classification

| Field | Merged decision |
| --- | --- |
| `coil_category` | Required. Valid MVP value is `DX` only. |
| `header_type` | Required. Phase 2 MVP supports `Header 1`, `Header 2`, and `Header 3` for DX. |
| `feed_type` | Required for schema consistency. For DX MVP use `NOT_APPLICABLE` unless a future DX-specific rule is approved. |
| `normalized_roadmap_bucket` | Derived from reviewed category/header/special-feature fields. |
| `special_feature` / `normalized_special_feature` | Preserve normalized `HGBP` for EZC-0013 by John decision. |
| `source_feature` | Preserve source `ASC` separately from normalized `HGBP`; do not collapse the source evidence. |

### Core Geometry And Dimension Labels

| Drawing label family | Phase 1A evidence | Canonical/checklist disposition | MVP disposition |
| --- | --- | --- | --- |
| `FH`, `FL` | Strong direct mappings in every category. DX uses `Geometry.FH` and `Geometry.FL`. | Map to `physical_geometry.fin_height` and `physical_geometry.fin_length`; drawing labels can bind to reviewed canonical fields. | Safe for DX MVP when source trace and units are preserved. |
| `CH`, `CL`, `CD`, `TF`, `BF`, `RB` | Strong direct mappings in old-schema DX/CWC/HWC cases. | Preserve as physical/drawing dimensions with Phase 1A source trace. | Safe for DX MVP when current Phase 1A direct mappings apply. |
| `HD`, `HD1`, `HD2`, `HDx1` | Strongest mappings use `Geometry.Headers[].HD`, not top-level same-name fields for suffix labels. | Represent per-header dimensions under `headers.items[]`; preserve PDF label aliases. | `JOHN_REVIEW_REQUIRED` for suffix semantics, but use header-array source paths rather than same-name top-level fields. |
| `SL`, `SL1`, `SL2`, `SL3` | Strongest mappings use `Geometry.Headers[].SL[0]`, not top-level `Geometry.SL` for suffix labels. | Represent as per-header dimension/alias data; preserve suffix label as drawing alias. | `JOHN_REVIEW_REQUIRED` for suffix numbering. |
| `I`, `S`, `O`, `R` and suffixes | Strongest DX mappings use `Geometry.Headers[].IO[0]` and `Geometry.Headers[].SR`, not top-level `Geometry.I/S/O/R`. | Store as header/connection offset drawing bindings, not as simple top-level physical geometry fields. | `PHASE2_BLOCKER` if implementation tries to use same-name top-level fields. |
| `OAL` | `Geometry.OAL` is `0` or mismatched in old-schema cases. DX observed formula is `Geometry.CL + Geometry.RB2`. | Keep as `derived_dimensions[]` or `drawing_dimensions.OAL` with explicit rule id and review status. | `JOHN_REVIEW_REQUIRED` before using derived OAL as an active MVP rule. |
| `HF`, `RF` | Phase 1A maps to `Geometry.LEP` or `Geometry.REP` with medium confidence where values overlap. | Keep source path and label alias explicit. | `JOHN_REVIEW_REQUIRED` before treating these as approved engineering meanings. |

### Drawing Label Dictionary

The merged Phase 1 drawing label vocabulary includes:

- Core dimensions: `ROWS`, `X`, `FH`, `FL`, `CH`, `CL`, `CD`, `HD`, `OAL`, `SL`, `I`, `S`, `O`, `R`, `TF`, `BF`, `HF`, `RF`, `RB`.
- Suffix variants: `HD1`, `HD2`, `HDx1`, `SL1`, `SL2`, `SL3`, `I1`, `I3`, `S1`, `S3`, `S5`, `O2`, `O4`, `O6`, `R2`, `R4`, `R6`.
- Right panel labels: `TUBE MATERIAL`, `FIN MATERIAL`, `CASING MATERIAL`, `COIL TUBE FACE`, `CIRCUITING`, `HEADER MATERIAL`, `DISTRIBUTORS`, `RETURN CONN SIZE`, `FASTENER TYPE`, `DRY WEIGHT`, and `INTERNAL VOLUME`.
- Title and notes labels: `Coil ID`, `Tag`, `WO #`, `Qty`, `Item`, `Rev`, model number, `NOTES:`, and `ALL DIMENSIONS ARE IN INCHES`.
- Direction label: `AIRFLOW`.
- Conditional callouts: collared holes, lifting lugs, coating, mounting holes, distributor extensions, and source-backed notes.

For Phase 2 MVP, labels may be present with blank or blocked values only when the validation report explicitly records why the value is missing. Missing labels must not be silently dropped.

### Workflow And Contract Alignment

| Contract area | Merged decision |
| --- | --- |
| Checklist requiredness | Use a DX MVP subset rather than all broad Phase 1B draft fields. Non-DX fields remain optional/future until their category is implemented. |
| Review state | Preserve both Phase 1B traceable-field `review_status` and Phase 1D workflow review statuses through an adapter mapping. Do not flatten review status into booleans. |
| Validation | Use Phase 1D statuses: `unchecked`, `pass`, `warn`, `fail`, `blocked`, and `not_applicable` for field checks; `generated_review_aid` or `generated_with_warnings` for drawings. |
| JSON export | Default future export package should include checklist, canonical model, drawing metadata, validation report, review object, and compatibility object. |
| SVG | Primary drawing artifact for MVP. Use fixed `0 0 1600 1200` viewBox, stable IDs, searchable text, source/review metadata, and visible review watermark. |
| PDF | Optional secondary export after SVG is visually reviewed. |

## Conflict Handling Policy

Use these statuses in Phase 2 planning and implementation:

- `JOHN_REVIEW_REQUIRED`: A product/process/engineering interpretation is needed before the rule can be treated as approved.
- `PHASE2_BLOCKER`: The conflict blocks Phase 2 implementation for the affected feature or bucket.
- `SAFE_TO_DEFER`: The conflict is outside the recommended Phase 2 MVP or can remain documented without blocking the MVP.

See `outputs/phase1_merged_review/phase1_conflict_matrix.md` for the detailed conflict table.

## Recommended Phase 2 MVP

Build the first MVP as a DX drawing populator for locked DX reference cases only:

- DX Header 1: EZC-0001, EZC-0003, EZC-0009.
- DX Header 2: EZC-0011.
- DX Header 3: EZC-0007.
- DX HGBP/ASC: EZC-0013, preserving source `ASC` and normalized `HGBP`.

Keep DX Header 4 out of scope until a reference case is added.

## John Review Required Before Phase 2 Implementation

- Approve whether the DX `OAL = Geometry.CL + Geometry.RB2` observed formula may be used in MVP output.
- Confirm suffix semantics for `HDx1`, `HD2`, `SL1/SL2/SL3`, and `I/S/O/R` variants.
- Decide whether HGBP should be visible on the drawing, metadata-only, or shown in notes while preserving source `ASC`.
- Confirm airflow arrow convention and whether `airflow_direction` must be an explicit checklist field.
- Confirm whether PDF export is optional for MVP or required after SVG validation.
- Confirm exact review watermark/title block wording.

## Out Of Scope For This Merged Spec

- Drawing populator implementation.
- Full selection calculation engine.
- Production drawing approval workflow.
- Raw JSON/PDF edits.
- DX Header 4 generation.
- HGRH, CWC, and HWC drawing generation.
- Hidden/default EZ Coil rules not supported by explicit source evidence or review.
