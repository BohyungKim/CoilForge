# Case 004 - DX Image Seed

Sanitized draft case transcribed from paired PDF screenshots and a Direct Coil selection screenshot provided in chat.

## Source Images

The source images were not copied into the repository. Store sanitized copies here before promoting this case to a golden dataset:

- `input/source_images/page_001_cover_table.png`
- `input/source_images/page_002_unit_summary.png`
- `input/source_images/page_003_cooling_dx.png`
- `output/source_images/direct_coil_dx_filled.png`

## Intended Mapping Lessons

- `CDXC-1` maps to Direct Coil DX layout.
- Cover page `RH` normalizes to Direct Coil `Right`.
- `Unit Details -> Altitude (ft)` maps to Direct Coil `Altitude(FT)`.
- `Cooling DX -> Entering` maps to Direct Coil air and refrigerant data.
- PDF `Tube Material: 0.016 Copper` does not directly equal Direct Coil option `Copper 0.014 Plain`; this row is marked review-required.
- PDF capacity values are present, but the provided Direct Coil screenshot shows `Total Capacity(MBH)(Per Coil) = 0`; this is marked review-required.

## Review Status

Draft from image transcription. John/engineering review required before using as a golden mapping rule.
