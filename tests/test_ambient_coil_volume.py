"""Phase 1 — Ambient coil-volume formula port (pure; no I/O).

The golden value was computed from an INDEPENDENT transcription of the Excel
formula (not this module), so a typo in the port is caught here.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ambient.coil_volume import coil_volume_cuin


# Independently-computed reference: feeds=6, fin_height=15, rows=5, fin_length=47,
# tube_thickness=0.016, tube_od=3/8 -> 364.5545613291935 (Excel formula, transcribed
# separately). This is the load-bearing "matches the workbook" assertion.
_GOLDEN_INPUTS = dict(
    feeds=6, fin_height=15, rows=5, fin_length=47, tube_thickness_in=0.016
)
_GOLDEN_VALUE = 364.5545613291935


def test_matches_excel_golden():
    got = coil_volume_cuin(**_GOLDEN_INPUTS)
    assert got is not None
    assert abs(got - _GOLDEN_VALUE) < 1e-9


def test_missing_input_returns_none():
    # Any missing required input -> None (never invent).
    for drop in ("feeds", "fin_height", "rows", "fin_length", "tube_thickness_in"):
        kwargs = dict(_GOLDEN_INPUTS)
        kwargs[drop] = None
        assert coil_volume_cuin(**kwargs) is None


def test_zero_feeds_returns_none_not_raise():
    kwargs = dict(_GOLDEN_INPUTS)
    kwargs["feeds"] = 0
    assert coil_volume_cuin(**kwargs) is None


def test_monotonic_in_length_and_rows():
    base = coil_volume_cuin(**_GOLDEN_INPUTS)
    longer = coil_volume_cuin(**{**_GOLDEN_INPUTS, "fin_length": 94})
    more_rows = coil_volume_cuin(**{**_GOLDEN_INPUTS, "rows": 6})
    # Strictly increasing in both — but note doubling fin_length does NOT double the
    # volume, because the return-bend term is length-independent (708.5, not 729.1).
    assert longer > base
    assert more_rows > base
    assert longer < 2 * base


def test_straight_run_term_scales_linearly_with_length():
    # Only the straight-run portion depends on fin_length; the bend term is constant.
    # So volume(2L) - volume(L) == volume(L) - volume(0-length bends only) for the
    # straight part. Verify the length-delta is linear: delta(47->94) == straight(47).
    v47 = coil_volume_cuin(**{**_GOLDEN_INPUTS, "fin_length": 47})
    v94 = coil_volume_cuin(**{**_GOLDEN_INPUTS, "fin_length": 94})
    v141 = coil_volume_cuin(**{**_GOLDEN_INPUTS, "fin_length": 141})
    assert abs((v94 - v47) - (v141 - v94)) < 1e-9
