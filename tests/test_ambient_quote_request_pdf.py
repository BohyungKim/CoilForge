"""Phase 5 — the Ambient quote-request PDF (builder + /api/ambient/quote-request-pdf).

Two halves. The builder tests feed the real ``AmbientPackage.as_dict()`` shape straight in,
so they pin the payload contract without needing a PDF or the web layer. The route tests
patch the workflow (same technique as tests/test_ambient_web.py) so no customer PDF is
committed, and exercise the kill-switch, the 400/500 contract, and the memo reuse that the
re-POST design depends on.

The load-bearing assertions here are the never-invent ones: a value the submittal did not
state must render as a dash and never as 0/N/A, and a payload that CLAIMS export_allowed
must not be able to promote the result.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

fitz = pytest.importorskip("fitz")

from coilforge.ambient.quote_request_pdf import (  # noqa: E402
    _MISSING,
    build_ambient_quote_request_pdf,
)
from coilforge.package.assembler import REVIEW_WATERMARK  # noqa: E402

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="200">'
    '<text x="10" y="30">COIL DRAWING</text></svg>'
)


def _line(label, value, unit=None, key=None):
    return {
        "label": label,
        "group": "performance",
        "key": key or label.lower().replace(" ", "_"),
        "value": value,
        "unit": unit,
        "review_required": True,
    }


def _coil(tag="CDXC-1", *, lines=None, band=None, missing=(), svg=None, omitted=None, source=None):
    return {
        "tag": tag,
        "category": "DX",
        "performance_lines": list(lines) if lines is not None else [_line("Rows Deep", 4)],
        "targets": {},
        "acceptance_band": band,
        "missing_fields": list(missing),
        "drawing": {"source": source, "svg": svg, "omitted_reason": omitted},
    }


def _package(coils, warnings=()):
    return {
        "coils": list(coils),
        "warnings": list(warnings),
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
        "review_required": True,
    }


def _text(result, page_index=None) -> str:
    doc = fitz.open(stream=base64.b64decode(result.pdf_base64), filetype="pdf")
    try:
        if page_index is None:
            return "\n".join(page.get_text() for page in doc)
        return doc[page_index].get_text()
    finally:
        doc.close()


# --- builder ---------------------------------------------------------------------------


def test_multi_coil_pdf_is_cover_then_performance_then_drawing_per_coil():
    result = build_ambient_quote_request_pdf(
        _package(
            [
                _coil("CDXC-1", svg=_SVG, source="track_b_generated"),
                _coil("RHHGRC-1", svg=_SVG, source="track_b_generated"),
            ]
        )
    )
    assert result.page_count == 5  # cover + (perf + drawing) x 2
    assert result.coil_count == 2
    first, second = result.coil_pages
    assert first["performance_page_index"] == 1
    assert first["drawing_page_index"] == 2
    # The second coil starts only after the first coil's drawing — pages are grouped by coil,
    # not by kind, so the supplier reads one coil at a time.
    assert second["performance_page_index"] > first["drawing_page_index"]
    assert second["drawing_page_index"] == 4


def test_coil_without_drawing_gets_performance_page_and_a_loud_omission():
    result = build_ambient_quote_request_pdf(
        _package([_coil(omitted="no seeded reference for this hand/header")])
    )
    assert result.page_count == 2  # cover + performance only
    assert result.coil_pages[0]["drawing_page_index"] is None
    assert "no seeded reference for this hand/header" in _text(result, 1)


def test_missing_value_renders_as_a_dash_and_is_never_guessed():
    result = build_ambient_quote_request_pdf(
        _package(
            [
                _coil(
                    lines=[_line("Total Capacity", None, "MBH")],
                    missing=["geometry.rows_deep", "performance.capacity_mbh"],
                )
            ]
        )
    )
    page = _text(result, 1)
    assert _MISSING in page
    assert "geometry.rows_deep" in page and "performance.capacity_mbh" in page
    # The absent capacity must NOT have been defaulted into a number or an "N/A".
    assert "N/A" not in page
    assert "0" not in page.split("Total Capacity")[1].splitlines()[1]


def test_a_stated_zero_survives_and_is_not_treated_as_missing():
    # 0 is a real transcribed value (John fills 0 for capacity by hand); only None is absent.
    result = build_ambient_quote_request_pdf(
        _package([_coil(lines=[_line("Air Side Fouling Factor", 0)])])
    )
    assert "0" in _text(result, 1).split("Air Side Fouling Factor")[1]


def test_absent_acceptance_band_is_omitted_not_fabricated():
    result = build_ambient_quote_request_pdf(_package([_coil(band=None)]))
    assert "EKEXVA" not in _text(result)
    assert "ACCEPTANCE BAND" not in _text(result)


def test_assumed_circuits_are_surfaced_on_the_page():
    band = {
        "ekexva_kit": "EKEXVA-120",
        "nominal_tons": 10,
        "capacity_band_mbh": [115, 145],
        "coil_volume_band_cuin": [900, 1100],
        "band_basis": "kit",
        "circuits": 1,
        "circuits_assumed": True,
    }
    page = _text(build_ambient_quote_request_pdf(_package([_coil(band=band)])), 1)
    assert "EKEXVA-120" in page
    assert "115 - 145" in page
    assert "circuits assumed" in page


def test_safety_flags_are_locked_even_when_the_payload_lies():
    # The most important test here: the flags are hard-wired on the model, never read from
    # the incoming payload, so a caller cannot promote a review aid into an export.
    lying = _package([_coil()])
    lying["export_allowed"] = True
    lying["production_drawing_approval_claimed"] = True
    result = build_ambient_quote_request_pdf(lying)
    assert result.export_allowed is False
    assert result.production_drawing_approval_claimed is False
    assert result.raw_private_data_returned is False


def test_review_watermark_is_on_every_page_including_the_drawing():
    result = build_ambient_quote_request_pdf(
        _package([_coil(svg=_SVG, source="track_b_generated")])
    )
    doc = fitz.open(stream=base64.b64decode(result.pdf_base64), filetype="pdf")
    try:
        assert doc.page_count == 3
        for index in range(doc.page_count):
            assert REVIEW_WATERMARK in doc[index].get_text(), f"page {index} unwatermarked"
    finally:
        doc.close()
    assert result.watermarked is True


def test_cover_page_states_project_date_and_coil_count():
    from datetime import date

    result = build_ambient_quote_request_pdf(
        _package([_coil("CDXC-1"), _coil("RHHGRC-1")]),
        project_name="Olympic Tower",
        project_number="2766",
        generated_on=date(2026, 7, 28),
    )
    cover = _text(result, 0)
    assert "QUOTE REQUEST" in cover
    assert "Olympic Tower" in cover and "2766" in cover
    assert "2026-07-28" in cover
    assert "CDXC-1" in cover and "RHHGRC-1" in cover


def test_cover_page_leaves_unknown_project_blank_not_guessed():
    cover = _text(build_ambient_quote_request_pdf(_package([_coil()])), 0)
    assert _MISSING in cover
    assert "Unknown" not in cover
    assert "N/A" not in cover


def test_unparseable_drawing_svg_warns_and_never_aborts_the_document():
    result = build_ambient_quote_request_pdf(
        _package([_coil("CDXC-1", svg="not an svg at all", source="track_b_generated")])
    )
    # The quote request still ships; only that one drawing is lost, and loudly.
    assert result.page_count == 2
    assert result.coil_pages[0]["drawing_page_index"] is None
    assert any("CDXC-1" in w for w in result.warnings)


def test_non_ascii_glyphs_are_transliterated_not_dropped():
    # MuPDF's base-14 font silently renders an em dash as a middle dot. Degree and
    # superscript-two DO render and must survive, since they carry unit meaning.
    result = build_ambient_quote_request_pdf(
        _package([_coil(lines=[_line("Entering Dry Bulb — design", 80.0, "°F")])])
    )
    page = _text(result, 1)
    assert "·" not in page, "em/en dash silently became a middle dot"
    assert "°F" in page


def test_empty_package_raises_value_error():
    with pytest.raises(ValueError):
        build_ambient_quote_request_pdf(_package([]))


# --- route -----------------------------------------------------------------------------

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import coilforge.web_app as web  # noqa: E402
from tests.test_ambient_web import _submittal_candidate  # noqa: E402

_ROUTE = "/api/ambient/quote-request-pdf"


@pytest.fixture
def client():
    web.clear_ambient_cache()
    web.clear_ambient_package_cache()
    return TestClient(web.app)


def _patch_package(monkeypatch, drawings=("track_b_generated", _SVG, None)):
    cand = _submittal_candidate()
    tag = cand.tag.value
    monkeypatch.setattr(
        web, "_baseline_workflow_and_candidates", lambda *a, **k: ([cand], {tag: drawings})
    )
    return tag


def test_route_kill_switch_returns_503(client, monkeypatch):
    monkeypatch.setenv("COILFORGE_AMBIENT", "0")
    assert client.post(_ROUTE, files={"submittal": ("s.pdf", b"x")}).status_code == 503


def test_route_missing_submittal_is_400(client):
    assert client.post(_ROUTE, files={"other": ("x.pdf", b"x")}).status_code == 400


def test_route_returns_pdf_base64_and_locked_safety_flags(client, monkeypatch):
    _patch_package(monkeypatch)
    response = client.post(_ROUTE, files={"submittal": ("s.pdf", b"%PDF-1")})
    assert response.status_code == 200
    data = response.json()
    assert base64.b64decode(data["pdf_base64"])[:5] == b"%PDF-"
    assert data["export_allowed"] is False
    assert data["production_drawing_approval_claimed"] is False
    assert data["raw_private_data_returned"] is False
    assert data["coil_count"] == 1
    assert data["page_count"] >= 2


def test_route_reuses_the_package_memo_without_reparsing(client, monkeypatch):
    # This is what justifies re-POSTing the PDFs instead of trusting the browser's rendered
    # JSON: back-to-back, the export costs no second parse. (Not a universal guarantee — the
    # LRU can evict — so the two calls are made in one test with nothing in between.)
    calls = {"n": 0}
    cand = _submittal_candidate()
    tag = cand.tag.value

    def _counted(*args, **kwargs):
        calls["n"] += 1
        return ([cand], {tag: ("track_b_generated", _SVG, None)})

    monkeypatch.setattr(web, "_baseline_workflow_and_candidates", _counted)
    files = {"submittal": ("s.pdf", b"%PDF-same-bytes")}
    assert client.post("/api/ambient/package", files=files).status_code == 200
    assert client.post(_ROUTE, files=files).status_code == 200
    assert calls["n"] == 1


def test_route_carries_optional_project_fields_onto_the_cover(client, monkeypatch):
    _patch_package(monkeypatch)
    response = client.post(
        _ROUTE,
        files={"submittal": ("s.pdf", b"%PDF-1")},
        data={"project_name": "Olympic Tower", "project_number": "2766"},
    )
    assert response.status_code == 200
    doc = fitz.open(
        stream=base64.b64decode(response.json()["pdf_base64"]), filetype="pdf"
    )
    try:
        cover = doc[0].get_text()
    finally:
        doc.close()
    assert "Olympic Tower" in cover and "2766" in cover


def test_route_garbage_pdf_never_crashes(client):
    response = client.post(_ROUTE, files={"submittal": ("s.pdf", b"not a pdf")})
    assert response.status_code in (400, 500)
    assert "detail" in response.json()
