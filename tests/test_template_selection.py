"""Extracted coil selection -> correct drawing template link."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.services.template_selection import (  # noqa: E402
    classify_template_request,
    link_drawing_template,
)
from coilforge.workflows.submittal_to_drawing import _detect_hgbp  # noqa: E402


def _dx(circuits, hand=1, asc=False):
    return {"Geometry": {
        "NumCircuits": circuits, "CoilHand": hand, "isASC": asc,
        "Headers": [{"ID": 1, "IsSupply": True, "IsASC": asc}],
    }}


def test_dx_single_circuit_links_header1() -> None:
    out = link_drawing_template(coil_type="DX", ez_json=_dx(1, hand=1))
    assert out["selection"]["header_type"] == "Header 1"
    assert out["selection"]["coil_hand"] == "LH"
    assert out["template_id"] == "coilmaster_dx_lh_header1"
    assert out["generation_allowed"] is True  # the one seeded template


def test_dx_two_circuit_rh_links_header2() -> None:
    out = link_drawing_template(coil_type="DX", ez_json=_dx(2, hand=0))
    assert out["selection"]["header_type"] == "Header 2"
    assert out["selection"]["coil_hand"] == "RH"
    assert out["template_id"] == "coilmaster_dx_rh_header2"


def test_dx_three_circuit_links_header3() -> None:
    out = link_drawing_template(coil_type="DX", ez_json=_dx(3, hand=1))
    assert out["template_id"] == "coilmaster_dx_lh_header3"


def test_dx_hgbp_detected_from_asc_flag() -> None:
    out = link_drawing_template(coil_type="DX", ez_json=_dx(1, hand=1, asc=True))
    assert out["selection"]["special_feature"] == "HGBP"
    assert out["template_id"] == "coilmaster_dx_lh_hgbp"


# --- _detect_hgbp: the submittal-text sibling of the EZ-JSON isASC flag above. ---
# The EZ JSON states HGBP as a boolean; the drawing states it as an ASC **count**
# inside the distributor string. Both live here so the two readings stay visible.


@pytest.mark.parametrize(
    "text",
    [
        "(1)501-2-3/16-1.5(1 ASC)",  # real distributor string, HGBP selected
        "(1)501-2-3/16-1.75(2 ASC)",
        "(1)501-2-3/16-1.5(10 ASC)",
        "HGBP VALVE - DANFOSS AXV-H and hot-gas bypass stub-out on coils adder",
        "Hot Gas Bypass",
        "Cover option: hot-gas bypass (HGBP) adder stated on cover page 3",
    ],
)
def test_detect_hgbp_true(text: str) -> None:
    assert _detect_hgbp(text) is True


@pytest.mark.parametrize(
    "text",
    [
        # "0 ASC" means NO hot gas bypass -- the count, not a flag. This exact string
        # reaches _detect_hgbp via manufacturing_options.distributor_notes.
        "(1)501-2-3/16-1.5(0 ASC)",
        "DISTRIBUTOR 1 HAS 6\" EXTENSION",
        "economizer bypass damper",
        "CASCADE control sequence",
        "ascending order",
        "",
    ],
)
def test_detect_hgbp_false(text: str) -> None:
    assert _detect_hgbp(text) is False


def test_detect_hgbp_zero_asc_is_not_hot_gas_bypass_across_joined_texts() -> None:
    """The real shape: coil_type + notes + the joined manufacturing_options blob.
    A "(0 ASC)" distributor note must NOT route an ordinary DX coil to HGBP."""
    assert (
        _detect_hgbp(
            "DX COIL",
            "Cover product/model code: DXM05C13-12.00x15.00L",
            "(1)501-2-3/16-1.5(0 ASC) DISTRIBUTOR 1 HAS 6\" EXTENSION",
        )
        is False
    )


def test_hgrh_standard_links_header1() -> None:
    pd = {"PhysicalData": {"coilStyle": "standard"},
          "Construction": {"coilHand": "leftHand"}}
    out = link_drawing_template(coil_type="HGRH", ez_json=pd)
    assert out["selection"]["header_type"] == "Header 1"
    assert out["template_id"] == "coilmaster_hgrh_lh_header1"


def test_hgrh_facesplit2_links_header2() -> None:
    pd = {"PhysicalData": {"coilStyle": "faceSplit2Circ"},
          "Construction": {"coilHand": "leftHand"}}
    out = link_drawing_template(coil_type="HGRH", ez_json=pd)
    assert out["template_id"] == "coilmaster_hgrh_lh_header2"


def test_cwc_and_hwc_link_their_buckets() -> None:
    cwc = link_drawing_template(coil_type="CWC", coil_hand="LH")
    assert cwc["template_id"] == "coilmaster_cwc_lh"
    hwc = link_drawing_template(coil_type="HWC", coil_hand="LH")
    assert hwc["template_id"] == "coilmaster_hwc_lh"


def test_explicit_hand_overrides_when_no_json() -> None:
    req = classify_template_request(coil_type="DX", coil_hand="RH")
    assert req.coil_hand == "RH" and req.header_type == "Header 1"
