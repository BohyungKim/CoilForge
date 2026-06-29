# CoilForge MVP Finalization Checklist

> Living checklist for finalizing the template-first MVP. Tick items as they close.
> Tags: **[MVP]** = required for MVP sign-off · **[EXT]** = extends beyond the MVP
> use-case set · **[DEFER]** = explicitly post-MVP (do not let these creep in).
>
> See `CLAUDE.md` → *CoilForge MVP taxonomy (confirmed 2026-06-21)* for the rules this
> checklist operationalizes. Last anchored: 2026-06-21.

## 0. MVP use-case set (multiple paths)

The MVP is anchored on the **10 currently-seeded review-aid templates** (everything in
`template_population/catalog.ACTIVE_TEMPLATES`), all **Nova / Ventum H** family
(family-agnostic template selection):

| Use case | Seeded template | Source |
| --- | --- | --- |
| DX · 1 header · LH | `coilmaster_dx_lh_header1` | EZC-0001 |
| DX · 2 header · RH | `coilmaster_dx_rh_header2` | EZC-0011 |
| DX · 3 header · LH | `coilmaster_dx_lh_header3` | EZC-0007 |
| DX · HGBP · LH | `coilmaster_dx_lh_hgbp` | EZC-0013 |
| HGRH · 1 header · LH | `coilmaster_hgrh_lh_header1` | EZC-0002 |
| HGRH · 1 header · RH | `coilmaster_hgrh_rh_header1` | EZC-0012 |
| HGRH · 2 header · LH | `coilmaster_hgrh_lh_header2` | EZC-0008 |
| HGRH · 3 header · RH | `coilmaster_hgrh_rh_header3` | EZC-0016 |
| CWC · LH | `coilmaster_cwc_lh` | EZC-0014 |
| HWC · LH | `coilmaster_hwc_lh` | EZC-0005 |

- [ ] **[MVP]** Confirm this 10-template set is the intended MVP scope (or trim/extend it).

---

## 1. Unregistered drawing templates (coverage axis)

- [ ] **[MVP]** Verify each of the **22 seeded templates** renders end-to-end and is
  John-reviewed as a valid review aid. *(2026-06-21: previews rendered to
  `build/feed_preview_png/` — awaiting John's eyeball sign-off.)*
- [x] **[EXT]** Seed the 8 former-mirror `needs_pair` buckets from real per-hand PDFs
  (`dx_rh_header1`, `dx_lh_header2`, `dx_rh_header3`, `dx_rh_hgbp`, `hgrh_rh_header2`,
  `hgrh_lh_header3`, `cwc_rh`, `hwc_rh`). *(Done 2026-06-21 — real seeds, no mirrors.)*
- [x] **[EXT]** **4HD**: seeded real DX/HGRH header-4 references (LH+RH) and registered
  them; the `placeholder_blocked` branch is now inert. *(Done 2026-06-21.)*
- [ ] **[EXT]** **Ventum+ fork**: add catalog `product_family` discriminator + full
  parallel Ventum+ bucket matrix; remove the downstream `_UNREGISTERED_PRODUCT_LINES`
  hard-block in `workflows/submittal_to_drawing.py`. New buckets start unseeded.
- [ ] **[MVP]** Confirm the "unregistered/unseeded" list is **known and surfaced** (not a
  silent gap) for everything outside the 10-template set.

## 2. Drawing parameter rules by product (parameter axis)

- [ ] **[MVP]** **Parameter completeness audit** for every use case in the set: confirm
  each drawing slot resolves to a **HIGH** value, or is intentionally annotated as
  `review_required` / omitted — no silent `None`.
- [ ] **[MVP]** **MEDIUM → HIGH promotions needing John's sign-off** (currently
  `review_required`): `R-044a/c` supply_sl, `R-048` HGRH positions, `R-066` vent_drain,
  `R-002b` lifting_lugs, `R-073` HGRH casing depth, `R-074` casing dims (single-source
  CHK), `R-077` drain-pan, `R-085` back-to-back, `R-086` coil style. Decide which the MVP
  auto-draws vs leaves as review.
- [ ] **[MVP]** **CONFLICT/blocked disposition**: confirm `R-084` ASC orientation stays
  blocked for MVP (deferred until the Direct Coil field-naming convention exists).
- [ ] **[EXT]** **Terra split**: `TERRA → TERRA_H + TERRA_V` (Terra H C as sub-variant);
  re-key ~15 Terra rules + engine call-sites (`header_prepopulate_engine.py:334,511,591`)
  + `coilmaster_drawing_extract.py` resolver + `direct_coil_drawing_pipeline.py` `_PRODUCT`
  map + tests.
- [x] **[EXT]** **Terra V drawing values finalized from SOP 2024018** (John 2026-06-28,
  commit `42d6364`): `R-023` (DX return spacing), `R-046` (HGRH supply/return I/O + SL),
  `R-067` (CWC/HWC vent-drain) promoted **LOW→HIGH and now drawn** — no longer blocked.
  Companion rules added: `R-021v`/`R-027v`/`R-042v` (constants), `R-034v`/`R-061v`/`R-065v`
  (specials). 10 confirmed Terra-V-vs-Terra-H deltas — see **§2a** below. Terra H == Terra
  H C (unchanged). HGRH Supply 2/3/4 I/O stays `review_required` (software default not
  derivable).
- [ ] **[DEFER]** `R-082` Terra mounting holes — confirm remains blocked, not MVP.

### 2a. Terra V delta logic (vs Terra H = Terra H C)

> SOP-confirmed difference logic from `2024018 - SOP - EZ Coil Ordering.docx` (John
> 2026-06-28). Terra V values layer on top of the Terra (H) baseline; **Terra H / Terra
> H C are unchanged**.
>
> **Values are not duplicated here** — they live in
> `src/coilforge/rules/coil_header_rules.yaml`. The 10 confirmed deltas are the `…v`
> override rules (`R-021v`/`R-027v`/`R-042v`/`R-061v`/`R-065v` constants;
> `R-034v` special) plus the promoted `R-023` (DX return spacing), `R-046` (HGRH
> supply/return I/O + SL), and `R-067` (CWC/HWC vent-drain). Slot-layer formulas
> (`S = CD − Rₙ`, CWC return `O = CH − 2.75`) live in
> `services/direct_coil_drawing_pipeline.py::build_drawing_slots`.

The two mechanisms that make this work (the "logic", not just the values):

- [x] **[EXT]** **Last-writer-wins**: each Terra V rule (`R-0xxv`) is placed *after* its
  generic Terra rule in YAML order, so the emitter's `place()` overwrites Terra H's value
  for Terra V only — no ruleset fork.
- [x] **[EXT]** **Engine/slot dual-path**: `S = CD − Rₙ` (DX) and CWC return `O = CH −
  2.75` live at the **slot layer** (`build_drawing_slots`), not the engine, because they
  need casing dims (CD/CH) the engine never sees. The generic-R safety net is guarded
  `and not is_terra_v` so Terra V never borrows Terra H's spacing (the prior gate leak).
- [ ] **[MVP]** Confirm these 10 Terra V deltas draw correctly end-to-end for a real
  Terra V case (eyeball gate) before counting Terra V as MVP-complete.

## 3. End-to-end pipeline & the three outputs

- [ ] **[MVP]** Review-aid **SVG drawing** renders with `export_allowed: False` + watermark.
- [ ] **[MVP]** **Paste-ready field set** produced and validated against the real CCSI
  "Direct Coil" form field list.
- [ ] **[MVP]** **Validation / compatibility report** clearly flags `review_required` and
  `blocked` fields.
- [ ] **[MVP]** **Evidence/traceability**: every drawn value carries `source_evidence`
  (the `FieldValue` contract) — no bare values.

## 4. Review / sign-off gates

- [ ] **[MVP]** John confirms the **inferred JSON→slot mappings** still flagged uncertain:
  `L-009/L-010` (HF/RF ambiguous), `L-013/L-014` (derived offsets), `L-050–052` (OAL
  derived), `L-041` (ASC orientation deferred).
- [ ] **[MVP]** Template review-aid sign-off recorded for each of the 10 seeded templates.

## 5. UI & coverage visibility

- [ ] **[MVP]** Web UI supports each use case end-to-end (upload PDF / fill Direct Coil
  form → drawing + fields + report) and clearly shows `review_required` / `blocked`.
- [ ] **[EXT]** **Coverage-checklist generator** (`scripts/generate_coverage_dashboard.py`)
  replacing the hand-authored `docs/coverage_dashboard.html` snapshot.

## 6. Tests & safety

- [ ] **[MVP]** Full suite green (`python -m pytest -q`) for in-scope categories/products.
- [ ] **[MVP]** Safety flags asserted in API responses (`raw_private_data_returned`,
  `export_allowed`, `production_drawing_approval_claimed` = False).

## 7. Things easy to miss (the "anything else")

- [ ] **[MVP]** **Direct Coil field-naming convention** — real dependency: `R-084` (and
  others) are *blocked until it exists*. Defining it unblocks ASC orientation.
- [ ] **[MVP]** **Single-feed vs multi-feed water coils** (`R-064-sl/io/hd`) — confirm the
  feed-count path for CWC/HWC is correct for the seeded cases.
- [ ] **[MVP]** **Unit-size picker correctness** (`R-076` enumerations; Terra zero-padding)
  — tokens must match real submittal callouts.
- [ ] **[MVP]** **Casing-dims table completeness** (`R-074`) — single-source (CHK only) and
  MEDIUM; confirm in-scope products' rows are present and reviewed.
- [ ] **[MVP]** **Notes assembly** (`R-007/R-008` base + `R-080/R-081` coating) — final note
  text matches SOP Rev H wording.

## Explicitly DEFER (NOT MVP)

- [ ] **[DEFER]** Parametric drawing engine (SVG/DXF/PDF backends) — MVP is template-first.
- [ ] **[DEFER]** DXF / PDF export + the `export_allowed` promotion gate.
- [ ] **[DEFER]** Full selection-calculation engine (forbidden without explicit approval).
