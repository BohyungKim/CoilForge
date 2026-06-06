# Phase 2B.13 Accuracy Harness

## One-line implementation result

Phase 2B.13 adds a regression harness that compares the sanitized submittal-to-drawing MVP workflow against a stable expected summary fixture.

## Files changed

- `src/coilforge/accuracy/__init__.py`
- `src/coilforge/accuracy/regression.py`
- `tests/fixtures/accuracy/submittal_to_drawing_expected.json`
- `tests/test_phase2b_accuracy_harness.py`
- `docs/PHASE2B_ACCURACY_HARNESS.md`
- `docs/PHASE2B_MVP_DEMO_RUNBOOK.md`

## Expected fixture format

The expected fixture is `tests/fixtures/accuracy/submittal_to_drawing_expected.json`.

It stores stable, sanitized summary fields only:

- Input policy flags.
- Candidate counts, tag, review status, and unmapped source keys.
- Canonical validation status, blocked fields, review-required count, and unmapped count.
- Direct Coil draft field count and ready/review-required/blocked/unmapped counts.
- Readiness report total fields, blocked keys, required missing keys, review-required keys, unmapped keys, and export status.
- SourceEvidence counts and field keys.
- Drawing preview status, DrawingIntent export/review state, SVG presence, review watermark presence, and selected metadata.
- Validation status and export-disabled policy.

The fixture intentionally excludes raw submittal text, raw PDF content, OCR text, full SVG body, customer/project source data, and private documents.

## Regression flow

The harness runs this path:

```text
sanitized submittal input
-> SubmittalCoilCandidate
-> CanonicalCoilRecord
-> DirectCoilInputDraft
-> ReadinessReport
-> DrawingIntent
-> SVG metadata / blocked preview response
-> Validation summary
```

`build_submittal_to_drawing_summary()` executes the default sanitized workflow and extracts a stable summary. `compare_accuracy_summary()` compares that summary to the expected fixture.

## Regression checks

The tests verify:

- Expected fixture loads and has the expected format version.
- Current sanitized workflow matches expected field counts.
- Blocked fields match expected keys.
- SourceEvidence exists without raw/private text.
- Drawing metadata or blocked preview response matches expected status.
- Export remains disabled and `not_implemented`.
- Full summary comparison returns a readable diff on mismatch.

## Current expected fixture summary

- Candidate count: `1`
- Direct Coil registry field count: `52`
- Ready fields: `0`
- Review-required fields: `12`
- Blocked fields: `4`
- Unmapped fields: `36`
- Required blocked drawing fields: `BF`, `CD`, `CH`, `TF`
- SourceEvidence fields: `12`
- Drawing preview: allowed with review-required metadata
- Review watermark: present when SVG is returned
- Export: disabled / `not_implemented`

## Mismatch behavior

On mismatch, the comparison returns path-specific rows such as:

```text
$.readiness_report.summary_counts.blocked: expected 99, actual 4
```

This keeps failures readable without dumping raw workflow payloads.

## Safety boundaries

- No PDF export.
- No Direct Coil final export.
- No OCR.
- No broad parser.
- No supplier integration.
- No raw data.
- No production drawing approval claim.

## Known limitations

- The fixture is scoped to the current sanitized DX Header 1 demo only.
- It checks summary stability, not pixel-perfect SVG geometry.
- It checks SourceEvidence presence and field keys, not raw source text.
- Manual UI override persistence is not part of this harness.

## Next recommended phase

Phase 2B.14 should add a controlled MVP review packet that packages the accuracy summary, readiness report, and demo observations for John/application team review while keeping export disabled.
