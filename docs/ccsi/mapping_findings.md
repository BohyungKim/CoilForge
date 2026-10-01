# CCSI coil-data cross-check — findings and open decisions

Read-only harvests (DevTools snippet `web/ccsi/ccsi_harvest_snippet.js`, 2026-09-29) compared
against the capture ledger's draft stage via `scripts/ccsi_crosscheck.py`. Nothing in CCSI was
changed. (The line that stood here — "every mapping is still `captured`" — is out of date: John
promoted fields to `validated` on 2026-09-29/30; the maps and `JOHN_APPROVED_VALIDATED` in
`tests/test_ccsi_coil_data_map.py` are the current list.)

| Coil | CCSI form | match | real mismatch | note |
|---|---|---|---|---|
| 3232 CDXC-1 | `DXCoil` | 17 | Feeds 6 vs **7**; tube 0.016 vs **Copper 0.020 Plain** | |
| 3232 RHHGRC-1 | `CondenserCoil` | 13 | LDB 70.01 vs 90 (see D5) | |
| 3031 CCWC-1 | `ColdWaterCoil` | 13 | — | |
| 3031 HHWC-1 | `HotWaterCoil` | 9 | — | **not a finished selection**: Rows/FPI/Feeds = `Optimise`, Capacity blank. Excluded as ground truth; needs another HWC. |

Fields that match on every harvested coil so far: Tag, FH, FL, Rows, FPI, Hand, CFM, face
velocity, altitude, EDB (+ EWB on DX/CWC), refrigerant (DX/HGRH), fin surface, return connection
(DX). One project per category is **not** enough to promote anything (`validated` needs ≥3).

## Open decisions (John)

**D1 — Tube / fin material.** ✅ Decided and built 2026-09-30 — see "Decided 2026-09-30 — D1" below.
(Original premise, now corrected: "DX/HGRH drafts carry the gauge only". They carry the material too,
in the field's `unit`.)

**D2 — Fields the submittal never states, identical on all 4 coils.** Header Copper / wall (L),
Connection Ends Same End Only, Coating Plain, Casing Standard + Galv 16 ga, Drain pan None / SST,
ACFM Standard, fouling 0, turbulators No, Connection Material Copper (refrigerant) / **Steel**
(water), Connection Type Sweat / **MPT**, Tube Diameter 3/8 1.00×0.866 (DX/HGRH) /
5/8 1.50×1.299 (water). Question: are these an Oxygen8 standard profile CoilForge may push as a
review-required default, or must the application engineer set them?

**D3 — Connection size.** CCSI keeps `Calculate` for water `ConnectionSize` and HGRH
`Supply/ReturnConnectionSize` (HGRH return has no other option). Push the submittal size, or
leave CCSI's own calculation?

**D4 — CCSI "Leaving Dry Bulb".** Read-only 55.00 on both DX coils and 90 on HGRH (not the
submittal LAT 54.91 / 70.01), but 66.8 on CWC (submittal 66.2) and editable 72 on HWC (= submittal).
Is it a target the application engineer types? If so it is an input to push, not a result.
✅ **Revised 2026-09-30 (John: "개정").** The "fixed default" reading was a pre-Calculate artifact:
after Calculate the form's `#LeavingDryBulb` input still reads the locked 55.00, while the rating
(`#mainResult`, and the report PDF's `Leaving Dry Bulb`) is the real result — 52.14 = submittal on
2803 (`calculate_flow.md`, Live test 2), 50.75 on 3237 REV0. Rule: the rating LDB is compared
against the submittal as a performance check; the form's LDB input is never pushed. The order gate
therefore never uses the harvested LDB as calibration evidence (`order_gate._NOT_COMPARABLE_ON_FORM`).
HGRH capacity pairs with the report's `Total Capacity /Coil (Total)` (John, same day).

**D5 — Real DX differences.** 3232 CDXC-1: feeds 6 (submittal) vs 7 (CCSI), tube wall 0.016 vs
0.020. Extraction error, or a deliberate re-selection in CCSI? Needs the submittal page.

**D6 — System Type.** CCSI = refrigerant circuit arrangement (all `Single-Circuit` so far); the
draft's `system_type` is the Oxygen8 unit system (Heat Recovery / Heat Pump). Derive from
circuits, default Single-Circuit, or leave to the engineer?

## Evidence log (per harvested coil)

- **3237 CDXC-1** (Nova DX): 17 match incl. feeds 8, EWB 68.44, SST/liquid/superheat.
  - D4: LDB read-only **55.00** again (submittal 50.75) — third DX at exactly 55.00 → a fixed CCSI
    DX default, not the submittal LAT.
  - D3: DX return size `Calculate` here, but `1 1/8"` on 3232 — the engineers do both.
  - D2 counter-example: **ACFM = Actual** (3232 / 3031 were Standard) — not a constant.
  - D6 counter-example: **System Type = Dual-Circuit Intertwined** (8 feeds); 3232 (7 feeds) was
    Single-Circuit, so feeds alone do not decide it. Draft says "Heat Recovery System" for both.

- **3237 RHHGRC-1** (Nova HGRH): 13 match (same set as 3232 RHHGRC-1, feeds 2).
  - D4: LDB read-only **90** again (submittal 70.88) — 2/2 HGRH at 90 → fixed CCSI HGRH default.
  - D3: supply and return both `Calculate` — 2/2 HGRH.
  - HGRH refrigerant block identical on 3232 and 3237: vapor 140 / condensing 115 / subcooling 18
    (SST 45 / suction 68 locked). Whether these are the submittal's values needs the canonical
    source (they are not in the draft).
  - ACFM = Actual here too (follows the unit's DX coil).

- **3183 CDXC-1 / RHHGRC-1** (Terra V; project inferred from a unique ledger match, not stated):
  DX 14 match, HGRH 9 match. But the **submittal geometry was re-selected in CCSI**: submittal fins
  are `Sine` + 0.0075 (neither exists in CCSI) → CCSI shows Flat/Corrugated + Aluminum 0.008, and
  rows / FPI changed with it (DX 6/9 → 5/12, HGRH 2/8 → 1/12). This is **D7** below.
  - D3: DX return `7/8"` = submittal 0.875 (match). HGRH: CCSI supply `5/8"` = the submittal's
    0.625 that CoilForge files as `return_connection_size`, while CCSI return is `1/2"` → for HGRH the
    draft's connection size looks like CCSI's **supply** size (1 project, Likely).
  - D4: LDB 55.00 (DX, 4/4) and 90 (HGRH, 3/3) — confirmed fixed CCSI defaults.

**D7 — Submittal fin types CCSI does not offer.** Sine fins and 0.0075 fins (ledger: 17 and 41 DX
coils) have no CCSI option, and the one observed case shows the application engineer re-optimising
rows/FPI after substituting the fin. Rating-mode push of the submittal geometry cannot reproduce such
a coil; it needs a substitution rule (which fin, and whether rows/FPI are pushed at all), or these
coils stay manual.

## Decided 2026-09-29 (John)

- **Promotion A — done.** The lists below are `validated` in the DX / HGRH maps, each entry carrying
  its `evidence`; `test_every_map_file_honours_the_contract` pins them by equality. Altitude was
  re-roled `locked` → `input` on all four maps: every harvest with ACFM = Actual had it editable
  (3183, 3237); it is read-only only under Standard (3232, 3031), where the push simply skips it.
- **D7 A — done.** `coil_data_map.geometry_reselect_reason` withholds RowsDeep / FinsPerInch /
  FinSurface / FinMaterial (`CCSI_GEOMETRY_RESELECT`) when the submittal fin surface or gauge is not
  on that form's CCSI list. Ledger replay: 40 / 156 DX and 26 / 92 HGRH coils are gated.

## Promotion candidates (≥3 projects, 0 mismatch) — approved

DX: Tag, FinnedHeight, FinnedLength, TotalAirFlow, Altitude, EnteringDryBulb, EnteringWetBulb,
EvaporatingTemperature, LiquidTemperature, Superheat, Refrigerant (3183 / 3232 / 3237).
HGRH: Tag, FinnedHeight, FinnedLength, NumberOfFeeds, TotalAirFlow, Altitude, EnteringDryBulb,
Refrigerant (3183 / 3232 / 3237). FaceVelocity also agrees but is CCSI-computed (never pushed).

- **Step A re-parse (3232, 3031 submittals):** water fluid type / % / EWT / LWT match on CCWC-1 and
  HHWC-1 (4/4 each); HGRH condensing 115 / subcooling 18 match on 3232 (vapor not extracted). CCSI
  leaves GPM **blank** on every water harvest (verdict `ccsi_blank`) — likely derived from EWT/LWT;
  pushing GPM would over-constrain. **Decided 2026-09-29 (John): push GPM** as submittal GPM x coil
  quantity (CCSI label says `(All Coils)`); `validated` by decision, not by match evidence.
- **3154 HHWC-1 / HHWC-2** (Ventum H; project inferred from a unique ledger match): 9–10 match.
  - **CFM:** HHWC-1 has CoilQuantity **3**, TotalAirFlow 1200, AirFlowPerCoil 400; the ledger CFM is
    400 → the submittal CFM is **per coil**; CCSI Total = qty × per-coil. TotalAirFlow must not be
    pushed from a per-coil value when qty > 1 (DX/HGRH promotion was on qty-1 coils only).
    **Resolved 2026-09-29:** `TotalAirFlow` = submittal CFM × submittal coil quantity
    (`number_times_quantity`; unknown quantity → blocked, never assumed 1), and `AirFlowPerCoil` is
    compared against the submittal CFM — **10/10 coils match**, the qty-3 coil included. The ledger
    does not record quantity, so ledger replays show Total as `submittal_missing`; the live draft has it.
  - Altitude: submittal 13, CCSI 0 on both. HWC LDB 90.0 read-only (a fixed default, like HGRH).

- **2954 CCWC-1 / CCWC-2** (Ventum+ CWC; project inferred from a unique ledger match): 12 match each
  (FH, FL, rows, FPI, fin surface, hand, per-coil CFM, altitude 30, EDB, EWB). ConnectionSize
  `Calculate`; LDB read-only **55.00** (so CWC also carries a fixed default — 3031's 66.8 was edited).

## Decided 2026-09-29 — "전부 A" (John)

- **W:** CWC / HWC Tag, FH, FL, rows, FPI, fin surface, hand, EDB, Total air flow → `validated`
  (2954 / 3031 / 3154 pooled across the two water forms).
- **D2:** the fields below carry a `default` (Oxygen8 CCSI default profile). Used only when the source
  is absent (unmapped, or blocked with `required canonical field missing`); a stated value always wins
  and a stated value off the CCSI list stays blocked (Finkote → never `Plain`).
- **D3:** every connection size is `computed` (compared, never pushed); CCSI `Calculate` reads as
  `not_persisted`.
- **D6:** `RefrigerationSystemType` = `value_map` on `geometry.circuits` (DX 1 → Single-Circuit,
  2 → Dual-Circuit Intertwined; HGRH 1 → Single-Circuit); any other count is `CCSI_OPTION_UNMAPPED`.
- Re-check over all 11 finished selections: 97 validated field/category pairs, **91 match on every
  coil, 0 mismatch**; the other 6 are Total air flow / GPM, which need the coil quantity the ledger
  does not record (the live draft does).

## Evidence for D2 / D3 / D6 (11 finished selections, 2026-09-29)

- **D2 — identical on every coil (11/11):** Header Copper, Wall (L), Connection Ends Same End Only,
  Coating Plain, Casing Standard + Galv 16 ga, air fouling 0. **Identical within category:** tube
  diameter 3/8 1.00×0.866 (DX/HGRH 6/6) vs 5/8 1.50×1.299 (water 5/5); drain pan None / SST (6/6);
  connection Copper + Sweat (refrigerant 6/6) vs Steel + MPT (water 5/5); water turbulators No,
  CoilType Standard, airflow Horizontal, vent/drain 1/8" (5/5); HGRH temperature input Vapor (3/3);
  DX capillary 1/4×0.025 (3/3). **Not constant:** ACFM (Actual 7 / Standard 4), max fluid PD
  (20 ×3 / 15 ×2), fin gauge (0.008 ×10 / 0.010 ×1), tube wall (0.016 / 0.018 / 0.020).
- **D3 — connection size:** water `Calculate` 5/5; HGRH supply+return `Calculate` 2/3; DX mixed
  (7/8", 1 1/8", Calculate).
- **D6 — system type follows the ledger's `circuits`:** DX 1 → Single-Circuit (3232), 2 →
  Dual-Circuit Intertwined (3237, 3183); HGRH 1 → Single-Circuit (3/3). No other count observed.

## Source check — 3232 submittal (2026-09-29, read-only)

`3232 - Oxygen8 Submittal - Brooks Building …pdf` p.4 (CDXC-1) prints `Total Feeds: 6`,
`Fin Material: 0.008 Aluminum`, `Tube Material: 0.016 Copper`; p.5 (RHHGRC-1) `Total Feeds: 1`,
same materials. So:
- **D5:** CoilForge extracted the submittal correctly (6 feeds, 0.016). The saved CCSI coil
  (7 feeds, Copper 0.020 Plain) differs from the submittal — a CCSI-side selection difference,
  not an extraction defect.
- **D1:** the material IS in the source (`0.008 Aluminum`, `0.016 Copper`), and the intake keeps it —
  in the draft field's `unit`, not its value (corrected 2026-09-30). The word `Plain` is not printed;
  the tube surface is, as `Tube Surface: Smooth` (3232 Rev1 p.4-5, 3237 Rev0 p.5-6).

## Decided 2026-09-30 — D1 (John)

- **No intake change.** `submittal/extract.py::_normalize_value` splits `0.016 Copper` into value
  `0.016` + unit `Copper`, and the draft and the ledger (`field_observation.unit`) both keep the unit.
  Only the CCSI readers dropped it (`load_coils` did not select `unit`; `_unwrap` returns the value).
  Changing the intake would have moved the 52-field paste surface, the title slot and the ledger's
  value shape for no gain.
- **`option_material_gauge`** (DX / HGRH TubeMaterial + FinMaterial): whole-material equality
  (`Aluminium` spelled `Aluminum`; `Aluminum` is never `Coated aluminum`), numeric gauge equality
  (`0.0075` never becomes `0.008`; ledger `0.01` is `0.010`), and a tube surface that must be stated.
- **Smooth = Plain** (John). The surface is the canonical `materials_construction.tube_surface`; the
  ledger keeps it only as the drawing's `slot.TUBE_MATERIAL_2`, which `load_coils` now reads. No
  stated surface → unmapped, even where `Plain` is the only candidate.
- Ledger replay: TubeMaterial DX 0 → 145/156, HGRH 0 → 92/92; FinMaterial DX 0 → 105/156, HGRH
  0 → 66/92. Still unmapped: `0.0075` fins (DX 41, HGRH 26 — D7 territory), one DX coil with no
  recorded surface, and the intake column bleed (`0.016 Copper Refrig. PD`).
- Cross-check: DX Tube 3183 / 3237 match, 3232 mismatch (D5 — CCSI re-selected 0.020); DX Fin 3232 /
  3237 match, 3183 off-vocabulary (0.0075). HGRH Tube 3 / 3 match; Fin 3232 / 3237 match, 3183
  off-vocabulary.
- **Promotion "A" (John 2026-09-30):** HGRH `TubeMaterial` → `validated` (3183 / 3232 / 3237 match,
  0 mismatch). DX `TubeMaterial` stays `captured` (3232 = D5 CCSI re-selection, a rule exception John
  did not take); both `FinMaterial` entries stay `captured` (match on 2 projects only — 3183 is 0.0075).
- Water coils print no tube or fin material, so their CWC / HWC entries stay `option_exact` with
  no source (a D2 question, not D1).

## Decided 2026-09-30 — Coil coating (John)

"드랍다운에 매칭되는 코팅이 있으면 선택하되, 없으면 coating을 선택, note section과 도면에 coating
노트를 꼭 추가."

- CCSI's Coil Coating dropdown is `Plain` / `AA Coating` (re-captured live on 2803 CDXC-1, 2026-09-30).
  Transform `option_coating`: a coating the dropdown names is selected by name; any other stated
  coating (ElectroFin, Finkote, Heresite, Blygold, Black Poly) selects `AA Coating`, with the reason
  saying so; no coating → `Plain`. Two coating options would be ambiguous and stay unmapped.
- The Drawing Notes (paste field → CCSI `#DrawingNotes`) now lead with the coating's name
  (`<FAMILY> COATING REQUIRED`, `submittal_to_drawing._engine_drawing_notes`), before the R-080 /
  R-081 "Do Not Coat Last 5-6 inches" note. The drawing already stamped the same text on every
  template (`_inject_coating_note_label`).
- The gap was upstream: the intake's coating vocabulary (the Coil Checklist families) had no `AA`,
  so a cover "Miscellaneous AA coil coating adder" (2840) read as no coating and pushed `Plain`.
  `AA` is now a family (only with a coating word after it), and the adder is matched across its
  two-line wrap. The Coil Checklist has no AA option — it receives `AA` as a review-required value.
- Water coils are never coated (`_drop_coating_from_water_coil`), so they get neither the option
  nor a note. Tests: `tests/test_coating_ccsi_and_notes.py`.

## Bug fix 2026-09-30 — water fluid block (John: "glycolratio 먼저 버그를 고치도록")

- The submittal's `Fluid Percent (%)` is the share of the fluid it names (`Water` + 100,
  `Propylene` + 40); CCSI's `Fluid Ratio(%)` is the glycol share. Read straight across, plain
  water went out as 100 % glycol (3154 HHWC-1/2, 2954 CCWC-1/2: CoilForge 100 vs CCSI 0).
  Transform `glycol_ratio`: Water → 0 (only at 100 %; any other percent contradicts itself and
  stays unresolved), a glycol → its percent, no stated fluid → unresolved (never guessed).
- Same root, same fix: the submittal names the glycol without the word, so `FluidType` uses
  `option_fluid_type` (`Propylene` → `Propylene Glycol`, `Ethylene` → `Ethylene Glycol`).
- Both stay `captured` (not pushed) until the order batch supports promotion. Re-check on 2954
  (same-PDF ledger pairing): GlycolRatio 0 = 0 and FluidType Water = Water on both coils.
  Tests: `tests/test_ccsi_fluid_block.py`.

## Finding 2026-09-30 — the report's "OPPOSITE END COIL REQUIRED" note is not Connection Ends

`report_extras` first read that report note as the form's `ConnectionEnds = Opposite End Only`. The
adapter calibration disproved it: the four harvested coils that carry the note (2954 CCWC-1,
3183 RHHGRC-1, 3154 HHWC-1, 3154 HHWC-2) all read `Same End Only` on their live CCSI forms. The
note is now left unmapped (it appears on 64 report pages); which field — if any — it reflects is
an open question for John. `ConnectionEnds` stays a D2 default that the reports cannot test.
With it removed the calibration is PASS again, and the fields the extras do capture calibrate
cleanly: capillary 3/3, drain & vent 6/6, feeds from the model number 11/11.

## Decided 2026-09-30 — order cross-check "A" (John: "A + altitude")

Source: CCSI selection reports of 77 ordered projects / 212 coils (`scripts/ccsi_report_crosscheck.py` +
`scripts/ccsi_order_gate.py`, adapter calibration PASS against the 12 live harvests).

- **Promoted to `validated`:** HGRH `Subcooling` (74/74), `CondensingTemperature` (74/74, all 115),
  `CoilQuantity`; DX / HWC `CoilQuantity`; CWC / HWC `FluidType`, `GlycolRatio` (16/16 after the glycol
  fix), `EnteringFluidTemp` (16/16), `LeavingFluidTemp` (13/15); CWC `EnteringWetBulb`.
- **HGRH `VaporTemperature` = default 140:** the submittal never states it; 74/74 ordered reports print 140.
- **Demoted:** CWC / HWC `FluidFlowRate` (GPM matched 8/16 while EWT/LWT matched — CCSI solves the flow
  from the temperatures; the 2026-09-29 "push GPM" decision is reversed).
- **Kept:** every validated field at ≥90 % order agreement (the strict "one unexplained mismatch" list is
  mostly order-time re-selections without a REV0 to show it). Altitude: the submittal value stays
  (John ①), although CCSI selections often left 0 (DX 17 / HGRH 12 coils).
- **Not decided / watch list:** `ACFM` (orders split Actual 135 / Standard 77 — no rule, left to the
  engineer); below-90 % fields not demoted (HWC FinSurface 7/9, HWC FPI 10/13, HWC ConnectionMaterial
  11/13, HGRH feeds 66/74, CWC ConnectionMaterial / TubeTurbulators 2/3).
- Gate change: a numeric difference at printed precision (≤0.015 or ≤0.2 %) is cause `rounding`, not a defect.
- Three submittals never finished extraction (2982, 3037, 3191; >30 min each) and are not in these counts.

## Decided 2026-10-01 — Air flow basis = Actual (John)

The `ACFM` watch-list item above is settled: **CCSI "Air flow basis" = `Actual`** on all four forms
(`default`, `validated`; the submittal never states it). John: Direct Coil selections have been calculated
in ACFM; SCFM would be the ideal basis, but it is not what the orders were rated on. The order split
(Actual 135 / Standard 77) is a mid-corpus switch, not noise — relayed by the performance-validation
session from `crosscheck.json`: with the coil's own Actual basis 26/26 ordered heating coils reproduce
capacity, 0/7 on Standard (Likely; not re-derived here).

- Push order is load-bearing: under Standard CCSI locks Altitude to 0 and stage 1 skips a locked field, so
  `ACFM` comes before `Altitude` in every map (pinned by a test).
- Expected order-gate effect: Altitude "unexplained" (DX 17 / HGRH 12) were Standard-selected coils whose
  altitude CCSI locked to 0; ordered coils selected on Standard will now show an `ACFM` mismatch. Neither
  is a CoilForge defect — a gate cause "air basis" is the open follow-up.
- **Standard (SCFM) is parked on the roadmap as a suspect area** (John 2026-10-01), not adopted.

## Implementation already in scope (no decision needed)

- Thread canonical-only values into the coil-data source (plan Step A): HGRH vapor / condensing /
  subcooling, water fluid type / % / EWT / LWT / GPM / PD. They are extracted but absent from the
  draft and the ledger, so the comparison needs a re-parse of those projects' submittals.
- Collect more coils: ≥3 projects per category before any `validated` proposal; one finished HWC.
