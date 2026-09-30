"""Page-text cache: record round trip, reader equality with a live parse, staleness,
the never-cache-PyPDF2 rule, no OCR in extraction, and the per-file batch runner
(timeout kill, ledger mismatch, cache hits).
"""
from __future__ import annotations

import dataclasses
import hashlib
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.corpus import fs, page_cache  # noqa: E402
from coilforge.corpus.page_cache import (  # noqa: E402
    BatchItem,
    PageCacheHeader,
    build_page_record,
    extractor_fingerprint,
    intake_with_page_cache,
    pages_path,
    read_page_record,
    run_batch,
    write_page_record,
)
from coilforge.submittal import pdf_intake  # noqa: E402
from coilforge.submittal.pdf_intake import clear_pdf_intake_caches  # noqa: E402


def _make_text_pdf(lines: list[str]) -> bytes:
    text_ops = ["BT", "/F1 12 Tf", "72 720 Td"]
    first = True
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if not first:
            text_ops.append("0 -16 Td")
        text_ops.append(f"({safe}) Tj")
        first = False
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("latin-1")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        (
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        ),
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(stream)} >> stream\n".encode("ascii")
        + stream
        + b"\nendstream endobj\n",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj
    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode("ascii")
    pdf += (
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    return pdf


def _sample_pdf(tmp_path: Path, name: str = "3232 - Oxygen8 Submittal - Rev1.pdf", tag: str = "CDXC-1") -> Path:
    path = tmp_path / "pdfs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        _make_text_pdf([f"Tag {tag}", "Coil Quantity 2", "Handing Left", "Finned Height 18 in", "Finned Length 36 in"])
    )
    return path


@pytest.fixture(autouse=True)
def _isolation(tmp_path, monkeypatch):
    monkeypatch.setenv(fs.ENV_INDEX_DIR, str(tmp_path / "index_data"))
    clear_pdf_intake_caches()
    yield
    clear_pdf_intake_caches()


def _sleepy_target(source_path: str, expected_sha1: str, data_dir: str) -> None:
    time.sleep(60)


def _dump(result) -> dict:
    return result.model_dump(mode="json")


# --- internals guard ------------------------------------------------------------------


def test_pdf_intake_internals_the_cache_relies_on():
    """Fails loudly if the pdf_intake surface the cache uses changes shape: the public
    seam, the ``_TextPage`` layout it rebuilds, and the fingerprinted extractor source."""
    assert callable(pdf_intake.prime_text_pages_cache)
    assert [f.name for f in dataclasses.fields(pdf_intake._TextPage)] == ["page_number", "text", "tables"]
    for name in page_cache._FINGERPRINTED_FUNCTIONS:
        assert callable(getattr(pdf_intake, name))
    assert len(extractor_fingerprint()) == 64


def test_prime_seam_makes_the_next_extraction_a_hit(monkeypatch):
    pages = [pdf_intake._TextPage(page_number=1, text="Tag CDXC-1", tables=())]
    pdf_intake.prime_text_pages_cache("f" * 40, pages, "pdfplumber")

    def forbidden(_pdf_bytes):
        raise AssertionError("primed pages must not be re-extracted")

    monkeypatch.setattr(pdf_intake, "_pdf_bytes_sha1", lambda _b: "f" * 40)
    monkeypatch.setattr(pdf_intake, "_extract_text_pages_from_pdf_bytes_uncached", forbidden)
    got, engine = pdf_intake.extract_text_pages_from_pdf_bytes(b"any bytes")
    assert engine == "pdfplumber" and got == pages and got is not pages


# --- records --------------------------------------------------------------------------


def test_record_round_trip_keeps_lone_surrogates_and_tables(tmp_path):
    pages = [
        pdf_intake._TextPage(page_number=1, text="broken \ud800 glyph", tables=((("Tag", "CDXC-1"),),)),
        pdf_intake._TextPage(page_number=2, text="", tables=()),
    ]
    header = PageCacheHeader(
        sha1="a" * 40, byte_size=10, engine="pdfplumber", extractor_fingerprint=extractor_fingerprint(),
        page_count=2, text_chars=15, extracted_at="t", duration_s=0.1,
    )
    write_page_record(tmp_path, header, pages)
    status, loaded_header, loaded_pages = read_page_record(tmp_path, "a" * 40)
    assert status == "HIT"
    assert loaded_header == header
    assert loaded_pages == pages
    assert pages_path(tmp_path, "a" * 40).read_text(encoding="utf-8").isascii()


def test_build_page_record_never_reaches_ocr(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("OCR must not run during page extraction")

    monkeypatch.setattr(pdf_intake, "_extract_page_text_with_llm_ocr_uncached", forbidden)
    monkeypatch.setattr(pdf_intake, "_maybe_run_llm_ocr", forbidden)
    built = build_page_record(_sample_pdf(tmp_path).read_bytes())
    assert built is not None and built[0].engine == "pdfplumber" and built[0].page_count == 1


def test_pypdf2_fallback_is_never_cached(tmp_path, monkeypatch):
    real = pdf_intake._extract_text_pages_from_pdf_bytes_uncached

    def fallback(pdf_bytes):
        pages, _ = real(pdf_bytes)
        return pages, "PyPDF2"

    monkeypatch.setattr(pdf_intake, "_extract_text_pages_from_pdf_bytes_uncached", fallback)
    pdf = _sample_pdf(tmp_path)
    assert build_page_record(pdf.read_bytes()) is None
    cached = intake_with_page_cache(pdf, data_dir=tmp_path / "data")
    assert cached.cache_status == "ENGINE_FALLBACK"
    assert not (tmp_path / "data" / "pages").exists()


def test_refused_replace_is_done_only_for_a_current_record(tmp_path, monkeypatch):
    built = build_page_record(_sample_pdf(tmp_path).read_bytes())
    assert built is not None
    header, pages = built
    target = pages_path(tmp_path, header.sha1)
    target.parent.mkdir(parents=True)
    target.write_text('{"header": {}, "pages": []}', encoding="utf-8")  # corrupt

    def refused(*_args, **_kwargs):
        raise PermissionError("held open by a reader")

    monkeypatch.setattr(os, "replace", refused)
    with pytest.raises(PermissionError):
        write_page_record(tmp_path, header, pages)  # corrupt target is NOT "done"
    monkeypatch.undo()
    write_page_record(tmp_path, header, pages)
    monkeypatch.setattr(os, "replace", refused)
    write_page_record(tmp_path, header, pages)  # current record already there -> done


# --- reader ---------------------------------------------------------------------------


def test_cached_intake_equals_live_parse_and_never_reparses(tmp_path, monkeypatch):
    pdf = _sample_pdf(tmp_path)
    data = tmp_path / "data"
    live = intake_with_page_cache(pdf, data_dir=data)
    assert live.cache_status == "MISS_PARSED"
    assert live.result.summary.source_filename == pdf.name

    clear_pdf_intake_caches()

    def forbidden(_pdf_bytes):
        raise AssertionError("cache HIT must not re-run pdfplumber")

    monkeypatch.setattr(pdf_intake, "_extract_text_pages_from_pdf_bytes_uncached", forbidden)
    cached = intake_with_page_cache(pdf, data_dir=data)
    assert cached.cache_status == "HIT"
    assert _dump(cached.result) == _dump(live.result)


def test_stale_and_corrupt_records_are_reparsed(tmp_path, monkeypatch):
    pdf = _sample_pdf(tmp_path)
    data = tmp_path / "data"
    first = intake_with_page_cache(pdf, data_dir=data)

    monkeypatch.setattr(page_cache, "extractor_fingerprint", lambda: "different-extractor")
    clear_pdf_intake_caches()
    stale = intake_with_page_cache(pdf, data_dir=data)
    assert stale.cache_status == "STALE_REPARSED"
    monkeypatch.undo()

    pages_path(data, first.sha1).write_text("not json", encoding="utf-8")
    clear_pdf_intake_caches()
    corrupt = intake_with_page_cache(pdf, data_dir=data)
    assert corrupt.cache_status == "CORRUPT_REPARSED"
    assert read_page_record(data, first.sha1)[0] == "HIT"
    assert _dump(corrupt.result) == _dump(first.result)


def test_cached_source_path_pairs_a_sha1_with_its_file(tmp_path):
    pdf = _sample_pdf(tmp_path)
    data = tmp_path / "data"
    sha1 = intake_with_page_cache(pdf, data_dir=data).sha1
    assert page_cache.cached_source_path(sha1, data) == str(pdf)
    assert page_cache.cached_source_path("0" * 40, data) is None  # never cached
    pdf.unlink()
    assert page_cache.cached_source_path(sha1, data) is None  # file moved/deleted


# --- batch ----------------------------------------------------------------------------


def test_batch_extracts_then_hits_and_skips_ledger_mismatch(tmp_path):
    a = _sample_pdf(tmp_path, "a.pdf", "CDXC-1")
    b = _sample_pdf(tmp_path, "b.pdf", "CDXC-2")
    a_copy = tmp_path / "pdfs" / "a copy.pdf"
    a_copy.write_bytes(a.read_bytes())
    data = tmp_path / "data"
    events_seen: list[str] = []

    items = [
        BatchItem(path=str(a)),
        BatchItem(path=str(a_copy)),
        BatchItem(path=str(b), ledger_expected={"0" * 40}),
    ]
    outcome = run_batch(items, data_dir=data, workers=2, emit=lambda e: events_seen.append(e["status"]), poll_s=0.05)
    statuses = {Path(e["path"]).name: e["status"] for e in outcome.events}
    assert statuses == {"a.pdf": "EXTRACTED", "a copy.pdf": "DUPLICATE_IN_RUN", "b.pdf": "LEDGER_SIZE_ONLY_MISMATCH"}
    assert events_seen == [e["status"] for e in outcome.events]
    assert not pages_path(data, outcome.file_sha1[str(b)]).exists()

    again = run_batch([BatchItem(path=str(a))], data_dir=data, poll_s=0.05)
    assert [e["status"] for e in again.events] == ["CACHE_HIT"]


def test_batch_confirms_ledger_candidate(tmp_path):
    a = _sample_pdf(tmp_path, "a.pdf")
    sha1 = hashlib.sha1(a.read_bytes()).hexdigest()
    outcome = run_batch([BatchItem(path=str(a), ledger_expected={sha1})], data_dir=tmp_path / "d", poll_s=0.05)
    assert [e["status"] for e in outcome.events] == ["LEDGER_CONFIRMED", "EXTRACTED"]
    assert outcome.ledger_confirmed == {str(a): sha1}


def test_batch_kills_a_worker_past_the_deadline(tmp_path):
    a = _sample_pdf(tmp_path, "a.pdf")
    started = time.monotonic()
    outcome = run_batch(
        [BatchItem(path=str(a))], data_dir=tmp_path / "d", timeout_s=2, target=_sleepy_target, poll_s=0.1
    )
    assert [e["status"] for e in outcome.events] == ["TIMEOUT"]
    assert time.monotonic() - started < 30
    assert not (tmp_path / "d" / "pages").exists()


def test_batch_read_failures_and_hydrate_budget(tmp_path):
    missing = [BatchItem(path=str(tmp_path / f"gone{i}.pdf"), cloud_only=True) for i in range(4)]
    outcome = run_batch(missing, data_dir=tmp_path / "d", poll_s=0.05)
    assert [e["status"] for e in outcome.events] == ["READ_FAILED"] * 3 + ["ABORTED"]
    assert outcome.aborted

    a = _sample_pdf(tmp_path, "a.pdf")
    budget = run_batch(
        [BatchItem(path=str(a), cloud_only=True), BatchItem(path=str(a), cloud_only=True)],
        data_dir=tmp_path / "d2", max_hydrate=1, poll_s=0.05,
    )
    assert sorted(e["status"] for e in budget.events) == ["EXTRACTED", "HYDRATE_BUDGET_EXHAUSTED"]
