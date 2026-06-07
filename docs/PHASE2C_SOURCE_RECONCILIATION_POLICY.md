# Phase 2C.5 Source Reconciliation / Merge Policy Engine

## One-line implementation result

Phase 2C.5 adds a review-first reconciliation policy engine that turns compatibility comparisons and mapping registry entries into per-field decisions.

## Scope

- Applies policy to current sanitized submittal and EZ comparison output.
- Uses Phase 2C.4 mapping approval status.
- Selects matched values only as review candidates.
- Holds mismatch and source-only values for review.
- Keeps downstream use and export disabled.
- Does not mutate canonical records or overwrite source evidence.

## Current policy behavior

- Matched values: `use_matched_candidate_for_review`
- Mismatches: `hold_mismatch_for_review`
- Source-only values: `hold_source_only_for_review`
- No mapping: `no_mapping_rule`
- Export allowed: `False`
- Policy status: `review_required_no_auto_merge`

## Current sanitized summary

- Total fields: `52`
- Downstream allowed: `0`
- Review required: `52`
- Current mismatches held: `0`
- Source-only fields held for review: `10`

## Review policy

The engine is not an auto-merge tool. It creates a review plan that preserves both source paths and blocks downstream use until John/engineering approval is explicitly recorded in a future phase.

## Validation

- `python -m pytest`
- `python -m compileall src`
- `git diff --check`

## Next recommended phase

Phase 2C.6 should expose the compatibility report and reconciliation plan in the local UI comparison/review panel.
