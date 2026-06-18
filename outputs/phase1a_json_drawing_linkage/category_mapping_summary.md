# Phase 1A JSON-to-Drawing Dimension Linkage Summary

Run timestamp: 2026-06-05T14:49:11

## Scope

- Inputs used: `Case/EZC-0001` through `Case/EZC-0015`, `outputs/phase0_category_assessment`, `outputs/phase0_reference_lock`, and `docs/REFERENCE_CASE_SET.md`.
- Analysis only: no raw JSON, raw PDF, or drawing-populator code was modified or created.
- Direct matching tolerance: 0.01 inch.
- PDF evidence came from page-2 dimension callouts, the page-2 dimension table, and explicit note tokens such as `I1=2` when present.

## Case Coverage

| Category | Locked cases | Notes |
| --- | ---: | --- |
| DX | 6 | Includes EZC-0013, where source ASC is normalized to HGBP by John decision. |
| HGRH | 5 | All HGRH JSON files lack `Geometry.Headers`; only some expose dimension tokens in `Construction.notes`. |
| CWC | 1 | One locked Header 1 case. |
| HWC | 3 | PHWC exposes populated Headers; HHWC cases do not expose populated Headers. |

## Mapping Status Counts

| Status | Rows |
| --- | ---: |
| EXACT_MATCH | 218 |
| TOLERANCE_MATCH | 54 |
| DERIVED_CANDIDATE | 24 |
| PDF_ONLY | 87 |
| JSON_ONLY | 18 |
| MISMATCH | 158 |
| UNCERTAIN | 16 |

## Category Findings

### DX

- Strong direct mappings: `FH`, `FL`, `CH`, `CL`, `CD`, `TF`, `BF`, `RB` map from `Geometry.*` fields within 0.01 inch.
- Header connection labels map through `Geometry.Headers[]`, not through the same-name top-level `Geometry.I/S/O/R` fields. Examples: `I1/S1` map to supply/distributor `IO[0]/SR`, and `O2/R2` map to return header `IO[0]/SR`. Header 2/3 drawings also expose additional observed labels such as `I3`, `S3`, `O4`, `R4`, `O6`, and `R6`.
- `HDx1` maps to distributor header `Geometry.Headers[0].HD = 4.5`; `HD2` maps to return-header `HD = 3.5`, not `Geometry.HD2 = 5.0`.
- `OAL` is not populated by `Geometry.OAL` because the JSON value is `0`; in DX cases it is an observed derived candidate: `Geometry.CL + Geometry.RB2`.

### HGRH

- Strong direct mappings are limited to `FH -> PhysicalData.finHeight` and `FL -> PhysicalData.finLength`.
- `Construction.notes` provides direct label tokens only in EZC-0002 and EZC-0010 (`I1`, `S1`, `SL1`, `O2`, `R2`, `HD2`, `SL2`). EZC-0004, EZC-0008, and EZC-0012 do not expose equivalent JSON dimension tokens.
- `CH`, `CL`, and `OAL` are derived candidates in HGRH because the new schema has no explicit casing/header geometry fields. `CL = PhysicalData.finLength + 3.0` is consistent; `CH` uses an observed height offset; `OAL` varies by feed/header pattern and should be reviewed.
- `PhysicalData.connectionSize` sometimes numerically equals `R2`, `TF`, or `BF`, but it is marked `UNCERTAIN` where no explicit drawing-location field exists.

### CWC

- The locked CWC case follows the water-coil old-schema pattern: `FH`, `FL`, `CH`, `CL`, `CD`, `TF`, `BF`, and `RB` map from `Geometry.*`.
- `HD1`, `SL1`, `I`, `S`, `O`, and `R` map to `Geometry.Headers[]` values.
- `OAL` is an observed derived candidate: `Geometry.CL + Geometry.RB`.

### HWC

- PHWC (`EZC-0005`) follows the populated `Geometry.Headers[]` water-coil pattern for `HD1`, `SL1`, `I`, `S`, `O`, and `R`.
- HHWC (`EZC-0006`, `EZC-0015`) exposes no populated `Geometry.Headers[]`; `HD` matches `Geometry.HD` / `Geometry.SingleFeedExtensionHD`, but `SL`, `I`, `S`, `O`, and `R` remain PDF-only or uncertain.
- `OAL` differs by HWC subtype: PHWC matches `Geometry.CL + Geometry.RB`; HHWC matches `Geometry.FL + Geometry.RB`.

## Additional Observed Labels

- Additional labels observed beyond the prompt list: I3, I5, O4, O6, R4, R6, S3, S5, SL3.

## Output Files

- `json_to_drawing_mapping_candidates.csv`: all candidate, derived, PDF-only, JSON-only, mismatch, and uncertain rows.
- `direct_matches.csv`: `EXACT_MATCH` and `TOLERANCE_MATCH` rows only.
- `derived_or_uncertain_mappings.csv`: `DERIVED_CANDIDATE`, `PDF_ONLY`, `JSON_ONLY`, `MISMATCH`, and `UNCERTAIN` rows.

## Review Risk

- These are mapping candidates, not approved drawing-population rules.
- Labels with matching numeric values but no semantic JSON field, especially HGRH `connectionSize` overlaps, must not be promoted without John or engineering review.
- OAL formulas are observed candidates and need engineering confirmation before Phase 1B canonical schema lock.
