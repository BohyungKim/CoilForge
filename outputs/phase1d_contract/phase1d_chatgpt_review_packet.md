# Phase 1D ChatGPT Review Packet

## One-Line Result

CoilForge Phase 1D now has a design-only checklist workflow, JSON import/export contract, and validation status contract for future Direct Coil checklist-to-drawing workflows.

## Files Inspected

- `docs/PLAN.md`
- `docs/IMPLEMENTATION.md`
- `docs/REFERENCE_CASE_SET.md`
- `docs/PHASE1_PARALLEL_EXECUTION_PLAN.md`
- `outputs/phase0_reference_lock/locked_reference_case_set.csv`
- `outputs/phase0_reference_lock/john_review_decisions.md`
- `outputs/phase0_reference_lock/phase0c_chatgpt_review_packet.md`
- `outputs/phase1b_model_design` directory

## Files Created

- `docs/CHECKLIST_WORKFLOW.md`
- `docs/JSON_IMPORT_EXPORT_CONTRACT.md`
- `docs/VALIDATION_CONTRACT.md`
- `outputs/phase1d_contract/checklist_to_drawing_workflow.md`
- `outputs/phase1d_contract/phase1d_chatgpt_review_packet.md`

## 1. Proposed Checklist Workflow

The proposed workflow is:

```text
Manual checklist entry
Excel checklist import
Submittal PDF extracted checklist draft
    -> checklist draft
    -> engineer review / edit
    -> reviewed checklist snapshot
    -> canonical model generation
    -> canonical model snapshot
    -> drawing generation trigger
    -> generated drawing review aid + checklist snapshot
    -> validation report
    -> JSON export
    -> JSON import
    -> revalidation
    -> future Direct Coil workflow comparison
```

Manual entry, Excel import, and future PDF extraction all produce the same checklist draft structure. Engineer review is required before canonical model generation. Drawing generation should happen from a canonical model snapshot, not directly from raw checklist inputs.

Checklist and drawing generation should eventually happen together from the same reviewed snapshot so generated drawings, checklist outputs, validation reports, and JSON exports all reference the same source state.

## 2. JSON Import / Export Structure

The draft JSON package envelope is:

```json
{
  "schema_name": "coilforge.direct_coil.workflow_package",
  "schema_version": "0.1-phase1d-draft",
  "payload_kind": "export",
  "package_id": "pkg_example",
  "workflow_id": "wf_example",
  "created_at": "2026-06-05T00:00:00Z",
  "created_by": "coilforge",
  "source_context": {},
  "checklist": {},
  "canonical_model": {},
  "drawing_generation": {},
  "validation_report": {},
  "review": {},
  "compatibility": {}
}
```

The contract preserves:

- Source context.
- Checklist snapshot.
- Canonical model snapshot.
- Drawing generation metadata.
- Drawing field bindings.
- Validation report metadata.
- Review status.
- Compatibility warnings and unsupported fields.

Import should mark payloads as requiring revalidation and must not auto-approve checklist fields or drawings.

## 3. Validation Statuses

Field validation statuses:

- `unchecked`
- `pass`
- `warn`
- `fail`
- `blocked`
- `not_applicable`

Workflow validation statuses:

- `not_started`
- `pass`
- `pass_with_warnings`
- `fail`
- `blocked`
- `stale`

Review statuses:

- `unreviewed`
- `accepted`
- `edited`
- `rejected`
- `unknown`
- `not_applicable`
- `needs_john_review`

Drawing statuses:

- `not_generated`
- `generated_review_aid`
- `generated_with_warnings`
- `generation_blocked`
- `rejected_after_review`
- `engineer_reviewed`

Validation is evidence only. It does not approve drawings for manufacturing release.

## 4. Future Submittal PDF Extractor Interface

The future extractor should return a checklist draft, not a canonical model or approved drawing input. Each extracted candidate should include:

- Source PDF id.
- Extractor version.
- Field key.
- Raw extracted value.
- Parsed value and unit.
- Source citation, such as page, region, text snippet, or rule id.
- Confidence metadata.
- Extraction warnings.
- `review_status = unreviewed`.

Extraction confidence is separate from validation. Even high-confidence extracted values require engineer review before canonical model generation.

## 5. Direct Coil Workflow Integration

The Direct Coil workflow should use:

- Checklist as the input/review layer.
- Canonical Coil Model as the normalized source of truth.
- Drawing generator as a review-aid producer.
- Validation report as an evidence layer.
- JSON import/export as the repeatability and comparison layer.

Future comparison should support current package vs historical Phase 0C reference case, imported package vs current contract, and generated drawing bindings vs Phase 1A mapping rules when available.

Known Phase 0C constraints must be preserved:

- HGRH header type and feed type are separate.
- Single Feed is not Single Connection.
- DX Header 4 is missing or uncertain.
- HGRH Single Connection is missing or uncertain.
- HGRH Header 3 and Header 4 are missing or uncertain.
- EZC-0013 source evidence is ASC, while normalized `special_feature` is HGBP.

## 6. Risks

- Phase 1B canonical model draft was not available as a file at inspection time, so field names and section names are placeholders.
- Phase 1A label mappings are required before drawing-label validation can be fully specified.
- Drawing generation gating needs John review, especially whether warnings allow generation.
- Historical EZ Coil / CoilMaster JSON may not round-trip cleanly without explicit unsupported-field handling.
- Approval vocabulary must avoid implying manufacturing release.
- Future PDF extraction can create false confidence if extraction confidence is confused with engineering validation.

## 7. Questions For John

- Should every required field be explicitly engineer-reviewed before drawing generation, or can accepted imported/manual values proceed once validation passes?
- Should drawings be allowed to generate with warnings if warnings are clearly attached to the drawing package?
- What exact status should CoilForge use for a drawing that is reviewed but not released?
- Should JSON import support checklist-only drafts first, or should it require full workflow packages in Phase 1 implementation?
- How strict should round-trip expectations be for historical EZ Coil / CoilMaster JSON?
- Which Direct Coil checklist fields should be required before the first Phase 1C drawing populator MVP?

## Compatibility Notes

- Phase 1B final canonical field names remain open.
- Phase 1C drawing package names and template identifiers remain open.
- Phase 1A label linkage rules are needed before label-level validation can move from blocked to active.

## Validation Performed

Performed after file creation:

- Confirmed all five required Phase 1D files exist.
- Confirmed required workflow topics are present in the generated documents.
- Confirmed JSON package envelope fields and revalidation language are present.
- Confirmed validation statuses and drawing review-aid status language are present.
- Checked the five new Markdown files for trailing whitespace; no matches were found.
- `git status` could not be used because this folder is not currently a git repository.
- No raw JSON or PDF files were intentionally modified; this cannot be independently diff-verified without git state.
