# Stage 2b — Parameter-Completeness Audit (MVP set)

> Review artifact. Generated 2026-07-06 by driving all 10 seeded MVP use cases through the
> **real** pipeline (`services/direct_coil_drawing_pipeline.run_direct_coil_drawing_pipeline`).
> Representative inputs: product **NOVA**, unit **A16**, rows=6, feeds=4, FH=12, FL=22.
> Review aid only — this audits **completeness/surfacing** (does every slot resolve or get
> surfaced), NOT value correctness (that stays John's eyeball gate).

## Headline

- **Silent-None violations: 0** — the confidence-gate invariant *("no silent None")* **holds**
  across the MVP set. Every `required_for_preview` slot either resolved to a value or was
  surfaced as review-required (never a silent blank).
- Required slots: **102 resolved / 9 review-surfaced / 0 silent** across 10 use cases.
- All 10 templates found + populated.

The 0 is authoritative, not heuristic: every unresolved required slot appears in the pipeline's
own `missing_required_slots` (what `populate_template_slots` reports and the UI renders RED).

## The two recurring review-surfaced required slots (by design, not gaps)

- `slot.MODEL_NUMBER` — all 10 cases. Hand-suffix requires review; not derivable without the
  model number. Correctly surfaced via `missing_required_slots`.
- `slot.HD2` — CWC/HWC only. **Investigated (Stage 2d lead — resolved).** The water header-depth
  rule is `special_cwc_hd` (`coil_header_rules.yaml`), evidence `CHK IF(feeds=1,'N/A',4)`:
  - **feeds ≥ 2 (multi-feed):** `hd` = HIGH **4** → `slot.HD2` resolves HIGH. Fully correct; the
    audit only missed it because the representative input used `feeds=1`.
  - **feeds = 1 (single-feed):** `hd` is legitimately **N/A** — the engine knows this and emits
    `hd="N/A"` into the **MEDIUM** bucket. But `map_engine_to_slots` forwards only HIGH values to
    slots, so the N/A is dropped and `slot.HD2` (required_for_preview=true) renders as a RED
    *missing-required* blank. **Not a silent-None** (it's surfaced) and **not a math error** — a
    presentation-fidelity gap: an N/A dimension reads as a failed one.
  - **DECISION (John, 2026-07-06): leave as-is.** The RED missing-required flag stays — it's
    already surfaced (not a silent None), it correctly prompts the review single-feed HD2 needs,
    and multi-feed water already resolves HD2=4. No code change; `map_engine_to_slots` untouched.
    **Closed.**

## MEDIUM→HIGH promotion surface (feeds John's §2b decision)

Engine fields that surfaced as **MEDIUM (review_required)** in a live NOVA render, mapped to the
rules on the finalization checklist's promotion list:

| Engine field | # cases | Rule | On the "9"? |
| --- | --- | --- | --- |
| `lifting_lugs` | 10 (all) | R-002b | ✅ |
| `supply_sl` | 4 (HGRH) | R-044a/c | ✅ |
| `supply_position` + `return_position` | 4 (HGRH) | R-048 | ✅ |
| `vent_drain` | 2 (water) | R-066 | ✅ |
| `return_spacing` | 4 (HGRH) | (HGRH R spacing) | — |
| `hd`, `io` | 2 (water) | R-064 water header | — |

**Blocked** (LOW/CONFLICT): `copper_straps_required` ×2 (CWC/HWC) → **R-090** water-strap
multiplier — correctly blocked, matches the known-undecided water-strap item.

### Which of the nominal "9" did NOT surface as MEDIUM here
`R-073` (casing depth) and `R-074` (casing dims) resolved **HIGH** for A16; `R-077` (drain-pan)
is a **fit-report** rule consumed off the drawing path (not a slot); `R-085` (back-to-back) and
`R-086` (coil style) need special inputs a standard render doesn't carry. So the **effective**
promotion decision surface in the drawing path is narrower than the full 9 — the live-gating
ones are **R-002b, R-044a/c, R-048, R-066**.

## Per-use-case detail

| Template | Coil | req resolved | req review | silent | HIGH / MED / blk |
| --- | --- | --- | --- | --- | --- |
| coilmaster_dx_lh_header1 | DX LH 1HD | 11 | 1 | 0 | 19 / 1 / 0 |
| coilmaster_dx_rh_header2 | DX RH 2HD | 11 | 1 | 0 | 19 / 1 / 0 |
| coilmaster_dx_lh_header3 | DX LH 3HD | 11 | 0 | 0 | 19 / 1 / 0 |
| coilmaster_dx_lh_hgbp | DX LH HGBP | 11 | 1 | 0 | 19 / 1 / 0 |
| coilmaster_hgrh_lh_header1 | HGRH LH 1HD | 10 | 1 | 0 | 15 / 5 / 0 |
| coilmaster_hgrh_rh_header1 | HGRH RH 1HD | 10 | 1 | 0 | 15 / 5 / 0 |
| coilmaster_hgrh_lh_header2 | HGRH LH 2HD | 10 | 0 | 0 | 15 / 5 / 0 |
| coilmaster_hgrh_rh_header3 | HGRH RH 3HD | 10 | 0 | 0 | 15 / 5 / 0 |
| coilmaster_cwc_lh | CWC LH | 9 | 2 | 0 | 11 / 4 / 1 |
| coilmaster_hwc_lh | HWC LH | 9 | 2 | 0 | 11 / 4 / 1 |

*(review-surfaced count varies by header count because `slot.MODEL_NUMBER` is only counted when
the template declares it required; the 2HD/3HD variants resolve more optional per-header slots.)*

## Scope + caveats

- **Product scope:** NOVA/A16 (Nova/Ventum-H MVP family). Terra H/V and Ventum+ have their own
  review surfaces (e.g. Terra V HGRH Supply 2/3/4 I/O is review-required by design).
- **Completeness, not correctness:** a slot counted "resolved" means it holds a traceable value,
  not that the value is engineering-correct. Correctness remains the human eyeball gate.
- **Snapshot:** run against the current working tree (engine files are mid-edit by a concurrent
  session); re-run after those land for a fresh picture.
- Reproduce: `python <job-tmp>/param_completeness_audit.py` (throwaway harness, not committed).
