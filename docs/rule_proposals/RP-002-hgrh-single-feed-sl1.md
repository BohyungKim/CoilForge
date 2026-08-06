# RP-002 — Reconcile the Coil Checklist's two answers for single-feed HGRH `SL1`

**Status:** proposed · **Target:** Oxygen8's `Coil Checklist Template.xlsx`, not CoilForge
**Raised by:** KD-006 … KD-009 (`src/coilforge/rules/known_divergences.yaml`)
**Adjudicated:** 2026-08-06 · John

> **Nothing is applied by this document.** It targets a spreadsheet CoilForge does not
> own. CoilForge's own behaviour was changed separately (the slot layer now draws 6); this
> is the matching correction on the sheet's side, for Oxygen8 to accept or reject.

---

## The defect

The HGRH sheet states the single-feed supply stub dimension **twice, with different
values**, and both are live at once:

| Cell | What it says when `C14 = 1` (FEEDS/CIRCUITS) |
| --- | --- |
| `HGRH!C58` (the `SL1` dimension row) | `IF(C3="TERRA V",5, IF(C14=1, 3, 6+C15/2-C46))` → **3** |
| `HGRH!C26` (NOTES) | `… " Add Headers & Stubouts. I1=2. SupConnAngle=LAS. S1="&C46&". SL1=6. …"` → **6** |

`C26` carries that note in **all three** product branches:

| Branch | Note text (abridged) |
| --- | --- |
| `C3="TERRA H"` | `… SL1=6. O2=3.25. R2=<C42>. HD2=3.5. SL2=10` |
| `C3="NOVA"` or `"VENTUM H"` | `… SL1=6. O2=2. R2=<C42>. HD2=3.5. SL2=8` |
| `C3="VENTUM+"` | `… SL1=6. O2=2. R2=<C42>. HD2=3.5. SL2=10` |

`TERRA V` has no add-headers branch, and its `SL1` comes from the SOP as `5`. It is not
part of this proposal.

## Why 6 is the right answer

A single-feed coil has **no supply header of its own** — `C26` exists precisely to
instruct that one be added. The header that then appears on the drawing IS the added
header, so the dimension the drawing must carry is the note's, not the row's.

Every other source agrees with the note:

| Source | Value |
| --- | --- |
| `HGRH!C26`, all three product branches | `SL1=6` |
| `R-044a` `supply_sl` (HGRH NOVA / VENTUM_H, MEDIUM) | `6` |
| `R-044c` `supply_sl` (HGRH VENTUM_PLUS, HIGH) | `6` |
| EZC-0002 / EZC-0010 as-built notes (`json_drawing_link_rules.yaml`) | `SL1=6` |
| `coilmaster_vplus_hgrh_lh_header1` seeded reference, baked note | `SL1=6` |
| `HGRH!C58` | **`3`** |

`C58`'s `3` is the lone dissent, and no reading of it has been found that makes it the
drawn dimension.

## Required change

`HGRH!C58`'s single-feed arm should return `6`:

```
=IF(C3="TERRA V", 5, IF(C14=1, 6, 6+C15/2-C46))
                             ^ was 3
```

The multi-feed arm and the Terra V arm are unchanged.

⚠️ **Verify the cell address against the workbook before editing.** `C58` was read out of
the live template on 2026-08-06, but the template is external and gitignored, so nothing in
this repository can confirm it stays there.

## If `3` is actually right

Then the defect is in `C26` instead, and the same reconciliation is still required — the
sheet cannot keep both. In that case CoilForge's change should be reverted (it is a single
branch value in `direct_coil_drawing_pipeline.build_drawing_slots`, pinned by
`test_hgrh_single_feed_sl1_is_six`) and KD-006…009 re-adjudicated as `coilforge_wrong`,
which by design stays RED rather than dimming to amber.

## What CoilForge does until this is resolved

Draws `6`, and **reports the disagreement** rather than hiding it. The checklist compare
still computes the sheet's `3` independently and shows both; KD-006…009 re-label that row
from red to amber with this reasoning attached, gated by `delta_band {3, 3}` so only the
single-feed case is covered. A multi-feed HGRH coil, where CoilForge and the sheet agree
exactly, is untouched and any future disagreement there still escalates.
