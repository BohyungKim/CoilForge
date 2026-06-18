# Phase 1A ChatGPT Review Packet

Run timestamp: 2026-06-05T14:49:11

## 1. Strong Direct Mappings

- `FH` and `FL` are strong direct mappings in every category: old-schema cases use `Geometry.FH/FL`; HGRH uses `PhysicalData.finHeight/finLength`.
- Old-schema DX/CWC/HWC cases strongly map `CH`, `CL`, `CD`, `TF`, `BF`, and `RB` from `Geometry.CH`, `Geometry.CL`, `Geometry.CD`, `Geometry.TSP`, `Geometry.BSP`, and `Geometry.RB` within 0.01 inch.
- Header/location labels are strongest when mapped to `Geometry.Headers[]`: `HD1/HD2/HDx1`, `SL1/SL2`, and `I/S/O/R` families map to header `HD`, `SL[0]`, `IO[0]`, and `SR`, not to top-level same-name geometry fields.
- HGRH note-token direct mappings exist only where `Construction.notes` explicitly contains labels, currently EZC-0002 and EZC-0010.

## 2. Derived Mapping Candidates

- `OAL` is derived, not direct. `Geometry.OAL` is `0` in old-schema cases and should not be used as the drawing label source.
- DX observed formula: `OAL = Geometry.CL + Geometry.RB2`.
- CWC and PHWC observed formula: `OAL = Geometry.CL + Geometry.RB`.
- HHWC observed formula: `OAL = Geometry.FL + Geometry.RB`.
- HGRH observed formulas are schema-limited: `CL = PhysicalData.finLength + 3.0`; `CH` uses an observed height offset; `OAL` varies by HGRH subtype/feed pattern and should stay `DERIVED_CANDIDATE` pending review.
- PDF values rounded to two decimals produce legitimate `TOLERANCE_MATCH` rows, such as `6.38` vs `6.375` and `0.63` vs `0.625`.

## 3. Category-Specific Mapping Differences

- DX: direct geometry plus header-array mapping is strong; multi-header DX drawings expose additional header-specific labels beyond the prompt list.
- HGRH: direct mapping is sparse because the JSON schema is different; many header/stubout values are PDF-only unless embedded in `Construction.notes`.
- CWC: one case, but it follows the populated water-coil `Geometry.Headers[]` pattern.
- HWC: PHWC behaves like CWC with populated headers; HHWC lacks populated `Headers`, so several visible labels remain uncertain.

## 4. HGRH Schema Limitations

- HGRH cases without `Geometry.Headers`: EZC-0002, EZC-0004, EZC-0008, EZC-0010, EZC-0012.
- HGRH cases with explicit dimension tokens in `Construction.notes`: EZC-0002, EZC-0010.
- HGRH `PhysicalData.connectionSize` is a connection-size value, not confirmed as a drawing-location dimension. Numeric overlaps are marked `UNCERTAIN`, not direct mappings, unless an explicit note token exists.
- HGRH header type and feed type remain classification metadata from John review, not inferred from `Geometry.Headers`.

## 5. DX HGBP/ASC Handling

- EZC-0013 is normalized as DX / HGBP by John decision while preserving ASC as source evidence.
- Its dimensions follow the DX Header 1 mapping pattern: `Geometry.Headers[0].IsASC = true` and `Geometry.isASC = true` should be preserved as source flags, not collapsed into generic DX without provenance.
- Recommended canonical handling: keep both `special_feature = HGBP` and `source_feature = ASC`, with source paths retained.

## 6. Recommended Fields for Canonical Model

- `source_schema_type`: old_geometry_json, hgrh_physicaldata_json, or unknown.
- `source_dimensions`: `fin_height`, `fin_length`, `casing_height`, `casing_length`, `casing_depth`, `top_flange`, `bottom_flange`, `left/right/end flange`, `return_bend_allowance`.
- `headers[]`: `header_id`, `role` (`supply`, `return`, `distributor`), `diameter`, `hd`, `sl`, `io`, `sr`, `connection_size`, `is_asc`, `source_paths`, and `pdf_label_aliases`.
- `derived_dimensions[]`: label, formula, inputs, observed_value, review_status, and category/subtype applicability.
- `drawing_label_values[]`: label, value, source (`direct_json`, `derived`, `pdf_only`, `note_token`), tolerance_status, and evidence case IDs.
- `classification`: `coil_category`, `header_type`, `feed_type`, `special_feature`, `source_feature`, and John review status.

## 7. Questions for John

- Confirm whether `HDx1` should be canonicalized as `header[1].hd` / distributor HD or preserved as a separate PDF-label alias.
- Confirm the `OAL` formulas by category/subtype before Phase 1B schema lock, especially HGRH and HHWC.
- For HHWC cases with no populated `Geometry.Headers[]`, identify whether `I/S/O/R/SL` should come from hidden/default EZ Coil rules, a missing export field, or checklist input.
- For HGRH cases without note tokens, identify the approved source of header/stubout dimensions (`I1`, `S1`, `O2`, `R2`, `SL1`, `SL2`, `HD2`).
- Decide whether `PhysicalData.connectionSize` may ever populate `R/R2`-style labels, or whether it must remain separate connection metadata.
- Confirm that CoilForge should retain both `source_feature = ASC` and normalized `special_feature = HGBP` for EZC-0013 and future ASC/HGBP cases.
