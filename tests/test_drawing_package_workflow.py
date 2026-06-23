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
