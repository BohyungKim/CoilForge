# Case 001 - DX + HGRH

Sanitized mock case for an Oxygen8-style submittal where the cover page contains one DX cooling coil and one hot gas reheat coil.

## Intended Mapping Lessons

- `CDXC-1` maps to Direct Coil DX layout.
- `RHHGRC-1` maps to Direct Coil condensing/HGRH-style layout.
- Cover page `LH` normalizes to Direct Coil `Left`.
- Cooling DX section values should not be reused for HGRH.

## Review Notes

- Tube material and casing defaults are engineer-entered mock values.
- Refrigerant values are mocked for rule-shape validation only.
