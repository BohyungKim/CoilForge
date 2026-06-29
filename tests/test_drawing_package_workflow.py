"""Drawing-package workflow + /api/package/assemble route.

Covers the copper-strap rule wiring (DX -> count, CWC -> blocked, missing
header count -> review_required), input validation, and the HTTP contract
(200 with a base64 PDF; 400 on bad input; safety flags never relaxed).
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

fitz = pytest.importorskip("fitz")

from coilforge.workflows import run_drawing_package_workflow  # noqa: E402
from coilforge.workflows.drawing_package import run_quote_package_workflow  # noqa: E402

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200">'
    '<rect x="10" y="10" width="280" height="180" fill="none" stroke="black"/></svg>'
)


def _dc_pdf_b64(pages: int = 2) -> str:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    data = doc.tobytes()
    doc.close()
    return base64.b64encode(data).decode("ascii")


def _request(**overrides):
    base = {
        "direct_coil_pdf_base64": _dc_pdf_b64(2),
        "coilforge_drawing_svg": _SVG,
        "coil_type": "DX",
        "header_count": 2,
    }
    base.update(overrides)
    return base


def test_dx_package_counts_straps_and_appends_drawing() -> None:
    out = run_drawing_package_workflow(_request(coil_type="DX", header_count=2))
    assert out["copper_straps"]["count"] == 2
    assert out["copper_straps"]["status"] == "required"
    assert out["copper_straps"]["confidence"] == "HIGH"
    assert out["copper_straps"]["evidence_refs"]  # provenance carried
    pkg = out["package"]
    assert pkg["direct_coil_page_count"] == 2
    assert pkg["page_count"] == 3
    assert pkg["coilforge_page_index"] == 2
    assert out["export_allowed"] is False
    assert out["production_drawing_approval_claimed"] is False


def test_hgrh_two_straps_per_header() -> None:
    out = run_drawing_package_workflow(_request(coil_type="HGRH", header_count=3))
    assert out["copper_straps"]["count"] == 6
    assert "COPPER STRAPS REQUIRED: 6" == out["copper_straps"]["note"]


def test_cwc_blocked_never_invented() -> None:
    out = run_drawing_package_workflow(_request(coil_type="CWC", header_count=1))
    assert out["copper_straps"]["status"] == "blocked"
    assert out["copper_straps"]["count"] is None
    assert "REVIEW REQUIRED" in out["copper_straps"]["note"]


def test_missing_header_count_is_review_required() -> None:
    out = run_drawing_package_workflow(_request(coil_type="DX", header_count=None))
    assert out["copper_straps"]["status"] == "review_required"
    assert out["copper_straps"]["count"] is None


def test_invalid_coil_type_raises() -> None:
    with pytest.raises(ValueError):
        run_drawing_package_workflow(_request(coil_type="BOGUS"))


def test_bad_base64_raises() -> None:
    with pytest.raises(ValueError):
        run_drawing_package_workflow(_request(direct_coil_pdf_base64="!!!notb64!!!"))


def test_missing_svg_raises() -> None:
    with pytest.raises(ValueError):
        run_drawing_package_workflow(_request(coilforge_drawing_svg="  "))


def test_route_assembles_package() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from coilforge.web_app import app

    client = TestClient(app)
    resp = client.post("/api/package/assemble", json=_request(coil_type="DX", header_count=2))
    assert resp.status_code == 200
    body = resp.json()
    assert body["copper_straps"]["count"] == 2
    assert body["package"]["page_count"] == 3
    # base64 payload is a real PDF
    merged = base64.b64decode(body["package"]["pdf_base64"])
    doc = fitz.open(stream=merged, filetype="pdf")
    assert doc.page_count == 3
    doc.close()


def test_route_rejects_bad_input() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from coilforge.web_app import app

    client = TestClient(app)
    resp = client.post("/api/package/assemble", json={"coil_type": "DX"})  # no pdf, no svg
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# Multi-coil quote workflow: build from the reviewed per-coil state the UI sends
# (no blind re-extract), and never invent a header count.
# --------------------------------------------------------------------------- #
def _quote_pdf_b64() -> str:
    """A 2-page PDF: a COIL QUOTE page + a drawing page bearing the coil tag."""
    doc = fitz.open()
    quote = doc.new_page()
    for i, line in enumerate(["COIL QUOTE", "Tagged: RHHGRC-1", "Cost Each: CAD$960.00"]):
        quote.insert_text((40, 60 + i * 18), line)
    drawing = doc.new_page()
    for i, line in enumerate(["RHHGRC-1", "47 F.L.", "4.33 FIN"]):
        drawing.insert_text((40, 60 + i * 18), line)
    data = doc.tobytes()
    doc.close()
    return base64.b64encode(data).decode("ascii")


def test_quote_workflow_prices_from_reviewed_coils() -> None:
    # John's worked example: a 2-header HGRH -> 2 x 2 x $25 = $100, priced from the
    # reviewed header count the UI supplies (not re-extracted from the PDF).
    out = run_quote_package_workflow(
        {
            "source_pdf_base64": _quote_pdf_b64(),
            "coils": [
                {"tag": "RHHGRC-1", "coil_type": "HGRH", "our_svg": _SVG, "header_count": 2}
            ],
        }
    )
    coil = out["coils"][0]
    assert coil["copper_straps"]["total"] == 100.0
    assert coil["copper_straps"]["note"] == "Copper Strap Adder CAD$100.00"
    assert out["package"]["inserted_coil_count"] == 1
    assert out["export_allowed"] is False


def test_quote_workflow_unknown_header_count_flags_review() -> None:
    out = run_quote_package_workflow(
        {
            "source_pdf_base64": _quote_pdf_b64(),
            "coils": [
                {"tag": "RHHGRC-1", "coil_type": "HGRH", "our_svg": _SVG, "header_count": None}
            ],
        }
    )
    straps = out["coils"][0]["copper_straps"]
    assert straps["status"] == "review_required"
    assert straps["total"] is None  # no invented price


# --------------------------------------------------------------------------- #
# Tag-alias matching: a reviewed tag must match its source page across the
# documented RHHGRC <-> RHHGRH spelling alias (the 2766 Broadway drop bug, where
# the reviewed state said RHHGRH but the PDF said RHHGRC -> coil silently dropped).
# --------------------------------------------------------------------------- #
def test_coil_tag_aliases_groups_hgrh_spellings() -> None:
    from coilforge.submittal.pdf_intake import coil_tag_aliases

    aliases = coil_tag_aliases("RHHGRH-1")
    assert set(aliases) == {"RHHGRH-1", "RHHGRC-1", "HGRC-1", "HGRH-1"}
    assert coil_tag_aliases("CDXC-1") == ("CDXC-1",)  # DX has no aliases
    assert coil_tag_aliases("BOGUS-9") == ("BOGUS-9",)  # unknown prefix -> verbatim
    # HHWC (heating) and PHWC (preheat) are DISTINCT coils, NOT spelling variants —
    # they must never be grouped, or a package could match the wrong source page.
    assert coil_tag_aliases("HHWC-1") == ("HHWC-1",)
    assert "PHWC-1" not in coil_tag_aliases("HHWC-1")


def test_quote_workflow_inserts_across_tag_spelling_alias() -> None:
    # Source PDF spells the coil RHHGRC-1; the reviewed UI state carries the alias
    # spelling RHHGRH-1. It must still match its drawing page and insert (4/4-style),
    # not silently drop.
    out = run_quote_package_workflow(
        {
            "source_pdf_base64": _quote_pdf_b64(),
            "coils": [
                {"tag": "RHHGRH-1", "coil_type": "HGRH", "our_svg": _SVG, "header_count": 2}
            ],
        }
    )
    assert out["package"]["inserted_coil_count"] == 1
    coil = out["package"]["coils"][0]
    assert coil["inserted"] is True
    assert coil["not_inserted_reason"] is None


def test_quote_workflow_unmatched_coil_reports_loud_reason() -> None:
    # A tag that appears on no source page must be reported (inserted False + reason),
    # never silently dropped.
    out = run_quote_package_workflow(
        {
            "source_pdf_base64": _quote_pdf_b64(),
            "coils": [
                {"tag": "CDXC-9", "coil_type": "DX", "our_svg": _SVG, "header_count": 1}
            ],
        }
    )
    assert out["package"]["inserted_coil_count"] == 0
    coil = out["package"]["coils"][0]
    assert coil["inserted"] is False
    assert coil["not_inserted_reason"]
    assert "CDXC-9" in coil["not_inserted_reason"]
