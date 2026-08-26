"""Omnia (OW### model codes) — a first-class family that IS Ventum+ except TF/BF.

John 2026-08-25: "everything is exactly the same rule and drawing template as Ventum+;
the only difference is TF and BF = 0.625". The load-bearing test here is the field-by-
field equality of the engine output against a Ventum+ request: if a Ventum+ rule or a
Python `== VENTUM_PLUS` branch ever forgets Omnia, that comparison goes red.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.checklist.mapping import build_checklist_fill  # noqa: E402
from coilforge.compatibility.mechanical_fit import (  # noqa: E402
    evaluate_coil_fit,
    evaluate_drain_pan_fit,
)
from coilforge.review.divergence import annotate_known_divergences, load_registry  # noqa: E402
from coilforge.schemas.header_prepopulate import (  # noqa: E402
    CoilType,
    HeaderPrepopulateRequest,
    ProductFamily,
)
from coilforge.services.direct_coil_drawing_pipeline import build_drawing_slots  # noqa: E402
from coilforge.services.header_prepopulate_engine import prepopulate  # noqa: E402
from coilforge.submittal.coilmaster_drawing_extract import (  # noqa: E402
    detect_product_and_size,
    product_for_unit_size,
    product_size_options,
    resolve_product_line,
)
from coilforge.template_population.catalog import (  # noqa: E402
    TEMPLATE_BUCKET_COUNT,
    VENTUM_PLUS_TEMPLATES,
    load_drawing_template_catalog,
)
from coilforge.workflows.submittal_to_drawing import derive_coil_template_drawing  # noqa: E402

OMNIA_SIZES = ["OW050", "OW055", "OW060", "OW070", "OW075", "OW080", "OW085"]
FLANGES = ("top_flange", "bottom_flange")


# --------------------------------------------------------------------------- #
# detection — no dedicated regex; the R-076 token does the work
# --------------------------------------------------------------------------- #
def test_omnia_model_code_detects_from_the_r076_token():
    cover = "ERV-1 ERV OW085_I_Wheel 208V/3ph/60Hz Vertical S2 LH CDXC-1 DXC Cooling OW085_I"
    assert detect_product_and_size(cover) == ("OMNIA", "OW085")
    assert detect_product_and_size("OW085_I") == ("OMNIA", "OW085")
    assert detect_product_and_size("OW085") == ("OMNIA", "OW085")


def test_unknown_omnia_size_is_not_invented():
    assert detect_product_and_size("OW999_I") == (None, None)
    assert product_for_unit_size("OW999") is None


def test_existing_detections_are_untouched():
    assert detect_product_and_size("H30_I_ERV V150 1 16 x 20") == ("VENTUM_H", "H30")
    assert detect_product_and_size("TR_C_009") == ("TERRA H", "009")
    assert detect_product_and_size("V40_I_ERV") == ("VENTUM_PLUS", "V40")


def test_product_line_resolution_and_size_picker():
    assert resolve_product_line("OMNIA") == ("OMNIA", None)
    assert product_size_options()["OMNIA"] == OMNIA_SIZES
    assert product_for_unit_size("OW050") == "OMNIA"


# --------------------------------------------------------------------------- #
# engine — Omnia == Ventum+ except TF/BF
# --------------------------------------------------------------------------- #
def _req(coil: CoilType, product: ProductFamily, size: str, **kw):
    return HeaderPrepopulateRequest(
        type_of_coil=coil, product_type=product, unit_size=size, **kw
    )


def _bucket_dump(resp):
    """{bucket: {field: (value, rule_id, confidence)}} minus the fields that legitimately
    differ (flanges) and the size-keyed casing lookup (R-074 has no Omnia rows yet)."""
    skip = set(FLANGES) | {"casing_width", "casing_height"}
    out = {}
    for bucket in ("values", "suggestions", "blocked"):
        items = getattr(resp, bucket)
        out[bucket] = {
            f: (v.value, v.rule_id, getattr(v.confidence, "value", v.confidence))
            for f, v in items.items() if f not in skip
        }
    return out


_CASES = [
    (CoilType.DX, dict(circuits=1, conn_size=0.875, rows=4)),
    (CoilType.DX, dict(circuits=2, qty_conn_per_header=2, conn_size=1.125, rows=6)),
    (CoilType.DX, dict(circuits=3, qty_conn_per_header=3, conn_size=1.375, rows=6)),
    (CoilType.HGRH, dict(circuits=1, qty_conn_per_header=1, conn_size=0.875, rows=2)),
    (CoilType.HGRH, dict(circuits=2, qty_conn_per_header=2, conn_size=1.125, rows=2)),
    (CoilType.CWC, dict(feeds=1, conn_size=1.5, rows=4)),
    (CoilType.CWC, dict(feeds=4, conn_size=2.0, rows=6)),
    (CoilType.HWC, dict(feeds=1, conn_size=1.0, rows=2)),
    (CoilType.HWC, dict(feeds=2, conn_size=1.5, rows=2)),
]


def _kw(kw):
    fields = HeaderPrepopulateRequest.model_fields
    unknown = set(kw) - set(fields)
    assert not unknown, f"case over-specified: {unknown}"
    return kw


@pytest.mark.parametrize(
    "coil,kw", _CASES, ids=[f"{c.value}-{i}" for i, (c, _) in enumerate(_CASES)]
)
def test_omnia_engine_output_equals_ventum_plus_except_flanges(coil, kw):
    omnia = prepopulate(_req(coil, ProductFamily.OMNIA, "OW085", **_kw(kw)))
    vplus = prepopulate(_req(coil, ProductFamily.VENTUM_PLUS, "V80", **_kw(kw)))
    assert _bucket_dump(omnia) == _bucket_dump(vplus)
    for f in FLANGES:
        assert omnia.values[f].value == 0.625 and omnia.values[f].rule_id == "R-011o"
        assert vplus.values[f].value == 1 and vplus.values[f].rule_id == "R-011"


def test_omnia_casing_is_blocked_not_guessed():
    # The sizing chart John supplied gives the coil envelope, not the unit casing, so
    # R-074 carries no OMNIA rows: casing must come out absent, never borrowed.
    resp = prepopulate(
        _req(CoilType.DX, ProductFamily.OMNIA, "OW085", circuits=1, conn_size=0.875)
    )
    for f in ("casing_width", "casing_height"):
        assert f not in resp.values and f not in resp.suggestions, f


def test_every_omnia_size_passes_the_r076_gate():
    for size in OMNIA_SIZES:
        resp = prepopulate(
            _req(CoilType.DX, ProductFamily.OMNIA, size, circuits=1, conn_size=0.875)
        )
        assert resp.values["top_flange"].value == 0.625, size
    bad = prepopulate(
        _req(CoilType.DX, ProductFamily.OMNIA, "V80", circuits=1, conn_size=0.875)
    )
    assert "top_flange" not in bad.values  # a Ventum+ size is not an Omnia size


# --------------------------------------------------------------------------- #
# slots / drawing
# --------------------------------------------------------------------------- #
def test_omnia_slots_carry_the_flange_and_ch():
    slots, _ = build_drawing_slots(
        coil_type="DX", product_type="OMNIA", unit_size="OW085", rows=4,
        circuits=1, suction_conn_size=0.875, finned_height=20.0, finned_length=60.0,
    )
    assert slots["slot.TF"] == 0.625 and slots["slot.BF"] == 0.625
    assert slots["slot.CH"] == pytest.approx(20.0 + 1.25)


def _derive(category, hand, circuits):
    return derive_coil_template_drawing(
        dict(coil_category=category, coil_hand=hand, circuits=circuits,
             product_type="OMNIA", unit_size="OW085", rows=4,
             finned_height=12, finned_length=15, suction_conn_size=0.625)
    )


def test_omnia_dx_draws_on_the_dedicated_ventum_plus_template():
    out = _derive("DX", "Right", 1)
    assert out["template_id"] == "coilmaster_vplus_dx_rh_header1"
    assert out["dedicated_family_template"] == "VENTUM_PLUS"
    assert out["svg"] and out["export_allowed"] is False
    assert out.get("distributor_orientation_warning") is None


def test_omnia_unseeded_dx_is_gated_like_ventum_plus():
    out = _derive("DX", "Right", 3)  # no vplus DX RH 3-header reference is seeded
    assert not out["svg"] and out["template_found"] is False
    assert out.get("unregistered_ventum_plus_dx") is True
    assert "R-032" in (out.get("not_registered_reason") or "")


def test_omnia_water_and_hgrh_draw():
    for category, hand, tid in (
        ("HWC", "Left", "coilmaster_vplus_hwc_lh"),
        ("CWC", "Left", "coilmaster_vplus_cwc_lh"),
        ("HGRH", "Right", "coilmaster_vplus_hgrh_rh_header1"),
    ):
        out = _derive(category, hand, 1)
        assert out["svg"], category
        assert out["template_id"] == tid, category


def test_no_omnia_bucket_was_seeded():
    # Omnia is an alias onto the Ventum+ set — the catalog must not have grown.
    catalog = load_drawing_template_catalog()
    assert len(catalog.entries) == TEMPLATE_BUCKET_COUNT
    assert not any("omnia" in t.template_id.lower() for t in catalog.entries)
    assert not any(t.product_family == "OMNIA" for t in catalog.entries)
    assert len(VENTUM_PLUS_TEMPLATES) == 11


# --------------------------------------------------------------------------- #
# checklist + known divergence
# --------------------------------------------------------------------------- #
def _dx_coil(**over):
    coil = dict(
        tag="CDXC-1", coil_type="DX", product_label="OMNIA", unit_size="OW085",
        quantity=1, finned_height=21.0, finned_length=70.0, rows=4, feeds=6,
        circuits=1, suction_conn_size=0.875, qty_conn_per_header=1, coil_hand="L",
        coating=None,
    )
    coil.update(over)
    return coil


def test_checklist_fills_unit_as_ventum_plus_and_leaves_size_blank():
    fill = build_checklist_fill([_dx_coil()])
    cells = {c.label: c for c in fill.sheets[0].cells}
    assert cells["UNIT"].value == "VENTUM+"
    assert cells["SIZE"].value is None  # OW085 is not in the workbook's VENTUM+ list


def test_omnia_flange_divergence_is_a_known_ruling():
    registry = load_registry(staging_path=Path("does-not-exist.yaml"))
    review = {"sheets": [{"tag": "CDXC-1", "category": "DX", "comparisons": [
        {"label": "TF", "slot": "slot.TF", "coilforge": 0.625, "checklist": 1.0,
         "verdict": "mismatch"},
        {"label": "BF", "slot": "slot.BF", "coilforge": 0.625, "checklist": 1.0,
         "verdict": "mismatch"},
        {"label": "TF", "slot": "slot.TF", "coilforge": 0.625, "checklist": 2.0,
         "verdict": "mismatch"},
        {"label": "CH", "slot": "slot.CH", "coilforge": 28.25, "checklist": 29.0,
         "verdict": "mismatch"},
    ]}]}
    coils = [{"tag": "CDXC-1", "coil_type": "DX", "product_label": "OMNIA",
              "unit_size": "OW085"}]
    out = annotate_known_divergences(copy.deepcopy(review), coils, registry=registry)
    rows = out["sheets"][0]["comparisons"]
    assert rows[0]["divergence"]["id"] == "KD-010"
    assert rows[1]["divergence"]["id"] == "KD-011"
    assert rows[2].get("divergence", {}).get("in_band") is not True  # wrong magnitude
    assert rows[3]["divergence"]["id"] == "KD-018"  # CH = FH + TF + BF, live 3097 case
    # A Ventum+ coil with the same numbers is NOT covered — the ruling is Omnia-scoped.
    vp = annotate_known_divergences(
        copy.deepcopy(review), [dict(coils[0], product_label="VENTUM_PLUS")],
        registry=registry,
    )
    assert "divergence" not in vp["sheets"][0]["comparisons"][0]


# --------------------------------------------------------------------------- #
# mechanical fit — no casing / drain-pan data yet
# --------------------------------------------------------------------------- #
def test_omnia_fit_cannot_evaluate_without_casing_rows():
    res = evaluate_coil_fit(
        coil_type="DX", product_family="OMNIA", size_class=None,
        casing_width=None, casing_height=None, fl=70, fh=21, ch=None, oal=None,
    )
    assert res.width.verdict == "CANNOT_EVALUATE"
    assert res.height.verdict == "CANNOT_EVALUATE"
    pan = evaluate_drain_pan_fit(
        product_family="OMNIA", unit_size="OW085", this_cd=9, partner_cd=9,
        partner_tag="RHHGRH-1", installed_on_drain_pan=True,
    )
    assert pan.verdict == "CANNOT_EVALUATE"
