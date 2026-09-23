"""Coil Checklist template refresh (2026-09-22): what moved and what deliberately did not.

John refined every tab of "Coil Checklist Template.xlsx" on 2026-09-22 and ruled that
the checklist wins over CoilForge's earlier SOP-derived values on five named conflicts.
Each block below pins one back-cracked formula (cell cited) against the CoilForge layer
that mirrors it. Two rows are pinned in the OPPOSITE direction on purpose: the water O
callout stays O == I (John 2026-07-29) and the Terra V HGRH CD stays rows-based (KD-001)
-- those are John decisions the refresh did not cover.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

pytest.importorskip("yaml")

from coilforge.checklist import template_map as T  # noqa: E402
from coilforge.checklist.mapping import _dim_slot, _to_size, build_checklist_fill  # noqa: E402
from coilforge.services.direct_coil_drawing_pipeline import (  # noqa: E402
    build_drawing_slots,
    build_header_request,
)
from coilforge.services.header_prepopulate_engine import prepopulate  # noqa: E402

_KD = ROOT / "src" / "coilforge" / "rules" / "known_divergences.yaml"


def _water(coil_type, product, size, **over):
    coil = {
        "tag": "HHWC-1" if coil_type == "HWC" else "CCWC-1", "coil_type": coil_type,
        "product_label": product, "unit_size": size, "quantity": 1,
        "finned_height": 30.0, "finned_length": 40.0, "rows": 2, "feeds": 4, "circuits": 1,
        "inlet_conn_size": 1.5, "outlet_conn_size": 1.25, "conn_size": 1.25,
        "coil_hand": "L", "coating": None, "application": "STANDALONE",
    }
    coil.update(over)
    return coil


def _cells(sheet):
    return {c.label: c for c in sheet.cells}


def _dims(sheet):
    return {d.label: d for d in sheet.compare_dims}


# --------------------------------------------------------------------------- #
# Units tab: Terra V SIZE tokens are numeric now
# --------------------------------------------------------------------------- #
def test_terra_v_size_dropdown_is_numeric_for_all_13_sizes():
    # Units!A56:A68 changed from 'TV006'.. strings to 6..100 numbers. A string token would
    # fail validation AND make the Terra V CASING XLOOKUP / FIT formulas (`C4=6`) FALSE.
    for token in ("006", "009", "012", "015", "018", "024", "032", "040", "048",
                  "060", "072", "084", "100"):
        assert _to_size("TERRA V", token) == int(token), token
    assert T.SIZE_OPTIONS["TERRA V"] == (6, 9, 12, 15, 18, 24, 32, 40, 48, 60, 72, 84, 100)
    assert _to_size("TERRA V", "TV084") is None   # the old spelling is no longer a value


# --------------------------------------------------------------------------- #
# HWC / CWC sheets: separate I / O / S / R rows
# --------------------------------------------------------------------------- #
def test_water_sheets_list_the_new_rows_and_map_them_to_header_1_slots():
    for cat in ("HWC", "CWC"):
        dims = T.SHEET_LABELS[cat]["dims"]
        assert ("I", "O", "S", "R") == tuple(d for d in dims if d in ("I", "O", "S", "R"))
        assert "I/O" not in dims
        # The two text rows have no drawing slot and are deliberately NOT compare dims.
        assert "SUPPLY V/D ANGLE" not in dims and "VENT & DRAIN" not in dims
    assert (_dim_slot("I"), _dim_slot("O"), _dim_slot("S"), _dim_slot("R")) == (
        "slot.I1", "slot.O2", "slot.S1", "slot.R2"
    )


def test_water_compare_rows_carry_the_drawn_slot_values():
    """The CoilForge column for O / S / R is the DRAWN slot value -- never a separate copy
    of the sheet's formula made only for the comparison (that would always `match` and
    hide a real drawing-vs-sheet difference).

    Since 2026-09-23 the DRAWING itself follows the sheet for water S/R (John: CWC S =
    IN/2 + 3, R = OUT; HWC S = IN, R = OUT), so the drawn value and the sheet agree by a
    decision, not by mirroring. O is drawn as I (R-060) on the header-side artwork; the
    Terra O datum is covered by test_water_o_is_one_position_in_two_datums_...."""
    for cat in ("HWC", "CWC"):
        sheet = build_checklist_fill([_water(cat, "NOVA", "C24")]).sheets[0]
        d = _dims(sheet)
        assert {"I", "O", "S", "R", "HD", "SL"} <= set(d)
        assert d["I"].coilforge_value == d["O"].coilforge_value == 2.3125   # O == I (R-060)
        # fixture: IN 1.5, OUT 1.25 (unequal, so the two ends cannot be confused)
        expected_s = 1.5 / 2 + 3 if cat == "CWC" else 1.5
        assert d["S"].coilforge_value == expected_s, cat
        assert d["R"].coilforge_value == 1.25, cat


def test_water_rb_is_compared_not_written_and_dx_rb_is_still_written():
    # CWC!C26 / HWC!C30 now carry a real rule, so the sheet's RB is left as a formula and
    # compared (R-006/R-006v/R-006p mirror it). DX/HGRH RB stays a written input (1.5 vs
    # the sheet's stale 1.75, John 2026-07-01).
    water = build_checklist_fill([_water("HWC", "NOVA", "C24")]).sheets[0]
    assert "RB" not in _cells(water)
    assert _dims(water)["RB"].coilforge_value == 2.25
    dx = build_checklist_fill([{
        "tag": "CDXC-1", "coil_type": "DX", "product_label": "NOVA", "unit_size": "C24",
        "quantity": 1, "finned_height": 45.0, "finned_length": 54.0, "rows": 5, "feeds": 9,
        "circuits": 2, "suction_conn_size": 2.0, "qty_conn_per_header": 2, "coil_hand": "L",
    }]).sheets[0]
    assert _cells(dx)["RB"].value == 1.5 and "RB" not in _dims(dx)


# --------------------------------------------------------------------------- #
# Engine: water CD connection term (CWC!C21 / HWC!C25)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("coil_type, expected", [("HWC", 6.0), ("CWC", 8.25)])
def test_water_cd_takes_the_max_of_rows_base_and_connection_term(coil_type, expected):
    # rows=2 -> base ROUNDUP(2.598 to 1/8)+2 = 4.625. HWC: 1.5*(1.5+1.5)+1.5 = 6.0;
    # CWC: 1.5*1.5 + 1.5 + 4.5 = 8.25. Both dominate the base.
    req = build_header_request(
        coil_type=coil_type, product_type="NOVA", unit_size="C24", rows=2, feeds=2,
        inlet_conn_size=1.5, outlet_conn_size=1.5,
    )
    assert prepopulate(req).values["casing_depth"].value == expected
    # Either connection size absent -> the base stands alone, still HIGH (never guessed).
    for kw in ({"inlet_conn_size": 1.5}, {"outlet_conn_size": 1.5}, {}):
        r = prepopulate(build_header_request(
            coil_type=coil_type, product_type="NOVA", unit_size="C24", rows=2, feeds=2, **kw
        ))
        assert r.values["casing_depth"].value == 4.625, kw


def test_water_cd_base_still_wins_when_the_connections_are_small():
    req = build_header_request(
        coil_type="HWC", product_type="NOVA", unit_size="C24", rows=6, feeds=2,
        inlet_conn_size=0.5, outlet_conn_size=0.5,
    )
    # rows=6 -> ROUNDUP(7.794 to 1/8)+2 = 9.875 > 1.5*1+1.5 = 3.
    assert prepopulate(req).values["casing_depth"].value == 9.875


# --------------------------------------------------------------------------- #
# Engine: HWC Terra INSTALLED ON DP tri-state (HWC!C28:C29, C31:C32)
# --------------------------------------------------------------------------- #
def _hwc_terra(dp):
    return prepopulate(build_header_request(
        coil_type="HWC", product_type="TERRA H", unit_size="024", rows=2, feeds=2,
        installed_on_drain_pan=dp,
    ))


def test_hwc_terra_off_the_pan_takes_flanges_1_and_io_2_3125():
    r = _hwc_terra(False)
    assert (r.values["top_flange"].value, r.values["bottom_flange"].value) == (1, 1)
    assert r.values["io"].value == 2.3125
    assert r.values["top_flange"].rule_id == "R-014h"


def test_hwc_terra_on_the_pan_keeps_the_terra_values():
    r = _hwc_terra(True)
    assert (r.values["top_flange"].value, r.values["bottom_flange"].value) == (1.625, 0.5)
    assert r.values["io"].value == 3.25
    assert r.values["top_flange"].review_required is False


def test_hwc_terra_with_unknown_pan_state_keeps_terra_values_high_but_flags_review():
    """The drawing / mechanical-fit paths never state the pan. They must keep resolving
    slot.TF/BF/CH byte-identically (HIGH), with only a review flag added -- a bool() gate
    would have read None as "off the pan" and rewritten every Terra H HWC to 1/1."""
    r = _hwc_terra(None)
    for f in ("top_flange", "bottom_flange", "io"):
        assert f in r.values and f not in r.suggestions, f
        assert r.values[f].review_required is True, f
        assert "INSTALLED ON DP" in (r.values[f].review_required_reason or ""), f
    assert (r.values["top_flange"].value, r.values["bottom_flange"].value) == (1.625, 0.5)
    slots, _ = build_drawing_slots(
        coil_type="HWC", product_type="TERRA H", unit_size="024", rows=2, feeds=2,
        finned_height=20.0, conn_size=1.0,
    )
    assert slots["slot.TF"] == 1.625 and slots["slot.BF"] == 0.5 and slots["slot.CH"] == 22.125


def test_hwc_terra_v_off_the_pan_also_takes_1_and_cwc_is_untouched():
    r = prepopulate(build_header_request(
        coil_type="HWC", product_type="TERRA V", unit_size="024", rows=2, feeds=2,
        installed_on_drain_pan=False,
    ))
    assert (r.values["top_flange"].value, r.values["bottom_flange"].value) == (1, 1)
    c = prepopulate(build_header_request(
        coil_type="CWC", product_type="TERRA H", unit_size="024", rows=2, feeds=2,
        installed_on_drain_pan=False,
    ))
    assert (c.values["top_flange"].value, c.values["bottom_flange"].value) == (1.625, 0.5)
    assert c.values["io"].value == 3.25


def test_checklist_fill_feeds_the_sheets_pan_state_into_the_engine():
    # A lone HWC (no CWC partner) -> INSTALLED ON DP False -> the CoilForge column shows
    # the off-pan flanges the sheet will compute; paired -> the Terra flanges.
    alone = build_checklist_fill([_water("HWC", "TERRA H", "024")]).sheets[0]
    assert _cells(alone)["INSTALLED ON DP"].value is False
    assert _dims(alone)["TF"].coilforge_value == 1 and _dims(alone)["I"].coilforge_value == 2.3125
    paired = build_checklist_fill([
        _water("HWC", "TERRA H", "024"),
        _water("CWC", "TERRA H", "024"),
    ])
    hwc = next(s for s in paired.sheets if s.category == "HWC")
    assert _cells(hwc)["INSTALLED ON DP"].value is True
    assert _dims(hwc)["TF"].coilforge_value == 1.625 and _dims(hwc)["I"].coilforge_value == 3.25


# --------------------------------------------------------------------------- #
# Engine: water RB by family (CWC!C26 / HWC!C30), single-feed specials retired
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("product, size, expected", [
    ("NOVA", "C24", 2.25), ("VENTUM_H", "H15", 2.25), ("TERRA H", "024", 2.25),
    ("TERRA V", "024", 1.875), ("VENTUM_PLUS", "V30", 1.875), ("OMNIA", "OW060", 1.875),
])
def test_water_return_bend_by_family(product, size, expected):
    for cat in ("CWC", "HWC"):
        r = prepopulate(build_header_request(coil_type=cat, product_type=product, unit_size=size))
        assert r.values["return_bend"].value == expected, (cat, product)


def test_water_single_feed_resolves_like_multi_feed():
    r = prepopulate(build_header_request(
        coil_type="CWC", product_type="NOVA", unit_size="C24", rows=2, feeds=1,
    ))
    assert r.values["sl"].value == 8 and r.values["hd"].value == 4
    assert r.values["io"].value == 2.3125
    assert not any(k in r.suggestions for k in ("io", "hd", "sl"))
    # feeds ABSENT is unchanged: the sheet blanks I/O and HD, so they stay MEDIUM.
    absent = prepopulate(build_header_request(coil_type="CWC", product_type="NOVA", unit_size="C24", rows=2))
    assert "io" in absent.suggestions and "hd" in absent.suggestions


def test_water_vent_drain_and_vd_angle_follow_the_sheet_on_every_line():
    for product, size in (("NOVA", "C24"), ("TERRA V", "024"), ("VENTUM_PLUS", "V30")):
        r = prepopulate(build_header_request(coil_type="HWC", product_type=product, unit_size=size))
        assert r.values["vent_drain"].value == "ConnEnd", product     # was Connections / HDR ENDS
        assert r.values["supply_vd_angle"].value == "LAS", product


# --------------------------------------------------------------------------- #
# DX: distributor extension 17 on Ventum H H05/H10 (DX!C59)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("product, size, expected", [
    ("VENTUM_H", "H05", 17), ("VENTUM_H", "H10", 17), ("VENTUM_H", "H15", 6), ("NOVA", "C24", 6),
])
def test_dx_distributor_extension_is_17_only_on_ventum_h_h05_h10(product, size, expected):
    slots, _ = build_drawing_slots(coil_type="DX", product_type=product, unit_size=size, rows=4)
    assert slots["slot.DIST_EXT"] == expected


# --------------------------------------------------------------------------- #
# Deliberately NOT moved by the refresh (John decisions the refresh did not cover)
# --------------------------------------------------------------------------- #
def _review_of(sheet, computed):
    from coilforge.checklist.compare import build_review
    from coilforge.checklist.model import ChecklistFill

    review = build_review(ChecklistFill(sheets=(sheet,)),
                          {"sheets": [{"tag": sheet.sheet_tag, "computed_dims": computed}]})
    return {r["label"]: r for r in review["sheets"][0]["comparisons"]}


def test_water_o_is_one_position_in_two_datums_and_compares_as_a_match():
    """The sheet's Terra O row (CH - 2.75) and the drawn O measure ONE stubout position
    from opposite ends (John 2026-09-23). Terra CWC now draws on its own opposite-datum
    artwork (O = CH - I); both sides are re-expressed from the header end before
    matching, so the row matches -- KD-024..027 are retired, not suppressing it."""
    sheet = build_checklist_fill([_water("CWC", "TERRA V", "024")]).sheets[0]
    o = _dims(sheet)["O"]
    ch = _dims(sheet)["CH"].coilforge_value
    assert (o.coilforge_datum, o.sheet_datum) == ("opposite", "opposite")
    assert o.coilforge_value == round(ch - 2.75, 4)
    rows = _review_of(sheet, {"CH": ch, "O": ch - 2.75, "I": 2.75})
    assert rows["O"]["verdict"] == "match"
    assert rows["O"]["checklist"] == ch - 2.75            # raw value kept for the ledger
    assert rows["O"]["compared_from_header_end"]["checklist"] == 2.75
    assert rows["O"]["compared_from_header_end"]["checklist_as_drawn"] == ch - 2.75
    # A genuinely different stubout position still fails.
    assert _review_of(sheet, {"CH": ch, "O": ch - 3.25})["O"]["verdict"] == "mismatch"

    entries = yaml.safe_load(_KD.read_text(encoding="utf-8"))["divergences"]
    assert not [e for e in entries if e["slot"] == "slot.O2"
                and e["coil_category"] in ("CWC", "HWC")]


def test_hwc_terra_o_matches_on_and_off_the_drain_pan():
    """Terra HWC draws on its own opposite-datum art (seed 13.50 = CH 16.25 - I 2.75).
    The sheet's O is opposite-datum only when INSTALLED ON DP; off the pan it prints the
    plain header-side 2.3125 -- the same stubout either way, so both rows match."""
    on_pan = build_checklist_fill(
        [_water("HWC", "TERRA V", "024"), _water("CWC", "TERRA V", "024")]
    ).sheets
    hwc = next(s for s in on_pan if s.category == "HWC")
    o, ch, i1 = _dims(hwc)["O"], _dims(hwc)["CH"].coilforge_value, _dims(hwc)["I"].coilforge_value
    assert (o.coilforge_datum, o.sheet_datum) == ("opposite", "opposite")
    assert o.coilforge_value == round(ch - i1, 4)
    rows = _review_of(hwc, {"CH": ch, "O": ch - i1})
    assert rows["O"]["verdict"] == "match"
    assert rows["O"]["compared_from_header_end"]["checklist_as_drawn"] == ch - i1

    off_pan = build_checklist_fill([_water("HWC", "TERRA V", "024")]).sheets[0]
    o, ch, i1 = (_dims(off_pan)["O"], _dims(off_pan)["CH"].coilforge_value,
                 _dims(off_pan)["I"].coilforge_value)
    assert (o.coilforge_datum, o.sheet_datum) == ("opposite", "header_side")
    rows = _review_of(off_pan, {"CH": ch, "O": i1})
    assert rows["O"]["verdict"] == "match"
    # "use checklist" must copy the sheet's O in the DRAWING's datum (CH - I), never the
    # raw header-side number, which would land on the opposite-datum dimension line.
    assert rows["O"]["compared_from_header_end"]["checklist_as_drawn"] == round(ch - i1, 4)


def test_water_o_conversion_needs_a_ch_and_never_guesses_one():
    sheet = build_checklist_fill([_water("CWC", "TERRA V", "024")]).sheets[0]
    assert _review_of(sheet, {"O": 20.0})["O"]["verdict"] == "missing_one"


def test_non_terra_water_o_is_unchanged():
    for cat in ("CWC", "HWC"):
        o = _dims(build_checklist_fill([_water(cat, "NOVA", "C24")]).sheets[0])["O"]
        assert (o.coilforge_datum, o.sheet_datum) == ("header_side", "header_side")


def test_terra_v_hgrh_cd_stays_rows_based_pending_kd_001():
    slots, _ = build_drawing_slots(
        coil_type="HGRH", product_type="TERRA V", unit_size="072",
        rows=2, circuits=2, conn_size=0.875, qty_conn_per_header=2,
    )
    assert slots["slot.CD"] == 3.75      # not the sheet's else-branch 4.125
    entries = yaml.safe_load(_KD.read_text(encoding="utf-8"))["divergences"]
    ids = {e["id"] for e in entries}
    assert "KD-001" in ids and "KD-004" not in ids and not ids & {"KD-006", "KD-007", "KD-008", "KD-009"}
    assert {"KD-005", "KD-022", "KD-023"} <= ids       # Terra V O4/O6/O8 = 2 is a sheet defect


def test_water_o_compare_uses_the_ch_each_side_stood_on_after_a_ch_override():
    """A CH override is written into the sheet AFTER the read-back, and the sheet's O
    (a dependent) is re-read on the NEW CH, while `computed["CH"]` keeps the formula's
    own value. The sheet side must therefore convert with the override, not the stale
    CH -- else every CH override on a Terra water coil reads as an O mismatch."""
    from coilforge.checklist.model import DimCompare, OverrideNote, SheetFill

    sheet = SheetFill(
        category="CWC", source_sheet="CWC", sheet_tag="CCWC-1",
        compare_dims=(
            DimCompare("CH", "slot.CH", 20.0, override=OverrideNote("CH", 19.25, "test")),
            DimCompare("O", "slot.O2", 17.25, coilforge_datum="opposite",
                       sheet_datum="opposite"),
        ),
    )
    rows = _review_of(sheet, {"CH": 19.25, "O": 20.0 - 2.75})
    assert rows["CH"]["verdict"] == "overridden"
    assert rows["O"]["verdict"] == "match"
    assert rows["O"]["compared_from_header_end"]["checklist"] == 2.75
