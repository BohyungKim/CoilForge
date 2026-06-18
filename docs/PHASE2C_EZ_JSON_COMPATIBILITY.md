# Phase 2C.1 EZ JSON Compatibility Path

## One-line implementation result

Phase 2C.1 adds a sanitized EZ JSON compatibility adapter that maps EZ reference fields into `CanonicalCoilRecord`, then reuses the existing Direct Coil draft mapper and DrawingIntent bridge.

## Files changed

- `src/coilforge/adapters/__init__.py`
- `src/coilforge/adapters/ez_json.py`
- `src/coilforge/adapters/ez_to_canonical.py`
- `tests/test_phase2c_ez_json_compatibility.py`
- `docs/PHASE2C_EZ_JSON_COMPATIBILITY.md`

## EZ adapter flow

```text
sanitized EZ JSON fixture
-> load_sanitized_ez_json()
-> map_ez_json_to_canonical_result()
-> CanonicalCoilRecord
-> map_canonical_to_direct_coil_draft()
-> resolve_drawing_parameters()
-> create_drawing_intent_from_direct_coil()
```

EZ JSON is a compatibility/reference input only. It does not bypass canonical and does not create a final Direct Coil export.

## Field mapping summary

The current sanitized fixture maps these EZ keys:

- `source_case_id` -> `project.source_case_id`
- `coil_name` -> `coil_identity.coil_name`
- `model_number` -> `coil_identity.model_number`
- `coil_category` -> `product_type`
- `header_type` -> `header_type`
- `rows` -> `geometry.rows_deep`
- `fin_height` -> `geometry.finned_height`
- `fin_length` -> `geometry.finned_length`
- `fin_density_fpi` -> `geometry.fins_per_inch`
- `airflow_direction` -> `geometry.airflow_direction`
- `coil_hand` -> `connections.coil_hand`
- `return_connection_size` -> `connections.return_connection_size`
- `casing_depth` -> `drawing_parameters.CD`
- `top_flange` -> `drawing_parameters.TF`
- `bottom_flange` -> `drawing_parameters.BF`
- `casing_height` -> `drawing_parameters.CH`
- `casing_length` -> `drawing_parameters.SL`
- `return_bend_allowance` -> `drawing_parameters.R`

Current sanitized fixture summary:

- Mapped EZ keys: `18`
- Unmapped EZ keys: `6`
- Direct Coil draft fields: `52`
- Direct Coil draft ready: `0`
- Direct Coil draft review-required: `14`
- Direct Coil draft blocked: `0`
- Direct Coil draft unmapped: `38`

## SourceEvidence behavior

Every mapped imported value receives `SourceEvidence` with:

- `source_type = sanitized_ez_reference`
- `source_id` from `source_case_id`
- `source_location = sanitized-ez-json:<source_key>`
- original sanitized source key/value
- normalized value
- unit where known
- `review_status = unreviewed`

Unmapped EZ fields also preserve SourceEvidence. The adapter does not store raw EZ exports or private source documents.

## Unmapped policy

Unknown or unsupported EZ fields are not discarded. They are preserved as canonical `unmapped_fields` with their source evidence and a reason:

```text
No approved Phase 2C EZ JSON compatibility mapping rule.
```

Current fixture unmapped keys:

- `fixture_name`
- `fixture_status`
- `circuiting_display`
- `notes`
- `release_status`
- `drawing_status`

## Review-required policy

Imported EZ values remain review-required because this path is compatibility/reference input, not an approved engineering import.

Classification-like values such as `coil_category` and `header_type` are review-required. The adapter does not silently infer missing `coil_type`.

## Blocked policy

Unsupported `header_type` is blocked. Missing required Direct Coil values are handled by the existing canonical validation and Direct Coil draft mapper.

For the current sanitized fixture, all required Direct Coil drawing baseline fields used by the preview resolver are present through explicit EZ mappings (`CD`, `BF`, `TF`, `CH`), so the Direct Coil draft has no blocked fields.

## Direct Coil draft reuse

The adapter returns a `CanonicalCoilRecord`. Direct Coil draft generation uses the existing `map_canonical_to_direct_coil_draft()` function. No separate EZ-to-Direct-Coil shortcut is implemented.

## DrawingIntent reuse

Drawing preview uses the existing resolver and bridge:

- `resolve_drawing_parameters()`
- `create_drawing_intent_from_direct_coil()`

When the sanitized EZ fixture has supported Header 1 values, a DrawingIntent can be created with preview allowed and export disabled. Unsupported header types remain blocked.

## Known limitations

- Sanitized DX Header 1 fixture only.
- No raw EZ exports.
- No Direct Coil final export.
- No PDF export.
- No supplier integration.
- No broad UI expansion.
- No production drawing approval claim.
- `circuiting_display` is preserved as unmapped until an approved parsing/mapping rule exists.

## Next recommended phase

Phase 2C.2 should add a combined compatibility regression fixture that compares submittal-derived and EZ-derived canonical/draft summaries for the same sanitized case while keeping both paths review-required and export-disabled.
