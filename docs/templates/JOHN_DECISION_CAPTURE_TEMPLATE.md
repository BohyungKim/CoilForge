# John Decision Capture Template

## Review Session Metadata

| Field | Value |
| --- | --- |
| review_date |  |
| reviewer |  |
| phase | Phase 2C-M5 |
| reviewed_commit |  |
| case_id |  |
| decision_scope | manual_review_intent_only |

## Warning

This template records review intent only.
It does not update runtime behavior.
It does not enable export.
It does not approve drawing semantics.

## Allowed Reviewer Decision Values

- `keep_review_required`
- `keep_blocked`
- `accept_for_review_only`
- `request_more_source_evidence`
- `request_unit_conversion_rule`
- `request_drawing_semantics_review`
- `request_manual_engineering_override`
- `mark_not_applicable`
- `defer_decision`

## Explicitly Excluded Approval / Export Values

- `engineering_approved`
- `production_approved`
- `export_ready`
- `quote_ready`

## Decision Table

| field_key | direct_coil_group | canonical_path | current_policy | proposed_decision | reviewer_decision | reviewer_notes | owner | follow_up_required | safe_for_mvp_test |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |
