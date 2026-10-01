# Handoff to the CCSI session — performance self-consistency in the push payload

From the performance-consistency session (branch `claude/performance-consistency`, cut from
`c9d84d4`). **Nothing here has been applied.** `src/coilforge/ccsi/coil_data_map.py`,
`web/ccsi/ccsi_autofill.user.js` and `web/app.js` belong to the CCSI session and were not
touched. There is no patch file on purpose: the working copy of `coil_data_map.py` has moved
past `c9d84d4`, so a patch cut here would not apply.

## What is available

`coilforge.coil_utilities.performance_consistency.check_performance_consistency(sources, coil_type=...)`
returns a `PerformanceConsistencyReport` (seven findings, each `consistent` / `inconsistent` /
`cannot_evaluate` with a reason code). It reads the same `sources` mapping
`resolve_coil_data` reads, untransformed. See `docs/validation/performance_consistency.md`.

The module imports only `pydantic` and `coil_utilities.geometry`, so it adds nothing to the
import cost of `coil_data_map`.

## Suggested wiring (three lines)

In `build_coil_data_payload`, after `entries = resolve_coil_data(sources, coil_type=resolved_type)`:

- import inside the function, like the other late imports in that module:
  `from coilforge.coil_utilities.performance_consistency import check_performance_consistency`
- add one key to the returned dict:
  `"performance_consistency": check_performance_consistency(sources, coil_type=resolved_type).model_dump()`

The key is additive. `entries`, `pushable` and every existing key stay as they are, so the
userscript's schema check is unaffected until it chooses to read the new key.

Two things to keep:

- Pass `sources` as built by `coil_data_sources` — **before** any transform. The checks need
  the submittal's own statement: per-coil GPM (not `number_times_quantity`) and the fluid as
  named (`Water` 100, not glycol 0).
- Pass the resolved coil type (`DX` / `HGRH` / `CWC` / `HWC`). `None` makes the type-dependent
  checks `PERF_COIL_TYPE_UNKNOWN`.

## Showing it

The panel that lists why a field is held is the natural place: one line per finding whose
verdict is `inconsistent`, with `reason`, `observed` and `expected`. A `consistent` finding
should earn no green mark — it means "not contradicted", and on heating coils 30 of 118 match
both air bases.

## Behaviour on `inconsistent` — decided (John 2026-10-01): warn only

An `inconsistent` finding is shown with its reason and does **not** stop "Run all" before
Calculate. So the wiring needs no change to the stage-1 stop conditions: add the key, render
the warnings, leave the flow as it is. Measured rate on the ordered corpus at the defaults
(F 1.085, tol ±0.02): 13 of 118 heating coils, 7 of 153 DX coils (sensible), 0 of 26 water
coils, 3 of 278 on face velocity. John settled the tolerance at ±0.02 on 2026-10-01; DX is
sensitive to it (7 → 25 → 46 inconsistent at ±0.02 → ±0.015 → ±0.01), so it should not be
narrowed without re-reading the sweep.

## Findings worth a look on the CCSI side

- **2755 RHHGRC-2 / -3:** the submittal prints entering DB 54; the ordered selection used 52,
  and only 52 reconciles with the printed capacity and leaving DB. The push would send 54.
- **3058 RHHGRC-2:** the submittal prints 4800 CFM; the order used 4500, and only 4500
  reconciles. The push would send 4800.
- **ACFM basis — Actual (John 2026-10-01), already applied by the CCSI session** (`6a19675`:
  `ACFM` = `Actual` on all four maps, before `Altitude`). Standard (SCFM) would be the ideal
  basis and is parked on the roadmap as a suspect area, not adopted. An earlier revision of
  this page said Standard was decided; that was this session's misreading, corrected here.
- **Altitude goes with it.** Under Standard, CCSI locks the altitude field at 0 — 49 of 130
  Standard orders have a non-zero submittal altitude against CCSI 0. That is the gate's
  "Altitude unexplained" bin and the reason stage 1 reported Altitude as `locked` on 2803.
  Under Actual the altitude is carried (148 of 149 ordered coils).
- **Where a capacity gap is still expected.** A submittal whose own numbers fit Standard only
  (`air_basis: standard` on its `air_sensible_balance` finding — older projects; none of the
  heating coils from project 3100 on) will rate differently on Actual. That is the basis, not
  an extraction or mapping defect. The reverse case is measured: ordered coils whose submittal
  fits Actual only reproduced capacity on 26 of 26 with CCSI on Actual and 0 of 7 on Standard.
- On capacity-matched heating coils the basis inferred from the submittal's own numbers
  agrees with the report's ACFM: `actual` → Actual 26 of 26, `standard` → Standard 14 of 16.
- **Pairing.** Capacity mismatch against the order is 28 % on projects paired by ledger hash
  and 57 % on projects paired by `heuristic_highest_rev` (order tier). Part of the
  "unexplained" capacity bin may be the wrong submittal revision rather than extraction.
