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
from coilforge.services.header_prepopulate_engine import prepopulate  # noqa: E402

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
    assert v["return_bend"].value == 1.5           # engine default RB (R-005; John 2026-06-25). EZC-0001 as-built was 1.75
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
    assert s["slot.RB"] == 1.5   # engine default RB (R-005; John 2026-06-25)
    assert s["slot.HDx1"] == 4.5
    assert s["slot.HD2"] == 3.5
    assert s["slot.I1"] == 3
    assert s["slot.SL2"] == 8
    assert "Copper Straps Required." in s["slot.NOTES"]
    # DX distributor extension note (R-035a/b) rides slot.NOTES too.
    assert 'Distributor 6" Extension' in s["slot.NOTES"]
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
    assert r.slot_values["slot.RB"] == 1.5      # engine default RB (R-005; John 2026-06-25)
    assert r.slot_values["slot.OAL"] == 20.0    # OAL = FL + RB + HD2 = 15 + 1.5 + 3.5 (John 2026-06-29)


def test_slot_sl2_is_17_for_dx_ventum_h_h05() -> None:
    """R-025b SL=17 override propagates to the even drawing slot slot.SL2 (John 2026-06-26).
    slot.SL{even} = suction_sl per build_drawing_slots' per-circuit loop."""
    slots, _ = build_drawing_slots(
        coil_type="DX", product_type="VENTUM_H", unit_size="H05",
        rows=4, circuits=1, suction_conn_size=0.625,
    )
    assert slots["slot.SL2"] == 17


def test_hgrh_supply_sl_odd_position_formula_same_per_slot() -> None:
    """HGRH odd SL (supply position) = 6 + return_conn/2 - S{odd}. Per the Coil Checklist
    (HGRH!C46/C58, David 2026-07-16, the source of truth — supersedes the 2026-06-26
    "differs per slot" call), every odd HGRH S shares one formula, so S1=S3 and the
    positions are EQUAL per slot. circuits=2/feeds=2 so the single-feed branch doesn't fire."""
    conn = 0.625
    slots, _ = build_drawing_slots(
        coil_type="HGRH", product_type="NOVA", unit_size="C20",
        rows=4, circuits=2, feeds=2, conn_size=conn,
    )
    assert slots["slot.SL1"] == round(6 + conn / 2 - slots["slot.S1"], 4)
    assert slots["slot.SL3"] == round(6 + conn / 2 - slots["slot.S3"], 4)
    assert slots["slot.S1"] == slots["slot.S3"]      # checklist: one S formula per family
    assert slots["slot.SL1"] == slots["slot.SL3"]


def test_hgrh_single_feed_sl1_is_six() -> None:
    """Single-feed supply SL1 = 6 (John 2026-08-06), NOT checklist HGRH!C58's 3.

    The sheet states this dimension twice and contradicts itself: C58's dimension row
    computes 3, while C26's "Add Headers & Stubouts" note -- emitted for exactly this
    case, C14 = 1 -- spells out "SL1=6" in all three product branches. A single-feed
    coil has no supply header of its own, so the drawn header is the ADDED one and 6 is
    its dimension. R-044a/R-044c and the EZC-0002/EZC-0010 as-built notes agree with the
    note; only C58 dissents.

    SL2 is untouched -- it stays the return_sl length (8 for NOVA).
    """
    conn = 0.625
    slots, _ = build_drawing_slots(
        coil_type="HGRH", product_type="NOVA", unit_size="C20",
        rows=4, circuits=1, feeds=1, conn_size=conn,
    )
    assert slots["slot.SL1"] == 6
    assert slots["slot.SL2"] == 8


def test_hgrh_single_feed_sl1_is_six_on_every_product_line() -> None:
    """The 2026-08-06 ruling is line-wide: CHK HGRH!C26 emits its "SL1=6" note for all
    three product branches (NOVA/VENTUM H, TERRA H, VENTUM+), so all three move together.

    TERRA V is the exception and must NOT move: it has no add-headers branch in C26 at
    all, and its supply SL comes from the SOP (R-046) as 5.
    """
    def sl(prod, size):
        s, _ = build_drawing_slots(
            coil_type="HGRH", product_type=prod, unit_size=size,
            rows=4, circuits=1, feeds=1, conn_size=0.625,
        )
        return s["slot.SL1"], s["slot.SL2"]

    assert sl("NOVA", "C20") == (6, 8)
    assert sl("VENTUM_H", "H15") == (6, 8)
    assert sl("TERRA H", "032") == (6, 10)
    assert sl("VENTUM_PLUS", "V20") == (6, 10)
    assert sl("TERRA V", "012") == (5, 12)      # SOP, untouched


def test_hgrh_multi_feed_slots_are_byte_identical() -> None:
    """The no-regression contract for the single-feed change. Multi-feed takes a
    different branch, so nothing about it may move -- asserted on the WHOLE slot dict,
    not just SL, because a shared-state mistake would surface in CD/S/O/R first.

    Literals captured from the pre-change implementation.
    """
    nova2, _ = build_drawing_slots(
        coil_type="HGRH", product_type="NOVA", unit_size="C20",
        rows=4, circuits=2, feeds=2, conn_size=0.625,
    )
    assert nova2 == {
        "slot.BF": 0.625, "slot.CD": 5.5, "slot.HD2": 3.5, "slot.HD4": 3.5,
        "slot.HDx1": 3.5, "slot.HDx3": 3.5, "slot.HF": 1.5, "slot.I1": 2,
        "slot.I3": 2, "slot.NOTES": "Copper Straps Required.", "slot.O2": 2,
        "slot.O4": 2, "slot.R2": 0.625, "slot.R4": 2.75, "slot.RB": 1.5,
        "slot.RF": 1.5, "slot.ROWS": 4, "slot.S1": 1.5, "slot.S3": 1.5,
        "slot.SL1": 4.8125, "slot.SL2": 8, "slot.SL3": 4.8125, "slot.SL4": 8,
        "slot.TF": 0.625,
    }

    terra_h3, _ = build_drawing_slots(
        coil_type="HGRH", product_type="TERRA H", unit_size="032",
        rows=4, circuits=3, feeds=3, conn_size=0.625,
    )
    assert terra_h3 == {
        "slot.BF": 0.5, "slot.CD": 6.625, "slot.HD2": 3.5, "slot.HD4": 3.5,
        "slot.HD6": 3.5, "slot.HDx1": 3.5, "slot.HDx3": 3.5, "slot.HDx5": 3.5,
        "slot.HF": 1.5, "slot.I1": 2, "slot.I3": 2, "slot.I5": 2,
        "slot.NOTES": "Copper Straps Required.", "slot.O2": 3.25, "slot.O4": 3.25,
        "slot.O6": 3.25, "slot.R2": 0.625, "slot.R4": 2.75, "slot.R6": 4.875,
        "slot.RB": 1.5, "slot.RF": 1.5, "slot.ROWS": 4, "slot.S1": 0.625,
        "slot.S3": 0.625, "slot.S5": 0.625, "slot.SL1": 5.6875, "slot.SL2": 10,
        "slot.SL3": 5.6875, "slot.SL4": 10, "slot.SL5": 5.6875, "slot.SL6": 10,
        "slot.TF": 1.625,
    }

    # The remaining lines keep the position formula (C58's multi-feed arm) untouched.
    conn = 0.625
    for prod, size in (("VENTUM_H", "H15"), ("VENTUM_PLUS", "V20")):
        s, _ = build_drawing_slots(
            coil_type="HGRH", product_type=prod, unit_size=size,
            rows=4, circuits=2, feeds=2, conn_size=conn,
        )
        assert s["slot.SL1"] == round(6 + conn / 2 - s["slot.S1"], 4), prod


def test_hgrh_single_feed_sl1_present_when_cd_unresolved() -> None:
    """The single-feed 6 is a constant, but it used to sit inside the `cd is not None`
    block, so an un-gated coil lost SL1 with no value and no reason -- just absent.

    Terra V in the same state gains nothing new: its 5 is not this constant."""
    ungated, _ = build_drawing_slots(
        coil_type="HGRH", product_type="NOVA", unit_size="ZZ99",
        rows=None, circuits=1, feeds=1, conn_size=None,
    )
    assert ungated.get("slot.CD") is None      # CD genuinely unresolved
    assert ungated["slot.SL1"] == 6

    terra_v, _ = build_drawing_slots(
        coil_type="HGRH", product_type="TERRA V", unit_size="ZZ99",
        rows=None, circuits=1, feeds=1, conn_size=None,
    )
    assert "slot.SL1" not in terra_v


def test_engine_supply_sl_agrees_with_slot_layer_single_feed() -> None:
    """The bridge test. ``supply_sl`` is emitted by the rule engine and read by NO python
    in src/, so engine (6) and slot layer (3) contradicted each other for a year without
    a single test failing. This is what stops that recurring.

    R-044c is HIGH (VENTUM+) so it lands in ``values``; R-044a is MEDIUM (NOVA/VENTUM H)
    so it lands in ``suggestions``. Both say 6, and the slot layer must now agree.
    """
    for prod, size in (("NOVA", "C20"), ("VENTUM_H", "H15"), ("VENTUM_PLUS", "V20")):
        request = build_header_request(
            coil_type="HGRH", product_type=prod, unit_size=size,
            rows=4, circuits=1, feeds=1, conn_size=0.625,
        )
        response = prepopulate(request)
        engine = response.values.get("supply_sl") or response.suggestions.get("supply_sl")
        assert engine is not None, prod
        slots, _ = build_drawing_slots(
            coil_type="HGRH", product_type=prod, unit_size=size,
            rows=4, circuits=1, feeds=1, conn_size=0.625,
        )
        assert engine.value == slots["slot.SL1"] == 6, prod


def test_dx_and_water_unaffected_by_hgrh_sl1_change() -> None:
    """The change sits behind ``is_hgrh``. DX has no supply header (no odd SL at all) and
    water coils never enter the branch."""
    dx, _ = build_drawing_slots(
        coil_type="DX", product_type="NOVA", unit_size="B20",
        rows=4, circuits=1, feeds=1, conn_size=0.625, suction_conn_size=0.625,
    )
    assert "slot.SL1" not in dx and dx["slot.SL2"] == 8

    for coil_type in ("CWC", "HWC"):
        water, _ = build_drawing_slots(
            coil_type=coil_type, product_type="NOVA", unit_size="C20",
            rows=4, circuits=1, feeds=1, conn_size=1.0,
        )
        assert "slot.SL1" not in water


def test_hgrh_supply_sl_gated_by_circuit_count() -> None:
    # circuits=3 (no single feed) -> SL1/SL3/SL5 present, SL7 absent.
    slots, _ = build_drawing_slots(
        coil_type="HGRH", product_type="NOVA", unit_size="C20",
        rows=4, circuits=3, feeds=3, conn_size=0.625,
    )
    assert {"slot.SL1", "slot.SL3", "slot.SL5"} <= slots.keys()
    assert "slot.SL7" not in slots


def test_dx_emits_no_supply_odd_sl() -> None:
    # DX has no supply header -> no odd slot.SL1/3/5/7 (only even slot.SL2 from suction_sl).
    slots, _ = build_drawing_slots(
        coil_type="DX", product_type="NOVA", unit_size="B20",
        rows=4, circuits=2, feeds=2, conn_size=0.625, suction_conn_size=0.625,
    )
    assert "slot.SL1" not in slots and "slot.SL3" not in slots
    assert "slot.SL2" in slots  # even/return SL still present


def test_dx_distributor_orientation_slot_emitted_per_family() -> None:
    # R-031/R-032 dist_orientation is a HIGH engine value; build_drawing_slots surfaces it
    # as slot.DIST_ORIENTATION so the parametric engine can redraw the distributor side.
    # Ventum+ = UP (R-032); Nova/Terra/Ventum H = DOWN (R-031).
    common = dict(unit_size=None, rows=4, circuits=1, feeds=2,
                  conn_size=0.625, suction_conn_size=0.625)
    vp, _ = build_drawing_slots(coil_type="DX", product_type="VENTUM_PLUS",
                                **{**common, "unit_size": "V20"})
    nova, _ = build_drawing_slots(coil_type="DX", product_type="NOVA",
                                  **{**common, "unit_size": "B20"})
    assert vp["slot.DIST_ORIENTATION"] == "UP"
    assert nova["slot.DIST_ORIENTATION"] == "DOWN"


def test_non_dx_emits_no_distributor_orientation_slot() -> None:
    # HGRH/CWC/HWC have no distributor -> R-031/R-032 do not apply -> no orientation slot.
    for coil_type in ("HGRH", "CWC", "HWC"):
        slots, _ = build_drawing_slots(
            coil_type=coil_type, product_type="VENTUM_PLUS", unit_size="V20",
            rows=4, circuits=1, feeds=2, conn_size=0.625, suction_conn_size=0.625,
        )
        assert "slot.DIST_ORIENTATION" not in slots, coil_type


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
    """HGRH sources supply_io/return_io and the shared header depth `hd` for both
    headers (no distributor, so the supply header depth HDx1 = HD2 = hd)."""
    s = _slots("HGRH")
    assert s["slot.I1"] == 2          # supply_io
    assert s["slot.O2"] == 2          # return_io
    assert s["slot.HD2"] == 3.5       # hd (return header depth)
    assert s["slot.SL2"] == 8         # return_sl
    assert s["slot.HDx1"] == 3.5      # supply header depth = hd (dimensioned too)


def test_terra_h_multi_circuit_return_spacing_all_circuits() -> None:
    """Terra H DX populates R for EVERY circuit from R-022 (Rn = n*D + (n-1)*1.5),
    not just the first. Regression: the second-header R (slot.R4) was blank."""
    s2, _ = build_drawing_slots(
        coil_type="DX", product_type="TERRA H", unit_size="024",
        rows=5, feeds=9, circuits=2, suction_conn_size=1.125,
        finned_height=15.0, finned_length=47.0,
    )
    assert s2["slot.R2"] == 1.125          # circuit 1: 1*1.125
    assert s2["slot.R4"] == 3.75           # circuit 2: 2*1.125 + 1.5

    s3, _ = build_drawing_slots(
        coil_type="DX", product_type="TERRA H", unit_size="024",
        rows=5, feeds=9, circuits=3, suction_conn_size=1.125,
        finned_height=15.0, finned_length=47.0,
    )
    assert (s3["slot.R2"], s3["slot.R4"], s3["slot.R6"]) == (1.125, 3.75, 6.375)


def test_cwc_per_header_slots_resolved_from_shared_geometry() -> None:
    """CWC/HWC carry a single shared header geometry (io/hd/sl); no distributor, so
    the supply header depth HDx1 = HD2 = hd (both headers dimensioned)."""
    s = _slots("CWC")
    assert s["slot.I1"] == 2.3125     # io
    assert s["slot.O2"] == 2.3125     # io (shared)
    assert s["slot.HD2"] == 4         # hd
    assert s["slot.SL2"] == 8         # sl
    assert s["slot.HDx1"] == 4        # supply header depth = hd


def test_water_supply_and_return_spacing_are_the_connection_size() -> None:
    """CWC/HWC S = R = the connection size (John 2026-07-29).

    Same shape the rest of the family already takes for a single-connection header —
    DX R-022 gives R1 = D, HGRH R-052 gives R = D at n = 1 — and a water coil is always
    1HD with one supply and one return. Replaces an even-spacing fallback (CD/2) that
    matched none of the seven seeded water references. Product-line-independent."""
    common = dict(rows=4, circuits=1, feeds=1,
                  conn_size=0.625, suction_conn_size=0.625, finned_height=20.0)
    for coil_type in ("CWC", "HWC"):
        for product, unit_size in (("TERRA V", "012"), ("TERRA H", "012"),
                                   ("NOVA", "C24"), ("VENTUM_H", "H15")):
            slots, _ = build_drawing_slots(
                coil_type=coil_type, product_type=product, unit_size=unit_size, **common
            )
            assert slots["slot.S1"] == 0.625, (coil_type, product)
            assert slots["slot.R2"] == slots["slot.S1"], (coil_type, product)


def test_water_spacing_resolves_from_the_suction_named_connection_too() -> None:
    """The frozen PDF path passes the read connection ONLY as `suction_conn_size` (the
    DX-flavoured name), never `conn_size` — the same trap that once blanked HGRH R. Water
    S/R must resolve from either."""
    slots, _ = build_drawing_slots(
        coil_type="HWC", product_type="TERRA V", unit_size="040",
        rows=1, circuits=1, feeds=2, suction_conn_size=1.0,
        finned_height=36.0, finned_length=33.0,
    )
    assert slots["slot.S1"] == 1.0            # 2949 Ferguson HHWC-1: 1" connection
    assert slots["slot.R2"] == 1.0


def test_water_spacing_does_not_need_the_casing_depth() -> None:
    """S is the connection size, so it no longer depends on CD — a coil whose casing
    depth the engine could not derive still gets S and R."""
    slots, _ = build_drawing_slots(
        coil_type="HWC", product_type="NOVA", unit_size="012",  # not a Nova size -> no CD
        rows=4, circuits=1, feeds=1, suction_conn_size=0.75, finned_height=20.0,
    )
    assert slots.get("slot.CD") is None
    assert slots["slot.S1"] == 0.75
    assert slots["slot.R2"] == 0.75


def test_water_return_io_mirrors_supply_io_on_every_product_line() -> None:
    """Regression (2949 Ferguson HHWC-1, John 2026-07-29): Terra V water printed
    O = CH - 2.75 = 34.5 into the stubout I/O callout, which carries a 2-3" dimension.
    That is the same physical position measured from the OPPOSITE datum — a datum
    mismatch, not a different value. Every one of the seven seeded water references
    reads O{even} == I{odd}; none reads CH - 2.75. Terra V was the only line whose O
    diverged from its own I, which is the tell."""
    common = dict(rows=1, circuits=1, feeds=2, conn_size=1.0, suction_conn_size=1.0,
                  finned_height=36.0, finned_length=33.0)
    for coil_type in ("CWC", "HWC"):
        for product, unit_size in (("TERRA V", "040"), ("TERRA H", "012"),
                                   ("NOVA", "C24"), ("VENTUM_H", "H15")):
            slots, _ = build_drawing_slots(
                coil_type=coil_type, product_type=product, unit_size=unit_size, **common
            )
            i1, o2, ch = slots.get("slot.I1"), slots.get("slot.O2"), slots.get("slot.CH")
            assert o2 == i1, (coil_type, product, i1, o2)
            # The stubout callout is a small dimension — never a casing-height-scale one.
            assert ch is None or o2 < ch / 2, (coil_type, product, o2, ch)


def test_water_spacing_stays_blank_without_a_connection_size() -> None:
    """With no connection size there is nothing to derive S from, so S and R must both
    stay blank rather than raise — and R must NOT fall through to the generic R-022 net,
    which would print an R with no S beside it. A KeyError here would blank the whole
    template_drawing into an error payload, which the UI reports as the misleading
    'template not registered'."""
    slots, _ = build_drawing_slots(
        coil_type="HWC", product_type="NOVA", unit_size="C24",
        rows=4, circuits=1, feeds=1, finned_height=20.0,   # no conn size at all
    )
    assert "slot.S1" not in slots
    assert "slot.R2" not in slots


def test_dx_and_hgrh_return_spacing_unaffected_by_the_water_rule() -> None:
    """Scope guard: R = S is water-only. DX keeps its R-023 (Terra V) / R-022 spacing and
    HGRH its R-052, pinned to their documented values."""
    common = dict(unit_size="012", rows=4, circuits=2, feeds=2,
                  conn_size=0.625, suction_conn_size=0.625, finned_height=20.0)

    dx_v, _ = build_drawing_slots(coil_type="DX", product_type="TERRA V", **common)
    # R-023 Terra V: R1 = 0.5*0.625+0.75, R2 = 1.5*0.625+2.25 — unchanged by the water rule.
    assert (dx_v["slot.R2"], dx_v["slot.R4"]) == (1.0625, 3.1875)
    dx_h, _ = build_drawing_slots(coil_type="DX", product_type="TERRA H", **common)
    assert dx_h["slot.R2"] == 0.625                       # generic R-022 net, k=1
    hgrh_v, _ = build_drawing_slots(coil_type="HGRH", product_type="TERRA V", **common)
    assert hgrh_v["slot.R2"] == 0.625                     # R-052, single connection


def test_terra_v_drawing_slots_use_sop_specials() -> None:
    """Terra V drawing slots use the SOP specials, NOT Terra H values (John 2026-06-28):
    DX S = CD - Rn (own R-023 formula, never the generic R-022 net); DX I/O=2.75, SL=12;
    HGRH supply SL = 5; CWC supply AND return I/O = 2.75."""
    common = dict(unit_size="012", rows=4, circuits=2, feeds=2,
                  conn_size=0.625, suction_conn_size=0.625, finned_height=20.0)

    dx, _ = build_drawing_slots(coil_type="DX", product_type="TERRA V", **common)
    # R-023 Terra V return spacing: R1=0.5*0.625+0.75, R2=1.5*0.625+2.25.
    assert dx["slot.R2"] == 1.0625 and dx["slot.R4"] == 3.1875
    # S = CD - Rn (CD=5.5): S1=5.5-1.0625, S3=5.5-3.1875.
    assert dx["slot.S1"] == 4.4375 and dx["slot.S3"] == 2.3125
    assert dx["slot.O2"] == 2.75 and dx["slot.SL2"] == 12

    # Terra H is unaffected (generic even-spacing S, generic R, O=3.25, SL=10).
    dx_h, _ = build_drawing_slots(coil_type="DX", product_type="TERRA H", **common)
    assert dx_h["slot.R2"] == 0.625 and dx_h["slot.O2"] == 3.25 and dx_h["slot.SL2"] == 10

    hgrh, _ = build_drawing_slots(coil_type="HGRH", product_type="TERRA V", **common)
    # Terra V HGRH SL callouts split (John 2026-07-03): supply reheat stub SL1 = 5 (its own
    # redacted template callout), return clearance SL2 = 12 (R-046 return_sl). The old
    # force-SL2=5 workaround is gone.
    assert hgrh["slot.SL1"] == 5 and hgrh["slot.SL3"] == 5    # supply SL = 5 (odd)
    assert hgrh["slot.SL2"] == 12 and hgrh["slot.SL4"] == 12  # return SL = 12 (even)
    # CD restored to the rows-based base depth (R-070 HIGH), not the R-073 multi value;
    # rows=4 -> ROUNDUP(4*0.866 to 1/8)+2 = 5.5. This also makes S = CD - Rn use the real CD.
    assert hgrh["slot.CD"] == 5.5
    assert hgrh["slot.S1"] == round(5.5 - hgrh["slot.R2"], 4)  # S = CD - Rn

    # Scope guard: non-Terra-V HGRH keeps the return_sl clearance on the drawn even slot.
    hgrh_h, _ = build_drawing_slots(coil_type="HGRH", product_type="TERRA H", **common)
    assert hgrh_h["slot.SL2"] == 10                         # Terra H HGRH still draws return_sl
    assert hgrh_h["slot.CD"] == 5.5                         # rows-based base depth (R-070)

    cwc, _ = build_drawing_slots(coil_type="CWC", product_type="TERRA V", **common)
    assert cwc["slot.I1"] == 2.75                           # supply I/O = 2.75
    # Return I/O prints the SAME stubout dimension as the supply (John 2026-07-29). The
    # old expectation here was `CH - 2.75`, which is that same position measured from the
    # opposite datum — writing it into the stubout callout printed 34.5 where ~2.75
    # belongs. All seven seeded water references read O{even} == I{odd}, and none reads
    # CH - 2.75 (checked across CH 17.00-38.75).
    assert cwc["slot.O2"] == 2.75
    assert cwc["slot.O2"] == cwc["slot.I1"]
    assert cwc["slot.SL2"] == 12


def test_hgrh_return_spacing_r_resolves_when_conn_only_suction_side() -> None:
    """Regression (3025 Bauducco RHHGRC-2, Terra V 012, John 2026-07-02): the frozen
    template path (pdf_to_template_drawing) passes the read connection size ONLY as
    `suction_conn_size`, never `conn_size`. HGRH R (R-052) consumes `conn_size`, so the
    slot layer must route suction->conn for HGRH. Terra V exposed the bug because its R
    safety net is off (`and not is_terra_v`); Terra H was masked by that net. For a single
    connection R reduces to the connection size as-is (John's expectation)."""
    tv, _ = build_drawing_slots(
        coil_type="HGRH", product_type="TERRA V", unit_size="012",
        circuits=1, suction_conn_size=0.5,  # conn_size deliberately omitted (template shape)
    )
    assert tv["slot.R2"] == 0.5            # was blank before the conn_size routing fallback

    # Terra H HGRH: same call, same value — via the now-primary R-052 path, previously the
    # safety net. Guards against a behavior change on the variants that already worked.
    th, _ = build_drawing_slots(
        coil_type="HGRH", product_type="TERRA H", unit_size="012",
        circuits=1, suction_conn_size=0.5,
    )
    assert th["slot.R2"] == 0.5


def test_hgrh_cd_stays_rows_based_when_conn_present() -> None:
    """Regression (3025 Bauducco, John 2026-07-03): routing conn_size for HGRH R must NOT
    blank slot.CD. CD is the rows-based base depth (R-070 HIGH) for all HGRH, single or
    multi-circuit; the R-073 multi formula (a non-physical 1.0"/1.25" for one circuit) must
    never replace it. Template call shape: connection size supplied ONLY as suction_conn_size."""
    # rows=2 -> ROUNDUP(2*0.866=1.732 to 1/8)=1.75, +2 = 3.75 (the value that went blank).
    tv, _ = build_drawing_slots(
        coil_type="HGRH", product_type="TERRA V", unit_size="012",
        rows=2, circuits=1, suction_conn_size=0.5,
    )
    assert tv["slot.CD"] == 3.75          # was blank when R-073 (MEDIUM) hijacked casing_depth
    assert tv["slot.R2"] == 0.5
    assert tv["slot.SL1"] == 5 and tv["slot.SL2"] == 12
    assert tv["slot.S1"] == round(3.75 - 0.5, 4)  # S = CD - Rn uses the real (rows-based) CD


def test_dx_cd_with_hgrh_reheat_pair_uses_checklist_branch() -> None:
    """Regression (3058 Apple Coconut Point, David 2026-07-16): a DX paired with a reheat
    HGRH takes the with-HGRH R-072 casing-depth branch, matching the Coil Checklist
    DX!C24 IF(W/HGRH=TRUE, circuits*(D+1.5)+(D-D_hgrh)/2, ...). CDXC-2 (rows=5, circuits=3,
    suction D=1.125, paired RHHGRC-2 conn=0.875) must resolve CD=8.0, NOT the standalone
    7.5 — and S1/S3/S5 = k*CD/(circuits+1) follow to 2.0/4.0/6.0."""
    base = dict(
        coil_type="DX", product_type="TERRA H", unit_size="048",
        rows=5, circuits=3, suction_conn_size=1.125, tag="CDXC-2",
    )
    # Standalone DX (no reheat partner) keeps the plain multi-circuit branch.
    standalone, _ = build_drawing_slots(**base)
    assert standalone["slot.CD"] == 7.5
    assert (standalone["slot.S1"], standalone["slot.S3"], standalone["slot.S5"]) == (
        1.875, 3.75, 5.625,
    )
    # Reheat-paired DX takes the with-HGRH branch: 3*(1.125+1.5)+(1.125-0.875)/2 = 8.0.
    paired, _ = build_drawing_slots(with_hgrh=True, hgrh_conn_size=0.875, **base)
    assert paired["slot.CD"] == 8.0
    assert (paired["slot.S1"], paired["slot.S3"], paired["slot.S5"]) == (2.0, 4.0, 6.0)


def test_hgrh_cd_s_sl_align_to_checklist_family_branches() -> None:
    """Regression (3058 Apple Coconut Point, David 2026-07-16): HGRH CD/S1/SL1 match the
    Coil Checklist HGRH!C27/C46/C58 family branches (the confirmed source of truth):
      CD  = MAX(base, TERRA H:(n+2)conn+(n-1)1.5+0.5 | NOVA/VH:(n+1)conn+(n-1)1.5 | VP:3conn)
      S1  = conn (TERRA H / VENTUM+)  |  CD-((n+2)conn+(n-1)1.5) (NOVA / VENTUM H)
      SL1 = 5 (Terra V) | 6 (single feed, CHK C26 note -- see below) | 6+conn/2-S1
    Values verified against the sheet's recomputed cells for the 3058 reheat coils.

    CD and S1 are the regression this case exists for and are asserted UNCHANGED. Only
    the single-feed SL1 element moved (3 -> 6, John 2026-08-06): C58's dimension row and
    C26's "Add Headers & Stubouts" note disagree, and the note is what the drawing shows.
    """
    def hgrh(prod, size, rows, conn, n, feeds):
        s, _ = build_drawing_slots(
            coil_type="HGRH", product_type=prod, unit_size=size,
            rows=rows, conn_size=conn, qty_conn_per_header=n, feeds=feeds, circuits=1,
        )
        return s["slot.CD"], s["slot.S1"], s["slot.SL1"]

    # RHHGRC-2 TERRA H rows=1 conn=0.875 n=1 feeds=3: CD 2.875->3.125, S1=conn, SL1=6+conn/2-S1.
    assert hgrh("TERRA H", "048", 1, 0.875, 1, 3) == (3.125, 0.875, 5.5625)
    # RHHGRC-3 VENTUM H rows=2 conn=0.5 n=1 feeds=1: base dominates CD; S1=CD-formula;
    # single feed SL1=6 (CD 3.75 and S1 2.25 unchanged — the regression this case guards).
    assert hgrh("VENTUM_H", "H10", 2, 0.5, 1, 1) == (3.75, 2.25, 6)
    # RHHGRC-5 TERRA H rows=1 conn=0.625 n=1 feeds=2: SL1 takes the position formula (not 3).
    assert hgrh("TERRA H", "032", 1, 0.625, 1, 2) == (2.875, 0.625, 5.6875)


def test_hgrh_sl1_single_feed_branch_keys_on_feeds_then_circuits() -> None:
    """The single-feed SL1 branch keys on the SAME value the checklist's FEEDS/CIRCUITS
    cell holds — ``feeds`` if stated, else ``circuits`` (checklist/mapping.py). So a
    submittal that omits feeds but states 1 circuit still takes the single-feed branch,
    while feeds omitted + 2 circuits takes the position formula.

    The KEY under test is unchanged by the 2026-08-06 ruling; only the branch's VALUE
    moved (3 -> 6). Both C58 and all three C26 note branches fire on that same cell, so
    which coils are single-feed is not in dispute — only what SL1 reads for them."""
    def sl1(feeds, circuits):
        s, _ = build_drawing_slots(
            coil_type="HGRH", product_type="NOVA", unit_size="C20",
            rows=4, circuits=circuits, feeds=feeds, conn_size=0.625,
        )
        return s["slot.SL1"]

    assert sl1(None, 1) == 6                       # feeds absent, 1 circuit -> single feed
    assert sl1(1, 2) == 6                          # feeds stated =1 wins over circuits=2
    conn = 0.625
    s, _ = build_drawing_slots(
        coil_type="HGRH", product_type="NOVA", unit_size="C20",
        rows=4, circuits=2, feeds=None, conn_size=conn,
    )
    assert s["slot.SL1"] == round(6 + conn / 2 - s["slot.S1"], 4)  # feeds absent, 2 circuits


def test_hgrh_terra_v_unchanged_by_checklist_alignment() -> None:
    """The HGRH checklist alignment must NOT touch Terra V: its CD stays rows-based (SOP)
    and its S = CD - Rn / supply SL = 5 path is preserved (guards the R-073 disable
    rationale — Terra V CD must never be replaced by a multi-header term)."""
    s, _ = build_drawing_slots(
        coil_type="HGRH", product_type="TERRA V", unit_size="012",
        rows=2, circuits=1, suction_conn_size=0.5,
    )
    assert s["slot.CD"] == 3.75              # rows-based base, not a multi term
    assert s["slot.S1"] == round(3.75 - 0.5, 4)  # S = CD - Rn (R-023), unchanged
    assert s["slot.SL1"] == 5                 # Terra V supply SL (SOP), not 6 or the formula


def test_dx_cd_with_hgrh_noop_when_base_dominates() -> None:
    """The with-HGRH branch is a MAX with the rows-based base, so a low-circuit DX is
    unchanged by the flag (base wins). CDXC-3 (rows=5, circuits=1, D=0.875, partner 0.5):
    with-HGRH term 1*(0.875+1.5)+(0.875-0.5)/2 = 2.5625 < base 6.375 -> CD stays 6.375.
    Guards standalone/low-circuit coils against drift."""
    base = dict(
        coil_type="DX", product_type="VENTUM_H", unit_size="H10",
        rows=5, circuits=1, suction_conn_size=0.875, tag="CDXC-3",
    )
    standalone, _ = build_drawing_slots(**base)
    paired, _ = build_drawing_slots(with_hgrh=True, hgrh_conn_size=0.5, **base)
    assert standalone["slot.CD"] == 6.375
    assert paired["slot.CD"] == 6.375  # base dominates -> flag is a no-op here
