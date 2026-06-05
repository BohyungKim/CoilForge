# CoilForge Drawing Template Spec

Status: Phase 1C draft for engineering review.

Created: 2026-06-05.

Scope: Template requirements for a future simple 2D SVG drawing populator. This spec does not implement drawing generation and does not create production manufacturing drawings.

## Evidence Used

- `Case/EZC-0001` through `Case/EZC-0015`
- `outputs/phase0_category_assessment/rendered_pages`
- `outputs/phase0_reference_lock`
- `docs/REFERENCE_CASE_SET.md`
- `docs/DRAWING_LABEL_DICTIONARY.md`

Phase 1A dependency: no Phase 1A output files were present. This template therefore defines zones and review requirements, not final JSON-to-dimension rules.

## Template Purpose

The Phase 1 drawing template should produce review-ready engineering aids that make drawing population explainable, inspectable, and markable. Generated drawings remain engineering review aids until formally approved by John/engineering.

## Drawing Coordinate System

Use a simple normalized 2D SVG coordinate system:

- SVG root coordinate origin is top-left.
- `x` increases right.
- `y` increases down.
- Use a fixed sheet viewBox for MVP, recommended `0 0 1600 1200` to match the existing rendered review image proportions.
- Treat drawing dimensions as inch values in data, then convert to SVG coordinates through a template-zone scale.
- Keep geometric scale local to each drawing zone. The full sheet is not required to be one universal inch-to-pixel scale because the reference drawings use multiple scaled views on one sheet.
- Preserve dimension text values as reviewed data strings. Do not recompute or round unless a Phase 1A/1B rule explicitly defines it.

Recommended layer order:

1. Sheet frame and title-block grid.
2. Static panel headings.
3. Coil geometry strokes.
4. Header/connection/detail geometry.
5. Dimension guide lines and arrows.
6. Dimension labels.
7. Airflow arrows.
8. Notes/callouts.
9. Markup overlay.
10. Review watermark and metadata.

## Template Zones

| Zone | Approximate role | Required for MVP | Notes |
| --- | --- | --- | --- |
| `sheet_frame` | Outer drawing border. | Yes | Include safe margin for review export. |
| `top_left_callouts` | Hole, coating, lug, distributor extension callouts. | Yes | Conditional text list; source-backed only. |
| `top_center_disclaimer` | Legacy interference disclaimer area. | Review required | Decide whether to preserve vendor wording or replace with CoilForge review language. |
| `top_header_view` | Top/header/connection layout. | Yes | Must support DX distributor/header, HGRH supply/return, and water supply/return variants. |
| `front_view` | Main front coil face. | Yes | Primary large view with face dimensions and airflow arrows. |
| `side_view` | Connection/side view at right of front view. | Yes | Must support one or more connection stems and suffix dimension labels. |
| `right_spec_panel` | Materials, circuiting, connection sizes, weight, volume. | Yes | Text-heavy panel; needs controlled wrapping. |
| `bottom_dimension_table` | Dimension code table. | Yes | Must include core code columns even if some values are blank or review-required. |
| `bottom_notes` | Notes block. | Yes | Source-backed or review-entered text only. |
| `title_block` | Coil ID, tag, WO, qty, item, rev, model. | Yes | Review drawing revision should not imply manufacturing release. |
| `review_metadata` | Watermark/status/provenance. | Yes | CoilForge-specific addition for markup-readiness. |

## Front View Assumptions

Current evidence shows a large front coil face in the lower-left/middle drawing area with:

- Outer casing/fin-pack rectangle.
- Blue dimension lines and labels around the face.
- Dimension labels such as `FH`, `FL`, `CH`, `CL`, `OAL`, `TF`, `BF`, `HF`, `RF`, and `RB`.
- Grey airflow arrows on the face in several rendered pages.

Assumptions to preserve as unapproved:

- The front view is the primary review view, not necessarily a manufacturing-scale projection.
- Left-hand/right-hand model suffixes may require mirroring; do not assume the visible reference orientation applies to all future drawings.
- Header/connection side placement should come from reviewed canonical fields or explicit template parameters, not from category alone.

## Side View Assumptions

Current evidence shows a side/connection view to the right of the main front view. It can include:

- Vertical header/connection stems.
- Multiple connection rows for multi-header or multi-circuit references.
- Dimension labels such as `I`, `S`, `O`, `R` and suffix variants.
- Supply/return geometry for HGRH, CWC, and HWC.
- Distributor/return geometry for DX.

Assumptions to preserve as unapproved:

- Side view location is consistent enough for MVP template zones, but connection geometry rules require Phase 1A/engineering review.
- Suffix labels such as `I3`, `S5`, `O6`, and `R6` should be data-driven and may appear only for multi-connection layouts.
- Vent/drain symbols on CWC/HWC should be visually reviewed before generator support is treated as accepted.

## Airflow Arrow Convention

MVP convention:

- Render at least one labeled `AIRFLOW` arrow near the top/side view.
- Render front-view grey airflow arrows only when the template category or reviewed drawing style calls for them.
- Store airflow direction as explicit data, for example `left`, `right`, `up`, or `down`, rather than deriving from model suffix or category.
- If direction is unknown, render a review warning in metadata instead of choosing a direction silently.

Current uncertainty:

- The locked rendered pages show airflow arrows, but the orientation-to-coil-hand rule is not confirmed.
- John must visually confirm whether CoilForge should preserve CoilMaster arrow placement exactly, use a normalized CoilForge convention, or mirror based on coil hand.

## Header and Connection Display Convention

MVP display must separate these concepts:

- `coil_category`: DX, HGRH, CWC, HWC.
- `header_type`: Header 1, Header 2, Header 3, Header 4, UNKNOWN.
- `feed_type`: Single Feed, Non-Single Feed, UNKNOWN, NOT_APPLICABLE.
- `special_feature`: HGBP, ASC source evidence, None, UNKNOWN.

Category conventions:

- DX: show distributor block, return connection block, distributor extension callouts, and DX-specific circuit labels.
- HGRH: show supply and return connection blocks; keep feed type separate from header type.
- CWC: show supply and return connection blocks plus vent/drain review notes where source-backed.
- HWC: show supply and return connection blocks plus MPT/vent/drain review notes where source-backed.

Do not generate:

- DX Header 4 until a reference exists.
- HGRH Header 3 or Header 4 until references or John-approved rules exist.
- HGRH Single Connection from Single Feed evidence.
- Any extra supply/return/header geometry not backed by reviewed data.

## Dimension Label Placement

MVP placement rules:

- Use blue text for dimension labels to match locked reference drawings.
- Place dimension labels outside or just inside dimension lines so text does not overlap geometry.
- Keep a stable text baseline and minimum gap from strokes.
- Use leader/dimension lines with arrow or tick endpoints.
- Use suffix labels exactly as provided, for example `SL1`, `SL2`, `I3`, `O4`, `R6`.
- Place bottom table values in the same code order:
  `ROWS`, `X`, `FH`, `FL`, `CH`, `CL`, `CD`, `HD`, `OAL`, `SL`, `I`, `S`, `O`, `R`, `TF`, `BF`, `HF`, `RF`, `RB`.
- If a value is missing, leave the table cell blank or mark `TBD` only when review status allows it. Do not invent a value.

Review-required placement items:

- Exact dimension-code definitions.
- Header suffix numbering.
- Whether to show all suffix dimensions in the bottom table or only base code values.
- How to avoid label collisions on small coils such as EZC-0005 and EZC-0006.

## SVG Output Strategy

Use SVG as the primary MVP drawing artifact:

- Store the generated review drawing as one SVG file.
- Keep text as SVG text elements, not converted outlines, so labels remain inspectable and searchable.
- Assign stable IDs to every generated label and geometry group, for example `label.FH.front`, `zone.right_spec_panel`, `connection.supply.1`.
- Include data attributes for source field, confidence, and review status when available.
- Keep geometry simple: lines, rectangles, polylines, arrows, circles, and text.
- Use CSS classes for drawing layers such as `dimension-line`, `dimension-label`, `coil-geometry`, `connection-geometry`, `callout`, `review-warning`.
- Include a visible watermark such as `REVIEW AID - NOT FOR MANUFACTURING` until a future approval workflow explicitly changes it.

## PDF Export Strategy

PDF export should be secondary to SVG for Phase 1 MVP.

Recommended staged approach:

1. Phase 1C: Define requirements only.
2. MVP renderer: Generate SVG first and validate labels/geometry in SVG.
3. Optional MVP PDF: Export the SVG to PDF using a deterministic browser or vector renderer after SVG visual review passes.
4. Future: Add PDF/A or release-grade formatting only after John approves the drawing workflow and approval semantics.

PDF requirements:

- PDF must preserve vector text when feasible.
- PDF must include the review watermark.
- PDF must not remove provenance or review-state metadata from the package.
- PDF must be treated as an export view, not the canonical drawing source.

## Markup-Readiness Requirements

Generated drawing packages should support engineer markup and review:

- Stable object IDs for labels, dimensions, geometry, and zones.
- A visible review status and timestamp.
- A sidecar metadata payload listing source fields, normalized fields, review status, and unresolved assumptions.
- Adequate whitespace around title block and drawing zones for redline comments.
- Searchable text labels in SVG/PDF.
- No hidden auto-approval flags.
- Optional markup layer in SVG with separate group ID such as `markup.review`.
- Revision/status naming that distinguishes draft, validated, John-reviewed, and approved.

## Minimum MVP Template Set

The safest MVP template path is:

1. `direct_coil_dx.svg` for DX Header 1/2/3 and HGBP source-evidence display.
2. `direct_coil_hgrh.svg` for HGRH Header 1/2 with feed-type separation.
3. `direct_coil_water.svg` for CWC/HWC Header 1 variants.

This can be reduced to one parameterized `direct_coil_base.svg` only if the renderer keeps category logic separate and the template remains readable.

## Review Gate

John/engineering must visually review:

- Airflow direction and mirroring.
- Header and connection side placement.
- Distributor extension display.
- Vent/drain display.
- Dimension-code meanings and suffix numbering.
- Whether legacy CoilMaster wording should remain in CoilForge-generated review drawings.
