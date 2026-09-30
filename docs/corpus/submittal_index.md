# Submittal PDF index + page-text cache

Review aid. Finds the real submittal PDFs **without downloading** them. Caches the
slow pdfplumber page extraction so a submittal's canonical values re-derive in about a
second instead of 2–4 minutes.

Code: `src/coilforge/corpus/` (`fs`, `submittal_index`, `ledger_link`, `page_cache`).
Built 2026-09-30 in a parallel session. The plan went through two plan-review rounds and
an invariant-guard audit.

## Where things live

All data is **outside the repo**, because it names customer projects and holds raw
submittal text:

`COILFORGE_SUBMITTAL_INDEX_DIR`, or by default `~/CoilForgeData/submittal_index/`.

| File | What |
|---|---|
| `index.json` | every PDF under the PO tree and the extra roots — metadata only |
| `primaries.json` | each project's primary submittal: path, reason, provisional flag, rejected files |
| `assignments.json` | John's explicit picks (`--assign`), pinned by sha1 |
| `pages/<sha1>.json` | cached page text and tables for one PDF |
| `runs/<utc>.jsonl` | one event per file per batch run |

The capture ledger is opened **read-only** (`mode=ro`), at `COILFORGE_CAPTURE_DB` or
`~/CoilForgeData/capture/coilforge.sqlite3`. Its path is never a command-line argument.

## Run

```
python scripts/build_submittal_index.py                  # ~30 s, no download
python scripts/pre_extract_submittals.py --ledger-matches --project 3232 --dry-run
python scripts/pre_extract_submittals.py --assign 3232="C:\...\file.pdf" --dry-run
python scripts/pre_extract_submittals.py --ledger-matches --project 3232   # after John approves
```

`--dry-run` hashes local files only. It prints the per-project primary table and the
download and time estimate, then writes `primaries.json`. The real run downloads
cloud-only files **one at a time**. It extracts each file in its own worker process
(default 4 workers, 20 min timeout per file).

## Rules worth knowing

- **Index every PDF, not just "submittal" names.** Signed copies are often named
  `<number> - <project>.pdf` (3232).
- **Project number.**
  - In the PO tree it is the project folder's leading token.
  - Filename numbers count only when a whole ` - ` segment is exactly 4 digits. So a date,
    an 8-digit rep number, or a `SIGNED 2954` segment is never read as a project number.
  - A folder and filename that disagree give `NUMBER_CONFLICT`, e.g. a `2955 - …` file in
    the 2954 folder.
- **Revision key.**
  - It is read from the **stem** only. On the full name, `.pdf` was read as the revision
    letter, so `Rev1.pdf` ranked above `Rev1a.pdf`.
  - `RevS*`, a bare As built and two different Rev tokens give no key.
- **Primary selection (John, 2026-09-30).** The rules apply in this order:
  0. `--assign`
  1. Ledger match — the exact file CoilForge saw. If there are several, the latest
     `ts_utc` wins.
  2. Signed Final Submittal
  3. Final Working
- **Rules 2 and 3 are fail-closed.**
  - Only files that are Oxygen8-named, not archived, have a parseable Rev, are not
    as-built and have no number conflict are eligible.
  - Anything else gets a reason code (`SIGNED_FINAL_UNRECOGNIZED`, `REVISION_AMBIGUOUS`,
    `ARCHIVED_HIGHER_REV`, …) and no pick.
  - A Signed Final folder with no eligible file does **not** fall through to Final
    Working.
- **Ledger matching.**
  - Candidates are found by upload-name hash or byte size. The name hash mirrors
    `web/app.js::sanitizeHeaderValue`, and the raw name is also tried for the case path.
  - A candidate counts only when its sha1 matches. A size-only match is never extracted.
- **The cache holds page text only.**
  - Candidates and canonical values are rebuilt from it with the **current** intake code.
    So intake fixes and rule edits never make it stale.
  - `extractor_fingerprint` does make it stale. It hashes the pdfplumber and pdfminer
    versions plus the three extractor functions.
- **PyPDF2 fallback results are never cached.** Those come from pdfplumber raising,
  e.g. with a MemoryError under load, and they have no tables.
- **OCR is not cached on disk.** A consumer with an OpenAI key re-sends degraded pages
  in every new process. For deterministic results, run with the key blank **in-process**:
  `os.environ["OPENAI_API_KEY"] = ""`. Do not use PowerShell `$env:…=""`, which deletes
  the variable so `.env` reloads the key.

## Consumer API

```python
from coilforge.corpus.page_cache import intake_with_page_cache
cached = intake_with_page_cache(pdf_path)       # -> CachedIntake(result, sha1, cache_status)
coils = cached.result.cover_candidates or [cached.result.candidate]
```

`cache_status` is one of `HIT`, `MISS_PARSED`, `STALE_REPARSED`, `CORRUPT_REPARSED` or
`ENGINE_FALLBACK`.

To go from a project number to a path, read `primaries.json` and act **only** on rows
with `"usable": true`. A row is not usable in any of these cases:

- it is fail-closed;
- it is provisional: an unconfirmed ledger candidate, an assignment not re-verified this
  run, or a primary that changed after John approved the table;
- it has no pick.

When two project folders share a number, Signed Final and Final Working are fail-closed
(`DUPLICATE_FOLDER_NUMBER`). A ledger match is still used there, because it is the exact
file CoilForge saw.

To pair a ledger run with its own PDF, use `cached_source_path(run.input_hash)`, not
"the project's latest file". The CCSI crosscheck migration is in
`ccsi_crosscheck_handoff.md` and `ccsi_crosscheck_handoff.patch`.
