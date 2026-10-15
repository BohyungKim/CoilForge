# Handoff to the CCSI session — crosscheck × submittal page cache

This is from the submittal-index session (2026-09-30). **Nothing here has been applied.**
`scripts/ccsi_crosscheck.py` and `scripts/ccsi_coil_data_readiness.py` belong to the CCSI
session.

The patch is `ccsi_crosscheck_handoff.patch`, next to this file. It was generated from the
committed versions at `c44ca77`, and `git apply --check` passes. It needs `coilforge.corpus`
(this branch), so apply it **after** the branch is merged.

All numbers below come from the live ledger (opened read-only), the harvests in
`outputs/ccsi_harvest` (12 coils in 2954, 3031, 3154, 3183, 3232 and 3237), and cached
real PDFs. The run wrote nothing.

## 1. Bug — the whole-document candidate hides the first coil's values

`submittal_canonical_by_tag` iterates `[result.candidate, *result.cover_candidates]` with
`setdefault`. The whole-document candidate therefore claims the first tag. That candidate
has no per-coil detail block, so the first coil's canonical-path values come back empty.

| Project | First tag | Current code | Patched: `cover_candidates or [candidate]` |
|---|---|---|---|
| 2954 | CCWC-1 | fluid block `None` | Water / 100 / EWT 44 / LWT 54 / 16.1 GPM / 6.56 ft |
| 3154 | HHWC-1 | fluid block `None` | Water / 100 / 122 / 104 / 0.66 GPM |
| 3031 | PHWC-1 | fluid block `None` | Propylene Glycol 40 % / 115 / 95 / 12.2 GPM |
| 3232, 3237 | CDXC-1 | refrigerant `None` | evaporating 43 / liquid 77 / superheat 9 |
| 3183 | — | no cover candidates, so no change | |

The drawing workflow already uses `cover_candidates or [candidate]`
(`workflows/submittal_to_drawing.py`).

## 2. Pairing — pull canonical values from the SAME PDF the draft came from

`--submittal P=PDF` merges one PDF into **every** ledger coil of project P. That is only
correct when that PDF is the one the draft run read. It often isn't:

- **Newer uploads that aren't on disk.** 3183's two newest ledger uploads (2026-09-23 21:09
  and 21:24) are not in the PO tree. The newest *located* file is an earlier upload.
- **Several draft runs per project.** 2954 has two draft runs, each reading a different
  PDF (Rev3a and `SIGNED … Rev3-OXY-37861`).

What the patch changes:

- `load_coils` now carries `input_hash`, the sha1 of the draft's PDF.
- `merge_submittal(..., input_hash=)` merges only into coils drafted from that exact PDF.
- New flag `--submittal-from-ledger`: for each harvested project, the PDF is resolved with
  `coilforge.corpus.page_cache.cached_source_path(input_hash)`. If it can't be resolved,
  the coil is skipped with an explicit note; no other revision is borrowed in its place.
- A re-read costs about 1 s from the page cache; a live parse takes 0.5–13 min.

## 3. Decision for the CCSI session / John — which draft run to use

The readiness query picks the **latest draft-bearing run**. For 5 of the 6 harvested
projects, that run is a `deliverable_finalized` run. That run has **no PDF hash**, because
it is recorded without bytes, so same-PDF pairing can't find a PDF. Measured on the 9
canonical-path CCSI fields:

| Run selection | match | submittal_missing | mismatch | ccsi_blank | both_missing |
|---|---|---|---|---|---|
| current code (no merge) | 6 | 33 | 0 | 0 | 6 |
| patch, current run selection | 12 | 25 | 2 | 2 | 4 |
| **patch + latest draft run that read a PDF** | **29** | **5** | **5** | **6** | 0 |

The third row adds `and r.input_hash is not null` to both the outer and inner filters of
`_LATEST_DRAFT_RUNS`. With it, 5 of 6 projects pair; 3183 cannot, since neither of its
hash-bearing drafts is on disk. All 12 harvested coils still match a ledger coil.

The trade-off is that finalized drafts can carry John's manual fills, while intake drafts
are the machine's reading of the submittal. For a submittal-versus-CCSI check, the intake
draft is arguably the right side. **This change is not in the patch**; it's your call.

## 4. Mismatches this exposes (for `docs/ccsi/mapping_findings.md`)

- **`GlycolRatio`, CoilForge `100` vs CCSI `0`** — on 2954 CCWC-1 and CCWC-2 and on 3154
  HHWC-1 and HHWC-2.
  - The submittal states "Water 100 %". CoilForge files that as `fluid_percent = 100`,
    while CCSI's field is the *glycol* ratio.
  - This is a mapping-semantics gap, not an extraction error. It likely needs a
    `value_map` (`Water` → glycol 0) or a derived rule.
- **`EnteringFluidTemp`, 3154 HHWC-1: 122 vs 123** — a real 1 °F difference, worth checking
  against the page.

## 5. Tests worth adding (in `tests/test_ccsi_crosscheck.py`)

- `submittal_canonical_by_tag` takes values from the per-coil candidate when both the
  whole-document candidate and a cover candidate carry the same tag. Monkeypatch
  `intake_with_page_cache` to return that shape.
- `merge_submittal(..., input_hash=X)` leaves coils drafted from another PDF untouched.
- `merge_submittals_from_ledger` notes, and does not merge, a coil when its `input_hash` is
  `None`, and when the PDF is not located.

## 6. Notes

- **OCR.** Only the pdfplumber layer is cached; OCR results are not. 5 of the 8 PDFs checked
  have degraded pages. A process with an OpenAI key re-sends those pages each time, so for
  deterministic runs set `os.environ["OPENAI_API_KEY"] = ""` in-process.
- **`primaries.json`** is still the right lookup when there is no ledger run, such as when
  starting from a project number. Act only on rows with `"usable": true`.
