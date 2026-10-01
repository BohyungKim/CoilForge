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

## Decision this needs (John)

Whether an `inconsistent` finding only warns or also stops "Run all" before Calculate. The
module takes no position: it reports. Measured rate on the ordered corpus at the defaults
(F 1.085, tol ±0.02): 13 of 118 heating coils, 7 of 153 DX coils (sensible), 0 of 26 water
coils, 3 of 278 on face velocity. John settled the tolerance at ±0.02 on 2026-10-01; DX is
sensitive to it (7 → 25 → 46 inconsistent at ±0.02 → ±0.015 → ±0.01), so it should not be
narrowed without re-reading the sweep.

## Findings worth a look on the CCSI side

- **2755 RHHGRC-2 / -3:** the submittal prints entering DB 54; the ordered selection used 52,
  and only 52 reconciles with the printed capacity and leaving DB. The push would send 54.
- **3058 RHHGRC-2:** the submittal prints 4800 CFM; the order used 4500, and only 4500
  reconciles. The push would send 4800.
- **ACFM basis.** On capacity-matched heating coils the basis inferred from the submittal's
  own numbers agrees with the report's ACFM: `actual` → Actual 26 of 26, `standard` →
  Standard 14 of 16. 23 coils are indeterminate. This is evidence for a rule candidate, not a
  rule.
- **Pairing.** Capacity mismatch against the order is 28 % on projects paired by ledger hash
  and 57 % on projects paired by `heuristic_highest_rev` (order tier). Part of the
  "unexplained" capacity bin may be the wrong submittal revision rather than extraction.
