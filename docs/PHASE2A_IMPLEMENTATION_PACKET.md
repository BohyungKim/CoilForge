# Phase 2A Implementation Packet

Status: Phase 2A-0 implementation packet and interface lock.

Created: 2026-06-05.

This packet prepares the implementation boundary for Phase 2A. It does not build the local web app, does not implement the SVG renderer, does not implement the validation engine, and does not approve generated drawings for manufacturing.

## One-Line Objective

Build a local interactive web MVP for DX Header 1 / EZC-0001 where parameter edits update an Oxygen8-style SVG drawing preview with validation feedback.

## Current Approved Scope

- Local web app.
- DX only.
- Header 1 only.
- EZC-0001 first vertical slice.
- SVG preview primary.
- Review aid only.
- No PDF export.
- No selection calculation engine.

## Implementation Assumptions

- Local-only app first.
- FastAPI backend recommended.
- Vanilla HTML/CSS/JavaScript frontend recommended.
- Pydantic models for request/response validation.
- SVG renderer returns SVG text/string.
- Validation engine returns structured checks.
- Sanitized fixtures only in public repo.
- Default parameter data starts from `examples/sanitized/dx_header1_ezc0001_default.json`.
- Raw EZ Coil JSON, raw PDFs, rendered pages, and customer/project source data remain out of repo changes and out of committed fixtures.

## First User Workflow

1. Start local server.
2. Open browser UI.
3. Load default DX Header 1 parameter set.
4. Edit values.
5. Click update or trigger live update.
6. Validation panel updates.
7. SVG drawing preview updates.
8. Checklist snapshot and metadata are available.

## Implementation Modules

| Module | Purpose | Phase 2A boundary |
| --- | --- | --- |
| Local web server | Serve the browser UI and local JSON API. | Local-only; no external systems; no production deployment. |
| Parameter/checklist model | Represent the DX Header 1 editable parameter state. | Use sanitized/default data and explicit user edits only. |
| Canonical adapter | Convert the parameter state into the current draft canonical shape where needed. | Adapter stays narrow to DX Header 1 / EZC-0001 and does not finalize global schemas. |
| Validation engine | Return structured validation checks and drawing-generation gating state. | Must expose warnings/blockers instead of hiding uncertainty. |
| SVG renderer | Generate an Oxygen8-style SVG review preview from validated state. | Review-aid SVG only; no PDF or manufacturing release output. |
| Metadata/snapshot generator | Produce checklist snapshot and drawing metadata objects. | Metadata must preserve review status, fixture/source context, and unresolved items. |
| Simple frontend UI | Let John edit parameters, run validation, inspect SVG, and view warnings. | No multi-case manager, auth, external sync, or production workflow. |
| Integration test/demo flow | Prove the local vertical slice starts and responds with default state, validation, render, snapshot, and metadata. | Focused demo validation only. |

## Out of Scope

- DX Header 2.
- DX Header 3.
- DX HGBP.
- DX Header 4.
- HGRH.
- CWC.
- HWC.
- PDF export.
- Submittal PDF extraction.
- Excel import.
- Full JSON import/export adapter.
- Full selection calculation engine.
- Manufacturing drawing approval.
- Raw EZ Coil / CoilMaster JSON mutation.
- Raw PDF mutation.
- Raw rendered drawing mutation.
- Customer/project source data in public fixtures.
- OAL active generation from an unapproved formula.
- Hidden inference of airflow direction.
- Generalized header suffix semantics.
- HGBP visible drawing treatment.
- Production deployment or external system writes.

## Review Gates

- John must visually review first generated SVG.
- Any blocked/review-required engineering rule must remain visible.
- Generated drawing must not imply manufacturing release.
- OAL must remain blocked or review-required until John approves a derived rule.
- Airflow direction must be an explicit reviewed input or a visible warning/blocker.
- Unsupported category/header input must be rejected or blocked with a visible validation state.
- Right-panel values must be source-backed, manually reviewed, explicitly unknown, or blocked.

## Phase 2A Entry Criteria

- This packet is reviewed.
- The interface contract is accepted as the workstream boundary.
- The sanitized default fixture is accepted as safe public sample data.
- John accepts that Phase 2A implementation will start with DX Header 1 / EZC-0001 only.

## Phase 2A Exit Evidence

Phase 2A implementation will be ready for review only when it can show:

- Local app startup command.
- Browser UI loading evidence.
- Default sanitized DX Header 1 state loading.
- Editable parameter state.
- Validation response with pass, warn, fail, blocked, and not_applicable support.
- SVG preview that updates from current parameter values.
- Checklist snapshot output.
- Drawing metadata output.
- Review watermark in the drawing preview.
- No raw `Case/`, `outputs/`, PDF, Excel, raw JSON/TXT, rendered page, customer, or project source data staged.
