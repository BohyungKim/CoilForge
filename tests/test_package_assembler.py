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
from coilforge.package.assembler import (  # noqa: E402
    MultiCoilPackageResult,
    _stamp_quote_price_notes,
    assemble_multi_coil_package,
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


def test_review_markups_carried_but_not_stamped() -> None:
    # The markups remain in the result for the on-screen review surface, but the
    # noisy "! suggestion / ! missing_input" lines are NOT drawn on the drawing.
    result = assemble_drawing_package(
        direct_coil_pdf=_make_pdf(1),
        coilforge_drawing_svg=_SVG,
        copper_strap_note="COPPER STRAPS REQUIRED: 2",
        review_markups=["suggestion:lifting_lugs=False (review)", "missing_input:header_count"],
        watermark=True,
    )
    assert "missing_input:header_count" in result.review_markups  # carried in the payload
    doc = fitz.open(stream=base64.b64decode(result.pdf_base64), filetype="pdf")
    our_page_text = doc[result.coilforge_page_index].get_text()
    assert "REVIEW AID - NOT FOR MANUFACTURING" in our_page_text  # watermark kept
    assert "COPPER STRAPS REQUIRED: 2" in our_page_text  # copper line kept
    assert "missing_input" not in our_page_text  # noise NOT stamped
    assert "suggestion:" not in our_page_text
    doc.close()


def test_package_rejects_unreadable_direct_coil_pdf() -> None:
    with pytest.raises(ValueError):
        assemble_drawing_package(
            direct_coil_pdf=b"not a pdf",
            coilforge_drawing_svg=_SVG,
            copper_strap_note="COPPER STRAPS REQUIRED: 1",
        )


# --------------------------------------------------------------------------- #
# Multi-coil quote package: per-coil drawing insertion + quote price notes.
# --------------------------------------------------------------------------- #
def _make_text_pdf(pages: list[str]) -> bytes:
    """A multi-page PDF with the given per-page text (one line per ``\\n``)."""
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        y = 60.0
        for line in text.split("\n"):
            page.insert_text((40, y), line)
            y += 18.0
    data = doc.tobytes()
    doc.close()
    return data


def test_multi_coil_inserts_after_drawing_page_and_notes_quote() -> None:
    # p0 quote, p1 textual REPORT (not the drawing), p2 drawing (F.L./FIN markers).
    source = _make_text_pdf(
        [
            "COIL QUOTE\nTagged: CDXC-1\nCost Each: CAD$100.00",
            "DX COIL REPORT\nCDXC-1\nspecs",
            "CDXC-1\n47 F.L.\n4.33 FIN",
        ]
    )
    coils = [
        {
            "tag": "CDXC-1",
            "coil_type": "DX",
            "our_svg": _SVG,
            "price_note": "Copper straps adder (review aid): +CAD$25.00",
            "price_total": 25.0,
            "price_status": "required",
        }
    ]
    result = assemble_multi_coil_package(source_pdf=source, coils=coils)
    assert isinstance(result, MultiCoilPackageResult)
    assert result.source_page_count == 3
    assert result.page_count == 4  # 3 source + 1 inserted
    assert result.inserted_coil_count == 1
    # The drawing page is the F.L./FIN page (index 2), NOT the REPORT page (index 1).
    assert result.coils[0]["drawing_page_source_index"] == 2

    doc = fitz.open(stream=base64.b64decode(result.pdf_base64), filetype="pdf")
    assert doc.page_count == 4
    # Our drawing sits right after the source drawing page -> output index 3.
    assert "REVIEW AID - NOT FOR MANUFACTURING" in doc[3].get_text()
    # Quote page keeps the ORIGINAL price (note-only) and gains the note.
    quote_text = doc[0].get_text()
    assert "CAD$100.00" in quote_text  # source number unchanged
    assert "Copper straps adder" in quote_text  # note stamped above the price
    doc.close()


def test_multi_coil_stamps_superseded_watermark_on_source_drawing_page() -> None:
    # p0 quote, p1 report, p2 drawing. Our drawing inserts at output index 3; the
    # source drawing page (output index 2) gets the large "revised next page" stamp.
    source = _make_text_pdf(
        [
            "COIL QUOTE\nTagged: CDXC-1\nCost Each: CAD$100.00",
            "DX COIL REPORT\nCDXC-1\nspecs",
            "CDXC-1\n47 F.L.\n4.33 FIN",
        ]
    )
    coils = [{"tag": "CDXC-1", "coil_type": "DX", "our_svg": _SVG}]
    result = assemble_multi_coil_package(source_pdf=source, coils=coils)
    doc = fitz.open(stream=base64.b64decode(result.pdf_base64), filetype="pdf")
    # Source drawing page (index 2) is marked superseded, pointing to the next page.
    assert "SUPERSEDED" in doc[2].get_text()
    assert "next page" in doc[2].get_text()
    # Quote page (0) and our inserted drawing (3) are NOT marked superseded.
    assert "SUPERSEDED" not in doc[0].get_text()
    assert "SUPERSEDED" not in doc[3].get_text()
    assert "REVIEW AID - NOT FOR MANUFACTURING" in doc[3].get_text()
    doc.close()


def test_multi_coil_superseded_watermark_can_be_disabled() -> None:
    source = _make_text_pdf(
        ["COIL QUOTE\nTagged: CDXC-1\nCost Each: CAD$1.00", "report", "CDXC-1\nF.L."]
    )
    result = assemble_multi_coil_package(
        source_pdf=source,
        coils=[{"tag": "CDXC-1", "coil_type": "DX", "our_svg": _SVG}],
        mark_source_superseded=False,
    )
    doc = fitz.open(stream=base64.b64decode(result.pdf_base64), filetype="pdf")
    assert "SUPERSEDED" not in doc[2].get_text()
    doc.close()


# --------------------------------------------------------------------------- #
# Multi-PAGE quote schedule: a many-coil quote spills its pricing rows onto a
# 2nd quote page that carries 'Cost Each' rows but NO 'COIL QUOTE' header. Every
# such page must be stamped, and each coil's note must land on the page that
# actually prices it — never only the first page (the reported bug).
# --------------------------------------------------------------------------- #
def _two_quote_page_source() -> bytes:
    """p0: COIL QUOTE + CDXC-1/2 priced. p1 (no COIL QUOTE): CDXC-3/4 priced.

    Followed by one drawing page per coil so insertion leaves the two quote pages
    at output indices 0 and 1.
    """
    return _make_text_pdf(
        [
            "COIL QUOTE\nTagged: CDXC-1\nCost Each: CAD$100.00\n"
            "Tagged: CDXC-2\nCost Each: CAD$200.00",
            # NOTE: no 'COIL QUOTE' header on the continuation quote page.
            "Tagged: CDXC-3\nCost Each: CAD$300.00\nTagged: CDXC-4\nCost Each: CAD$400.00",
            "CDXC-1\n47 F.L.\n4.33 FIN",
            "CDXC-2\n47 F.L.\n4.33 FIN",
            "CDXC-3\n47 F.L.\n4.33 FIN",
            "CDXC-4\n47 F.L.\n4.33 FIN",
        ]
    )


def _four_dx_coils() -> list[dict]:
    return [
        {"tag": f"CDXC-{i}", "coil_type": "DX", "our_svg": _SVG, "price_note": f"STRAP-{i}"}
        for i in (1, 2, 3, 4)
    ]


def test_multi_page_quote_stamps_every_page() -> None:
    result = assemble_multi_coil_package(source_pdf=_two_quote_page_source(), coils=_four_dx_coils())
    # Both quote pages are detected and stamped (keyed on 'Cost Each', not 'COIL QUOTE').
    assert result.quote_page_indices == [0, 1]
    assert result.quote_page_index == 0  # back-compat scalar = first quote page
    assert result.inserted_coil_count == 4
    doc = fitz.open(stream=base64.b64decode(result.pdf_base64), filetype="pdf")
    p0, p1 = doc[0].get_text(), doc[1].get_text()
    # Every coil got its note, on the page that prices it — not just page 0.
    assert "STRAP-1" in p0 and "STRAP-2" in p0
    assert "STRAP-3" in p1 and "STRAP-4" in p1
    doc.close()


def test_multi_page_quote_note_lands_on_owning_page() -> None:
    # A note for a coil priced on quote page 1 must NOT be stamped on page 0.
    result = assemble_multi_coil_package(source_pdf=_two_quote_page_source(), coils=_four_dx_coils())
    doc = fitz.open(stream=base64.b64decode(result.pdf_base64), filetype="pdf")
    p0, p1 = doc[0].get_text(), doc[1].get_text()
    assert "STRAP-3" in p1 and "STRAP-3" not in p0
    assert "STRAP-1" in p0 and "STRAP-1" not in p1
    doc.close()


def test_multi_page_quote_boundary_spill_coil() -> None:
    # The real 2843-file failure: a coil's TAG prints at the bottom of quote page 0
    # but its 'Cost Each' pricing row spilled to the TOP of quote page 1, with a second
    # coil also priced on page 1. Pass 1 places the page-1 coil on its own row; pass 2
    # absorbs the boundary coil onto page 1's leftover top row — never onto page 0, and
    # without displacing the page-1 coil.
    source = _make_text_pdf(
        [
            # p0: CDXC-1 priced; RHHGRC-1 TAG only (its cost spilled to p1).
            "COIL QUOTE\nTagged: CDXC-1\nCost Each: CAD$100.00\nTagged: RHHGRC-1",
            # p1 (no COIL QUOTE): RHHGRC-1's spilled cost row at top, then RHHGRC-2 priced.
            "Cost Each: CAD$150.00\nTagged: RHHGRC-2\nCost Each: CAD$250.00",
        ]
    )
    coils = [
        {"tag": "CDXC-1", "coil_type": "DX", "price_note": "STRAP-CDXC1"},
        {"tag": "RHHGRC-1", "coil_type": "HGRH", "price_note": "STRAP-RHHGRC1"},
        {"tag": "RHHGRC-2", "coil_type": "HGRH", "price_note": "STRAP-RHHGRC2"},
    ]
    result = assemble_multi_coil_package(source_pdf=source, coils=coils)
    assert result.quote_page_indices == [0, 1]
    doc = fitz.open(stream=base64.b64decode(result.pdf_base64), filetype="pdf")
    p0, p1 = doc[0].get_text(), doc[1].get_text()
    # Boundary coil's note is on page 1 (where it is priced), NOT page 0 (where its tag is).
    assert "STRAP-RHHGRC1" in p1 and "STRAP-RHHGRC1" not in p0
    # The page-1 coil keeps its own note (not displaced by the boundary coil).
    assert "STRAP-RHHGRC2" in p1
    # Page 0 carries only its own coil's note.
    assert "STRAP-CDXC1" in p0
    doc.close()


def test_multi_page_quote_alias_match() -> None:
    # Reviewed tag RHHGRH-4; the source continuation page spells it RHHGRC-4. Alias-aware
    # matching must still stamp its note on the continuation page (never dropped).
    source = _make_text_pdf(
        [
            "COIL QUOTE\nTagged: CDXC-1\nCost Each: CAD$100.00",
            "Tagged: RHHGRC-4\nCost Each: CAD$400.00",
        ]
    )
    coils = [
        {"tag": "CDXC-1", "coil_type": "DX", "price_note": "STRAP-CDXC1"},
        {"tag": "RHHGRH-4", "coil_type": "HGRH", "price_note": "STRAP-RH4"},
    ]
    result = assemble_multi_coil_package(source_pdf=source, coils=coils)
    doc = fitz.open(stream=base64.b64decode(result.pdf_base64), filetype="pdf")
    assert "STRAP-RH4" in doc[1].get_text()  # matched via RHHGRH-4 <-> RHHGRC-4 alias
    doc.close()


def test_single_quote_page_indices_unchanged() -> None:
    # Single-quote-page package: indices collapse to [0] and the scalar stays 0.
    source = _make_text_pdf(
        ["COIL QUOTE\nTagged: CDXC-1\nCost Each: CAD$100.00", "CDXC-1\nF.L."]
    )
    result = assemble_multi_coil_package(
        source_pdf=source,
        coils=[{"tag": "CDXC-1", "coil_type": "DX", "our_svg": _SVG, "price_note": "STRAP-1"}],
    )
    assert result.quote_page_indices == [0]
    assert result.quote_page_index == 0


def test_quote_note_right_edge_aligns_with_item_total_figure() -> None:
    # A pricing line with a far-right 'Item 1 Total' figure (mirrors the real quote
    # layout). The stamped note's right edge must align with that figure's right edge
    # so its trailing 'NN.00' sits directly above the total's trailing 'NN.00'.
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((40, 80), "Tagged: CDXC-1")
    page.insert_text((40, 120), "Cost Each: CAD$1,952.00")
    page.insert_text((300, 120), "Item 1 Total:")
    page.insert_text((480, 120), "CAD$1,952.00")  # far-right total figure

    note = "Copper Strap Adder CAD$50.00"
    _stamp_quote_price_notes(page, [{"tag": "CDXC-1", "price_note": note}])

    words = page.get_text("words")  # (x0, y0, x1, y1, word, ...)
    # The far-right total figure on the pricing line (y0 ~ 120 baseline region).
    price_x1 = max(w[2] for w in words if w[4] == "CAD$1,952.00")
    # The note is stamped on its own band just above the line; find its rightmost word.
    note_words = [w for w in words if w[1] < 118 and "50.00" in w[4]]
    assert note_words, "note '50.00' token not found above the pricing line"
    note_x1 = max(w[2] for w in note_words)
    # Right edges coincide within a couple points (glyph-extent vs text-length slack).
    assert abs(note_x1 - price_x1) <= 3.0, (note_x1, price_x1)
    doc.close()


def test_multi_coil_safety_flags_never_relaxed() -> None:
    source = _make_text_pdf(["COIL QUOTE\nTagged: CDXC-1\nCost Each: CAD$1.00", "CDXC-1\nF.L."])
    result = assemble_multi_coil_package(
        source_pdf=source,
        coils=[{"tag": "CDXC-1", "coil_type": "DX", "our_svg": _SVG, "price_note": "x"}],
    )
    assert result.export_allowed is False
    assert result.production_drawing_approval_claimed is False
    assert result.raw_private_data_returned is False
    assert result.watermarked is True


def test_multi_coil_rejects_empty_source() -> None:
    with pytest.raises(ValueError):
        assemble_multi_coil_package(source_pdf=b"", coils=[])
