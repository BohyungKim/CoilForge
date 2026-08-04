"""Terra V HGRH: header 2+ values the SOP does not specify are left blank (pure).

Two defects, found by tracing RHHGRC-3 (Terra V / TV072 / 2 rows / 6 feeds /
0.875" conn / 2 conn-per-header) against the Coil Checklist:

1. R-046 asserts Supply **1** I/O = 2.75 and its own YAML comment says Supply 2/3/4
   I/O "is NOT derivable here" — yet the slot layer broadcast the Supply-1 constant
   to every odd header, printing 2.75 on positions the SOP declines to specify. That
   is the exact case the checklist flagged (`I3: CoilForge 2.75 vs Checklist TBD`).
2. A Terra V HGRH whose circuit count exceeds its connections-per-header ran off the
   end of the R-052 return-spacing list and fell through to the generic even-spacing
   safety net, printing DX distributor spacing (`k*CD/(circuits+1)`) on a REHEAT coil.

Both now leave the slot blank, and the panel says WHY rather than showing the generic
"engine did not derive this" — a withheld value and a failed one must not look alike.

Scoped to Terra V HGRH throughout: every other product line's supply_io comes from
rules that do cover all headers, so their broadcast is deliberately unchanged.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.services.direct_coil_drawing_pipeline import build_drawing_slots
from coilforge.services.drawing_param_resolver import (
    parameter_set_from_template_drawing,
)


def _slots(**over):
    """RHHGRC-3 as the submittal actually resolves it (circuits falls back to
    qty_conn_per_header when the CoilMaster prose states no circuit count)."""
    kwargs = dict(
        coil_type="HGRH", product_type="TERRA V", unit_size="072",
        rows=2, feeds=6, circuits=2, conn_size=0.875, qty_conn_per_header=2,
        finned_height=39, finned_length=54, tag="RHHGRC-3", terra_variant="TERRA_V",
    )
    kwargs.update(over)
    slots, _ = build_drawing_slots(**kwargs)
    return slots


# --- 1. Supply I/O beyond header 1 ------------------------------------------
def test_terra_v_hgrh_supply_io_is_written_for_header_1_only():
    slots = _slots()
    assert slots["slot.I1"] == 2.75, "R-046 Supply 1 I/O is SOP-confirmed and must stay"
    assert "slot.I3" not in slots, (
        "Supply 2 I/O is a software default per R-046's own comment — never invent it"
    )


def test_the_rest_of_the_terra_v_hgrh_geometry_is_untouched():
    """The blanking must not disturb the values the checklist already agreed with."""
    slots = _slots()
    assert slots["slot.CD"] == 3.75           # rows-based (SOP); NOT the checklist 4.125
    assert slots["slot.S1"] == 2.875          # CD - R1
    assert slots["slot.S3"] == 0.5            # CD - R2  (Terra V SOP branch, not the net)
    assert slots["slot.R2"] == 0.875
    assert slots["slot.R4"] == 3.25
    assert slots["slot.O2"] == 2.75 and slots["slot.O4"] == 2.75
    assert slots["slot.SL1"] == 5 and slots["slot.SL2"] == 12
    assert slots["slot.OAL"] == 59.0 and slots["slot.CH"] == 40.25


def test_other_product_lines_still_broadcast_supply_io_to_every_header():
    """Terra H / Nova HGRH resolve supply_io from rules that DO cover all headers."""
    for product, variant in (("TERRA H", "TERRA_H_C"), ("NOVA", None)):
        slots = _slots(
            product_type=product,
            unit_size="072" if product == "TERRA H" else "C24",
            terra_variant=variant,
        )
        if "slot.I1" in slots:
            assert slots.get("slot.I3") == slots["slot.I1"], product


def test_terra_v_dx_supply_side_is_untouched():
    """The rule is HGRH-scoped: a Terra V DX distributor is a different rule family."""
    dx = _slots(
        coil_type="DX", tag="CDXC-3",
        suction_conn_size=0.875, conn_size=None,
    )
    i_slots = {k: v for k, v in dx.items() if k.startswith("slot.I")}
    assert len(i_slots) >= 2, f"Terra V DX lost its per-header I values: {i_slots}"


# --- 2. Supply spacing past the return-spacing list -------------------------
def test_terra_v_hgrh_supply_spacing_stops_where_its_basis_stops():
    """S = CD - Rn, and Rn runs to qty_conn_per_header — past that there is no basis.

    Reachable whenever the CoilMaster prose states a circuit count ("Interlaced 6
    Circuits") that exceeds the connections per header: the loop then runs k=1..6
    while R-052 produced only two spacings.
    """
    slots = _slots(circuits=6)
    assert slots["slot.S1"] == 2.875 and slots["slot.S3"] == 0.5
    for parity_id in (5, 7, 9, 11):
        assert f"slot.S{parity_id}" not in slots, (
            f"slot.S{parity_id} fell through to the DX even-spacing net on a reheat coil"
        )


def test_non_terra_v_hgrh_still_gets_a_spacing_for_every_header():
    """The exclusion is Terra V's alone — Nova HGRH keeps its checklist-family S."""
    slots = _slots(product_type="NOVA", unit_size="C24", terra_variant=None, circuits=6)
    assert all(f"slot.S{n}" in slots for n in (1, 3, 5, 7, 9, 11))


# --- 3. The panel explains the blank ----------------------------------------
def _panel(slots, product_type="TERRA V"):
    return parameter_set_from_template_drawing(
        {
            "slot_values": slots,
            "product_type": product_type,
            "unit_size": "072",
            "extracted": {"coil_category": "HGRH"},
        },
        circuits=6,
    )


def test_a_withheld_header_value_says_why_instead_of_reading_as_a_bug():
    params = _panel(_slots(circuits=6)).parameters
    by_key = {p.key: p for p in params} if isinstance(params, list) else params

    i2 = by_key["I2"]
    assert i2.value is None
    assert "R-046" in (i2.blocked_reason or ""), i2.blocked_reason
    assert "Supply 1 only" in (i2.blocked_reason or "")

    s3 = by_key["S3"]
    assert s3.value is None
    assert "Rn" in (s3.blocked_reason or ""), s3.blocked_reason
    assert "did not derive" not in (s3.blocked_reason or "").lower(), (
        "a deliberately withheld value must not share the generic failure wording"
    )


def test_other_lines_keep_the_generic_header_message():
    """Only Terra V HGRH gets the SOP wording; nothing else changes tone."""
    nova = _panel(
        {"slot.CD": 3.75}, product_type="NOVA",
    ).parameters
    by_key = {p.key: p for p in nova} if isinstance(nova, list) else nova
    reason = by_key["R"].blocked_reason or ""
    assert "R-046" not in reason and "Rn" not in reason


# --- 4. Disclosed side effect: the project gate counts one more exception ----
def _page_from(panel):
    params = panel.parameters
    items = {p.key: p for p in params} if isinstance(params, list) else params
    return {
        "tag": "RHHGRC-3",
        "workflow": {
            "drawing_parameter_set": {
                "parameters": {k: v.model_dump() for k, v in items.items()}
            },
            "template_drawing": {"found": True, "svg": "<svg/>"},
        },
    }


def test_blanking_raises_the_project_gate_exception_count_and_says_why():
    """A withheld value IS an exception — that is the point, and it is disclosed.

    `project_gate._classify_coil` counts any value-less parameter as a `blocked`
    exception, so blanking I2/S3+ raises `exceptions_K` for every multi-header Terra V
    HGRH coil. That is the intended fail-closed direction (better a flagged blank than
    a confidently wrong number), but it shifts the ledger's reason-class distribution,
    so it is pinned here rather than discovered later as drift.
    """
    from coilforge.review.project_gate import _classify_coil

    result = _classify_coil(_page_from(_panel(_slots(circuits=6))), None, None)
    blocked = [e for e in result["exceptions"] if e["reason"] == "blocked"]
    withheld = [
        e for e in blocked
        if "R-046" in (e.get("detail") or "") or "Rn" in (e.get("detail") or "")
    ]

    assert result["verdict"] == "exception"
    # 6 header columns: I2..I6 withheld (5) + S3..S6 withheld (4) = 9 SOP-withheld keys.
    assert len(withheld) == 9, [e["key"] for e in withheld]
    assert {e["key"] for e in withheld} == {
        "I2", "I3", "I4", "I5", "I6", "S3", "S4", "S5", "S6",
    }
