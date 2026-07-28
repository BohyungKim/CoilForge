# Phase 2E-M1 MVP Test Runbook + Metrics Pack

## 1. One-Line Purpose

Phase 2E-M1 prepares a controlled sanitized / real-style MVP test procedure for moving from sanitized submittal or POs-derived intake to Direct Coil draft, engineering adjustment review, drawing review, review packet generation, and metrics capture without running final export, PDF export, OCR, raw ingestion, quote finalization, or production drawing approval.

## 2. Test Purpose

Use this runbook to validate whether the current CoilForge MVP workflow is ready for an actual controlled test with John and engineering.

The test is a review aid only. It measures workflow completion, field coverage, drawing review clarity, adjustment handling, and time saved against a manual baseline. It does not approve engineering logic, release drawings, create a quote-ready package, or send data to any external system.

## 3. Supported Test Inputs

Supported inputs are limited to sanitized material:

- Existing sanitized demo case in `examples/sanitized/`.
- Sanitized real-style case prepared from customer-like source documents after removing customer names, job numbers, pricing, private notes, raw source text, and source attachments.
- Sanitized POs-derived intake summary when available through existing safe CoilForge POs review logic.

## 4. Prohibited Inputs

Do not use these inputs in Phase 2E-M1 or the actual MVP test unless a later approved phase explicitly changes this rule:

- raw PDFs
- raw customer data
- raw Excel exports
- raw quote documents
- unsanitized PO/source documents
- raw JSON/TXT exports from customer or project systems
- uploaded reference images containing customer or project data
- raw submittal PDFs
- raw PO/customer documents
- OCR output from raw documents

## 5. Pre-Test Validation

Run these commands before any actual MVP test session:

```powershell
python -m compileall src
python -m pytest
git status --short --branch
git diff --check
```

Confirm in the `git status --short --branch` output:

- The branch is `phase2a/local-web-mvp`.
- `outputs/` remains unstaged.
- Raw/private files are not staged.
- Any existing unrelated untracked files are identified and excluded from the test artifact set.

## 6. App Startup Steps

1. From the repository root, run the existing local web app command used for CoilForge Phase 2A/2B testing.
2. Open the local CoilForge web UI in a browser.
3. Confirm the page title or first screen identifies the Direct Coil draft workflow.
4. Confirm the review/export controls are visible but disabled where applicable.
5. Confirm no raw source document upload or OCR workflow is required for this test.

## 7. Browser / UI Check Steps

Before recording metrics, confirm:

- Sanitized demo or sanitized real-style case can be loaded.
- Candidate and draft panels render without console errors.
- Compatibility panel or review surface is available when EZ comparison data is available.
- Decision capture or review surface remains read-only.
- Export controls remain disabled.
- PDF export controls remain disabled.
- Direct Coil final export remains unavailable.
- Any drawing preview is visibly marked as a review aid.

## 8. Workflow Test Steps

Use one sanitized case at a time.

1. Record `test_case_id` and `source_type` in the metrics template.
2. Load the sanitized case.
3. If available, run the POs-based intake review path.
4. Generate or inspect the `SubmittalCoilCandidate`.
5. Generate or inspect the `CanonicalCoilRecord`.
6. Generate or inspect the `DirectCoilInputDraft`.
7. Review the Direct Coil readiness report.
8. If sanitized EZ JSON path is available, compare the submittal path against the EZ path.
9. Review the compatibility panel or compatibility packet.
10. Review the decision capture or decision matrix surface.
11. Apply one safe representative engineering adjustment if the current app or API supports it.
12. Confirm the adjustment remains review-required and `downstream_applied=false`.
13. Generate or inspect the `DrawingIntent`.
14. Generate the SVG preview when the current sanitized path allows it.
15. Confirm the watermark and review-aid status are visible.
16. Confirm CD/BF/TF/CH status is visible and not treated as production-approved drawing semantics.
17. Confirm all 22 drawing-impacting fields remain review-required or otherwise unresolved until reviewed.
18. Generate or inspect the review packet.
19. Fill `docs/templates/PHASE2E_MVP_TEST_METRICS_TEMPLATE.md`.
20. Summarize the session with `docs/templates/PHASE2E_MVP_TEST_REPORT_TEMPLATE.md`.

## 9. Drawing Review Snapshot

Capture this section during the test:

| Review item | Expected Phase 2E-M1 status | Observed status | Notes |
| --- | --- | --- | --- |
| Watermark visible | `REVIEW AID - NOT FOR MANUFACTURING` visible |  |  |
| Production approval not claimed | true |  |  |
| CD/BF/TF/CH status | review-required or blocked |  |  |
| Airflow convention status | review-required until confirmed |  |  |
| OAL policy status | review-required; no formula approved |  |  |
| Title block wording status | review-aid wording only |  |  |
| SVG metadata behavior | raw SVG excluded from review packet; metadata summarized |  |  |
| Drawing-impacting fields | 22 fields remain review-required until reviewed |  |  |

## 10. Manual Baseline Timing Method

Record manual baseline timing as elapsed minutes with start/end timestamps where possible:

| Baseline segment | Start | End | Minutes | Notes |
| --- | --- | --- | ---: | --- |
| Current manual process time (`current_manual_process_time`) |  |  |  | End-to-end manual path. |
| Application team selection time (`application_team_selection_time`) |  |  |  | Existing application selection work. |
| Engineering adjustment time (`engineering_adjustment_time`) |  |  |  | Manual review and adjustment work. |
| Drawing markup/EZ snapshot time (`drawing_markup/EZ snapshot time`) |  |  |  | Drawing or EZ snapshot preparation. |
| Quote prep time (`quote_prep_time`) |  |  |  | Quote-prep review and packaging. |

## 11. CoilForge-Assisted Timing Method

Record CoilForge-assisted timing as elapsed minutes with start/end timestamps:

| Assisted segment | Start | End | Minutes | Notes |
| --- | --- | --- | ---: | --- |
| Intake time (`intake time`) |  |  |  | Sanitized case load and intake review. |
| Review time (`review time`) |  |  |  | Candidate, canonical, draft, and readiness review. |
| Adjustment time (`adjustment time`) |  |  |  | One safe representative engineering adjustment if supported. |
| Drawing review time (`drawing review time`) |  |  |  | DrawingIntent, SVG preview, and drawing snapshot review. |
| Packet generation time (`packet generation time`) |  |  |  | Review packet and report preparation. |

## 12. Required Metrics

Capture these metrics for each case:

- `test_case_id`
- `source_type`
- `manual_baseline_time`
- `CoilForge_assisted_time`
- `estimated_time_saved`
- `total_fields`
- `ready_fields`
- `review_required_fields`
- `blocked_fields`
- `unmapped_fields`
- `exact_matches`
- `submittal_only_fields`
- `ez_only_fields`
- `conflicts`
- `POs_supported_fields`
- `POs_needs_review_fields`
- `engineering_adjustments`
- `manual_corrections`
- `drawing_issues`
- `CD_BF_TF_CH_status`
- `quote_prep_issues`
- `go_no_go_result`

## 13. Safety Invariants

These values must remain true throughout the MVP test:

- `export_allowed=false`
- `pdf_export_enabled=false`
- `direct_coil_final_export_available=false`
- `production_drawing_approval_claimed=false`
- review decisions do not apply downstream
- engineering adjustments remain review records only unless a later approved phase changes that behavior
- raw/private source text is not returned in review packets
- no final quote is created

If export, PDF export, final Direct Coil export, or production drawing approval becomes enabled, stop the test and record `NO-GO if export/approval accidentally enabled`.

## 14. Go / No-Go Criteria

Use one of these results:

| Result | Meaning | Required follow-up |
| --- | --- | --- |
| GO for continued MVP refinement | The sanitized workflow can be completed, safety invariants remain false/disabled, and blockers are understood. | Continue iterative MVP refinement. |
| GO with blockers | The workflow mostly completes but has specific review or field blockers. | Fix blockers before broader testing. |
| NO-GO until drawing review | Drawing snapshot, CD/BF/TF/CH, airflow, OAL, title block, or drawing-impacting fields are not reviewable enough. | John/engineering drawing review first. |
| NO-GO until source evidence improved | Required fields lack enough sanitized source evidence to evaluate the workflow. | Improve sanitized evidence and rerun. |
| NO-GO if export/approval accidentally enabled | Export, PDF export, Direct Coil final export, final quote, or production drawing approval became enabled or implied. | Stop and fix safety regression before any further test. |

## 15. Report-Back Format for ChatGPT / John Review

Use this format after an actual MVP test:

```text
One-Line Result:

Case Used:

Workflow Completed / Not Completed:

Timing Result:

Field Coverage Result:

Drawing Review Snapshot:

Engineering Adjustment Result:

Review Packet Result:

Safety Invariants:

Go / No-Go Recommendation:

Blockers:

Next Recommended Fixes:

John / Engineering Review Required:
```

## 16. Out of Scope

- Direct Coil final export
- PDF export
- OCR
- broad PDF parser
- supplier API/DLL integration
- quote finalization
- production drawing approval
- raw customer/project data ingestion
- raw PDF/Excel parsing
- active approval workflow
- approval persistence
- downstream behavior change from review decisions
- actual MVP test execution in Phase 2E-M1

## 17. Remaining John / Engineering Review Items

- CD/BF/TF/CH drawing semantics
- airflow convention
- OAL policy
- title block wording
- sanitized default preview value acceptability
- 22 drawing-impacting fields
- POs-supported field adoption
- future unit conversion approval
- BOM/linestring policy

## 18. Browser Eyeball Gate — 2026-07-28 UI/UX pass

Five workstreams landed together; four of them are JS, and this repo has no JS test runner.
The Python guards (`tests/test_condensing_mirror_fields.py`,
`tests/test_direct_coil_company_rules_vs_seeds.py`) pin the SOURCE shape and the rule table
against John's hand-filled seeds — they do NOT prove the rendered mirror is correct. These
manual checks are the real gate.

Run `run_server.bat` (port 8011). It has **no `--reload`**: restart it after any `src/` edit,
and re-analyze the PDF in the browser since `pdfCoilPages` is cached client-side.

### 18.1 Condensing (RHHGRC/HGRH) mirror

Analyze a submittal containing an RHHGRC coil, then confirm on the condensing mirror:

- [ ] Header Material / Header Wall Schedule / Connection Material / Connection Type /
      Casing Material / Casing Style / Connection Ends / Coil Coating populate with the
      amber review-required edge — no longer "unmapped".
- [ ] Face Velocity(FPM) shows a computed value.
- [ ] **Condensing Temperature shows the CONDENSING value, not the liquid temperature.**
      (This was the wrong-value bug — check it against the submittal by hand once.)
- [ ] The 7 HGRH review defaults appear: Saturated Suction 45, Suction Temp at Compressor 68,
      Vapor 140, Condensing 115, Subcooling 18, Supply/Return Connection Size "Calculate".
- [ ] **Masking check (highest risk):** on a submittal that DOES state a condensing
      temperature, the extracted value wins over the 115 default. If 115 appears where the
      submittal said something else, the defaults were hoisted above the fallbackMap.
- [ ] System Type and Separate Subcooling Tubes High / Circuits read `unmapped` — these are
      not derivable and must never be guessed.
- [ ] No drain-pan value and no DX distributor value appears anywhere on this mirror.

### 18.2 Leaving DB/WB highlight

- [ ] On DX, condensing and water mirrors, Leaving Dry Bulb and Leaving Wet Bulb carry the
      accent bar + bold, and the eye lands on them without hunting.
- [ ] Check in BOTH light and dark theme.
- [ ] The DX mirror shows Leaving Wet Bulb exactly ONCE (it moved out of the calculated panel).
- [ ] On a reheat coil with no leaving WB, the row reads plain `unmapped` with NO accent — a
      highlighted empty box would be a failure.

### 18.3 Removed sections

- [ ] "Project Review — Exceptions First" and "Audit CCSI Export" are gone from the review flow.
- [ ] Browser console is clean (no missing-element errors from removed listeners).
- [ ] The Ambient panel's coil cards are still styled correctly — it reuses the
      `.ccsi-audit-coil/-badge/-table/-note` classes the removed section seeded.
- [ ] In Ambient supplier mode, the Coil Checklist Auto-Fill section is still HIDDEN.

### 18.4 Drawing Notes in the CCSI payload

- [ ] Copy the CCSI payload; the JSON has a top-level `drawing_notes` with the assembled text.
- [ ] `fields[]` still contains exactly the 13 base params (+ any multi-header keys) —
      the notes must NOT have become a 14th dimension field.

### 18.5 Ambient quote-request PDF

In Ambient supplier mode, "Generate package from submittal":

- [ ] The "Export quote request PDF" button is disabled until a package renders.
- [ ] Switch to "Compare two files" — the button must NOT be visible there.
- [ ] Export, then open the PDF: cover page, then per coil its performance page(s) followed by
      its drawing page.
- [ ] Every page carries the REVIEW AID band, including drawing pages.
- [ ] A value the submittal did not state renders as `-`, never as 0 or N/A. A stated 0 still
      shows 0.
- [ ] Degree and superscript-two render in the unit labels; no stray middle dots (that is the
      base-14 font substituting for an em dash).
