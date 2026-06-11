# case_006_v60_dx_hgrh_combined_image_seed

Sanitized draft mapping case for an Oxygen8 V60 unit with two detected coil
instances in the same cover-page sequence:

- `CDXC-1` maps to the supplier `Cooling DX` section and Direct Coil `DX COIL DATA`.
- `RHHGRC-1` maps to the supplier `Reheat Hot Gas Reheat Coil` section and Direct Coil
  `CONDENSING COIL DATA`.

## Source Images

Images were used as visual transcription inputs only. They are not copied into this
repository.

- Cover page: `codex-clipboard-f16c44c3-dc4b-43b5-b3fd-f786c917a0b8.png`
- Unit summary: `codex-clipboard-00fde7fc-ee49-4adc-bea3-57358b58962f.png`
- Cooling DX PDF section: `codex-clipboard-4d56b90f-d5ed-4601-ae76-b5dbab650530.png`
- HGRH PDF section: `codex-clipboard-eb95cb2e-3ab6-4e0b-bb91-5b5572c04a14.png`
- Direct Coil DX output: `codex-clipboard-7a6fef32-7300-4bd7-84e1-4ef3ddec24de.png`
- Direct Coil condensing output: `codex-clipboard-4e4efb17-1c29-4ed2-8c1f-d58db66f9258.png`

## Review Required

- `CDXC-1` Direct Coil `Fins Per Inch` shows `12` while the PDF `Cooling DX` section
  shows `FPI` as `11`.
- `CDXC-1` Direct Coil `Leaving Dry Bulb` shows `55.00` while the PDF operating
  setpoint DB shows `54.5`.
- `RHHGRC-1` Direct Coil `Fins Per Inch`, `Number Of Feeds`, and `Fin Surface` differ
  from the shown HGRH PDF section.
- `RHHGRC-1` Direct Coil refrigerant fields such as saturated suction, compressor
  suction, and vapor temperature are visible in the Direct Coil output but not in the
  shown HGRH PDF section.

## John Review Notes - 2026-06-11

- `CDXC-1` FPI and leaving dry bulb mismatch: keep as `review_required`. John noted
  this may be either an application engineer mistake or an intentional adjustment to
  keep the leaving dry bulb similar or below the supplier value.
- `RHHGRC-1` FPI and feeds mismatch: keep as `review_required` for the same reason.
- `RHHGRC-1` fin surface mismatch: John identified this as an application engineer
  misselect. The Direct Coil screenshot output remains `Flat` as visible target
  evidence, but future mapping logic should not learn `Flat` as the supplier-derived
  value for this PDF row because the PDF source says `Sine`.
- `RHHGRC-1` Direct Coil-only refrigerant values remain unresolved. John is unsure of
  the source for these values, so they stay `review_required`.
