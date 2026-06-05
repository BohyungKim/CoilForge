# Phase 2A Acceptance Criteria

Status: Phase 2A-0 completion checklist for future implementation.

Created: 2026-06-05.

This checklist defines when Phase 2A implementation can be considered ready for John review. It does not implement the local app, renderer, validation engine, or export workflow.

## Completion Checklist

Phase 2A is acceptable only when all applicable items below are demonstrated with current repo evidence:

1. Local app starts successfully.
2. Browser UI loads.
3. Default sanitized DX Header 1 parameter state loads.
4. User can edit parameters.
5. Validation panel updates.
6. SVG preview updates from current parameter values.
7. Unsupported category/header is blocked.
8. Missing `airflow_direction` is blocked or visibly warned.
9. OAL is blocked or visibly marked review-required.
10. Drawing includes review watermark.
11. Drawing release status remains `review_aid_only`/`not_approved`.
12. Checklist snapshot can be generated.
13. Drawing metadata can be generated.
14. No raw Case/output/source files are committed.
15. Tests or validation commands are documented.

## Phase 2A Is Not Complete If

- SVG is static and does not update from parameter changes.
- The system requires raw JSON/PDF files from the public repo.
- The drawing implies manufacturing approval.
- Unsupported buckets are silently accepted.
- OAL is silently generated from an unapproved formula.
- Airflow direction is inferred silently.
- Validation warnings or blockers are hidden from the UI or metadata.
- Checklist snapshot omits current edited values.
- Drawing metadata omits `release_status` or review-aid status.
- Any customer/project source data is needed to run the demo.

## Required Validation Evidence

Future implementation closeout should include:

- Startup command and result.
- Browser/UI verification result.
- Fixture loading check.
- Model or route test for required DX Header 1 fields.
- Validation tests for supported and unsupported category/header.
- Validation tests for missing `airflow_direction`.
- Validation test showing OAL remains blocked or review-required.
- Renderer test showing SVG includes `viewBox="0 0 1600 1200"`.
- Renderer test showing `REVIEW AID - NOT FOR MANUFACTURING`.
- Snapshot/metadata generation test.
- `git status --short`.
- `git diff --check`.
- `git diff --cached --check` before commit.
- `git diff --cached --name-only` before commit.

## John Review Required Before Marking Complete

John or engineering must review:

- First generated SVG visual layout.
- Airflow arrow convention.
- OAL handling or continued block.
- Header/connection suffix semantics before expansion.
- Right-panel requiredness and unknown/blocked behavior.
- Review watermark/title block wording.

## Allowed Phase 2A Status Before John Review

The repo may be reported as `Validated` when technical checks pass, but not `Completed` if John visual/business review remains open.

Generated drawings remain review aids only until formally approved outside CoilForge.
