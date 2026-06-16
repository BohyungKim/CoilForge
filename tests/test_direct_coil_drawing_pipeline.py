"""End-to-end Track A test: coil inputs -> header engine -> draft drawing.

Validates the DX / single-circuit / LH slice against the EZC-0001 as-built
values (Case/#3/EZC-0001 CDXC-1.txt): CD=5.5, TF/BF=0.625, RB=1.75,
distributor HD=4.5, suction HD=3.5, dist I=3, return SL=8, dist ext=6.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.services.direct_coil_drawing_pipeline import (  # noqa: E402
    build_drawing_slots,
    build_header_request,
    run_direct_coil_drawing_pipeline,
)

# EZC-0001 geometry-sourced (non-engine) slots.
EZC0001_GEOMETRY_SLOTS = {
    "slot.FH": 12.0,
    "slot.FL": 15.0,
    "slot.CH": 13.25,
    "slot.CL": 18.0,
    "slot.ROWS": 4,
    "slot.TAG": "CDXC-1",
}


def _run_ezc0001():
    # product_type/unit_size come from submittal context (Track B); NOVA matches
    # the as-built TF/BF=0.625. Size B20 is a valid NOVA size (geometry/header
    # values for this DX slice do not depend on size).
    return run_direct_coil_drawing_pipeline(
        coil_type="DX",
        product_type="NOVA",
        unit_size="B20",
        hand="LH",
        header_type="Header 1",
        rows=4,
        feeds=2,
        circuits=1,
        suction_conn_size=0.625,
        geometry_slots=EZC0001_GEOMETRY_SLOTS,
    )


def test_step1_input_bridge_builds_request() -> None:
    req = build_header_request(
        coil_type="DX", product_type="NOVA", unit_size="B20",
        rows=4, feeds=2, circuits=1, suction_conn_size=0.625, handing="LH",
    )
    assert req.type_of_coil.value == "DX"
    assert req.product_type.value == "NOVA"
    assert req.rows == 4 and req.circuits == 1 and req.suction_conn_size == 0.625


def test_step2_header_values_match_ezc0001_asbuilt() -> None:
    r = _run_ezc0001()
    v = r.header_response.values
    assert v["casing_depth"].value == 5.5          # as-built CD
    assert v["top_flange"].value == 0.625          # as-built TF
    assert v["bottom_flange"].value == 0.625       # as-built BF
    assert v["return_bend"].value == 1.75          # as-built RB
    assert v["dist_hd"].value == 4.5               # as-built HDx1 (distributor)
    assert v["suction_hd"].value == 3.5            # as-built HD2 (return/suction)
    assert v["dist_i"].value == 3                  # as-built I1
    assert v["suction_sl"].value == 8              # as-built return SL
    assert v["dist_extension"].value == 6          # as-built dist ext
    assert v["header_flange"].value == 1.5
    assert v["return_flange"].value == 1.5


def test_step3_engine_values_mapped_to_slots() -> None:
    r = _run_ezc0001()
    s = r.slot_values
    assert s["slot.CD"] == 5.5
    assert s["slot.TF"] == 0.625
    assert s["slot.BF"] == 0.625
    assert s["slot.RB"] == 1.75
    assert s["slot.HDx1"] == 4.5
    assert s["slot.HD2"] == 3.5
    assert s["slot.I1"] == 3
    assert s["slot.SL2"] == 8
    assert "Copper Straps Required." in s["slot.NOTES"]
    # geometry slots passed through
    assert s["slot.FH"] == 12.0 and s["slot.TAG"] == "CDXC-1"


def test_step4_template_selected_and_svg_rendered() -> None:
    r = _run_ezc0001()
    assert r.template_found is True
    assert r.template_id == "coilmaster_dx_lh_header1"
    assert r.svg and ("5.5" in r.svg) and ("4.5" in r.svg)
    # review aid, never manufacturing
    assert r.population_status in (
        "generated_review_aid",
        "generated_with_review_required_values",
    )


def test_all_dimension_labels_are_value_driven() -> None:
    """Every dimension slot is driven by a mechanical value (engine/formula)."""
    r = _run_ezc0001()
    dimension_slots = [
        "slot.CD", "slot.I1", "slot.O2", "slot.S1", "slot.R2", "slot.HD2",
        "slot.HDx1", "slot.SL2", "slot.TF", "slot.BF", "slot.HF", "slot.RF",
        "slot.RB", "slot.FH", "slot.FL", "slot.CH", "slot.CL", "slot.OAL",
    ]
    for slot in dimension_slots:
        assert r.slot_values.get(slot) is not None, slot
    # spot-check recovered/derived ones against the as-built coil.
    assert r.slot_values["slot.CH"] == 13.25   # FH+TF+BF
    assert r.slot_values["slot.CL"] == 18.0     # FL+3
    assert r.slot_values["slot.S1"] == 2.75     # CD/2
    assert r.slot_values["slot.RB"] == 1.75


def test_material_and_title_slots_wired_from_coil_data() -> None:
    ez = {"Geometry": {
        "FH": 12, "FL": 15, "CD": 5.5, "Nrows": 4, "Nfeeds": 2, "NumCircuits": 1,
        "ReturnConnectionsSize": 0.625,
        "Distributors": ["501-2-3/16-1.5"],
        "MultiCircuitCoilFeeds": [2], "MultiCircuitCoilPasses": [24],
        "Headers": [{"ID": 1, "IsSupply": True, "HD": 4.5, "IO": [3.0], "SR": 2.75},
                    {"ID": 2, "IsSupply": False, "HD": 3.5, "IO": [2.0], "SR": 0.625, "SL": [8.0]}],
    }}
    r = run_direct_coil_drawing_pipeline(
        coil_type="DX", product_type="NOVA", unit_size="B20", hand="LH",
        rows=4, feeds=2, circuits=1, suction_conn_size=0.625, ez_json=ez,
        geometry_slots={"slot.FH": 12, "slot.FL": 15, "slot.TAG": "CDXC-1"},
        model_number="CDXC-1-DX",
    )
    assert r.slot_values["slot.CIRCUITING"] == "2 Feed / 24 Pass"
    assert r.slot_values["slot.DISTRIBUTORS"] == "501-2-3/16-1.5"
    assert r.slot_values["slot.RETURN_CONN_SIZE"] == 0.625
    assert r.slot_values["slot.MODEL_NUMBER"] == "CDXC-1-DX"


def test_step4_review_items_surfaced_not_silently_drawn() -> None:
    r = _run_ezc0001()
    # MEDIUM/blocked/missing must be surfaced for review, never auto-filled.
    assert r.review_items
    # casing width/height need `application` (not provided) -> review item.
    assert any("casing" in item or "application" in item for item in r.review_items)


# --------------------------------------------------------------------------- #
# Category-aware engine->slot bridge: the per-header geometry (I/O/HD/SL) must
# resolve for every coil category, not just DX. The rule engine names this
# geometry differently per category, so the bridge selects the right source
# field instead of assuming DX's dist_*/suction_* names. Regression for the bug
# where HGRH/CWC/HWC left I/O/HD/SL/HDx blocked even with the engine running.
# --------------------------------------------------------------------------- #
def _slots(coil_type: str):
    slots, _ = build_drawing_slots(
        coil_type=coil_type, product_type="NOVA", unit_size="B20",
        rows=4, feeds=2, circuits=1, suction_conn_size=0.625,
        finned_height=12.0, finned_length=15.0,
    )
    return slots


def test_dx_per_header_slots_unchanged() -> None:
    """DX still sources from dist_*/suction_* — exact as-built values preserved."""
    s = _slots("DX")
    assert s["slot.I1"] == 3          # dist_i
    assert s["slot.HDx1"] == 4.5      # dist_hd (distributor present for DX)
    assert s["slot.O2"] == 2          # suction_io
    assert s["slot.HD2"] == 3.5       # suction_hd
    assert s["slot.SL2"] == 8         # suction_sl


def test_hgrh_per_header_slots_resolved_from_category_fields() -> None:
    """HGRH sources supply_io/return_io/hd/return_sl; no distributor -> no HDx."""
    s = _slots("HGRH")
    assert s["slot.I1"] == 2          # supply_io
    assert s["slot.O2"] == 2          # return_io
    assert s["slot.HD2"] == 3.5       # hd
    assert s["slot.SL2"] == 8         # return_sl
    assert "slot.HDx1" not in s       # HGRH has no distributor header


def test_cwc_per_header_slots_resolved_from_shared_geometry() -> None:
    """CWC/HWC carry a single shared header geometry (io/hd/sl); no distributor."""
    s = _slots("CWC")
    assert s["slot.I1"] == 2.3125     # io
    assert s["slot.O2"] == 2.3125     # io (shared)
    assert s["slot.HD2"] == 4         # hd
    assert s["slot.SL2"] == 8         # sl
    assert "slot.HDx1" not in s
