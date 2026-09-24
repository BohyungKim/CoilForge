"""Terra H / Terra V water drawings were withheld while their SVG templates were
re-seeded (John 2026-09-22: "keep the drawing template vacant for now").

2026-09-23: the Terra CWC pair and then the Terra HWC pair were seeded from John's
references (coilmaster_terra_{cwc,hwc}_{lh,rh}, one artwork per category for Terra H and
Terra V), so the gate withholds **nothing** -- it stays as an extension point.

Scope pinned: every Terra water coil draws on its own dedicated template (never the
shared Nova-shaped one); Terra DX/HGRH and every other line's water coil are untouched.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytest.importorskip("yaml")

from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    _TERRA_WATER_WITHHELD_CATEGORIES,
    _TERRA_WATER_WITHHELD_FAMILIES,
    derive_coil_template_drawing,
)


def _derive(category, product, size, hand="Left"):
    return derive_coil_template_drawing(
        dict(coil_category=category, coil_hand=hand, circuits=1, product_type=product,
             unit_size=size, rows=4, finned_height=12, finned_length=15,
             suction_conn_size=0.625)
    )


def test_the_gate_names_exactly_the_two_terra_families():
    assert _TERRA_WATER_WITHHELD_FAMILIES == {"TERRA_H", "TERRA_V"}


def test_no_terra_water_category_is_withheld_any_more():
    """CWC and HWC were both released when their Terra templates were seeded (2026-09-23)."""
    assert _TERRA_WATER_WITHHELD_CATEGORIES == set()


@pytest.mark.parametrize("product", ["TERRA H", "TERRA V"])
@pytest.mark.parametrize("category", ["CWC", "HWC"])
@pytest.mark.parametrize("hand, suffix", [("Left", "lh"), ("Right", "rh")])
def test_terra_water_draws_on_its_own_dedicated_template(product, category, hand, suffix):
    expected = f"coilmaster_terra_{category.lower()}_{suffix}"
    out = _derive(category, product, "024", hand)
    assert out["svg"] and out["generation_allowed"] is True
    assert out["template_id"] == expected
    assert out.get("unregistered_terra_water") is None
    # values are still the Terra variant's own (I/O = 3.25 Terra H, 2.75 Terra V)
    assert out["slot_values"]["slot.I1"] == (3.25 if product == "TERRA H" else 2.75)
    assert out["export_allowed"] is False


@pytest.mark.parametrize("category", ["DX", "HGRH"])
@pytest.mark.parametrize("product", ["TERRA H", "TERRA V"])
def test_terra_dx_and_hgrh_still_draw(category, product):
    out = _derive(category, product, "024")
    assert out["svg"] and out["generation_allowed"] is True
    assert out.get("unregistered_terra_water") is None


@pytest.mark.parametrize("product, size", [("NOVA", "C24"), ("VENTUM_H", "H15"), ("VENTUM_PLUS", "V20")])
@pytest.mark.parametrize("category", ["CWC", "HWC"])
def test_other_lines_water_still_draws(product, size, category):
    out = _derive(category, product, size)
    assert out["svg"] and out["generation_allowed"] is True
    assert out.get("unregistered_terra_water") is None
