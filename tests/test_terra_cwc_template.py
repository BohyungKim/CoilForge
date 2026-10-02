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

_TEMPLATE_ROOT = ROOT / "templates" / "drawing" / "coilmaster"


def _dir(template_id):
    """Terra water buckets live under their own category folder (cwc/ or hwc/)."""
    return _TEMPLATE_ROOT / TERRA_TEMPLATES[template_id][0] / template_id


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


def test_other_lines_do_not_borrow_the_terra_water_art():
    assert _select("NOVA", "LH").template_id == "coilmaster_cwc_lh"
    assert _select(None, "RH").template_id == "coilmaster_cwc_rh"
    assert _select("NOVA", "LH", "HWC").template_id == "coilmaster_hwc_lh"
    assert _select("VENTUM_H", "RH", "HWC").template_id == "coilmaster_hwc_rh"


@pytest.mark.parametrize("family", ["TERRA_H", "TERRA_V", "TERRA H C"])
@pytest.mark.parametrize("hand, expected", [("LH", "coilmaster_terra_hwc_lh"),
                                            ("RH", "coilmaster_terra_hwc_rh")])
def test_terra_hwc_selects_its_dedicated_template(family, hand, expected):
    # Seeded 2026-09-23 from John's TERRA_HWC_LH/RH (HW-A-F-03-11-15.00x22.50-L/R).
    sel = _select(family, hand, "HWC")
    assert sel.found and sel.template_id == expected
    assert sel.entry.product_family == TERRA_FAMILY


def test_bucket_count_includes_the_four_terra_templates():
    assert len(TERRA_TEMPLATES) == 4
    assert len(load_drawing_template_catalog().entries) == TEMPLATE_BUCKET_COUNT


# --- the seeded artwork ------------------------------------------------------------------
@pytest.mark.parametrize("template_id", sorted(TERRA_TEMPLATES))
def test_the_artwork_carries_no_baked_dimension(template_id):
    svg = (_dir(template_id) / "template.svg").read_text(encoding="utf-8")
    texts = re.findall(r"<tspan[^>]*>([^<]*)</tspan>", svg)
    baked = [t for t in texts if re.fullmatch(r"\s*-?\d+(\.\d+)?\s+[A-Z][A-Za-z]{0,3}\d?\s*", t)]
    assert baked == [], baked
    # The supply-header callouts the seeder used to miss are slots now.
    assert "{{slot.HD2}} HD1" in svg and "{{slot.SL2}} SL1" in svg


@pytest.mark.parametrize("template_id", sorted(TERRA_TEMPLATES))
def test_every_placeholder_is_registered_in_the_slot_map(template_id):
    """An unregistered placeholder renders literally (`{{slot.X}}`) -- the redaction gotcha."""
    folder = _dir(template_id)
    used = set(re.findall(r"\{\{(slot\.[A-Z0-9_]+)\}\}", (folder / "template.svg").read_text(encoding="utf-8")))
    registered = {s["slot_id"] for s in json.loads((folder / "slot_map.json").read_text(encoding="utf-8"))["slots"]}
    assert used <= registered, used - registered


def test_each_hand_is_its_own_seed_not_a_mirror():
    meta = {
        t: json.loads((_dir(t) / "template_metadata.json").read_text(encoding="utf-8"))
        for t in TERRA_TEMPLATES
    }
    assert meta["coilmaster_terra_cwc_lh"]["coil_hand"] == "LH"
    assert meta["coilmaster_terra_cwc_rh"]["coil_hand"] == "RH"
    assert meta["coilmaster_terra_hwc_lh"]["coil_hand"] == "LH"
    assert meta["coilmaster_terra_hwc_rh"]["coil_hand"] == "RH"
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
    # The Terra art dimensions O from the opposite end (seed 16.50 = CH 19.25 - I 2.75).
    assert slots["slot.O2"] == round(slots["slot.CH"] - slots["slot.I1"], 4)
    if product == "TERRA V":
        assert (slots["slot.CH"], slots["slot.I1"], slots["slot.O2"]) == (19.25, 2.75, 16.5)
    assert out["export_allowed"] is False


@pytest.mark.parametrize("product", ["TERRA H", "TERRA V"])
@pytest.mark.parametrize("hand, expected", [("Left", "coilmaster_terra_hwc_lh"),
                                            ("Right", "coilmaster_terra_hwc_rh")])
def test_a_terra_hwc_renders_into_its_own_art(product, hand, expected):
    out = derive_coil_template_drawing(dict(
        coil_category="HWC", coil_hand=hand, circuits=1, product_type=product,
        unit_size="006", rows=3, finned_height=15.0, finned_length=22.5,
        suction_conn_size=1.25, water_conn_extracted={"inlet": 1.25, "outlet": 1.25},
    ))
    assert out["template_id"] == expected
    assert out.get("unregistered_terra_water") is not True
    svg, slots = out["svg"], out["slot_values"]
    assert svg and "{{slot." not in svg
    assert slots["slot.S1"] == 1.25 and slots["slot.R2"] == 1.25   # HWC S = IN, R = OUT
    # Opposite-datum art (seed O2 13.50 = CH 16.25 - I1 2.75, both hands).
    assert slots["slot.O2"] == round(slots["slot.CH"] - slots["slot.I1"], 4)
    assert out["export_allowed"] is False


def test_terra_hwc_seed_evidence_is_opposite_datum():
    for t in ("coilmaster_terra_hwc_lh", "coilmaster_terra_hwc_rh"):
        ev = json.loads((_dir(t) / "seed_evidence.json").read_text(encoding="utf-8"))
        vals = {e["slot_id"]: float(e["value"]) for e in ev["slot_evidence"]
                if e["slot_id"] in ("slot.CH", "slot.I1", "slot.O2")}
        assert vals == {"slot.CH": 16.25, "slot.I1": 2.75, "slot.O2": 13.5}, t


def _terra_v_cwc(**extra):
    return dict(
        coil_category="CWC", coil_hand="Left", circuits=1, product_type="TERRA V",
        unit_size="006", rows=6, finned_height=18.0, finned_length=36.0,
        suction_conn_size=1.0, water_conn_extracted={"inlet": 1.0, "outlet": 1.0}, **extra,
    )


def _ov(key, value):
    return {"key": key, "value": value, "override_reason": "test"}


def test_a_manual_ch_or_i_carries_the_opposite_datum_o_with_it():
    ch = derive_coil_template_drawing(_terra_v_cwc(param_overrides=[_ov("CH", 20.0)]))
    assert ch["slot_values"]["slot.O2"] == 17.25                # 20 - 2.75
    i = derive_coil_template_drawing(_terra_v_cwc(param_overrides=[_ov("I", "3")]))
    assert i["slot_values"]["slot.O2"] == 16.25                 # 19.25 - 3
    # An O the engineer typed wins over the recompute.
    both = derive_coil_template_drawing(
        _terra_v_cwc(param_overrides=[_ov("CH", 20.0), _ov("O", 15.0)])
    )
    assert both["slot_values"]["slot.O2"] == 15.0


def test_an_unresolved_ch_leaves_the_terra_o_blank_instead_of_printing_i():
    out = derive_coil_template_drawing(dict(_terra_v_cwc(), finned_height=None))
    assert "slot.O2" not in out["slot_values"]
    reason = out["drawing_parameter_set"]["parameters"]["O"]["blocked_reason"]
    assert "opposite end" in reason


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
