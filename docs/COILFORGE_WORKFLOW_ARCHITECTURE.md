# CoilForge Workflow Architecture

Status: Architecture reframe draft for John review.

Created: 2026-06-05.

Scope: Documentation only. This document reframes CoilForge from a simple drawing populator into a Submittal-to-Coil Selection Workbench. It does not change code, UI, parsers, exports, raw data, or external systems.

## 1. Current Business Workflow

Current clarified workflow:

1. The application team selects coils from a customer or project submittal PDF.
2. Engineering adjusts headers in Direct Coil.
3. Minor drawing adjustments are handled by PDF markup or EZ Coil drawing snapshots.
4. The quote is sent after the drawing and coil details are acceptable enough for the quote workflow.

The current process depends on human interpretation of the submittal, software-specific entry in Direct Coil, reference comparison against historical EZ Coil / CoilMaster material, and manual drawing review.

## 2. Pain Points

- Submittal interpretation is not yet converted into structured, traceable coil candidates.
- Direct Coil entry and header adjustment depend on human transfer of information.
- EZ Coil / CoilMaster JSON and drawing snapshots are useful references, but they are not a shared internal source of truth.
- Drawing edits are handled after the fact through markup or snapshot comparison.
- Missing, inferred, and engineer-reviewed values are not consistently separated.
- Back-and-forth happens when the application team, engineering, and quote workflow discover different assumptions at different times.
- A drawing populator alone does not solve the upstream selection and validation problem.

## 3. Target Future Workflow

Target long-term workflow:

```text
Submittal PDF
  -> recognize coil tags, coil types, and candidate specs
  -> create SubmittalCoilCandidate records with source evidence
  -> normalize candidates into CanonicalCoilRecord drafts
  -> populate Direct Coil-specific input drafts
  -> generate review-aid drawing intent and drawing preview
  -> engineering review, adjustment, and approval boundary capture
  -> create quote package with validation and review evidence
```

The near-term path should still be checklist-driven. PDF recognition can arrive later as another source adapter that creates checklist or candidate drafts rather than bypassing review.

## 4. Core Product Definition

CoilForge should be treated as a Submittal-to-Coil Selection Workbench.

The product is not only a drawing generator. It is a review-first workflow layer that helps engineering users move from messy source evidence to structured coil candidates, canonical coil records, software-specific input drafts, generated review drawings, validation reports, and quote-ready review packets.

The core product promise is:

- Capture source evidence.
- Normalize into a common CoilForge record.
- Produce software-specific views and drafts without duplicating business logic.
- Make every uncertain or inferred value visible.
- Generate drawings and quote support artifacts only as review aids until formally approved.

## 5. Architecture

CoilForge should use a shared canonical core with adapters and views around it.

```text
Source adapters
  -> source evidence records
  -> SubmittalCoilCandidate / checklist draft
  -> CanonicalCoilRecord
  -> validation and review layer
  -> target adapters
  -> DrawingIntent / DirectCoilInputDraft / EZ comparison view
  -> ReviewPacket / quote package support
```

### Source Adapters

Source adapters convert external or historical inputs into traceable candidate data. They do not approve values.

Initial and future source adapters:

- Manual checklist entry adapter.
- Sanitized EZ Coil / CoilMaster JSON reference adapter.
- Future submittal PDF extraction adapter.
- Future CoilForge JSON import adapter.
- Future supplier import adapter.

Each source adapter must emit source evidence, source type, source references, confidence or review status, and unresolved values.

### Canonical Coil Record

The CanonicalCoilRecord is the shared internal model. It should preserve source value, normalized value, reviewed value, unit, source references, review status, validation status, and derived-rule references when applicable.

Direct Coil and EZ Coil must not own separate copies of business logic. They should read from or write into the canonical core through adapters.

### Target Adapters

Target adapters turn canonical records into software-specific drafts or views.

Examples:

- Direct Coil adapter creates DirectCoilInputDraft objects and Direct Coil-oriented checklist views.
- EZ Coil adapter imports or compares historical EZ JSON and drawing evidence against canonical fields.
- Future supplier adapters create supplier-specific payloads or comparison views.

Target adapters may format, rename, filter, or map fields for a software interface. They must not invent values or fork product logic.

### Drawing Populator

The drawing populator consumes CanonicalCoilRecord plus DrawingIntent. It should generate review-aid drawings with field bindings, warnings, blocked fields, and review watermarking.

The Phase 2A SVG renderer is an early local version of this layer for the DX Header 1 / EZC-0001 slice.

### Review Layer

The review layer records decisions, engineering adjustments, manual overrides, blocked reasons, and approval boundaries.

It must distinguish:

- a candidate value extracted from source evidence;
- a value accepted by an engineer;
- a value edited by an engineer;
- a value blocked or unknown;
- a drawing approved only as a review aid;
- a value approved outside CoilForge for engineering or manufacturing use.

## 6. Software-Specific Interface Strategy

### Direct Coil Interface

Direct Coil is the near-term target interface because engineering adjusts headers there.

The Direct Coil interface should:

- expose Direct Coil-specific labels and required fields;
- generate DirectCoilInputDraft objects from canonical records;
- keep header adjustment fields explicit and reviewable;
- preserve field provenance back to submittal, checklist, EZ reference, or manual entry;
- block exports until required fields and approval boundaries are defined.

Direct Coil-specific behavior belongs in an adapter or view, not in duplicated core selection logic.

### EZ Coil Interface

EZ Coil / CoilMaster data is reference evidence, not automatically authoritative product logic.

The EZ Coil interface should:

- import or inspect sanitized historical JSON as source evidence;
- compare EZ fields and drawing labels to canonical fields;
- preserve source values separately from normalized CoilForge values;
- identify mappings, conflicts, and missing values;
- support historical drawing snapshot comparison where available.

EZ JSON should help define and validate mappings. It should not become the internal model.

### Future Supplier Interface

Future supplier interfaces should be adapters over the canonical core.

They may:

- map canonical fields into supplier-specific inputs;
- identify unsupported supplier fields;
- produce comparison or quote-support payloads;
- require supplier-specific review gates.

They must not create a second version of CoilForge coil logic.

## 7. Key Data Objects

### SubmittalCoilCandidate

Draft object created from a submittal PDF, manual checklist entry, or imported reference. It captures a possible coil and its evidence before engineering review.

Expected contents:

- candidate_id
- source_document_id
- coil_tag
- detected_or_entered_coil_type
- candidate_specs
- source_evidence_refs
- extraction_or_entry_status
- confidence
- review_status
- unresolved_fields

### CanonicalCoilRecord

Shared internal source of truth after candidate normalization and review decisions.

Expected contents:

- canonical_record_id
- identity
- project_context
- coil_classification
- performance_inputs
- airside_inputs
- fluidside_or_refrigerant_inputs
- physical_geometry
- casing
- headers
- connections
- distributors
- special_features
- drawing_dimensions
- source_traceability
- validation_state
- review_state

### DirectCoilInputDraft

Direct Coil-specific draft generated from the canonical record.

Expected contents:

- draft_id
- source_canonical_record_id
- direct_coil_field_values
- required_fields_missing
- header_adjustment_fields
- adapter_warnings
- blocked_fields
- validation_status
- review_required_fields

### DrawingIntent

Drawing-facing instruction package generated from the canonical record and selected template.

Expected contents:

- drawing_intent_id
- source_canonical_record_id
- drawing_template_id
- drawing_label_bindings
- display_values
- review_watermark_policy
- blocked_or_review_required_labels
- markup_layer_policy
- generation_status

### EngineeringAdjustment

Explicit record of a manual engineering change or decision.

Expected contents:

- adjustment_id
- target_field
- previous_value
- adjusted_value
- reason
- adjusted_by
- adjusted_at
- source_evidence_refs
- review_status
- downstream_effects

### ReviewPacket

Review and quote-support package that groups the candidate, canonical record, draft inputs, drawing intent/output, validation, and open questions.

Expected contents:

- review_packet_id
- workflow_id
- candidate_refs
- canonical_record_ref
- direct_coil_input_draft_ref
- drawing_intent_ref
- drawing_output_ref
- validation_report_ref
- engineering_adjustments
- quote_package_readiness
- open_questions
- john_or_engineering_review_required

## 8. Accuracy Policy

CoilForge should use explicit workflow statuses:

| Status | Meaning |
| --- | --- |
| `ready` | Required data is present for the next workflow step, with no blockers for that step. |
| `review_required` | Data or drawing output can be shown as a review aid, but a human must confirm before relying on it. |
| `blocked` | The next step must not proceed because required data, approved mapping, validation, or review is missing. |
| `manual_override` | A human intentionally overrode source or normalized values; the override must include reason and reviewer. |
| `engineering_approved` | Engineering has approved the relevant value or artifact within the defined workflow boundary. This is not manufacturing release unless a future approved release workflow says so. |

Existing Phase 2A statuses such as `review_aid_only`, `generated_review_aid`, `generated_with_warnings`, and `generation_blocked` should remain compatible with this broader policy.

## 9. Source Evidence Requirements

Every non-manual value should preserve source evidence. Required evidence metadata:

- source_type
- source_document_id or source_case_id
- source location, such as JSON path, PDF page/region, checklist field, or drawing label
- raw source value
- normalized value, if available
- confidence or evidence status
- review status
- notes for conflicts or transformations

If evidence is missing, the field should be marked missing, unknown, or review_required. It should not be filled by guesswork.

## 10. Direct Coil Field Model Priority

Direct Coil should guide the near-term field model priority because it is where engineering currently adjusts headers.

Priority order:

1. Identify required Direct Coil fields for a DX/Header 1 draft.
2. Map those fields to CanonicalCoilRecord paths.
3. Preserve source evidence for each field.
4. Identify fields that are manual-only, derived, unavailable, or review-required.
5. Add validation checks for required fields and unsafe statuses.
6. Expand to additional Direct Coil categories and header patterns only after the DX/Header 1 path is reviewed.

Direct Coil field names may be exposed in a Direct Coil view, but canonical field names should remain software-neutral.

## 11. EZ JSON Role

EZ JSON is historical reference data.

Its role:

- provide source examples for fields, dimensions, headers, connections, circuiting, and category classification;
- support mapping discovery between source data and drawing labels;
- provide comparison evidence for future generated outputs;
- expose conflicts and gaps.

Its non-role:

- it is not automatically authoritative product logic;
- it must not overwrite reviewed Direct Coil requirements;
- raw EZ JSON files must not be modified;
- source-specific field names must not become the only internal model.

## 12. Submittal PDF Role

Submittal PDFs are future source documents for candidate detection.

Their role:

- detect coil tags and candidate coil types;
- extract candidate specs with citations;
- create SubmittalCoilCandidate records;
- prefill checklist drafts where confidence and evidence allow;
- surface ambiguous or missing values for review.

Their non-role:

- PDF extraction does not approve values;
- extraction confidence is not engineering validation;
- PDF parsing should not trigger Direct Coil export or drawing release without review gates.

## 13. Drawing Populator Role

The drawing populator is a review-aid generator that consumes canonical data and drawing intent.

Its role:

- render drawing previews from reviewed or explicitly review-required canonical fields;
- bind visible labels to canonical fields and source evidence;
- show warnings, blockers, and missing values;
- preserve review watermarking;
- support markup-ready output in future phases.

Its non-role:

- it does not perform coil selection calculations;
- it does not approve manufacturing drawings;
- it does not invent dimensions such as OAL without an approved rule.

## 14. Quote Package Role

The quote package should collect enough evidence for the quote workflow without pretending to be final manufacturing release.

Expected contents:

- selected or candidate coil summary;
- Direct Coil input draft status;
- generated review-aid drawing or drawing intent status;
- validation summary;
- engineering adjustments;
- unresolved fields and review-required items;
- source evidence summary;
- quote readiness status.

Quote package status should be separate from drawing release status.

## 15. Recommended Implementation Phases

### Phase 2B: Workflow Architecture Acceptance

- Review this architecture with John.
- Confirm the shared canonical core plus software-specific adapter rule.
- Confirm Direct Coil field model priority.
- Confirm accuracy vocabulary and review boundaries.

### Phase 2C: Direct Coil Field Model Baseline

- Define Direct Coil DX/Header 1 field list.
- Map Phase 2A fields to canonical paths.
- Mark required, optional, derived, review-required, and blocked fields.
- Add a draft DirectCoilInputDraft contract.

### Phase 2D: Canonical Core Contract Update

- Update the canonical model around workflow objects and adapter boundaries.
- Add source evidence and review status requirements for new objects.
- Keep compatibility with Phase 2A local MVP objects.

### Phase 2E: Adapter Contract Design

- Define source adapter interface.
- Define target adapter interface.
- Document EZ JSON reference adapter and Direct Coil target adapter.
- No raw data mutation or external integration.

### Phase 2F: Review Packet Model

- Define ReviewPacket contents and validation summary shape.
- Tie checklist, canonical record, drawing intent, and engineering adjustments together.
- Keep generated artifacts review-aid only.

### Later Phase: Submittal PDF Candidate Extraction

- Implement PDF extraction only after source evidence, candidate object, and review gates are approved.
- Extraction should create SubmittalCoilCandidate drafts, not Direct Coil exports.

### Later Phase: Direct Coil Export

- Implement only after DirectCoilInputDraft, validation, review gates, and external-system boundaries are approved.

## 16. Out-of-Scope Items

Out of scope for this architecture task:

- Code changes.
- UI changes.
- Parser implementation.
- Direct Coil export.
- PDF export.
- Supplier integration.
- Raw data changes.
- Selection calculation engine.
- Manufacturing drawing approval workflow.
- Editing raw JSON, PDF, Excel, rendered page, customer, project, or environment files.

## 17. Safety Rules

- Do not modify raw JSON files.
- Do not modify raw PDF files.
- Do not invent engineering values.
- Do not auto-approve generated drawings.
- Do not treat inferred mappings as confirmed without John or engineering review.
- Do not create separate duplicated business logic for EZ Coil and Direct Coil.
- Do not build the full selection calculation engine until explicitly approved.
- Generated drawings remain engineering review aids until formally approved.
- Direct Coil, EZ Coil, and future supplier interfaces must be adapters/views over the canonical core.
- Source evidence and normalized interpretation must remain separate.
- Manual overrides must be explicit, traceable, and reviewable.

## 18. Next Recommended Implementation Step

Create a Direct Coil field model baseline document for the DX/Header 1 workflow.

Recommended next task:

- Inspect the Phase 2A models, validation rules, renderer labels, and sanitized EZC-0001 fixture.
- Define `DirectCoilInputDraft` as a documentation-only contract.
- Map each current Phase 2A field to a proposed canonical path and Direct Coil field/view label.
- Mark each field as required, optional, derived, review_required, or blocked.
- Preserve `OAL` as review_required or blocked until John approves a rule.
- Do not implement exports or parser changes.

Acceptance criteria for the next task:

- One new Direct Coil field model document.
- No code changes.
- No raw data changes.
- Field mappings include source evidence expectations and review status.
- Validation confirms only the intended doc is staged.
