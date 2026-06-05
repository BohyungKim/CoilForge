# CoilForge Drawing Label Dictionary

Status: Phase 1C draft for engineering review.

Created: 2026-06-05.

Scope: Drawing label vocabulary for the future checklist-driven drawing populator. This file does not define approved manufacturing logic and does not implement a renderer.

## Evidence Used

- `Case/EZC-0001` through `Case/EZC-0015`
- `outputs/phase0_category_assessment/rendered_pages`
- `outputs/phase0_reference_lock/locked_reference_case_set.csv`
- `outputs/phase0_reference_lock/john_review_decisions.md`
- `docs/REFERENCE_CASE_SET.md`

Phase 1A dependency: `outputs/phase1a_json_drawing_linkage` exists but has no files in this checkout. Dimension-code meanings below are therefore MVP label vocabulary plus working interpretation, not approved JSON-to-drawing mapping.

## Label Status Levels

| Status | Meaning |
| --- | --- |
| `mvp_required` | Visible across locked references or required for category-specific MVP review drawings. |
| `category_required` | Required for one or more categories but not common to all categories. |
| `conditional` | Required only when source evidence includes the feature. |
| `review_required` | Visible or likely needed, but placement, meaning, or rule is not confirmed. |
| `future_reference_needed` | Needed for a roadmap bucket not covered by the locked reference set. |

## Core Sheet Labels

| Label | Status | Evidence | Drawing role | Review notes |
| --- | --- | --- | --- | --- |
| `AIRFLOW` | `mvp_required` | All rendered drawing pages show an airflow arrow label. | Labels airflow direction on side/top view and supports visual orientation. | Arrow direction must be visually confirmed by John before any renderer treats orientation as authoritative. |
| `Casing Style` | `mvp_required` | Bottom-left row across rendered pages. | Sheet-level casing summary. | Text value is source-driven; do not infer missing casing style. |
| `Stacking Flanges` | `mvp_required` | Bottom-left row across rendered pages. | Sheet-level feature flag. | Boolean display should preserve source value. |
| `ROWS` | `mvp_required` | Bottom dimension table. | Tube/row count row. | Source mapping requires Phase 1A/1B confirmation. |
| `X` | `mvp_required` | Bottom dimension table and selected water/HGRH drawings. | Dimension code column and occasional top-view label. | Meaning is not confirmed in Phase 1C. |
| `FH` | `mvp_required` | Bottom table and front view labels. | Working interpretation: fin height. | Needs Phase 1A confirmation against source fields. |
| `FL` | `mvp_required` | Bottom table and front/top labels. | Working interpretation: fin length. | Needs Phase 1A confirmation. |
| `CH` | `mvp_required` | Bottom table and front view labels. | Working interpretation: casing height. | Needs Phase 1A confirmation. |
| `CL` | `mvp_required` | Bottom table and front view labels. | Working interpretation: casing length. | Needs Phase 1A confirmation. |
| `CD` | `mvp_required` | Bottom table and top/header view labels. | Working interpretation: coil/casing depth. | Needs Phase 1A confirmation. |
| `HD`, `HD1`, `HD2`, `HDx1` | `mvp_required` | Top/header view labels and table. | Header diameter or header depth label family. | Exact suffix semantics require engineering review. |
| `OAL` | `mvp_required` | Bottom table and front view labels. | Working interpretation: overall length. | Needs Phase 1A confirmation. |
| `SL`, `SL1`, `SL2`, `SL3` | `mvp_required` | Top/header view labels and table. | Stub/header extension length label family. | Suffix and category behavior require Phase 1A review. |
| `I`, `I1`, `I3` | `mvp_required` | Side/header connection labels and table. | Inlet or connection offset label family. | Meaning must not be inferred as approved. |
| `S`, `S1`, `S3`, `S5` | `mvp_required` | Side/header connection labels and table. | Supply or spacing label family. | Meaning and suffix behavior require review. |
| `O`, `O2`, `O4`, `O6` | `mvp_required` | Side/header labels and table. | Outlet or connection offset label family. | Meaning and suffix behavior require review. |
| `R`, `R2`, `R4`, `R6` | `mvp_required` | Side/header labels and table. | Return or connection offset label family. | Meaning and suffix behavior require review. |
| `TF` | `mvp_required` | Front view and table. | Top flange or tube face offset label. | Working meaning requires Phase 1A confirmation. |
| `BF` | `mvp_required` | Front view and table. | Bottom flange or bottom offset label. | Working meaning requires Phase 1A confirmation. |
| `HF` | `mvp_required` | Front view and table. | Header/front flange label. | Working meaning requires Phase 1A confirmation. |
| `RF` | `mvp_required` | Front view and table. | Return/front flange label. | Working meaning requires Phase 1A confirmation. |
| `RB` | `mvp_required` | Front view and table. | Rear/bottom/back offset label. | Working meaning requires Phase 1A confirmation. |

## Right-Side Specification Panel Labels

| Label | Status | Categories | Drawing role | Review notes |
| --- | --- | --- | --- | --- |
| `TUBE MATERIAL` | `mvp_required` | DX, HGRH, CWC, HWC | Material block header. | Preserve material text from reviewed source/canonical field. |
| `FIN MATERIAL` | `mvp_required` | DX, HGRH, CWC, HWC | Material block header. | Includes fins per inch, thickness, material, and pattern when available. |
| `CASING MATERIAL` | `mvp_required` | DX, HGRH, CWC, HWC | Material block header. | Gauge and material should be separate fields in canonical model. |
| `COIL TUBE FACE` | `mvp_required` | DX, HGRH, CWC, HWC | Coil tube face count/descriptor. | Source mapping requires Phase 1B/1A alignment. |
| `CIRCUITING` | `mvp_required` | DX, HGRH, CWC, HWC | Circuit/feed/pass summary. | Must preserve category-specific phrasing such as `2 Feed / 24 Pass`, `10 Passes per Feed`, or `C1: 5 Feed`. |
| `HEADER MATERIAL` | `mvp_required` | DX, HGRH, CWC, HWC | Header material block. | Usually `Type L Copper` in locked evidence; do not hard-code as universal. |
| `DISTRIBUTORS` | `category_required` | DX | DX distributor block. | Required for DX references including HGBP/ASC source evidence. |
| `SUPPLY CONN SIZE` | `category_required` | HGRH, CWC, HWC | Supply connection size/type block. | Not shown as a primary right-panel block in DX references reviewed here. |
| `RETURN CONN SIZE` | `mvp_required` | DX, HGRH, CWC, HWC | Return connection size/type block. | DX often shows return only; water/HGRH show supply and return. |
| `FASTENER TYPE` | `mvp_required` | DX, HGRH, CWC, HWC | Hardware block. | Values differ (`Bolts`, `Rivets`). |
| `DRY WEIGHT` | `mvp_required` | DX, HGRH, CWC, HWC | Weight block. | Review-ready value only; not a selection calculation. |
| `INTERNAL VOLUME` | `mvp_required` | DX, HGRH, CWC, HWC | Volume block. | Units vary by category (`ft3`, `Gal`); preserve source unit. |

## Bottom Title Block Labels

| Label | Status | Drawing role | Review notes |
| --- | --- | --- | --- |
| `Coil ID` | `mvp_required` | Internal drawing identifier. | Preserve as source/reference metadata. |
| `Tag` | `mvp_required` | Coil tag/name. | Must match reviewed checklist/canonical tag. |
| `WO #` | `mvp_required` | Work order field. | May be blank in generated review aids if not provided. |
| `Qty` | `mvp_required` | Quantity field. | Source/checklist-driven. |
| `Item` | `mvp_required` | Item number. | Source/checklist-driven. |
| `Rev` | `mvp_required` | Revision field. | Generated review aids should use draft/review revision conventions, not manufacturing release revision unless approved. |
| Model number string | `mvp_required` | Bottom-right model display. | Must preserve source and normalized model distinction when they differ. |
| `NOTES:` | `mvp_required` | Free-text drawing notes. | Notes must be source-backed or review-entered. Do not invent engineering notes. |
| `ALL DIMENSIONS ARE IN INCHES` | `mvp_required` | Dimension unit note. | Required unless future non-inch drawings are explicitly supported. |

## Top-Left Callout Labels

| Label | Status | Evidence | Drawing role | Review notes |
| --- | --- | --- | --- | --- |
| `COLLARED HOLES REQUIRED` | `conditional` | Many locked cases. | Manufacturing/review callout. | Generated drawing should display only when explicitly set. |
| `LIFTING LUGS REQUIRED` | `conditional` | EZC-0007. | Large-coil callout. | Needs checklist/canonical field before generation. |
| `ELECTROFIN COATING REQUIRED` | `conditional` | EZC-0009, EZC-0010, EZC-0011, EZC-0012. | Coating callout. | Preserve as feature/callout, not a material inference. |
| `0.3125 in. MOUNTING HOLES` | `conditional` | Multiple DX/HGRH references. | Mounting hole callout. | Mounting hole size and spacing are separate labels. |
| `MOUNTING HOLE SPACING` | `conditional` | Multiple DX/HGRH references. | Mounting spacing callout. | Preserve exact source spacing. |
| `DISTRIBUTOR N HAS 6" EXTENSION` | `conditional` | DX references including EZC-0001, 0003, 0007, 0009, 0011, 0013. | Distributor-specific extension callout. | `N` must come from distributor evidence, not header count inference. |
| `Coilmaster will revise any drawing that contains component interferences` | `review_required` | All rendered pages. | Legacy vendor disclaimer. | Decide whether CoilForge review drawings should preserve, replace, or omit vendor wording. |

## Category-Specific Label Groups

### DX

MVP labels:

- Common dimension code family: `FH`, `FL`, `CH`, `CL`, `CD`, `HD*`, `OAL`, `SL*`, `I*`, `S*`, `O*`, `R*`, `TF`, `BF`, `HF`, `RF`, `RB`.
- `DISTRIBUTORS`
- `RETURN CONN SIZE`
- Distributor extension callouts.
- Circuiting labels such as `2 Feed / 24 Pass`, `6 Feed / 12 Pass`, `10 Passes per Feed`, and `C1/C2/C3` feed lines.
- HGBP/ASC display support for EZC-0013 source evidence.

Review required:

- DX Header 4 is missing from locked references.
- HGBP normalized label must preserve source evidence `ASC` separately from normalized project feature `HGBP`.
- Header count and distributor extension placement require visual review.

### HGRH

MVP labels:

- Common dimension code family.
- `SUPPLY CONN SIZE`
- `RETURN CONN SIZE`
- HGRH notes such as `Add Headers & Stubouts` when source-backed.
- Circuiting/feed labels including `1 Feed / 24 Pass`, `2 Feed / 14 Pass`, `3 Feed / 16 Pass`, `8 Passes per Feed`, and `C1/C2` feed lines.

Review required:

- HGRH `header_type` and `feed_type` are separate. Single Feed must not be treated as Single Connection.
- HGRH Header 3 and Header 4 are missing from locked references.
- HGRH Single Connection remains missing.
- Header/stubout geometry in notes must be linked by Phase 1A before automatic placement.

### CWC

MVP labels:

- Common dimension code family.
- `SUPPLY CONN SIZE`
- `RETURN CONN SIZE`
- `Vent & Drain installed <= 3" from MPT connection` style note when source-backed.
- `Only 1 Supply and 1 Return connection required` style note when source-backed.
- Circuiting labels with multiple feed/pass rows.

Review required:

- CWC currently has only Header 1 locked reference coverage.
- Vent/drain symbol and placement must be visually reviewed.

### HWC

MVP labels:

- Common dimension code family.
- `SUPPLY CONN SIZE`
- `RETURN CONN SIZE`
- Water/glycol connection notes such as MPT and vent/drain statements when source-backed.
- Circuiting labels such as `1 Feed/ 14 Pass`, `1 Feed/ 12 Pass`, and `1 Feed/ 26 Pass`.

Review required:

- HWC currently has only Header 1 locked reference coverage.
- `PHWC` and `HHWC` naming differences should remain tag/model evidence, not separate engineering categories unless John confirms.

## MVP Label Support Recommendation

The MVP drawing populator should support:

- Sheet/title metadata labels.
- Common dimension labels and suffix variants visible in locked references.
- Right-side material/performance/specification panel labels.
- Bottom dimension table labels.
- `AIRFLOW` arrow label.
- Category-specific connection blocks: DX distributor/return, HGRH supply/return, CWC/HWC supply/return.
- Source-backed callouts and notes.

The MVP should not support:

- DX Header 4 generation.
- HGRH Single Connection generation.
- HGRH Header 3 or Header 4 generation.
- Any production approval stamp.
- Any inferred engineering value without review-state metadata.
