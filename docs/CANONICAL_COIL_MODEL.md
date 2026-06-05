# Canonical Coil Model

## Status

Phase 1B draft for John and engineering review.

This document defines the proposed internal source-of-truth shape for CoilForge. It is schema/design only. It does not implement the drawing populator, does not approve generated drawings, and does not add selection calculation logic.

Phase 1A dependency: `outputs/phase1a_json_drawing_linkage` exists but had no files when this draft was created. Drawing-dimension mappings are therefore placeholders that must be reviewed after Phase 1A produces label-to-field evidence.

## Evidence Base

This draft is based on:

- `docs/REFERENCE_CASE_SET.md`
- `outputs/phase0_reference_lock/locked_reference_case_set.csv`
- `outputs/phase0_reference_lock/john_review_decisions.md`
- `outputs/phase0_reference_lock/phase0c_chatgpt_review_packet.md`
- `outputs/phase0_category_assessment/*`
- Representative read-only source inspection from `Case/EZC-0001`, `Case/EZC-0002`, `Case/EZC-0005`, and `Case/EZC-0014`

Confirmed Phase 0C constraints:

- `coil_category` identifies DX, HGRH, CWC, or HWC.
- HGRH `header_type` and `feed_type` are separate fields.
- Single Feed is not Single Connection.
- EZC-0013 source evidence is ASC, while the normalized internal special feature is HGBP by John-confirmed company standard.
- Missing buckets must not be invented: DX Header 4, HGRH Single Connection, HGRH Header 3, and HGRH Header 4.

## Core Design Choice

Each engineering value should be stored as a traceable field object:

```json
{
  "value": 12.0,
  "unit": "in",
  "field_role": "required",
  "review_status": "source_observed",
  "source_trace": [
    {
      "source_type": "ez_coil_json",
      "source_path": "Case/EZC-0001/CDXC-1.txt",
      "source_field": "Geometry.FH",
      "source_value": 12.0,
      "evidence_status": "observed",
      "notes": null
    }
  ],
  "notes": null
}
```

This is heavier than a flat payload, but it supports the project rules: explainable values, JSON import/export, future PDF extraction, checklist review, validation reports, and review-only drawing generation.

## Field Roles

- `required`: Needed for minimum canonical identity or Direct Coil review workflow.
- `optional`: Useful when available but not required for the first draft.
- `derived`: Must come from an explicit reviewed mapping, rule, or trusted imported source. Do not invent these values.
- `future`: Reserved for later extraction, import/export, validation, or selection workflow work.

## Review Status Values

- `source_observed`: Directly present in a source file or report.
- `ai_inferred`: Inferred from source evidence and not individually confirmed.
- `john_confirmed`: Confirmed by John review.
- `engineering_review_required`: Must be reviewed before implementation or drawing use.
- `validated`: Checked by a future validator.
- `not_applicable`: Field does not apply to this coil category.
- `missing`: Required or expected field is absent.
- `future`: Placeholder for a later phase.

## Proposed Model Sections

### case_identity

Purpose: identify the CoilForge case and reference/source identity.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `coilforge_case_id` | required | Internal stable id for future import/export. |
| `source_case_id` | optional | Example: `EZC-0001`; optional for new checklist-created cases. |
| `coil_name` | required | Source examples include `CDXC-1`, `RHHGRC-1`, `PHWC-1`, `CCWC-1`, `HHWC-1`. |
| `model_number` | required | Source examples include model strings in Phase 0C locked CSV. |
| `item_number` | optional | Present in some CoilMaster-style JSON. |
| `reference_status` | optional | Example: `LOCKED_REFERENCE`. |

### project_context

Purpose: capture project and workflow context without binding to any external system.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `project_name` | optional | Future submittal/checklist field. |
| `customer_name` | future | Should not be backfilled from current reference cases. |
| `quote_or_job_number` | optional | Future workflow/import field. |
| `quantity` | optional | Present in CoilMaster-style construction data. |
| `coils_per_bank` | optional | Present in some physical data. |
| `total_coils` | optional | Present in some construction data. |
| `workflow_stage` | required | Draft/review/validated state for workflow routing. |

### coil_category

Purpose: hold normalized category and classification evidence.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `category` | required | DX, HGRH, CWC, HWC, or UNKNOWN. |
| `normalized_roadmap_bucket` | derived | Example: `DX / Header 1`; review required when source is inferred. |
| `classification_basis` | required | Phase 0 report, John review, source evidence, or future engineering review. |
| `classification_confidence` | optional | Example: HIGH or HIGH_AFTER_JOHN_REVIEW from Phase 0C outputs. |

### product_family

Purpose: keep source product naming separate from normalized interpretation.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `source_product_code` | required | Raw source product/family code. |
| `normalized_family` | optional | Reviewable interpretation, not a calculation result. |
| `application_mode` | optional | Heating, cooling, reheat, heat reclaim, or future approved value. |
| `coil_style` | optional | Source examples include `standard`. |

### performance_inputs

Purpose: preserve performance-related inputs for future validation/import/export without implementing selection calculations.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `desired_capacity` | optional | Present in EZ Coil `Inputs`; often zero in reference data. |
| `system_capacity` | future | Reserved; do not calculate in Phase 1B. |
| `maximum_airside_pressure_drop` | optional | Source input where available. |
| `maximum_fluid_pressure_drop` | optional | Source input where available. |
| `capacity_ratio` | optional | Present in CoilMaster-style JSON. |
| `fan_rpm` | future | Present as source field but not used yet. |

### airside_inputs

Purpose: capture airside conditions from checklist, EZ Coil source, or future PDF extraction.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `standard_cfm` | required | Maps to `Inputs.SCFM` or `Airside.standardCFM`. |
| `actual_cfm` | optional | Maps to `Inputs.ACFM` when available. |
| `altitude` | optional | Source input where available. |
| `entering_air_dry_bulb` | required | Maps to source entering air dry bulb fields. |
| `entering_air_wet_bulb` | optional | Needed for some cooling workflows. |
| `leaving_air_dry_bulb` | optional | Source may call this desired or leaving value. |
| `leaving_air_wet_bulb` | optional | Source may call this desired or leaving value. |

### fluidside_or_refrigerant_inputs

Purpose: support water/glycol coils and DX/HGRH refrigerant cases in the same canonical section.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `fluid_type` | required | Numeric or named source values must be normalized only with review. |
| `refrigerant` | optional | Example: `R32` in CoilMaster-style HGRH data. |
| `entering_fluid_temp` | optional | Water/glycol cases. |
| `leaving_fluid_temp` | optional | Water/glycol cases. |
| `glycol_mass_percent` | optional | Water/glycol cases. |
| `gpm` | optional | Source `GPM`. |
| `sgpm` | optional | Source `SGPM`. |
| `evaporating_temp` | optional | DX-style source field. |
| `condensing_temp` | optional | DX/HGRH-style source field. |
| `entering_superheat` | optional | Refrigerant cases. |
| `leaving_superheat` | optional | Refrigerant cases. |
| `leaving_subcooling` | optional | Refrigerant cases. |
| `leaving_quality` | optional | Refrigerant cases. |
| `refrigerant_liquid_temp` | optional | Refrigerant cases. |
| `fluidside_fouling_factor` | optional | Future validation/import field. |

### physical_geometry

Purpose: capture dimensional and construction geometry that can feed drawings and JSON import/export.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `rows` | required | Source examples: `Inputs.Nrows`, `Geometry.Nrows`, `PhysicalData.rows`. |
| `fin_height` | required | Source examples: `Geometry.FH`, `PhysicalData.finHeight`. |
| `fin_length` | required | Source examples: `Geometry.FL`, `PhysicalData.finLength`. |
| `fin_density_fpi` | required | Source examples: `Inputs.Fpi`, `Geometry.fpi`, `PhysicalData.finDensity`. |
| `fin_id` | optional | Source field. |
| `fin_material` | optional | Source field. |
| `fin_thickness` | optional | Source field. |
| `tube_geometry` | optional | Present in CoilMaster-style JSON. |
| `tube_type` | optional | EZ Coil numeric code; meaning needs mapping before UI exposure. |
| `tube_material` | optional | Source field/code. |
| `tube_wall_thickness` | optional | Source field. |
| `circuits` | optional | Source examples: `Geometry.NumCircuits`, `PhysicalData.circuiting`. |
| `feeds` | optional | Source examples: `Inputs.Nfeeds`, `Geometry.Nfeeds`. |
| `slabs` | optional | Source field. |
| `multi_circuit_feeds` | optional | Source array where available. |
| `multi_circuit_passes` | optional | Source array where available. |
| `coil_weight` | optional | Source-derived reference value; not a Phase 1B calculation. |
| `internal_volume` | optional | Source-derived reference value; not a Phase 1B calculation. |

### casing

Purpose: capture casing material, casing type, and construction options.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `material` | required | Source examples: `Geometry.CasingMaterial`, `Construction.casingMaterial`. |
| `gauge` | required | Source examples: `Geometry.CasingGauge`, `Construction.casingGauge`. |
| `thickness` | optional | Source field where available. |
| `type` | optional | Source examples: `Geometry.CasingType1`, `Construction.casingType`. |
| `coating` | optional | Source examples: `Construction.coilCoating`. |
| `stacking_flanges` | optional | Special option. |
| `collared_holes` | optional | Special option. |
| `mounting_holes` | optional | Special option. |
| `fasteners` | optional | Special option. |
| `recessed_vent_drain` | optional | Source field. |
| `notes` | optional | Preserve source notes, do not parse into engineering rules without review. |

### headers

Purpose: model header pattern while preserving the Phase 0C HGRH correction.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `header_type` | required | Header 1, Header 2, Header 3, Header 4, UNKNOWN, or NOT_APPLICABLE. |
| `feed_type` | required | Single Feed, Non-Single Feed, UNKNOWN, or NOT_APPLICABLE. |
| `header_count` | optional | Derived from `Geometry.Headers` where available; John-reviewed for HGRH cases lacking exposed headers. |
| `items[]` | optional | Per-header traceable items. |

Header item fields should include `header_id`, `role`, `diameter`, `material`, `number_of_connections`, `connection_type`, `connection_size`, `is_distributor`, `is_asc`, `header_dimension_hd`, `header_dimension_sl`, `vent_drain_location`, `rotation`, and `location`.

### connections

Purpose: represent supply/return/refrigerant connection details without assuming all categories use the same connection pattern.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `connection_summary` | required | Human-reviewable summary. |
| `items[]` | required | Connection objects with role, size, type, material, quantity, rotation, and location. |

### distributors

Purpose: support DX/HGRH distributor and ASC/HGBP evidence.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `applies` | required | True for distributor-based cases; false or not applicable for water coils. |
| `distributor_count` | optional | Source count where available. |
| `items[]` | optional | Distributor model, nozzle family, ASC flag, orientation, extension, feed tubes, and target header. |

### hgbp_or_special_features

Purpose: preserve normalized and source special-feature facts separately.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `normalized_special_feature` | optional | Example: HGBP for EZC-0013 after John review. |
| `source_feature` | optional | Example: ASC source evidence for EZC-0013. |
| `hgbp_required` | optional | Review-required normalized flag. |
| `asc_present` | optional | Source evidence flag. |
| `special_options` | optional | Construction options or source flags. |
| `engineering_review_notes` | optional | Review comments and unresolved decisions. |

### handing_and_airflow

Purpose: capture hand and airflow/connection orientation before drawing generation.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `coil_hand` | required | Source examples include numeric `Geometry.CoilHand`, text `Construction.coilHand`, and model suffixes. Mapping must be reviewed. |
| `airflow_direction` | future | Needed for drawing workflow but not confirmed from Phase 0C. |
| `connection_end` | optional | Inferred only with review. |
| `opposite_end_connections` | optional | Source examples: `Geometry.OppositeEndConnections`, `SpecialOptions.oppositeEnd`. |
| `coil_orientation` | future | Reserve for template/drawing use. |
| `heat_pump_heating_mode` | optional | Source field where available. |

### drawing_dimensions

Purpose: hold drawing-facing dimensions and labels without implementing population rules.

Initial fields:

| Field | Role | Notes |
| --- | --- | --- |
| `FH` | derived | Source candidate: `Geometry.FH`; Phase 1A required for drawing label confirmation. |
| `FL` | derived | Source candidate: `Geometry.FL`; Phase 1A required. |
| `CH` | derived | Source candidate: `Geometry.CH`; Phase 1A required. |
| `CL` | derived | Source candidate: `Geometry.CL`; Phase 1A required. |
| `CD` | derived | Source candidate: `Geometry.CD`; Phase 1A required. |
| `HD` | derived | Source candidates: `Geometry.HD`, `Geometry.Headers[].HD`; Phase 1A required. |
| `SL` | derived | Source candidates: `Geometry.SL`, `Geometry.Headers[].SL`; Phase 1A required. |
| `S`, `R`, `I`, `O` | derived | Source candidates from `Geometry`; Phase 1A required. |
| `RB`, `TSP`, `BSP`, `REP`, `LEP`, `OAL` | derived | Source candidates from `Geometry`; Phase 1A required. |
| `secondary_dimensions` | future | Label variants such as `FH2`, `HD2`, `SL2`, `R2`, `S2`, `I2`, `O2`. |
| `other_labels` | future | For Phase 1A/1C label dictionary expansion. |

### validation_state

Purpose: make review/release state explicit.

Required status fields:

- `overall_status`
- `schema_status`
- `engineering_review_status`
- `drawing_release_status`
- `missing_required_fields`
- `warnings`
- `open_questions`

`drawing_release_status` must remain `not_released_manufacturing_drawing` for generated/review-aid outputs unless John explicitly approves a future release workflow.

### source_traceability

Purpose: central provenance and normalization record.

Required fields:

- `source_documents`
- `field_trace_policy`
- `normalization_notes`
- `unresolved_dependencies`

## JSON Import/Export Readiness

The model is designed for JSON round-trip work by:

- using stable snake_case canonical paths;
- separating source values from normalized interpretation;
- preserving raw source document references;
- giving every engineering value its own `source_trace`;
- allowing `null` values with explicit status instead of fabricated values;
- reserving `future` fields for later adapters without changing current meanings.

## Known Risks

- The traceable wrapper is verbose. It is appropriate for review-first engineering workflows, but a future UI may need a flattened view model.
- Numeric source codes such as material, tube type, casing type, connection type, and fluid type need lookup tables before they are shown as normalized business values.
- Drawing labels remain provisional until Phase 1A confirms source versus derived mappings.
- HGRH header details cannot be inferred from current HGRH JSON shape alone; John-confirmed classification remains the authority for the locked cases.

## John Review Required

Yes.

Review points:

- Approve or revise the traceable field wrapper approach.
- Confirm the minimum required checklist fields for Direct Coil Phase 1C.
- Confirm whether drawing dimension labels should be user-visible checklist fields or derived-only canonical fields.
- Confirm normalized values for fluid/material/type code tables before implementation.
