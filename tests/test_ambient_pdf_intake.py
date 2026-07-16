"""Phase 2 — Ambient PDF parser (text-level; sanitized fixtures, no committed PDF).

The parser is exercised at the text->candidate seam (``_parse_report_page`` /
``parse_ambient_pdf`` given synthetic page text), so no customer PDF is needed and the
Btu/hr->MBH + label mapping logic is verified directly. The real PDF-bytes path reuses
the already-tested ``submittal.pdf_intake`` text extraction.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ambient.pdf_intake import _parse_report_page

# Sanitized DX Coil Report page text (neutral project; real structure/numbers).
_DX_TEXT = """DX Coil Report
Customer Name Date 7/13/2026
Contact Reference SANITIZED
Model Number: 3DX15.00x47.00-5R-9FPI-LH Tag: 590004 / CDXC-1
Coil Data
Finned Height 15 In
Finned Length 47 In
Rows Deep 5
Number Of Feeds 9
Fins Per Inch 9
Tube Diameter 3/8 (1 x 0.866)
Supply Connection Size 1/2"
Return Connection Size 1 1/8"
Tube Material Copper 0.016
Fin Material Aluminum 0.0075
Fin Surface Sine
Face Area 4.9 ft
System Type Intertwined (x2)
Coil Weight 77.7 lb
Coil Weight (Wet) 82.15 lb
Air Data
Total Air Flow 2200 SCFM
Standard Face Velocity 449.36 FPM
Entering Dry Bulb 90.8 F
Entering Wet Bulb 76.2 F
Leaving Dry Bulb 54.4 F
Air Pressure Drop 0.78 inWG
Capacity(All Coils) 171514 Btu/hr
Sensible Capacity(All Coils) 86625 Btu/hr
Refrigerant Data
Refrigerant R32
Evaporating Temperature 43 F
Superheat 9 F
Refrigerant Pressure Drop 6.01 PSIG
Version:1.0.10
"""

_CONDENSING_TEXT = """Condensing Coil Report
Model Number: 3C15.00x47.00-2R-11FPI-LH Tag: 590005 / RHHGRC-1
Coil Data
Finned Height 15 In
Finned Length 47 In
Rows Deep 2
Number Of Feeds 3
Tube Material Copper 0.016
Air Data
Capacity(All Coils) 50225 Btu/hr
Refrigerant Data
Refrigerant R32
Vapor Temperature 140 F
Condensing Temperature 115 F
Subcooling 18 F
Refrigerant Pressure Drop 1.21 PSIG
"""


def test_dx_report_parses_key_fields():
    c = _parse_report_page(_DX_TEXT, page_number=1, source_id="T")
    assert c is not None
    assert c.tag.value == "CDXC-1"
    assert c.coil_type.value == "DX COIL"
    assert c.geometry["rows_deep"].value == 5.0
    assert c.geometry["number_of_feeds"].value == 9.0
    assert c.geometry["tube_thickness_in"].value == 0.016
    assert c.materials_construction["fin_surface"].value == "Sine"


def test_dx_capacity_btuh_normalized_to_mbh():
    c = _parse_report_page(_DX_TEXT, page_number=1, source_id="T")
    cap = c.performance["nominal_cooling_capacity_mbh"]
    assert cap.unit == "MBH"
    assert abs(cap.value - 171.514) < 1e-9  # 171514 Btu/hr / 1000
    assert any("Btu/hr" in n for n in cap.notes)


def test_condensing_report_has_reheat_temps():
    c = _parse_report_page(_CONDENSING_TEXT, page_number=1, source_id="T")
    assert c.tag.value == "RHHGRC-1"
    assert c.coil_type.value == "HGRH COIL"
    assert c.refrigerant_conditions["condensing_temp_f"].value == 115.0
    assert c.refrigerant_conditions["subcooling_f"].value == 18.0
    # No evaporating temp on a condensing coil -> omitted, not invented.
    assert "evaporating_temp_f" not in c.refrigerant_conditions


def test_mbh_labeled_capacity_is_not_divided():
    text = _DX_TEXT.replace("Capacity(All Coils) 171514 Btu/hr", "Capacity(All Coils) 171.5 MBH")
    c = _parse_report_page(text, page_number=1, source_id="T")
    cap = c.performance["nominal_cooling_capacity_mbh"]
    assert cap.unit == "MBH"
    assert abs(cap.value - 171.5) < 1e-9  # NOT divided by 1000


def test_every_value_is_review_required():
    c = _parse_report_page(_DX_TEXT, page_number=1, source_id="T")
    for grp in (c.geometry, c.airside_conditions, c.refrigerant_conditions, c.performance, c.materials_construction, c.connections, c.manufacturing_options):
        for fv in grp.values():
            assert fv.review_required is True
            assert fv.status == "review_required"
            assert fv.source_evidence  # never a bare value


def test_non_report_text_returns_none():
    assert _parse_report_page("Coilmaster drawing page\nROWS X FH FL ...", page_number=2, source_id="T") is None


def test_report_page_with_zero_fields_is_loud_not_silent():
    # A report header + tag but no parseable data lines -> loud ocr_blocked note, not
    # a silently-empty candidate.
    text = "DX Coil Report\nModel Number: X Tag: 1 / CDXC-9\n(cid:12)(cid:44) garbage\n"
    c = _parse_report_page(text, page_number=1, source_id="T")
    assert c is not None
    assert c.tag.value == "CDXC-9"
    assert any(n.startswith("ambient_ocr_blocked") for n in c.notes)
