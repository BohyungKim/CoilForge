# Phase 2E MVP Test Metrics Template

## Test Metadata

| Field | Value |
| --- | --- |
| test_case_id |  |
| source_type | existing_sanitized_demo / sanitized_real_style |
| reviewer |  |
| test_date |  |
| branch | phase2a/local-web-mvp |
| commit |  |
| sanitized_input_confirmed |  |
| prohibited_raw_input_absent |  |

## Safety Status

| Safety invariant | Expected | Observed | Notes |
| --- | --- | --- | --- |
| export_allowed | false |  |  |
| pdf_export_enabled | false |  |  |
| direct_coil_final_export_available | false |  |  |
| production_drawing_approval_claimed | false |  |  |
| final_quote_created | false |  |  |
| raw_private_source_text_returned | false |  |  |

## Timing Metrics

| Metric | Value | Notes |
| --- | ---: | --- |
| manual_baseline_time |  |  |
| CoilForge_assisted_time |  |  |
| estimated_time_saved |  |  |
| current_manual_process_time |  |  |
| application_team_selection_time |  |  |
| engineering_adjustment_time |  |  |
| drawing_markup_EZ_snapshot_time |  |  |
| quote_prep_time |  |  |
| intake_time |  |  |
| review_time |  |  |
| adjustment_time |  |  |
| drawing_review_time |  |  |
| packet_generation_time |  |  |

## Field Coverage Metrics

| Metric | Value | Notes |
| --- | ---: | --- |
| total_fields |  |  |
| ready_fields |  |  |
| review_required_fields |  |  |
| blocked_fields |  |  |
| unmapped_fields |  |  |
| exact_matches |  |  |
| submittal_only_fields |  |  |
| ez_only_fields |  |  |
| conflicts |  |  |
| POs_supported_fields |  |  |
| POs_needs_review_fields |  |  |

## Adjustment / Drawing / Quote Metrics

| Metric | Value | Notes |
| --- | --- | --- |
| engineering_adjustments |  |  |
| manual_corrections |  |  |
| drawing_issues |  |  |
| CD_BF_TF_CH_status |  |  |
| quote_prep_issues |  |  |
| go_no_go_result |  |  |

## Allowed Go / No-Go Values

- GO for continued MVP refinement
- GO with blockers
- NO-GO until drawing review
- NO-GO until source evidence improved
- NO-GO if export/approval accidentally enabled

## Prohibited Status Values

The following values are not allowed as completed MVP-test outcomes:

- `engineering_approved`
- `production_approved`
- `export_ready`
- `quote_ready`

## Notes

| Topic | Notes |
| --- | --- |
| intake notes |  |
| readiness notes |  |
| compatibility notes |  |
| drawing notes |  |
| review packet notes |  |

## Blockers

| Blocker | Impact | Owner | Next action |
| --- | --- | --- | --- |
|  |  |  |  |

## Review-Required Items

| Item | Why review is required | Owner | Target follow-up |
| --- | --- | --- | --- |
| CD/BF/TF/CH | Drawing semantics remain unresolved. | engineering |  |
| airflow convention | Direction convention remains review-required. | John/engineering |  |
| OAL policy | No approved formula or policy in current MVP. | John/engineering |  |
| title block wording | Review-aid wording only. | John/engineering |  |
| 22 drawing-impacting fields | Drawing semantics are not production-approved. | engineering |  |

## Next Fix Recommendation

| Priority | Recommendation | Evidence | Owner |
| --- | --- | --- | --- |
|  |  |  |  |
