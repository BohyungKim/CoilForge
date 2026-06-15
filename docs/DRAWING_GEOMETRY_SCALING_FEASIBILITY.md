# Drawing geometry scaling — feasibility (NOT implemented)

**Question (John):** can the *drawn geometry* be extended/narrowed to match the parameter values —
e.g. a 26"-tall coil drawn taller than a 12"-tall coil — rather than only the dimension *numbers*
changing? Is there any way to do this in the current system?

**Short answer:** not today. Geometry is 100% decoupled from values: template population only swaps
`{{slot.X}}` text tokens; every path (coil body, header pipes, arrows) is the reference PDF's fixed
vector artwork. A 12" and a 26" coil render the *same* rectangle with different numbers printed on it.
It is feasible to add proportional scaling of the coil-body region (Option B below) as a review aid,
reusing the path-parsing already in `mirror.py`. This document scopes that; **no code is changed here.**

## Current state (verified)

- **Population is text-only.** `src/coilforge/template_population/slot_population.py` does
  `svg.replace("{{" + slot_id + "}}", value)` — no coordinate math.
- **Seeding copies paths verbatim.** `scripts/seed_templates_from_pdf.py` extracts the PDF page via
  PyMuPDF `get_svg_image()` and only redacts dimension *values* to slot tokens; the geometry `<path>`s
  are copied as-is.
- **Coordinate system.** Templates use `viewBox="0 0 792 612"` (US-letter points, 72 units/inch) and
  every path carries `transform="matrix(1,0,0,-1,0,612)"` (Y-flip to PDF space). The coil-body rectangle
  in `coilmaster_dx_lh_header1/template.svg` is `M231.37 197.01V292.92H351.26V197.01H231.37` — i.e. it is
  drawn at a fixed ~120×96 unit size **regardless of FH/FL**. The drawing is therefore schematic, not
  to-scale.
- **Only existing coordinate logic** is `src/coilforge/template_population/mirror.py`: a region-restricted
  horizontal reflection. Its primitives are directly reusable:
  - `_path_bbox(d)` — parses all numbers out of a path `d`, returns the page-space bounding box.
  - `_text_xy(attrs, inner)` — extracts a `<text>`/`<tspan>` anchor in page space.
  - `_in_region(...)` / `_COIL_REGION = (150, 640, 95, 492)` — restricts edits to the coil drawing area,
    leaving title block / side panel / brand untouched.

## Options

### Option A — full geometry reconstruction (rejected for now)
Generate every path from parameters (body, header pipes, distributor stacks, arrows, dimension lines).
Highest fidelity, but it is effectively a CAD generator — large effort, high risk, and a separate project.
Bézier header pipes and arrow/label collision handling make naive coordinate scaling break.

### Option B — proportional scale of the coil-body region only (RECOMMENDED if/when we do this)
Scale just the main coil rectangle and its FH/FL dimension lines; keep header pipes, title block, side
panel, and brand static.

Sketch (reusing `mirror.py` primitives):
1. Establish the template's reference size once: measured coil-body bbox ↔ the reference FH/FL it was
   seeded from (store per template, e.g. in `template_metadata.json`). Gives `units_per_inch_x/y`.
2. Compute scale factors `sx = target_FL / ref_FL`, `sy = target_FH / ref_FH` (clamp to a sane band, see
   risks).
3. For each `<path>`/`<text>` whose bbox is inside `_COIL_REGION` *and* part of the body (exclude the
   header-pipe sub-region), affine-scale coordinates about the body centroid:
   `x' = cx + (x-cx)*sx`, `y' = cy + (y-cy)*sy`, then rewrite the `d` / anchor.
4. Re-anchor the FH/FL dimension arrows to the new body edges.

Effort: ~300 lines + tests. Output remains **review-aid only** (already watermarked).

## Risks / limits of Option B
- **Arrow & label drift.** Dimension callouts and arrowheads must be re-anchored or they detach from the
  resized body. This is the main fragility.
- **Aspect-ratio distortion.** Beyond roughly ±1.5× the reference aspect ratio the schematic looks wrong
  even when numerically correct. Recommend clamping `sx/sy` and logging when clamped (no silent caps).
- **Header geometry stays fixed.** Pipes/distributors won't grow with the body; acceptable for a reference
  drawing, but a tall coil with a small fixed header looks slightly off.
- **Path parsing is polygonal.** `_path_bbox` assumes line/`V`/`H` segments; any curved sub-paths in the
  body would need proper handling before scaling (the body itself is rectilinear, so low risk if the
  header-pipe sub-region is excluded).

## Recommendation
Defer implementation. When prioritized, do Option B behind a flag, store the per-template reference FH/FL,
reuse `mirror.py`'s `_path_bbox`/`_text_xy`/region filtering, clamp+log scale factors, and keep the
review-aid watermark. Until then the drawings remain schematic: **numbers are exact and logic-derived; the
drawn proportions are illustrative, not to scale.**
