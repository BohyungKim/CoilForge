# Phase 2C.4 Mapping Rule Registry + Approval Status

## One-line implementation result

Phase 2C.4 adds a Direct Coil mapping rule registry that summarizes current sanitized submittal and EZ coverage with explicit approval status.

## Scope

- Uses existing sanitized submittal and EZ mapping rule definitions.
- Covers the current 52 Direct Coil-facing field keys.
- Marks mapped rules as `not_approved_review_required`.
- Marks missing Direct Coil field mappings as `not_mapped`.
- Does not create engineering-approved rules or change mapping behavior.

## Current coverage summary

- Total Direct Coil fields: `52`
- Both sanitized sources: `8`
- Submittal-only: `4`
- EZ-only: `6`
- Unmapped: `34`
- Approved: `0`
- Review-required mapped rules: `18`

## Example rule statuses

- `rows_deep`: both sources, not approved, review required.
- `CD`: EZ-only, not approved, review required.
- `total_air_flow_cfm`: submittal-only, not approved, review required.
- `tube_material`: unmapped, not mapped.

## Approval policy

The registry is descriptive. It does not promote candidate evidence, approve engineering values, or enable final export. Any approval must be a separate John/engineering decision.

## Validation

- `python -m pytest`
- `python -m compileall src`
- `git diff --check`

## Next recommended phase

Phase 2C.5 should add a source reconciliation / merge policy engine that selects review surfaces from the registry and compatibility report without overwriting evidence.
