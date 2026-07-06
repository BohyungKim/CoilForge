"""Auto-OCR recovery for submittals whose coil pages have un-extractable fonts.

Some Oxygen8 submittal exports embed subset fonts with a broken ToUnicode CMap: the pages
render fine on screen but extract as "(cid:NN)" glyph soup (pdfplumber) or an ASCII-shifted
cipher (PyPDF2). The intake must detect that and auto-OCR the affected pages instead of
silently reporting "no coils". These tests pin the detector and the auto-OCR trigger; the
OpenAI call itself is monkeypatched so no network or API key is required.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.submittal import pdf_intake as pi
from coilforge.submittal.pdf_intake import (
    _OcrPageResult,
    _TextPage,
    _classify_openai_ocr_error,
    _page_text_is_degraded,
    extract_coil_candidate_from_pdf_bytes,
)


_CID_SOUP = "(cid:51)(cid:85)(cid:82)(cid:77)(cid:72)(cid:70)(cid:87)(cid:29)(cid:3)" * 30
_CLEAN_NONCOIL = (
    "Unit Sound Data dBA. Supply fan Lw at each octave band. The values are estimates "
    "for the selected unit and airflow. Total radiated sound power level shown. " * 3
)
_COVER_TEXT = "\n".join(
    [
        "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
        "1 CDXC-1 DXC Cooling TR_C_015 LH",
        "1 RHHGRC-1 HGRC Reheat TR_C_015 LH",
    ]
)


def _shift(text: str, offset: int = -29) -> str:
    return "".join(
        chr(ord(ch) + offset) if 33 <= ord(ch) <= 126 else ch for ch in text
    )


def test_page_text_is_degraded_detects_broken_fonts() -> None:
    # pdfplumber glyph soup and the PyPDF2 fixed-offset cipher are both unreadable.
    assert _page_text_is_degraded(_CID_SOUP) is True
    assert _page_text_is_degraded(_shift(_COVER_TEXT + " " + _CLEAN_NONCOIL)) is True
    # Readable English content and near-empty pages are NOT flagged (no needless OCR).
    assert _page_text_is_degraded(_CLEAN_NONCOIL) is False
    assert _page_text_is_degraded("Qty Tag Model") is False


def test_auto_ocr_recovers_coils_from_degraded_cover_page(monkeypatch) -> None:
    pages = [
        _TextPage(page_number=1, text=_CID_SOUP),
        _TextPage(page_number=2, text=_CLEAN_NONCOIL),
    ]
    monkeypatch.setattr(
        pi, "extract_text_pages_from_pdf_bytes", lambda _bytes: (pages, "pdfplumber")
    )

    ocr_calls: list[int] = []

    def _fake_ocr(_pdf_bytes: bytes, page_number: int) -> _OcrPageResult:
        ocr_calls.append(page_number)
        text = _COVER_TEXT if page_number == 1 else ""
        return _OcrPageResult(
            page_number=page_number,
            text=text,
            model="gpt-4o",
            status="completed" if text else "completed_empty",
        )

    monkeypatch.setattr(pi, "_extract_page_text_with_llm_ocr", _fake_ocr)

    result = extract_coil_candidate_from_pdf_bytes(b"%PDF-fake")

    assert ocr_calls == [1]  # only the degraded page was OCR'd
    assert result.summary.text_extraction_degraded is True
    assert result.summary.degraded_page_numbers == [1]
    assert result.summary.ocr_pages == [1]
    assert result.summary.ocr_status == "completed"
    assert result.summary.ocr_blocked is False
    assert result.summary.ocr_alert is None
    assert "auto_llm_ocr" in result.summary.extraction_engine
    # The cover schedule is recovered from the OCR text -> real coil tags surface.
    assert result.summary.cover_page_detected is True
    assert [row.tag for row in result.summary.cover_page_rows] == ["CDXC-1", "RHHGRC-1"]


class _FakeRateLimitError(Exception):
    def __init__(self) -> None:
        self.status_code = 429
        self.code = "insufficient_quota"
        self.message = "You exceeded your current quota, please check your plan and billing."


class _FakeAuthError(Exception):
    def __init__(self) -> None:
        self.status_code = 401
        self.code = "invalid_api_key"
        self.message = "Incorrect API key provided."


def test_classify_openai_ocr_error() -> None:
    assert _classify_openai_ocr_error(_FakeRateLimitError())[0] == "blocked_openai_quota_exhausted"
    assert _classify_openai_ocr_error(_FakeAuthError())[0] == "blocked_openai_auth"
    assert _classify_openai_ocr_error(RuntimeError("boom"))[0] == "failed_openai_request"


def test_quota_exhausted_raises_ocr_blocked_alert(monkeypatch) -> None:
    pages = [
        _TextPage(page_number=1, text=_CID_SOUP),
        _TextPage(page_number=2, text=_CLEAN_NONCOIL),
    ]
    monkeypatch.setattr(
        pi, "extract_text_pages_from_pdf_bytes", lambda _bytes: (pages, "pdfplumber")
    )

    def _quota_blocked(_pdf_bytes: bytes, page_number: int) -> _OcrPageResult:
        return _OcrPageResult(
            page_number=page_number,
            model="gpt-4o",
            status="blocked_openai_quota_exhausted",
            error="OpenAI token/quota exhausted (insufficient_quota).",
        )

    monkeypatch.setattr(pi, "_extract_page_text_with_llm_ocr", _quota_blocked)

    result = extract_coil_candidate_from_pdf_bytes(b"%PDF-fake")

    assert result.summary.text_extraction_degraded is True
    assert result.summary.ocr_pages == []  # nothing recovered
    assert result.summary.ocr_blocked is True
    assert "token/quota" in (result.summary.ocr_alert or "")
    # Still fails loudly, not silently: no coils, but the alert explains why.
    assert result.summary.cover_page_detected is False


def test_clean_pdf_is_not_degraded_and_skips_ocr(monkeypatch) -> None:
    pages = [
        _TextPage(
            page_number=1,
            text=_COVER_TEXT + "\n" + _CLEAN_NONCOIL,
        )
    ]
    monkeypatch.setattr(
        pi, "extract_text_pages_from_pdf_bytes", lambda _bytes: (pages, "pdfplumber")
    )

    ocr_called = False

    def _fail_ocr(_pdf_bytes: bytes, page_number: int) -> _OcrPageResult:
        nonlocal ocr_called
        ocr_called = True
        raise AssertionError("OCR must not run for a cleanly-extracted PDF")

    monkeypatch.setattr(pi, "_extract_page_text_with_llm_ocr", _fail_ocr)

    result = extract_coil_candidate_from_pdf_bytes(b"%PDF-fake")

    assert ocr_called is False
    assert result.summary.text_extraction_degraded is False
    assert result.summary.degraded_page_numbers == []
    assert result.summary.ocr_pages == []
    assert result.summary.ocr_status == "not_requested"
    assert "auto_llm_ocr" not in result.summary.extraction_engine
