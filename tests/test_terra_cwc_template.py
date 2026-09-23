"""Terra CWC dedicated templates + water S/R/CD from the Coil Checklist (John 2026-09-23).

Seeded from John's own CoilMaster drawings of one CWC in each hand (TERRA_CCWC_LH/RH,
created 2026-09-23). One artwork serves Terra H and Terra V -- every printed value is
CoilForge's own, filled per coil. Each hand is its own seed (never a mirror).

Alongside it, water S/R/CD follow the checklist on every product line: CWC S = IN/2 + 3,
R = OUT; HWC S = IN, R = OUT; CD = MAX(rows base, R-071 connection term).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.template_population.catalog import (  # noqa: E402
    TEMPLATE_BUCKET_COUNT,
    TEMPLATE_FAMILY_ALIAS,
    TERRA_FAMILY,
    TERRA_TEMPLATES,
    TemplateSelectionRequest,
    load_drawing_template_catalog,
    select_drawing_template,
)
from coilforge.workflows.submittal_to_drawing import derive_coil_template_drawing  # noqa: E402

_CWC_DIR = ROOT / "templates" / "drawing" / "coilmaster" / "cwc"


def _select(family, hand, category="CWC"):
    return select_drawing_template(TemplateSelectionRequest(
        supplier="coilmaster", coil_category=category, coil_hand=hand,
        header_type="Header 1", product_family=family,
    ))


# --- catalog --------------------------------------------------------------------------
def test_both_terra_lines_and_every_spelling_fold_onto_one_bucket_family():
    for token in ("TERRA_H", "TERRA_V", "TERRA_H_C", "TERRA H", "TERRA V", "TERRA H C"):
        assert TEMPLATE_FAMILY_ALIAS[token] == TERRA_FAMILY, token


@pytest.mark.parametrize("family", ["TERRA_H", "TERRA_V", "TERRA H C"])
@pytest.mark.parametrize("hand, expected", [("LH", "coilmaster_terra_cwc_lh"),
                                            ("RH", "coilmaster_terra_cwc_rh")])
def test_terra_cwc_selects_its_dedicated_template(family, hand, expected):
    sel = _select(family, hand)
    assert sel.found and sel.template_id == expected
    assert sel.entry.product_family == TERRA_FAMILY


def test_other_lines_and_terra_hwc_do_not_borrow_the_terra_cwc_art():
    assert _select("NOVA", "LH").template_id == "coilmaster_cwc_lh"
    assert _select(None, "RH").template_id == "coilmaster_cwc_rh"
    # Terra HWC has no dedicated bucket yet: it falls back to the SHARED one here, and
    # the workflow gate is what keeps that drawing withheld (tests/test_terra_water_...).
    assert _select("TERRA_V", "LH", "HWC").template_id == "coilmaster_hwc_lh"


def test_bucket_count_includes_the_two_terra_templates():
    assert len(TERRA_TEMPLATES) == 2
    assert len(load_drawing_template_catalog().entries) == TEMPLATE_BUCKET_COUNT


# --- the seeded artwork ------------------------------------------------------------------
@pytest.mark.parametrize("template_id", sorted(TERRA_TEMPLATES))
def test_the_artwork_carries_no_baked_dimension(template_id):
    svg = (_CWC_DIR / template_id / "template.svg").read_text(encoding="utf-8")
    texts = re.findall(r"<tspan[^>]*>([^<]*)</tspan>", svg)
    baked = [t for t in texts if re.fullmatch(r"\s*-?\d+(\.\d+)?\s+[A-Z][A-Za-z]{0,3}\d?\s*", t)]
    assert baked == [], baked
    # The supply-header callouts the seeder used to miss are slots now.
    assert "{{slot.HD2}} HD1" in svg and "{{slot.SL2}} SL1" in svg


@pytest.mark.parametrize("template_id", sorted(TERRA_TEMPLATES))
def test_every_placeholder_is_registered_in_the_slot_map(template_id):
    """An unregistered placeholder renders literally (`{{slot.X}}`) -- the redaction gotcha."""
    folder = _CWC_DIR / template_id
    used = set(re.findall(r"\{\{(slot\.[A-Z0-9_]+)\}\}", (folder / "template.svg").read_text(encoding="utf-8")))
    registered = {s["slot_id"] for s in json.loads((folder / "slot_map.json").read_text(encoding="utf-8"))["slots"]}
    assert used <= registered, used - registered


def test_each_hand_is_its_own_seed_not_a_mirror():
    meta = {
        t: json.loads((_CWC_DIR / t / "template_metadata.json").read_text(encoding="utf-8"))
        for t in TERRA_TEMPLATES
    }
    assert meta["coilmaster_terra_cwc_lh"]["coil_hand"] == "LH"
    assert meta["coilmaster_terra_cwc_rh"]["coil_hand"] == "RH"
    for m in meta.values():
        assert m["seed_method"].startswith("vectorised_from_provided_ez_drawing_pdf")
        assert m["export_allowed"] is False and m["production_approved"] is False


# --- rendered through the workflow -------------------------------------------------------
@pytest.mark.parametrize("product", ["TERRA H", "TERRA V"])
def test_a_terra_cwc_renders_coilforge_values_into_the_terra_art(product):
    out = derive_coil_template_drawing(dict(
        coil_category="CWC", coil_hand="Left", circuits=1, product_type=product,
        unit_size="006", rows=6, finned_height=18.0, finned_length=36.0,
        suction_conn_size=1.0, water_conn_extracted={"inlet": 1.0, "outlet": 1.0},
    ))
    assert out["template_id"] == "coilmaster_terra_cwc_lh"
    svg, slots = out["svg"], out["slot_values"]
    assert "{{slot." not in svg, "no placeholder left unfilled"
    assert slots["slot.S1"] == 3.5 and slots["slot.R2"] == 1.0   # CWC S = IN/2 + 3, R = OUT
    assert out["export_allowed"] is False


# --- water CD / S / R from the checklist, every path ------------------------------------
def test_drawing_and_checklist_agree_on_water_cd_s_and_r():
    from coilforge.checklist.mapping import _resolve_engine

    for cat, product, size in (("CWC", "NOVA", "C24"), ("HWC", "TERRA H", "012")):
        drawn = derive_coil_template_drawing(dict(
            coil_category=cat, tag="X-1", circuits=1, rows=2, finned_height=30.0,
            finned_length=40.0, product_type=product, unit_size=size, suction_conn_size=1.25,
            water_conn_extracted={"inlet": 1.5, "outlet": 1.25},
        ))["slot_values"]
        sheet, _ = _resolve_engine(
            {"coil_type": cat, "product_label": product, "unit_size": size, "rows": 2,
             "circuits": 1, "suction_conn_size": 1.25, "inlet_conn_size": 1.5,
             "outlet_conn_size": 1.25, "finned_height": 30.0, "finned_length": 40.0,
             "tag": "X-1"},
            None,
        )
        for slot in ("slot.CD", "slot.S1", "slot.R2"):
            assert drawn[slot] == sheet[slot], (cat, slot, drawn[slot], sheet[slot])
