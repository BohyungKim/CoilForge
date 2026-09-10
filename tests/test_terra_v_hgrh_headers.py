"""Terra V HGRH: header 2+ values the SOP does not specify are left blank (pure).

Two defects, found by tracing RHHGRC-3 (Terra V / TV072 / 2 rows / 6 feeds /
0.875" conn / 2 conn-per-header) against the Coil Checklist:

1. R-046 asserts Supply **1** I/O = 2.75 and its own YAML comment says Supply 2/3/4
   I/O "is NOT derivable here" — yet the slot layer broadcast the Supply-1 constant
   to every odd header, printing 2.75 on positions the SOP declines to specify. That
   is the exact case the checklist flagged (`I3: CoilForge 2.75 vs Checklist TBD`).
2. [SUPERSEDED 2026-09-09] A Terra V HGRH whose circuit count exceeds its connections-
   per-header ran off the end of the R-052 return-spacing list. The 2026-08-30 answer was
   to blank those headers, because the then-current S = CD - Rn grows with the header
   index. That premise is gone: the SOP scopes Terra V's supply/return SPACING special to
   **DX** (R-023, "SOP 2024018 §DX-TNVH"), and its Terra V HGRH section states only I/O
   and SL values (R-046). Terra V HGRH therefore takes the general RHHGRC supply formula,
   which is ONE equation for `Supply 1/2/3/etc.` — a single fixed position shared by every
   supply header (John 2026-09-09), and legitimately negative ("Supply S/R values may be
   negative", SOP). Five measured Terra V references match it on S, R and X exactly.

Defect 1 still stands and is still pinned below. Defect 2's blanking is replaced by a
computed value; the panel wording for it was removed with the branch that produced it.

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


# --- 1. Supply I/O on every header ------------------------------------------
def test_terra_v_hgrh_supply_io_is_written_on_every_header():
    """[SUPERSEDED 2026-08-04 -> 2026-09-09] I1 = I2 = I3 (John, on a live Header-2 panel).

    From 2026-08-04 this asserted the opposite: Supply 2+ was blanked because R-046
    covers Supply 1 and the SOP adds "Supply 2,3,4 round to nearest INT", which CoilForge
    cannot do without EZ Coil's default. John ruled the supply I/O is the SAME on every
    header, which overrides that SOP wording for Terra V and is recorded as his ruling.
    """
    slots = _slots()
    assert slots["slot.I1"] == 2.75, "R-046 Supply 1 I/O is SOP-confirmed and must stay"
    assert slots["slot.I3"] == slots["slot.I1"], "supply I/O is one value for all headers"


def test_the_rest_of_the_terra_v_hgrh_geometry_is_untouched():
    """The blanking must not disturb the values the checklist already agreed with."""
    slots = _slots()
    assert slots["slot.CD"] == 3.75           # rows-based (SOP); NOT the checklist 4.125
    # One SOP position for every supply header: CD - [(n+2)*D + (n-1)*1.5] with
    # n = qty_conn_per_header = 2, D = 0.875 -> 3.75 - 5.0. Negative is legitimate.
    assert slots["slot.S1"] == -1.25
    assert slots["slot.S3"] == slots["slot.S1"]
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
def test_terra_v_hgrh_supply_spacing_is_one_fixed_position_on_every_header():
    """SOP RHHGRC states `Supply 1/2/3/etc.` as a SINGLE equation, so one position
    serves every supply header (John 2026-09-09: the supply stub is a fixed position).

    Replaces the 2026-08-30 blanking — see the module docstring. The guard that matters
    now is the opposite one: no supply header may be blank, and none may drift from the
    first, because the DX even-spacing net (`k*CD/(circuits+1)`) would do both.
    """
    slots = _slots(circuits=6)
    supply = {k: v for k, v in slots.items()
              if k.startswith("slot.S") and k[len("slot.S"):].isdigit()}
    assert len(supply) == 6, supply
    assert set(supply.values()) == {-1.25}, (
        "every supply header must share the one SOP position; a k-scaled value means the "
        f"DX even-spacing net leaked onto a reheat coil: {supply}"
    )


def test_terra_v_hgrh_supply_s_matches_the_measured_coilmaster_reference():
    """3025 Bauducco RHHGRC-1 (TV_B_024): the drawing prints S 1.88, R 0.63, X 1.25.

    This is the case that exposed the defect. A DX-only rule (R-023, "SOP 2024018
    §DX-TNVH SPECIAL CASE Terra V") had been widened to HGRH, which overshot every
    Terra V reheat supply S by exactly 2*D -- 3.125 instead of 1.875 here.

    `X` is not a rule: it is CD - R - S, so pinning S and R pins the X the drawing shows.
    """
    slots = _slots(
        unit_size="024", rows=2, circuits=1, feeds=4, qty_conn_per_header=1,
        suction_conn_size=0.625, conn_size=0.625,
        finned_height=30.0, finned_length=33.0,
    )
    assert slots["slot.CD"] == 3.75            # printed 3.75
    assert slots["slot.S1"] == 1.875           # printed 1.88
    assert slots["slot.R2"] == 0.625           # printed 0.63
    assert round(slots["slot.CD"] - slots["slot.R2"] - slots["slot.S1"], 4) == 1.25
    assert slots["slot.I1"] == 2.75            # R-046; the drawing's 2.00 is its own deviation


def test_terra_v_hgrh_supply_s_now_agrees_with_the_other_cd_formula_lines():
    """Terra V shares the general RHHGRC supply formula, so it must equal Nova's S.

    The SOP gives Terra V an HGRH special for I/O and SL values only; its spacing
    special is DX-scoped. If Terra V ever diverges from Nova here again, a family
    branch has been reintroduced without an SOP line behind it.
    """
    common = dict(
        rows=2, circuits=1, feeds=4, qty_conn_per_header=1,
        suction_conn_size=0.625, conn_size=0.625,
        finned_height=30.0, finned_length=33.0,
    )
    terra_v = _slots(unit_size="024", **common)
    nova = _slots(product_type="NOVA", unit_size="C24", terra_variant=None, **common)
    assert terra_v["slot.S1"] == nova["slot.S1"] == 1.875


def test_terra_v_dx_keeps_its_own_supply_spacing_special():
    """R-023 is `coil_type: [DX]` -- narrowing the slot layer must not narrow DX too."""
    dx = _slots(
        coil_type="DX", tag="CDXC-9", circuits=2, feeds=2,
        suction_conn_size=0.875, conn_size=None,
    )
    # CD - Rn with the Terra V DX return spacing (R-023), NOT the HGRH CD-formula.
    assert dx["slot.S1"] == 2.9375 and dx["slot.S3"] == 0.5625


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


def test_no_terra_v_hgrh_header_value_is_withheld_any_more():
    """[SUPERSEDED 2026-09-09] Both Terra V HGRH withholdings are gone.

    I2+ now carries the supply I/O (John's ruling) and S2+ carries the SOP supply
    position, so the panel shows numbers where it used to show a reason. Pinned in the
    positive direction: a regression to blanking would fail here, loudly.
    """
    params = _panel(_slots(circuits=6)).parameters
    by_key = {p.key: p for p in params} if isinstance(params, list) else params

    for key, expected in (("I2", 2.75), ("S2", -1.25)):
        row = by_key[key]
        assert row.value == expected, (key, row.value)
        assert not row.blocked_reason, (key, row.blocked_reason)

    # S3 is no longer withheld (2026-09-09): the SOP formula defines it, so the panel
    # shows a number instead of a reason. Pinned so a regression to blanking is loud.
    s3 = by_key["S3"]
    assert s3.value == -1.25, s3.value
    assert not s3.blocked_reason, s3.blocked_reason


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

    # [SUPERSEDED 2026-09-09] Both SOP withholdings are gone: the supply I/O broadcasts
    # (John's ruling) and the supply position comes from the SOP formula. The count went
    # 9 -> 5 -> 0. Pinned at zero because exceptions_K feeds the review ledger, and a
    # silent return of either blank would inflate it again on every multi-header Terra V.
    assert withheld == [], [e["key"] for e in withheld]
