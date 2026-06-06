# Direct Coil Field Model

Status: Phase 2C Direct Coil field model baseline.

Created: 2026-06-05.

Scope: Direct Coil field registry and documentation only. This phase does not implement Direct Coil export, PDF export, parser work, supplier integration, UI redesign, or raw data changes.

## 1. Implementation Result

This phase adds a Direct Coil-specific field model that mirrors the Phase 2A web app input structure while keeping CoilForge's shared canonical-core rule intact.

Implemented artifacts:

- `src/coilforge/interfaces/direct_coil/fields.py`
- `tests/test_direct_coil_field_model.py`
- this documentation file

The registry defines field groups, field metadata, required fields, units, allowed values where known, source trace policy, manual override policy, header blocking behavior, and drawing parameter auto/manual policy.

## 2. Field Groups

The Direct Coil registry uses these groups:

1. Coil Geometry
2. Materials & Construction
3. Airside Conditions
4. Refrigerant Conditions
5. Manufacturing Options
6. Drawing Parameters

### Coil Geometry

- `tube_diameter_od`
- `tube_geometry`
- `rows_deep`
- `fins_per_inch`
- `tubes_high`
- `finned_height`
- `finned_length`
- `number_of_feeds`
- `airflow_direction`
- `header_type`

### Materials & Construction

- `tube_material`
- `fin_material`
- `fin_surface`
- `header_material`
- `connection_material`
- `connection_type`
- `supply_connection_size`
- `return_connection_size`
- `casing_material`
- `casing_style`
- `connection_ends`
- `coil_hand`

### Airside Conditions

- `total_air_flow_cfm`
- `face_velocity_fpm`
- `altitude_ft`
- `entering_dry_bulb_f`
- `entering_wet_bulb_f`
- `leaving_dry_bulb_f`
- `relative_humidity_pct`
- `total_capacity_mbh`

### Refrigerant Conditions

- `refrigerant`
- `evaporating_temp_f`
- `liquid_temp_f`
- `superheat_f`
- `dx_dist_capillary_size`

### Manufacturing Options

- `drain_pan_type`
- `coil_coating`
- `system_type`
- `distributor_notes`

### Drawing Parameters

- `CD`
- `I`
- `S`
- `O`
- `R`
- `BF`
- `HD`
- `HF`
- `TF`
- `RF`
- `CH`
- `SL`
- `ZD`

## 3. Field Metadata Model

Each field definition includes:

| Property | Purpose |
| --- | --- |
| `field_key` | Stable Direct Coil field key used by the registry. |
| `label` | Human-readable Direct Coil-facing label. |
| `group` | One of the six Direct Coil field groups. |
| `data_type` | Expected value type, such as `string`, `number`, or `integer`. |
| `unit` | Unit for dimensional or performance values. Blank when not applicable. |
| `required` | Whether the field is required for the current Direct Coil draft baseline. |
| `allowed_values` | Known allowed values or mode values. Empty when unknown or open-ended. |
| `source_required` | Whether imported/prepopulated values must carry source trace. |
| `review_policy` | Review behavior for the field. |
| `blocked_conditions` | Conditions that should block use of the field or workflow step. |
| `notes` | Implementation and review notes. |

The registry is intentionally a contract layer. It does not export to Direct Coil.

## 4. Required Fields

Current required fields are aligned with the Phase 2A DX/Header 1 web MVP and drawing-review needs:

- `rows_deep`
- `fins_per_inch`
- `finned_height`
- `finned_length`
- `airflow_direction`
- `header_type`
- `return_connection_size`
- `coil_hand`
- `CD`
- `BF`
- `TF`
- `CH`

The drawing parameters listed as required are required for the current drawing review baseline, not proof that all values are approved for manufacturing use.

## 5. Units

Dimensional and performance units are defined in the registry:

| Unit | Fields |
| --- | --- |
| `in` | `tube_diameter_od`, `finned_height`, `finned_length`, connection sizes, and drawing parameters. |
| `rows` | `rows_deep`. |
| `fpi` | `fins_per_inch`. |
| `tubes` | `tubes_high`. |
| `feeds` | `number_of_feeds`. |
| `cfm` | `total_air_flow_cfm`. |
| `fpm` | `face_velocity_fpm`. |
| `ft` | `altitude_ft`. |
| `degF` | dry bulb, wet bulb, evaporating, liquid, and superheat temperatures. |
| `pct` | `relative_humidity_pct`. |
| `MBH` | `total_capacity_mbh`. |

## 6. Allowed Values

Known allowed values are intentionally narrow:

| Field | Allowed values |
| --- | --- |
| `header_type` | `Header 1` |
| `airflow_direction` | `left_to_right`, `right_to_left` |
| `coil_hand` | `Left`, `Right` |
| Drawing parameter mode | `auto`, `manual`, `review_required`, `blocked` |

`Header 2`, `Header 3`, and `Header 4` remain future review items and are blockable in the current registry.

## 7. Source Trace Policy

Imported and prepopulated values require source trace.

Required trace fields:

- `source_type`
- `source_id`
- `source_location`
- `source_value`
- `normalized_value`
- `review_status`

Allowed source types for the current contract:

- `manual_entry`
- `sanitized_ez_reference`
- `coilforge_json_import`
- `submittal_pdf_candidate`

Manual values must be distinguishable from imported values by using `source_type = manual_entry` or equivalent entry metadata. Manual entry does not need a raw source document, but it still needs entry metadata and review status.

## 8. Review / Blocked Policy

Direct Coil field values are draft inputs until reviewed.

Review policies:

- `review_required`: default policy for input fields.
- `review_note_only`: notes are preserved for review but do not drive generated values.
- `auto_or_manual_review_required`: drawing parameter policy.

Blocked conditions:

- Unsupported `header_type` is blocked.
- Missing `airflow_direction` is blocked because airflow must not be inferred silently.
- Drawing auto mode is blocked when no approved canonical source or derived rule exists.
- Drawing manual mode requires explicit review metadata.

Manual override policy:

- Use status `manual_override`.
- Preserve previous value and override value.
- Require override reason.
- Require reviewer and review status.
- Do not erase imported source evidence.

## 9. Drawing Parameter Policy

Drawing parameters support Auto/manual mode as metadata.

Allowed modes:

- `auto`: value is populated from a reviewed canonical source or approved derived rule.
- `manual`: value is entered or adjusted by a reviewer and must carry manual override metadata.
- `review_required`: value is present or expected but not approved for automatic use.
- `blocked`: value cannot be used for drawing population.

This phase does not implement drawing export, PDF export, CAD output, or Direct Coil export. The policy only defines the metadata needed for future drawing intent and review packets.

## 10. Known Placeholders

- The registry does not yet map every Direct Coil field to a final canonical path.
- `header_type` supports only `Header 1` for the current baseline.
- Many material, casing, refrigerant, and manufacturing option values are open-ended until John or engineering confirms allowed values.
- Drawing parameter label semantics still need engineering review before production-like use.
- OAL remains outside this field set and must stay review-required or blocked until John approves a rule.
- The registry does not calculate face velocity, capacity, or drawing dimensions.
- The registry does not import raw EZ JSON or parse submittal PDFs.

## 11. Next Phase

Recommended next phase: Direct Coil field-to-canonical mapping.

Scope:

- Map each Direct Coil field key to a proposed `CanonicalCoilRecord` path.
- Identify source evidence expectations for each mapped field.
- Mark fields as source-observed, manual-entry, derived, review-required, blocked, or future.
- Keep Direct Coil export out of scope.
- Keep raw customer and project data out of scope.

Acceptance criteria:

- Mapping document exists.
- No raw data is modified.
- No export implementation is added.
- Unsupported headers remain blockable.
- Source trace and manual override policies remain explicit.
