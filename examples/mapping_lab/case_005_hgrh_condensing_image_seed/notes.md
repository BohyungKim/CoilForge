# case_005_hgrh_condensing_image_seed

Sanitized draft mapping case for an Oxygen8 RHHGRC/HGRH reheat coil that maps to the
Direct Coil `CONDENSING COIL DATA` screen.

## Source Images

Images were used as visual transcription inputs only. They are not copied into this
repository.

- Cover page: `codex-clipboard-ebe55166-8bcd-4209-b5a9-38cf70c9e7d0.png`
- Unit summary: `codex-clipboard-b62c921f-6607-4205-b666-9b4577888f20.png`
- PDF coil section: `codex-clipboard-7463baa5-6b45-4401-bc41-620bed6ba787.png`
- Direct Coil filled screen: `codex-clipboard-5fbdb202-9cca-4e6a-a88b-76ece9a71de1.png`

## Mapping Intent

- `RHHGRC-1` from the cover page maps to the next `Reheat Hot Gas Reheat Coil`
  supplier section.
- The Direct Coil target format is `condensing`, not hot water.
- Shared unit summary values such as altitude apply to the coil mapping when the
  Direct Coil output expects them.
- Values visible only in the Direct Coil screen remain `engineer_default` or
  `review_required`.

## Review Required

- Confirm whether `Tubes High` should always use PDF `Fin Height (in)` for this
  Oxygen8 HGRH/condensing case.
- Confirm Direct Coil condensing screen values for `Leaving Dry Bulb`, `Saturated
  Suction Temperature`, `Suction Temperature at Compressor`, and `Vapor Temperature`,
  because those are visible in Direct Coil but not directly present in the shown PDF
  HGRH section.
- Confirm whether PDF `Capacity (MBH)` should remain unmapped when the Direct Coil
  screen shows `Total Capacity(MBH)(Per Coil)` as `0`.

