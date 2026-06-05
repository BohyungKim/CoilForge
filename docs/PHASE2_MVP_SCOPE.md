# CoilForge Phase 2 MVP Scope

Status: Recommended MVP scope from Phase 1 merged review, updated for Phase 2A local web MVP approval.

Created: 2026-06-05.

Goal: Build the smallest useful drawing-populator MVP after John approves this scope. The MVP should prove a checklist-to-canonical-to-validation-to-SVG review-aid workflow for locked DX references only.

## 1. Clarified MVP Intent

The Phase 2 MVP includes a local interactive web application.

The MVP is not limited to command-line SVG generation or static-only file output. The local web UI must allow John to edit parameter values in a checklist-style input panel and see an Oxygen8-style SVG drawing preview update from those values.

The generated drawing should follow an Oxygen8-style review-aid drawing layout, not a manufacturing-approved drawing. Generated drawings remain engineering review aids until formally approved outside the generator.

The first vertical slice is DX Header 1 / EZC-0001 only.

## 2. Phase Split

| Phase | Scope | Implementation boundary |
| --- | --- | --- |
| Phase 2A | Local web app shell + DX Header 1 parameter panel + SVG preview + validation panel. | Supports DX Header 1 / EZC-0001 only. No full selection calculation engine. |
| Phase 2B | Expand to additional locked DX references after Phase 2A review. | Add DX Header 1 expansion cases, DX Header 2, DX Header 3, and DX HGBP only after review. |

Phase 2A should focus on this flow:

```text
Parameter values
    -> checklist snapshot
    -> canonical model snapshot
    -> validation
    -> interactive SVG drawing update
```

Phase 2A is not a heat transfer selection calculation engine.

## 3. Supported Coil Category

Supported category for Phase 2:

- `DX`

Explicitly unsupported for Phase 2:

- DX Header 4
- HGRH
- CWC
- HWC

Unsupported categories or headers should be rejected or blocked with visible validation state.

## 4. Supported Reference Cases

### Phase 2A First Slice

| Bucket | Reference case | Notes |
| --- | --- | --- |
| DX Header 1 | EZC-0001 | First local interactive vertical slice only. |

### Phase 2B Expansion Candidates

| Bucket | Reference cases | Notes |
| --- | --- | --- |
| DX Header 1 | EZC-0003, EZC-0009 | Add only after EZC-0001 workflow and drawing preview are reviewed. |
| DX Header 2 | EZC-0011 | Include after Header 1 template behavior is stable. |
| DX Header 3 | EZC-0007 | Include to exercise multi-header/suffix labels after suffix review. |
| DX HGBP | EZC-0013 | Preserve source `ASC` and normalized `HGBP`; drawing visibility requires John review. |

Do not add DX Header 4 until a locked reference case or John-approved surrogate rule exists.

## 5. Phase 2A User Workflow

1. Start the local web app.
2. Open the browser UI.
3. Load the default DX Header 1 / EZC-0001 parameter set.
4. Edit parameter values in a checklist-style form.
5. See validation state update.
6. See the Oxygen8-style SVG drawing preview update.
7. Generate a checklist snapshot from the current UI state.
8. Generate drawing metadata.
9. Preserve compatibility for future JSON export/import.

## 6. Required Checklist Fields For Phase 2A

The Phase 2A checklist should be a DX Header 1 subset, not the full future platform checklist.

Minimum first-slice fields:

- `coil_name`
- `model_number`
- `coil_category`
- `header_type`
- `rows`
- `fin_height` / `FH`
- `fin_length` / `FL`
- `casing_height` / `CH`
- `casing_length` / `CL`
- `casing_depth` / `CD`
- `top_flange` / `TF`
- `bottom_flange` / `BF`
- `return_bend_allowance` / `RB`
- `coil_hand`
- `airflow_direction`
- `return_connection_size`
- circuiting display text
- notes

Rules:

- `coil_category` must be `DX`.
- `header_type` must be `Header 1` for Phase 2A.
- `airflow_direction` must be explicit and reviewed; do not infer it silently.
- Right-panel values must be source-backed, manually reviewed, unknown, or blocked. Do not invent missing values.
- OAL must remain blocked or visibly warned until John approves a derived rule.

## 7. Required Drawing Preview

Phase 2A should render an interactive SVG review-aid preview with:

- visible review watermark
- title block
- front view placeholder/geometry
- side/header view placeholder/geometry
- dimension labels
- right panel
- validation warning display
- reserved markup layer

SVG requirements:

- Use a fixed `0 0 1600 1200` viewBox unless a later reviewed template changes it.
- Keep text as SVG text, not outlines.
- Use stable IDs for zones, labels, geometry, connection groups, and callouts.
- Include visible watermark: `REVIEW AID - NOT FOR MANUFACTURING`.
- Include release metadata equivalent to `release_status=review_aid_only`.

## 8. Validation Rules

Minimum Phase 2A validation:

- DX only.
- Header 1 only.
- EZC-0001 only as the first default/reference case.
- Unsupported category/header should be blocked.
- Required fields missing should block or warn clearly.
- OAL should be blocked unless approved.
- No silent inference of airflow direction.
- No manufacturing approval language.
- Every populated drawing label must have a source field, reviewed manual value, or approved derived rule.
- `I`, `S`, `O`, `R`, `SL`, and suffix variants must not be populated from misleading same-name top-level fields.
- Generated drawing status must remain `generated_review_aid` or `generated_with_warnings`.
- Drawing release status must remain `not_approved` or `review_aid_only`.
- Imported or edited payloads require revalidation before generation.
- No raw JSON or PDF file is modified.

## 9. Out Of Scope Items

Out of scope for Phase 2A:

- Full selection calculation engine.
- DX Header 2 / Header 3 / HGBP implementation.
- DX Header 4.
- HGRH / CWC / HWC.
- PDF export.
- Submittal PDF extraction.
- Excel import.
- Full JSON import/export adapter.
- Production drawing release.
- Raw EZ Coil / CoilMaster JSON mutation.
- Raw PDF mutation.
- Automatic engineering value invention.
- Hidden/default EZ Coil rules without reviewed evidence.
- CAD-grade drafting.

## 10. Acceptance Criteria

Phase 2A is acceptable when:

- The local web app can be started.
- The browser UI loads.
- The UI loads a sanitized/default DX Header 1 / EZC-0001 parameter set.
- John can edit DX Header 1 parameters.
- The SVG preview updates based on current parameter values.
- A checklist snapshot is generated from current UI state.
- Drawing metadata is generated from the current checklist/canonical state.
- The validation panel shows pass, warn, blocked, and not-applicable statuses where relevant.
- The drawing output includes `REVIEW AID - NOT FOR MANUFACTURING`.
- Unsupported DX buckets and non-DX categories are blocked.
- OAL is blocked or visibly warned until approved.
- No raw data is committed.
- The MVP does not mark drawings as manufacturing-approved.

## 11. John Review Required Before Build

Yes.

John must review:

- DX Header 1 / EZC-0001 first-slice approval.
- OAL derived-rule approval or continued block.
- Header/connection suffix semantics before Phase 2B generalization.
- Airflow direction policy.
- Right-panel requiredness.
- HGBP drawing visibility before Phase 2B HGBP work.
- PDF export priority.
- Review watermark/title block wording.
