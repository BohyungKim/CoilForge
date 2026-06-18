# Phase 2C-M1 Compatibility Review Workbench

## 1. One-line implementation result

Phase 2C-M1 adds an integrated review-only compatibility workbench that compares sanitized submittal-derived and EZ-derived canonical, Direct Coil draft, readiness, and DrawingIntent summaries without enabling final export, PDF export, or production drawing approval.

## 2. Files changed

- `src/coilforge/compatibility/*`
- `src/coilforge/reconciliation/*`
- `src/coilforge/rules/*`
- `src/coilforge/web_app.py`
- `web/index.html`
- `web/app.js`
- `web/style.css`
- `tests/test_phase2c_compatibility_workbench.py`
- `tests/fixtures/compatibility/submittal_vs_ez_expected.json`
- `docs/PHASE2C_COMPATIBILITY_WORKBENCH.md`

## 3. Compatibility comparison behavior

The comparison starts from the two sanitized paths:

- sanitized submittal candidate -> canonical -> DirectCoilInputDraft -> readiness -> DrawingIntent summary
- sanitized EZ JSON -> canonical -> DirectCoilInputDraft -> readiness -> DrawingIntent summary

Each Direct Coil mapped field is categorized as one of:

- `exact_match`
- `submittal_only`
- `ez_only`
- `value_mismatch`
- `unit_mismatch`
- `status_mismatch`
- `evidence_mismatch`
- `blocked_mismatch`

The workbench keeps missing and unmapped fields visible through `status_mismatch` instead of hiding them. Values that match remain review-only unless later approved through a separate engineering process.

## 4. Review packet behavior

`build_compatibility_diff_review_packet()` generates a Markdown review packet with:

- source path summaries
- compatibility counts
- grouped differences for geometry, airside, refrigerant, materials, connections, drawing parameters, and validation/readiness
- required Direct Coil field issues
- drawing-impacting issues
- DrawingIntent comparison summary
- safety notes
- John/engineering decision list

The packet excludes raw/private source text and does not include raw submittal PDF text or customer source documents.

## 5. Mapping rule registry behavior

The mapping rule registry covers:

- `submittal_to_canonical`
- `ez_to_canonical`
- `canonical_to_direct_coil`
- `direct_coil_to_drawing_intent`

Rule approval statuses are limited to the explicit model values:

- `draft`
- `review_required`
- `approved`
- `deprecated`
- `blocked`

Current sanitized rules are `draft` or `review_required`; no draft or review-required rule is treated as engineering approved.

## 6. Reconciliation policy

The reconciliation policy is review-first:

- matching values may become `confirmed_for_review`
- source-only values remain `review_required`
- value conflicts remain `review_required`
- unit conflicts become `blocked` unless an explicit conversion rule exists
- blocked mismatches become `blocked`
- source evidence IDs are preserved in the decision summary
- downstream final export remains disabled

The policy does not mutate canonical records or Direct Coil drafts.

## 7. UI compatibility panel behavior

The existing web UI now exposes a Compatibility Review panel backed by:

- `GET /api/compatibility/default-demo`
- `POST /api/compatibility/compare`
- `POST /api/compatibility/review-packet`

The older `GET /api/compatibility/default-review` remains available for compatibility with earlier Phase 2C tests.

The panel shows:

- exact matches
- submittal-only fields
- EZ-only fields
- value, unit, status, and blocked mismatch counts
- required field issue count
- drawing-impacting issue count
- export disabled status

Filters are available for all, exact, source-only, mismatch, blocked, matched, held, and unmapped rows.

## 8. Known limitations

- No final Direct Coil export is implemented.
- No PDF export is implemented.
- No OCR or broad PDF parser is implemented.
- No supplier API, DLL, Epicor, quote package, or PO integration is implemented.
- DrawingIntent output remains a review aid only.
- Matching sanitized values are not engineering-approved values.
- The compatibility fixture covers the current sanitized DX/Header 1 path only.

## 9. Remaining John/engineering review items

- Review whether `exact_match` fields can be promoted to a stronger review status in a later phase.
- Approve or reject mapping rules before any production or external-system use.
- Decide whether any unit conversion rules should be introduced.
- Review drawing-impacting fields before drawing semantics are treated as approved.
- Confirm the intended handling of fields that are missing from both sanitized paths.

## 10. Manual demo checklist

1. Start the local app with the existing web app command.
2. Open the CoilForge web UI.
3. Confirm the Compatibility tab/card loads.
4. Confirm exact match, source-only, mismatch, blocked, held, and unmapped filters render rows.
5. Confirm Export and Export PDF remain disabled.
6. Call `GET /api/compatibility/default-demo` and verify `raw_private_data_returned=false`.
7. Call `POST /api/compatibility/compare` with `{}` and verify the same default sanitized case is returned.
8. Call `POST /api/compatibility/review-packet` and verify raw source text is absent.

## 11. Next recommended task

Phase 2C-M2 should add a John/engineering decision capture artifact that records field-level review decisions for exact matches, source-only values, and conflicts without promoting anything to production export.
