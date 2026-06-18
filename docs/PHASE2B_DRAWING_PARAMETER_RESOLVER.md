# Phase 2B Drawing Parameter Resolver

Status: Phase 2B.7 preview policy baseline.

Scope: Direct Coil draft drawing parameter resolver only. This phase does not change the SVG renderer, implement PDF export, implement Direct Coil final export, add UI, parse PDFs/OCR, or approve production drawings.

## 1. One-Line Implementation Result

Phase 2B.7 adds a drawing parameter resolver that turns `DirectCoilInputDraft` drawing fields plus explicit manual/default preview values into a review-required `DrawingParameterSet` with separate `preview_allowed` and `export_allowed` flags.

## 2. Files Changed

- `src/coilforge/drawing/__init__.py`
- `src/coilforge/drawing/parameters.py`
- `tests/test_phase2b_drawing_parameter_resolver.py`
- `docs/PHASE2B_DRAWING_PARAMETER_RESOLVER.md`

## 3. Drawing Parameter Set Shape

`DrawingParameterSet` includes:

- `parameters`
- `preview_allowed`
- `export_allowed`
- `blocked_parameters`
- `review_required_parameters`
- `required_preview_parameters`
- `notes`

Each `DrawingParameter` includes:

- `key`
- `label`
- `value`
- `unit`
- `mode`
- `source_evidence`
- `status`
- `review_required`
- `blocked_reason`
- `manual_override`

Supported drawing parameters are `CD`, `I`, `S`, `O`, `R`, `BF`, `HD`, `HF`, `TF`, `RF`, `CH`, `SL`, and `ZD`.

## 4. Auto/Manual Behavior

Draft-provided values are treated as `auto` mode only as review-aid values. The resolver does not apply formulas or claim final engineering approval.

Manual values require explicit manual override metadata and remain `review_required` unless a future approved review workflow changes that state.

## 5. Default/Fixture Value Policy

Default preview values are allowed only when explicitly supplied as `sanitized_fixture/default`. The resolver creates source evidence for each default value and keeps the resulting parameter `review_required`, not `ready`.

## 6. Preview Allowed Vs Export Allowed

`preview_allowed` can be true only when all required preview drawing parameters are present with a non-blocked value. Current required preview parameters are `CD`, `BF`, `TF`, and `CH`.

`export_allowed` is always false in this phase.

## 7. Blocked Policy

Missing required drawing parameters remain blocked unless an explicit manual override or sanitized default preview value is supplied. Without manual/default values, `CD`, `BF`, `TF`, and `CH` remain blocked for the sanitized fixture.

## 8. Review-Required Policy

Manual and default preview values remain review-required. Draft values that are unreviewed, inferred, ambiguous, or already review-required remain review-required. John drawing semantics review remains pending.

## 9. Known Limitations

- No SVG renderer changes are included.
- No PDF export is implemented.
- No Direct Coil final export is implemented.
- No UI is added.
- No parser or OCR is implemented.
- No production drawing approval is claimed.
- OAL remains outside this drawing parameter set and must not be derived without a separately approved rule.

## 10. Remaining John Review Items

- Confirm whether `CD`, `BF`, `TF`, and `CH` are the correct required preview gate for this Direct Coil drawing baseline.
- Confirm whether sanitized default preview values are acceptable for review-aid rendering.
- Confirm manual override metadata requirements before any future drawing preview UI.
- Confirm Phase 2A watermark/title block wording before wider drawing use.

## 11. Next Recommended Phase

Recommended next phase: Phase 2B.8 drawing preview packet serialization.

Scope:

- Serialize `DrawingParameterSet` as a stable review packet.
- Keep SVG renderer changes, PDF export, Direct Coil final export, UI, parser/OCR, and production drawing approval out of scope.
