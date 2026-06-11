# Phase 2C.6 UI Comparison & Review Panel

## One-line implementation result

Phase 2C.6 adds a local UI compatibility review panel backed by the Phase 2C regression, mapping registry, and reconciliation policy.

## Scope

- Adds `/api/compatibility/default-review` for the sanitized default case.
- Adds a Compatibility tab and review panel to the local web shell.
- Displays mismatch count, mapping coverage, held source-only count, downstream allowance, and export-disabled status.
- Adds simple filters for all, matched, held, and unmapped reconciliation decisions.
- Does not enable Direct Coil final export, PDF export, production approval, OCR, or raw source ingestion.

## UI behavior

The panel is review-only. Matched values are shown as candidates, source-only values remain held for review, unmapped fields remain unmapped, and export remains disabled.

## Validation

- `python -m pytest`
- `python -m compileall src`
- `git diff --check`
- Rendered browser check for local app load and Compatibility filter interaction.

## Next recommended phase

Phase 2C.7 should add a sanitized case onboarding template and tests that keep fixture creation away from raw/private/customer data.
