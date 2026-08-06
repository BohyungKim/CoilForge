"""Phase 3 — Coil Utilities internal table (geometry engine + capacity-range charts).

Values are checked against the source workbook's known outputs.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.coil_utilities import (
    R32_CHART,
    coil_volume_cuin,
    drop_tubes,
    face_area_sqft,
    heating_capacity_mbh,
    kit_for_cooling_btuh,
    passes,
    pct_drop_tubes,
    ranges_for_kit,
    tons_for_kit,
)
from coilforge.coil_utilities.ranges import classify_face_velocity


def test_r32_chart_is_the_full_14_kit_set():
    assert len(R32_CHART) == 14
    assert R32_CHART[0].index == 12
    assert R32_CHART[-1].index == 192
    # Spot-check a published band (kit 174U cooling 169000–189000, volume 287–778).
    k174 = next(r for r in R32_CHART if r.index == 174)
    assert k174.cooling_min == 169000 and k174.cooling_max == 189000
    assert k174.volume_min == 287 and k174.volume_max == 778
    assert k174.heating_nominal == 192000


def test_tons_and_geometry_match_workbook():
    assert tons_for_kit(174) == 14.5
    # 'R32' sheet example: FH18 FL30 Rows4 Feeds5 -> Passes 14, Vol 233.7, Face 3.75.
    assert passes(fin_height=18, rows=4, feeds=5) == 14
    vol = coil_volume_cuin(feeds=5, fin_height=18, rows=4, fin_length=30, tube_thickness_in=0.016)
    assert abs(vol - 233.7) < 0.5
    assert abs(face_area_sqft(fin_height=18, fin_length=30) - 3.75) < 0.01


def test_drop_tubes_and_pct():
    # FH18 Rows4 Feeds5: passes=14, drop = 18*4 - 5*14 = 72-70 = 2; total=floor(18)*4=72.
    assert drop_tubes(fin_height=18, rows=4, feeds=5) == 2
    assert abs(pct_drop_tubes(fin_height=18, rows=4, feeds=5) - 2 / 72) < 1e-9


def test_ranges_scale_by_circuits():
    one = ranges_for_kit(174, 1)
    two = ranges_for_kit(174, 2)
    assert one.cooling_min_btuh == 169000
    assert two.cooling_min_btuh == 338000  # doubled by circuits
    assert one.cooling_min_mbh == 169.0
    assert one.volume_max_cuin == 778 and two.volume_max_cuin == 1556


def test_kit_selection_by_cooling_capacity():
    # 171514 BTU/h (the real CDXC-1 capacity) falls in kit 174U's band [169000,189000].
    assert kit_for_cooling_btuh(171514, 1) == 174
    # A small load selects a small kit.
    assert kit_for_cooling_btuh(11000, 1) == 12
    # Above the chart -> largest kit, never None.
    assert kit_for_cooling_btuh(10_000_000, 1) == 192


def test_unknown_kit_or_refrigerant_returns_none():
    assert ranges_for_kit(999, 1) is None
    assert ranges_for_kit(174, 1, refrigerant="R404A") is None


def test_heating_capacity_calc():
    # Extras: EAT17 LAT80 CFM5000 -> ~341.8 MBH.
    mbh = heating_capacity_mbh(eat_f=17, lat_f=80, cfm=5000)
    assert abs(mbh - 341.77) < 0.1


def test_face_velocity_classification():
    assert classify_face_velocity(425) == "ideal"
    assert classify_face_velocity(480) == "acceptable"
    assert classify_face_velocity(520) == "out_of_range"
    assert classify_face_velocity(None) == "unknown"


def test_missing_geometry_returns_none():
    assert coil_volume_cuin(feeds=None, fin_height=18, rows=4, fin_length=30, tube_thickness_in=0.016) is None
    assert passes(fin_height=18, rows=4, feeds=0) is None
