# Phase 2C-M3 Decision Matrix Review Surface

## 1. One-line implementation result

Phase 2C-M3 adds a John/engineering-facing decision matrix review surface over the existing Phase 2C-M2 field decision matrix, with review grouping, approval-state policy, POs logic visibility, and read-only API access while keeping export, PDF export, final Direct Coil export, OCR, raw ingestion, and engineering approval disabled.

## 2. Files changed

- `docs/PHASE2C_M3_DECISION_MATRIX_REVIEW_SURFACE.md`
- `src/coilforge/compatibility/decision_review.py`
- `src/coilforge/compatibility/__init__.py`
- `src/coilforge/web_app.py`
- `tests/test_phase2c_decision_matrix_review_surface.py`

## 3. Untracked UI compatibility file triage result

| File | Classification | M3 handling |
| --- | --- | --- |
| `docs/PHASE2C_UI_COMPATIBILITY_PANEL.md` | `duplicate_of_committed_workbench` plus `useful_content_to_absorb` | Left untracked. Useful safety notes about review-only UI behavior, disabled export, and validation were absorbed into this M3 document. |
| `tests/test_phase2c_ui_compatibility_panel.py` | `duplicate_of_committed_workbench` plus `useful_content_to_absorb` | Left untracked. Useful API/static-shell safety checks were absorbed into `tests/test_phase2c_decision_matrix_review_surface.py`. |
| `outputs/` | `unsafe/out_of_scope` for this commit | Left untracked. `outputs/ remains unstaged`; no generated output or rendered artifact is committed. |

No duplicate or obsolete UI compatibility files are staged directly in M3.

## 4. Decision review surface summary

The review surface is generated from `FieldDecisionMatrix` and adds:

- grouped field-key lists for John/engineering review
- one review item per Direct Coil field
- explicit approval states that do not include engineering approval
- POs-supported and POs-needs-review visibility
- highlighted CD/BF/TF/CH, drawing-impacting fields, and required Direct Coil fields
- export safety fields fixed to false

The optional read-only API routes are:

- `GET /api/compatibility/decision-matrix`
- `GET /api/compatibility/decision-review`

These routes do not accept approval decisions and do not expose raw/private source text.

## 5. Field categories

Default sanitized fixture category counts:

| Category | Count |
| --- | ---: |
| total_fields | 52 |
| exact_match | 8 |
| submittal_only | 4 |
| ez_only | 6 |
| value_mismatch | 0 |
| unit_mismatch | 0 |
| status_mismatch | 0 |
| evidence_mismatch | 0 |
| blocked_mismatch | 0 |
| missing_both | 34 |
| drawing_impacting | 22 |
| required_direct_coil | 12 |
| needs_john_review | 10 |
| blocked | 0 |
| pos_supported | 2 |
| pos_needs_john_review | 2 |

Review group keys are:

- `exact_match`
- `submittal_only`
- `ez_only`
- `missing_both`
- `status_mismatch`
- `drawing_impacting`
- `required_direct_coil`
- `needs_john_review`
- `blocked`

## 6. CD/BF/TF/CH status

| Field | Category | Current policy | Approval state | Drawing impact | Submittal status | EZ status |
| --- | --- | --- | --- | --- | --- | --- |
| `CD` | `ez_only` | `review_required_source_only` | `needs_john_review` | yes | `missing` | `canonical:review_required\|draft:review_required` |
| `BF` | `ez_only` | `review_required_source_only` | `needs_john_review` | yes | `missing` | `canonical:review_required\|draft:review_required` |
| `TF` | `ez_only` | `review_required_source_only` | `needs_john_review` | yes | `missing` | `canonical:review_required\|draft:review_required` |
| `CH` | `ez_only` | `review_required_source_only` | `needs_john_review` | yes | `missing` | `canonical:review_required\|draft:review_required` |

CD/BF/TF/CH remain source-only, drawing-impacting, and review-required. They are not approved for downstream drawing use.

## 7. Drawing-impacting field status

Drawing-impacting fields are highlighted separately from approval state:

- `rows_deep`
- `fins_per_inch`
- `tubes_high`
- `finned_height`
- `finned_length`
- `airflow_direction`
- `header_type`
- `return_connection_size`
- `coil_hand`
- `CD`
- `I`
- `S`
- `O`
- `R`
- `BF`
- `HD`
- `HF`
- `TF`
- `RF`
- `CH`
- `SL`
- `ZD`

Exact matching drawing-impacting fields are only `confirmed_for_review`, with current policy `confirmed_for_review_not_engineering_approved`.

## 8. POs-supported field status

The review surface exposes POs-supported logic only as review metadata:

| Field | POs status | Source rule | Safety |
| --- | --- | --- | --- |
| `header_type` | `pos_supported_reusable_with_sanitization` | `po_component_coil_detection` | Review categorization only; not approved product logic. |
| `system_type` | `pos_supported_reusable_with_sanitization` | `po_cover_table_product_detection` | Requires sanitized fixtures before behavior changes. |

Global POs logic `po_unit_tag_normalization` and `po_review_before_export_gate` remain reusable governance/intake ideas, but they do not approve Direct Coil fields.

## 9. POs-needs-review logic

POs logic needing John review remains visible but not active downstream:

| Field | POs status | Source rule | Safety |
| --- | --- | --- | --- |
| `drain_pan_type` | `pos_logic_needs_john_review` | `po_bom_linestring_decisions` | Possible quote/BOM signal only; not Direct Coil drawing semantics. |
| `distributor_notes` | `pos_logic_needs_john_review` | `po_bom_linestring_decisions` | Possible quote/BOM signal only; not Direct Coil drawing semantics. |

Not found in safe inspected files:

- `po_application_team_selection`
- `po_bto_selection_workflow`

## 10. Approval state policy

Supported approval states:

- `pending_review`
- `confirmed_for_review`
- `needs_john_review`
- `blocked`
- `not_approved`

Default sanitized fixture approval-state counts:

| Approval state | Count |
| --- | ---: |
| pending_review | 34 |
| confirmed_for_review | 8 |
| needs_john_review | 10 |
| blocked | 0 |
| not_approved | 0 |

Policy details:

- `exact_match` fields use approval state `confirmed_for_review`, but current policy remains `confirmed_for_review_not_engineering_approved`.
- Source-only values use `needs_john_review` and current policy `review_required_source_only`.
- Missing-both values use `pending_review`.
- Unit or blocked mismatches use `blocked`.
- No `engineering_approved` state is created.

## 11. Export disabled policy

The review surface keeps all downstream use disabled:

- `export_allowed=false`
- `pdf_export_enabled=false`
- `direct_coil_final_export_available=false`
- per-field `export_allowed=false`
- per-field `pdf_export_enabled=false`
- per-field `direct_coil_final_export_available=false`
- `raw_private_data_returned=false`

## 12. John/engineering review checklist

- Review CD/BF/TF/CH as EZ-only drawing baseline values before any downstream drawing use.
- Review all 22 drawing-impacting fields before drawing semantics are treated as approved.
- Review all 12 required Direct Coil fields before using them as final input.
- Decide whether POs-supported `header_type` and `system_type` metadata should remain review-only or become a later sanitized detection task.
- Decide whether `po_bom_linestring_decisions` belongs in CoilForge quote/BOM review signals.
- Confirm that missing application-team and BTO/final-selection logic are either not needed or must be sourced separately.

## 13. Validation results

Validation run during implementation:

- `python -m compileall src` - passed.
- `python -m pytest tests/test_phase2c_decision_matrix_review_surface.py` - passed, 12 tests, 1 FastAPI/Starlette deprecation warning.
- `python -m pytest` - passed, 186 tests, 1 FastAPI/Starlette deprecation warning. Note: the currently untracked `tests/test_phase2c_ui_compatibility_panel.py` was present in the worktree and was collected by pytest, but it is not staged for this M3 commit.
- `git diff --check` - passed with Windows LF-to-CRLF warnings only.

Final staged validation:

- `git diff --cached --check` - passed.
- `git diff --cached --name-only` - staged only:
  - `docs/PHASE2C_M3_DECISION_MATRIX_REVIEW_SURFACE.md`
  - `src/coilforge/compatibility/__init__.py`
  - `src/coilforge/compatibility/decision_review.py`
  - `src/coilforge/web_app.py`
  - `tests/test_phase2c_decision_matrix_review_surface.py`

## 14. Next recommended task

Phase 2C-M4 should turn this review surface into a John decision capture packet or disabled-placeholder UI panel for recording review outcomes, still without enabling final export, PDF export, OCR, raw data ingestion, or automatic approval.
