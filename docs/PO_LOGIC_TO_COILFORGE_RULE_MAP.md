# PO Logic to CoilForge Rule Map

## One-line implementation result

POs logic is mapped into CoilForge as review-only rule summaries and field-decision policies; no raw PO data, raw PDF text, OCR, parser behavior, export, or final field approval is enabled.

## Source locations inspected

Safe sibling source locations:

- `C:\Users\JohnKim\Desktop\Bins\Projects\PO Release Engineering Workflow\pdf_extractor\pdf_processing.py`
- `C:\Users\JohnKim\Desktop\Bins\Projects\PO Release Engineering Workflow\pdf_extractor\bom_ordering_rules.py`
- `C:\Users\JohnKim\Desktop\Bins\Projects\PO Release Engineering Workflow\pdf_extractor\EXTRACTION_CONTRACT.md`
- `C:\Users\JohnKim\Desktop\Bins\Projects\PO Release Engineering Workflow\pdf_extractor\PROJECT_CONTEXT.md`

Skipped:

- raw PDFs
- Excel exports
- raw JSON/TXT exports
- customer/project source folders
- generated reports/logs
- SQLite memory stores
- `Case/`
- `outputs/`
- venv/site-packages

## Rule map

| POs logic | Source area | CoilForge category | Classification | CoilForge use |
| --- | --- | --- | --- | --- |
| Unit tag normalization | `pdf_processing.py` | `submittal_identity_rules` | `reusable_now` | Candidate identity cleanup only; raw values excluded. |
| Cover table product detection | `pdf_processing.py` | `source_field_detection` | `reusable_with_sanitization` | Future sanitized signal for product type review. |
| Component/coil detection | `pdf_processing.py` | `component_classification` | `reusable_with_sanitization` | Future review categorization only. |
| BOM linestring decisions | `bom_ordering_rules.py` | `quote_or_bom_review_signal` | `needs_john_review` | Possible quote/BOM review signal, not drawing logic. |
| PDF extraction pipeline | `pdf_processing.py` | `out_of_scope_source_parser` | `not_safe_for_coilforge` | Do not import or enable in Phase 2C-M2. |
| Review-before-export gate | `EXTRACTION_CONTRACT.md`, `PROJECT_CONTEXT.md` | `review_gate_policy` | `reusable_now` | Preserve human review before downstream use. |
| Application-team selection | not found | `source_intake_gap` | `not_found` | No CoilForge behavior added. |
| BTO selection workflow | not found | `source_intake_gap` | `not_found` | No CoilForge behavior added. |

## Classification definitions

- `reusable_now`: deterministic governance or normalization rule that can be represented without raw data.
- `reusable_with_sanitization`: candidate logic that needs sanitized fixtures and John review before behavior changes.
- `needs_john_review`: business/process logic that may be useful but should not be assumed as CoilForge policy.
- `not_safe_for_coilforge`: requires raw/private source data, parser activation, OCR, export, or production workflow behavior.
- `not_found`: requested logic was not found in safe inspected files.

## Decision policy map

| Compatibility category | Policy | Owner | Export |
| --- | --- | --- | --- |
| `exact_match` | Confirmed for review only, not engineering approved. | John; engineering for drawing-impacting fields | disabled |
| `submittal_only` | Source-only review required. | John or engineering | disabled |
| `ez_only` | Source-only review required. | John or engineering | disabled |
| `value_mismatch` | Hold for field-level review; no merged value. | John or engineering | disabled |
| `unit_mismatch` | Block until explicit conversion rule is approved. | engineering | disabled |
| `status_mismatch` | Review required. | John or engineering | disabled |
| `evidence_mismatch` | Review required. | John or engineering | disabled |
| `blocked_mismatch` | Block; no merged value. | John or engineering | disabled |
| `missing_both` | Keep visible and request source/entry decision. | John | disabled |
| `drawing_impacting` | Review drawing semantics before downstream use. | John or engineering | disabled |

## Drawing-impacting fields

Drawing-impacting fields include Direct Coil drawing parameters plus core drawing summary fields such as:

- `header_type`
- `airflow_direction`
- `finned_height`
- `finned_length`
- `rows_deep`
- `fins_per_inch`
- `tubes_high`
- `coil_hand`
- `return_connection_size`
- Direct drawing parameters including `CD`, `BF`, `TF`, and `CH`

## Safety conclusions

- Raw/private source text is excluded from rule summaries and matrix items.
- Exact matches are not engineering approval.
- Source-only values stay review-required.
- Unit mismatches are blocked without an explicit conversion rule.
- Drawing-impacting values stay review-required before downstream drawing use.
- Direct Coil final export remains unavailable.
- PDF export remains disabled.
