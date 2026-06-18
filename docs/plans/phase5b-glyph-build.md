# Phase 5b — per-category styled glyphs (implementation plan)

> Branch: `claude/phase5-topology`. Builds on landed 5a (tag `phase5a-landed`).
> **Status: plan approved; implementation NOT started (open decisions D1–D4 pending John).**

## Context
5a made composition table-driven and drew the non-DX supply as a *plain* `connection_supply`
circle (no new glyph). 5b adds the styled per-category glyphs that render the gated topology
data 5a already sources (`docs/design/phase5b-glyph-spec.md`, `ez-drawing-model.md §7`). Scope is
**locked** (below); the deliverable is review-aid drawings that visually distinguish HGRH / CWC /
HWC / DX-HGBP from plain DX, while **plain DX stays byte-identical** (E6). Real-PDF fidelity +
final glyph form are tuned at a human **eyeball gate**; non-DX/HGBP goldens are **not** frozen
this phase.

## Locked scope (plan to THIS; do not re-expand)
1. **`supply_header_port`** (HGRH/CWC/HWC) — the one real new styled glyph. `.header-port` CSS
   class. Render = existing header circle (anchor supply `I/S`, `r=HDx/2`, already in 5a) **+** a
   connection **stub of length `SL` (sourced)** ending in a **neutral connection-type marker**.
   MPT-vs-SWT end-fitting (from SUPPLY CONN SIZE) **deferred to eyeball** — neutral marker now,
   do not invent the fitting symbol.
2. **`conn_angle`** (HGRH) — **label-only baseline**: on R-047 `values`, render the token
   (`"LAS"`) as a callout. **Investigation item D2** (do not lock from one reference): is the
   supply connection *angle* geometrically derivable from sourced `SL`+`HD`+anchor? If derivable
   **and** the engine supports it → propose the angled stub; else stay label-only. Review decision.
3. **`hgbp_bypass`** (DX-HGBP) — **presence-annotation, not a geometric redraw**. Presence via
   R-083 (`values`). Render an ASC/HGBP presence marker/callout anchored to the distributor,
   **additive** on the standard DX distributor geometry. Orientation stays **neutral + review
   annotation** (R-084 blocked — never draw a committed ASC angle/side). Must make DX-HGBP (M≥1
   ASC) visually distinct from plain DX (0 ASC) while leaving **plain DX byte-identical**.
4. **vent/drain** (CWC/HWC) — **review annotation, NO positioned port glyph**. Position is a
   tolerance ("≤ 3 in from MPT"), not a coordinate; a positioned port would invent placement. On
   review/blocked, surface the requirement as a note (e.g. `"Vent & Drain required ≤ 3 in from
   MPT — review"`). Upgrades the existing review-bucket path from silent omit → meaningful note.

## Architecture recommendation — ONE parameterized supply connection-stub helper (items 1+2)
**Recommend:** a single layout helper `_supply_connection(port, *, sl, angle=None, end="neutral")`
emitting the port circle + stub Segment + neutral end-marker, parameterized straight (angle=None)
vs angled (angle set, D2). **Rationale:** items 1 and 2 share anchor/`SL`/end-marker and differ
*only* by angle; folding them keeps mirror-covariance + de-collision in one place and avoids
duplicate stub code. Define the stub by **endpoints in inches** (not a stored angle) so
`mirror_view_x` reflects it for free. **Keep `hgbp_bypass` separate** — it is a presence marker on
the DX distributor, semantically and geometrically unrelated to a supply stub; vent/drain is
annotation-only (no primitive). So: 1 shared stub helper + 1 hgbp presence marker + 0 new
primitive for vent/drain.

## Backend additions (SVG backend layer ONLY — engine stays unaware; backend-swappable invariant)
In `src/coilforge/drawing/backends/svg.py` only:
- `_CIRCLE_CLASS["supply_header_port"] = "header-port"`.
- `_SEGMENT_CLASS`: `"supply_conn_stub" → "conn-stub"`, `"supply_conn_end" → "stub"` (neutral),
  `"hgbp_bypass" → "hgbp"`.
- Add the new segment features to `_GLYPH_OBSTACLE_FEATURES` (labels must clear them). Circles
  already auto-join the obstacle set.
- New `<style>` classes: `.header-port`, `.conn-stub`, `.hgbp` (annotation-fixed stroke; never
  scaled). Labels reuse existing `.callout` / `.review` / `.omitted`.
- **No engine/layout type leaks**: model/layout emit only generic `Circle`/`Segment`/`Label` with
  new `feature` strings; DXF/PDF backends will map the same strings later.

## Sourcing prerequisites (gated, fail-closed — confirm before drawing)
- **Supply `SL`:** `schematic_model._make_header` currently hardcodes supply `stub_length=None`.
  Change the **supply branch** to read `slot.SL{id}` (same as returns). **DX-safe:** DX distributor
  supplies have no `slot.SL{odd}` slot → stays `None` → DX byte-identical; the DX distributor path
  never reads supply `stub_length`. Plain headers get `SL` from fixtures/sourcing. (Decision **D1**:
  confirm a supply-`SL` source exists for HGRH/CWC/HWC; if absent → stub omitted+annotated, fail-closed.)
- **HGBP presence (Decision D3):** today `slot.HGBP` ← R-083 (`asc="selected"`, HIGH, only_when
  `hot_gas_bypass` *input*). The human-visible signal is the `"(M ASC)"` count in
  `distributors_display` (M≥1 ⇒ present), which is **not parsed today**. Plan baseline = use
  `slot.HGBP` (R-083) as the gated presence flag (engine stays the source of truth). **Investigate**
  whether to additionally source/cross-check `"(M ASC)"` (parse in `distributor_slots`/
  `topology_slots`) so a 1-ASC fixture is internally consistent. Do not silently draw from the
  string; if added it is a gated source like the rest.
- `conn_angle`/`vent_drain`/`hgbp_selected`/`topo_blocked`/`topo_review_labels` already on
  `CoilGeometry` (5a) — layout reads them; no new carry-fields beyond supply `SL`.

## TDD-first build order (per item: failing tests BEFORE code)
Each item lands as: **(a)** failing tests → **(b)** layout/backend code → **(c)** green + DX guard.
For every item the test set is **4-way**:
- **values-positive:** slot in `values` ⇒ glyph/annotation IS drawn (assert the feature present).
- **review/blocked-negative:** slot in `review`/`blocked`/`None` ⇒ **omitted or annotated, never
  drawn** (assert feature absent + a note present).
- **mutation-proof (gate is load-bearing):** force-promote the driving slot's confidence (or
  monkeypatch `bucket_for_confidence`) and assert the glyph would change bucket — proving the gate,
  not the wiring, controls drawing (mirrors `test_topology_slots.test_disabling_the_gate…`).
- **hand-invariance:** LH and RH both render correctly; `mirror_view_x(LH) == RH` for the new
  features (extend `test_mirror_symmetry_both_views` discipline; endpoints-defined stubs reflect).

**Order:**
1. **Supply connection-stub helper + `supply_header_port`** (HGRH/CWC/HWC). Tests: port circle at
   `I/S` + stub of len `SL` + neutral end on values; `SL` missing → stub omitted+annotated; LH/RH.
2. **`conn_angle` label-only** (HGRH). Tests: `LAS` callout on R-047 values; review/blocked →
   omitted+annotated; mutation-proof; LH/RH anchor flip. **Then D2 investigation** (separate, no
   code unless derivable+approved): if angled stub adopted, add angled-variant tests via the same
   helper (angle param) — else document label-only as the locked baseline.
3. **`hgbp_bypass` presence marker** (DX-HGBP). Tests: marker/callout present + DX-HGBP visually
   distinct from plain DX when `slot.HGBP` ∈ values; orientation NOT drawn + `asc_orientation:
   blocked` note (R-084); plain DX (no HGBP) draws no marker; mutation-proof; LH/RH. **Additive on
   the distributor path** — must not perturb the 0-ASC plain-DX geometry.
4. **vent/drain review annotation** (CWC/HWC). Tests: review (R-066) ⇒ `"Vent & Drain required ≤ 3
   in from MPT — review"` note present, **no positioned port circle/segment**; blocked (R-067 Terra
   V) ⇒ blocked note; never a coordinate. (No new primitive.)

## New fixtures (`examples/sanitized/`, synthetic, reference-only)
- **`dx_hgbp_1asc_*`** — values-positive: `hot_gas_bypass`→R-083 fires (`slot.HGBP=True`) **and**
  `distributors_display` shows `"(1 ASC)"` (fix the existing `dx_hgbp_ezc0013` `"(0 ASC)"`
  inconsistency, or add a new fixture) so presence is internally consistent.
- **`hgrh_*` with R-047 `conn_angle` values** + a supply `SL` (so the stub + `LAS` callout draw).
- **Retain negatives:** plain DX 0-ASC (single + multi-distributor) for the DX-frozen guard;
  CWC/HWC vent/drain review + Terra-V blocked (existing `cwc_header1_terra_v`).

## DX-frozen guard (must hold throughout 5b)
- Plain DX **single and multi-distributor, 0 ASC** stays **byte-identical**. **E6**
  (`test_dx_output_byte_identical_to_phase4_baseline`, 4 cases) stays green; regenerate the 12
  `tests/golden/phase5_dx_baseline/` only to *re-verify identity* (they must be unchanged — a diff
  is a defect, not a re-baseline).
- **How new paths avoid the plain-DX path:** (1) `supply_header_port`/`conn_angle`/vent-drain live
  on the `supply_kind=="plain_header"` branch — DX never enters it. (2) supply-`SL` model read is
  `None` for DX (no slot) → no behavior change. (3) `hgbp_bypass` is gated on `slot.HGBP ∈ values`
  (only fires for DX-HGBP); plain DX has no `slot.HGBP` → marker not emitted → identical bytes.
  (4) backend additions are keyed by new feature strings DX never emits.

## Goldens NOT captured this phase (explicit)
HGRH / CWC / HWC / **DX-HGBP** drawings are **not** snapshot-frozen in 5b. They are covered by
feature-set / gating / hand-invariance tests only. Per-category golden capture is **deferred to
post-eyeball** (decision-C): John eyeball-accepts each against its locked reference
(EZC-0002·0008·0016 / 0014 / 0005 / 0013) before any baseline is committed. Re-baselining must
never edit/regenerate the DX baseline.

## Verification criteria ("done", defined up front)
- All new TDD tests green (the 4-way set per item).
- **E6 green**; the 12 DX goldens regenerate **byte-identical** (single + multi).
- Full suite green (`python -m pytest -q`), no regressions.
- Each glyph: values→drawn, review/blocked→omitted+annotated (never invented); mutation-proof
  red when the gate is disabled; LH==mirror(RH).
- DX-HGBP visually distinct from plain DX (presence marker) with plain DX bytes unchanged.
- Backend-only CSS/primitive additions; engine/layout emit generic primitives only (grep: no
  renderer types above the backend).
- No new committed goldens for non-DX/HGBP categories (eyeball-gated).

## Files (anticipated)
- Edit: `src/coilforge/drawing/schematic_layout.py` (supply-stub helper + plain_header branch;
  hgbp marker on distributor branch; vent/drain note), `src/coilforge/drawing/backends/svg.py`
  (CSS/primitive maps — backend only), `src/coilforge/drawing/schematic_model.py` (supply `SL`
  read), possibly `src/coilforge/services/topology_slots.py` / `distributor_slots.py` (only if D3
  adds `"(M ASC)"` sourcing).
- New: `examples/sanitized/dx_hgbp_1asc_*.json`, an HGRH-with-conn_angle fixture; tests in
  `tests/test_schematic_renderer.py` (glyphs, DX guard) + `tests/test_topology_slots.py`
  (any new sourcing).
- DO-NOT-TOUCH: `tests/golden/phase5_dx_baseline/` except to re-verify identity; the frozen
  template path (`slot_population.py`, the 17 `template.svg`, `pdf_to_template_drawing.py`).

## Open decision points (for John)
- **D2 (headline):** is the HGRH supply connection **angle** geometrically derivable from
  `SL`+`HD`+anchor (or a rule), or is `LAS` a non-numeric orientation token? → angled stub vs
  locked label-only. Don't infer an angle from one reference.
- **D1:** supply-side `SL` source for HGRH/CWC/HWC plain headers — exists upstream, or stub stays
  omitted+annotated?
- **D3:** HGBP presence source — R-083 engine flag alone, or also parse/cross-check `"(M ASC)"`
  from `distributors_display`? (Fix the `"(0 ASC)"` fixture inconsistency either way.)
- **D4:** end-fitting MPT-vs-SWT marker — confirmed neutral-now, symbol at eyeball.
- Cross-cutting: HGRH **Header 3/4** have no locked reference case — multi-header HGRH glyphs
  can't be reference-validated this phase; flag, don't infer.
