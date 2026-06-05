# CoilForge Phase 1 Parallel Execution Plan

## Status

Phase 1 preparation plan for parallel Codex workstreams.

This plan follows the Phase 0C locked reference case set and John engineering review decisions. Phase 1 is analysis and architecture preparation for a future checklist-driven drawing populator. It is not drawing-populator implementation.

## Phase 0C Reference Inputs

Use these files as the current reference lock:

- `outputs/phase0_reference_lock/locked_reference_case_set.csv`
- `outputs/phase0_reference_lock/john_review_decisions.md`
- `outputs/phase0_reference_lock/phase0c_chatgpt_review_packet.md`
- `docs/REFERENCE_CASE_SET.md`

Phase 0C locked cases include 15 EZ Coil cases. John-confirmed classifications are:

- `EZC-0002`: HGRH / Header 1 / Single Feed
- `EZC-0010`: HGRH / Header 1 / Single Feed
- `EZC-0004`: HGRH / Header 1 / Single Feed
- `EZC-0012`: HGRH / Header 1 / Non-Single Feed
- `EZC-0008`: HGRH / Header 2 / Non-Single Feed
- `EZC-0013`: DX / HGBP, with source evidence preserved as ASC

## Shared Boundaries

All Phase 1 workstreams must preserve these boundaries:

- Do not modify raw JSON files.
- Do not modify raw PDF files.
- Do not move or rename case folders.
- Do not build the drawing populator.
- Do not build the web app.
- Do not build the selection calculation engine.
- Do not invent engineering values.
- Do not auto-approve engineering logic or generated drawings.
- Keep source evidence separate from normalized interpretation.
- Preserve uncertainty and John-review-required items explicitly.
- Keep workstream outputs separated until the merged review stage.

## Parallel Workstream Map

| Workstream | Output Folder | Primary Review Packet |
| --- | --- | --- |
| Phase 1A - JSON <-> Drawing Dimension Linkage | `outputs/phase1a_json_drawing_linkage` | `outputs/phase1a_json_drawing_linkage/phase1a_chatgpt_review_packet.md` |
| Phase 1B - Canonical Coil Model + Checklist Schema | `outputs/phase1b_model_design` | `outputs/phase1b_model_design/phase1b_chatgpt_review_packet.md` |
| Phase 1C - Drawing Label Dictionary + Template Spec | `outputs/phase1c_drawing_spec` | `outputs/phase1c_drawing_spec/phase1c_chatgpt_review_packet.md` |
| Phase 1D - Checklist Workflow + JSON Import/Export Contract | `outputs/phase1d_contract` | `outputs/phase1d_contract/phase1d_chatgpt_review_packet.md` |
| Phase 1 Merged Review | `outputs/phase1_merged_review` | `outputs/phase1_merged_review/phase1_merged_chatgpt_review_packet.md` |

## Phase 1A - JSON <-> Drawing Dimension Linkage

### Objective

Map available EZ Coil / CoilMaster JSON fields and PDF drawing labels to explicit dimension-linkage candidates for the locked reference cases.

The goal is to identify evidence-backed relationships between source JSON values, drawing labels, rendered drawing positions, and normalized project fields without treating inferred mappings as approved engineering logic.

### Inputs

- Phase 0C reference lock files listed above.
- Raw case JSON files under `Case/EZC-*/`.
- Raw case PDF files under `Case/EZC-*/`.
- Existing text extracts under `Case/EZC-*/*.txt`, when present.
- Phase 0 assessment outputs under `outputs/phase0_category_assessment/`.

### Allowed Files to Modify

- `outputs/phase1a_json_drawing_linkage/**`
- Workstream-specific notes under `docs/`, only if clearly named for Phase 1A.

### Required Outputs

- JSON-to-drawing field linkage matrix.
- Per-case evidence notes for linked, conflicting, missing, and uncertain dimensions.
- List of candidate canonical fields discovered from source evidence.
- Explicit unresolved mapping questions for John or engineering review.
- `outputs/phase1a_json_drawing_linkage/phase1a_chatgpt_review_packet.md`

### Out of Scope

- Implementing drawing generation.
- Changing raw JSON or PDF files.
- Creating final canonical schema contracts.
- Auto-confirming inferred dimension mappings.
- Building extraction or rendering automation beyond scoped analysis helpers.

### Acceptance Criteria

- Uses the Phase 0C locked reference case set.
- Covers all locked cases where relevant JSON/PDF evidence exists.
- Separates source evidence from normalized interpretation.
- Labels every inferred mapping with confidence and review status.
- Lists missing, conflicting, or unavailable evidence explicitly.
- Produces a ChatGPT review packet suitable for independent review.

### ChatGPT Review Packet Requirement

The Phase 1A review packet must include:

- One-line result.
- Files inspected.
- Files created or updated.
- Linkage matrix summary.
- Highest-confidence mappings.
- Uncertain or conflicting mappings.
- John review required items.
- Recommended merge-review inputs.
- Validation performed.

## Phase 1B - Canonical Coil Model + Checklist Schema

### Objective

Design the first draft of the Canonical Coil Model and checklist schema that can support future drawing population, JSON import/export, validation, and engineer review.

The model should be architecture preparation only. It must not encode unapproved selection calculations or manufacturing-release logic.

### Inputs

- Phase 0C reference lock files listed above.
- Phase 1A candidate field outputs, if available.
- Existing project docs under `docs/`.
- Raw case source files as reference only.

### Allowed Files to Modify

- `outputs/phase1b_model_design/**`
- `schemas/**`
- Workstream-specific notes under `docs/`, only if clearly named for Phase 1B.

### Required Outputs

- Canonical Coil Model field inventory.
- Checklist schema draft.
- Source-evidence versus normalized-field mapping notes.
- Field status labels such as confirmed, inferred, optional, missing, and John-review-required.
- Draft schema files under `schemas/`, if needed for review.
- `outputs/phase1b_model_design/phase1b_chatgpt_review_packet.md`

### Out of Scope

- Implementing a model runtime.
- Building the checklist UI.
- Creating a full selection calculation engine.
- Treating historical EZ Coil data as authoritative product logic.
- Finalizing shared contracts without merged review.

### Acceptance Criteria

- Defines model/checklist fields at a reviewable draft level.
- Preserves Phase 0C distinctions such as HGRH `header_type` versus `feed_type`.
- Preserves EZC-0013 source `ASC` versus normalized `HGBP`.
- Identifies fields needed by drawing population without implementing population.
- Keeps unconfirmed engineering logic marked for review.
- Produces a ChatGPT review packet suitable for independent review.

### ChatGPT Review Packet Requirement

The Phase 1B review packet must include:

- One-line result.
- Files inspected.
- Files created or updated.
- Proposed model sections.
- Proposed checklist sections.
- Schema draft locations.
- Unconfirmed fields and assumptions.
- John review required items.
- Compatibility concerns for Phase 1D.
- Validation performed.

## Phase 1C - Drawing Label Dictionary + Template Spec

### Objective

Create a drawing label dictionary and template specification for the future drawing populator.

The workstream should identify labels, callouts, zones, repeated drawing elements, and template requirements from the locked reference cases without generating production drawings.

### Inputs

- Phase 0C reference lock files listed above.
- Raw case PDF files under `Case/EZC-*/`.
- Existing rendered page images under `outputs/phase0_category_assessment/rendered_pages/`.
- Phase 1A linkage outputs, if available.
- Existing project docs under `docs/`.

### Allowed Files to Modify

- `outputs/phase1c_drawing_spec/**`
- Workstream-specific notes under `docs/`, only if clearly named for Phase 1C.

### Required Outputs

- Drawing label dictionary.
- Template-zone inventory.
- Per-category and per-header drawing variation notes.
- Markup and validation considerations for generated drawings.
- List of drawing assumptions requiring John or engineering review.
- `outputs/phase1c_drawing_spec/phase1c_chatgpt_review_packet.md`

### Out of Scope

- Generating SVG or PDF drawings.
- Building a drawing renderer.
- Modifying raw PDF files.
- Approving drawing layout or engineering details for manufacturing use.
- Implementing validation logic.

### Acceptance Criteria

- Covers labels and template zones visible in the locked reference evidence.
- Distinguishes common labels from category-specific or header-specific labels.
- Preserves uncertainty for ambiguous labels or unreadable evidence.
- Identifies future renderer requirements without implementing them.
- Produces a ChatGPT review packet suitable for independent review.

### ChatGPT Review Packet Requirement

The Phase 1C review packet must include:

- One-line result.
- Files inspected.
- Files created or updated.
- Label dictionary summary.
- Template-zone summary.
- Category/header variation notes.
- Drawing assumptions requiring review.
- Recommended merge-review inputs.
- Validation performed.

## Phase 1D - Checklist Workflow + JSON Import/Export Contract

### Objective

Define the checklist workflow and JSON import/export contract for future CoilForge architecture.

This workstream prepares the contract between submittal extraction, checklist review, canonical model creation, drawing population, validation, and JSON import/export.

### Inputs

- Phase 0C reference lock files listed above.
- Phase 1B model/checklist draft outputs, if available.
- Phase 1A linkage outputs, if available.
- Existing project docs under `docs/`.
- Raw case JSON files as reference only.

### Allowed Files to Modify

- `outputs/phase1d_contract/**`
- `schemas/**`
- Workstream-specific notes under `docs/`, only if clearly named for Phase 1D.

### Required Outputs

- Checklist workflow specification.
- JSON import contract draft.
- JSON export contract draft.
- Validation-state and review-state definitions.
- Contract compatibility notes with Phase 1B model draft.
- Explicit list of fields or behaviors requiring John review.
- `outputs/phase1d_contract/phase1d_chatgpt_review_packet.md`

### Out of Scope

- Implementing import/export code.
- Creating a web app or checklist UI.
- Writing to external systems.
- Changing raw source JSON files.
- Finalizing shared contract names without merged review.

### Acceptance Criteria

- Defines the workflow stages from submittal PDF through checklist draft, engineer review, canonical model, drawing populator, validation, and JSON import/export.
- Separates draft, reviewed, validated, and approved states.
- Keeps generated drawings as engineering review aids, not released manufacturing drawings.
- Flags schema or contract decisions that affect multiple workstreams.
- Produces a ChatGPT review packet suitable for independent review.

### ChatGPT Review Packet Requirement

The Phase 1D review packet must include:

- One-line result.
- Files inspected.
- Files created or updated.
- Workflow contract summary.
- Import/export contract summary.
- Review and validation state definitions.
- Compatibility questions for Phase 1B and Phase 1C.
- John review required items.
- Validation performed.

## Phase 1 Merged Review Stage

### Objective

Merge the four Phase 1 workstream outputs into one reviewable architecture packet before any implementation phase begins.

### Inputs

- `outputs/phase1a_json_drawing_linkage/phase1a_chatgpt_review_packet.md`
- `outputs/phase1b_model_design/phase1b_chatgpt_review_packet.md`
- `outputs/phase1c_drawing_spec/phase1c_chatgpt_review_packet.md`
- `outputs/phase1d_contract/phase1d_chatgpt_review_packet.md`
- Any workstream matrices, schema drafts, dictionaries, or contract drafts created under the Phase 1 output folders.

### Allowed Files to Modify

- `outputs/phase1_merged_review/**`
- `docs/`, only for a clearly named Phase 1 merged review summary.
- `schemas/`, only for reviewed contract consolidation after John approval.

### Required Outputs

- Cross-workstream conflict list.
- Consolidated Canonical Coil Model and checklist field recommendations.
- Drawing-populator readiness summary.
- Contract/schema decisions requiring John review.
- Implementation-phase readiness recommendation.
- `outputs/phase1_merged_review/phase1_merged_chatgpt_review_packet.md`

### Out of Scope

- Starting Phase 2 implementation.
- Building the drawing populator.
- Building the web app.
- Auto-approving merged architecture decisions.

### Acceptance Criteria

- All four workstream review packets are present.
- Cross-workstream field, label, and contract conflicts are identified.
- John-review-required items are consolidated.
- Implementation is not started.
- The final merged packet states whether CoilForge is ready for the next approved phase.

## Recommended Parallel Prompt Pattern

For each separate Codex thread, start with:

```text
You are working in C:\Users\JohnKim\Desktop\Bins\Projects\CoilForge.
Follow AGENTS.md and docs/PHASE1_PARALLEL_EXECUTION_PLAN.md.
Execute only Phase 1X.
Do not build implementation.
Do not modify raw JSON or PDF files.
Produce the required workstream outputs and ChatGPT review packet.
Report files changed, validation, uncertainty, and John review required items.
```

Replace `Phase 1X` with `Phase 1A`, `Phase 1B`, `Phase 1C`, or `Phase 1D`.
