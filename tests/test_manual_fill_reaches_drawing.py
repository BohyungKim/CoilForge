"""A lever the fill panel offers must change the DRAWING, not only the panel beside it.

John 2026-10-02: submittal data can always be missing, so the engineer types it in and
re-runs. Three offered levers did not reach the SVG. This file pins the defect class --
"the value moved in ``slot_values`` and the artwork kept the old number" -- which the
older Tier-A tests could not see because they assert ``slot_values`` only.

Every SVG assertion here uses a SHARED-bucket coil on purpose: a coil with a dedicated
family template is re-populated later by ``_prefer_dedicated_family_template`` and would
pass whether or not the Tier-A re-run reaches the artwork.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.workflows import submittal_to_drawing as std  # noqa: E402
from coilforge.workflows.submittal_to_drawing import derive_coil_template_drawing  # noqa: E402


def _hwc(**kw):
    spec = dict(
        coil_category="HWC", coil_hand="LH", tag="HHWC-1", circuits=1, rows=1, feeds=2,
        finned_height=36.0, finned_length=33.0, suction_conn_size=1.0,
        product_type="NOVA", unit_size="C24",
    )
    spec.update(kw)
    return spec


# 3095 Harrison's RHHGRC geometry opened out to 4 circuits (see test_terra_v_hgrh_pdf_path):
# the one line where the submittal's stated connections-per-header reaches the engine.
def _terra_v_hgrh(**kw):
    spec = dict(
        coil_category="HGRH", coil_hand="RH", tag="RHHGRC-1", circuits=4, rows=2, feeds=4,
        finned_height=24, finned_length=15, return_conn_size=0.5,
        product_type="TERRA V", unit_size="012",
    )
    spec.update(kw)
    return spec


def _nova_hgrh(**kw):
    spec = dict(
        coil_category="HGRH", coil_hand="LH", tag="RHHGRC-1", circuits=2, rows=2, feeds=4,
        finned_height=20.0, finned_length=40.0, return_conn_size=0.875,
        product_type="NOVA", unit_size="B20",
    )
    spec.update(kw)
    return spec


def _slots(result):
    return result.get("slot_values") or {}


# --------------------------------------------------------------------------- #
# 1a -- a Tier-A re-run reaches the SVG
# --------------------------------------------------------------------------- #
def test_tier_a_only_fill_repopulates_the_svg():
    """Typed inlet/outlet must draw exactly what the same sizes draw when intake read them."""
    plain = derive_coil_template_drawing(_hwc())
    typed = derive_coil_template_drawing(_hwc(inlet_conn_size=2.0, outlet_conn_size=2.0))
    # Shaped as analyze sends it: the panel's connection text comes from the inlet.
    read = derive_coil_template_drawing(
        _hwc(water_conn_extracted={"inlet": 2.0, "outlet": 2.0}, panel={"conn_size": 2.0})
    )

    assert typed["template_id"] == "coilmaster_hwc_lh", "precondition: a shared bucket"
    assert _slots(typed)["slot.CD"] == _slots(read)["slot.CD"] != _slots(plain)["slot.CD"]
    assert typed["svg"] != plain["svg"], "the artwork kept the pre-fill dimensions"
    assert typed["svg"] == read["svg"]


def test_tier_a_fill_drops_per_header_slots_the_rerun_declined():
    """A slot the better-informed run declines is REMOVED, not left behind by update()."""
    without = _slots(derive_coil_template_drawing(_terra_v_hgrh()))
    stated = derive_coil_template_drawing(_terra_v_hgrh(stated_qty_conn_per_header=2))
    typed = derive_coil_template_drawing(_terra_v_hgrh(qty_conn_per_header=2))

    declined = set(without) - set(_slots(stated))
    assert declined, "precondition: qty 2 withdraws at least one per-header slot"
    assert not declined & set(_slots(typed))
    assert _slots(typed) == _slots(stated)
    assert typed["svg"] == stated["svg"]


def test_stated_qty_survives_an_unrelated_tier_a_fill():
    """`application` changes no slot, yet supplying it used to discard the submittal's own
    connections-per-header and move CD. Invisible while the SVG was stale; fatal once the
    re-run reaches the artwork."""
    stated = derive_coil_template_drawing(_terra_v_hgrh(stated_qty_conn_per_header=2))
    both = derive_coil_template_drawing(
        _terra_v_hgrh(stated_qty_conn_per_header=2, application="INTEGRATED")
    )
    assert _slots(both) == _slots(stated)
    assert both["svg"] == stated["svg"]
    assert both["stated_qty_conn_per_header_applied"] == 2


def test_a_typed_qty_beats_the_stated_one():
    typed_only = derive_coil_template_drawing(_terra_v_hgrh(qty_conn_per_header=3))
    both = derive_coil_template_drawing(
        _terra_v_hgrh(qty_conn_per_header=3, stated_qty_conn_per_header=2)
    )
    stated_only = derive_coil_template_drawing(_terra_v_hgrh(stated_qty_conn_per_header=2))

    assert _slots(both) == _slots(typed_only) != _slots(stated_only)
    assert both["svg"] == typed_only["svg"] != stated_only["svg"]
    assert "stated_qty_conn_per_header_applied" not in both


def test_stated_qty_scope_is_not_widened_by_a_tier_a_fill():
    """The stated qty reaches the engine for Terra V HGRH only (it moves CD on every other
    line -- John's separate decision). A Tier-A fill must not open that door."""
    lever = derive_coil_template_drawing(_nova_hgrh(application="INTEGRATED"))
    both = derive_coil_template_drawing(
        _nova_hgrh(application="INTEGRATED", stated_qty_conn_per_header=1)
    )
    assert _slots(both) == _slots(lever)
    assert "stated_qty_conn_per_header_applied" not in both


def test_tier_a_fill_on_a_withheld_drawing_updates_slots_only(monkeypatch):
    monkeypatch.setattr(std, "_TERRA_WATER_WITHHELD_CATEGORIES", {"HWC"})
    terra = dict(product_type="TERRA V", unit_size="024", suction_conn_size=1.5)
    plain = derive_coil_template_drawing(_hwc(**terra))
    typed = derive_coil_template_drawing(
        _hwc(**terra, inlet_conn_size=2.0, outlet_conn_size=2.0)
    )
    assert plain["not_registered_reason"], "precondition: the re-armed gate withheld it"
    assert typed["svg"] == ""
    assert _slots(typed)["slot.CD"] != _slots(plain)["slot.CD"]


def test_tier_a_then_tier_b_draws_both():
    tier_a = derive_coil_template_drawing(_hwc(inlet_conn_size=2.0, outlet_conn_size=2.0))
    both = derive_coil_template_drawing(
        _hwc(
            inlet_conn_size=2.0, outlet_conn_size=2.0,
            param_overrides=[{"key": "BF", "value": 1.37, "override_reason": "measured"}],
        )
    )
    assert _slots(both)["slot.CD"] == _slots(tier_a)["slot.CD"]
    assert _slots(both)["slot.BF"] == 1.37
    # The machine proposal the override replaced is the Tier-A one, not the pre-fill one.
    (event,) = both["manual_override_events"]
    assert event["previous_value"] == _slots(tier_a)["slot.BF"]
    assert "1.37" in both["svg"]


def test_unparseable_conn_string_keeps_its_r_slots_after_a_tier_a_fill():
    """The frozen path parses `0.625" OD`; the re-run's coercion does not. Deleting the
    slots the re-run "declined" there would remove an R the drawing legitimately has."""
    odd = dict(return_conn_size='0.625" OD')
    plain = _slots(derive_coil_template_drawing(_nova_hgrh(**odd)))
    filled = _slots(derive_coil_template_drawing(_nova_hgrh(**odd, application="INTEGRATED")))
    assert plain.get("slot.R2") is not None, "precondition: the frozen path read the size"
    assert filled.get("slot.R2") == plain["slot.R2"]
    assert filled.get("slot.R4") == plain.get("slot.R4")


# --------------------------------------------------------------------------- #
# 1f -- the fill plan says what is actually missing, and keeps what was typed
# --------------------------------------------------------------------------- #
def _items(result):
    return {item["key"]: item for item in result["manual_fill_plan"]["items"]}


def _dx(**kw):
    spec = dict(
        coil_category="DX", coil_hand="LH", tag="CDXC-1", circuits=2, rows=4, feeds=6,
        finned_height=20.0, finned_length=40.0, product_type="NOVA", unit_size="B20",
    )
    spec.update(kw)
    return spec


def test_satisfied_levers_stay_offered_as_resolved():
    """Once every missing input was supplied the plan fell back to the stale analyze-time
    list and asked for them all again; fixing only that would make them VANISH instead,
    leaving a typo with no control to correct it (the coil-hand lesson, 2026-07-29)."""
    before = _items(derive_coil_template_drawing(_dx(suction_conn_size=1.125)))
    assert before["application"]["unresolved"] is True

    after = _items(
        derive_coil_template_drawing(
            _dx(suction_conn_size=1.125, application="INTEGRATED", header_count=2)
        )
    )
    for key, value in (("application", "INTEGRATED"), ("header_count", 2)):
        assert after[key]["unresolved"] is False, key
        assert after[key]["current_value"] == value, key


def test_inputs_the_drawing_has_are_not_offered():
    """The engine reports missing inputs in PAIRS (`suction_conn_size` + `circuits`), so a
    coil whose circuits were read was asked for them anyway."""
    items = _items(derive_coil_template_drawing(_dx()))  # no connection size
    assert "circuits" not in items
    assert "rows" not in items
    assert {"suction_conn_size", "return_conn_size"} & set(items), "the absent one stays"


def test_read_hand_is_critical_but_resolved():
    """`coil_hand` and the water connection sizes are standing correction levers, offered
    on every coil. Painting them red when nothing is missing is noise that hides the
    inputs that ARE missing."""
    assumed = _items(derive_coil_template_drawing(_hwc(coil_hand=None)))
    assert assumed["coil_hand"]["critical"] and assumed["coil_hand"]["unresolved"] is True
    assert assumed["inlet_conn_size"]["unresolved"] is True

    read = _items(
        derive_coil_template_drawing(_hwc(water_conn_extracted={"inlet": 1.5, "outlet": 1.5}))
    )
    assert read["coil_hand"]["critical"] and read["coil_hand"]["unresolved"] is False
    assert read["inlet_conn_size"]["unresolved"] is False
    assert read["outlet_conn_size"]["unresolved"] is False

    typed = _items(derive_coil_template_drawing(_hwc(inlet_conn_size=2.0)))
    assert typed["inlet_conn_size"]["unresolved"] is False
    assert typed["outlet_conn_size"]["unresolved"] is True
