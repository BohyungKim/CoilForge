# CoilForge Plan

## Phase 0A - Category Assessment

Objective: Classify the available EZ Coil / CoilMaster cases by coil category and drawing/header pattern.

Inputs: Raw case folders, JSON or JSON-like text files, PDFs, rendered drawing pages.

Outputs: Case-level AI category assessments, summary CSV, roadmap coverage matrix, uncertainty and conflict reports.

Acceptance Criteria: Every case has an assessment, every PDF drawing page is rendered, and every roadmap bucket is marked covered, missing, or uncertain.

Out of Scope: Drawing populator implementation, selection calculations, production drawing release.

Review Gate: John reviews uncertain categories before any locked reference-case set is created.

## Phase 0B - John Review Decisions

Objective: Apply John engineering review decisions to correct inferred classifications.

Inputs: Phase 0A reports, John-confirmed HGRH corrections, John-confirmed ASC/HGBP interpretation.

Outputs: Updated case assessments and aggregate reports with JOHN_CONFIRMED classifications.

Acceptance Criteria: HGRH header/feed separation is corrected, EZC-0013 is locked as HGBP, and prior uncertainty notes are preserved as source context.

Out of Scope: Adding new cases or inventing missing buckets.

Review Gate: Confirm the corrected roadmap coverage matches John decisions.

## Phase 0C - Locked Reference Case Set

Objective: Freeze the current reference case set for Phase 1A linkage analysis.

Inputs: Corrected Phase 0B outputs and rendered drawing evidence.

Outputs: Locked reference CSV, John review decision log, Phase 0C review packet, reference case documentation.

Acceptance Criteria: Locked cases distinguish coil_category, header_type, feed_type, special_feature, and review_status.

Out of Scope: Dimension-linkage implementation.

Review Gate: Proceed only when locked coverage is accepted for Phase 1A.

## Phase 1A - JSON to Drawing Dimension Linkage

Objective: Identify which JSON values populate drawing labels and which drawing values are derived by rules.

Inputs: Locked reference cases, JSON source fields, PDF text extraction, rendered drawing pages.

Outputs: Label-to-field mapping table, derived-value candidate list, missing-field report.

Acceptance Criteria: Core drawing labels such as FH, FL, CH, CL, CD, HD, SL, I, S, O, and R are mapped or marked derived/unknown with evidence.

Out of Scope: Building the drawing populator.

Review Gate: Engineering review of the mapping rules before implementation.

## Phase 1B - Canonical Coil Model and Checklist Schema

Objective: Define the internal source-of-truth data model and checklist schema for Direct Coil drawing generation.

Inputs: Phase 1A mappings, locked reference cases, Direct Coil checklist expectations.

Outputs: Canonical Coil Model draft, checklist schema draft, example payloads.

Acceptance Criteria: Required, optional, derived, and review-only fields are clearly separated.

Out of Scope: Full selection calculation engine.

Review Gate: John approves schema shape before code implementation.

## Phase 1C - Checklist-to-Drawing Populator MVP

Objective: Build the first rule-driven MVP that populates a drawing from reviewed checklist/canonical values.

Inputs: Canonical Coil Model, checklist schema, Phase 1A mapping rules.

Outputs: MVP drawing populator, sample generated drawing, validation output.

Acceptance Criteria: A selected reference case can be regenerated as a reviewable drawing aid with traceable field provenance.

Out of Scope: Automatic manufacturing release.

Review Gate: Engineering markup review of generated drawing output.

## Phase 1D - Drawing Validation Engine

Objective: Compare generated drawings against expected source values and rule-derived values.

Inputs: Generated drawings, canonical model payloads, reference mappings.

Outputs: Validation report with pass/warn/fail checks.

Acceptance Criteria: Critical drawing labels and connection features are validated with explicit evidence.

Out of Scope: Black-box approval logic.

Review Gate: John confirms validation checks are meaningful for engineering review.

## Phase 2A - Submittal PDF Extractor

Objective: Extract checklist draft fields from submittal PDFs.

Inputs: Submittal PDFs, extraction rules, checklist schema.

Outputs: Draft checklist values with source citations and confidence flags.

Acceptance Criteria: Extracted values are reviewable and editable before drawing generation.

Out of Scope: Fully automated engineering acceptance.

Review Gate: Human review of extraction accuracy.

## Phase 2B - Web Review and Markup Workflow

Objective: Provide a user workflow for reviewing extracted values, generated drawings, and validation results.

Inputs: Checklist draft, generated drawing, validation report.

Outputs: Review interface, markup capture, approval notes.

Acceptance Criteria: Engineers can inspect, edit, annotate, and export review-ready artifacts.

Out of Scope: External system writes without approval.

Review Gate: John approves review workflow ergonomics.

## Phase 3 - Direct Coil Workflow Integration

Objective: Integrate checklist, drawing, validation, and JSON export into a coherent Direct Coil workflow.

Inputs: MVP populator, validation engine, review workflow, JSON adapter.

Outputs: End-to-end Direct Coil workflow prototype.

Acceptance Criteria: A reviewed checklist can produce drawing, validation report, and JSON export payload.

Out of Scope: Broad product-family coverage beyond approved scope.

Review Gate: Engineering signoff on Direct Coil workflow behavior.

## Phase 4 - Selection-Software-Like JSON Import/Export Platform

Objective: Make JSON import/export a durable platform capability.

Inputs: Canonical model, JSON adapter, reference payloads.

Outputs: Import/export adapters, compatibility checks, versioned payload examples.

Acceptance Criteria: Payloads can round-trip where source data supports it, with clear warnings for unsupported fields.

Out of Scope: Replacing the selection software calculation engine.

Review Gate: John approves payload contract and compatibility limits.

## Phase 5 - Internal Coil Intelligence / Future Selection Engine

Objective: Explore future rule/calculation intelligence after the reviewable workflow is stable.

Inputs: Accumulated reference cases, engineering rules, validated workflow outputs.

Outputs: Candidate rule engine, calculation roadmap, risk review.

Acceptance Criteria: Any intelligence is explainable, testable, and reviewed before use.

Out of Scope: Black-box engineering decisions.

Review Gate: Explicit John approval required before implementation.
