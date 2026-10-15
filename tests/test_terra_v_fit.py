"""Terra V mechanical fit from the 2026-09-22 Coil Checklist: casing (Units tab), drain
pan (Install tab) and the Terra V FIT arms (width vs OAL, height = FH cap by size band).

Until this refresh Terra V had no rows of its own in R-077 / R-078 and was folded onto
Terra H's clearances (width vs FL - 12, height vs CH - 3.875) with a TBD drain pan. John
2026-09-22: "Unit tab, there should be all the sizing data listed for Terra V Casing so
apply on our fit checklist field".
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

pytest.importorskip("yaml")

from coilforge.compatibility.mechanical_fit import (  # noqa: E402
    _drain_pan_row,
    _fit_clearance_row,
    build_mechanical_fit_report,
    evaluate_coil_fit,
)
from coilforge.services.direct_coil_drawing_pipeline import build_header_request  # noqa: E402
from coilforge.services.header_prepopulate_engine import prepopulate  # noqa: E402

_CASING = {  # Units!A56:C68 (W, H)
    "006": (30, 47), "009": (30, 47), "012": (30, 47),
    "015": (44, 58), "018": (44, 58), "024": (44, 58),
    "032": (48, 74), "040": (48, 74), "048": (48, 74),
    "060": (69, 74), "072": (69, 74), "084": (69, 74),
    "100": (77, 76),
}
_PAN = {  # Install!B20:C22
    "006": 28, "009": 28, "012": 28, "015": 29, "018": 29, "024": 29,
    "032": 32, "040": 32, "048": 32, "060": 32, "072": 32, "084": 32, "100": 32,
}
_FH_CAP = {  # HEIGHT FIT Terra V arm (every sheet)
    "006": 24, "009": 24, "012": 24, "015": 24, "018": 24, "024": 24,
    "032": 42, "040": 42, "048": 42, "060": 45, "072": 45, "084": 45, "100": 48,
}


def test_terra_v_casing_matches_the_units_tab_for_all_13_sizes():
    for size, (w, h) in _CASING.items():
        r = prepopulate(build_header_request(
            coil_type="DX", product_type="TERRA V", unit_size=size, application="INTEGRATED",
        ))
        assert (r.suggestions["casing_width"].value, r.suggestions["casing_height"].value) == (w, h), size


def test_terra_v_drain_pan_width_by_size_band():
    for size, width in _PAN.items():
        assert _drain_pan_row("TERRA_V", size, None) == {"drain_pan_width": width}, size


def test_terra_v_has_its_own_fit_rows_on_every_category():
    for cat, w_sub in (("DX", 9.75), ("HGRH", 9.75), ("HWC", 8.75), ("CWC", 8.75)):
        row = _fit_clearance_row(cat, "TERRA_V", None)
        assert row["w_sub"] == w_sub and row["w_basis"] == "OAL", cat
        assert row["h_kind"] == "fh_max_by_size", cat
    # Terra H still resolves through the coarse TERRA row (no own row).
    assert _fit_clearance_row("DX", "TERRA_H", None) == _fit_clearance_row("DX", "TERRA", None)


@pytest.mark.parametrize("cat, w_sub", [("DX", 9.75), ("HGRH", 9.75), ("HWC", 8.75), ("CWC", 8.75)])
def test_terra_v_width_fit_is_casing_width_minus_oal_against_the_threshold(cat, w_sub):
    # size 024 -> W 44. (W - OAL) >= w_sub  <=>  OAL <= 44 - w_sub. Boundary PASS, +0.25 FAIL.
    boundary = 44 - w_sub
    kw = dict(coil_type=cat, product_family="TERRA_V", size_class=None, unit_size="024",
              casing_width=44, casing_height=58, fl=99, fh=10, ch=11)
    ok = evaluate_coil_fit(oal=boundary, **kw)
    assert ok.width.verdict == "PASS" and ok.width.basis == "OAL" and ok.width.margin == 0
    bad = evaluate_coil_fit(oal=boundary + 0.25, **kw)
    assert bad.width.verdict == "FAIL"
    # FL is irrelevant to the Terra V width check (fl=99 above did not fail it).


@pytest.mark.parametrize("size, cap", [("024", 24), ("032", 42), ("060", 45), ("100", 48)])
def test_terra_v_height_fit_is_a_finned_height_cap_by_size_band(size, cap):
    w, h = _CASING[size]
    kw = dict(coil_type="DX", product_family="TERRA_V", size_class=None, unit_size=size,
              casing_width=w, fl=10, ch=999, oal=10)
    ok = evaluate_coil_fit(fh=cap, casing_height=h, **kw)
    assert ok.height.verdict == "PASS" and ok.height.basis == "FH" and ok.height.available == cap
    bad = evaluate_coil_fit(fh=cap + 0.1, casing_height=h, **kw)
    assert bad.height.verdict == "FAIL"
    # Casing height is NOT an input to this check: the verdict is identical without it.
    no_casing = evaluate_coil_fit(fh=cap, casing_height=None, **kw)
    assert no_casing.height.verdict == "PASS"
    assert "casing height not used" in no_casing.height.detail


def test_terra_v_height_fit_without_a_cap_for_the_size_cannot_evaluate():
    res = evaluate_coil_fit(
        coil_type="DX", product_family="TERRA_V", size_class=None, unit_size="999",
        casing_width=44, casing_height=58, fl=10, fh=10, ch=11, oal=10,
    )
    assert res.height.verdict == "CANNOT_EVALUATE" and "no cap" in res.height.detail


def _coil(tag, coil_type, size="072", **over):
    coil = {
        "tag": tag, "coil_type": coil_type, "product_type": "TERRA V", "unit_size": size,
        "finned_height": 30.0, "finned_length": 30.0, "rows": 2, "circuits": 1,
        "suction_conn_size": 0.875, "conn_size": 0.875,
    }
    coil.update(over)
    return coil


def test_terra_v_pair_evaluates_end_to_end_with_no_cannot_evaluate_left():
    # 072: W 69, pan 32, FH cap 45. DX OAL = FL + RB + HD2 = 30 + 1.5 + 3.5 = 35 -> 69 - 35 = 34
    # >= 9.75 PASS; FH 30 <= 45 PASS; CD 3.75 + 3.75 = 7.5 < 32 PASS.
    report = build_mechanical_fit_report(
        [_coil("CDXC-1", "DX"), _coil("RHHGRC-1", "HGRH")], installed_on_drain_pan=True,
    )
    for entry in report.coils:
        assert entry.width.verdict == "PASS", (entry.tag, entry.width.detail)
        assert entry.height.verdict == "PASS", (entry.tag, entry.height.detail)
        assert entry.drain_pan.verdict == "PASS", (entry.tag, entry.drain_pan.detail)
        assert entry.drain_pan.columns[0].width == 32
        assert entry.width.review_required and entry.height.review_required  # still a review aid


def test_terra_v_pair_fails_the_pan_when_the_coils_are_too_deep():
    report = build_mechanical_fit_report(
        [_coil("CDXC-1", "DX", size="006", rows=12), _coil("RHHGRC-1", "HGRH", size="006", rows=12)],
        installed_on_drain_pan=True,
    )
    # rows=12 -> CD 12.5 each -> 25 < 28 still passes; force it with a stated big CD via rows? No:
    # CD is engine-derived, so pin the boundary through evaluate_drain_pan_fit instead.
    from coilforge.compatibility.mechanical_fit import evaluate_drain_pan_fit

    fail = evaluate_drain_pan_fit(
        product_family="TERRA_V", unit_size="006", this_cd=14.0, partner_cd=14.0,
        partner_tag="RHHGRC-1", installed_on_drain_pan=True,
    )
    assert fail.verdict == "FAIL" and fail.columns[0].width == 28
    assert {c.drain_pan.verdict for c in report.coils} == {"PASS"}
