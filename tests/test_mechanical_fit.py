"""Tests for the per-coil mechanical WIDTH/HEIGHT fit checks (Phase 1).

Expected verdicts are hand-computed from the four CHK FIT formulas
(Coil Checklist Template.xlsx): WIDTH/HEIGHT FIT = (casing_dim[/2] - clearance)
>= basis_value. Casing dims used below are the real R-074 values for the named
(product_family, application, unit_size). One integration test pulls the casing
dims + size_class straight from the engine to confirm the data flow.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.compatibility.mechanical_fit import (  # noqa: E402
    build_mechanical_fit_report,
    evaluate_coil_fit,
    evaluate_drain_pan_fit,
    mechanical_fit_report_dict,
)
from coilforge.schemas.header_prepopulate import (  # noqa: E402
    HeaderPrepopulateRequest,
)
from coilforge.services.header_prepopulate_engine import prepopulate  # noqa: E402
from coilforge.submittal.pdf_intake import (  # noqa: E402
    coil_category_of_tag,
    drain_pan_partner_tag,
)


# --------------------------------------------------------------------------- #
# Verdict math — one case per category, NOVA size classes, VENTUM+ half-height
# --------------------------------------------------------------------------- #
def test_dx_nova_2in_pass():
    # R-074 NOVA|DECOUPLED|A18 => W=36 H=22 ; R-078 DX|NOVA_2IN w_sub=12 h_sub=6 (FH)
    res = evaluate_coil_fit(
        coil_type="DX", product_family="NOVA", size_class="NOVA_2IN",
        casing_width=36, casing_height=22, fl=20, fh=14, ch=None, oal=None,
    )
    assert res.width.verdict == "PASS"
    assert res.width.available == 24 and res.width.margin == 4
    assert res.width.basis == "FL"
    assert res.height.verdict == "PASS"
    assert res.height.available == 16 and res.height.basis == "FH"
    # casing dims are MEDIUM upstream => every verdict stays review-required.
    assert res.width.review_required and res.height.review_required


def test_dx_nova_2in_width_fail():
    res = evaluate_coil_fit(
        coil_type="DX", product_family="NOVA", size_class="NOVA_2IN",
        casing_width=36, casing_height=22, fl=30, fh=14, ch=None, oal=None,
    )
    assert res.width.verdict == "FAIL" and res.width.margin == -6
    assert "DOES NOT FIT" in res.width.detail
    assert res.height.verdict == "PASS"


def test_dx_terra_uses_ch_for_height():
    # R-074 TERRA|INTEGRATED|012 => W=44 H=20 ; R-078 DX|TERRA h_sub=3.875 basis CH
    res = evaluate_coil_fit(
        coil_type="DX", product_family="TERRA", size_class=None,
        casing_width=44, casing_height=20, fl=30, fh=99, ch=15, oal=None,
    )
    assert res.width.verdict == "PASS" and res.width.margin == 2
    assert res.height.basis == "CH"  # NOT FH — DX/Terra height is CH-based
    assert res.height.available == 16.125 and res.height.verdict == "PASS"


def test_ventum_plus_dx_half_height():
    # R-074 VENTUM_PLUS|INTEGRATED|V20 => W=56.375 H=52 ; half-height: 52/2 - 8.25
    res = evaluate_coil_fit(
        coil_type="DX", product_family="VENTUM_PLUS", size_class=None,
        casing_width=56.375, casing_height=52, fl=40, fh=16, ch=None, oal=None,
    )
    assert res.height.half is True
    assert res.height.available == 17.75  # 26 - 8.25
    assert res.height.verdict == "PASS" and res.height.basis == "FH"
    assert res.width.verdict == "PASS"


def test_hgrh_nova_1in_uses_ch_for_height():
    # HGRH height basis is CH for ALL families (unlike DX). NOVA|DECOUPLED|A16 W=34 H=20
    res = evaluate_coil_fit(
        coil_type="HGRH", product_family="NOVA", size_class="NOVA_1IN",
        casing_width=34, casing_height=20, fl=20, fh=99, ch=14, oal=None,
    )
    assert res.width.available == 23.5 and res.width.verdict == "PASS"  # 34 - 10.5
    assert res.height.basis == "CH"
    assert res.height.available == 15.5 and res.height.verdict == "PASS"  # 20 - 4.5


def test_cwc_nova_1in_height_clearance_five():
    # CWC NOVA_1IN height clearance is 5 (bigger than HWC's 2.5). Width basis OAL.
    res = evaluate_coil_fit(
        coil_type="CWC", product_family="NOVA", size_class="NOVA_1IN",
        casing_width=34, casing_height=20, fl=None, fh=None, ch=14, oal=30,
    )
    assert res.width.basis == "OAL"
    assert res.width.available == 31.5 and res.width.verdict == "PASS"  # 34 - 2.5
    assert res.height.available == 15 and res.height.verdict == "PASS"  # 20 - 5


def test_hwc_nova_2in_width_fail_on_oal():
    # NOVA|CPLD/DCPLD VERT|A18 => W=17.625 H=21.875 ; HWC|NOVA_2IN w_sub=4 basis OAL
    res = evaluate_coil_fit(
        coil_type="HWC", product_family="NOVA", size_class="NOVA_2IN",
        casing_width=17.625, casing_height=21.875, fl=None, fh=None, ch=16, oal=20,
    )
    assert res.width.basis == "OAL"
    assert res.width.available == 13.625 and res.width.verdict == "FAIL"
    assert res.height.verdict == "PASS"


# --------------------------------------------------------------------------- #
# Missing-input degradation (never guess)
# --------------------------------------------------------------------------- #
def test_missing_casing_dim_cannot_evaluate():
    res = evaluate_coil_fit(
        coil_type="DX", product_family="NOVA", size_class="NOVA_2IN",
        casing_width=None, casing_height=22, fl=20, fh=14, ch=None, oal=None,
    )
    assert res.width.verdict == "CANNOT_EVALUATE" and res.width.available is None
    assert res.height.verdict == "PASS"  # height still evaluable


def test_missing_basis_cannot_evaluate_but_reports_available():
    res = evaluate_coil_fit(
        coil_type="DX", product_family="NOVA", size_class="NOVA_2IN",
        casing_width=36, casing_height=22, fl=None, fh=14, ch=None, oal=None,
    )
    assert res.width.verdict == "CANNOT_EVALUATE"
    assert res.width.available == 24  # still surfaces the clearance space
    assert res.width.required is None


def test_nova_without_size_class_cannot_evaluate():
    res = evaluate_coil_fit(
        coil_type="DX", product_family="NOVA", size_class=None,
        casing_width=36, casing_height=22, fl=20, fh=14, ch=None, oal=None,
    )
    assert res.width.verdict == "CANNOT_EVALUATE"
    assert res.height.verdict == "CANNOT_EVALUATE"


# --------------------------------------------------------------------------- #
# Integration: casing dims + size_class sourced from the real engine
# --------------------------------------------------------------------------- #
def test_casing_dims_from_engine_feed_fit():
    req = HeaderPrepopulateRequest(
        type_of_coil="DX", product_type="NOVA", unit_size="A18",
        application="DECOUPLED", rows=4,
    )
    resp = prepopulate(req)
    casing_w = resp.suggestions["casing_width"].value
    casing_h = resp.suggestions["casing_height"].value
    size_class = resp.values["size_class"].value
    assert (casing_w, casing_h) == (36, 22)
    assert size_class == "NOVA_2IN"
    res = evaluate_coil_fit(
        coil_type="DX", product_family="NOVA", size_class=size_class,
        casing_width=casing_w, casing_height=casing_h,
        fl=20, fh=14, ch=None, oal=None,
    )
    assert res.width.verdict == "PASS" and res.height.verdict == "PASS"


# --------------------------------------------------------------------------- #
# Phase 2 — coil pairing (DX<->HGRH, CWC<->HWC by tag sequence)
# --------------------------------------------------------------------------- #
def test_pairing_dx_to_hgrh_by_sequence():
    tags = ["CDXC-1", "RHHGRH-1", "CDXC-2", "RHHGRC-2"]
    assert drain_pan_partner_tag("CDXC-1", tags) == "RHHGRH-1"
    assert drain_pan_partner_tag("CDXC-2", tags) == "RHHGRC-2"
    assert drain_pan_partner_tag("RHHGRH-1", tags) == "CDXC-1"


def test_pairing_cwc_to_hwc():
    tags = ["CCWC-1", "HHWC-1"]
    assert drain_pan_partner_tag("CCWC-1", tags) == "HHWC-1"
    assert drain_pan_partner_tag("HHWC-1", tags) == "CCWC-1"


def test_pairing_hhwc_and_phwc_are_not_partners():
    # Both are Hot Water Coil; their partner is Chilled Water, never each other.
    assert drain_pan_partner_tag("HHWC-1", ["PHWC-1"]) is None
    assert coil_category_of_tag("HHWC-1") == "Hot Water Coil"
    assert coil_category_of_tag("PHWC-1") == "Hot Water Coil"


def test_pairing_standalone_returns_none():
    assert drain_pan_partner_tag("CDXC-1", ["CDXC-1", "CCWC-1"]) is None
    assert drain_pan_partner_tag("ABC-1", ["XYZ-1"]) is None


# --------------------------------------------------------------------------- #
# Phase 2 — drain-pan / install fit (pair check, strict <)
# --------------------------------------------------------------------------- #
def test_drain_pan_nova_surfaces_both_columns_with_access_fails():
    # NOVA|A18 => coil_module_only=19.375, with_access=14.875 ; combined CD 16.
    res = evaluate_drain_pan_fit(
        product_family="NOVA", unit_size="A18", this_cd=8, partner_cd=8,
        partner_tag="RHHGRH-1", installed_on_drain_pan=True,
    )
    cols = {c.column: c for c in res.columns}
    assert cols["coil_module_only"].verdict == "PASS" and cols["coil_module_only"].margin == 3.375
    assert cols["with_access"].verdict == "FAIL" and cols["with_access"].margin == -1.125
    assert res.verdict == "FAIL"  # aggregate: any column failing => FAIL


def test_drain_pan_nova_both_pass():
    res = evaluate_drain_pan_fit(
        product_family="NOVA", unit_size="A18", this_cd=6, partner_cd=6,
        partner_tag="RHHGRH-1", installed_on_drain_pan=True,
    )
    assert res.verdict == "PASS"
    assert all(c.verdict == "PASS" for c in res.columns)


def test_drain_pan_ventum_plus_uses_install_width_as_basis():
    # VENTUM_PLUS|V20 => install_width=17, drain_pan_width=21.875 ; combined 18.
    res = evaluate_drain_pan_fit(
        product_family="VENTUM_PLUS", unit_size="V20", this_cd=9, partner_cd=9,
        partner_tag="RHHGRH-1", installed_on_drain_pan=True,
    )
    cols = {c.column: c for c in res.columns}
    assert cols["install_width"].verdict == "FAIL"  # 17 - 18 < 0
    assert cols["drain_pan_width"].verdict == "PASS"  # 21.875 - 18 > 0
    assert res.verdict == "FAIL"  # install_width is the binding basis for VENTUM+


def test_drain_pan_not_installed_is_not_applicable():
    res = evaluate_drain_pan_fit(
        product_family="NOVA", unit_size="A18", this_cd=8, partner_cd=8,
        partner_tag="RHHGRH-1", installed_on_drain_pan=False,
    )
    assert res.verdict == "NOT_APPLICABLE" and res.columns == ()


def test_drain_pan_no_partner_cannot_evaluate():
    res = evaluate_drain_pan_fit(
        product_family="NOVA", unit_size="A18", this_cd=8, partner_cd=None,
        partner_tag=None, installed_on_drain_pan=True,
    )
    assert res.verdict == "CANNOT_EVALUATE"


def test_drain_pan_terra_needs_option():
    res = evaluate_drain_pan_fit(
        product_family="TERRA", unit_size="012", this_cd=8, partner_cd=8,
        partner_tag="RHHGRH-1", installed_on_drain_pan=True, drain_pan_option=None,
    )
    assert res.verdict == "CANNOT_EVALUATE" and "option" in res.detail


def test_drain_pan_terra_with_option():
    # TERRA|D2 => drain_pan_width 20.5 ; combined 16 => PASS.
    res = evaluate_drain_pan_fit(
        product_family="TERRA", unit_size="012", this_cd=8, partner_cd=8,
        partner_tag="RHHGRH-1", installed_on_drain_pan=True, drain_pan_option="D2",
    )
    assert res.verdict == "PASS"
    assert res.columns[0].width == 20.5


# --------------------------------------------------------------------------- #
# Phase 3 — report builder (engine-sourced) + pairing + serialization + API
# --------------------------------------------------------------------------- #
def _dx_hgrh_pair():
    return [
        {"tag": "CDXC-1", "coil_type": "DX", "product_type": "NOVA",
         "unit_size": "A18", "application": "DECOUPLED", "rows": 4,
         "finned_height": 14, "finned_length": 20},
        {"tag": "RHHGRH-1", "coil_type": "HGRH", "product_type": "NOVA",
         "unit_size": "A18", "application": "DECOUPLED", "rows": 2,
         "finned_height": 6, "finned_length": 20},
    ]


def test_report_resolves_casing_and_pairs_drain_pan():
    rep = build_mechanical_fit_report(_dx_hgrh_pair(), installed_on_drain_pan=True)
    by_tag = {c.tag: c for c in rep.coils}
    dx = by_tag["CDXC-1"]
    hgrh = by_tag["RHHGRH-1"]
    # casing dims came from R-074 via the engine; width/height evaluated.
    assert (dx.casing_width, dx.casing_height) == (36, 22)
    assert dx.width.verdict == "PASS" and dx.height.verdict == "PASS"
    # HGRH height is CH-based (not FH).
    assert hgrh.height.basis == "CH"
    # drain-pan paired both ways, combined CD = DX CD + HGRH CD.
    assert dx.partner_tag == "RHHGRH-1" and hgrh.partner_tag == "CDXC-1"
    assert dx.drain_pan.verdict == "PASS"
    assert dx.drain_pan.columns[0].combined_cd == round(dx.cd + hgrh.cd, 4)
    assert rep.export_allowed is False


def test_report_single_coil_drain_pan_not_applicable_when_not_installed():
    rep = build_mechanical_fit_report(_dx_hgrh_pair()[:1], installed_on_drain_pan=False)
    coil = rep.coils[0]
    assert coil.width.verdict in {"PASS", "FAIL"}
    assert coil.drain_pan.verdict == "NOT_APPLICABLE"
    assert coil.partner_tag is None


def test_report_missing_product_is_noted_not_dropped():
    rep = build_mechanical_fit_report(
        [{"tag": "CDXC-9", "coil_type": "DX", "finned_height": 14}]
    )
    assert len(rep.coils) == 1
    assert rep.coils[0].note and rep.coils[0].width is None


def test_mechanical_fit_endpoint():
    fastapi = pytest.importorskip("fastapi")  # noqa: F841
    from fastapi.testclient import TestClient

    from coilforge.web_app import app

    client = TestClient(app)
    resp = client.post(
        "/api/mechanical-fit",
        json={"coils": _dx_hgrh_pair(), "installed_on_drain_pan": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["export_allowed"] is False
    assert len(data["coils"]) == 2
    dx = next(c for c in data["coils"] if c["tag"] == "CDXC-1")
    assert dx["width"]["verdict"] == "PASS"
    assert dx["drain_pan"]["verdict"] == "PASS"
