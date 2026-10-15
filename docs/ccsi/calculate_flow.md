# CCSI Calculate flow (Step E, observed live 2026-09-30)

Test coil 2803 CDXC-1 (John's own project), stage-1 values from the 3237 CDXC-1 ledger draft.
Calculate was pressed once with John's approval; Save / Apply / Custom Dimensions were not.

## Request chain

| Step | Trigger | Request |
|---|---|---|
| field edit | each field's inline `onchange` → `getDependencyOptions(field)` | `POST /Coils/GetDependencies` (19 calls for 24 fields) |
| Calculate | `#calcBtn` → `calculateCoilData(projectId, revisionId)` | `POST /Coils/Calculate` |
| after Calculate (DX) | automatic | `POST /Coils/GetDXDistFeeds` `{"id": …}`, `POST /Coils/GetDXDistModels` `{"supplier":"Sporlan","capillary":"1/4 x 0.025","feeds":"1"}` ×2, `POST /Coils/UpdateDXCircuitSplitData` (Dual-Circuit), `GET /Coils/Draw3d` |
| Custom Dimensions | `#customDimensionsButton` → dimension grid (`cdFormId`) | — |
| Apply dims | `customDimensionsApply()` | `POST /Coils/CustomDimensionsApply`, then `calculateCoilData` again |
| Save | `#saveButton` / `#saveToProjectButton` / `…AndContinue…` | separate buttons |

`POST /Coils/Calculate` body (JSON, 2,265 chars):

```json
{ "jsonInputs": "<JSON.stringify(convertFormToJSON(#coilFormId))>",
  "coilId": 8103782, "projectId": 351437, "revisionId": 537707 }
```

`convertFormToJSON` = `serializeArray` → flat `{name: value}` (first occurrence wins; select VALUE,
e.g. Tube Material `Copper - 0.016 Plain`, ACFM `SCFM`). The response is an **HTML fragment**
(13 KB) rendered into `#mainResult` — results are read from the DOM, not from JSON.

## Result read back (DX, 3237 conditions on 2803 geometry)

Model `3DX-04-21.0-11-32.0-2`; total capacity **48.3 MBH** (sensible 37.79), LDB 64.07 / LWB 61.36 °F,
air PD 0.29 inWG, refrigerant PD 32.56 PSIG, mass flow 347 lb/h. The 3237 submittal says 108.9 MBH:
rows 4 matched, but **FPI (11 vs 13) and feeds (2 vs 8) were not pushed** — DX RowsDeep / FinsPerInch /
NumberOfFeeds are still `captured`, so the saved 2803 values stayed. Rating mode is only meaningful
once the geometry fields are pushable.

## End-to-end Rating check — geometry promoted (John 2026-09-30 "A")

After DX/HGRH rows / FPI / feeds / fin surface / hand were promoted, stage 1 set 29/30 (Altitude
locked under ACFM = Standard, as before) and Calculate returned:

| | geometry not pushed | **geometry pushed** | 3237 submittal |
|---|---|---|---|
| Model | 3DX-04-21.0-11-32.0-2 | **3DX-04-21.0-13-32.0-8** | — |
| Total capacity | 48.3 MBH | **112.07 MBH** (sensible 66.29) | 108.9 MBH |
| Leaving DB / WB | 64.07 / 61.36 °F | **50.92 / 50.13 °F** | 50.75 °F |
| Air PD / refrigerant PD | 0.29 inWG / 32.56 PSIG | 0.33 inWG / 3.99 PSIG | — |

CCSI rates the CoilForge-pushed coil within +2.9 % capacity and +0.17 °F LAT of the submittal.
The residual is expected: altitude stayed 417 ft (the form's own lock), and CCSI is a different
selection engine. The product record was still unchanged afterwards (not saved).

## Persistence (Confirmed)

Before and after Calculate the project list showed CDXC-1 unchanged: model `3DX-04-12.0-11-24.0-2`,
weight 32, modified `Tue Jun 30 2026, 15:21:35`. Calculate does not save the product. (What
`UpdateDXCircuitSplitData` stores server-side is not visible from the product list — Unknown.)

## Custom Dimensions grid (observed after John's own Calculate → Custom Dimensions, 2026-09-30)

- `#customDimensionsButton` → `navigateCustomDimensions(calcCoilId, 'Imperial', '0')` →
  `POST /Coils/CustomDimensions/{calcCoilId}/Imperial` → HTML grid (41 KB) inside `#cdFormId`.
  `calcCoilId` (9002409 here) is the calculation's id, not the saved product id (8103782).
- All 13 dimension-map selectors resolve inside the grid (`#HS #VS #HR #VR #EF #FF #CS #DX_ZD #CD
  #BF #HD #TF #CH`); header 2 is `#DX_HS2 / #DX_VS2 / #DX_HR2 / #DX_VR2 / #DX_HD2 / #DX_ZD2`.
  Read-only until their `<id>_isActive` is ticked: EF, FF, CH (CCSI-computed) and the header-2 S/R/I/O.
  Also in the grid: `DX_DistX/Y`, `Connections`, `MountingHoles`, `ApplyVDConstraints`.
- **There is no separate Apply button.** `calculateCoilData` calls `customDimensionsApply`
  (`POST /Coils/CustomDimensionsApply`) — pressing **Calculate again with the grid open applies the
  dimensions**. Save / Save & Continue (`saveToProject` / `saveAndContinueToProject`), Drawing,
  Psychrometric, TechSpec and Cancel are separate buttons.

## One button — v3.1 (built and live-tested 2026-09-30)

Technically possible from the userscript, pressed by the engineer:
stage 1 fill → click `#calcBtn` → wait for `/Coils/Calculate` + `#mainResult` → click
`#customDimensionsButton` → wait for the grid → stage 2 fill → **stop before Apply and Save**.
Claude pressing Calculate directly was blocked by the Claude Code permission classifier once and
allowed after John approved (option B); the product-side button keeps a human click in the loop.

### Live test (2803 CDXC-1, 3237 values, not saved)

"▶ Run all" in the panel: stage 1 → `#calcBtn` → `#customDimensionsButton` → stage 2, then stop.

| Step | Time | Result |
|---|---|---|
| 1 coil data | 3 s | 29/30 set; Altitude skipped (CCSI-locked under ACFM = Standard) |
| 2 Calculate | 13 s | `/Coils/Calculate` 200 (grid was open, so CCSI also posted `CustomDimensionsApply`) |
| 3 Custom Dimensions | 5 s | grid re-rendered, `#CD` found inside `#cdFormId` |
| 4 drawing parameters | < 1 s | **10/10 set and verified** (CD 5.5, I 3, S 1.875, O 2, R 0.875, BF/TF 0.625, HD 3.5, SL 8, ZD 4.5); HF / RF / CH skipped (CCSI-computed) |

No alert, no Save; the product list still showed `3DX-04-12.0-11-24.0-2`, `Jun 30 2026, 15:21:35`.

- **First attempt timed out** after a successful Calculate: with the dimension grid open CCSI keeps
  `#mainResult` `display:none`, so a visibility test on it never passes. Arrival is now "marker gone +
  `#customDimensionsButton` visible" (pinned by `test_run_all_does_not_require_the_hidden_result_block_to_be_visible`).
- The grid has its own **"Update Drawing"** control (a `<div>` under the grid, handler bound elsewhere) in
  addition to Calculate re-applying the dimensions. v3.1 presses neither.
- The live run injected the v3.1 CCSI-side code into the page (the Tampermonkey install path was not used);
  the panel's display helpers were simplified in the injected copy, the fill / wait / verify functions were not.

### Live test 2 (2803 CDXC-1, CoilForge's own 2803 payload, not saved)

The payload was CoilForge's real 2803 analysis (29 pushable coil-data entries + 13 drawing fields),
carried from the CoilForge tab into the CCSI tab verbatim (5955 chars, parsed + schema-checked by
`load`). The shipped v3.1 file was injected unchanged apart from two test hooks
(`window.__cfLoad`, a `__cfRunAllDone` flag).

- Run all: **9.3 s**, "10/10 drawing parameters set", no alert, stage 1 had no reset/mismatch
  (Altitude read-only under ACFM = Standard, as before).
- CCSI rated `3DX-04-12.0-11-24.0-2`, the **same model number as the saved selection**.
- Rating vs the submittal (capture ledger draft stage): Total Capacity **32.37 = 32.37 MBH**, Leaving
  Dry Bulb **52.14 = 52.14 °F**, Face Velocity **392.5 = 392.5 FPM** — exact on all three.
- Grid after stage 2: CD 5.5, HS 3, VS 2.75, HR 2, VR 0.625, BF/TF 0.625, HD 3.5, CS 17, DX_ZD 4.5;
  FF/EF 1.500 and CH 13.25 untouched (CCSI-computed).
- Product list afterwards: CDXC-1 still `Tue Jun 30 2026, 15:21:35` — nothing saved.
- **D4 evidence:** after Calculate the form's `#LeavingDryBulb` input still reads `55.00` (read-only), while
  the `#mainResult` rating block reads 52.14 = submittal. The "fixed 55" in the harvests is that locked
  input, not the rating; the rating LDB lives in `#mainResult` (and the report PDF) and is comparable.
- Caveat: John had set this form up as 2803 CDXC-1 beforehand, so every pushed value equalled the
  value already on the form. This proves the flow and the rating round-trip, not that a blank or
  different form is overwritten correctly (Live test 1 covered that with 3237 values).
