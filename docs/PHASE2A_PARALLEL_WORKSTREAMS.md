# Phase 2A Parallel Workstreams

Status: Phase 2A-0 workstream split for implementation after packet review.

Created: 2026-06-05.

This document defines parallel implementation boundaries for Phase 2A after John reviews the packet and interface contract. It does not implement app source, renderer source, validation source, or tests.

## Workstream Boundaries

- 2A-1 should not implement business validation or renderer details.
- 2A-2 should not implement web routes or renderer.
- 2A-3 should not implement UI or renderer layout.
- 2A-4 should not implement backend routes or validation policy beyond consuming validation flags.
- 2A-5 should not implement UI or SVG geometry.
- 2A-Merge must integrate all prior workstreams and produce a runnable local demo.

## Shared Inputs For All Workstreams

- `docs/PHASE2A_IMPLEMENTATION_PACKET.md`
- `docs/PHASE2A_INTERFACE_CONTRACT.md`
- `docs/PHASE2A_ACCEPTANCE_CRITERIA.md`
- `examples/sanitized/dx_header1_ezc0001_default.json`
- `docs/PHASE2_MVP_SCOPE.md`
- `docs/VALIDATION_CONTRACT.md`
- `docs/DRAWING_TEMPLATE_SPEC.md`
- `docs/JSON_IMPORT_EXPORT_CONTRACT.md`
- `schemas/canonical_coil_model.schema.json`
- `schemas/checklist_schema_draft.json`
- `AGENTS.md`

## 2A-1 Local Web App Shell

| Item | Boundary |
| --- | --- |
| Objective | Create the local browser UI and FastAPI route shell for the Phase 2A MVP. |
| Inputs | Phase 2A interface contract, sanitized fixture path, README/AGENTS safety rules. |
| Allowed files to modify | `src/coilforge/` local server shell files, `web/` static UI files, focused route-shell tests, README updates if needed. |
| Files not allowed to modify | `Case/`, `outputs/`, raw JSON/TXT exports, raw PDFs, rendered pages, public data fixtures outside `examples/sanitized/`, schema contracts unless explicitly approved. |
| Required outputs | Local server entrypoint, static UI shell, route stubs matching the contract, documented startup command. |
| Acceptance criteria | App starts locally, `GET /` loads, `/api/default-state` returns sanitized fixture, route stubs return structured placeholder responses without business logic. |
| Report-back format | Files changed, startup command, route list, validation command, known placeholders, John review items. |
| Merge risks | Route shape drift from contract, accidental validation logic duplication, UI assuming renderer/validation internals. |

## 2A-2 DX Header 1 Parameter / Checklist Model

| Item | Boundary |
| --- | --- |
| Objective | Define the DX Header 1 parameter state and checklist snapshot model used by the UI and API. |
| Inputs | Interface contract, fixture, checklist schema draft, canonical model schema, Phase 2 MVP required fields. |
| Allowed files to modify | `src/coilforge/` model files, `examples/sanitized/` fixture refinements if safe, focused model tests, docs clarifications if needed. |
| Files not allowed to modify | Web route implementation, SVG renderer layout, validation policy implementation, raw source data, generated outputs. |
| Required outputs | Pydantic or equivalent models for `DxHeader1ParameterState` and `ChecklistSnapshot`, fixture loading/parsing helper, tests for required fields/default statuses. |
| Acceptance criteria | Fixture parses successfully, defaults enforce `coil_category=DX`, `header_type=Header 1`, `release_status=review_aid_only`, and `drawing_status=not_generated`. |
| Report-back format | Files changed, model fields, fixture parse result, test command/result, unresolved model questions. |
| Merge risks | Overfitting model to full future schema, adding sensitive source data, treating sanitized fixture values as product logic. |

## 2A-3 Validation Engine

| Item | Boundary |
| --- | --- |
| Objective | Implement Phase 2A validation checks and return structured `ValidationReport` objects. |
| Inputs | Interface contract validation section, `docs/VALIDATION_CONTRACT.md`, Phase 2 approval checklist. |
| Allowed files to modify | `src/coilforge/` validation files, focused validation tests, validation-related docs clarifications if needed. |
| Files not allowed to modify | UI layout, SVG geometry, raw source data, external systems, schema-breaking changes. |
| Required outputs | Validation functions for required fields, DX only, Header 1 only, airflow direction, OAL blocked/review-required, release status safety, drawing status safety. |
| Acceptance criteria | Tests cover pass, warn, fail, blocked, and not_applicable paths; unsupported category/header is blocked; manufacturing approval language is rejected. |
| Report-back format | Files changed, checks implemented, validation statuses covered, test command/result, unresolved rule questions. |
| Merge risks | Making unapproved engineering decisions, hiding blocked conditions as warnings, allowing OAL formula generation without approval. |

## 2A-4 SVG Drawing Renderer

| Item | Boundary |
| --- | --- |
| Objective | Render a DX Header 1 review-aid SVG from validated parameter state and validation flags. |
| Inputs | Interface contract SVG section, drawing template spec, label dictionary, current parameter model. |
| Allowed files to modify | `src/coilforge/` renderer files, renderer tests/snapshots using sanitized data, optional static CSS for SVG if local. |
| Files not allowed to modify | Backend route policy, validation rule policy, UI business logic, raw source data, PDF export code. |
| Required outputs | SVG string generation with fixed viewBox, stable IDs, review watermark, title block, front view, side/header view, right panel, bottom dimension table, reserved markup layer. |
| Acceptance criteria | Renderer output contains `<svg`, `viewBox="0 0 1600 1200"`, stable zone IDs, text labels, `REVIEW AID - NOT FOR MANUFACTURING`, and no manufacturing approval language. |
| Report-back format | Files changed, renderer IDs/zones, SVG validation command/result, limitations, John visual review items. |
| Merge risks | Static SVG not tied to parameter values, layout implying approved manufacturing drawing, renderer inventing missing values. |

## 2A-5 Metadata / Snapshot Package

| Item | Boundary |
| --- | --- |
| Objective | Generate checklist snapshots and drawing metadata from current state, validation, and optional renderer metadata. |
| Inputs | Interface contract object definitions, JSON import/export contract, validation report shape. |
| Allowed files to modify | `src/coilforge/` snapshot/metadata files, focused tests, docs clarifications if needed. |
| Files not allowed to modify | UI, SVG geometry, validation policy, raw source data, full JSON import/export adapter. |
| Required outputs | Snapshot generator, drawing metadata generator, stable IDs, review status fields, source fixture context, unresolved warnings/blocked fields. |
| Acceptance criteria | Snapshot and metadata include `review_aid_only`, `generated_review_aid` or `not_generated`, source fixture context, validation status, and John review required flag. |
| Report-back format | Files changed, generated object examples, test command/result, export limitations, unresolved metadata questions. |
| Merge risks | Accidentally building full export/import adapter, marking drawings complete/approved, losing validation warnings. |

## 2A-Merge Integrated Local Web Vertical Slice

| Item | Boundary |
| --- | --- |
| Objective | Integrate workstreams into one runnable local web MVP for DX Header 1 / EZC-0001. |
| Inputs | Outputs from 2A-1 through 2A-5, Phase 2A acceptance criteria, sanitized default fixture. |
| Allowed files to modify | Integration glue across `src/coilforge/`, `web/`, focused integration tests, README startup notes if needed. |
| Files not allowed to modify | `Case/`, `outputs/`, raw PDFs, raw JSON/TXT exports, rendered pages, customer/project data, external systems. |
| Required outputs | Runnable local app, editable UI, validation panel, SVG preview update, checklist snapshot generation, drawing metadata generation. |
| Acceptance criteria | All Phase 2A acceptance criteria pass or unresolved items are explicitly marked as blockers/John review items. |
| Report-back format | Files changed, demo command, validation command/results, screenshots or local verification notes if available, remaining John review items. |
| Merge risks | Contract mismatch between workstreams, stale validation after edits, SVG not actually responding to parameter changes, unsafe files staged. |

## Safe Staging Rule For Phase 2A Implementation

Before any Phase 2A implementation commit:

```bash
git status --short
git diff --check
git diff --cached --check
git diff --cached --name-only
```

Do not stage:

- `Case/`
- `outputs/`
- `*.pdf`
- `*.xlsx`
- `*.xlsm`
- Raw JSON/TXT exports.
- Rendered pages.
- Customer/project source data.
- `.env` files.
