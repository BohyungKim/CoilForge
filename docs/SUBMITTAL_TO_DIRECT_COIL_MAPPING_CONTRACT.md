# Submittal To Direct Coil Mapping Contract

Status: Phase 2B.2 documentation contract.

Created: 2026-06-05.

Scope: Contract only. This document does not implement PDF parsing, OCR, UI changes, Direct Coil export, PDF export, supplier integration, raw data changes, or drawing release.

## 1. One-Line Objective

Define how future submittal PDF candidates and existing Direct Coil fields map into a review-first `CanonicalCoilRecord` with explicit source evidence, review-required, blocked, unmapped, and manual override policies.

## 2. Current Business Workflow Summary

Current clarified workflow:

1. The application team selects coils from a customer or project submittal PDF.
2. Engineering adjusts headers in Direct Coil.
3. Minor drawing adjustments are handled by PDF markup or EZ Coil drawing snapshots.
4. The quote is sent after the drawing and coil details are acceptable enough for the quote workflow.

Current risk: the human-readable submittal, Direct Coil entry, historical EZ Coil / CoilMaster reference data, and drawing markup do not yet share one traceable internal record. This contract makes the future bridge explicit without implementing extraction.

## 3. Target CoilForge MVP Workflow

Target workflow:

```text
Submittal PDF
  -> detect coil tags, product type candidates, coil type candidates, and spec candidates
  -> create SubmittalCoilCandidate records with SourceEvidence
  -> normalize reviewed candidates into CanonicalCoilRecord drafts
  -> create DirectCoilInputDraft from canonical fields
  -> create DrawingIntent from canonical fields and drawing bindings
  -> render SVG review-aid preview
  -> capture engineering review, manual overrides, blockers, and quote-readiness notes
```

PDF extraction results must not bypass `CanonicalCoilRecord`. Direct Coil drafts and drawing intents read from canonical records after review gates are visible.

## 4. Existing PO / Planning Logic Summary For Submittal PDF Reading

Existing planning documents define PDF work as future source-adapter work, not active parser logic:

- `docs/PLAN.md` identifies a future Submittal PDF Extractor phase that outputs draft checklist values with source citations and confidence flags.
- `docs/CHECKLIST_WORKFLOW.md` says submittal extraction creates checklist drafts with source PDF id, extractor version, extracted field candidates, citations, confidence, warnings, and `review_status = unreviewed`.
- `docs/VALIDATION_CONTRACT.md` says extracted values cannot trigger generation until reviewed and must validate extractor metadata, source PDF identity, citations, candidate structure, confidence metadata, and review status.
- `docs/COILFORGE_WORKFLOW_ARCHITECTURE.md` says submittal PDFs detect coil tags and candidate coil types, create `SubmittalCoilCandidate` records, prefill checklist drafts where confidence and evidence allow, and surface ambiguous or missing values for review.
- `docs/PHASE2A_INTERFACE_CONTRACT.md` and `docs/PHASE2A_REVIEW_PACKET.md` keep the current SVG and snapshot workflow local, sanitized, and review-aid only.

Conclusion: existing planning logic supports the contract shape below, but there is no approved PDF parser, OCR implementation, or automated quote-ready extraction in the repo.

## 5. Supported Initial Submittal Assumptions

Initial future assumptions:

- A submittal PDF may contain one or more coil tags.
- Coil tags may appear in schedules, headers, detail blocks, or notes.
- A coil tag can have multiple nearby candidate specs.
- Product type, coil type, header type, and performance values are candidates until reviewed.
- A candidate value can prefill a checklist or Direct Coil draft only with source evidence and review status.
- The first useful target remains a Direct Coil-oriented DX/Header 1 workflow.
- Sanitized examples can be committed; raw customer/project source text must not be committed.

## 6. Explicit Out-Of-Scope PDF Formats

Out of scope for this phase and for the first implementation phase unless separately approved:

- Scanned-only PDFs requiring OCR.
- Hand-marked PDFs with handwritten specs.
- Multi-project packages where source identity cannot be sanitized.
- PDFs where coil schedules are images without selectable text.
- Non-English submittals.
- Vendor-specific selection reports with unknown unit conventions.
- PDFs that require customer/project names, project numbers, or raw source text to be committed for tests.
- Any format where extraction would require modifying raw PDFs or rendered pages.

## 7. Coil Tag Recognition Rules

Coil tag recognition is candidate-only until reviewed.

- Preserve each detected tag exactly as source-observed in `SourceEvidence.source_value`.
- Store normalized display tag separately from source value.
- Require page and region or extraction rule id for each detected tag.
- If two tags are close to the same spec table, create separate candidates or mark the association `review_required`.
- If a tag is inferred from context rather than explicitly read, set confidence below final-use threshold and mark `review_required`.
- Do not copy raw project/customer text into committed fixtures or contracts.
- Do not merge tags silently.
- Do not drop unrecognized tags; store them in `unmapped_fields` or `unresolved_fields`.

## 8. Product Type Recognition Rules

Product type recognition should classify broad source product evidence, not final engineering meaning.

Initial candidate values:

- `DX`
- `HGRH`
- `CWC`
- `HWC`
- `UNKNOWN`

Rules:

- Product type may come from explicit schedule text, model/source product code, reviewed checklist entry, sanitized EZ reference, or imported CoilForge JSON.
- If product type is inferred from model text or nearby schedule labels, set `review_required`.
- Do not treat inferred `product_type` as final.
- Preserve source product naming separately in `canonical.product_family.source_product_code`.
- Preserve known source-vs-normalized distinctions, such as ASC source evidence and HGBP normalized internal classification.

## 9. Coil Type Recognition Rules

Coil type is a workflow classification candidate that may include category, refrigerant/fluid mode, and special feature.

Rules:

- Store source-observed coil type text under `SourceEvidence`.
- Store normalized interpretation under `canonical.coil_category.category`, `canonical.product_family.application_mode`, or `canonical.hgbp_or_special_features`.
- Mark ambiguous combinations as `review_required`.
- Mark unsupported or missing classification as `blocked` when required for Direct Coil draft generation.
- Do not infer HGRH Single Connection from HGRH Single Feed.
- Do not treat HGBP drawing visibility as approved until John or engineering reviews drawing semantics.

## 10. Header Type Recognition Rules

Current Direct Coil field registry supports `Header 1` only.

Rules:

- `Header 1` may be accepted into a Direct Coil draft only when source evidence or manual review supports it.
- `Header 2`, `Header 3`, and `Header 4` are known future headers and are blockable in the current registry.
- Unknown header type blocks Direct Coil draft readiness when header type is required.
- Header type must stay separate from feed type and connection type.
- Header adjustments made by engineering must be captured as manual overrides or engineering adjustments, not silent changes.

## 11. Performance / Spec Extraction Targets

Future extraction may target:

- Total air flow / standard CFM.
- Face velocity.
- Altitude.
- Entering dry bulb.
- Entering wet bulb.
- Leaving dry bulb.
- Relative humidity.
- Total capacity.
- Refrigerant.
- Evaporating temperature.
- Liquid temperature.
- Superheat.

Policy:

- Extracted performance values remain candidates until reviewed.
- Do not perform selection calculations.
- Do not derive missing values unless an explicit approved rule exists.
- Keep source units and normalized units separate.
- Unit conversion requires an explicit rule id and source evidence.

## 12. Geometry Extraction Targets

Future extraction may target:

- Tube diameter OD.
- Tube geometry.
- Rows deep.
- Fins per inch.
- Tubes high.
- Finned height.
- Finned length.
- Number of feeds.
- Drawing dimensions such as `CD`, `I`, `S`, `O`, `R`, `BF`, `HD`, `HF`, `TF`, `RF`, `CH`, `SL`, and `ZD`.

Policy:

- Geometry values that come from PDFs, EZ references, or imported JSON require evidence.
- Drawing dimensions are not automatically approved manufacturing dimensions.
- OAL remains review-required or blocked until John approves a rule.
- Unmapped drawing labels must be preserved as unmapped, not dropped.

## 13. Material / Construction Extraction Targets

Future extraction may target:

- Tube material.
- Fin material.
- Fin surface.
- Header material.
- Connection material.
- Casing material.
- Casing style.
- Drain pan type.
- Coil coating.
- System type.
- Distributor notes.

Policy:

- Source material codes or shorthand require review before being shown as normalized engineering values.
- Construction notes should be preserved as review notes unless an approved mapping exists.
- Optional values should remain optional but traceable.

## 14. Connection Extraction Targets

Future extraction may target:

- Connection type.
- Supply connection size.
- Return connection size.
- Connection ends.
- Coil hand.
- Distributor capillary size.

Policy:

- Supply and return roles must not be swapped silently.
- Coil hand must preserve source value and normalized value separately.
- Connection end and airflow orientation are drawing-sensitive and require review.
- Missing required connection fields block Direct Coil draft readiness.

## 15. Direct Coil Field-To-Canonical Mapping Table

Accepted source type alias used below:

```text
current_source_types = manual_entry, sanitized_ez_reference, coilforge_json_import, submittal_pdf_candidate
```

`submittal_pdf_candidate` values are candidate values only until reviewed. Drawing parameter `auto` mode additionally requires a reviewed canonical source or approved derived rule.

| direct_coil_field_key | direct_coil_group | canonical_path | expected_unit | required | source_required | accepted_source_types | confidence_policy | review_required_conditions | blocked_conditions | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `tube_diameter_od` | Coil Geometry | `canonical.physical_geometry.tube_diameter_od` | `in` | no | yes | current_source_types | Candidate or imported value requires evidence; low/ambiguous confidence requires review. | Missing optional value; source code requires lookup; source and normalized values differ. | None unless required by selected workflow. | Optional Direct Coil geometry value. |
| `tube_geometry` | Coil Geometry | `canonical.physical_geometry.tube_geometry` | none | no | yes | current_source_types | Text/code values require review before normalized use. | Source code, shorthand, or inferred tube geometry. | None unless selected workflow requires it. | Preserve source text/code separately. |
| `rows_deep` | Coil Geometry | `canonical.physical_geometry.rows` | `rows` | yes | yes | current_source_types | Must be explicit source or reviewed manual value. | PDF candidate, conflicting source values, edited value. | Missing, non-integer, rejected, or unsupported value. | Phase 2A equivalent: `rows`. |
| `fins_per_inch` | Coil Geometry | `canonical.physical_geometry.fin_density_fpi` | `fpi` | yes | yes | current_source_types | Must be explicit source or reviewed manual value. | PDF candidate, unit uncertainty, conflicting source values. | Missing, non-numeric, rejected, or unsupported unit. | Phase 2A equivalent: `fin_density_fpi`. |
| `tubes_high` | Coil Geometry | `canonical.physical_geometry.tubes_high` | `tubes` | no | yes | current_source_types | Candidate requires evidence and review if inferred from drawing. | Inferred from drawing view or schedule note. | None unless selected workflow requires it. | Proposed canonical extension. |
| `finned_height` | Coil Geometry | `canonical.physical_geometry.fin_height` | `in` | yes | yes | current_source_types | Must be explicit source, reviewed manual entry, or approved normalized value. | PDF candidate, unit conversion, conflict with drawing label. | Missing, non-numeric, rejected, or unsupported unit. | Phase 2A equivalent: `fin_height`. |
| `finned_length` | Coil Geometry | `canonical.physical_geometry.fin_length` | `in` | yes | yes | current_source_types | Must be explicit source, reviewed manual entry, or approved normalized value. | PDF candidate, unit conversion, conflict with drawing label. | Missing, non-numeric, rejected, or unsupported unit. | Phase 2A equivalent: `fin_length`. |
| `number_of_feeds` | Coil Geometry | `canonical.physical_geometry.feeds` | `feeds` | no | yes | current_source_types | Source value or reviewed manual entry required for use. | Feed count inferred from circuiting text. | None unless selected workflow requires feeds. | Do not treat feed type as connection type. |
| `airflow_direction` | Coil Geometry | `canonical.handing_and_airflow.airflow_direction` | none | yes | yes | current_source_types | Must be explicit; no silent inference. | Any extracted or imported candidate before engineering confirmation. | Missing airflow direction is blocked. | Drawing-sensitive field. |
| `header_type` | Coil Geometry | `canonical.headers.header_type` | none | yes | yes | current_source_types | Supported value still requires trace or manual review. | Inferred header type; future header values. | Unsupported `header_type` is blocked. | Current registry supports `Header 1` only. |
| `tube_material` | Materials & Construction | `canonical.physical_geometry.tube_material` | none | no | yes | current_source_types | Material codes require lookup and review. | Source code, shorthand, or conflicting sources. | None unless selected workflow requires it. | Optional until Direct Coil material list is confirmed. |
| `fin_material` | Materials & Construction | `canonical.physical_geometry.fin_material` | none | no | yes | current_source_types | Material codes require lookup and review. | Source code, shorthand, or conflicting sources. | None unless selected workflow requires it. | Optional construction value. |
| `fin_surface` | Materials & Construction | `canonical.physical_geometry.fin_surface` | none | no | yes | current_source_types | Text/code values require review. | Source code or unapproved normalized label. | None unless selected workflow requires it. | Proposed canonical extension. |
| `header_material` | Materials & Construction | `canonical.headers.items[].material` | none | no | yes | current_source_types | Header material candidate requires evidence. | Inferred from default or family. | None unless selected workflow requires it. | Header item linkage may require later schema refinement. |
| `connection_material` | Materials & Construction | `canonical.connections.items[].material` | none | no | yes | current_source_types | Connection material candidate requires evidence. | Inferred material, source code, or mismatch with connection type. | None unless selected workflow requires it. | Preserve per-connection role where available. |
| `connection_type` | Materials & Construction | `canonical.connections.items[].type` | none | no | yes | current_source_types | Candidate requires role and source evidence. | Ambiguous supply/return role or source shorthand. | None unless required by selected workflow. | Do not infer from size alone. |
| `supply_connection_size` | Materials & Construction | `canonical.connections.items[role=supply].size` | `in` | no | yes | current_source_types | Candidate requires source evidence and role clarity. | Role ambiguous; unit conversion; conflict with return size. | None unless selected workflow requires supply size. | Preserve source role. |
| `return_connection_size` | Materials & Construction | `canonical.connections.items[role=return].size` | `in` | yes | yes | current_source_types | Must be explicit source or reviewed manual value. | PDF candidate, role ambiguity, unit conversion. | Missing, role-ambiguous, non-numeric, or unsupported unit. | Phase 2A required field. |
| `casing_material` | Materials & Construction | `canonical.casing.material` | none | no | yes | current_source_types | Material candidate requires review if coded or inferred. | Source code, shorthand, or imported default. | None unless selected workflow requires casing material. | Checklist schema marks casing material draft-required; Direct Coil registry currently optional. |
| `casing_style` | Materials & Construction | `canonical.casing.type` | none | no | yes | current_source_types | Style/type candidate requires evidence. | Source code or unapproved normalized style. | None unless selected workflow requires it. | Equivalent to casing type/style. |
| `connection_ends` | Materials & Construction | `canonical.handing_and_airflow.connection_end` | none | no | yes | current_source_types | Drawing-sensitive candidate requires review. | Inferred end, opposite-end note, or drawing-only evidence. | None unless selected workflow requires it. | Keep separate from coil hand and airflow. |
| `coil_hand` | Materials & Construction | `canonical.handing_and_airflow.coil_hand` | none | yes | yes | current_source_types | Must be explicit or reviewed normalization from source code. | Numeric/source-code mapping, PDF candidate, edited value. | Missing, unsupported value, or rejected review. | Allowed Direct Coil values: `Left`, `Right`. |
| `total_air_flow_cfm` | Airside Conditions | `canonical.airside_inputs.standard_cfm` | `cfm` | no | yes | current_source_types | Candidate requires evidence and unit clarity. | PDF candidate, standard vs actual ambiguity. | None unless selected workflow requires airflow. | Direct Coil label is total air flow; canonical initial path uses standard CFM. |
| `face_velocity_fpm` | Airside Conditions | `canonical.performance_inputs.face_velocity` | `fpm` | no | yes | current_source_types | Extracted or derived candidate requires evidence. | Derived from airflow/face area without approved rule. | Block derived use when no approved rule exists. | Proposed canonical extension; no calculation approved. |
| `altitude_ft` | Airside Conditions | `canonical.airside_inputs.altitude` | `ft` | no | yes | current_source_types | Candidate requires evidence and unit clarity. | Missing source unit or conversion needed. | None unless selected workflow requires it. | Optional airside input. |
| `entering_dry_bulb_f` | Airside Conditions | `canonical.airside_inputs.entering_air_dry_bulb` | `degF` | no | yes | current_source_types | Candidate requires evidence and source context. | PDF candidate, schedule ambiguity, unit conversion. | None unless selected workflow requires it. | Checklist schema marks entering dry bulb draft-required; Direct Coil registry currently optional. |
| `entering_wet_bulb_f` | Airside Conditions | `canonical.airside_inputs.entering_air_wet_bulb` | `degF` | no | yes | current_source_types | Candidate requires evidence and source context. | PDF candidate, not applicable, or unit conversion. | None unless selected workflow requires it. | Optional for some workflows. |
| `leaving_dry_bulb_f` | Airside Conditions | `canonical.airside_inputs.leaving_air_dry_bulb` | `degF` | no | yes | current_source_types | Candidate requires evidence and source context. | Desired vs leaving ambiguity; unit conversion. | None unless selected workflow requires it. | Preserve source wording. |
| `relative_humidity_pct` | Airside Conditions | `canonical.airside_inputs.relative_humidity` | `pct` | no | yes | current_source_types | Candidate requires evidence and unit clarity. | RH basis unclear or derived from wet bulb without rule. | Block derived use when no approved rule exists. | Proposed canonical extension. |
| `total_capacity_mbh` | Airside Conditions | `canonical.performance_inputs.desired_capacity` | `MBH` | no | yes | current_source_types | Candidate requires evidence and capacity basis. | Total/sensible/latent ambiguity; unit conversion. | None unless selected workflow requires it. | No selection calculation approved. |
| `refrigerant` | Refrigerant Conditions | `canonical.fluidside_or_refrigerant_inputs.refrigerant` | none | no | yes | current_source_types | Candidate requires evidence or reviewed manual entry. | Source shorthand or conflict with product type. | None unless selected workflow requires it. | Do not infer from DX alone. |
| `evaporating_temp_f` | Refrigerant Conditions | `canonical.fluidside_or_refrigerant_inputs.evaporating_temp` | `degF` | no | yes | current_source_types | Candidate requires evidence and unit clarity. | PDF candidate or unit conversion. | None unless selected workflow requires it. | Optional refrigerant input. |
| `liquid_temp_f` | Refrigerant Conditions | `canonical.fluidside_or_refrigerant_inputs.refrigerant_liquid_temp` | `degF` | no | yes | current_source_types | Candidate requires evidence and unit clarity. | Liquid/condensing/subcooling ambiguity. | None unless selected workflow requires it. | Preserve source label. |
| `superheat_f` | Refrigerant Conditions | `canonical.fluidside_or_refrigerant_inputs.superheat` | `degF` | no | yes | current_source_types | Candidate requires evidence and unit clarity. | Entering vs leaving superheat ambiguity. | None unless selected workflow requires it. | Canonical model also reserves entering/leaving superheat paths. |
| `dx_dist_capillary_size` | Refrigerant Conditions | `canonical.distributors.items[].capillary_size` | none | no | yes | current_source_types | Candidate requires distributor evidence. | Distributor model/capillary ambiguity. | None unless selected workflow requires it. | Proposed distributor item path. |
| `drain_pan_type` | Manufacturing Options | `canonical.casing.drain_pan_type` | none | no | yes | current_source_types | Candidate requires construction evidence. | Source note needs interpretation. | None unless selected workflow requires it. | Proposed canonical extension. |
| `coil_coating` | Manufacturing Options | `canonical.casing.coating` | none | no | yes | current_source_types | Candidate requires evidence and coating vocabulary review. | Source shorthand or unapproved normalized coating. | None unless selected workflow requires it. | Existing canonical casing path includes coating. |
| `system_type` | Manufacturing Options | `canonical.product_family.application_mode` | none | no | yes | current_source_types | Candidate requires evidence and review. | Inferred from product type or schedule context. | None unless selected workflow requires it. | Do not make system type final from PDF inference. |
| `distributor_notes` | Manufacturing Options | `canonical.distributors.notes` | none | no | yes | current_source_types | Notes preserve evidence; do not drive values without review. | Any note that affects generated values. | None unless note is required for selected workflow. | Review-note-only Direct Coil policy. |
| `CD` | Drawing Parameters | `canonical.drawing_dimensions.CD` | `in` | yes | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Drawing review-aid parameter. |
| `I` | Drawing Parameters | `canonical.drawing_dimensions.I` | `in` | no | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Optional drawing parameter. |
| `S` | Drawing Parameters | `canonical.drawing_dimensions.S` | `in` | no | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Optional drawing parameter. |
| `O` | Drawing Parameters | `canonical.drawing_dimensions.O` | `in` | no | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Optional drawing parameter. |
| `R` | Drawing Parameters | `canonical.drawing_dimensions.R` | `in` | no | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Optional drawing parameter. |
| `BF` | Drawing Parameters | `canonical.drawing_dimensions.BF` | `in` | yes | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Required drawing review baseline field. |
| `HD` | Drawing Parameters | `canonical.drawing_dimensions.HD` | `in` | no | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Header dimension candidate. |
| `HF` | Drawing Parameters | `canonical.drawing_dimensions.HF` | `in` | no | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Proposed drawing dimension path. |
| `TF` | Drawing Parameters | `canonical.drawing_dimensions.TF` | `in` | yes | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Required drawing review baseline field. |
| `RF` | Drawing Parameters | `canonical.drawing_dimensions.RF` | `in` | no | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Proposed drawing dimension path. |
| `CH` | Drawing Parameters | `canonical.drawing_dimensions.CH` | `in` | yes | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Required drawing review baseline field. |
| `SL` | Drawing Parameters | `canonical.drawing_dimensions.SL` | `in` | no | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Header/location drawing dimension candidate. |
| `ZD` | Drawing Parameters | `canonical.drawing_dimensions.ZD` | `in` | no | yes | current_source_types | Auto mode requires reviewed canonical source or approved derived rule. | Manual mode, PDF candidate, EZ reference, or missing label mapping. | Auto mode blocked without approved source/rule; manual mode blocked without review metadata. | Proposed drawing dimension path. |

## 16. SubmittalCoilCandidate Object Shape

Draft shape:

```json
{
  "candidate_id": "scc_example",
  "source_document_id": "submittal_sanitized_example",
  "source_document_type": "submittal_pdf",
  "coil_tag": {
    "source_value": "TAG-1",
    "normalized_value": "TAG-1",
    "status": "review_required",
    "source_evidence_refs": ["ev_tag_1"]
  },
  "detected_or_entered_product_type": {
    "source_value": "DX",
    "normalized_value": "DX",
    "status": "review_required",
    "source_evidence_refs": ["ev_product_1"]
  },
  "detected_or_entered_coil_type": {
    "source_value": null,
    "normalized_value": "UNKNOWN",
    "status": "review_required",
    "source_evidence_refs": []
  },
  "candidate_specs": [],
  "unmapped_fields": [],
  "extraction_or_entry_status": "extracted_candidate",
  "confidence": {
    "overall_band": "medium",
    "requires_review": true
  },
  "review_status": "unreviewed",
  "unresolved_fields": []
}
```

## 17. CanonicalCoilRecord Proposed Object Shape

Draft shape:

```json
{
  "canonical_record_id": "ccr_example",
  "canonical_schema_version": "0.1-phase2b2-contract",
  "record_status": "draft",
  "source_candidate_refs": ["scc_example"],
  "case_identity": {},
  "project_context": {},
  "coil_category": {},
  "product_family": {},
  "performance_inputs": {},
  "airside_inputs": {},
  "fluidside_or_refrigerant_inputs": {},
  "physical_geometry": {},
  "casing": {},
  "headers": {},
  "connections": {},
  "distributors": {},
  "hgbp_or_special_features": {},
  "handing_and_airflow": {},
  "drawing_dimensions": {},
  "source_traceability": {
    "source_documents": [],
    "field_trace_policy": "source_evidence_required_for_imported_or_prepopulated_values",
    "unmapped_fields": [],
    "normalization_notes": []
  },
  "validation_state": {
    "overall_status": "not_started",
    "missing_required_fields": [],
    "warnings": [],
    "blocked_fields": [],
    "open_questions": []
  },
  "review_state": {
    "engineering_review_status": "unreviewed",
    "john_review_required": true,
    "drawing_release_status": "review_aid_only"
  }
}
```

Each engineering value inside the record should use a traceable field wrapper:

```json
{
  "value": null,
  "unit": "in",
  "field_role": "required",
  "field_status": "review_required",
  "source_trace": [],
  "review_status": "unreviewed",
  "validation_status": "unchecked",
  "notes": []
}
```

## 18. SourceEvidence Object Shape

Draft shape:

```json
{
  "evidence_id": "ev_example",
  "source_type": "submittal_pdf_candidate",
  "source_document_id": "submittal_sanitized_example",
  "source_location": {
    "page": 1,
    "region_id": "schedule_row_1",
    "extraction_rule_id": "future_rule_id",
    "json_path": null,
    "checklist_field": null,
    "drawing_label": null
  },
  "source_value": "source-observed value or sanitized placeholder",
  "normalized_value": null,
  "unit_source": null,
  "unit_normalized": null,
  "confidence": {
    "score": null,
    "band": "medium",
    "reason": "future extractor candidate"
  },
  "review_status": "unreviewed",
  "evidence_status": "candidate",
  "notes": []
}
```

Source evidence must not require committing raw customer names, project names, project numbers, raw PDF text, raw PDFs, raw rendered pages, or private source payloads.

## 19. Field Status Policy

| Status | Meaning | Allowed next step |
| --- | --- | --- |
| `ready` | Required data is present for the next workflow step and no blocker exists for that step. | May flow into the next draft object, still with provenance. |
| `review_required` | Data may be shown as candidate/review aid but needs human confirmation. | May appear in review UI and review packet; cannot be treated as final. |
| `blocked` | Required data, mapping, unit rule, review, or supported workflow is missing. | Must not generate Direct Coil export or final drawing output. |
| `unmapped` | Source field or Direct Coil field has no approved canonical path or adapter handling. | Preserve in `unmapped_fields`; do not drop silently. |
| `manual_override` | A reviewer intentionally changed or supplied a value. | Use only with override metadata and preserved prior evidence. |

## 20. Unit Handling Policy

- Preserve source unit and normalized unit separately.
- Do not auto-correct or convert units unless an explicit approved rule exists.
- Unit conversion requires a rule id, source value, normalized value, and review status.
- Missing unit on numeric extracted values marks the field `review_required` or `blocked` depending on requiredness.
- Inch-based Direct Coil fields use `in`.
- Temperature fields use `degF`.
- Airflow fields use `cfm` or `fpm`.
- Capacity uses `MBH`.
- Percent uses `pct`.

## 21. Unknown / Unmapped Field Policy

- Unknown source fields must be captured in `unmapped_fields`.
- Unknown Direct Coil fields must be captured with source evidence, source location, candidate value, and reason unmapped.
- Unmapped fields must not be silently dropped during canonical generation, JSON import/export, Direct Coil draft creation, or drawing intent creation.
- If a required Direct Coil field is unmapped, Direct Coil draft readiness is `blocked`.
- If an optional field is unmapped, preserve it as `unmapped` and include it in the review packet.

## 22. Manual Override Policy

Manual overrides must include:

- `target_field`
- `previous_value`
- `override_value`
- `override_reason`
- `reviewed_by`
- `review_status`
- `source_evidence_refs`
- `downstream_effects`

Manual overrides must not erase imported source evidence. They should create a new review decision or engineering adjustment record that points back to the original candidate.

## 23. Engineering Adjustment Policy

Engineering adjustments are expected for Direct Coil header work and drawing review.

Rules:

- Header adjustments must be recorded as `EngineeringAdjustment` records or field-level manual overrides.
- Adjusted values may become the reviewed canonical value only after review status is explicit.
- A Direct Coil-specific adjustment must not fork product logic away from `CanonicalCoilRecord`.
- Drawing previews generated after an adjustment must reference the adjusted canonical snapshot.
- Quote-readiness and manufacturing release remain separate statuses.

## 24. Relationship To DirectCoilInputDraft

`DirectCoilInputDraft` is a target-adapter draft created from `CanonicalCoilRecord`.

Expected shape:

```json
{
  "draft_id": "dci_example",
  "source_canonical_record_id": "ccr_example",
  "direct_coil_field_values": {},
  "required_fields_missing": [],
  "header_adjustment_fields": [],
  "adapter_warnings": [],
  "blocked_fields": [],
  "validation_status": "not_started",
  "review_required_fields": []
}
```

Rules:

- Direct Coil drafts must not read directly from raw PDFs.
- Direct Coil drafts must preserve canonical field refs and source evidence refs.
- Missing required fields block draft readiness.
- Unsupported headers block draft readiness.
- Export to Direct Coil remains out of scope.

## 25. Relationship To DrawingIntent

`DrawingIntent` is a drawing-facing instruction package created from the canonical record and selected template.

Expected shape:

```json
{
  "drawing_intent_id": "di_example",
  "source_canonical_record_id": "ccr_example",
  "drawing_template_id": "phase2a_dx_header1_review_svg",
  "drawing_label_bindings": [],
  "display_values": {},
  "review_watermark_policy": "review_aid_only",
  "blocked_or_review_required_labels": [],
  "markup_layer_policy": "reserved",
  "generation_status": "not_generated"
}
```

Rules:

- Drawing generation must be review-aid only.
- Drawing labels must bind to canonical fields or approved derived rules.
- Missing drawing label mapping is `blocked` or `review_required`, not `pass`.
- Generated drawings are not manufacturing drawings unless a future approved release workflow says so.

## 26. Relationship To EZ JSON Compatibility Path

EZ Coil / CoilMaster JSON remains reference evidence.

Rules:

- Historical EZ data can support mapping discovery and comparison.
- Sanitized EZ reference values can be accepted source evidence when preserved as `sanitized_ez_reference`.
- Raw EZ JSON must not be modified.
- EZ source field names must not become the only internal model.
- Source values and normalized CoilForge values must remain separate.
- Conflicts between EZ reference, submittal extraction, and manual entry require review or blocking.

## 27. Test Plan For Future Implementation

Future implementation tests should cover:

1. A sanitized submittal candidate creates `SubmittalCoilCandidate` without raw source leakage.
2. Each candidate field has `SourceEvidence`.
3. PDF candidate values start as `review_required` or `unreviewed`.
4. Required Direct Coil fields block readiness when missing.
5. `Header 2`, `Header 3`, and `Header 4` remain blocked until supported.
6. Missing `airflow_direction` blocks drawing/Direct Coil draft readiness.
7. Unit conversion does not occur without approved rule id.
8. Unmapped fields are preserved and reported.
9. Manual override preserves prior source evidence.
10. `DirectCoilInputDraft` is generated only from `CanonicalCoilRecord`, not raw PDF results.
11. `DrawingIntent` is generated only from canonical snapshot plus approved bindings.
12. JSON import/export preserves unresolved, blocked, review-required, and unmapped states.

Recommended validation commands for the documentation-only phase:

```bash
git status --short --branch
git diff --check
git diff --cached --check
git diff --cached --name-only
```

## 28. Sanitization Requirements

- Do not commit raw customer names.
- Do not commit raw project names.
- Do not commit project numbers.
- Do not commit raw source text unless already sanitized.
- Do not commit raw PDFs, rendered pages, uploaded reference images, spreadsheets, raw JSON/TXT exports, or private source documents.
- Use sanitized IDs, sanitized tags, and placeholder text in committed fixtures.
- Keep `Case/` and `outputs/` unstaged for this phase.

## 29. Known Risks

- PDF schedule layouts may vary enough that first parser work needs a narrow fixture format.
- Product type and coil type inference can look confident but still be wrong without engineering review.
- Header type, feed type, and connection type can be confused if source text is sparse.
- Material and numeric code lookup tables are not yet approved.
- Drawing dimension labels are still dependent on approved label-to-field evidence.
- Direct Coil requiredness may change after John or engineering reviews the Direct Coil workflow.
- Broad parser implementation before this contract is tested could create false quote-ready signals.

## 30. Recommended Next Implementation Phase

Recommended next phase: sanitized `SubmittalCoilCandidate` fixture and schema test only.

Scope:

- Create one sanitized candidate JSON fixture.
- Create a lightweight schema or dataclass for `SubmittalCoilCandidate` and `SourceEvidence`.
- Add tests that required evidence fields exist and raw/private source text is absent.
- Do not parse PDFs.
- Do not add UI.
- Do not generate Direct Coil exports or PDF exports.
- Do not touch `Case/`, `outputs/`, raw PDFs, raw JSON/TXT exports, spreadsheets, or customer/project documents.

Acceptance criteria:

- Candidate object shape exists in code or schema.
- Source evidence is required for candidate values.
- Candidate values default to `review_required` / `unreviewed`.
- Unknown/unmapped fields are preserved.
- Tests pass.
- Only intended schema/test/sanitized fixture files are staged.
