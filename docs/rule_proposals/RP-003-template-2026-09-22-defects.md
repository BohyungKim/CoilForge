# RP-003 — Three defects in the 2026-09-22 Coil Checklist template

**Status:** proposed · **Target:** Oxygen8's `Coil Checklist Template.xlsx`, not CoilForge
**Raised by:** the 2026-09-22 template back-crack (KD-005 / KD-022 / KD-023 in
`src/coilforge/rules/known_divergences.yaml`)
**Adjudicated:** 2026-09-22 · John (item 1 ruled a sheet defect; items 2–3 reported)
**Updated 2026-09-24 (John):** item 1 confirmed and scoped — every Terra V return I/O
(O2/O4/O6/O8) is 2.75 and every Terra H one is 3.25; item 2 goes on the fix-request list;
item 3 is **FIXED** in the 2026-09-24 template (`CWC!C20` now reads `C27`).

> **Nothing is applied by this document.** It targets a spreadsheet CoilForge does not
> own. CoilForge's behaviour for item 1 is to keep its own value (2.75) and label the
> disagreement amber; items 2–3 do not change any CoilForge number.

---

## 1. HGRH Terra V: `O4 / O6 / O8` = 2 while `O2` = 2.75

| Cell | Formula (2026-09-22) | Terra V result |
| --- | --- | --- |
| `HGRH!C37` (O2) | `IF(C3="VENTUM+",IF(C16=1,2,"TBD"),IF(C3="TERRA H",3.25,IF(C3="TERRA V",2.75,2)))` | **2.75** |
| `HGRH!C38` (O4) | `IF(C3="VENTUM+",…,IF(C16>1,IF(C3="TERRA H",3.25,2),"N/A"))` | **2** |
| `HGRH!C39` (O6) | same shape as C38 | **2** |
| `HGRH!C40` (O8) | same shape as C38 | **2** |

The Terra V arm was added to `C37` only. A return I/O that differs between header 1
and header 2 of the same coil has no engineering basis. John ruled this a sheet defect
(2026-09-22) and confirmed the scope on 2026-09-24: **Terra V = 2.75 on every return
header, Terra H = 3.25 on every return header** (the Terra H arm in `C38:C40` is already
correct). CoilForge draws exactly that (R-042v / R-042).

**Proposed fix:** add `IF(C3="TERRA V",2.75, …)` to the inner `IF` of `C38:C40`, mirroring
`C37`. Still present in the 2026-09-24 template.

## 2. HGRH `SL5` / `SL7` reference `C47` (S3) instead of `C48` / `C49`

| Cell | Formula (2026-09-22) | Should reference |
| --- | --- | --- |
| `HGRH!C62` (SL5) | `IF(C16>2,6+C15/2-C47,"N/A")` | `C48` (S5) |
| `HGRH!C64` (SL7) | `IF(C16>3,6+C15/2-C47,"N/A")` | `C49` (S7) |

Numerically inert today because `S1 = S3 = S5 = S7` on every product line (one supply
position per coil), but a future per-header S would silently print the wrong SL5/SL7.
**On the fix-request list (John 2026-09-24).** Still present in the 2026-09-24 template.

## 3. CWC NOTES references `C327` (should be `C27`) — FIXED 2026-09-24

`CWC!C20`: `…"Add Headers Stubouts and Copper Straps I-" & TEXT(C327, "# ?/?") & …`

`C327` is an empty cell, so the single-feed note prints `I- ` with no value. `C27` is
the I row. (The HWC twin, `HWC!C24`, correctly references `C31`.)

Cosmetic but engineer-facing: the note is what gets pasted into the order.
**Resolved:** the 2026-09-24 template reads `TEXT(C27, "# ?/?")` (checked with openpyxl).

## Also noted (no fix requested)

- `CWC!E8` uses relative `Units!C21:C29` / `Units!C56:C68` where the other sheets use
  absolute references — works as long as the cell is not copied.
- `Install | Drain Pan Width!B23` still reads `TBD` under the now-filled Terra V rows.
