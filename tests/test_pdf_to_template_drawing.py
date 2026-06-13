"""PDF text -> linked, populated template-first drawing."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from io import BytesIO  # noqa: E402

from coilforge.submittal.pdf_to_template_drawing import (  # noqa: E402
    pdf_text_to_template_drawing,
    slots_from_drawing_extract,
)
from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    run_pdf_to_drawing_workflow,
)

# Single-header DX drawing text (mirrors CDXC-1.pdf).
DX1_TEXT = (
    "15 FL\n12 FH13.25 CH\n18.00 CL1.50 HF 1.50 RF0.63 TF\n0.63 BF5.50 CD\n"
    "20.25 OAL1.75 RB\n2.00 O2\n0.63 R23.00 I12.75 S13.50 HD28.00 SL2\n4.50 HDx1\n"
    "1.50 1.752 Feed / 24 Pass\n13 Fins Per Inch\n"
    'RETURN CONN SIZE\n0.625" OD Header\n'
    "DX-F-S-04-13-12.00x15.00-L\nTag: CDXC-1\n"
)
COVER = "1 CDXC- 1 DXC Cooling A16_V_I_ERV LH\n"

# Multi-header DX (2 circuits) -> Header 2 (links, not seeded).
DX2_TEXT = (
    "34 FL\n26 FH27.25 CH\n37.00 CL1.50 HF 1.50 RF0.63 TF\n0.63 BF5.50 CD\n"
    "39.25 OAL1.75 RB\n2.00 O2\n1.13 R22.00 O4\n3.75 R43.00 I11.88 S1\n"
    "3.00 I33.63 S33.50 HD28.00 SL24.50 HDx1\n"
    "14 Passes per Feed\nC1: 3 Feed C2: 4 Feed\n"
    "DX-F-S-04-14-26.00x34.00-R\nTag: CDXC-2\n"
)


def test_slots_map_extracted_dims_to_slot_ids() -> None:
    from coilforge.submittal.coilmaster_drawing_extract import extract_coilmaster_drawing

    slots = slots_from_drawing_extract(extract_coilmaster_drawing(DX1_TEXT))
    assert slots["slot.CD"] == 5.5
    assert slots["slot.HDx1"] == 4.5
    assert slots["slot.FH"] == 12.0
    assert slots["slot.TAG"] == "CDXC-1"


def test_dx1_pdf_links_and_renders() -> None:
    out = pdf_text_to_template_drawing(DX1_TEXT, cover_text=COVER)
    assert out["extracted"]["coil_category"] == "DX"
    assert out["extracted"]["circuits"] == 1
    assert out["unit_size"] == "A16" and out["product_type"] == "NOVA"
    assert out["template_id"] == "coilmaster_dx_lh_header1"
    assert out["generation_allowed"] is True
    assert out["svg"] and "5.5" in out["svg"]
    assert out["export_allowed"] is False


def test_dx2_links_and_renders_seeded_header2() -> None:
    out = pdf_text_to_template_drawing(DX2_TEXT)
    assert out["extracted"]["circuits"] == 2 and out["extracted"]["feeds"] == 7
    assert out["template_id"] == "coilmaster_dx_rh_header2"
    assert out["template_found"] is True
    # DX Header 2 RH is now seeded (from EZC-0011's real EZ drawing) and renders.
    assert out["generation_allowed"] is True
    assert out["svg"] and "5.5" in out["svg"]
    assert out["export_allowed"] is False
    assert out["slot_values"]["slot.CD"] == 5.5
    assert out["slot_values"]["slot.HDx1"] == 4.5


def test_workflow_includes_populated_template_drawing() -> None:
    """The intake workflow surfaces a populated template_drawing for a DX1 PDF."""
    workflow = run_pdf_to_drawing_workflow(_make_text_pdf(DX1_TEXT.splitlines()))
    template_drawing = workflow["template_drawing"]
    assert "error" not in template_drawing
    assert template_drawing["template_id"] == "coilmaster_dx_lh_header1"
    assert template_drawing["generation_allowed"] is True
    assert template_drawing["svg"] and "5.5" in template_drawing["svg"]
    assert template_drawing["export_allowed"] is False
    assert template_drawing["extracted"]["tag"] == "CDXC-1"


def _make_text_pdf(lines: list[str]) -> bytes:
    """Minimal single-page text PDF (mirrors the intake test helper)."""
    text_ops = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            text_ops.append("0 -16 Td")
        text_ops.append(f"({safe}) Tj")
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
    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = []
    for obj in objects:
        offsets.append(output.tell())
        output.write(obj)
    xref_offset = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return output.getvalue()
