# Phase 2C.2 Submittal vs EZ Compatibility Regression

## One-line implementation result

Phase 2C.2 adds a review-only regression comparator for the same sanitized case through the submittal-derived and EZ-derived canonical paths.

## Scope

- Compares sanitized submittal candidate data against sanitized EZ JSON reference data.
- Compares through the shared `CanonicalCoilRecord` and Direct Coil draft mapping surface.
- Keeps both sources review-required and export-disabled.
- Does not parse raw PDFs, modify raw JSON, generate PDFs, or approve drawings.

## Regression flow

```text
sanitized submittal candidate -> CanonicalCoilRecord -> Direct Coil draft summary
sanitized EZ JSON fixture      -> CanonicalCoilRecord -> Direct Coil draft summary
                                     |
                                     v
                         Direct Coil field compatibility comparison
```

## Current sanitized case result

- Case: `SCC-SANITIZED-DX-H1-001__EZC-0001`
- Review status: `compatibility_review_required`
- Export allowed: `False`
- Mismatch field count: `0`
- EZ-only drawing fields: `CD`, `BF`, `TF`, `CH`, `SL`, `R`

## Matching field examples

- `rows_deep`
- `finned_height`
- `finned_length`
- `fins_per_inch`
- `airflow_direction`
- `coil_hand`
- `return_connection_size`
- `header_type`

## Review policy

Matching sanitized values still remain review-only because both source paths contain candidate evidence with unreviewed status. Any mismatch changes the report status to `mismatch_review_required`.

## Validation

- `python -m pytest`
- `python -m compileall src`
- `git diff --check`

## Next recommended phase

Phase 2C.3 should package the comparison output into a John/engineering-facing compatibility diff review packet without changing mapping behavior.
