# Checklist Schema

## Status

Phase 1B draft for John and engineering review.

The checklist schema is the near-term user input layer for CoilForge. It should populate the Canonical Coil Model, but it is not the source of truth after values are normalized and reviewed.

Phase 1A dependency: no Phase 1A files were present when this draft was created. Drawing-related checklist fields are therefore review-required placeholders.

## Design Principles

- Checklist fields map to canonical model paths.
- Checklist values must be import/export-friendly JSON.
- Checklist values preserve source trace when populated from EZ Coil data, submittal PDFs, imported JSON, or John/engineering review.
- The checklist should not invent engineering values.
- Drawing dimensions can be captured or imported, but should remain `derived` or `engineering_review_required` until Phase 1A mapping is available.
- Generated drawings remain review aids, not released manufacturing drawings.

## Checklist Payload Shape

Future checklist payloads should follow this shape:

```json
{
  "checklist_version": "0.1.0-phase1b-draft",
  "checklist_id": "CF-CHECKLIST-0001",
  "workflow_stage": "draft",
  "source_documents": [],
  "field_values": [
    {
      "field_id": "fin_height",
      "canonical_path": "/physical_geometry/fin_height",
      "value": 12.0,
      "unit": "in",
      "field_role": "required",
      "review_status": "draft",
      "source_trace": []
    }
  ],
  "review_state": {
    "overall_status": "draft",
    "john_review_required": true,
    "engineering_review_required": true
  }
}
```

## Section Summary

### Case Identity

Required:

- `coilforge_case_id`
- `coil_name`
- `model_number`

Optional:

- `source_case_id`
- `item_number`

These fields populate `/case_identity/*`.

### Project Context

Optional/future fields:

- `project_name`
- `customer_name`
- `quote_or_job_number`
- `quantity`

These fields support future submittal extraction and export workflows. Current reference cases do not prove all of them.

### Coil Category

Required:

- `coil_category`
- `normalized_roadmap_bucket`

The checklist should allow the category to be selected or imported, but final classification status must remain traceable. Current locked values include DX, HGRH, CWC, and HWC.

Important Phase 0C rules:

- HGRH `header_type` and `feed_type` are separate.
- Single Feed is not Single Connection.
- EZC-0013 preserves source `ASC` and normalized `HGBP`.

### Product Family

Required:

- `source_product_code`

Optional:

- `normalized_family`

The checklist should preserve raw product naming such as `CDXC-1`, `RHHGRC-1`, `PHWC-1`, `CCWC-1`, or `HHWC-1`. Normalized family values need review before implementation.

### Airside Inputs

Required draft fields:

- `standard_cfm`
- `entering_air_dry_bulb`

Optional:

- `altitude`
- `entering_air_wet_bulb`
- `leaving_air_dry_bulb`
- `leaving_air_wet_bulb`

Source candidates include EZ Coil `Inputs.SCFM`, `Inputs.EnteringAirDryBulb`, `Inputs.EnteringAirWetBulb`, and CoilMaster-style `Airside.standardCFM`.

### Fluidside or Refrigerant Inputs

Required draft field:

- `fluid_type`

Optional:

- `refrigerant`
- `entering_fluid_temp`
- `leaving_fluid_temp`
- `glycol_mass_percent`
- `gpm`
- `condensing_temp`
- `superheat`
- `subcooling`

This section intentionally supports both water/glycol and refrigerant cases. It does not add selection calculation logic.

### Physical Geometry

Required draft fields:

- `rows`
- `fin_height`
- `fin_length`
- `fin_density_fpi`

Optional:

- `feeds`
- `circuits`

Source candidates include EZ Coil `Inputs.Nrows`, `Inputs.Fpi`, `Geometry.FH`, `Geometry.FL`, `Geometry.NumCircuits`, and CoilMaster-style `PhysicalData.rows`, `PhysicalData.finHeight`, `PhysicalData.finLength`, `PhysicalData.finDensity`.

### Casing and Options

Required draft fields:

- `casing_material`
- `casing_gauge`

Optional:

- `casing_type`

Additional construction options remain optional until a Direct Coil checklist template is confirmed.

### Headers, Connections, and Distributors

Required draft fields:

- `header_type`
- `feed_type`
- `supply_connection_size`
- `return_connection_size`

Optional:

- `distributor_model_number`
- `normalized_special_feature`
- `source_feature`

This section is the highest review-risk section because locked HGRH cases require John-confirmed classification where source JSON does not expose `Geometry.Headers`.

### Handing and Airflow

Required draft field:

- `coil_hand`

Optional:

- `opposite_end_connections`

`coil_hand` source mapping needs review because current source examples include numeric values, text values, and model suffixes.

### Drawing Dimensions

Derived/review-required draft fields:

- `drawing_FH`
- `drawing_FL`
- `drawing_CH`
- `drawing_CL`
- `drawing_CD`
- `drawing_HD`
- `drawing_SL`
- `drawing_connection_offsets`

These are included for drawing readiness, not for implementation. Phase 1A must confirm which drawing labels are direct source values, derived values, or unknown.

### Validation and Export

Required:

- `overall_status`

Future:

- `json_import_source`
- `json_export_profile`

The checklist draft reserves import/export fields so JSON compatibility remains a first-class requirement.

## Required vs Optional vs Derived vs Future

Required fields should be enough to create a reviewable canonical draft for Direct Coil workflows. Optional fields should be preserved when known. Derived fields must not be manually invented. Future fields reserve schema space without implying implementation approval.

## JSON Import/Export Readiness

The checklist draft supports JSON import/export by:

- using stable `field_id` values;
- mapping every checklist field to a canonical JSON Pointer path;
- requiring `field_role` and `review_status`;
- requiring `source_trace`, even when empty;
- separating raw source feature values from normalized values;
- avoiding implicit calculations in checklist payloads.

## Questions for John

1. Should Direct Coil users manually enter drawing dimensions, or should dimensions remain derived/imported only?
2. Which fields are truly required for the first checklist MVP: airside conditions, physical geometry, casing, headers/connections, or all of them?
3. Should raw EZ Coil numeric codes be shown in the checklist, hidden behind lookup labels, or preserved only in source trace?
4. Should `customer_name` and job metadata be included in Phase 1C, or reserved for the later submittal/import workflow?
