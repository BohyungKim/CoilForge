"""Multi-header (1HD-4HD) drawing-parameter mapping.

The web Drawing Parameters grid has a second-header column (I2/S2/O2/R2/HD2/ZD2)
that was always "unmapped". These tests cover the translation layer that bridges
the UI's *logical* header keys (I2 = "header assembly 2") to the engine's
*parity-encoded* per-header slots (slot.I3/O4 = circuit 2), generalized to N
headers for DX and HGRH, with ZD held at the owner-fixed constant 4.5.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.services.direct_coil_drawing_pipeline import build_drawing_slots  # noqa: E402
from coilforge.services.header_prepopulate_engine import round_eighth  # noqa: E402
from coilforge.services.drawing_param_resolver import (  # noqa: E402
    ZD_CONSTANT,
    _header_slot,
    is_multi_header_param_key,
    multi_header_logical_values,
    parameter_set_from_template_drawing,
)


# --------------------------------------------------------------------------- #
# Naming bridge: logical header key base + index -> engine parity-encoded slot
# --------------------------------------------------------------------------- #
def test_header_slot_parity_encoding() -> None:
    # supply/distributor header has odd id 2n-1 (I/S); return header even id 2n
    assert _header_slot("I", 2) == "slot.I3"
    assert _header_slot("S", 2) == "slot.S3"
    assert _header_slot("O", 2) == "slot.O4"
    assert _header_slot("R", 3) == "slot.R6"
    assert _header_slot("HD", 4) == "slot.HD8"
    # header 1 reproduces today's first-column mapping exactly
    assert _header_slot("I", 1) == "slot.I1"
    assert _header_slot("O", 1) == "slot.O2"


def test_is_multi_header_param_key() -> None:
    assert is_multi_header_param_key("I2")
    assert is_multi_header_param_key("ZD4")
    assert not is_multi_header_param_key("I")     # header-1 unsuffixed
    assert not is_multi_header_param_key("HDx1")  # distributor HD, not a header assembly
    assert not is_multi_header_param_key("CD")


# --------------------------------------------------------------------------- #
# Pure translation: parity slots -> logical (key, value) pairs
# --------------------------------------------------------------------------- #
def test_multi_header_logical_values_two_circuits() -> None:
    slots = {
        "slot.I1": 3, "slot.S1": 1.875, "slot.O2": 2, "slot.R2": 1.125, "slot.HD2": 3.5,
        "slot.I3": 3, "slot.S3": 3.625, "slot.O4": 2, "slot.R4": 3.75, "slot.HD4": 3.5,
    }
    pairs = dict(multi_header_logical_values(slots))
    # header-2 logical keys sourced from the parity slots I3/S3/O4/R4/HD4
    assert pairs["I2"] == 3
    assert pairs["S2"] == 3.625
    assert pairs["O2"] == 2
    assert pairs["R2"] == 3.75
    assert pairs["HD2"] == 3.5
    assert pairs["ZD2"] == ZD_CONSTANT == 4.5
    # only two circuits present -> no header-3 keys
    assert "I3" not in pairs


def test_multi_header_three_and_four_circuits() -> None:
    slots = {f"slot.I{2 * k - 1}": 3 for k in range(1, 5)}
    slots.update({f"slot.O{2 * k}": 2 for k in range(1, 5)})
    pairs = dict(multi_header_logical_values(slots))
    for n in (2, 3, 4):
        assert pairs[f"I{n}"] == 3
        assert pairs[f"O{n}"] == 2
        assert pairs[f"ZD{n}"] == 4.5


def test_single_circuit_degrades_to_no_extra_headers() -> None:
    slots = {"slot.I1": 3, "slot.O2": 2, "slot.R2": 1.125, "slot.HD2": 3.5}
    assert multi_header_logical_values(slots) == []  # 1HD -> no header-2+ keys


def test_circuits_hint_surfaces_header_without_fabricating() -> None:
    # Engine derived only header 1, but the coil is 2-circuit: header 2 surfaces as
    # review-required with None values (never a guessed number); ZD2 is the constant.
    slots = {"slot.I1": 3, "slot.O2": 2}
    pairs = dict(multi_header_logical_values(slots, circuits=2))
    assert pairs["I2"] is None
    assert pairs["O2"] is None
    assert pairs["ZD2"] == 4.5


# --------------------------------------------------------------------------- #
# Path #2 (live UI): parameter_set_from_template_drawing
# --------------------------------------------------------------------------- #
def test_parameter_set_emits_logical_header2_keys() -> None:
    template_drawing = {
        "slot_values": {
            "slot.CD": 5.5, "slot.I1": 3, "slot.S1": 1.875, "slot.O2": 2,
            "slot.R2": 1.125, "slot.HD2": 3.5, "slot.SL2": 8,
            "slot.I3": 3, "slot.S3": 3.625, "slot.O4": 2, "slot.R4": 3.75, "slot.HD4": 3.5,
        }
    }
    pset = parameter_set_from_template_drawing(template_drawing)
    params = pset.parameters
    # logical keys present (NOT the parity-encoded I3/O4)
    for key in ("I2", "S2", "O2", "R2", "HD2", "ZD2"):
        assert key in params, key
        assert params[key].status == "review_required"
    assert "I3" not in params and "O4" not in params  # parity ids never leak to UI
    assert params["I2"].value == 3
    assert params["S2"].value == 3.625
    assert params["O2"].value == 2
    # ZD (header 1) and ZD2 are the owner constant
    assert params["ZD"].value == 4.5
    assert params["ZD2"].value == 4.5
    # review-aid only
    assert pset.export_allowed is False


def test_parameter_set_single_circuit_has_no_header2() -> None:
    template_drawing = {"slot_values": {"slot.I1": 3, "slot.O2": 2, "slot.HD2": 3.5}}
    params = parameter_set_from_template_drawing(template_drawing).parameters
    assert "I2" not in params  # degrades cleanly
    assert params["ZD"].value == 4.5  # header-1 ZD constant still emitted


def test_parameter_set_circuits_hint_blocks_missing_header_value() -> None:
    # 2-circuit coil whose engine produced only header-1 slots -> header 2 surfaces
    # review-required with no fabricated value.
    template_drawing = {"slot_values": {"slot.I1": 3, "slot.O2": 2}}
    params = parameter_set_from_template_drawing(template_drawing, circuits=2).parameters
    assert params["I2"].value is None
    assert params["I2"].status == "review_required"
    assert params["ZD2"].value == 4.5


# --------------------------------------------------------------------------- #
# Engine integration: build_drawing_slots emits parity slots for N circuits
# (NOVA/B20 DX is the known-good engine fixture; CD varies with circuit count, so
# the S relationship is asserted against the resolved CD rather than a constant.)
# --------------------------------------------------------------------------- #
def test_build_drawing_slots_parity_for_2_3_4_circuits() -> None:
    for circuits in (2, 3, 4):
        slots, _ = build_drawing_slots(
            coil_type="DX", product_type="NOVA", unit_size="B20",
            rows=4, feeds=circuits, circuits=circuits, suction_conn_size=0.625,
            finned_height=12.0, finned_length=15.0,
        )
        cd = slots["slot.CD"]
        for k in range(1, circuits + 1):
            supply_id, return_id = 2 * k - 1, 2 * k
            assert f"slot.I{supply_id}" in slots
            assert f"slot.O{return_id}" in slots
            assert f"slot.HD{return_id}" in slots
            # R-034 distributor S = CHK DX!C46:C49 -> ROUND(k*CD/(circuits+1)*8,0)/8
            s = slots[f"slot.S{supply_id}"]
            assert s == round_eighth(k * cd / (circuits + 1))
            assert s * 8 == int(s * 8), f"S{supply_id}={s} is not a whole 1/8"


def test_hgrh_multi_header_slots_present() -> None:
    slots, _ = build_drawing_slots(
        coil_type="HGRH", product_type="NOVA", unit_size="B20",
        rows=4, feeds=2, circuits=2, suction_conn_size=0.625,
        finned_height=12.0, finned_length=15.0,
    )
    # HGRH sources supply_io/return_io/hd; header 2 (parity I3/O4/HD4) must resolve.
    assert "slot.I3" in slots
    assert "slot.O4" in slots
    assert "slot.HD4" in slots
