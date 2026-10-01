# Performance self-consistency

`src/coilforge/coil_utilities/performance_consistency.py` checks whether one coil's extracted
performance values agree with each other. It exists for the moment a new submittal is pushed
to CCSI: the order cross-check (`docs/ccsi/mapping_findings.md`) needs an ordered selection to
compare against, and a new submittal has none.

It is a review aid. It never changes or fills a value, approves nothing, and gates no export
(`review_aid_only: True`, `export_allowed: False`, every finding `review_required`).

## What it reads

`check_performance_consistency(sources, coil_type=...)` takes the same mapping the CCSI push
resolves from: Direct Coil draft keys and/or canonical `group.key` paths, each a FieldValue,
its dict form, or a bare value. Draft key first, canonical path second; a key counts only when
its value is non-null. A `blocked` source is not used.

All values are **per coil**. The submittal states airflow, capacity and GPM per coil; the
`x quantity` step belongs to the CCSI map. Coil quantity is not read.

A value must be plainly numeric. `"3,735"`, `"95.0 °F"` and `"N/A"` are reported as
`PERF_VALUE_UNPARSEABLE`, not cleaned. A carried unit outside the expected set
(`cfm`, `degF`, `MBH`, `ft`, `fpm`, `in`, `gpm`, `pct`) is `PERF_UNIT_UNEXPECTED`, not converted.
A value that carries no unit at all is taken as stated: the unit check only runs when a unit
is present (every push-time value in the corpus carries one).

The report and each finding are frozen: `export_allowed`, `review_required` and the verdicts
cannot be reassigned after the check runs.

## Checks

All seven are always returned. One that does not apply is `cannot_evaluate` /
`PERF_NOT_APPLICABLE`, so "not checked by design" is distinguishable from "checked and fine".

| Check | Coils | Relation |
|---|---|---|
| `air_sensible_balance` | HGRH, HWC (total capacity); DX, CWC (sensible capacity) | `k = capacity x 1000 / (CFM x air delta-T)` equals the Standard or the Actual factor within tolerance |
| `air_total_vs_sensible` | DX, CWC | total capacity is not below the air-side sensible load (one-sided) |
| `sensible_le_total` | DX, CWC | sensible capacity does not exceed total capacity |
| `fluid_heat_balance` | CWC, HWC | `capacity x 1000 / (GPM x fluid delta-T)` lies in the captured band for that fluid |
| `face_velocity` | all | stated face velocity equals `CFM / (FH x FL / 144)` |
| `air_temp_direction` | all | cooling: leaving below entering; heating: leaving above entering |
| `wet_bulb_le_dry_bulb` | when a wet bulb is stated | entering wet bulb does not exceed entering dry bulb |

Air basis (`air_basis`): `standard`, `actual`, `indeterminate` (both match), or
`standard_only` (no altitude, so Actual was not evaluated). The nearer basis is never picked;
a value that fits neither is `inconsistent`. Altitude is never assumed to be 0.

## Constants

| Constant | Value | Status | Source |
|---|---|---|---|
| Sensible factor F | 1.085 | in repo; decided (John 2026-10-01) | `coil_utilities/geometry.py` (workbook Extras). CCSI Standard reports measure 1.082–1.092, mostly 1.084; verdicts are identical at ±0.02. The number is printed in neither the submittal nor the CCSI report — it is back-calculated |
| k tolerance | ±0.02 | decided (John 2026-10-01) | sweep below |
| Actual factor | `F x 529.67 / (459.67 + EDB) x (1 − 6.8754e-6 x altitude)^5.2559` | cited | ideal-gas temperature ratio at the entering air x standard-atmosphere pressure ratio; not taken from a CCSI document |
| Face-velocity tolerance | 1 % | decided (John 2026-10-01) | 275 of 278 coils are within 0.12 %, none between 0.12 % and 6 %, 3 above 6 %: any tolerance from 0.2 % to 5 % gives the same result |
| Fluid bands | water 488–503, PG 40 % 457–467, PG 50 % 443–453 | captured | unrounded extremes of the ordered corpus, rounded outward |
| Fluid band margin | ±3 % | decided (John 2026-10-01) | GPM is printed to two significant figures; the factor drifts with fluid temperature; no water coil above 160 °F was measured |

The fluid bands are measurements, not a property table. Any other fluid or percent is
`PERF_NO_REFERENCE`. A value outside band + margin is `inconsistent` with
`PERF_OUTSIDE_CAPTURED_RANGE`, a different code from a formula mismatch.

## What a verdict means

`consistent` means *not contradicted*. It does not mean the values are right.

- **Heating coils.** The Standard and Actual expectations differ by less than 0.04 on 100 of
  118 coils, and 30 match both. Only gross disagreement is caught.
- **DX total capacity cannot be verified.** It carries latent load, so there is no two-sided
  relation. The one-sided check is loose (total / air-sensible: median 1.60, p10 1.33): an
  over-read of any size passes, and so does an under-read of less than roughly 25–37 %. The
  recorded misread of Nominal 365.85 for 123.88 passes every total-capacity check. What can be
  checked two-sided on a DX coil is its **sensible** capacity.
- **CWC.** No corpus CWC coil states a sensible capacity (0 of 6), so its
  `air_sensible_balance` is always `cannot_evaluate`.
- **An inconsistent coil is not necessarily a misread.** On the two coils checked against the
  PDF (2755 RHHGRC-2, 3058 RHHGRC-2) the extraction matches the page; the submittal's own
  numbers do not reconcile, and the ordered selection used a different input.

## Measured on the ordered corpus (2026-09-30 run, F 1.085, tol ±0.02)

Produced by `scripts/performance_consistency_report.py`; numbers move when the cross-check
batch is re-run.

| | Evaluable | standard | actual | indeterminate | inconsistent |
|---|---|---|---|---|---|
| Heating coils (HGRH + HWC) | 118 of 118 | 42 | 33 | 30 | 13 |
| DX sensible (push-time sources) | 153 of 156 | 67 | 64 | 15 | 7 |

- 8 of the 13 inconsistent heating coils sit at k ≈ 1.00 (projects 2623, 2813, 2830, 2835,
  2847); their CCSI capacity is the submittal's x 1.083–1.084 while the CCSI leaving dry bulb
  equals the submittal's on all 8 — the temperatures agree and the printed capacity is the
  odd value. All 8 are quote-only projects (no order), and none of the 57 HGRH coils from
  project 2900 on is in the cluster. Cause not established.
- 6 of the 7 inconsistent DX coils have k 1.106–1.156; cause not established.
- Inferred basis against the report's ACFM, capacity-matched heating coils: `actual` → Actual
  26 of 26; `standard` → Standard 14 of 16.
- Fluid side: 26 of 27 coils `consistent`, 1 without a reference (PG 30 %). Band self-check:
  0 outside of 26 checked.
- Face velocity: 275 consistent, 3 inconsistent, 2 not evaluable.

Tolerance sensitivity — one (F, tol) pair drives both families, and DX sits on the edge:

| F | tol | heating inconsistent | heating indeterminate | DX sensible inconsistent |
|---|---|---|---|---|
| 1.085 | 0.01 | 14 | 12 | 46 |
| 1.085 | 0.015 | 13 | 21 | 25 |
| 1.085 | 0.02 | 13 | 30 | 7 |
| 1.085 | 0.03 | 12 | 59 | 5 |
| 1.084 | 0.02 | 13 | 27 | 7 |
| 1.08 | 0.02 | 13 | 28 | 25 |

## Air flow basis — decided (John 2026-10-01)

CCSI's `Air flow basis` for a Direct Coil selection is **Standard (SCFM)**. (John first said
ACFM — "it used to be SCFM with Coilmaster; we decided to use ACFM with Direct Coil" — and
corrected it the same day: "we should go with SCFM instead".)

The corpus does not line up with that rule, and John explained why: "ideally it should've
calculated with SCFM but we've been calculating all with ACFM for direct coil — that's why
that difference is happening." So Standard is the intended basis, and Actual is what the
Direct Coil selections have in practice been calculated on. The submittals' own numbers moved
from Standard to Actual around project 2900–3100, and the orders followed part of the way:

| Project number | Submittal heating coils fit: standard / actual / both / neither | Ordered CCSI basis: Actual / Standard |
|---|---|---|
| below 2700 | 9 / 0 / 6 / 2 | 11 / 19 |
| 2700–2899 | 14 / 1 / 7 / 10 | 26 / 52 |
| 2900–3099 | 19 / 11 / 11 / 1 | 69 / 43 |
| 3100 and later | 0 / 21 / 6 / 0 | 43 / 16 |

What this changes for a reader of the checks:

- `air_basis: standard` or `indeterminate`: the submittal's capacity is on the basis CCSI
  will rate on.
- `air_basis: actual`: the submittal's capacity was computed on actual air. Rated in CCSI on
  Standard, the capacity will not reproduce. Measured on ordered heating coils whose submittal
  fits Actual only: CCSI on Actual matched the submittal's capacity on 26 of 26; CCSI on
  Standard matched on 0 of 7. Every evaluable heating coil from project 3100 on is `actual`
  or `indeterminate` (21 and 6), so this is the normal case for a current submittal.
- It is still `consistent`: the check asks whether the submittal agrees with itself, not
  which basis CCSI should use. The checks accept both bases.

Altitude follows the basis. On Standard, CCSI locks the altitude field at 0 even when the
submittal states one (49 of 130 Standard orders). So with this rule the altitude is not a
value to push: the form reports it locked, which is expected, and the order cross-check's
"altitude mismatch" rows are that lock, not an extraction error.

## Open decisions (John)

1. ~~Sensible factor~~ — **decided 2026-10-01: 1.085.** It only drives the checks; it is never
   pushed and does not enter CCSI's rating.
2. ~~k tolerance~~ — **decided 2026-10-01: ±0.02.** Narrowing it on the heating numbers alone
   would flag 16–30 % of DX coils.
3. ~~Actual-density relation~~ — **decided 2026-10-01: accepted as the cited reference.** Every
   evaluable heating coil from project 3100 on fits it (actual 21, both 6, neither 0).
4. ~~The k ≈ 1.00 cluster~~ — **decided 2026-10-01: stays `inconsistent`.** No third basis is
   added for a convention whose cause is not established.
5. ~~Fluid band margin~~ — **decided 2026-10-01: measured bands + 3 %.** A wrong GPM lands far
   outside (3197 HHWC: factor 1133 against a 488–503 band).
6. ~~Face-velocity tolerance~~ — **decided 2026-10-01: 1 %.** The three coils it flags look like
   dimension discrepancies: 2674 HHWC-1 / -2 print a velocity that matches FH 10.5 while FH 9
   was extracted; 2873 CDXC-1 prints one that matches FL 16 while FL 15 was extracted. FH and
   FL are pushed to CCSI, so these are worth checking against the page.
7. On `inconsistent` at push time: warn or block (integration, with the CCSI session). **Open.**

## Running the report

```
python scripts/performance_consistency_report.py --crosscheck <abs>\crosscheck.json --sources-cache <abs>\cache
```

Both inputs are read only and must be absolute paths. Output goes to
`~/CoilForgeData/performance_consistency/` — it names project numbers, so it is refused
inside any git working tree. A truncated or restructured input exits 2 and writes nothing.
