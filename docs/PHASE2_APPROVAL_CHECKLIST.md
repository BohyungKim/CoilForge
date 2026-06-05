# Phase 2 MVP Approval Decision Table

Phase 2 implementation should not start until the decision items below are reviewed.

This approval gate is planning only. It does not implement the drawing populator, does not approve generated drawings for manufacturing, and does not approve selection calculations.

## Decision Status Vocabulary

| Status | Meaning |
| --- | --- |
| `APPROVED` | Approved for the scoped Phase 2 implementation path. |
| `APPROVED_WITH_CONSTRAINTS` | Approved only within the listed constraints. |
| `DEFERRED` | Not part of the immediate implementation slice. |
| `NEEDS_ENGINEERING_REVIEW` | Requires John or engineering review before the affected rule can be treated as approved. |
| `BLOCKED` | Blocks implementation until resolved. |

## Phase 2 Approval Gate

| Decision Item | Recommended Decision | John Decision | Status | Implementation Consequence | Blocker? | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| DX-only MVP scope | Approved. | Approved. | `APPROVED` | Phase 2 stays inside DX workflows and rejects HGRH, CWC, HWC, and DX Header 4. | No | Preserve the DX-only boundary from Phase 1. |
| First implementation slice | DX Header 1 / EZC-0001 only. | Approved unless John later changes it. | `APPROVED_WITH_CONSTRAINTS` | Phase 2A implementation must start with only the DX Header 1 / EZC-0001 vertical slice. | No | DX Header 2, DX Header 3, and DX HGBP remain expansion targets after Phase 2A review. |
| MVP delivery mode | Local interactive web app, not static-only file generation. | Approved. | `APPROVED` | Phase 2A should provide a local browser UI where John can edit parameters and inspect output. | No | Command-line SVG generation alone is not sufficient for the MVP. |
| Drawing behavior | Parameter edits update an Oxygen8-style SVG drawing preview. | Approved. | `APPROVED` | The renderer should support live or near-live preview updates from current UI values. | No | Generated drawings remain review aids only. |
| Checklist behavior | Checklist snapshot and drawing generation happen together. | Approved. | `APPROVED` | The UI should preserve the current checklist state, canonical model snapshot, drawing metadata, and validation state as one workflow package surface. | No | Full JSON import/export remains future-compatible, not required as a complete adapter in Phase 2A. |
| OAL derived formula | Do not actively generate from formula until John approves. | Pending. | `NEEDS_ENGINEERING_REVIEW` | OAL should be blocked or shown with a warning until approved. | Yes for OAL generation | Observed candidate `Geometry.CL + Geometry.RB2` is not approved product logic. |
| HD/SL/I/S/O/R suffix semantics | Preserve exact label aliases and source paths. Do not normalize semantics yet. | Pending. | `NEEDS_ENGINEERING_REVIEW` | First slice may display source-backed labels, but generalization is blocked. | Yes for generalized suffix rules | Use `Geometry.Headers[]` source paths where supported; do not use misleading same-name top-level offsets. |
| HGBP/ASC drawing visibility | Preserve `source_feature=ASC` and `normalized_special_feature=HGBP`. For first MVP, show in metadata/notes only. | Pending unless already confirmed separately. | `NEEDS_ENGINEERING_REVIEW` | HGBP visible drawing treatment is deferred from Phase 2A. | No for Phase 2A | Relevant to later DX HGBP expansion, not DX Header 1 / EZC-0001. |
| airflow_direction | Required reviewed checklist input. Do not infer silently. | Pending. | `NEEDS_ENGINEERING_REVIEW` | Missing airflow direction should block generation or produce a visible validation warning. | Yes if missing or inferred | Phase 2A UI should expose this as an explicit field. |
| Right-panel requiredness | Source-backed values only. Missing values should be unknown/blocked, not invented. | Pending. | `NEEDS_ENGINEERING_REVIEW` | Right-panel values may render only from reviewed input, source evidence, or explicit unknown/blocked status. | Yes for invented values | Do not fabricate material, circuiting, dry weight, internal volume, or connection values. |
| PDF export | Defer until SVG preview is visually validated. | Pending. | `DEFERRED` | Phase 2A should not spend implementation capacity on PDF export. | No | SVG preview is the primary review artifact. |
| Review watermark/title block | Use `REVIEW AID - NOT FOR MANUFACTURING` and `release_status=review_aid_only`. | Pending. | `NEEDS_ENGINEERING_REVIEW` | Phase 2A output should carry review-only language and must not imply manufacturing release. | Yes for release wording | Existing safety boundary already requires review-aid-only drawings. |

## Build Approval Summary

Phase 2A may proceed only as a local interactive web MVP for DX Header 1 / EZC-0001 after John accepts the pending review items or accepts the documented blockers/warnings for the first slice.

Do not begin Phase 2B expansion until Phase 2A output is reviewed.
