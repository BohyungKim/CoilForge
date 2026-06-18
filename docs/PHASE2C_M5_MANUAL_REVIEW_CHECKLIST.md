# Phase 2C-M5 Manual Review Checklist

## 1. One-line implementation result

Phase 2C-M5 adds a John/engineering-facing manual review checklist generator and copy-paste decision template from the Phase 2C-M4 `DecisionCapturePacket`, without adding active approval, persistence, runtime decision application, Direct Coil final export, PDF export, OCR, raw ingestion, or production drawing approval.

## 2. Files changed

- `docs/PHASE2C_M5_MANUAL_REVIEW_CHECKLIST.md`
- `docs/templates/JOHN_DECISION_CAPTURE_TEMPLATE.md`
- `src/coilforge/compatibility/manual_review_export.py`
- `src/coilforge/compatibility/__init__.py`
- `tests/test_phase2c_manual_review_checklist.py`

Known untracked files remain out of this M5 artifact set:

- `docs/PHASE2C_UI_COMPATIBILITY_PANEL.md`
- `tests/test_phase2c_ui_compatibility_panel.py`
- `outputs/`

## 3. Manual review checklist purpose

The manual review checklist is a Markdown/Notion-friendly review package for John and engineering to copy into Notion or a review document.

It is intentionally a copy-paste review format only:

- It returns string content only.
- It does not write generated files to tracked paths by default.
- It does not update runtime behavior.
- It does not persist reviewer decisions.
- It does not enable export or drawing approval.
- It excludes raw/private source text.

## 4. Manual review checklist sections

`build_manual_review_checklist(packet)` renders:

- executive summary
- safety status
- field category summary
- unresolved decision summary
- CD/BF/TF/CH review section
- drawing-impacting field section
- exact match section
- source-only values section
- missing-both fields section
- POs-supported fields section
- POs-needs-review logic section
- unit conversion decision section
- final go/no-go review section

The default sanitized packet currently accounts for:

- 52 decision items
- 9 decision sections
- 8 exact matches
- 4 submittal-only values
- 6 EZ-only values
- 34 missing-both fields
- 22 drawing-impacting fields
- 12 required Direct Coil fields
- 2 POs-supported fields
- 2 POs-needs-review logic fields

Each review item table includes:

- `field_key`
- `direct_coil_group`
- `canonical_path`
- `comparison_category`
- `current_policy`
- `proposed_decision`
- `proposed_decision_status`
- `required_owner`
- `drawing_impact`
- `direct_coil_impact`
- `quote_impact`
- `risk_if_skipped`
- `reviewer_notes`

## 5. John decision capture template summary

`docs/templates/JOHN_DECISION_CAPTURE_TEMPLATE.md` provides a blank copy-paste template with:

- review session metadata
- warning that review intent is not runtime behavior
- allowed reviewer decision values
- explicitly excluded approval/export values
- blank decision table

Review session metadata fields:

- `review_date`
- `reviewer`
- `phase`
- `reviewed_commit`
- `case_id`
- `decision_scope`

Decision table columns:

- `field_key`
- `direct_coil_group`
- `canonical_path`
- `current_policy`
- `proposed_decision`
- `reviewer_decision`
- `reviewer_notes`
- `owner`
- `follow_up_required`
- `safe_for_mvp_test`

## 6. Allowed reviewer decision values

- `keep_review_required`
- `keep_blocked`
- `accept_for_review_only`
- `request_more_source_evidence`
- `request_unit_conversion_rule`
- `request_drawing_semantics_review`
- `request_manual_engineering_override`
- `mark_not_applicable`
- `defer_decision`

Default sanitized proposed decision counts:

- `keep_review_required`: 2
- `keep_blocked`: 0
- `accept_for_review_only`: 9
- `request_more_source_evidence`: 6
- `request_unit_conversion_rule`: 0
- `request_drawing_semantics_review`: 4
- `request_manual_engineering_override`: 8
- `mark_not_applicable`: 0
- `defer_decision`: 23

## 7. Explicitly excluded approval/export values

The template explicitly excludes:

- `engineering_approved`
- `production_approved`
- `export_ready`
- `quote_ready`

These values are not allowed reviewer decisions and must not be used to imply runtime approval, drawing approval, quote readiness, or export readiness.

## 8. CD/BF/TF/CH handling

CD/BF/TF/CH remain:

- EZ-only
- `review_required_source_only`
- review-required
- drawing-impacting
- not downstream-approved

The checklist includes a dedicated CD/BF/TF/CH review section and repeats that these fields are not downstream-approved.

## 9. Drawing-impacting field handling

Drawing-impacting fields remain John/engineering review items.

The checklist states that drawing-impacting fields need John/engineering review before drawing semantics can be treated as approved. Exact drawing-impacting matches remain review-only.

## 10. POs-supported field handling

POs-supported fields remain `recommended_for_rule_review_not_ready`.

Default sanitized POs-supported fields:

- `header_type`
- `system_type`

POs-needs-review logic remains quote/BOM review signal only:

- `drain_pan_type`
- `distributor_notes`

## 11. Unit conversion handling

Unit conversion remains blocked until explicit conversion rule approval.

The default sanitized packet has no unit mismatch items, so the unit conversion section states that no unit conversion mismatches are present in the default packet.

The unit mismatch test case verifies:

- `current_policy=blocked_requires_explicit_conversion_rule`
- `proposed_decision=request_unit_conversion_rule`
- the field remains blocked/request-rule only

## 12. Safety flags

The generated checklist includes these fixed safety flags:

- `export_allowed=false`
- `pdf_export_enabled=false`
- `direct_coil_final_export_available=false`
- `decisions_apply_downstream=false`
- `raw_private_data_returned=false`

The checklist also states:

- exact matches are not engineering approved
- source-only values are not ready
- CD/BF/TF/CH are not downstream-approved
- captured decisions do not apply downstream
- export remains disabled
- PDF export remains disabled
- Direct Coil final export remains unavailable

## 13. Tests / validation results

Validation during implementation:

- `python -m compileall src` - passed.
- `python -m pytest tests/test_phase2c_manual_review_checklist.py` - passed, 14 tests.
- `python -m pytest` - passed, 214 tests, 1 FastAPI/Starlette deprecation warning. Note: the currently untracked `tests/test_phase2c_ui_compatibility_panel.py` was still present in the worktree and was collected by pytest, but it is not staged for this M5 commit.

Final git closeout checks are run before commit:

- `git diff --check`
- `git diff --cached --check`
- `git diff --cached --name-only`

## 14. Remaining John/engineering review items

- Fill the manual review checklist in Notion or a review document.
- Review CD/BF/TF/CH drawing semantics before any drawing baseline use.
- Review all 22 drawing-impacting fields before any drawing approval claim.
- Decide whether POs-supported `header_type` and `system_type` should become future sanitized rule-review tasks.
- Decide whether POs/BOM logic for `drain_pan_type` and `distributor_notes` belongs in quote review metadata.
- Approve explicit unit conversion rules before any unit mismatch can move out of blocked status.

## 15. Next recommended task

Phase 2C-M6 should add a docs-only decision review outcome summary format that lets John manually summarize completed review decisions, still without runtime persistence, approval application, final Direct Coil export, PDF export, OCR, or raw source ingestion.
