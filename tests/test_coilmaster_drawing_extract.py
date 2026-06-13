"""Tests for CoilMaster drawing + cover-page extraction (synthetic text)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.submittal.coilmaster_drawing_extract import (  # noqa: E402
    extract_coilmaster_drawing,
    extract_drawing_dimensions,
    extract_feeds_circuits,
    extract_unit_size,
    parse_model_number,
    product_for_unit_size,
)

# Mirrors the real CDXC-1.pdf text layout (values glued to labels).
DRAWING_TEXT = (
    "15 FL\n12 FH13.25 CH\n18.00 CL1.50 HF 1.50 RF0.63 TF\n0.63 BF5.50 CD\n"
    "20.25 OAL1.75 RB\n2.00 O2\n0.63 R23.00 I12.75 S13.50 HD28.00 SL2\n4.50 HDx1\n"
    "2 Feed / 24 Pass\n13 Fins Per Inch\n"
    'RETURN CONN SIZE\n0.625" OD Header\n'
    "DX-F-S-04-13-12.00x15.00-L\nTag: CDXC-1\n"
)

COVER_TEXT = "1 CDXC- 1 DXC Cooling A16_V_I_ERV LH\n"


def test_lone_dot_callout_does_not_crash_extraction() -> None:
    # HG drawings can emit a lone "." callout; float(".") used to crash extraction.
    text = "12 FH\n. SL2\n5.50 CD\nTag: RHHGRC-1\n"
    dims = extract_drawing_dimensions(text)
    assert dims["FH"] == 12.0
    assert dims["CD"] == 5.5
    assert "SL2" not in dims  # the "." callout is skipped, not a value
    out = extract_coilmaster_drawing(text)
    assert out["dimensions"]["FH"] == 12.0


def test_dimensions_extract_including_glued_fh() -> None:
    d = extract_drawing_dimensions(DRAWING_TEXT)
    assert d["FH"] == 12.0   # glued to next value, still parsed
    assert d["FL"] == 15.0
    assert d["CD"] == 5.5
    assert d["CH"] == 13.25
    assert d["HDx1"] == 4.5
    assert d["HD2"] == 3.5
    assert d["SL2"] == 8.0
    assert d["TF"] == 0.63


def test_model_number_parse() -> None:
    m = parse_model_number(DRAWING_TEXT)
    assert m["coil_code"] == "DX"
    assert m["rows"] == 4 and m["fpi"] == 13
    assert m["fh"] == 12.0 and m["fl"] == 15.0
    assert m["hand"] == "LH"


def test_full_drawing_extract() -> None:
    out = extract_coilmaster_drawing(DRAWING_TEXT)
    assert out["rows"] == 4
    assert out["return_conn_size"] == "0.625"
    assert out["passes"] == 24
    assert out["tag"] == "CDXC-1"
    assert out["dimensions"]["CD"] == 5.5


def test_cover_unit_size_to_product() -> None:
    size = extract_unit_size(COVER_TEXT)
    assert size == "A16"
    assert product_for_unit_size(size) == "NOVA"  # A16 is in R-076 NOVA list


# Mirrors the real DX_2 multi-header layout (2 circuits).
MULTI_HEADER_TEXT = (
    "34 FL\n26 FH27.25 CH\n37.00 CL1.50 HF 1.50 RF0.63 TF\n0.63 BF5.50 CD\n"
    "39.25 OAL1.75 RB\n2.00 O2\n1.13 R22.00 O4\n3.75 R43.00 I11.88 S1\n"
    "3.00 I33.63 S33.50 HD28.00 SL24.50 HDx1\n"
    "14 Passes per Feed\nC1: 3 Feed C2: 4 Feed\n"
)


def test_multi_header_values_not_corrupted() -> None:
    d = extract_drawing_dimensions(MULTI_HEADER_TEXT)
    assert d["HDx1"] == 4.5   # was 24.5 before the full label set
    assert d["HD2"] == 3.5 and d["SL2"] == 8.0
    assert d["I1"] == 3.0 and d["I3"] == 3.0      # both circuits
    assert d["S1"] == 1.88 and d["S3"] == 3.63
    assert d["O2"] == 2.0 and d["O4"] == 2.0
    assert d["R2"] == 1.13 and d["R4"] == 3.75


def test_multi_circuit_feeds_summed() -> None:
    fc = extract_feeds_circuits(MULTI_HEADER_TEXT)
    assert fc["circuits"] == 2
    assert fc["feeds"] == 7          # 3 + 4
    assert fc["passes_per_feed"] == 14


def test_single_feed_glued_to_rb_is_unglued() -> None:
    # "1.752 Feed / 24 Pass" with RB=1.75 -> feeds=2 (real text is space-separated).
    fc = extract_feeds_circuits("1.50 1.50 1.752 Feed / 24 Pass\n", rb=1.75)
    assert fc["circuits"] == 1
    assert fc["feeds"] == 2
    assert fc["passes"] == 24


def test_product_for_other_sizes() -> None:
    assert product_for_unit_size("V40") == "VENTUM_PLUS"
    assert product_for_unit_size("H15") == "VENTUM_H"
    assert product_for_unit_size("24") == "TERRA"
    assert product_for_unit_size("ZZZ") is None
