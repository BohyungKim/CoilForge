"""Cross-family sweep: which emitted dimensions may be non-positive, and why.

A blanket "no negative dimension" rule would be WRONG, and that is the point of this
file. The seeded CoilMaster references really do print a negative supply spacing --
`coilmaster_hgrh_rh_header3` shows `S1 = -0.63` -- and the engine reproduces it exactly
when the reference's own inputs are reconstructed (NOVA, rows 2, circuits 3, D 0.625 ->
CD 5.5, R 0.625/2.75/4.875, S1 -0.625, SL5 6.9375; every value matches the seed). So the
Nova / Ventum H supply-S formula is CONFIRMED by reference, not a defect to be repaired.

What is a defect is the Terra V `S = CD - Rn` branch running past its premise: Terra V's
CD is rows-based (R-070) and does not grow with the header count while Rn grows linearly,
so beyond some header the return stub has crossed the whole casing and the subtraction
yields a number with no physical meaning (measured: S5 = -0.75, S7 = -2.75 on 3095's
RHHGRC geometry at 4 circuits). That branch withholds instead.

The sweep exists because the difference between those two cases is invisible from a
single coil, and the earlier guard for it sat unreachable behind a silent default.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.services.direct_coil_drawing_pipeline import (  # noqa: E402
    UnknownCoilInputError,
    build_drawing_slots,
)

_LINES = [
    ("TERRA V", "012"),
    ("TERRA H", "015"),
    ("NOVA", "C20"),
    ("VENTUM H", "H10"),
    ("VENTUM_PLUS", "V20"),
]
_CIRCUITS = (1, 2, 3, 4)
_CONNS = (0.5, 0.625, 0.875, 1.125, 1.375)
_ROWS = (1, 2, 4, 6, 8)

#: Only the HGRH supply-S formula (`_hgrh_supply_s`) may go non-positive, and only on the
#: odd (supply) slots. Every other family/slot must be > 0 or absent.
#:
#: TERRA V joined the list on 2026-09-09: it now shares that same formula. Its old
#: `S = CD - Rn` branch is DX-scoped (R-023, "SOP 2024018 §DX-TNVH"), and the RHHGRC SOP
#: states outright that "Supply S/R values may be negative" -- the Nova/Ventum H seeds
#: already prove it (EZC-0016 prints S1 = -0.63).
_MAY_BE_NON_POSITIVE = {("HGRH", "NOVA"), ("HGRH", "VENTUM H"), ("HGRH", "TERRA V")}


def _sweep():
    for coil, (product, size), circuits, conn, rows in itertools.product(
        ("DX", "HGRH"), _LINES, _CIRCUITS, _CONNS, _ROWS
    ):
        try:
            slots, _ = build_drawing_slots(
                coil_type=coil, product_type=product, unit_size=size,
                rows=rows, feeds=circuits, circuits=circuits,
                suction_conn_size=conn, finned_height=24, finned_length=15,
            )
        except (UnknownCoilInputError, ValueError):
            continue
        yield coil, product, circuits, conn, rows, slots


def _non_positive(slots: dict[str, object]) -> dict[str, float]:
    out = {}
    for key, value in slots.items():
        base = key[len("slot.") :].rstrip("0123456789")
        if base in ("S", "R", "I", "O") and isinstance(value, (int, float)):
            if not isinstance(value, bool) and value <= 0:
                out[key] = float(value)
    return out


def test_only_the_confirmed_nova_ventum_h_branch_emits_a_non_positive_dimension() -> None:
    offenders = []
    for coil, product, circuits, conn, rows, slots in _sweep():
        bad = _non_positive(slots)
        if not bad:
            continue
        if (coil, product) in _MAY_BE_NON_POSITIVE and all(
            key.startswith("slot.S") for key in bad
        ):
            continue  # confirmed against the seeded references (see module docstring)
        offenders.append((coil, product, circuits, conn, rows, bad))
    assert offenders == [], offenders[:8]


@pytest.mark.parametrize("circuits", _CIRCUITS)
@pytest.mark.parametrize("conn", _CONNS)
def test_terra_v_hgrh_supply_spacing_is_one_sop_position_on_every_header(
    circuits: int, conn: float
) -> None:
    """[SUPERSEDED 2026-09-09] This swept for "withheld once Rn crosses the casing".

    That guard existed because `S = CD - Rn` grows with the header index. The SOP scopes
    that special to DX (R-023) and gives HGRH one equation for `Supply 1/2/3/etc.`, so the
    sweep now pins the opposite invariant: every supply header carries the SAME value, and
    it is exactly the SOP subtraction. A k-scaled or missing S means the DX even-spacing
    net leaked onto a reheat coil -- the failure this sweep has always been here to catch.
    """
    slots, _ = build_drawing_slots(
        coil_type="HGRH", product_type="TERRA V", unit_size="012",
        rows=2, feeds=circuits, circuits=circuits,
        suction_conn_size=conn, finned_height=24, finned_length=15,
    )
    cd = slots.get("slot.CD")
    n = circuits  # no stated connections-per-header -> the formula falls back to circuits
    expected = round(cd - ((n + 2) * conn + (n - 1) * 1.5), 4)
    drawn = [slots.get(f"slot.S{2 * k - 1}") for k in range(1, circuits + 1)]
    assert all(v is not None for v in drawn), f"circuits={circuits} conn={conn} {drawn}"
    assert set(drawn) == {expected}, f"circuits={circuits} conn={conn} {drawn}"


def test_the_nova_reference_geometry_still_reproduces_its_seeded_drawing() -> None:
    """Pins the evidence the exemption above rests on.

    `coilmaster_hgrh_rh_header3` / EZC-0016: if this ever stops matching, the exemption
    has lost its basis and must be re-argued, not silently kept.
    """
    slots, _ = build_drawing_slots(
        coil_type="HGRH", product_type="NOVA", unit_size="C20",
        rows=2, feeds=3, circuits=3, suction_conn_size=0.625, conn_size=0.625,
    )
    assert slots["slot.CD"] == 5.5           # seed CD 5.50
    assert slots["slot.R2"] == 0.625         # seed R2 0.63
    assert slots["slot.R4"] == 2.75          # seed R4 2.75
    assert slots["slot.R6"] == 4.875         # seed R6 4.88
    assert slots["slot.S1"] == -0.625        # seed drawing prints -0.63
    assert slots["slot.SL5"] == 6.9375       # seed drawing prints 6.94
