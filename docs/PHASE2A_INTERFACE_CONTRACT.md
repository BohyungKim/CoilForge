# Phase 2A Interface Contract

Status: Phase 2A-0 draft contract for parallel implementation workstreams.

Created: 2026-06-05.

This contract defines the local web MVP interface for the DX Header 1 / EZC-0001 vertical slice. It is an implementation boundary document only. It does not implement routes, validation, rendering, or JSON import/export.

## Contract Principles

- The local API accepts and returns sanitized Phase 2A objects only.
- The DX Header 1 parameter state is the editable UI state for the first slice.
- The validation report is the gating object for rendering and snapshot generation.
- SVG output is a review aid and must include review-only status language.
- Source evidence and normalized interpretation remain separate when they differ.
- Unsupported Phase 2A scope must be blocked visibly, not accepted silently.

## Backend Routes

### `GET /`

| Item | Contract |
| --- | --- |
| Purpose | Serve the local browser UI for the Phase 2A MVP. |
| Request shape | No request body. |
| Response shape | HTML page with parameter editor, validation panel, SVG preview region, snapshot action, and metadata display region. |
| Validation behavior | No engineering validation runs on initial page load. The UI should request `/api/default-state` after load. |
| Failure behavior | Return a local server error page or JSON-safe error details in development. Do not expose secrets or local private paths. |

### `GET /api/default-state`

| Item | Contract |
| --- | --- |
| Purpose | Load the sanitized DX Header 1 / EZC-0001 default parameter state. |
| Request shape | No request body. Optional query parameter `fixture=dx_header1_ezc0001_default` may be supported later. |
| Response shape | `DxHeader1ParameterState` plus fixture metadata. |
| Validation behavior | The response must be schema-shaped and must default `release_status` to `review_aid_only` and `drawing_status` to `not_generated`. |
| Failure behavior | Return a structured error if the sanitized fixture is missing or malformed. Do not fall back to raw `Case/` or `outputs/` data. |

Example response shape:

```json
{
  "state": {},
  "fixture": {
    "fixture_name": "sanitized_dx_header1_ezc0001_default",
    "fixture_status": "sanitized_example",
    "source_case_id": "EZC-0001"
  },
  "warnings": []
}
```

### `POST /api/validate`

| Item | Contract |
| --- | --- |
| Purpose | Validate the current DX Header 1 parameter state and return visible checks. |
| Request shape | `DxHeader1ParameterState`. |
| Response shape | `ValidationReport`. |
| Validation behavior | Must check required fields, DX category, Header 1, airflow direction, OAL generation policy, and release/drawing status safety. |
| Failure behavior | Malformed payloads return validation errors. Unsupported category/header returns a `blocked` check rather than a silent fallback. |

### `POST /api/render-svg`

| Item | Contract |
| --- | --- |
| Purpose | Render the current state into an Oxygen8-style SVG review preview. |
| Request shape | `SvgRenderRequest`. |
| Response shape | `SvgRenderResponse`. |
| Validation behavior | The renderer consumes validation flags. It may render with warnings only when warnings are visible in response metadata and the SVG review surface. Blocking issues should prevent generation or return a placeholder review surface marked blocked. |
| Failure behavior | Return structured errors and `blocked_fields` when rendering cannot proceed. Do not return manufacturing approval language. |

### `POST /api/generate-snapshot`

| Item | Contract |
| --- | --- |
| Purpose | Generate a checklist snapshot and drawing metadata package from current state and validation results. |
| Request shape | Current `DxHeader1ParameterState`, latest `ValidationReport`, and optional `SvgRenderResponse.metadata`. |
| Response shape | `ChecklistSnapshot` and `DrawingMetadata`. |
| Validation behavior | Snapshot generation requires current validation. If validation is stale or missing, return a warning or blocked result. |
| Failure behavior | Return structured error details. Do not create external files, write to Notion, export PDF, or import raw data. |

## Core Data Objects

### `DxHeader1ParameterState`

Editable parameter state for the Phase 2A UI. Required fields:

| Field | Type | Rule |
| --- | --- | --- |
| `coil_name` | string | Required. Sanitized fixture uses `SAMPLE_DX_HEADER1`. |
| `model_number` | string | Required. Sanitized fixture uses `DX-SAMPLE-HEADER1`. |
| `coil_category` | string | Must be `DX`. |
| `header_type` | string | Must be `Header 1`. |
| `source_case_id` | string | For default fixture, `EZC-0001`; source context only, not raw data. |
| `rows` | integer | Required positive integer. |
| `fin_height` | number | Required, inches. |
| `fin_length` | number | Required, inches. |
| `fin_density_fpi` | number | Required, fins per inch. |
| `casing_height` | number | Required, inches. |
| `casing_length` | number | Required, inches. |
| `casing_depth` | number | Required, inches. |
| `top_flange` | number | Required, inches. |
| `bottom_flange` | number | Required, inches. |
| `return_bend_allowance` | number | Required, inches. |
| `coil_hand` | string | Required; supported display values can include `Left` and `Right`. |
| `airflow_direction` | string | Required; must not be inferred silently. |
| `return_connection_size` | number | Required, inches. |
| `circuiting_display` | string | Required display text; do not derive unapproved circuiting logic. |
| `notes` | array of strings | Review notes and warnings. |
| `release_status` | string | Must default to `review_aid_only`. |
| `drawing_status` | string | Must default to `not_generated`; generated output may use `generated_review_aid` or `generated_with_warnings`. |

Draft shape:

```json
{
  "coil_name": "SAMPLE_DX_HEADER1",
  "model_number": "DX-SAMPLE-HEADER1",
  "coil_category": "DX",
  "header_type": "Header 1",
  "source_case_id": "EZC-0001",
  "rows": 4,
  "fin_height": 12.0,
  "fin_length": 15.0,
  "fin_density_fpi": 13.0,
  "casing_height": 13.25,
  "casing_length": 18.0,
  "casing_depth": 5.5,
  "top_flange": 0.63,
  "bottom_flange": 0.63,
  "return_bend_allowance": 1.75,
  "coil_hand": "Left",
  "airflow_direction": "left_to_right",
  "return_connection_size": 0.625,
  "circuiting_display": "2 Feed / 24 Pass",
  "notes": [],
  "release_status": "review_aid_only",
  "drawing_status": "not_generated"
}
```

### `ValidationReport`

Validation response for current state.

```json
{
  "validation_status": "pass_with_warnings",
  "summary": {
    "pass_count": 0,
    "warn_count": 0,
    "fail_count": 0,
    "blocked_count": 0,
    "not_applicable_count": 0
  },
  "checks": [
    {
      "check_id": "phase2a_category_dx",
      "status": "pass",
      "severity": "info",
      "target": "coil_category",
      "message": "Coil category is supported for Phase 2A.",
      "requires_review": false
    }
  ],
  "blocked_fields": [],
  "warnings": []
}
```

Allowed check statuses:

- `pass`
- `warn`
- `fail`
- `blocked`
- `not_applicable`

### `SvgRenderRequest`

Request to render current state.

```json
{
  "state": {},
  "validation_report": {},
  "render_options": {
    "viewBox": "0 0 1600 1200",
    "include_review_watermark": true,
    "include_markup_layer": true
  }
}
```

### `SvgRenderResponse`

Renderer response.

```json
{
  "svg": "<svg>...</svg>",
  "metadata": {},
  "warnings": [],
  "blocked_fields": []
}
```

### `ChecklistSnapshot`

Current checklist state captured for review and future export compatibility.

```json
{
  "snapshot_id": "chk_phase2a_example",
  "snapshot_status": "draft_review_aid",
  "source_fixture": "sanitized_dx_header1_ezc0001_default",
  "state": {},
  "validation_status": "pass_with_warnings",
  "created_by": "coilforge_local_mvp"
}
```

### `DrawingMetadata`

Drawing package metadata for the generated review aid.

```json
{
  "drawing_generation_run_id": "draw_phase2a_example",
  "drawing_status": "generated_review_aid",
  "release_status": "review_aid_only",
  "template_id": "phase2a_dx_header1_review_svg",
  "viewBox": "0 0 1600 1200",
  "source_case_id": "EZC-0001",
  "warnings": [],
  "blocked_fields": [],
  "john_review_required": true
}
```

## Field Rules

- `coil_category` must be `DX`.
- `header_type` must be `Header 1`.
- `release_status` must default to `review_aid_only`.
- `drawing_status` must default to `generated_review_aid` after successful generation or `not_generated` before generation.
- `airflow_direction` is required.
- OAL must remain blocked or review_required unless John approves a derived rule.
- No manufacturing approval language allowed.
- Unsupported categories or headers must return `blocked`.
- Missing required fields must return `fail` or `blocked`.
- Right-panel values must not be invented.
- Edited payloads must be revalidated before rendering or snapshot generation.

## SVG Renderer Contract

The SVG renderer should accept a validated parameter state and return:

```json
{
  "svg": "<svg>...</svg>",
  "metadata": {},
  "warnings": [],
  "blocked_fields": []
}
```

SVG must include:

- Fixed viewBox `0 0 1600 1200`.
- Stable IDs.
- Text labels, not outlines.
- Review watermark.
- Title block.
- Front view zone.
- Side/header view zone.
- Right panel zone.
- Bottom dimension table zone.
- Reserved markup layer.

Required stable zone IDs:

- `zone.sheet_frame`
- `zone.title_block`
- `zone.front_view`
- `zone.side_header_view`
- `zone.right_panel`
- `zone.bottom_dimension_table`
- `zone.review_metadata`
- `markup.review`

Required review text:

- `REVIEW AID - NOT FOR MANUFACTURING`

## Validation Contract

Validation must return these check statuses:

- `pass`
- `warn`
- `fail`
- `blocked`
- `not_applicable`

Validation must block or warn for:

- Missing required fields.
- Unsupported coil category.
- Unsupported header type.
- Missing `airflow_direction`.
- OAL active generation attempt.
- Release status implying manufacturing approval.

Minimum check IDs:

| Check ID | Target | Expected behavior |
| --- | --- | --- |
| `phase2a_required_coil_name` | `coil_name` | `blocked` or `fail` when missing. |
| `phase2a_category_dx` | `coil_category` | `pass` only for `DX`; otherwise `blocked`. |
| `phase2a_header1_only` | `header_type` | `pass` only for `Header 1`; otherwise `blocked`. |
| `phase2a_required_airflow_direction` | `airflow_direction` | `pass` when explicit; `blocked` or `warn` when missing. |
| `phase2a_oal_not_approved` | OAL/drawing dimensions | `blocked` or `warn` if active OAL generation is attempted. |
| `phase2a_release_status_safe` | `release_status` | `pass` only for `review_aid_only`. |
| `phase2a_drawing_status_safe` | `drawing_status` | `pass` for `not_generated`, `generated_review_aid`, or `generated_with_warnings`; fail/block manufacturing-like statuses. |

## Failure Response Shape

All API failures should use a structured shape:

```json
{
  "error": {
    "code": "phase2a_validation_error",
    "message": "Payload failed Phase 2A validation.",
    "details": [],
    "blocked_fields": []
  }
}
```

Failure messages must not include secrets, raw customer data, private file paths, or raw source payload excerpts.
