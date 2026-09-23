"""Terra H / Terra V CWC and HWC drawings are withheld while their SVG templates are
re-seeded (John 2026-09-22: "keep the drawing template vacant for now").

Scope of the gate, pinned in both directions: Terra water only. Terra DX/HGRH, every other
line's water coil (shared Nova/Ventum-H templates, dedicated Ventum+ templates) and the
parameter/checklist values of the withheld coils are untouched.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytest.importorskip("yaml")

from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
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


@pytest.mark.parametrize("product", ["TERRA H", "TERRA V"])
@pytest.mark.parametrize("category", ["CWC", "HWC"])
@pytest.mark.parametrize("hand", ["Left", "Right"])
def test_terra_water_is_withheld_with_a_reason_and_keeps_its_values(product, category, hand):
    out = _derive(category, product, "024", hand)
    assert not out["svg"] and out["template_id"] is None
    assert out["generation_allowed"] is False and out["template_found"] is False
    assert out.get("unregistered_terra_water") is True
    reason = out.get("not_registered_reason") or ""
    assert "re-seeded" in reason and "checklist" in reason
    # The numbers are still there for the panel and the Coil Checklist.
    slots = out.get("slot_values") or {}
    assert slots.get("slot.I1") == (3.25 if product == "TERRA H" else 2.75)
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
