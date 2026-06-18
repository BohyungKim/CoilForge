# Phase 1 Merged Conflict Matrix

Status: Phase 1 merged review artifact.

Created: 2026-06-05.

Conflict statuses:

- `JOHN_REVIEW_REQUIRED`: Needs John or engineering decision before implementation.
- `PHASE2_BLOCKER`: Blocks Phase 2 implementation for the affected feature or bucket.
- `SAFE_TO_DEFER`: Outside the recommended Phase 2 MVP or safe to document for later.

## Matrix

| ID | Conflict area | Phase 1A evidence | Phase 1B model/checklist | Phase 1C drawing spec | Phase 1D contract | Status | Merged handling |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C-001 | Stale dependency notes | Phase 1A outputs now exist. | Some docs say Phase 1A was absent when drafted. | Some docs say Phase 1A was absent when drafted. | References Phase 1A as future dependency. | `SAFE_TO_DEFER` | Merged spec uses current repo state and treats stale notes as historical context only. |
| C-002 | Phase 1B availability drift | Not applicable. | Schema files and docs now exist. | Phase 1C references Phase 1B as future. | Some Phase 1D docs say Phase 1B schema files were not present. | `SAFE_TO_DEFER` | Use current Phase 1B schema paths during Phase 2 planning. |
| C-003 | DX same-name connection fields | `Geometry.I/S/O/R/SL` repeatedly mismatch PDF labels; `Geometry.Headers[]` is stronger. | Drawing dimensions list same-name candidates as placeholders. | Labels require `I/S/O/R/SL` and suffix variants. | Validation must check drawing bindings. | `PHASE2_BLOCKER` | MVP must bind DX connection offsets through `Geometry.Headers[]` or block the label. |
| C-004 | DX `HD2` / `HDx1` source | Phase 1A shows suffix labels map to header-array entries, not always same-name `Geometry.HD2`. | Header item fields include `header_dimension_hd`, but label aliases are not finalized. | `HD1`, `HD2`, `HDx1` are required label variants. | Field bindings need drawing element IDs and canonical keys. | `JOHN_REVIEW_REQUIRED` | Preserve suffix aliases and source paths; do not collapse suffixes until reviewed. |
| C-005 | `OAL` source | `Geometry.OAL` is mismatched or zero in old-schema cases; DX observed formula is `Geometry.CL + Geometry.RB2`. | `OAL` is a derived drawing dimension placeholder. | `OAL` is MVP-required label. | Derived rules need rule IDs and validation. | `JOHN_REVIEW_REQUIRED` | Treat DX OAL as derived candidate; block active use until John approves formula. |
| C-006 | `HF` / `RF` meaning | Phase 1A maps some cases to `Geometry.LEP` or `Geometry.REP` with medium confidence. | Listed as derived dimensions. | `HF` and `RF` are common MVP labels. | Validation requires source or derived rule. | `JOHN_REVIEW_REQUIRED` | Include labels but require source path/confidence in output; review before approving meaning. |
| C-007 | HGBP versus ASC | Phase 1A says EZC-0013 follows DX Header 1 pattern and preserves ASC flags. | Phase 1B recommends `source_feature = ASC` and normalized HGBP. | Phase 1C asks whether HGBP is visible. | Phase 1D requires preserving source/normalized distinction. | `JOHN_REVIEW_REQUIRED` | Metadata preservation is required; visible drawing display needs John decision. |
| C-008 | DX Header 4 | No reference case. | Header enum includes Header 4. | DX Header 4 marked missing. | Validation supports unsupported bucket reporting. | `PHASE2_BLOCKER` | Header 4 must be rejected or blocked in Phase 2 MVP. |
| C-009 | HGRH Single Feed versus Single Connection | Phase 1A and Phase 0C preserve the distinction. | `header_type` and `feed_type` are separate fields. | HGRH Single Connection remains missing. | Phase 1D repeats Single Feed is not Single Connection. | `SAFE_TO_DEFER` | Not in DX MVP; must remain a blocker for future HGRH implementation. |
| C-010 | HGRH header/stubout dimensions | HGRH JSON lacks `Geometry.Headers`; note tokens exist only in EZC-0002 and EZC-0010. | HGRH header details need John-confirmed classification. | HGRH labels are required for future HGRH templates. | Validation must mark missing mappings blocked. | `SAFE_TO_DEFER` | Defer HGRH from Phase 2 MVP. |
| C-011 | HHWC missing header arrays | Phase 1A shows HHWC lacks populated `Geometry.Headers[]`. | Header fields exist but source is incomplete. | HWC Header 1 is covered but water-coil template is later. | Validation should block missing mappings. | `SAFE_TO_DEFER` | Defer HWC from Phase 2 MVP. |
| C-012 | Broad checklist versus small MVP | Phase 1A supports many drawing fields, but not every future workflow field. | Checklist draft includes broad required/optional fields. | Drawing spec lists many MVP-required labels. | Contract expects checklist, canonical, drawing, validation, and export metadata. | `JOHN_REVIEW_REQUIRED` | Use DX-focused required subset in `docs/PHASE2_MVP_SCOPE.md`; John should approve before build. |
| C-013 | Airflow arrow source | Not established by Phase 1A mapping. | `coil_hand` is required; `airflow_direction` is future. | `AIRFLOW` label/arrow is required, but orientation is uncertain. | Drawing validation should warn/block unknown orientation. | `JOHN_REVIEW_REQUIRED` | Require explicit reviewed `airflow_direction` or visible validation warning in MVP. |
| C-014 | Review status vocabulary | Phase 1A has mapping statuses/confidence. | Traceable fields use `source_observed`, `ai_inferred`, `john_confirmed`, etc. | Drawing output needs review watermark and metadata. | Workflow review statuses include `accepted`, `edited`, `needs_john_review`, etc. | `JOHN_REVIEW_REQUIRED` | Build a status mapping layer; do not flatten statuses to a single boolean. |
| C-015 | PDF export priority | Not applicable. | Not a schema blocker. | SVG first; PDF secondary. | JSON package can include drawing outputs. | `SAFE_TO_DEFER` | Keep PDF optional until SVG visual validation passes. |
| C-016 | Manufacturing approval language | Not applicable. | Validation state includes drawing release status. | Drawing must be review aid only. | Import/export/validation must not approve drawings. | `PHASE2_BLOCKER` | MVP must include review watermark and non-approved release status. |
| C-017 | Right-panel values | Phase 1A focuses dimension mappings, not every right-panel source value. | Some material/performance fields are optional or code-table dependent. | Right-panel labels are MVP-required drawing labels. | Validation requires provenance and unresolved values. | `JOHN_REVIEW_REQUIRED` | Support right-panel labels, but values must be source-backed/reviewed or explicitly blocked. |
| C-018 | Raw numeric code normalization | Not resolved by Phase 1A. | Phase 1B flags lookup-table risk. | Drawing labels need human-readable materials/specs. | JSON export should preserve raw and normalized values. | `SAFE_TO_DEFER` | Preserve raw codes/source text; defer lookup-table normalization unless needed for DX MVP label display. |
| C-019 | JSON import/export scope | Phase 1A can feed future drawing binding validation. | Schemas are draft. | SVG package metadata should be export-friendly. | Full workflow package is designed but not implemented. | `SAFE_TO_DEFER` | Emit metadata compatible with future export; full import/export adapter can be later. |
| C-020 | Generated drawing trigger | Phase 1A provides candidates, not approved rules. | Canonical snapshot is intended source of truth. | Drawing template is design only. | Drawing generation should happen from canonical snapshot. | `PHASE2_BLOCKER` | Phase 2 must not generate directly from raw JSON without reviewed canonical/checklist binding. |

## Phase 2 Blockers Summary

- Do not use top-level same-name `Geometry.I/S/O/R/SL` as DX drawing offsets.
- Do not implement DX Header 4.
- Do not emit drawings without review-aid-only status.
- Do not generate from raw JSON directly without checklist/canonical provenance.

## John Review Required Summary

- DX OAL formula approval.
- Header/connection suffix semantics.
- HGBP visibility policy.
- HF/RF source meaning.
- Airflow direction policy.
- DX MVP required checklist subset.
- Review-status vocabulary mapping.
- Right-panel value policy.

## Safe To Defer Summary

- Historical stale dependency notes.
- HGRH implementation.
- CWC/HWC implementation.
- PDF export.
- Raw numeric lookup normalization beyond source preservation.
- Full JSON import/export adapter.
