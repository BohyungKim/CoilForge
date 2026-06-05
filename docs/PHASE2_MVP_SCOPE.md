# CoilForge Phase 2 MVP Scope

Status: Recommended MVP scope from Phase 1 merged review.

Created: 2026-06-05.

Goal: Build the smallest useful drawing-populator MVP after John approves this scope. The MVP should prove the checklist-to-canonical-to-SVG review-aid workflow for locked DX references only.

## 1. First Supported Coil Category

Supported category:

- `DX`

Supported DX buckets:

- `DX / Header 1`
- `DX / Header 2`
- `DX / Header 3`
- `DX / HGBP`

Explicitly unsupported:

- `DX / Header 4`
- HGRH
- CWC
- HWC

## 2. First Supported Reference Cases

| Bucket | Reference cases | Notes |
| --- | --- | --- |
| DX Header 1 | EZC-0001, EZC-0003, EZC-0009 | Strongest first implementation target. |
| DX Header 2 | EZC-0011 | Include after Header 1 template is stable. |
| DX Header 3 | EZC-0007 | Include to exercise multi-header/suffix labels. |
| DX HGBP | EZC-0013 | Preserve source `ASC` and normalized `HGBP`; drawing visibility requires John review. |

Do not add DX Header 4 until a locked reference case or John-approved surrogate rule exists.

## 3. Required Checklist Fields

The Phase 2 MVP checklist should be a DX-focused subset, not the full future platform checklist.

### Case And Workflow Identity

Required:

- `coilforge_case_id`
- `source_case_id` when using locked reference cases
- `coil_name` or tag
- `model_number`
- `workflow_id`
- `checklist_snapshot_id`
- `review_status`

Optional but supported:

- `item_number`
- `quantity`
- `work_order_number`
- `revision`
- `project_name`

### DX Classification

Required:

- `coil_category = DX`
- `header_type`
- `feed_type = NOT_APPLICABLE` for initial DX cases
- `normalized_roadmap_bucket`
- `reference_status`
- `classification_basis`

Required for HGBP case:

- `normalized_special_feature = HGBP`
- `source_feature = ASC`
- source path or source evidence note for the ASC/HGBP distinction

### Physical Geometry

Required:

- `rows`
- `fin_height`
- `fin_length`
- `fin_density_fpi`
- `casing_height` or drawing `CH`
- `casing_length` or drawing `CL`
- `casing_depth` or drawing `CD`
- `top_flange` or drawing `TF`
- `bottom_flange` or drawing `BF`
- `return_bend_allowance` or drawing `RB`

Required as reviewed drawing bindings, not raw manual inventions:

- `FH`
- `FL`
- `CH`
- `CL`
- `CD`
- `TF`
- `BF`
- `RB`
- `HF`
- `RF`

### Header, Distributor, And Connection Fields

Required:

- `headers.items[]`
- per-header `header_id`
- per-header `role`
- per-header `header_dimension_hd`
- per-header `header_dimension_sl`
- per-header connection offset/source fields that bind to `I`, `S`, `O`, and `R` labels
- `distributors.applies`
- `distributors.items[]` when the DX reference has distributors
- `return_connection_size`
- `circuiting` display text or structured source-backed values

Rules:

- Use `Geometry.Headers[]` for DX header/connection label bindings.
- Do not use top-level same-name `Geometry.I/S/O/R/SL` fields for DX drawing offsets.
- Preserve suffix label aliases exactly as visible in the drawing.

### Right Panel And Notes

Required when source-backed or manually reviewed:

- `tube_material`
- `fin_material`
- `casing_material`
- `casing_gauge`
- `coil_tube_face`
- `circuiting`
- `header_material`
- `distributors`
- `return_connection_size`
- `fastener_type`
- `dry_weight`
- `internal_volume`
- `notes`
- source-backed callouts such as collared holes, lifting lugs, coating, mounting holes, and distributor extension notes

### Orientation

Required before drawing generation:

- `coil_hand`
- `airflow_direction`

If `airflow_direction` is not reviewed, drawing generation should be blocked or the generated SVG must carry a visible validation warning. The MVP must not infer airflow direction silently.

## 4. Required Drawing Labels

The MVP SVG must support these labels and zones for the supported DX cases.

Core sheet/title labels:

- `Coil ID`
- `Tag`
- `WO #`
- `Qty`
- `Item`
- `Rev`
- model number
- `NOTES:`
- `ALL DIMENSIONS ARE IN INCHES`

Core dimension table and drawing labels:

- `ROWS`
- `X`
- `FH`
- `FL`
- `CH`
- `CL`
- `CD`
- `HD`
- `OAL`
- `SL`
- `I`
- `S`
- `O`
- `R`
- `TF`
- `BF`
- `HF`
- `RF`
- `RB`

Suffix labels to support when present in the locked DX references:

- `HD1`
- `HD2`
- `HDx1`
- `SL1`
- `SL2`
- `SL3`
- `I1`
- `I3`
- `S1`
- `S3`
- `S5`
- `O2`
- `O4`
- `O6`
- `R2`
- `R4`
- `R6`

Right-panel labels:

- `TUBE MATERIAL`
- `FIN MATERIAL`
- `CASING MATERIAL`
- `COIL TUBE FACE`
- `CIRCUITING`
- `HEADER MATERIAL`
- `DISTRIBUTORS`
- `RETURN CONN SIZE`
- `FASTENER TYPE`
- `DRY WEIGHT`
- `INTERNAL VOLUME`

Direction and conditional labels:

- `AIRFLOW`
- distributor extension callouts
- collared holes, lifting lugs, coating, and mounting-hole callouts when source-backed
- review watermark

## 5. Required SVG Output

Required output package for each generated MVP drawing:

- `drawing.svg`
- `drawing.metadata.json`
- validation report or validation summary sidecar

SVG requirements:

- Use a fixed `0 0 1600 1200` viewBox.
- Keep text as SVG text, not outlines.
- Use stable IDs for zones, labels, geometry, connection groups, and callouts.
- Include source field, normalized field, confidence, review status, and validation status where available.
- Include visible watermark: `REVIEW AID - NOT FOR MANUFACTURING` unless John approves alternate wording.
- Include a title block status that does not imply manufacturing release.
- Use simple 2D elements: lines, rectangles, polylines, circles, arrows, and text.
- Support a reserved markup layer.

## 6. Optional PDF Export

PDF export is optional for the first MVP.

Recommended approach:

1. Generate and visually validate SVG first.
2. Add PDF export only after SVG labels, zones, and review metadata pass.
3. Preserve searchable text and the review watermark where feasible.
4. Treat PDF as an export view, not the canonical drawing source.

## 7. Validation Rules

Minimum MVP validation:

- Required input fields are present or explicitly `unknown`, `not_applicable`, or `blocked`.
- `coil_category` is `DX`.
- `header_type` is `Header 1`, `Header 2`, or `Header 3`, or the case is the HGBP reference bucket.
- DX Header 4 is rejected as unsupported.
- HGRH, CWC, and HWC are rejected as unsupported for this MVP.
- Every populated drawing label has a source field, reviewed manual value, or derived rule id.
- `FH`, `FL`, `CH`, `CL`, `CD`, `TF`, `BF`, and `RB` bind to Phase 1A-supported direct source paths for DX cases.
- `I`, `S`, `O`, `R`, `SL`, and suffix variants bind through `Geometry.Headers[]` or are blocked.
- Top-level same-name `Geometry.I/S/O/R/SL` values are not used as DX drawing offsets.
- `OAL` is blocked unless John approves the derived DX formula.
- `HGBP` output preserves source `ASC` separately from normalized `HGBP`.
- Generated drawing status is `generated_review_aid` or `generated_with_warnings`.
- Drawing release status remains `not_approved` or `review_aid_only`.
- Imported or edited payloads require revalidation before generation.
- No raw JSON or PDF file is modified.

## 8. Out Of Scope Items

Out of scope for Phase 2 MVP:

- DX Header 4.
- HGRH drawing generation.
- CWC drawing generation.
- HWC drawing generation.
- Full selection calculation engine.
- Production drawing approval or release workflow.
- Raw EZ Coil / CoilMaster JSON mutation.
- Raw PDF mutation.
- Automatic engineering value invention.
- Hidden/default EZ Coil rules without reviewed evidence.
- Full JSON import/export adapter.
- Submittal PDF extraction.
- Excel checklist import.
- CAD-grade drafting.
- Mandatory PDF export.

## 9. Acceptance Criteria

Phase 2 MVP is acceptable when:

- It supports only the approved DX reference buckets and rejects unsupported buckets clearly.
- It can generate review-aid SVG packages for the locked DX MVP reference cases.
- Each SVG contains required zones, required labels, stable IDs, review watermark, and metadata.
- Every populated label has source trace, reviewed checklist provenance, or an approved derived rule.
- Any missing, uncertain, or blocked field is visible in validation output.
- DX `I/S/O/R/SL/HD` labels are not populated from misleading same-name top-level fields.
- DX `OAL` is either approved as a derived rule or blocked with an explicit validation message.
- EZC-0013 preserves `source_feature = ASC` and `normalized_special_feature = HGBP`.
- The MVP does not modify raw JSON or PDF files.
- The MVP does not mark drawings as manufacturing-approved.
- Validation output distinguishes `pass`, `warn`, `fail`, `blocked`, and `not_applicable`.

## John Review Required Before Build

Yes.

John must review:

- DX-only MVP scope.
- OAL derived-rule approval.
- Header/connection suffix semantics.
- Airflow direction policy.
- HGBP drawing visibility.
- Required checklist field subset.
- PDF export priority.
- Review watermark/title block wording.
