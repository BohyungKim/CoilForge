# Case 003 - Multi PHWC + HHWC

Sanitized mock case for a sequence-sensitive PDF where the cover page contains two preheat hot water coils and two heating hot water coils.

## Intended Mapping Lessons

- `PHWC-1` maps to the first `Preheat HWC` section.
- `HHWC-1` maps to the first `Heating HWC` section.
- `PHWC-2` maps to the next `Preheat HWC` section, not the prior `PHWC-1` section.
- `HHWC-2` maps to the next `Heating HWC` section, not the prior `HHWC-1` section.
- Cover page quantity can be `2`, but sequence still needs separate coil instances.

## Review Notes

- This case is designed to catch accidental section reuse.
