# CoilForge Phase 1 Decision Log

Status: Phase 1 merged review decision log.

Created: 2026-06-05.

This log records merged Phase 1 decisions and open decisions for John review. It is not an implementation approval.

## Decision Status Vocabulary

- `MERGED_DECISION`: Adopted for the Phase 1 merged spec.
- `JOHN_REVIEW_REQUIRED`: Needs John or engineering decision before implementation.
- `PHASE2_BLOCKER`: Blocks the affected Phase 2 feature or bucket.
- `SAFE_TO_DEFER`: Documented but does not block the recommended Phase 2 MVP.

## Decisions

| ID | Status | Decision | Evidence | Implementation impact |
| --- | --- | --- | --- | --- |
| D-001 | `MERGED_DECISION` | Current Phase 1A outputs supersede older Phase 1B/1C notes that said Phase 1A files were absent. | `outputs/phase1a_json_drawing_linkage` now contains mapping CSVs and a review packet. | Future implementation should use Phase 1A linkage evidence instead of stale dependency assumptions. |
| D-002 | `MERGED_DECISION` | Current Phase 1B schema files supersede Phase 1D notes that said final Phase 1B files were not present. | `schemas/canonical_coil_model.schema.json`, `schemas/checklist_schema_draft.json`, and Phase 1B docs exist. | Phase 1D import/export contracts should align to current canonical/checklist paths during implementation. |
| D-003 | `MERGED_DECISION` | Phase 2 MVP should be DX-only. | Locked DX references cover Header 1, Header 2, Header 3, and HGBP/ASC. | Reduces first implementation risk and avoids unresolved HGRH/water-coil layout rules. |
| D-004 | `MERGED_DECISION` | Phase 2 MVP should include DX Header 1, DX Header 2, DX Header 3, and DX HGBP/ASC. | Phase 0C and Phase 1A cover EZC-0001, EZC-0003, EZC-0009, EZC-0011, EZC-0007, and EZC-0013. | The MVP can be validated against known locked reference cases. |
| D-005 | `PHASE2_BLOCKER` | DX Header 4 must remain out of scope. | Phase 0C marks DX Header 4 missing/uncertain. | Do not implement Header 4 generation until a reference case or John-approved rule exists. |
| D-006 | `MERGED_DECISION` | `FH`, `FL`, `CH`, `CL`, `CD`, `TF`, `BF`, and `RB` can be treated as DX MVP direct-mapping candidates when source trace and review state are preserved. | Phase 1A reports strong direct mappings for old-schema DX cases. | These can be first-pass drawing bindings, subject to validation. |
| D-007 | `PHASE2_BLOCKER` | Top-level same-name `Geometry.I/S/O/R/SL` fields must not be used as drawing-label sources for DX connection offsets. | Phase 1A found repeated mismatches and stronger header-array mappings. | MVP implementation must bind these labels to `Geometry.Headers[]` evidence or block the label. |
| D-008 | `JOHN_REVIEW_REQUIRED` | DX `OAL` should be treated as a derived candidate, not a direct source field. | Phase 1A found `Geometry.OAL` mismatches and observed `Geometry.CL + Geometry.RB2` for DX. | John/engineering must approve the formula before generated drawings use it as an active rule. |
| D-009 | `JOHN_REVIEW_REQUIRED` | `HDx1`, `HD2`, `SL*`, and `I/S/O/R` suffix semantics need review. | Phase 1A links many suffix labels to `Geometry.Headers[]`, but label numbering semantics are not formally approved. | Preserve label aliases and source paths; do not silently normalize suffixes away. |
| D-010 | `MERGED_DECISION` | EZC-0013 must preserve source `ASC` and normalized `HGBP`. | Phase 0C John review confirmed internal HGBP normalization while preserving source evidence. | Canonical/checklist/export payloads need both `source_feature` and `normalized_special_feature`. |
| D-011 | `JOHN_REVIEW_REQUIRED` | HGBP display policy is undecided. | Phase 1C asks whether HGBP should be visible on drawings, metadata-only, or note-based. | MVP can preserve metadata first; visible label requires John decision. |
| D-012 | `JOHN_REVIEW_REQUIRED` | Airflow direction must not be inferred from model suffix or category alone. | Phase 1C notes airflow arrows are visible but source rule and mirroring are not confirmed. | MVP should require explicit reviewed `airflow_direction` or render a visible validation warning. |
| D-013 | `MERGED_DECISION` | SVG is the primary MVP drawing artifact. | Phase 1C recommends simple 2D SVG with stable IDs and searchable text. | Phase 2 implementation should generate SVG first. |
| D-014 | `SAFE_TO_DEFER` | PDF export is secondary and optional for MVP. | Phase 1C output strategy says PDF follows SVG visual validation. | Do not block Phase 2 MVP on PDF unless John changes priority. |
| D-015 | `MERGED_DECISION` | JSON import/export is a core architecture requirement, but not the first drawing renderer deliverable. | Phase 1D defines workflow package envelope and repeatability rules. | Phase 2 MVP should emit metadata compatible with future export, but full import/export adapter can be phased. |
| D-016 | `PHASE2_BLOCKER` | Generated drawings must not auto-approve manufacturing release. | AGENTS.md, Phase 1C, and Phase 1D all preserve review-aid-only status. | MVP output must include review watermark and release status metadata. |
| D-017 | `SAFE_TO_DEFER` | HGRH drawing generation is deferred from Phase 2 MVP. | HGRH JSON lacks exposed `Geometry.Headers`; note-token coverage is incomplete. | Keep HGRH in future phase after mapping and visual review. |
| D-018 | `SAFE_TO_DEFER` | CWC/HWC drawing generation is deferred from Phase 2 MVP. | Water-coil references exist but are not the recommended first MVP. | Keep water-coil rules out of first implementation. |
| D-019 | `JOHN_REVIEW_REQUIRED` | Required checklist field subset for DX MVP needs final approval. | Phase 1B draft is broad; Phase 2 should stay small. | Use `docs/PHASE2_MVP_SCOPE.md` as the recommended subset. |
| D-020 | `JOHN_REVIEW_REQUIRED` | Review-status vocabulary mapping must be explicit. | Phase 1B uses traceable field statuses; Phase 1D uses workflow review statuses. | Implementation needs a mapping layer instead of flattening statuses. |

## Open John Decisions Before Phase 2 Build

1. Approve the DX-only MVP scope.
2. Approve or reject the DX OAL derived rule.
3. Confirm suffix-label semantics for header and connection dimensions.
4. Confirm airflow direction input/review policy.
5. Confirm HGBP drawing visibility policy.
6. Confirm Phase 2 required checklist field subset.
7. Confirm PDF export priority.
8. Confirm review watermark/title block wording.

## Deferred Decisions

- HGRH header/stubout mapping for cases without explicit note tokens.
- HGRH Single Connection support.
- HGRH Header 3 and Header 4 support.
- CWC/HWC generalized water-coil template support.
- Raw numeric code lookup tables for materials, tube type, casing type, connection type, and fluid type.
- Full JSON import/export adapter behavior.
- Production approval/release workflow.
