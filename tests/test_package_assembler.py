"""Drawing-package assembler: merge Direct Coil PDF + CoilForge drawing.

Verifies page ordering (Direct Coil first, our drawing appended right after),
the SVG->PDF print utility, the copper-strap note carry-through, and that the
review-aid safety flags are never relaxed by this layer.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

fitz = pytest.importorskip("fitz")  # PyMuPDF required for PDF assembly

from coilforge.package import (  # noqa: E402
    PackageResult,
    assemble_drawing_package,
    svg_to_pdf_bytes,
)

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200">'
    '<rect x="10" y="10" width="280" height="180" fill="none" stroke="black"/>'
    "<text x=\"20\" y=\"40\">COILFORGE DX</text></svg>"
)


def _make_pdf(pages: int) -> bytes:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def test_svg_to_pdf_single_page() -> None:
    pdf_bytes = svg_to_pdf_bytes(_SVG)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    assert doc.page_count == 1
    doc.close()


def test_svg_to_pdf_rejects_empty() -> None:
    with pytest.raises(ValueError):
        svg_to_pdf_bytes("   ")


def test_package_appends_our_drawing_after_direct_coil() -> None:
    dc_pdf = _make_pdf(2)
    result = assemble_drawing_package(
        direct_coil_pdf=dc_pdf,
        coilforge_drawing_svg=_SVG,
        copper_strap_note="COPPER STRAPS REQUIRED: 4",
    )
    assert isinstance(result, PackageResult)
    assert result.direct_coil_page_count == 2
    assert result.page_count == 3  # 2 Direct Coil + 1 CoilForge
    assert result.coilforge_page_index == 2  # our page sits AFTER the DC pages
    assert result.copper_strap_note == "COPPER STRAPS REQUIRED: 4"

    # The base64 payload is a real, openable PDF with the expected page count.
    merged = base64.b64decode(result.pdf_base64)
    doc = fitz.open(stream=merged, filetype="pdf")
    assert doc.page_count == 3
    doc.close()


def test_package_safety_flags_never_relaxed() -> None:
    result = assemble_drawing_package(
        direct_coil_pdf=_make_pdf(1),
        coilforge_drawing_svg=_SVG,
        copper_strap_note="COPPER STRAPS: REVIEW REQUIRED",
        review_markups=["return_spacing: review required"],
        watermark=True,
    )
    assert result.export_allowed is False
    assert result.production_drawing_approval_claimed is False
    assert result.raw_private_data_returned is False
    assert result.watermarked is True
    assert "return_spacing: review required" in result.review_markups


def test_package_rejects_unreadable_direct_coil_pdf() -> None:
    with pytest.raises(ValueError):
        assemble_drawing_package(
            direct_coil_pdf=b"not a pdf",
            coilforge_drawing_svg=_SVG,
            copper_strap_note="COPPER STRAPS REQUIRED: 1",
        )
