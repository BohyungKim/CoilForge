# Phase 1B ChatGPT Review Packet

## One-Line Result

Created a Phase 1B draft Canonical Coil Model and checklist schema that preserve Phase 0C source traceability, support JSON import/export, and stay out of drawing-populator and selection-calculation implementation.

## Files Inspected

- `AGENTS.md`
- `docs/REFERENCE_CASE_SET.md`
- `docs/PLAN.md`
- `docs/IMPLEMENTATION.md`
- `docs/PHASE1_PARALLEL_EXECUTION_PLAN.md`
- `outputs/phase0_reference_lock/locked_reference_case_set.csv`
- `outputs/phase0_reference_lock/john_review_decisions.md`
- `outputs/phase0_reference_lock/phase0c_chatgpt_review_packet.md`
- `outputs/phase0_category_assessment/chatgpt_review_packet.md`
- `outputs/phase0_category_assessment/roadmap_coverage_matrix.md`
- `outputs/phase0_category_assessment/case_classification_summary.csv`
- `outputs/phase0_category_assessment/json_pdf_conflict_report.md`
- `outputs/phase0_category_assessment/uncertain_cases.md`
- Representative read-only source examples:
  - `Case/EZC-0001/CDXC-1.txt`
  - `Case/EZC-0002/RHHGRC-1.json`
  - `Case/EZC-0005/PHWC-1.txt`
  - `Case/EZC-0014/CCWC-1.txt`

## Files Created or Updated

- `schemas/canonical_coil_model.schema.json`
- `schemas/checklist_schema_draft.json`
- `docs/CANONICAL_COIL_MODEL.md`
- `docs/CHECKLIST_SCHEMA.md`
- `outputs/phase1b_model_design/phase1b_chatgpt_review_packet.md`

## Phase 1A Availability

`outputs/phase1a_json_drawing_linkage` exists but contains no files. This Phase 1B draft proceeds from Phase 0C evidence and marks drawing-label mappings as Phase 1A-dependent.

## 1. Proposed Canonical Model Structure

The proposed canonical model includes the required sections:

- `case_identity`
- `project_context`
- `coil_category`
- `product_family`
- `performance_inputs`
- `airside_inputs`
- `fluidside_or_refrigerant_inputs`
- `physical_geometry`
- `casing`
- `headers`
- `connections`
- `distributors`
- `hgbp_or_special_features`
- `handing_and_airflow`
- `drawing_dimensions`
- `validation_state`
- `source_traceability`

Core design decision: each engineering value is represented as a traceable field object with:

- `value`
- `unit`
- `field_role`
- `review_status`
- `source_trace`
- `notes`

This makes source evidence, normalized interpretation, derived values, and future review states explicit.

## 2. Required vs Optional Fields

Draft required fields focus on minimum identity, workflow, classification, physical geometry, and drawing-readiness containers.

Required draft examples:

- `case_identity.coilforge_case_id`
- `case_identity.coil_name`
- `case_identity.model_number`
- `coil_category.category`
- `coil_category.normalized_roadmap_bucket`
- `product_family.source_product_code`
- `airside_inputs.standard_cfm`
- `airside_inputs.entering_air_dry_bulb`
- `fluidside_or_refrigerant_inputs.fluid_type`
- `physical_geometry.rows`
- `physical_geometry.fin_height`
- `physical_geometry.fin_length`
- `physical_geometry.fin_density_fpi`
- `casing.material`
- `casing.gauge`
- `headers.header_type`
- `headers.feed_type`
- `connections.items`
- `handing_and_airflow.coil_hand`

Optional examples:

- `project_context.project_name`
- `project_context.quote_or_job_number`
- `performance_inputs.desired_capacity`
- `fluidside_or_refrigerant_inputs.glycol_mass_percent`
- `physical_geometry.circuits`
- `casing.coating`
- `distributors.items`

Derived examples:

- `coil_category.normalized_roadmap_bucket`
- drawing labels such as `FH`, `FL`, `CH`, `CL`, `CD`, `HD`, `SL`, `S`, `R`, `I`, `O`

Future examples:

- `project_context.customer_name`
- `handing_and_airflow.airflow_direction`
- JSON import/export adapter profile fields
- selection-calculation outputs

## 3. Checklist Fields

The checklist draft is sectioned to populate canonical paths:

- Case Identity
- Project Context
- Coil Category
- Product Family
- Airside Inputs
- Fluidside or Refrigerant Inputs
- Physical Geometry
- Casing and Options
- Headers, Connections, and Distributors
- Handing and Airflow
- Drawing Dimensions
- Validation and Export

Each checklist field includes:

- `field_id`
- user-facing `label`
- `canonical_path`
- `field_role`
- `input_type`
- `source_trace_policy`
- `review_status_default`

This keeps checklist values mappable to canonical model fields without making the checklist the permanent source of truth.

## 4. Drawing-Related Fields

Drawing-related fields are present but marked derived or review-required:

- `FH`
- `FL`
- `CH`
- `CL`
- `CD`
- `HD`
- `SL`
- `S`
- `R`
- `I`
- `O`
- `RB`
- `TSP`
- `BSP`
- `REP`
- `LEP`
- `OAL`
- `secondary_dimensions`
- `other_labels`

Source candidates were visible in representative EZ Coil `Geometry` objects, but Phase 1A is required to confirm actual drawing-label linkage. This draft does not implement drawing population.

## 5. JSON Import/Export Readiness

The draft is JSON-ready because it uses:

- stable schema versioning;
- stable snake_case field names;
- canonical JSON Pointer paths from checklist to model;
- explicit `source_trace` arrays on values;
- nullable values with explicit missing/future/review statuses;
- separate raw source evidence and normalized interpretations;
- `source_documents` and `normalization_notes` for adapter context.

This supports future import/export without silently fabricating values that are not in the source data.

## 6. Risks / Overbuilt Areas

- The traceable field wrapper is verbose. It is justified for review-first engineering traceability but may need a flattened UI view later.
- Drawing dimensions may be overrepresented before Phase 1A. They are included as derived placeholders to keep drawing readiness visible.
- Raw source numeric codes need lookup tables before they become user-facing normalized values.
- HGRH header details are not fully exposed in current HGRH JSON examples; John-confirmed Phase 0C classification remains the authority.
- A checklist with too many fields could slow the MVP. John should confirm which fields are required in Phase 1C.

## 7. Questions for John

1. Should drawing dimensions be checklist-entered, imported/derived only, or allowed but always engineering-review-required?
2. For Phase 1C MVP, which fields are truly required: category, geometry, casing, header/connection, airside, fluidside, or all of them?
3. Should numeric source codes for materials, tube type, casing type, connection type, and fluid type be exposed to users or hidden behind reviewed lookup labels?
4. Should `customer_name`, job number, and project metadata be included in the first Direct Coil checklist, or reserved for future submittal/import phases?
5. Is the `source_feature = ASC` and `normalized_special_feature = HGBP` split the right durable representation for the EZC-0013 pattern?

## Unconfirmed Fields and Assumptions

- Drawing label mappings are not confirmed because Phase 1A output is absent.
- Coil hand normalization is not confirmed; source examples include numeric values, text values, and model suffixes.
- Raw numeric code meanings are not normalized in this draft.
- Required checklist fields are draft recommendations, not approved MVP scope.

## John Review Required Items

- Approve or revise the traceable field wrapper pattern.
- Confirm the minimum required checklist fields for Phase 1C.
- Confirm drawing dimension handling policy.
- Confirm lookup-table direction for raw source numeric codes.
- Confirm that Phase 0C HGRH and HGBP/ASC distinctions are represented correctly.

## Compatibility Concerns for Phase 1D

- Phase 1D should reuse canonical paths from `schemas/checklist_schema_draft.json`.
- Import/export adapters should preserve `source_trace` and should not flatten away review state.
- Export profiles should define which fields are allowed to round-trip to EZ Coil-like JSON versus CoilForge-native JSON.
- Validation state should distinguish schema validity from engineering approval and drawing release status.

## Validation Performed

- `Get-Content schemas\canonical_coil_model.schema.json -Raw | ConvertFrom-Json`: passed.
- `Get-Content schemas\checklist_schema_draft.json -Raw | ConvertFrom-Json`: passed.
- Required output existence check for all five Phase 1B files: passed.
- `rg -n "[ \t]+$"` across the five Phase 1B files: no trailing whitespace matches.

## Out of Scope Preserved

- No drawing populator was built.
- No raw JSON files were modified.
- No raw PDF files were modified.
- No selection calculation engine was added.
- No generated drawing was approved or released.
