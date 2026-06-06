# Phase 2B Workflow Orchestrator

Status: Phase 2B.10 backend workflow orchestration.

Scope: backend API routes and workflow wiring only. This phase does not implement UI, Direct Coil final export, PDF export, OCR, broad PDF parsing, supplier integration, or raw data changes.

## 1. One-Line Implementation Result

Phase 2B.10 adds backend workflow orchestration for sanitized submittal intake to Direct Coil draft readiness and drawing preview output.

## 2. Files Changed

- `src/coilforge/workflows/__init__.py`
- `src/coilforge/workflows/submittal_to_drawing.py`
- `src/coilforge/web_app.py`
- `tests/test_phase2b_workflow_orchestrator.py`
- `docs/PHASE2B_WORKFLOW_ORCHESTRATOR.md`

## 3. Workflow Flow

The direct draft workflow runs:

```text
sanitized submittal input
-> SubmittalCoilCandidate
-> CanonicalCoilRecord
-> DirectCoilInputDraft
-> DirectCoilReadinessReport
```

The drawing workflow adds:

```text
DirectCoilInputDraft
-> DrawingParameterSet
-> DrawingIntent
-> Phase 2A SVG review-aid renderer
```

## 4. API Routes

- `GET /api/workflow/default-demo`
- `POST /api/workflow/submittal-to-direct-draft`
- `POST /api/workflow/submittal-to-drawing`

## 5. Response Shape

`submittal-to-direct-draft` returns candidates, selected candidate summary, canonical summary, `DirectCoilInputDraft`, readiness report, and validation metadata.

`submittal-to-drawing` returns the same workflow data plus drawing parameter set, `DrawingIntent`, SVG string, renderer metadata, and preview validation metadata.

## 6. Validation Behavior

The workflow preserves review-required, blocked, and unmapped states from each phase. Direct Coil export remains `not_implemented`; drawing preview is review-aid only.

When preview defaults are not provided, missing required drawing parameters `CD`, `BF`, `TF`, and `CH` block SVG preview. When explicit sanitized preview defaults are provided, preview can be generated while remaining review-required.

## 7. SourceEvidence Behavior

Source evidence from sanitized intake is preserved through candidate, canonical, Direct Coil draft, readiness report, and drawing intent source evidence summaries.

## 8. Drawing Preview Behavior

SVG preview uses the existing Phase 2A renderer. The review watermark remains visible and metadata continues to report review-aid status.

## 9. Export Blocked Policy

No final Direct Coil export or PDF export is implemented. The workflow returns export metadata only, with export status remaining blocked or not implemented.

## 10. Known Limitations

- No UI is implemented.
- No broad PDF parser is implemented.
- No OCR is implemented.
- No supplier integration is implemented.
- No raw data ingestion is implemented.
- No production drawing approval is claimed.
- Current demo input is sanitized text only.

## 11. Next Recommended Phase

Recommended next phase: Phase 2B.11 local review packet serialization.

Scope:

- Serialize workflow outputs into a stable local JSON/markdown review packet.
- Keep UI, Direct Coil final export, PDF export, OCR, broad PDF parser, supplier integration, and raw data out of scope.
