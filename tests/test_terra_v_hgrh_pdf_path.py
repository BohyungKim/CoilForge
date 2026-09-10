"""The Terra V HGRH withholding guards, exercised on the path a real submittal takes.

Why this file exists at all: `tests/test_terra_v_hgrh_headers.py` calls
`build_drawing_slots` DIRECTLY, and it was green the whole time the guard it pins was
unreachable in production. The frozen `pdf_to_template_drawing.derive_slot_values` never
passes `qty_conn_per_header`, so R-052 fell back to `circuits`, `len(return_spacing)`
equalled `circuits`, and the `k <= len(return_spacing)` test that gates the blanking was
unconditionally true. A unit test one layer below the defect cannot see that.

So every assertion here goes through `derive_coil_template_drawing` -- the non-frozen
caller that the browser's `/api/coil-drawing/derive` and the analyze post-process chain
both share -- and pins the OBSERVABLE slot dictionary.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    derive_coil_template_drawing,
)

# 3095 Harrison's RHHGRC geometry (Terra Vertical TV_B_012, 2 rows, 0.5" connection),
# opened out to 4 circuits so the connections-per-header count and the header count
# genuinely disagree -- which is the only condition under which either guard can fire.
_BASE = dict(
    coil_category="HGRH",
    coil_hand="RH",
    product_type="TERRA V",
    unit_size="012",
    rows=2,
    feeds=4,
    circuits=4,
    return_conn_size=0.5,
    finned_height=24,
    finned_length=15,
    tag="RHHGRC-1",
)


def _slots(**extra: object) -> dict[str, object]:
    result = derive_coil_template_drawing({**_BASE, **extra})
    return result.get("slot_values") or {}


def test_the_stated_connection_count_reaches_the_engine_on_the_derive_path() -> None:
    """The submittal says 2 connections per header, so R-052's list stops at 2.

    Without this the list ran to `circuits` and invented R6/R8 for connections the
    submittal never claimed existed.
    """
    slots = _slots(stated_qty_conn_per_header=2)
    assert slots["slot.R2"] == 0.5
    assert slots["slot.R4"] == 2.5
    assert "slot.R6" not in slots
    assert "slot.R8" not in slots


def test_a_coil_with_no_stated_count_is_untouched() -> None:
    """No stated count -> the helper is a no-op, so an ordinary coil cannot regress."""
    assert _slots() == _slots(stated_qty_conn_per_header=None)


def test_a_stated_count_that_agrees_with_the_circuits_changes_nothing() -> None:
    """3095's own RHHGRC-1/-2/-3 are this case (qty == circuits == 2): byte-identical."""
    two = dict(feeds=2, circuits=2)
    assert _slots(**two) == _slots(**two, stated_qty_conn_per_header=2)


def test_supply_spacing_is_one_position_and_may_be_negative() -> None:
    """[SUPERSEDED 2026-09-09] This asserted no Terra V supply S could be negative.

    That rested on S = CD - Rn, which the SOP scopes to **DX** (R-023, "SOP 2024018
    §DX-TNVH"). The RHHGRC Supply equation applies instead, it is ONE equation for
    `Supply 1/2/3/etc.`, and the SOP states outright that "Supply S/R values may be
    negative". The value follows the stated connections-per-header, not the circuit count:
    4 connections put the supply behind the casing face, 2 put it 0.25" inside.
    """
    for extra, expected in (({}, -3.75), ({"stated_qty_conn_per_header": 2}, 0.25)):
        slots = _slots(**extra)
        supply = {
            key: value for key, value in slots.items()
            if key.startswith("slot.S") and key[len("slot.S"):].isdigit()
        }
        assert supply, extra
        assert set(supply.values()) == {expected}, (extra, supply)


def test_every_supply_header_is_drawn_and_none_drifts_from_the_first() -> None:
    """The DX even-spacing net (`k*CD/(circuits+1)`) would both blank and scale these."""
    slots = _slots()
    assert [slots.get(f"slot.S{2 * k - 1}") for k in range(1, 5)] == [-3.75] * 4


def test_the_supply_spacing_panel_row_carries_a_number_not_a_reason() -> None:
    """[SUPERSEDED 2026-09-09] Both Terra V supply-S withholding reasons were removed
    with the branch that produced them; the panel shows the SOP value instead."""
    from coilforge.services.drawing_param_resolver import (
        parameter_set_from_template_drawing,
    )

    result = derive_coil_template_drawing({**_BASE})
    params = parameter_set_from_template_drawing(result, circuits=4).model_dump()
    s3 = params["parameters"]["S3"]
    assert s3["value"] == -3.75
    assert not s3["blocked_reason"], s3["blocked_reason"]


def test_the_supply_and_return_io_now_agree_on_every_header() -> None:
    """[SUPERSEDED 2026-09-09] There is no contrast left to explain.

    I2 used to be blank beside a filled O2 (R-046 covers Supply 1, R-042v covers every
    return), and the panel carried a paragraph saying why. John ruled I1 = I2 = I3, so
    both sides now carry 2.75 and the explanation was removed with the blank.
    """
    from coilforge.services.drawing_param_resolver import (
        parameter_set_from_template_drawing,
    )

    result = derive_coil_template_drawing({**_BASE, "feeds": 2, "circuits": 2})
    by_key = parameter_set_from_template_drawing(result, circuits=2).model_dump()["parameters"]
    assert by_key["I2"]["value"] == 2.75
    assert by_key["O2"]["value"] == 2.75
    assert not by_key["I2"]["blocked_reason"], by_key["I2"]["blocked_reason"]


@pytest.mark.parametrize("circuits", [2, 3, 4])
def test_other_product_lines_are_not_touched_by_the_terra_v_helper(circuits: int) -> None:
    """The qty re-run is Terra-V-HGRH scoped on purpose: `qty_conn_per_header` also feeds
    `_hgrh_cd_multi`, whose TERRA_H / NOVA / VENTUM_H branches take it as `n`, so a
    line-agnostic thread would move `slot.CD` corpus-wide. That is a separate decision."""
    spec = {
        **_BASE,
        "product_type": "NOVA",
        "unit_size": "C20",
        "feeds": circuits,
        "circuits": circuits,
    }
    before = derive_coil_template_drawing(spec).get("slot_values") or {}
    after = derive_coil_template_drawing(
        {**spec, "stated_qty_conn_per_header": 1}
    ).get("slot_values") or {}
    assert before == after
