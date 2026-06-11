# Iteration 001 - EZC-0001 DX Header 1 Rule Observation

## One-Line Result
Created the first local evidence-backed drawing rule observation for `EZC-0001 / DX / Header 1` from paired source submittal PDF, EZ drawing PDF, and EZ JSON export.

## Source Files

| Role | Local file | Pages/notes |
| --- | --- | --- |
| Source submittal PDF | `Oxygen8 Submittal - Hoffman Hoffman - 2862 - Avon Operations Center - Rev3_AsBuilt.pdf` | 94 pages; page 1 cover and page 6 Cooling DX block used. |
| EZ drawing PDF | `CDXC-1.pdf` | 1 page; text labels extract cleanly. |
| EZ JSON export | `CDXC-1.txt` | Parsed JSON from `.txt`. |
| Existing assessment | `ai_category_assessment.txt` | Confirms DX / Header 1 reference candidate. |

Raw files were not copied into this output folder. Raw PDF text was not stored.

## Confirmed In This Pair

- `Fin Height 12` and `Fin Length 15` from submittal/EZ JSON appear as `12 FH` and `15 FL` in the EZ drawing.
- `Rows 4`, `FPI 13`, and `Total Feeds 2` align across source PDF, EZ JSON, and drawing/right-panel text.
- `Geometry.Headers` count is `2`, matching one DX distributor/supply header and one return header pair.
- Header 1 suffix values align for this case: `HDx1=4.50`, `I1=3.00`, `S1=2.75`, `HD2=3.50`, `SL2=8.00`, `O2=2.00`, `R2=0.63`.

## Candidate Rules Added

- `core_geometry_copy`: submittal/EZ geometry values can populate `FH`, `FL`, `ROWS`, and right-panel FPI/circuiting candidates.
- `ez_json_to_drawing_dimensions`: EZ geometry fields `CH`, `CL`, `CD`, `TSP`, `BSP`, `LEP`, `REP`, `RB` map to drawing labels `CH`, `CL`, `CD`, `TF`, `BF`, `HF`, `RF`, `RB` in this pair.
- `header_array_to_suffix_labels`: odd distributor/supply header ID maps to `HDx/I/S` suffix; even return header ID maps to `HD/SL/O/R` suffix for Header 1.
- `derived_dimension_candidate`: drawing `OAL=20.25` matches `Geometry.CL + Geometry.RB2`, but `Geometry.OAL=0.0`, so this remains unapproved.

## John Review Required

- Resolve hand/orientation conflict: cover page shows `CDXC-1` as `LH`, EZ drawing title ends `-L`, but the source PDF Cooling DX model text appears to end `R`.
- Confirm whether OAL may remain visible as observed candidate while formula approval stays blocked.
- Confirm whether Header 1 suffix interpretation can be tested next against DX Header 2/3 cases.

## Next Recommended Iteration

Use `Case/#2/EZC-0011` or `Case/#2/EZC-0007 - DX_3` next to validate whether Header 2/3 continues the suffix rule as `I1/S1/O2/R2`, `I3/S3/O4/R4`, `I5/S5/O6/R6`.

## Artifacts

- `rule_observation.json`
- `rule_observation_links.csv`
