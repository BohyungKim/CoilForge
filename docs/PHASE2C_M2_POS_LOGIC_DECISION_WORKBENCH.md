# Phase 2C-M2 POs Logic Decision Workbench

## 1. One-line implementation result

Phase 2C-M2 adds a review-only POs logic intake bridge and field-level decision matrix that connect existing sanitized compatibility results to John/engineering field decisions without enabling export, PDF export, OCR, supplier integration, or production drawing approval.

## 2. Files changed

- `docs/PHASE2C_M2_POS_LOGIC_DECISION_WORKBENCH.md`
- `docs/PO_LOGIC_TO_COILFORGE_RULE_MAP.md`
- `src/coilforge/submittal/po_logic_bridge.py`
- `src/coilforge/compatibility/decision_matrix.py`
- `src/coilforge/submittal/__init__.py`
- `src/coilforge/compatibility/__init__.py`
- `tests/test_phase2c_pos_logic_decision_workbench.py`
- `tests/fixtures/compatibility/field_decision_matrix_expected.json`

## 3. POs logic locations inspected

CoilForge internal files inspected:

- `docs/PHASE2C_COMPATIBILITY_WORKBENCH.md`
- `docs/PHASE2C_EZ_JSON_COMPATIBILITY.md`
- `docs/PHASE2B_ACCURACY_HARNESS.md`
- `docs/SUBMITTAL_TO_DIRECT_COIL_MAPPING_CONTRACT.md`
- `docs/DIRECT_COIL_FIELD_MODEL.md`
- `src/coilforge/compatibility/*`
- `src/coilforge/rules/*`
- `src/coilforge/reconciliation/*`
- `src/coilforge/submittal/*`
- `src/coilforge/contracts/*`
- `src/coilforge/direct_coil/*`
- `src/coilforge/drawing/*`
- `src/coilforge/workflows/*`
- `tests/fixtures/compatibility/*`
- `examples/sanitized/*`
- `tests/*`

Sibling project file-name search identified `C:\Users\JohnKim\Desktop\Bins\Projects\PO_Release_Engineering_Workflow\pdf_extractor` as the relevant source. Only code and project documents were inspected:

- `pdf_processing.py`
- `bom_ordering_rules.py`
- `EXTRACTION_CONTRACT.md`
- `PROJECT_CONTEXT.md`

Excluded from inspection: raw PDFs, Excel exports, raw JSON/TXT exports, customer/project source folders, `Case/`, `outputs/`, generated reports, logs, SQLite memory stores, venv/site-packages, and rendered pages.

## 4. POs logic found / not found summary

Found:

- Submittal PDF reading pipeline exists in the sibling project, but it is not safe to import or enable in CoilForge Phase 2C-M2.
- Coil tag recognition and normalization logic exists.
- Product/equipment type detection signals exist through unit tag prefixes and item-column keywords.
- Coil/component detection signals exist through deterministic component tag families.
- POs/BOM linestring rules exist, but they are manufacturing/task workflow rules, not approved Direct Coil drawing semantics.
- Review-before-export governance exists and aligns with CoilForge review-aid posture.

Not found in safe inspected files:

- Application-team selection logic.
- BTO/final selection workflow logic.
- Approved Direct Coil engineering field approval logic.

## 5. Reusable logic map

Reusable now:

- `po_unit_tag_normalization`: normalize unit tags by uppercasing, collapsing whitespace/dashes, and rejecting component-like tags.
- `po_review_before_export_gate`: require human review before export or downstream use.

Reusable with sanitization:

- `po_cover_table_product_detection`: use tag prefixes and product keywords as candidate source signals after sanitized fixture support exists.
- `po_component_coil_detection`: use component family recognition as review categorization only, not approved product logic.

Needs John review:

- `po_bom_linestring_decisions`: linestring-driven Required/Inventory/Manufactured/N/A task logic may help quote/BOM review, but it is not Direct Coil drawing logic.

Not safe for CoilForge Phase 2C-M2:

- `po_pdf_extraction_pipeline`: PDF text/image extraction, vision fallback, raw PDF handling, and parser behavior remain out of scope.

Not found:

- `po_application_team_selection`
- `po_bto_selection_workflow`

## 6. Not-safe / needs-review logic

Not safe:

- PDF parsing, OCR/vision fallback, raw text extraction, and source document ingestion.
- Any parser path that requires raw customer/project source data.
- Any export path using unreviewed extraction values.

Needs John/engineering review:

- BOM or task linestring statuses before using them as CoilForge quote-review signals.
- Product/component detection semantics before connecting them to Direct Coil field values.
- Drawing-impacting exact matches before downstream drawing use.

## 7. Decision matrix structure

Each decision item includes:

- `field_key`
- `group`
- `canonical_path`
- `direct_coil_field`
- `comparison_category`
- `submittal_status`
- `ez_status`
- `selected_policy`
- `recommended_decision`
- `required_decision_owner`
- `drawing_impact`
- `direct_coil_impact`
- `quote_impact`
- `source_evidence_summary`
- `raw_text_excluded`

The implementation also includes `decision_tags`, `export_allowed`, and `pdf_export_enabled` per item so tests can prove safety state directly.

## 8. Field-level decision policies

- `exact_match`: may be `confirmed_for_review_not_engineering_approved`; never engineering approved.
- `submittal_only` / `ez_only`: remain `review_required_source_only`.
- `value_mismatch`: held for field-level review; no merged value selected.
- `unit_mismatch`: blocked until an explicit conversion rule is approved.
- `status_mismatch` / `evidence_mismatch`: review required.
- `blocked_mismatch`: blocked; no merged value selected.
- `missing_both`: visible as `review_required_missing_both`.
- Drawing-impacting fields: require John or engineering review before downstream drawing use.
- `export_allowed`: false.
- `pdf_export_enabled`: false.

## 9. Drawing-impacting decision items

Default sanitized matrix summary:

- Total Direct Coil fields: 52
- Drawing-impacting fields: 22
- Exact matches: 8
- Submittal-only fields: 4
- EZ-only fields: 6
- Missing-both fields: 34
- Unit mismatches: 0 in default fixture
- Export allowed: false

Drawing-impacting exact matches such as `rows_deep` and `finned_height` are still review-only because matching source values do not approve drawing semantics.

## 10. CD/BF/TF/CH status

The required drawing baseline fields remain visible in the matrix:

| Field | Category | Submittal status | EZ status | Policy | Drawing impact |
| --- | --- | --- | --- | --- | --- |
| `CD` | `ez_only` | `missing` | `review_required` | `review_required_source_only` | yes |
| `BF` | `ez_only` | `missing` | `review_required` | `review_required_source_only` | yes |
| `TF` | `ez_only` | `missing` | `review_required` | `review_required_source_only` | yes |
| `CH` | `ez_only` | `missing` | `review_required` | `review_required_source_only` | yes |

## 11. Remaining John/engineering review items

- Decide whether PO tag normalization should become an approved CoilForge intake rule.
- Decide whether product/component detection signals should influence Direct Coil field review categories.
- Decide whether any BOM/linestring logic belongs in CoilForge quote-review signals.
- Approve or reject drawing semantics for drawing-impacting exact matches.
- Define explicit conversion rules before any unit mismatch can be used.
- Decide how missing application-team/BTO logic should be sourced, if still needed.

## 12. Validation results

Validation run in this phase:

- `python -m pytest tests/test_phase2c_pos_logic_decision_workbench.py` - passed, 10 tests.
- `python -m compileall src` - passed.
- `python -m pytest` - passed, 174 tests, 1 FastAPI/Starlette deprecation warning.

Final git whitespace/staging checks are run during phase closeout before commit:

- `git diff --check`
- `git diff --cached --check`
- `git diff --cached --name-only`

## 13. Next recommended task

Phase 2C-M3 should add a John-facing review packet or local UI tab for the decision matrix, still with export disabled and without importing raw PO/PDF data.
