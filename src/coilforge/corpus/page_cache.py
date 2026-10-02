"""On-disk cache of the slow pdfplumber page extraction, keyed by the PDF's sha1.

Why this layer and not candidate/canonical snapshots: ~all of a 2-4 minute parse is
``pdf_intake._extract_text_pages_from_pdf_bytes_uncached`` walking CoilMaster drawing
vectors, and that output depends ONLY on the bytes and the extractor code. Everything
above it (candidates, canonical, engine rules) re-derives in about a second, so intake
fixes and rule edits never stale this cache. ``extractor_fingerprint`` does: it hashes
the pdfplumber/pdfminer versions plus the source of the three extractor functions.

A record is ``<data>/pages/<sha1>.json`` = ``{header, pages}``. The page payload goes
through stdlib ``json`` with ASCII escaping because pdfminer can emit lone surrogates,
which Pydantic refuses; only the header is a Pydantic model. A PyPDF2-fallback result
(pdfplumber raised, e.g. MemoryError under load) is never cached -- it has no tables.

``intake_with_page_cache`` primes ``pdf_intake``'s in-process page memo from the record
and then calls the REAL ``extract_coil_candidate_from_pdf_bytes``, so a consumer's
output (OCR behaviour included) is exactly what a live parse gives.

The memo write goes through the public seam ``pdf_intake.prime_text_pages_cache``. Two
reads of ``pdf_intake`` privates remain, both pinned by
``test_pdf_intake_internals_the_cache_relies_on``: rebuilding ``_TextPage`` in
``_pages_from_payload`` and reading the extractor functions' source in
``extractor_fingerprint``.
"""
from __future__ import annotations

import functools
import hashlib
import inspect
import json
import multiprocessing
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from coilforge.corpus.fs import atomic_write_text, default_data_dir, long_path, read_pdf_bytes
from coilforge.submittal import pdf_intake
from coilforge.submittal.pdf_intake import PdfCoilIntakeResult

SCHEMA_VERSION = 1
PAGES_DIRNAME = "pages"
_FINGERPRINTED_FUNCTIONS = ("_extract_text_pages_from_pdf_bytes_uncached", "_clean_cell", "_clean_line")

# Worker exit codes (the child reports ONLY this; it writes its own record).
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_ENGINE_FALLBACK = 3
EXIT_SHA1_CHANGED = 4

LookupStatus = Literal["HIT", "MISSING", "STALE", "CORRUPT"]
CacheStatus = Literal["HIT", "MISS_PARSED", "STALE_REPARSED", "CORRUPT_REPARSED", "ENGINE_FALLBACK"]


class PageCacheHeader(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    sha1: str
    byte_size: int
    engine: Literal["pdfplumber"]
    extractor_fingerprint: str
    page_count: int
    text_chars: int
    extracted_at: str
    duration_s: float
    first_seen_path: str | None = None


@functools.lru_cache(maxsize=1)
def extractor_fingerprint() -> str:
    import pdfminer
    import pdfplumber

    parts = [f"pdfplumber={pdfplumber.__version__}", f"pdfminer={pdfminer.__version__}"]
    # _TextPage is deliberately NOT hashed: a layout change already fails the rebuild in
    # _pages_from_payload (-> CORRUPT -> reparse) and is pinned by the internals test.
    for name in _FINGERPRINTED_FUNCTIONS:
        parts.append(inspect.getsource(getattr(pdf_intake, name)).replace("\r\n", "\n"))
    return hashlib.sha256("\n\x00".join(parts).encode("utf-8")).hexdigest()


def pages_path(data_dir: str | os.PathLike[str], sha1: str) -> Path:
    return Path(data_dir) / PAGES_DIRNAME / f"{sha1}.json"


def _pages_payload(pages: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "page_number": page.page_number,
            "text": page.text,
            "tables": [[list(row) for row in table] for table in page.tables],
        }
        for page in pages
    ]


def _pages_from_payload(payload: Any) -> list[Any]:
    """Rebuild ``pdf_intake._TextPage`` objects, checking the structure strictly."""
    if not isinstance(payload, list):
        raise TypeError("pages is not a list")
    rebuilt = []
    for page in payload:
        number, text, tables = page["page_number"], page["text"], page["tables"]
        if not isinstance(number, int) or not isinstance(text, str) or not isinstance(tables, list):
            raise TypeError("malformed page")
        table_tuple = tuple(
            tuple(tuple(_require_str(cell) for cell in row) for row in table) for table in tables
        )
        rebuilt.append(pdf_intake._TextPage(page_number=number, text=text, tables=table_tuple))
    return rebuilt


def _require_str(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("table cell is not a string")
    return value


def build_page_record(
    pdf_bytes: bytes, source_path: str | None = None
) -> tuple[PageCacheHeader, list[Any]] | None:
    """Run the real page extraction; ``None`` when it fell back to PyPDF2."""
    started = time.perf_counter()
    pages, engine = pdf_intake.extract_text_pages_from_pdf_bytes(pdf_bytes)
    if engine != "pdfplumber":
        return None
    header = PageCacheHeader(
        sha1=hashlib.sha1(pdf_bytes).hexdigest(),
        byte_size=len(pdf_bytes),
        engine="pdfplumber",
        extractor_fingerprint=extractor_fingerprint(),
        page_count=len(pages),
        text_chars=sum(len(page.text) for page in pages),
        extracted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        duration_s=round(time.perf_counter() - started, 3),
        first_seen_path=source_path,
    )
    return header, list(pages)


def read_page_record(
    data_dir: str | os.PathLike[str], sha1: str
) -> tuple[LookupStatus, PageCacheHeader | None, list[Any] | None]:
    target = long_path(pages_path(data_dir, sha1))
    if not os.path.exists(target):
        return "MISSING", None, None
    try:
        with open(target, encoding="utf-8") as handle:
            raw = json.load(handle)
        header = PageCacheHeader.model_validate(raw["header"])
        pages = _pages_from_payload(raw["pages"])
    except (OSError, ValueError, KeyError, TypeError, ValidationError):
        return "CORRUPT", None, None
    if header.sha1 != sha1 or header.page_count != len(pages):
        return "CORRUPT", None, None
    if header.extractor_fingerprint != extractor_fingerprint():
        return "STALE", header, None
    return "HIT", header, pages


def write_page_record(
    data_dir: str | os.PathLike[str], header: PageCacheHeader, pages: list[Any]
) -> None:
    """Atomic write. A refused replace counts as done ONLY when the existing record
    already has this sha1 AND the current fingerprint -- a stale/corrupt record that
    cannot be replaced is a failure, never silently kept."""
    text = json.dumps({"header": header.model_dump(), "pages": _pages_payload(pages)}, ensure_ascii=True)
    try:
        atomic_write_text(pages_path(data_dir, header.sha1), text)
    except OSError:
        status, _, _ = read_page_record(data_dir, header.sha1)
        if status == "HIT":
            return
        raise


def cached_source_path(sha1: str, data_dir: str | os.PathLike[str] | None = None) -> str | None:
    """Where the PDF with this sha1 was read from, if its pages are cached and current.

    Lets a consumer pair a ledger run (``run.input_hash``) with the SAME PDF instead of
    "the project's latest file": the ledger stores no paths, and a project's newest
    upload may not be on disk at all (3183: its last two uploads are not in the PO tree).
    """
    directory = Path(data_dir) if data_dir is not None else default_data_dir()
    status, header, _ = read_page_record(directory, sha1)
    if status != "HIT" or header is None or not header.first_seen_path:
        return None
    return header.first_seen_path if os.path.exists(long_path(header.first_seen_path)) else None


# --- reader --------------------------------------------------------------------------


@dataclass
class CachedIntake:
    result: PdfCoilIntakeResult
    sha1: str
    cache_status: CacheStatus


def _prime_intake_page_cache(sha1: str, pages: list[Any], engine: str) -> None:
    pdf_intake.prime_text_pages_cache(sha1, pages, engine)


def intake_with_page_cache(
    pdf_path: str | os.PathLike[str],
    *,
    data_dir: str | os.PathLike[str] | None = None,
    write_through: bool = True,
    source_id: str = "PDF-UPLOAD-INTAKE-001",
    source_filename: str | None = None,
    cover_page_hint: int | None = None,
) -> CachedIntake:
    """Intake a PDF, reusing the cached page extraction when it is current.

    ``source_filename`` defaults to the file's own name (what ``ccsi_crosscheck`` passes).
    """
    directory = Path(data_dir) if data_dir is not None else default_data_dir()
    pdf_bytes = read_pdf_bytes(pdf_path)
    sha1 = hashlib.sha1(pdf_bytes).hexdigest()
    status, _, pages = read_page_record(directory, sha1)
    if status == "HIT":
        _prime_intake_page_cache(sha1, pages or [], "pdfplumber")
        cache_status: CacheStatus = "HIT"
    else:
        built = build_page_record(pdf_bytes, os.fspath(pdf_path))
        if built is None:
            cache_status = "ENGINE_FALLBACK"
        else:
            if write_through:
                write_page_record(directory, *built)
            cache_status = {
                "MISSING": "MISS_PARSED", "STALE": "STALE_REPARSED", "CORRUPT": "CORRUPT_REPARSED"
            }[status]  # type: ignore[assignment]
    result = pdf_intake.extract_coil_candidate_from_pdf_bytes(
        pdf_bytes,
        source_id=source_id,
        source_filename=source_filename if source_filename is not None else Path(pdf_path).name,
        cover_page_hint=cover_page_hint,
    )
    return CachedIntake(result=result, sha1=sha1, cache_status=cache_status)


# --- batch ---------------------------------------------------------------------------


def worker_main(source_path: str, expected_sha1: str, data_dir: str) -> None:
    """Spawn target: re-read the (already hydrated) file, extract, write its own record.

    Reports through the exit code only -- a shared queue can be corrupted by a child
    killed at the deadline.
    """
    pdf_bytes = read_pdf_bytes(source_path)
    if hashlib.sha1(pdf_bytes).hexdigest() != expected_sha1:
        sys.exit(EXIT_SHA1_CHANGED)
    built = build_page_record(pdf_bytes, source_path)
    if built is None:
        sys.exit(EXIT_ENGINE_FALLBACK)
    write_page_record(data_dir, *built)
    sys.exit(EXIT_OK)


@dataclass
class BatchItem:
    path: str
    cloud_only: bool = False
    # Ledger sha1s this file might be (name/size candidate). ``None`` = not a ledger
    # candidate; otherwise a read sha1 outside this set is LEDGER_SIZE_ONLY_MISMATCH and
    # the file is NOT extracted.
    ledger_expected: set[str] | None = None


@dataclass
class BatchOutcome:
    events: list[dict[str, Any]] = field(default_factory=list)
    file_sha1: dict[str, str] = field(default_factory=dict)
    ledger_confirmed: dict[str, str] = field(default_factory=dict)
    aborted: bool = False


def run_batch(
    items: list[BatchItem],
    *,
    data_dir: str | os.PathLike[str],
    workers: int = 4,
    timeout_s: float = 1200.0,
    max_hydrate: int | None = None,
    emit: Callable[[dict[str, Any]], None] | None = None,
    target: Callable[..., None] = worker_main,
    poll_s: float = 0.5,
) -> BatchOutcome:
    """Read files one at a time (downloads stay serial), extract in up to ``workers``
    spawned processes, one process per file, killed at ``timeout_s``."""
    outcome = BatchOutcome()
    context = multiprocessing.get_context("spawn")
    running: dict[str, tuple[Any, str, float]] = {}  # sha1 -> (process, path, started)
    seen: set[str] = set()
    hydrated = 0
    consecutive_cloud_failures = 0

    def record(status: str, path: str, sha1: str | None = None, **detail: Any) -> None:
        event = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "status": status, "path": path, "sha1": sha1, **detail}
        outcome.events.append(event)
        if emit is not None:
            emit(event)

    def reap(block_until_free: bool) -> None:
        while running:
            for sha1, (process, path, started) in list(running.items()):
                elapsed = time.monotonic() - started
                if process.is_alive():
                    if elapsed > timeout_s:
                        process.kill()
                        process.join()
                        del running[sha1]
                        record("TIMEOUT", path, sha1, duration_s=round(elapsed, 1))
                    continue
                process.join()
                del running[sha1]
                code = process.exitcode
                if code == EXIT_OK and read_page_record(data_dir, sha1)[0] == "HIT":
                    record("EXTRACTED", path, sha1, duration_s=round(elapsed, 1))
                elif code == EXIT_ENGINE_FALLBACK:
                    record("ENGINE_FALLBACK_NOT_CACHED", path, sha1)
                elif code == EXIT_SHA1_CHANGED:
                    record("EXTRACT_FAILED", path, sha1, detail="file changed between read and extract")
                elif code == EXIT_FAILED:
                    record("EXTRACT_FAILED", path, sha1, exitcode=code)
                else:
                    record("CRASHED", path, sha1, exitcode=code)
            if not block_until_free or len(running) < workers:
                return
            time.sleep(poll_s)

    for item in items:
        if item.cloud_only and max_hydrate is not None and hydrated >= max_hydrate:
            record("HYDRATE_BUDGET_EXHAUSTED", item.path)
            continue
        try:
            pdf_bytes = read_pdf_bytes(item.path)
        except OSError as exc:
            record("READ_FAILED", item.path, winerror=getattr(exc, "winerror", None), error=repr(exc))
            if item.cloud_only:
                consecutive_cloud_failures += 1
                if consecutive_cloud_failures >= 3:
                    outcome.aborted = True
                    record("ABORTED", item.path, detail="3 consecutive cloud-only read failures")
                    break
            continue
        if item.cloud_only:
            hydrated += 1
            consecutive_cloud_failures = 0
        sha1 = hashlib.sha1(pdf_bytes).hexdigest()
        del pdf_bytes
        outcome.file_sha1[item.path] = sha1
        if item.ledger_expected is not None:
            if sha1 not in item.ledger_expected:
                record("LEDGER_SIZE_ONLY_MISMATCH", item.path, sha1)
                continue
            outcome.ledger_confirmed[item.path] = sha1
            record("LEDGER_CONFIRMED", item.path, sha1)
        if sha1 in seen:
            record("DUPLICATE_IN_RUN", item.path, sha1)
            continue
        seen.add(sha1)
        if read_page_record(data_dir, sha1)[0] == "HIT":
            record("CACHE_HIT", item.path, sha1)
            continue
        reap(block_until_free=True)
        process = context.Process(target=target, args=(item.path, sha1, os.fspath(data_dir)))
        process.start()
        running[sha1] = (process, item.path, time.monotonic())

    while running:
        reap(block_until_free=False)
        if running:
            time.sleep(poll_s)
    return outcome
