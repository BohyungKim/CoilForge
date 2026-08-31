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


def test_supply_spacing_is_never_negative_on_a_terra_v_hgrh() -> None:
    """S = CD - Rn is withheld once Rn has crossed the casing, not drawn negative.

    Terra V's CD is rows-based (R-070) and does not grow with the header count while Rn
    grows linearly, so the SOP formula runs out of premise. Measured before the guard:
    S5 = -0.75, S7 = -2.75 on exactly this geometry.
    """
    for extra in ({}, {"stated_qty_conn_per_header": 2}):
        slots = _slots(**extra)
        negatives = {
            key: value
            for key, value in slots.items()
            if key.startswith("slot.S")
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value <= 0
        }
        assert negatives == {}, negatives


def test_the_supply_spacings_that_do_have_a_basis_are_still_drawn() -> None:
    """The guard withholds; it must not blank the headers the SOP does cover."""
    slots = _slots()
    assert slots["slot.S1"] == 3.25
    assert slots["slot.S3"] == 1.25


def test_a_withheld_supply_spacing_says_why_it_is_beyond_the_casing() -> None:
    """The panel must separate 'no Rn to subtract' from 'Rn is past the casing depth'.

    Both are Terra V HGRH supply-S withholdings and `_key_base` folds every S onto one
    reason key, so the two are told apart from the slot values rather than a new channel.
    """
    from coilforge.services.drawing_param_resolver import (
        parameter_set_from_template_drawing,
    )

    result = derive_coil_template_drawing({**_BASE})
    params = parameter_set_from_template_drawing(result, circuits=4).model_dump()
    by_key = params["parameters"]
    s3 = by_key["S3"]
    assert s3["value"] is None
    assert "casing depth" in (s3["blocked_reason"] or "")


def test_the_return_io_contrast_is_explained_next_to_the_withheld_supply_io() -> None:
    """I2 blank while O2 is filled is correct (R-046 vs R-042v) but reads as arbitrary
    unless the panel says so."""
    from coilforge.services.drawing_param_resolver import (
        parameter_set_from_template_drawing,
    )

    result = derive_coil_template_drawing({**_BASE, "feeds": 2, "circuits": 2})
    params = parameter_set_from_template_drawing(result, circuits=2).model_dump()
    by_key = params["parameters"]
    assert by_key["I2"]["value"] is None
    reason = by_key["I2"]["blocked_reason"] or ""
    assert "R-046" in reason and "R-042v" in reason
    # ...and the value it is being contrasted with is genuinely there.
    assert by_key["O2"]["value"] == 2.75


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
