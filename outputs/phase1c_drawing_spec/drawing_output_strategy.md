# Phase 1C Drawing Output Strategy

Status: Phase 1C draft for engineering review.

Created: 2026-06-05.

Scope: SVG/PDF strategy for the future CoilForge drawing populator. This document is not an implementation plan approval and does not create any drawing output.

## Strategy Summary

Use simple 2D SVG as the canonical generated drawing artifact for the MVP. Treat PDF as a secondary export view after SVG layout, label mapping, and visual review are validated.

Generated drawings must always be labeled as engineering review aids until formally approved. They are not automatically released manufacturing drawings.

## Inputs To Future Renderer

The future renderer should consume a reviewed canonical payload, not raw EZ Coil JSON directly.

Minimum renderer input groups:

- Sheet/title metadata.
- Category classification: DX, HGRH, CWC, HWC.
- Header type, feed type, and special feature.
- Dimension label values and review states.
- Material/specification panel values.
- Circuiting values.
- Connection/header/distributor features.
- Notes and callouts.
- Airflow direction and hand/orientation data.
- Source evidence references and confidence/review status.

Raw JSON/PDF files remain reference inputs and must not be modified.

## SVG As Canonical Review Artifact

SVG should be first because it is:

- Text-searchable.
- Diffable enough for development review.
- Easy to inspect in browser tooling.
- Layerable for markup.
- Suitable for stable object IDs.
- Good for simple 2D linework without CAD complexity.

Recommended SVG package:

- `drawing.svg`
- `drawing.metadata.json`
- Optional `drawing.review_notes.json`
- Optional exported `drawing.pdf`

Recommended SVG conventions:

- Fixed root viewBox, proposed `0 0 1600 1200`.
- CSS class names for all major layers.
- Stable IDs for labels and geometry.
- Data attributes for source field, normalized field, confidence, and review state.
- Visible review watermark.
- No hidden manufacturing approval state.

## PDF Export Strategy

PDF export should be future or optional MVP, depending on feasibility after SVG is validated.

Recommended PDF path:

- MVP default: no PDF required until SVG is visually accepted.
- MVP optional: browser-render SVG to PDF with review watermark.
- Future: deterministic PDF export with preserved vector text, page size controls, and package metadata.

PDF export acceptance requirements:

- Visual match to SVG within review tolerance.
- Searchable text where feasible.
- Review watermark visible.
- No loss of title block, notes, or dimension labels.
- No implication that PDF is a released manufacturing drawing.

## Markup Readiness

The output package should allow John/engineering to mark up both layout and data issues:

- Every label should have a stable ID.
- Every category-specific feature should have a stable ID.
- Reviewers should be able to point to `label.SL2.top_header_view` or similar objects.
- SVG should include a reserved `markup` layer.
- PDF should leave adequate visual whitespace around notes/title blocks.
- Metadata should list unresolved assumptions and review-required items.
- Export filenames should include review status, for example `review-draft`, not `released`.

## Validation Strategy For Future Implementation

Phase 1C validation is file/content validation only. Future implementation should add:

- Required label presence checks by category.
- Required zone presence checks.
- No-overlap checks for critical labels.
- Airflow arrow direction checks.
- Missing-value checks.
- Source provenance checks for every populated label.
- Image/PDF visual regression checks against selected reference cases.

Validation must distinguish:

- Source evidence present.
- Normalized field present.
- Derived field present.
- Review-required field present.
- Missing field.
- Unsupported bucket.

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Airflow orientation is misinterpreted. | Drawing could mislead review. | Store airflow direction explicitly and require John visual review. |
| Header location is inferred from category. | Wrong connection geometry. | Require header/connection data and review status. |
| Phase 1A mappings are absent. | Dimension code meanings remain uncertain. | Treat label dictionary as vocabulary until Phase 1A completes. |
| PDF export differs from SVG. | Markup/review confusion. | Validate SVG first and treat PDF as secondary. |
| Generated labels imply approval. | Process/safety issue. | Use visible review watermark and separate approval workflow. |
| Small-coil labels overlap. | Poor review usability. | Add collision checks or render review warnings in MVP. |

## Recommended Gating

Do not implement a drawing populator until:

- Phase 1A label/value linkage exists or dependency is explicitly waived.
- Phase 1B canonical/checklist fields are aligned with drawing labels.
- Phase 1D import/export contract agrees on drawing review states.
- John visually reviews Phase 1C orientation and template assumptions.
- Phase 1 merged review resolves conflicts across workstreams.
