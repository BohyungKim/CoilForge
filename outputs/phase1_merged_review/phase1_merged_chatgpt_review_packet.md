# Phase 1 Merged ChatGPT Review Packet

Run date: 2026-06-05.

## One-Line Result

Merged Phase 1A, 1B, 1C, and 1D into a DX-focused Phase 1 specification and recommended a small Phase 2 MVP without building the drawing populator.

## Files Inspected

- `AGENTS.md`
- `docs/REFERENCE_CASE_SET.md`
- `docs/CANONICAL_COIL_MODEL.md`
- `docs/CHECKLIST_SCHEMA.md`
- `docs/DRAWING_LABEL_DICTIONARY.md`
- `docs/DRAWING_TEMPLATE_SPEC.md`
- `docs/CHECKLIST_WORKFLOW.md`
- `docs/JSON_IMPORT_EXPORT_CONTRACT.md`
- `docs/VALIDATION_CONTRACT.md`
- `outputs/phase0_reference_lock/locked_reference_case_set.csv`
- `outputs/phase0_reference_lock/john_review_decisions.md`
- `outputs/phase0_reference_lock/phase0c_chatgpt_review_packet.md`
- `outputs/phase1a_json_drawing_linkage/phase1a_chatgpt_review_packet.md`
- `outputs/phase1a_json_drawing_linkage/category_mapping_summary.md`
- `outputs/phase1a_json_drawing_linkage/direct_matches.csv`
- `outputs/phase1a_json_drawing_linkage/derived_or_uncertain_mappings.csv`
- `outputs/phase1a_json_drawing_linkage/json_to_drawing_mapping_candidates.csv`
- `outputs/phase1b_model_design/phase1b_chatgpt_review_packet.md`
- `outputs/phase1c_drawing_spec/phase1c_chatgpt_review_packet.md`
- `outputs/phase1c_drawing_spec/template_requirements_by_category.md`
- `outputs/phase1c_drawing_spec/drawing_output_strategy.md`
- `outputs/phase1d_contract/checklist_to_drawing_workflow.md`
- `outputs/phase1d_contract/phase1d_chatgpt_review_packet.md`
- `schemas/canonical_coil_model.schema.json`
- `schemas/checklist_schema_draft.json`

## Files Created

- `docs/PHASE1_MERGED_SPEC.md`
- `docs/PHASE1_DECISION_LOG.md`
- `docs/PHASE2_MVP_SCOPE.md`
- `outputs/phase1_merged_review/phase1_merged_chatgpt_review_packet.md`
- `outputs/phase1_merged_review/phase1_conflict_matrix.md`

## Key Merged Decisions

- Use current Phase 1A outputs as active evidence, despite stale notes in older Phase 1B/1C docs saying Phase 1A was absent.
- Use current Phase 1B canonical/checklist schema files as active schema drafts, despite stale Phase 1D notes saying final Phase 1B files were absent.
- Recommend Phase 2 MVP as DX-only: DX Header 1, DX Header 2, DX Header 3, and DX HGBP/ASC.
- Keep DX Header 4 out of scope until a reference case or approved rule exists.
- Treat `FH`, `FL`, `CH`, `CL`, `CD`, `TF`, `BF`, and `RB` as DX direct-mapping candidates when source trace and review state are preserved.
- Bind DX `I/S/O/R/SL/HD` suffix labels through `Geometry.Headers[]` evidence, not top-level same-name fields.
- Treat DX `OAL` as a derived candidate, not a direct source field.
- Preserve EZC-0013 source `ASC` separately from normalized `HGBP`.
- Make SVG the primary MVP drawing artifact; PDF remains optional after SVG validation.
- Keep every generated drawing as a review aid with no manufacturing approval.

## Conflicts Requiring John Review

- Whether the observed DX `OAL = Geometry.CL + Geometry.RB2` formula may be used in MVP drawing output.
- Exact suffix semantics for `HDx1`, `HD2`, `SL*`, and `I/S/O/R` variants.
- Whether HGBP should be visible on the drawing, metadata-only, or notes-based.
- Whether `airflow_direction` must be explicit checklist input before generation.
- Which right-panel values are required versus allowed to be blank/blocked in the first MVP.
- How Phase 1B traceable-field statuses map to Phase 1D workflow review statuses.
- Whether PDF export is required in first MVP or deferred.
- Review watermark/title block wording.

## Phase 2 Blockers

- DX Header 4 generation.
- Any renderer that reads top-level same-name `Geometry.I/S/O/R/SL` as DX drawing offsets.
- Active `OAL` generation before John approves the derived formula.
- Drawing output without review-aid-only status.
- Raw JSON-to-SVG generation without checklist/canonical provenance.

## Recommended Phase 2 MVP

Build a DX drawing populator MVP for locked DX reference cases:

- DX Header 1: EZC-0001, EZC-0003, EZC-0009.
- DX Header 2: EZC-0011.
- DX Header 3: EZC-0007.
- DX HGBP/ASC: EZC-0013.

The MVP should generate review-aid SVG packages only, with stable IDs, metadata, validation output, and a visible non-manufacturing watermark. PDF export should remain optional.

## Validation Performed

Commands/results:

- Required input/output existence check: passed.
- Phase 1A output files exist: passed.
- Phase 1B output/schema files exist: passed.
- Phase 1C output files exist: passed.
- Phase 1D output files exist: passed.
- Merged spec exists: passed.
- Decision log exists: passed.
- Phase 2 MVP scope exists: passed.
- ChatGPT review packet exists: passed.
- Conflict matrix exists: passed.
- `rg -n "[ \t]+$"` across the five new Markdown files: no matches.
- `schemas/canonical_coil_model.schema.json` JSON parse: passed.
- `schemas/checklist_schema_draft.json` JSON parse: passed.
- Phase 1A row counts: `json_to_drawing_mapping_candidates.csv` = 575, `direct_matches.csv` = 272, `derived_or_uncertain_mappings.csv` = 303.

Repository note:

- `git status` is not available because `C:\Users\JohnKim\Desktop\Bins\Projects\CoilForge` is not currently a git repository.

## Notion-Ready Update Block

Status: Needs John Review.

Summary: Phase 1 merged review is documented. Recommended Phase 2 MVP is DX-only drawing populator for locked DX Header 1/2/3 and DX HGBP/ASC reference cases. DX Header 4, HGRH, CWC, and HWC are deferred. Main John review items are OAL formula approval, suffix-label semantics, airflow policy, HGBP visibility, right-panel requiredness, status vocabulary mapping, PDF priority, and review watermark wording.

Evidence: Phase 1A-1D outputs, current schemas, merged spec, decision log, Phase 2 MVP scope, and conflict matrix.

Next action: John reviews the Phase 1 merged decision log and approves or revises Phase 2 MVP scope before implementation.

## Next Codex Task Prompt Recommendation

```text
You are working on CoilForge Phase 2 MVP approval prep.

Objective:
Prepare an implementation-ready approval packet for the DX-only MVP based on docs/PHASE1_MERGED_SPEC.md, docs/PHASE1_DECISION_LOG.md, docs/PHASE2_MVP_SCOPE.md, and outputs/phase1_merged_review/phase1_conflict_matrix.md.

Do not build the drawing populator yet.

Scope:
- Convert John review items into a concise approval checklist.
- Define the exact first implementation slice for DX Header 1 only.
- Identify the minimal source files, schema fields, and validation checks needed.
- Preserve all raw JSON/PDF and review-aid-only boundaries.

Out of scope:
- Renderer implementation.
- Raw JSON/PDF edits.
- DX Header 4.
- HGRH/CWC/HWC.
- Production approval.

Report back with:
1. One-line result
2. Approval checklist
3. Proposed first implementation slice
4. Files to inspect
5. Files to modify
6. Acceptance criteria
7. Validation command
8. John review required
```
