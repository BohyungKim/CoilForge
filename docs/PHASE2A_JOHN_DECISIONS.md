# Phase 2A John Decision Log

Status: Needs John review.

Created: 2026-06-05.

Scope: Decision capture document only. This file does not add features, modify app behavior, change renderer logic, change API contracts, update tests, or touch raw/source/output data.

## 1. Review Status

Phase 2A is technically ready for John review, based on `docs/PHASE2A_REVIEW_PACKET.md`.

Current review state:

- Technical implementation: validated for local review-aid workflow testing.
- Business/engineering approval: not approved yet.
- Drawing release status: remains `review_aid_only`.
- Generated SVG status: review aid only, not a manufacturing drawing.
- Phase 2B expansion: should not start until the items below are approved or explicitly deferred.

## 2. Decision Status Vocabulary

Use the statuses below when recording John decisions.

| Status | Meaning |
| --- | --- |
| Proposed | Current implementation or recommendation is ready for review but not approved. |
| Approved | John accepts the current behavior or wording for the next implementation phase. |
| Rejected | John does not accept the current behavior or wording; follow-up change is required. |
| Deferred | John intentionally postpones the decision; dependent work must keep current blockers or review-required wording. |

## 3. Decisions Required From John

John or engineering must decide:

1. Whether the first SVG layout is acceptable as a Phase 2A review-aid drawing surface.
2. Whether the current airflow direction display convention is acceptable.
3. Whether OAL should remain review-required or move to an approved derived rule in a later phase.
4. Whether right-panel labels, requiredness, and unknown/blocked behavior are acceptable.
5. Whether the review watermark and title block wording are acceptable.
6. Whether `generated_with_warnings` is acceptable for default Phase 2A rendering while OAL remains review-required.

## 4. Decision Table

| Decision item | Current status | Proposed decision | John decision | Impact if not reviewed | Follow-up implementation phase |
| --- | --- | --- | --- | --- | --- |
| SVG layout | Proposed | Approve the current fixed `0 0 1600 1200` review-aid layout as sufficient for Phase 2A review testing, with visual refinements allowed later. | Pending | Phase 2B drawing expansion may copy a layout that does not match John's expected Oxygen8/CoilMaster review standard. | Phase 2A review closeout, then Phase 2B renderer refinement if needed. |
| Airflow direction convention | Proposed | Keep `airflow_direction` explicit and display `left_to_right` as `left to right`; do not infer direction silently. | Pending | Future generated previews may show reversed or ambiguous orientation, and downstream cases could inherit the wrong convention. | Phase 2A review closeout; Phase 2B only after convention is approved or explicitly blocked. |
| OAL handling | Proposed | Keep OAL as `REVIEW REQUIRED`; do not generate OAL from an unapproved formula. | Pending | A future implementation could accidentally treat an inferred formula as product logic. | Phase 2A review closeout; later OAL rule phase only after John approval. |
| Right-panel wording and requiredness | Proposed | Keep source-backed/reviewed values only, show notes/warnings/blocked fields visibly, and avoid invented material or engineering values. | Pending | Missing or uncertain values could appear authoritative, weakening review traceability. | Phase 2B UI/renderer wording pass after John review. |
| Watermark and title block | Proposed | Keep `REVIEW AID - NOT FOR MANUFACTURING`, `release_status=review_aid_only`, and visible title metadata. | Pending | Generated drawings could be misunderstood as released manufacturing drawings. | Phase 2A review closeout; Phase 2B wording update if rejected. |
| Default warning behavior | Proposed | Allow `generated_with_warnings` for default render while OAL remains visibly review-required. | Pending | Reviewers may confuse a warning state with either a full failure or a fully approved drawing. | Phase 2A validation wording review; Phase 2B only if accepted or explicitly deferred. |

## 5. SVG Layout Review Notes

Current SVG behavior to review:

- Uses fixed `viewBox="0 0 1600 1200"`.
- Preserves text as SVG text rather than outlines.
- Includes stable zones: `zone.sheet_frame`, `zone.title_block`, `zone.front_view`, `zone.side_header_view`, `zone.right_panel`, `zone.bottom_dimension_table`, `zone.review_metadata`, and `markup.review`.
- Shows front view, side/header view, right review panel, bottom dimension table, and review metadata.
- Updates visible values from current UI state.
- Marks blocked validation cases with `GENERATION BLOCKED - REVIEW REQUIRED`.

John review notes to capture:

| Area | John notes | Decision status |
| --- | --- | --- |
| Overall layout proportions | Pending | Proposed |
| Front view geometry | Pending | Proposed |
| Side/header view placement | Pending | Proposed |
| Dimension table placement | Pending | Proposed |
| Right-panel placement | Pending | Proposed |
| Markup layer expectations | Pending | Proposed |

## 6. Airflow Direction Convention Decision

Current implementation:

- `airflow_direction` is an editable required field.
- Missing `airflow_direction` is blocked.
- `left_to_right` renders as `left to right`.
- Other airflow values render from the current state text.
- The renderer does not infer airflow silently.

Decision to record:

| Option | Decision status | Notes |
| --- | --- | --- |
| Approve current convention | Proposed | Use current display convention for Phase 2B expansion. |
| Reject and revise convention | Proposed | Requires renderer/UI wording change before expansion. |
| Defer | Proposed | Keep airflow explicit and review-required; do not expand orientation-sensitive cases as approved. |

## 7. OAL Review-Required Decision

Current implementation:

- OAL is not calculated.
- The renderer shows `OAL: REVIEW REQUIRED`.
- Validation warns by default that OAL is not generated.
- Explicit OAL generation requests are blocked.

Decision to record:

| Option | Decision status | Notes |
| --- | --- | --- |
| Continue blocking OAL generation | Proposed | Safest current Phase 2A path. |
| Approve a future OAL derived rule | Proposed | Requires separate reviewed formula, examples, tests, and traceability. |
| Defer | Proposed | Keep `REVIEW REQUIRED` visible and prevent formula implementation. |

## 8. Right-Panel Wording Decision

Current implementation:

- Right panel is labeled `Review panel`.
- Shows `ROWS`, `FPI`, `CIRCUITING`, `OAL: REVIEW REQUIRED`, notes, warnings, and blocked fields.
- Values are sourced from current Phase 2A state or explicit review metadata.
- It does not invent material, circuiting, dry weight, internal volume, connection, or manufacturing values.

Decision to record:

| Option | Decision status | Notes |
| --- | --- | --- |
| Approve current wording | Proposed | Use as Phase 2B baseline. |
| Revise labels/requiredness | Proposed | Requires a focused wording pass before expansion. |
| Defer | Proposed | Keep unknown/blocked/review-required behavior visible. |

## 9. Watermark And Title Block Decision

Current implementation:

- Header UI and SVG use `REVIEW AID - NOT FOR MANUFACTURING`.
- Renderer metadata uses `release_status=review_aid_only`.
- Title block includes current coil name, model number, category, header type, source case id, release status, and drawing status.
- Drawing metadata sets `john_review_required=true`.

Decision to record:

| Option | Decision status | Notes |
| --- | --- | --- |
| Approve current watermark/title block | Proposed | Keeps Phase 2A safety language as-is for expansion. |
| Revise wording | Proposed | Requires a wording-only follow-up before broader drawing use. |
| Defer | Proposed | Keep existing review-only language and do not imply manufacturing release. |

## 10. Follow-Up Implementation Phase Mapping

| Follow-up item | Trigger | Target phase | Allowed work after decision |
| --- | --- | --- | --- |
| SVG layout refinement | SVG layout rejected or marked needs changes. | Phase 2A follow-up or Phase 2B preflight. | Renderer/UI wording-only or layout-only update scoped to reviewed notes. |
| Airflow convention update | Current convention rejected. | Phase 2A follow-up before Phase 2B. | Update display convention and validation wording; add focused tests if behavior changes. |
| OAL rule implementation | John approves a specific OAL rule. | Separate OAL rule phase before production-like use. | Add explicit derived rule, examples, validation, and renderer update. |
| Right-panel wording update | Current wording rejected or revised. | Phase 2B wording pass. | Update labels/requiredness display; no invented values. |
| Watermark/title block update | Current wording rejected. | Phase 2A follow-up before broader sharing. | Wording-only safety update. |
| Phase 2B expansion | Review items approved or explicitly deferred. | Phase 2B. | Add additional locked DX cases only within approved boundaries. |

## 11. Decision Capture Template

Use this block after John review.

```text
Phase 2A John review date:
Reviewer:

SVG layout:
- Decision: Approved / Rejected / Deferred
- Notes:

Airflow direction convention:
- Decision: Approved / Rejected / Deferred
- Notes:

OAL handling:
- Decision: Approved / Rejected / Deferred
- Notes:

Right-panel wording:
- Decision: Approved / Rejected / Deferred
- Notes:

Watermark/title block:
- Decision: Approved / Rejected / Deferred
- Notes:

Default warning behavior:
- Decision: Approved / Rejected / Deferred
- Notes:

Phase 2B allowed to start:
- Decision: Yes / No / Yes with constraints
- Constraints:
```

## 12. Safety Notes

- This document does not approve generated drawings for manufacturing.
- This document does not approve OAL calculation.
- This document does not approve silent airflow inference.
- This document does not approve broader DX/Header/HGBP expansion.
- Raw `Case/`, `outputs/`, PDFs, spreadsheets, raw exports, rendered pages, customer/project source data, and `.env` files are out of scope for this decision capture task.
