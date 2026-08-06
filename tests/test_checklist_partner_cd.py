"""The partner CD written onto a sheet must equal that partner's OWN sheet CD (pure).

`_build_sheet` deliberately runs a reheat-paired DX through R-072's with-HGRH casing
branch so the DX sheet's CoilForge column matches `DX!C24 IF(W/HGRH=TRUE,…)`. The
INSTALL-FIT block that writes the partner's CD onto the HGRH sheet did not pass those
arguments, so the same coil was described by two different numbers — 7.5 here, 7.5625
on its own sheet. `DX CD` is an INPUT to the sheet's INSTALL FIT, so the gap propagated
into the drain-pan verdict rather than staying cosmetic.

The gate is category-scoped on purpose: this block also serves the HWC sheet, whose
partner is a CWC, and an ungated with_hgrh would apply the reheat branch to a water coil.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.checklist.mapping import build_checklist_fill


def _dx(**over):
    coil = {
        "tag": "CDXC-1", "coil_type": "DX", "product_label": "NOVA", "unit_size": "C24",
        "quantity": 1, "finned_height": 45.0, "finned_length": 54.0, "rows": 5,
        "feeds": 9, "circuits": 2, "suction_conn_size": 2.0, "conn_size": 2.0,
        "qty_conn_per_header": 2, "coil_hand": "L",
    }
    coil.update(over)
    return coil


def _hgrh(**over):
    coil = {
        "tag": "RHHGRC-1", "coil_type": "HGRH", "product_label": "NOVA",
        "unit_size": "C24", "quantity": 1, "finned_height": 45.0, "finned_length": 54.0,
        "rows": 2, "feeds": 2, "circuits": 2, "conn_size": 0.875,
        "suction_conn_size": 0.875, "qty_conn_per_header": 2, "coil_hand": "L",
    }
    coil.update(over)
    return coil


def _cwc(**over):
    coil = {
        "tag": "CCWC-1", "coil_type": "CWC", "product_label": "NOVA", "unit_size": "C24",
        "quantity": 1, "finned_height": 30.0, "finned_length": 40.0, "rows": 4,
        "feeds": 4, "circuits": 1, "inlet_conn_size": 1.5, "outlet_conn_size": 1.5,
        "conn_size": 1.5, "coil_hand": "L", "application": "STANDALONE",
    }
    coil.update(over)
    return coil


def _hwc(**over):
    coil = {
        "tag": "HHWC-1", "coil_type": "HWC", "product_label": "NOVA", "unit_size": "C24",
        "quantity": 1, "finned_height": 30.0, "finned_length": 40.0, "rows": 2,
        "feeds": 4, "circuits": 1, "inlet_conn_size": 1.5, "outlet_conn_size": 1.5,
        "conn_size": 1.5, "coil_hand": "L", "application": "STANDALONE",
    }
    coil.update(over)
    return coil


def _sheet(fill, tag):
    return next(s for s in fill.sheets if s.sheet_tag == tag)


def _cell(sheet, label):
    key = label.upper().replace(" ", "")
    return next(c for c in sheet.cells if c.label.upper().replace(" ", "") == key)


def _compare(sheet, label):
    return next(d for d in sheet.compare_dims if d.label == label)


def test_hgrh_sheet_dx_cd_matches_the_dx_sheets_own_cd():
    fill = build_checklist_fill([_dx(), _hgrh()], None)
    dx_own_cd = _compare(_sheet(fill, "CDXC-1"), "CD").coilforge_value
    written = _cell(_sheet(fill, "RHHGRC-1"), "DX CD").value
    assert written == dx_own_cd, (
        f"HGRH sheet writes DX CD={written} while the DX sheet shows {dx_own_cd} "
        "for the same coil — the INSTALL FIT would compute from the wrong depth"
    )


def test_the_fixture_actually_exercises_the_with_hgrh_branch():
    """Guards against the test above going vacuous.

    If the with-HGRH and standalone branches ever produced the same CD for this coil,
    the equality assertion would pass without proving anything.
    """
    from coilforge.services.direct_coil_drawing_pipeline import build_drawing_slots

    common = dict(
        coil_type="DX", product_type="NOVA", unit_size="C24", rows=5, feeds=9,
        circuits=2, suction_conn_size=2.0, conn_size=2.0, qty_conn_per_header=2,
    )
    standalone, _ = build_drawing_slots(**common)
    paired, _ = build_drawing_slots(**common, with_hgrh=True, hgrh_conn_size=0.875)
    assert standalone["slot.CD"] != paired["slot.CD"], (
        "fixture no longer distinguishes the two casing-depth branches"
    )


def test_hwc_sheet_partner_cwc_cd_does_not_take_the_reheat_branch():
    """The shared block must not hand a water pair the DX reheat casing branch."""
    fill = build_checklist_fill([_cwc(), _hwc()], None)
    cwc_own_cd = _compare(_sheet(fill, "CCWC-1"), "CD").coilforge_value
    written = _cell(_sheet(fill, "HHWC-1"), "CWC CD").value
    assert written == cwc_own_cd
