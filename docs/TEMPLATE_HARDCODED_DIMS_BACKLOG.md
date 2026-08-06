# Backlog — un-redacted hardcoded dimension callouts in seeded templates

**Status:** DEFERRED (John, 2026-06-22 — "(나)로 진행, 일단은": leave as-is for now, track here).
**Owner gate:** John / engineering. Do **not** edit template SVGs without his per-dim slot mapping.

## What this is

During the geometry-only crop review (label-code view), several seeded CoilMaster
templates were found to still carry **as-built numeric values baked directly into the
dimension callouts** instead of `{{slot.X}}` placeholders. The seed/redaction step
slotted most dimensions but missed these.

These are **not** a crop / numbers-only display issue — the numbers live in the template
SVG source. The crop change (`_clean_template_svg`, viewBox `110 19 542 473`) is unrelated
and complete.

## Why it matters (latent correctness bug)

A hardcoded callout is **frozen to the seed coil's value** — when a *different* coil
populates that template, the dimension will still show the seed number (e.g. CWC always
draws `4.00 HD1`, `8.00 SL1`) instead of the actual coil's value. This is a
**drawing-template accuracy** defect for the affected families. DX is unaffected.

## Audit (as of 2026-06-22)

| Family | Templates | Hardcoded dims found |
| --- | --- | --- |
| **DX** | header1–4, HGBP, LH+RH (12) | **none — fully slotted ✓** |
| **CWC** | `cwc_lh` | `2.31 I` · `1.68 S` · `2.31 O` · `1.68 R` · `4.00 HD1` · `8.00 SL1` · `3.90 X` |
| | `cwc_rh` | `2.31 I` · `1.70 S` · `2.31 O` · `1.70 R` · `4.00 HD1` · `8.00 SL1` · `2.60 X` |
| **HWC** | `hwc_lh` | `2.31 I` · `1.63 S` · `2.31 O` · `1.63 R` · `3.00 HD1` · `12.00 SL1` · `1.38 X` |
| | `hwc_rh` | `2.31 I` · `1.63 S` · `2.31 O` · `1.63 R` · `3.50 HD1` · `8.00 SL1` · `1.38 X` |
| **HGRH** | `hgrh_lh_header1` | `3.00` *(no label)* |
| | `hgrh_rh_header1` | `4.13 SL1` · `1.25 X` |
| | `hgrh_lh_header2` / `rh_header2` | `-0.25 S1` · `6.56 SL3` · `3.38 X` |
| | `hgrh_lh_header3` | `5.63 SL5` · `5.50 X` |
| | `hgrh_rh_header3` | `-0.63 S1` · `6.94 SL5` · `5.50 X` |
| | `hgrh_lh_header4` | `5.50 SL7` · `7.63 X` |
| | `hgrh_rh_header4` | `5.38 SL7` · `7.63 X` |

(Regenerate with the audit snippet: blue `#1c0a80` callout tspans containing a literal
digit and no `{{slot}}`.)

## Open questions to resolve before redacting (the "(가)" path)

1. **`X` label** — which dimension/slot does the `… X` callout map to? (appears near CD.)
2. **`hgrh_lh_header1` bare `3.00`** — what dimension is this, and its slot?
3. **Negative `S1` values** (`-0.25`, `-0.63`) — confirm these are normal slot targets.

## When reactivated

Map each hardcoded callout to its slot (`4.00 HD1` → `{{slot.HD1}}`, `8.00 SL1` →
`{{slot.SL1}}`, `… X` → `{{slot.???}}`), edit the template SVGs (DO-NOT-TOUCH gate lifts
only with John's explicit go for this task), update `slot_map.json` if new slots appear,
and re-run the full suite + a label-code contact sheet to confirm the values became
placeholders.
