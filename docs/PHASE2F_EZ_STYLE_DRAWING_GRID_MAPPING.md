# Phase 2F EZ Style Drawing Grid Mapping

## Scope

This pass uses the local EZ Coil case files as drawing-grid evidence for the current review-aid renderer.

The implementation keeps the existing review-only boundary:

- no raw JSON or PDF files are modified
- no PDF export is enabled
- no Direct Coil final export is enabled
- no production drawing approval is claimed
- OAL remains an observed candidate, not an approved CoilForge formula

## Evidence Used

- `Case/EZC-0001/CDXC-1.txt`
- `Case/EZC-0003/EZC-0003.txt`
- `Case/EZC-0007/CDXC-1.txt`
- `Case/EZC-0009/CDXC-1.txt`
- `Case/EZC-0011/CDXC-2.txt`
- `Case/EZC-0013/CDXC-1.txt`
- `Case/EZC-0001/ai_category_assessment.txt`
- related `ai_category_assessment.txt` files for Header 1, Header 2, Header 3, and HGBP labels
- `outputs/phase1a_json_drawing_linkage/direct_matches.csv`
- `outputs/phase1a_json_drawing_linkage/json_to_drawing_mapping_candidates.csv`

At this checkpoint the local `Case/` folder contains JSON-like `.txt`/`.json` exports and assessment notes, not rendered `.png`, `.jpg`, or `.pdf` drawing images. The renderer therefore uses `Geometry.Headers[]` and the observed label lists as reference evidence instead of pixel tracing a drawing image.

## Implemented Renderer Surface

The Phase 2A SVG renderer now uses an EZ Coil / Coilmaster style drawing grid for the DX Header 1 review preview:

- top-left drawing callouts
- central front view
- top/header view driven by `Geometry.Headers[]`
- side connection view driven by `Geometry.Headers[]`
- right-side specification grid
- bottom dimension table
- bottom title/notes block
- review-only watermark and metadata

The renderer exposes `grid_style_id=ez_coil_dx_header1_candidate` and includes `grid_bindings` metadata so each drawing label can be traced back to a candidate JSON path.

## Why The Previous Preview Was Incomplete

The previous preview showed an EZ-style sheet border, right specification panel, and bottom dimension table, but the header geometry itself was schematic and mostly fixed:

- `zone.side_header_view` rendered static rectangles instead of looping over `Geometry.Headers[]`.
- Header count did not affect the drawing, so Header 1, Header 2, and Header 3 could not visually differ.
- `HDx1`, `HD2`, `SL2`, `I1`, `S1`, `O2`, and `R2` were shown as isolated labels, not as labels attached to visible distributor/return header assemblies.
- Top-level fields such as `Geometry.SL`, `Geometry.I`, `Geometry.S`, `Geometry.O`, and `Geometry.R` are not reliable drawing-label sources for DX connection offsets. The stronger source is `Geometry.Headers[]`, matching Phase 1 decision `D-007`.

The renderer now normalizes `Geometry.Headers[]` into `header_assemblies` and draws each visible supply/distributor or return header as a separate SVG group with source metadata.

## Header Array Rules Observed

| Reference case | Bucket | `Geometry.Headers` count | Visible suffix pattern | Renderer effect |
| --- | --- | ---: | --- | --- |
| `EZC-0001`, `EZC-0003`, `EZC-0009` | DX / Header 1 | 2 | `I1`, `S1`, `O2`, `R2` | One supply/distributor and one return header pair. |
| `EZC-0011` | DX / Header 2 | 4 | `I1/S1/O2/R2`, `I3/S3/O4/R4` | Two header pairs. Still review-blocked by Phase 2A support policy. |
| `EZC-0007` | DX / Header 3 | 6 | `I1/S1/O2/R2`, `I3/S3/O4/R4`, `I5/S5/O6/R6` | Three header pairs. Still review-blocked by Phase 2A support policy. |
| `EZC-0013` | DX / HGBP | 2 | `I1`, `S1`, `O2`, `R2` plus HGBP/ASC context | Draws the pair, but special feature visibility remains John-review-required. |

For DX references with populated `Geometry.Headers[]`:

- supply distributor/header IDs are odd numbers
- return header IDs are even numbers
- `HD` controls the visible header diameter label for that header group
- `SL[0]` controls that header group's stub/extension label when populated
- `IO[0]` controls the inlet/outlet offset label (`I{id}` for supply, `O{id}` for return)
- `SR` controls the spacing label (`S{id}` for supply, `R{id}` for return)
- `IsDistributor=True` causes the supply header diameter label to render as `HDx{id}` for DX distributor evidence

## Value-to-Drawing Effects

| JSON candidate path | Renderer state key | Drawing label | Drawing effect | Status |
| --- | --- | --- | --- | --- |
| `Inputs.Nrows`, `Geometry.Nrows` | `rows` | `ROWS` | Bottom table row count and right-panel row summary. | review-required candidate |
| `Geometry.FH`, `PhysicalData.finHeight` | `fin_height` | `FH` | Front-view fin-pack height label and visual face height. | review-required candidate |
| `Geometry.FL`, `PhysicalData.finLength` | `fin_length` | `FL` | Front-view fin-pack length label and visual face width. | review-required candidate |
| `Geometry.CH` | `casing_height` | `CH` | Front-view casing height label and outer casing height. | review-required candidate |
| `Geometry.CL` | `casing_length` | `CL` | Front-view casing length label and outer casing width. | review-required candidate |
| `Geometry.CD` | `casing_depth` | `CD` | Top/header-view depth label. | review-required candidate |
| `Geometry.TSP` | `top_flange` | `TF` | Top flange label. | review-required candidate |
| `Geometry.BSP` | `bottom_flange` | `BF` | Bottom flange label. | review-required candidate |
| `Geometry.RB`, `Geometry.RB2` | `return_bend_allowance` | `RB` | Return-bend/back allowance label. | review-required candidate |
| `Geometry.Headers[1].HD` | `return_header_diameter` | `HD2` | Return-header diameter label in top/header view. | review-required candidate |
| `Geometry.Headers[0].HD` | `distributor_header_diameter` | `HDx1` | Distributor-header diameter label in top/header view. | review-required candidate |
| `Geometry.Headers[1].SL[0]` | `return_stub_length` | `SL2` | Return stub/header extension label. | review-required candidate |
| `Geometry.Headers[0].IO[0]` | `supply_offset_i1` | `I1` | Supply/distributor inlet offset label. | review-required candidate |
| `Geometry.Headers[0].SR` | `supply_spacing_s1` | `S1` | Supply/distributor spacing label. | review-required candidate |
| `Geometry.Headers[1].IO[0]` | `return_offset_o2` | `O2` | Return-header outlet offset label. | review-required candidate |
| `Geometry.Headers[1].SR`, `Geometry.ReturnConnectionsSize` | `return_spacing_r2` | `R2` | Return-header spacing/connection label. | review-required candidate |
| `Geometry.Headers[]` | `header_assemblies` | `HDx1`, `HD2`, `I1`, `S1`, `O2`, `R2`, etc. | Controls visible header assembly count, role, suffix labels, stubs, and connection markers. | review-required candidate |
| `Geometry.LEP` | `header_face` | `HF` | Header-face offset label. | review-required candidate |
| `Geometry.REP` | `return_face` | `RF` | Return-face offset label. | review-required candidate |
| `Geometry.CL + Geometry.RB2` | `observed_oal` | `OAL` | Shows the EZ reference OAL candidate in the grid. | observed candidate, John review required |

## OAL Policy

The SVG may show the observed EZ reference value `20.25 OAL` for visual grid calibration, but metadata marks `oal_review_status=observed_candidate_review_required`.

This does not approve `Geometry.CL + Geometry.RB2` as a CoilForge formula. Existing validation still blocks active OAL generation through `oal`, `overall_length`, or `overall_length_oal` fields.

## Files Updated

- `src/coilforge/phase2a/ez_style_grid.py`
- `src/coilforge/phase2a/renderer.py`
- `src/coilforge/phase2a/drawing_populator.py`
- `src/coilforge/workflows/submittal_to_drawing.py`
- `examples/sanitized/dx_header1_ezc0001_default.json`
- `tests/test_phase2a_renderer.py`
- `tests/fixtures/accuracy/submittal_to_drawing_expected.json`

## Next Review Items

- Confirm whether OAL can stay visible as an observed candidate while formula approval remains blocked.
- Confirm whether Direct Coil should use one `HD` field for both `HD2` and `HDx1`, or whether Header 1 needs separate Direct Coil aliases.
- Confirm whether right-panel supplier wording should stay Coilmaster-style or move to CoilForge review wording.
