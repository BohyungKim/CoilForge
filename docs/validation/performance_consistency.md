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
| Sensible factor F | 1.085 | in repo | `coil_utilities/geometry.py` (workbook Extras). CCSI Standard reports measure 1.082–1.092, mostly 1.084 |
| k tolerance | ±0.02 | decided (John 2026-10-01) | sweep below |
| Actual factor | `F x 529.67 / (459.67 + EDB) x (1 − 6.8754e-6 x altitude)^5.2559` | cited | ideal-gas temperature ratio at the entering air x standard-atmosphere pressure ratio; not taken from a CCSI document |
| Face-velocity tolerance | 1 % | assumption | 3 of 278 coils fail at 0.5 %, 1 % and 2 % alike |
| Fluid bands | water 488–503, PG 40 % 457–467, PG 50 % 443–453 | captured | unrounded extremes of the ordered corpus, rounded outward |
| Fluid band margin | ±3 % | assumption | GPM is printed to two significant figures; the factor drifts with fluid temperature; no water coil above 160 °F was measured |

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
  2847); their CCSI capacity is the submittal's x 1.083–1.084. Cause not established.
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

## Open decisions (John)

1. Sensible factor: 1.085 (repo), 1.084 (CCSI reports) or 1.08.
2. ~~k tolerance~~ — **decided 2026-10-01: ±0.02.** Narrowing it on the heating numbers alone
   would flag 16–30 % of DX coils.
3. Whether the Actual-density relation is an acceptable cited reference.
4. The k ≈ 1.00 cluster: keep `inconsistent`, or recognise it as a known convention.
5. Fluid bands as measured + 3 %, or a supplied glycol property table.
6. Face-velocity tolerance.
7. On `inconsistent` at push time: warn or block (integration, with the CCSI session).

## Running the report

```
python scripts/performance_consistency_report.py --crosscheck <abs>\crosscheck.json --sources-cache <abs>\cache
```

Both inputs are read only and must be absolute paths. Output goes to
`~/CoilForgeData/performance_consistency/` — it names project numbers, so it is refused
inside any git working tree. A truncated or restructured input exits 2 and writes nothing.
