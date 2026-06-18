# Phase 1C ChatGPT Review Packet

One-line result: Created a Phase 1C drawing label dictionary, drawing template specification, category template requirements, and SVG/PDF output strategy for future CoilForge drawing population without implementing a renderer.

## Files Inspected

- `AGENTS.md`
- `docs/REFERENCE_CASE_SET.md`
- `docs/PLAN.md`
- `docs/IMPLEMENTATION.md`
- `docs/PHASE1_PARALLEL_EXECUTION_PLAN.md`
- `outputs/phase0_reference_lock/locked_reference_case_set.csv`
- `outputs/phase0_reference_lock/john_review_decisions.md`
- `outputs/phase0_category_assessment/case_classification_summary.csv`
- `outputs/phase0_category_assessment/roadmap_coverage_matrix.md`
- `outputs/phase0_category_assessment/json_pdf_conflict_report.md`
- `outputs/phase0_category_assessment/uncertain_cases.md`
- `outputs/phase0_category_assessment/rendered_pages/_contact_sheet_page_2.png`
- `outputs/phase0_category_assessment/rendered_pages/EZC-0001_page_2.png` through `EZC-0015_page_2.png`
- `Case/EZC-0001` through `Case/EZC-0015` source folders

Phase 1A dependency: `outputs/phase1a_json_drawing_linkage` was present but contained no files. Phase 1C proceeded as a draft and marked dimension mappings as review-required where Phase 1A linkage is needed.

## Files Created Or Updated

- `docs/DRAWING_LABEL_DICTIONARY.md`
- `docs/DRAWING_TEMPLATE_SPEC.md`
- `outputs/phase1c_drawing_spec/template_requirements_by_category.md`
- `outputs/phase1c_drawing_spec/drawing_output_strategy.md`
- `outputs/phase1c_drawing_spec/phase1c_chatgpt_review_packet.md`

## 1. Drawing Labels To Support In MVP

MVP should support these label groups:

- Sheet/title labels: `Coil ID`, `Tag`, `WO #`, `Qty`, `Item`, `Rev`, model number, `NOTES:`.
- Common dimension labels: `FH`, `FL`, `CH`, `CL`, `CD`, `HD`, `OAL`, `SL`, `I`, `S`, `O`, `R`, `TF`, `BF`, `HF`, `RF`, `RB`.
- Suffix dimension labels: `HD1`, `HD2`, `HDx1`, `SL1`, `SL2`, `SL3`, `I1`, `I3`, `S1`, `S3`, `S5`, `O2`, `O4`, `O6`, `R2`, `R4`, `R6`.
- Right-panel labels: `TUBE MATERIAL`, `FIN MATERIAL`, `CASING MATERIAL`, `COIL TUBE FACE`, `CIRCUITING`, `HEADER MATERIAL`, `DISTRIBUTORS`, `SUPPLY CONN SIZE`, `RETURN CONN SIZE`, `FASTENER TYPE`, `DRY WEIGHT`, `INTERNAL VOLUME`.
- Drawing direction label: `AIRFLOW`.
- Conditional callouts: `COLLARED HOLES REQUIRED`, `LIFTING LUGS REQUIRED`, `ELECTROFIN COATING REQUIRED`, mounting-hole callouts, and distributor extension callouts.

Important limitation: Dimension-code vocabulary is visible in the locked references, but final JSON-to-label meaning needs Phase 1A linkage or John/engineering review.

## 2. Category-Specific Drawing Differences

DX:

- Requires distributor display and `DISTRIBUTORS` block.
- Often shows `RETURN CONN SIZE` without a matching primary `SUPPLY CONN SIZE` block.
- Supports distributor extension callouts.
- Supports Header 1, Header 2, Header 3, and HGBP/ASC reference handling.
- DX Header 4 remains missing.

HGRH:

- Requires both `SUPPLY CONN SIZE` and `RETURN CONN SIZE`.
- Must preserve `header_type` separately from `feed_type`.
- Single Feed must not be treated as Single Connection.
- Header 1 and Header 2 are covered after John review.
- Single Connection, Header 3, and Header 4 remain missing.

CWC:

- Requires supply/return connection blocks.
- Requires MPT, vent/drain, and single supply/return notes when source-backed.
- Only Header 1 is covered.

HWC:

- Requires supply/return connection blocks.
- Requires MPT, vent/drain, and single supply/return notes when source-backed.
- PHWC/HHWC tags should remain evidence strings unless John confirms separate drawing behavior.
- Only Header 1 is covered.

## 3. Proposed SVG/PDF Approach

SVG:

- Use simple 2D SVG as the canonical MVP drawing artifact.
- Use a fixed `0 0 1600 1200` viewBox for sheet-level layout.
- Keep labels as searchable SVG text.
- Assign stable IDs and data attributes to labels, geometry, and zones.
- Include review watermark and metadata.
- Keep geometry simple: lines, rectangles, polylines, circles, arrows, and text.

PDF:

- Treat PDF as secondary export.
- Recommended MVP default is SVG first; PDF becomes optional after SVG visual review passes.
- PDF must preserve the review watermark and should preserve text when feasible.
- PDF must not imply manufacturing release.

## 4. Risks With Drawing Orientation

- Airflow arrow direction is visible in rendered references but not yet tied to an approved source rule.
- Left-hand/right-hand model suffixes may require mirroring; Phase 1C does not approve a mirroring rule.
- Header and connection placement should not be inferred from category alone.
- Distributor extension numbering must be tied to source evidence and visually reviewed.
- Vent/drain symbols on water coils need review before generator support.
- Small coil drawings can create dimension-label collisions.

## 5. What Must Be Visually Reviewed By John

- Airflow arrow convention and whether future drawings should preserve CoilMaster placement or use a CoilForge convention.
- Front view, side view, and top/header view orientation.
- Header/connection side placement for left-hand and right-hand models.
- DX distributor extension callout placement and numbering.
- HGRH supply/return stubout placement and embedded note values.
- CWC/HWC vent/drain symbol and note placement.
- Whether legacy CoilMaster disclaimer wording should be retained, replaced, or removed in CoilForge-generated review drawings.
- Review watermark/title-block wording for generated draft drawings.

## 6. Questions For John

1. Should CoilForge-generated review drawings preserve the same `AIRFLOW` arrow placement as the CoilMaster references, or should CoilForge define its own normalized convention?
2. Should the top-center CoilMaster interference disclaimer remain, be replaced by CoilForge review-aid wording, or be omitted?
3. For DX HGBP, should `HGBP` be visibly shown on the drawing, or should source `ASC` and normalized `HGBP` remain only in metadata/review notes?
4. Should generated review drawings use one unified base template with category parameters, or separate DX, HGRH, and water-coil templates for easier visual review?
5. Should PDF export be included in the first MVP, or should MVP stop at SVG until layout is validated?
6. What review-state wording should appear in the title block or watermark before a drawing is engineering-approved?

## Recommended Merge-Review Inputs

- `docs/DRAWING_LABEL_DICTIONARY.md`
- `docs/DRAWING_TEMPLATE_SPEC.md`
- `outputs/phase1c_drawing_spec/template_requirements_by_category.md`
- `outputs/phase1c_drawing_spec/drawing_output_strategy.md`
- Future Phase 1A linkage outputs, once available.
- Future Phase 1B canonical model/checklist fields, once available.
- Future Phase 1D review-state/import-export contract, once available.

## Validation Performed

- Confirmed `outputs/phase1a_json_drawing_linkage` had no output files.
- Confirmed locked Phase 0C reference files were present.
- Confirmed rendered page images existed for EZC-0001 through EZC-0015.
- Extracted page-2 PDF text from all 15 locked case PDFs using the bundled Python `pypdf` package.
- Visually inspected the rendered contact sheet and representative DX, HGRH, CWC, and HWC drawing pages.

## John Review Required

Yes.

Reason: Phase 1C defines drawing vocabulary and template assumptions that directly affect future generated drawing appearance. Airflow orientation, header/connection placement, dimension-code meanings, and review-watermark wording must be visually reviewed before implementation.
