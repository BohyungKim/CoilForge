"""P0-A: memoization of the two identity-free heavy intake sub-operations
(pdfplumber page extraction + per-page gpt-4o OCR).

These guard that the caches (1) actually dedupe the expensive work, (2) NEVER cache a
transient OCR failure (a rate-limit / network / missing-key result must be retried on a
later re-analyze), and (3) do not leak ``source_filename`` across two callers of the same
bytes -- the cache is keyed on bytes only and sits BELOW the identity/filename layer, so
project context stays per-caller (byte-identity / isolation guard, Round-2 review).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.submittal import pdf_intake
from coilforge.submittal.pdf_intake import (
    _OcrPageResult,
    clear_pdf_intake_caches,
    extract_coil_candidate_from_pdf_bytes,
    extract_text_pages_from_pdf_bytes,
)


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


def _sample_pdf_bytes() -> bytes:
    # Deliberately carries NO project-number label in its text, so the project context
    # falls back to source_filename -- which is exactly what test (3) exercises.
    return _make_text_pdf(
        [
            "Tag CDXC-1",
            "Coil Quantity 2",
            "Handing Left",
            "Finned Height 18 in",
            "Finned Length 36 in",
        ]
    )


@pytest.fixture(autouse=True)
def _clean_intake_caches():
    clear_pdf_intake_caches()
    yield
    clear_pdf_intake_caches()


def test_page_extraction_memoized_and_returns_fresh_list(monkeypatch) -> None:
    calls = [0]
    real = pdf_intake._extract_text_pages_from_pdf_bytes_uncached

    def counting(pdf_bytes):
        calls[0] += 1
        return real(pdf_bytes)

    monkeypatch.setattr(
        pdf_intake, "_extract_text_pages_from_pdf_bytes_uncached", counting
    )
    pdf = _sample_pdf_bytes()

    pages1, engine1 = extract_text_pages_from_pdf_bytes(pdf)
    pages2, engine2 = extract_text_pages_from_pdf_bytes(pdf)

    # Second call on identical bytes is a cache HIT: the expensive extractor ran once.
    assert calls[0] == 1
    assert engine1 == engine2
    assert [p.text for p in pages1] == [p.text for p in pages2]
    # ...but a fresh list container each time (callers may rebuild their page list).
    assert pages1 is not pages2

    # Different bytes -> different key -> the extractor runs again.
    extract_text_pages_from_pdf_bytes(_make_text_pdf(["Tag CDXC-9"]))
    assert calls[0] == 2


def test_ocr_failure_not_cached(monkeypatch) -> None:
    pdf = _sample_pdf_bytes()
    calls = [0]

    def failing(pdf_bytes, page_number):
        calls[0] += 1
        # Empty text == transient failure (rate limit / network / missing key).
        return _OcrPageResult(page_number=page_number, status="failed_openai_request")

    monkeypatch.setattr(
        pdf_intake, "_extract_page_text_with_llm_ocr_uncached", failing
    )
    pdf_intake._extract_page_text_with_llm_ocr(pdf, 1)
    pdf_intake._extract_page_text_with_llm_ocr(pdf, 1)

    # A transient failure is NEVER cached -> a re-analyze can still recover the page.
    assert calls[0] == 2


def test_ocr_success_cached(monkeypatch) -> None:
    pdf = _sample_pdf_bytes()
    calls = [0]

    def ok(pdf_bytes, page_number):
        calls[0] += 1
        return _OcrPageResult(
            page_number=page_number, text="RECOVERED", status="completed"
        )

    monkeypatch.setattr(pdf_intake, "_extract_page_text_with_llm_ocr_uncached", ok)

    r1 = pdf_intake._extract_page_text_with_llm_ocr(pdf, 1)
    r2 = pdf_intake._extract_page_text_with_llm_ocr(pdf, 1)

    # A successful (non-empty) OCR is memoized -> the gpt-4o call fires once.
    assert calls[0] == 1
    assert r1.text == r2.text == "RECOVERED"
    # A different page is a separate key.
    pdf_intake._extract_page_text_with_llm_ocr(pdf, 2)
    assert calls[0] == 2


def test_same_bytes_different_source_filename_no_project_leak() -> None:
    pdf = _sample_pdf_bytes()  # text has no project label -> filename provides it

    a = extract_coil_candidate_from_pdf_bytes(
        pdf, source_id="SRC-A", source_filename="1001 - Acme Project.pdf"
    )
    b = extract_coil_candidate_from_pdf_bytes(
        pdf, source_id="SRC-B", source_filename="2002 - Beta Project.pdf"
    )

    # The bytes-only page cache is shared, but project context runs per-caller with each
    # call's own source_filename -- so B must NOT inherit A's project number.
    assert a.summary.project_number == "1001"
    assert b.summary.project_number == "2002"
