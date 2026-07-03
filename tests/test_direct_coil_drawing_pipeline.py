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


def test_slot_sl2_is_17_for_dx_ventum_h_h05() -> None:
    """R-025b SL=17 override propagates to the even drawing slot slot.SL2 (John 2026-06-26).
    slot.SL{even} = suction_sl per build_drawing_slots' per-circuit loop."""
    slots, _ = build_drawing_slots(
        coil_type="DX", product_type="VENTUM_H", unit_size="H05",
        rows=4, circuits=1, suction_conn_size=0.625,
    )
    assert slots["slot.SL2"] == 17


def test_hgrh_supply_sl_odd_position_formula_differs_per_slot() -> None:
    """HGRH odd SL (supply position) = 6 + return_conn/2 - S{odd}; differs per slot
    (John 2026-06-26). circuits=2/feeds=2 so the single-feed exception does not fire."""
    conn = 0.625
    slots, _ = build_drawing_slots(
        coil_type="HGRH", product_type="NOVA", unit_size="C20",
        rows=4, circuits=2, feeds=2, conn_size=conn,
    )
    assert slots["slot.SL1"] == round(6 + conn / 2 - slots["slot.S1"], 4)
    assert slots["slot.SL3"] == round(6 + conn / 2 - slots["slot.S3"], 4)
    assert slots["slot.SL1"] != slots["slot.SL3"]


def test_hgrh_single_feed_uses_same_sl_formula_as_multi_feed() -> None:
    # John 2026-06-27: the single-feed (feeds==1) SL1=SL2=3 exception is removed — a
    # single-feed HGRH coil is drawn identically to a multi-feed one. SL1 follows the
    # supply position formula; SL2 is the return_sl length (8 for NOVA), not the old 3.
    conn = 0.625
    slots, _ = build_drawing_slots(
        coil_type="HGRH", product_type="NOVA", unit_size="C20",
        rows=4, circuits=1, feeds=1, conn_size=conn,
    )
    assert slots["slot.SL1"] == round(6 + conn / 2 - slots["slot.S1"], 4)
    assert slots["slot.SL2"] == 8


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


def test_terra_v_drawing_slots_use_sop_specials() -> None:
    """Terra V drawing slots use the SOP specials, NOT Terra H values (John 2026-06-28):
    DX S = CD - Rn (own R-023 formula, never the generic R-022 net); DX I/O=2.75, SL=12;
    HGRH supply SL = 5; CWC return O = CH - 2.75 with supply I = 2.75."""
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
    assert cwc["slot.O2"] == round(cwc["slot.CH"] - 2.75, 4)  # return I/O = CH - 2.75
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
