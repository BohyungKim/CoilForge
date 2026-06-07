# Phase 2C-M4 John Decision Capture

## 1. One-line implementation result

Phase 2C-M4 adds a disabled John/engineering decision-capture packet, read-only API routes, and a disabled UI placeholder for Phase 2C-M3 review outcomes without creating engineering approval, persistence, PDF export, final Direct Coil export, OCR, raw ingestion, or downstream behavior changes.

## 2. Files changed

- `docs/PHASE2C_M4_JOHN_DECISION_CAPTURE.md`
- `src/coilforge/compatibility/decision_capture.py`
- `src/coilforge/compatibility/__init__.py`
- `src/coilforge/web_app.py`
- `web/index.html`
- `web/app.js`
- `web/style.css`
- `tests/test_phase2c_john_decision_capture.py`

Known untracked files remain out of this M4 artifact set unless separately absorbed in a later task:

- `docs/PHASE2C_UI_COMPATIBILITY_PANEL.md`
- `tests/test_phase2c_ui_compatibility_panel.py`
- `outputs/`

## 3. Decision capture model

`DecisionCaptureItem` records one proposed/pending review outcome per M3 review item:

- `decision_id`
- `field_key`
- `direct_coil_group`
- `canonical_path`
- `comparison_category`
- `current_policy`
- `current_approval_state`
- `proposed_decision`
- `proposed_decision_status`
- `decision_owner`
- `decision_reason`
- `decision_scope`
- `drawing_impact`
- `direct_coil_impact`
- `quote_impact`
- `source_evidence_summary`
- `created_from_phase`
- `export_allowed_after_decision`
- `pdf_export_allowed_after_decision`
- `direct_coil_final_export_allowed_after_decision`
- `notes`

`DecisionCapturePacket` groups those items into John-facing sections, counts proposed decisions, exposes CD/BF/TF/CH status, and fixes these safety values:

- `export_allowed=false`
- `pdf_export_enabled=false`
- `direct_coil_final_export_available=false`
- `decisions_apply_downstream=false`
- `raw_private_data_returned=false`

## 4. Decision packet sections

Default sanitized M4 packet sections:

| Section | Fields | Recommended proposed decision | Required owner |
| --- | ---: | --- | --- |
| Exact matches | 8 | `accept_for_review_only` | `john_or_engineering` |
| Submittal-only values | 4 | `request_more_source_evidence` | `john_or_engineering` |
| EZ-only values | 6 | `request_more_source_evidence` | `john_or_engineering` |
| Missing-both fields | 34 | `defer_decision` | `john` |
| Drawing-impacting fields | 22 | `request_drawing_semantics_review` | `john_or_engineering` |
| Required Direct Coil fields | 12 | `request_manual_engineering_override` | `john_or_engineering` |
| POs-supported fields | 2 | `accept_for_review_only` | `john` |
| POs-needs-review logic | 2 | `keep_review_required` | `john` |
| CD/BF/TF/CH | 4 | `request_drawing_semantics_review` | `engineering` |

Each section includes what is currently known, current policy, recommended proposed decision, required owner, and risk if skipped.

## 5. Proposed decision statuses

Allowed proposed decisions:

- `keep_review_required`
- `keep_blocked`
- `accept_for_review_only`
- `request_more_source_evidence`
- `request_unit_conversion_rule`
- `request_drawing_semantics_review`
- `request_manual_engineering_override`
- `mark_not_applicable`
- `defer_decision`

Allowed proposed decision statuses:

- `pending_review`
- `proposed`
- `needs_john_review`
- `needs_engineering_review`
- `rejected`
- `deferred`

Default sanitized counts by proposed decision:

- `keep_review_required`: 2
- `keep_blocked`: 0
- `accept_for_review_only`: 9
- `request_more_source_evidence`: 6
- `request_unit_conversion_rule`: 0
- `request_drawing_semantics_review`: 4
- `request_manual_engineering_override`: 8
- `mark_not_applicable`: 0
- `defer_decision`: 23

Default sanitized counts by proposed decision status:

- `pending_review`: 1
- `proposed`: 8
- `needs_john_review`: 8
- `needs_engineering_review`: 12
- `rejected`: 0
- `deferred`: 23

## 6. Exact match policy

Exact matches stay `confirmed_for_review_not_engineering_approved`.

The capture layer may propose `accept_for_review_only`, but this means review visibility only. It does not create `engineering_approved`, does not change mapping approval, and does not allow downstream export.

## 7. Source-only policy

Submittal-only and EZ-only values stay source-only review items. The capture layer recommends more source evidence or drawing semantics review depending on impact, but the current policy remains `review_required_source_only`.

No source-only value becomes ready because of a captured proposed decision.

## 8. CD/BF/TF/CH policy

CD/BF/TF/CH remain:

- `ez_only`
- `review_required_source_only`
- `needs_john_review`
- drawing-impacting
- not approved for downstream use

The M4 proposed decision for each is `request_drawing_semantics_review` with status `needs_engineering_review`. Export remains false after decision capture.

## 9. Drawing-impacting field policy

Drawing-impacting fields remain review-required or John/engineering review items. Exact drawing-impacting matches are still review-only because value agreement does not approve drawing semantics.

The drawing-impacting section risk is that drawing semantics could be implied without approval if John/engineering review is skipped.

## 10. POs-supported logic policy

POs-supported fields remain `recommended_for_rule_review_not_ready`.

In the default sanitized packet:

- `header_type`
- `system_type`

These are review metadata only. They do not approve Direct Coil field values, drawing semantics, quote logic, or export readiness.

POs-needs-review logic remains `po_logic_review_signal_only` for:

- `drain_pan_type`
- `distributor_notes`

## 11. Unit conversion policy

Unit conversion decisions remain blocked until explicit conversion rules are approved in a future phase.

In a unit-mismatch test case, `finned_height` becomes:

- `comparison_category=unit_mismatch`
- `current_policy=blocked_requires_explicit_conversion_rule`
- `current_approval_state=blocked`
- `proposed_decision=request_unit_conversion_rule`
- `proposed_decision_status=needs_engineering_review`
- `export_allowed_after_decision=false`

## 12. Export disabled policy

The capture layer keeps all downstream behavior disabled:

- `export_allowed=false`
- `pdf_export_enabled=false`
- `direct_coil_final_export_available=false`
- `export_allowed_after_decision=false`
- `pdf_export_allowed_after_decision=false`
- `direct_coil_final_export_allowed_after_decision=false`
- `decisions_apply_downstream=false`

Captured decisions do not change `DirectCoilInputDraft` readiness, `DrawingIntent.review_status`, `DrawingIntent.export_allowed`, or drawing approval claims.

## 13. Optional UI/API behavior

Added read-only routes:

- `GET /api/compatibility/decision-capture`
- `GET /api/compatibility/decision-capture/template`

The template route returns the same disabled packet plus:

- `template_mode=disabled_placeholder`
- `save_enabled=false`
- `engineering_approval_enabled=false`
- `production_persistence_enabled=false`

The web shell adds a disabled John Decision Capture panel that shows:

- decision packet status
- drawing-impacting field count
- POs-supported count
- POs-needs-review count
- CD/BF/TF/CH
- disabled proposed-decision placeholders
- warning that decisions are not applied to downstream logic

No active approval button, production save behavior, PDF export, or final export control is added.

## 14. Tests / validation results

Validation during implementation:

- `python -m compileall src` - passed.
- `python -m pytest tests/test_phase2c_john_decision_capture.py` - passed, 14 tests, 1 FastAPI/Starlette deprecation warning.
- `python -m pytest tests/test_phase2c_decision_matrix_review_surface.py tests/test_phase2c_john_decision_capture.py` - passed, 26 tests, 1 FastAPI/Starlette deprecation warning.
- `python -m pytest` - passed, 200 tests, 1 FastAPI/Starlette deprecation warning. Note: the currently untracked `tests/test_phase2c_ui_compatibility_panel.py` was still present in the worktree and was collected by pytest, but it is not staged for this M4 commit.

Browser validation:

- Started current working-tree app on `http://127.0.0.1:8013/` because an existing `8012` process did not include the new M4 route.
- Verified page title `CoilForge Direct Coil Draft`.
- Verified John Decision Capture panel rendered.
- Verified 12 proposed-decision placeholders were disabled.
- Verified Review & Export tab interaction kept the capture panel visible.
- Verified Export and Export PDF buttons stayed disabled.
- Verified browser console returned no warnings or errors.

Final git closeout checks are run before commit:

- `git diff --check`
- `git diff --cached --check`
- `git diff --cached --name-only`

## 15. Remaining John/engineering review items

- Decide whether exact matches can remain `accept_for_review_only` in future review packets or need a stronger separate review status.
- Review CD/BF/TF/CH drawing semantics before any drawing baseline use.
- Review all 22 drawing-impacting fields before any drawing approval claim.
- Decide whether POs-supported `header_type` and `system_type` should become future sanitized rule-review tasks.
- Decide whether POs/BOM logic for `drain_pan_type` and `distributor_notes` belongs in quote review metadata.
- Approve explicit unit conversion rules before any unit mismatch can move out of blocked status.

## 16. Next recommended task

Phase 2C-M5 should create a John-facing review packet export format or review checklist for manually filling proposed decisions outside the runtime, still without persistence, approval workflow, final Direct Coil export, PDF export, OCR, or raw source ingestion.
