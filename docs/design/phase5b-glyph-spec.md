# Phase 5b — per-category glyph spec

Status: **5b-pre design, 2026-06-18.** Authoring only — **no `src/` or test changes in this
step.** Branch `claude/phase5-topology`. Specifies the four NEW styled glyphs deferred from
Phase 5a (`docs/design/ez-drawing-model.md §7.3`). 5a composed every category via the
topology table and drew the non-DX supply as a *plain* `connection_supply` circle (existing
primitive, no new glyph); 5b adds the styled per-category glyphs that render the gated
topology data 5a already sources.

## Re-grounding (read before implementing)

- **Topology + 4-primitive design:** `docs/design/ez-drawing-model.md §7` (esp. §7.2 per-category
  table, §7.3 new-primitive list, §7.4 sourcing audit).
- **Upstream sourcing / buckets:** `src/coilforge/services/topology_slots.py` —
  `topology_drawing_slots()` re-buckets each engine field by its **own** confidence via
  `bucket_for_confidence` (HIGH→`values`, MEDIUM→`review`, LOW/CONFLICT→`blocked`).
  `gated_slot_values()` returns **HIGH only**. Rules: `slot.conn_angle`←`conn_angle` (R-047),
  `slot.vent_drain`←`vent_drain` (R-066/R-067, blocked-first), `slot.HGBP`←`asc` (R-083,
  `"selected"`→`True`), `asc_orientation`←`asc_orientation` (R-084). Rule confidences are in
  `src/coilforge/rules/coil_header_rules.yaml`; the topology feature set per type is in
  `src/coilforge/rules/drawing_topology_rules.yaml` (`features` / `new_primitives` / `extra_slots`).
- **Backend conventions (the invariant the glyphs must obey):** `src/coilforge/drawing/backends/svg.py`.
  Geometry is mapped to CSS by lookup dicts: `_RECT_CLASS`, `_CIRCLE_CLASS = {"connection":"connection"}`
  (circles default to `.header-pipe`), `_SEGMENT_CLASS = {"row":"row","tube_run":"row",
  "nozzle_body":"nozzle","feeder_fan":"feeder","dist_extension":"dist-ext","stub_cap":"stub"}`
  (segments default to `.stub`). `_GLYPH_OBSTACLE_FEATURES` lists segment features that join the
  label de-collision obstacle set; **all circles already join it**. Annotations (text, arrowheads,
  the AIRFLOW arrow) are **fixed pixel size** — never scaled with geometry.
- **Reference visual form:** the locked reference set is `docs/REFERENCE_CASE_SET.md`; the raw EZC
  drawings/images are **NOT in the repo** (`.gitignore` blocks `*.pdf`/PNG/JPG; the mapping-lab
  `source_images/` hold only READMEs). So glyph *shape/size* that is not fixed by a rule or an
  existing primitive is **`[PROPOSED — needs John decision]`**, to be confirmed against the real
  PDF at the 5b eyeball gate (decision-C), never invented into a committed number.

## Binding constraints carried into 5b

1. **3-layer split, backend-swappable.** New glyph *kinds* are emitted by the layout layer as the
   existing generic primitives (`Circle`/`Segment`/`Label`) tagged with a new `feature` string.
   The new **CSS class + glyph styling lives in the SVG backend ONLY** (`_CIRCLE_CLASS` /
   `_SEGMENT_CLASS` / the `<style>` block). The model/layout stay renderer-agnostic; DXF/PDF
   backends map the same `feature` strings their own way. No backend type leaks upward.
2. **Inches / datum-offset only.** Every glyph anchors to a computed datum (supply `I/S`, return
   `O/R`, casing edge, MPT) in inches. No absolute coordinates.
3. **Mirror-covariance.** Placement must reflect under the single `mirror_view_x`. Use
   mirror-covariant expressions (midpoints, `anchor`-flips, signed offsets) — never a hardcoded
   `min(ax,bx)`+fixed anchor. Every glyph is validated LH **and** RH.
4. **Gated-slots-only, fail-closed.** A glyph renders **only** when its driving slot is in the
   `values` (HIGH) bucket. `review`/`blocked`/`None` → **omit + annotate** (review note /
   flagged label), never drawn as confirmed geometry. Same rule as DX `DistModel`/`DistOD`.
5. **Annotation rule.** Glyph *labels* and any arrowheads are fixed-size; only the structural
   geometry scales.

---

## Glyph 1 — `supply_header_port` (HGRH, CWC, HWC)

The styled upgrade of the Phase-5a placeholder: 5a draws the plain-header supply as
`Circle("connection_supply", …)` rendered via the default `.header-pipe` class. 5b gives it a
dedicated class and (optionally) a short manifold stub so a plain header reads distinctly from a
DX distributor and from a return connection.

**1. Visual form + geometry rule**
- **Anchor (derivable):** the supply `I/S` position — identical to the 5a `connection_supply`
  placement (offset `I` from the header edge, spaced `S` along `CD`), in the side (V2) and plan
  (V3) views. Hand-invariant; mirror handles LH/RH.
- **Sizing (derivable):** circle radius = `HDx{id}/2` (supply header diameter), as 5a already
  computes. Missing `HDx` → omit + annotate (unchanged 5a behavior).
- **Composition:** sits where the DX nozzle/fan/extension would sit; the return path
  (`connection_return` + `stub` + `stub_cap`) is unchanged. It must join the de-collision obstacle
  set (it is a circle, so it already does).
- `[PROPOSED — needs John decision]` whether a plain header also draws a **short manifold
  Segment** (a stub linking the port to the tube run) as §7.3 hints (“Circle + short manifold
  Segment”), and if so its **length/orientation in inches**. Not derivable from any slot.
- `[PROPOSED — needs John decision]` the `.header-port` **fill/stroke styling** distinguishing it
  from `.header-pipe`/`.connection` (visual-only; confirm at eyeball gate).

**2. Backend mapping**
- New circle feature `supply_header_port` → add `_CIRCLE_CLASS["supply_header_port"] = "header-port"`.
- If the manifold stub is adopted: segment feature `supply_manifold` → `_SEGMENT_CLASS` entry +
  add to `_GLYPH_OBSTACLE_FEATURES`.
- New `.header-port` CSS class in the `<style>` block (backend only).

**3. Gating rule**
- No dedicated topology slot. Gated by the **standard geometry-slot gate** (`HDx{id}` / `I{id}` /
  `S{id}` present in `values` → draw; missing/REVIEW → omit + annotate). Already fail-closed in
  the model; no rule-ID dependency.

**4. Categories:** HGRH, CWC, HWC (`supply: plain_header` rows in `drawing_topology_rules.yaml`).

---

## Glyph 2 — `conn_angle_glyph` (HGRH)

Renders the HGRH **supply connection angle** (`LAS`).

**1. Visual form + geometry rule**
- **Driving datum:** `slot.conn_angle` = the **string token `"LAS"`** (R-047). This is a
  *classification label, not a geometry value* — it does not encode an angle in degrees.
- **Derivable:** the **label** `LAS` placed as a supply-side data-strip callout (no leader raking
  the port column), mirror-covariant `anchor` flip — same convention as DX `dist_data`.
- `[PROPOSED — needs John decision]` the **angled-segment geometry**: the actual angle (degrees),
  segment length (inches), and attach point relative to the supply port. `LAS` → angle mapping is
  **not in the data**; needs John’s spec or a real-PDF measurement at the eyeball gate. Until
  decided, render **label-only** (the `LAS` callout) and omit the angled segment + annotate
  (`conn_angle geometry: REVIEW REQUIRED`).
- `[PROPOSED — needs John decision]` whether other `SupConnAngle` tokens beyond `LAS` exist and
  need distinct glyphs (reference set only confirms `LAS`).

**2. Backend mapping**
- Segment feature `conn_angle` → `_SEGMENT_CLASS["conn_angle"] = "conn-angle"` + add to
  `_GLYPH_OBSTACLE_FEATURES`. New `.conn-angle` CSS class (backend only). The `LAS` text uses the
  existing `.callout` class (label-only path needs no new class).

**3. Gating rule**
- Glyph/label render **only** when `slot.conn_angle` ∈ `values` (HIGH). **R-047** emits `"LAS"`
  HIGH for HGRH. If it is ever `review`/`blocked` → omit + annotate. (The *angled segment*
  additionally requires the `[PROPOSED]` geometry decision above; the *label* renders on HIGH.)

**4. Categories:** HGRH only (`T-HGRH`, `extra_slots: [conn_angle]`).

---

## Glyph 3 — `vent_port` / `drain_port` (CWC, HWC)

Renders the CWC/HWC **vent/drain** connections near the MPT (main pipe thread/connection).

**1. Visual form + geometry rule**
- **Driving datum:** `slot.vent_drain`. R-066 emits the **string `"Connections"`** at **MEDIUM**
  (review) for all CWC/HWC; R-067 emits it at **LOW** (blocked) for Terra V. **Neither path is
  ever HIGH.** Per the gating rule this means **the geometry glyph never renders under the
  current rules** — `vent_drain` stays a **flagged review label** (CWC/HWC) or **blocked
  omit+annotate** (Terra V). This is the load-bearing finding for this glyph.
- `[PROPOSED — needs John decision]` the **position of the vent and drain ports** (“near MPT”):
  §7.4 records *position unknown → omit+annotate*. No slot sources vent/drain coordinates today.
- `[PROPOSED — needs John decision]` whether a **HIGH source** for vent/drain position should be
  added upstream (a new rule or geometry field) so the glyph can ever leave the review/blocked
  bucket. Until then `vent_port`/`drain_port` are **spec’d but unreachable** — implement the
  backend mapping, but the layout only emits the flagged label, not the ports.
- `[PROPOSED — needs John decision]` port **size** (inches) and whether vent vs drain differ
  visually (e.g. open vs filled small circle).

**2. Backend mapping**
- Circle features `vent_port` / `drain_port` → `_CIRCLE_CLASS` entries `"vent"` / `"drain"`
  (circles already join the obstacle set). New `.vent` / `.drain` CSS classes (backend only).

**3. Gating rule**
- Render the ports **only** when `slot.vent_drain` ∈ `values` (HIGH). **R-066 = MEDIUM →
  review** (label-only, flagged); **R-067 (Terra V) = LOW → blocked** (omit + annotate). So as
  written, **no port geometry is ever drawn** — fail-closed by construction. Cite R-066 / R-067.

**4. Categories:** CWC, HWC (`T-CWC` / `T-HWC`, `extra_slots: [vent_drain]`).

---

## Glyph 4 — `hgbp_bypass` (DX-HGBP)

Renders the DX **hot-gas-bypass / ASC** connection. (Project standard: source `ASC` →
`special_feature = HGBP`; `source_feature = ASC` preserved — `REFERENCE_CASE_SET.md §HGBP/ASC`.)

**1. Visual form + geometry rule**
- **Driving datum:** `slot.HGBP` = **`True`** (R-083 emits `asc = "selected"`, HIGH, only when
  `hot_gas_bypass`; `topology_slots` maps `"selected"`→`True`). This is a **presence flag, not a
  geometry value**.
- **Composition:** DX-HGBP is the full DX distributor drawing **plus** the bypass connection;
  DX-plain geometry is untouched (the bypass is additive).
- `[PROPOSED — needs John decision]` the **bypass glyph form**: where the ASC/bypass connection
  attaches (which header/edge), its size and symbol. R-083 gives presence only; no geometry slot.
- **ASC orientation is BLOCKED (R-084 CONFLICT):** `asc_orientation` is in the `blocked` bucket
  (SOP “Left” vs CHK “LH→UP/RH→DOWN” conflict, deferred per L-041). The glyph must therefore be
  drawn **orientation-agnostic** (or at a neutral anchor) with the orientation **omitted +
  annotated** (`asc_orientation: blocked (review required) — omitted`). Do **not** pick a side.
- `[PROPOSED — needs John decision]` the neutral anchor/orientation to use while R-084 stays
  blocked, confirmed against EZC-0013 at the eyeball gate.

**2. Backend mapping**
- Segment (or small path) feature `hgbp_bypass` → `_SEGMENT_CLASS["hgbp_bypass"] = "hgbp"` + add
  to `_GLYPH_OBSTACLE_FEATURES`. New `.hgbp` CSS class (backend only).

**3. Gating rule**
- Bypass glyph renders **only** when `slot.HGBP` ∈ `values` (HIGH) — **R-083** (only_when
  `hot_gas_bypass`). Orientation never renders: **R-084 CONFLICT → blocked → omit + annotate**.

**4. Categories:** DX-HGBP only (`T-DX-HGBP`, `special: HGBP`, `extra_slots: [HGBP]`).

---

## Regression contract (5b)

- **DX (plain) stays byte-identical.** The `T-DX` path adds **no** new glyph; the
  `tests/golden/phase5_dx_baseline/` snapshots and **E6**
  (`test_dx_output_byte_identical_to_phase4_baseline`, 4 cases: single/multi × LH/RH × V1/V2/V3)
  must stay green through all of 5b. Anchor tag: `phase5a-landed`. Any DX byte change is a defect.
- **Backend-only additions don’t touch DX.** New `_CIRCLE_CLASS`/`_SEGMENT_CLASS`/CSS entries are
  keyed by the new feature strings; DX emits none of them, so DX output is unchanged by
  construction. Adding a class with a *new* key must not alter the default-class fallthrough for
  existing features.
- **Re-baselining is gated on the eyeball.** DX-HGBP and the plain-header categories (HGRH / CWC /
  HWC) are **not** snapshot-frozen until the 5b **real-PDF eyeball gate** (decision-C) accepts
  their drawings against the locked references (EZC-0013 / 0002·0008·0016 / 0014 / 0005). Only
  after John’s eyeball-accept do we capture per-category golden snapshots. Until then those
  categories are covered by feature-set / supply-kind / gating tests, **not** byte-frozen goldens.
- **Mirror equivariance** is asserted LH+RH for every new glyph (existing
  `test_mirror_symmetry_both_views` discipline) before any re-baseline.
- **No re-baseline masks a DX regression:** capturing new non-DX goldens must never edit or
  regenerate the DX baseline.

---

## Consolidated `[PROPOSED — needs John decision]` list

Geometry/visual decisions that are **not derivable** from a rule, slot, or existing primitive —
to be resolved by John and/or measured against the real PDF at the 5b eyeball gate, never invented:

1. **`supply_header_port`** — whether to add a short **manifold stub** segment, and its
   length/orientation (inches).
2. **`supply_header_port`** — `.header-port` fill/stroke styling vs `.header-pipe`/`.connection`
   (visual only).
3. **`conn_angle_glyph`** — the angled-segment **geometry**: `LAS`→angle (degrees), segment
   length, attach point. (No angle in the data; render label-only until decided.)
4. **`conn_angle_glyph`** — whether non-`LAS` `SupConnAngle` tokens exist and need distinct glyphs.
5. **`vent_port`/`drain_port`** — vent and drain **positions** near the MPT (no slot sources them).
6. **`vent_port`/`drain_port`** — whether to add a **HIGH upstream source** for vent/drain so the
   glyph can ever reach the `values` bucket (today R-066=review, R-067=blocked → never drawn).
7. **`vent_port`/`drain_port`** — port **size** (inches) and vent-vs-drain visual distinction.
8. **`hgbp_bypass`** — bypass connection **form**: attach point (header/edge), size, symbol.
9. **`hgbp_bypass`** — the **neutral anchor/orientation** to use while `asc_orientation` (R-084)
   stays CONFLICT/blocked (must not pick a side).

Cross-cutting (not per-glyph): HGRH **Header 3/4 have no locked reference case**
(`REFERENCE_CASE_SET.md` “Cases Requiring Future Data”) — multi-header HGRH glyph geometry cannot
be reference-validated at 5b until such a case exists; flag, don’t infer.
