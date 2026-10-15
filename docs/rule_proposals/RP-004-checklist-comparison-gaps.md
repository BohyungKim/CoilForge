# RP-004 — Coil Checklist rows that cannot be compared with CoilForge

**Status:** proposed · **Target:** Oxygen8's `Coil Checklist Template.xlsx` (Dave), plus the
CoilForge-side items listed separately at the end
**Raised by:** John, 2026-09-24 — "list every checklist item whose missing data makes the
CoilForge comparison hard, so Dave can update the sheet and the two align exactly"
**Evidence:** the 2026-09-24 template read with openpyxl (formulas, all four coil sheets);
the capture ledger's `compare_observation` rows for the checklist comparator (8,108 rows,
historical — counts include runs made before earlier fixes, so they show *where* rows fail
to compare, not current mismatch rates)

> **Nothing is applied by this document.** The workbook is Oxygen8's. CoilForge keeps its
> own values; a row that cannot be compared is shown as missing, never guessed.

---

## A. The sheet returns no number

### A1. HGRH `I3 / I5 / I7` are always `"TBD"`
`HGRH!C34:C36` = `IF(C16>k,"TBD","N/A")` on every product line. A multi-connection HGRH
therefore never has a supply I/O beyond header 1 to compare (ledger: sheet `TBD` on 55 of
55 `I3` rows). CoilForge draws the same supply I/O on every supply header (`I1 = I3 = I5 =
I7`, John 2026-09-09), and `I1` itself is `=2` on the sheet.
**Request:** `C34:C36` → `IF(C16>k, C33, "N/A")` (the header-1 value).

### A2. HGRH Ventum+ return I/O is `"TBD"` for multi-connection coils
`HGRH!C37` (O2) = `"TBD"` when `QTY CONN/HEADER ≠ 1`; `C38:C40` (O4/O6/O8) = `"TBD"` when
`C16 > k`. A Ventum+ (and Omnia, filled as Ventum+) HGRH with 2+ connections has no return
I/O to compare.
**Request:** a numeric Ventum+ value for every connection count.

### A3. Water `I / O / S / R / HD / OAL` blank when FEEDS/CIRCUITS is empty
`CWC!C27` (I), `C28` (O), `C33` (HD) and the HWC twins (`C31`, `C32`, `C37`) are
`IF(C14="","",…)`; S and R chain off I/O, and OAL off HD. Since the 2026-09-22 refresh
removed the single-feed special, **none of these values depends on the feed count** — yet
a submittal without FEEDS blanks the whole block (ledger: CWC HD/OAL/CH blank on both
sides in 14 of 18 runs).
CoilForge used to gate the same way. **John decided 2026-09-24: drop the gate on both
sides.** CoilForge now emits water I/O and HD at full confidence without FEEDS (feeds 1 and
4 give identical I/O/HD/OAL), so until the sheet follows, these rows read "missing on the
checklist side" rather than both-blank.
**Request:** gate `CWC!C27/C28/C33` and `HWC!C31/C32/C37` on `C3` (UNIT) instead of `C14`.

## B. Missing product lines / data

### B1. No OMNIA unit
The UNIT list and the Units tab have no OMNIA (`OW050…OW085`). CoilForge fills Omnia as
`VENTUM+`, so the sheet computes TF/BF = 1.0 where Omnia is 0.625 — 12 known-divergence
entries (KD-010..021) exist only to label that row amber, and SIZE is left blank (not in
the list).
**Request:** an OMNIA unit with TF/BF = 0.625, its sizes, and — when available — casing
W/H, drain-pan and install widths (CoilForge has none of these either; R-074/077/078).

### B2. `Install | Drain Pan Width!B23` still reads `TBD`
Under the Terra V rows filled on 2026-09-22.
**Request:** a value, or delete the row if it is a leftover.

### B3. HGRH CD / S have no explicit Terra V arm
`HGRH!C27` (CD) and `C46:C49` (S) send Terra V through the NOVA / VENTUM H else-branch.
That is now the agreed behaviour (John 2026-09-23: Terra V HGRH CD always follows the
checklist; KD-001 retired), but it is implicit.
**Request (low):** add an explicit `IF(C3="TERRA V", <same as NOVA/VH>, …)` so a future
edit to the Nova/Ventum H branch cannot silently change Terra V.

## C. Formula defects (carried from RP-003)

### C1. HGRH Terra V `O4 / O6 / O8` = 2 (should be 2.75)
`C38:C40` lack the Terra V arm that `C37` has. John 2026-09-24: Terra V = 2.75 and
Terra H = 3.25 on **every** return header (the Terra H arm is already right). Ledger:
52 of 55 `O4` rows mismatched. **Request:** add `IF(C3="TERRA V",2.75,…)` to `C38:C40`.

### C2. HGRH `SL5 / SL7` subtract `C47` (S3)
`C62` should use `C48` (S5), `C64` `C49` (S7). Inert today (one supply S per coil).

## D. Stale constant

### D1. DX / HGRH `RB` = 1.75
`DX!C29` and `HGRH!C32` are `=1.75`; the rule is **1.5** (John 2026-06-25, R-005).
CoilForge overwrites the cell with 1.5 on every fill so OAL recomputes correctly — which
means the sheet's own value is never used. **Request:** change both to `=1.5`. (The water
sheets' RB already carries the right family-branched rule.)

---

## CoilForge side — no action for Dave

These rows exist on the sheet but CoilForge does not compare them yet:

| Sheet | Row(s) | Why not compared |
| --- | --- | --- |
| DX | `DIST ORIENTATION` | CoilForge has the value (`slot.DIST_ORIENTATION`, R-031/R-032) but the compare has no mapping — a CoilForge follow-up |
| DX | `ASC`, `ASC ORIENTATION` | HGBP flag/orientation; not a drawn dimension |
| CWC / HWC | `SUPPLY V/D ANGLE`, `VENT & DRAIN` | Text constants (`LAS`, `ConnEnd`); CoilForge's R-066/R-066a agree by rule |
| HGRH | `NO INTERFERENCE` | Manual check by the engineer |
| all | `WIDTH / HEIGHT / INSTALL FIT` | Evaluated separately by CoilForge's Mechanical Fit card |

Inputs that are often blank because the **submittal** does not state them (not a sheet
defect): water FEEDS (see A3), Terra drain-pan option (read from the unit model code when
printed), HWC APPLICATION.
