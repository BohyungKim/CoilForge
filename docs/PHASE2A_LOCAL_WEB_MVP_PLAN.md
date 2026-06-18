# Phase 2A Local Web MVP Plan

## Objective

Build the first local interactive CoilForge drawing populator vertical slice.

## First Supported Case

DX Header 1 / EZC-0001 only.

## User Workflow

1. Start local server.
2. Open browser.
3. Load default DX Header 1 parameter values.
4. Edit parameters in checklist-style form.
5. See validation state update.
6. See SVG drawing preview update.
7. Save/export checklist snapshot and drawing metadata.

## Recommended Technical Approach

Backend:

- Python
- FastAPI or simple local server
- Pydantic validation models
- SVG generation module

Frontend:

- Simple HTML/CSS/JavaScript first
- Parameter form
- SVG preview area
- Validation/warning panel
- No heavy frontend framework unless necessary

## Core Modules

- checklist parameter model
- canonical model adapter
- validation engine
- SVG drawing renderer
- local web route/API
- metadata generator

## Initial Inputs

- sanitized default DX Header 1 parameter fixture
- no raw JSON/PDF committed to public repo
- local-only raw EZC-0001 may be used for development reference

## Required UI Fields for First Slice

Include a minimal DX Header 1 field set:

- `coil_name`
- `model_number`
- `coil_category`
- `header_type`
- `rows`
- `fin_height` / `FH`
- `fin_length` / `FL`
- `casing_height` / `CH`
- `casing_length` / `CL`
- `casing_depth` / `CD`
- `top_flange` / `TF`
- `bottom_flange` / `BF`
- `return_bend_allowance` / `RB`
- `coil_hand`
- `airflow_direction`
- `return_connection_size`
- circuiting display text
- notes

## Required Drawing Preview

- SVG review-aid drawing
- visible review watermark
- title block
- front view placeholder/geometry
- side/header view placeholder/geometry
- dimension labels
- right panel
- validation warning display
- reserved markup layer

## Validation Rules

- DX only.
- Header 1 only for Phase 2A.
- Unsupported category/header should be blocked.
- Required fields missing should block or warn clearly.
- OAL should be blocked unless approved.
- No silent inference of airflow direction.
- No manufacturing approval language.

## Out of Scope

- Full selection calculation.
- DX Header 2/3/HGBP implementation.
- DX Header 4.
- HGRH/CWC/HWC.
- PDF export.
- Submittal PDF extraction.
- Excel import.
- Production drawing release.

## Acceptance Criteria

- Local web app can be started.
- Browser UI loads.
- User can edit DX Header 1 parameters.
- SVG preview updates based on parameter values.
- Checklist snapshot is generated from current UI state.
- Validation panel shows pass/warn/blocked statuses.
- Drawing output includes review watermark.
- No raw data is committed.
