"""Phase 3 wiring — the Coil-Utilities range provider drives real acceptance verdicts."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ambient.mapping import build_ambient_comparison
from coilforge.ambient.pdf_intake import _parse_report_page
from coilforge.ambient.range_provider import coil_utilities_range_provider
from tests.test_ambient_pdf_intake import _DX_TEXT


def _dx(text=_DX_TEXT):
    return _parse_report_page(text, page_number=1, source_id="B")


def test_provider_turns_capacity_range_from_cannot_evaluate_into_a_verdict():
    result = build_ambient_comparison(
        [_dx()], [_dx()], range_provider=coil_utilities_range_provider
    )
    rows = result.coils[0].rows
    cap_range = next(r for r in rows if r.label == "Capacity Range")
    # CDXC-1 cooling 171.514 MBH -> kit 174U band [169,189] MBH -> in band -> match.
    assert cap_range.verdict == "match"
    assert cap_range.tolerance.startswith("[")

    vol_range = next(r for r in rows if r.label == "Coil Volume Range")
    assert vol_range.verdict in ("match", "mismatch")  # a real verdict, not cannot_evaluate


def test_ambient_capacity_outside_band_is_mismatch():
    baseline = _dx()
    # Ambient returns a wildly-low capacity -> outside kit 174U cooling band -> mismatch.
    ambient = _dx(_DX_TEXT.replace("171514 Btu/hr", "80000 Btu/hr"))
    result = build_ambient_comparison(
        [baseline], [ambient], range_provider=coil_utilities_range_provider
    )
    cap_range = next(r for r in result.coils[0].rows if r.label == "Capacity Range")
    assert cap_range.verdict == "mismatch"  # 80 MBH not in [169,189]


def test_baseline_missing_capacity_falls_back_to_ambient_for_kit():
    baseline = _dx()
    # Strip only the baseline capacity: the provider falls back to Ambient's capacity to
    # pick the kit, so the band is still derivable (workbook's coil-volume-in-band use).
    del baseline.performance["nominal_cooling_capacity_mbh"]
    result = build_ambient_comparison(
        [baseline], [_dx()], range_provider=coil_utilities_range_provider
    )
    cap_range = next(r for r in result.coils[0].rows if r.label == "Capacity Range")
    assert cap_range.verdict != "cannot_evaluate"


def test_no_capacity_on_either_side_is_cannot_evaluate():
    baseline, ambient = _dx(), _dx()
    del baseline.performance["nominal_cooling_capacity_mbh"]
    del ambient.performance["nominal_cooling_capacity_mbh"]
    result = build_ambient_comparison(
        [baseline], [ambient], range_provider=coil_utilities_range_provider
    )
    cap_range = next(r for r in result.coils[0].rows if r.label == "Capacity Range")
    assert cap_range.verdict == "cannot_evaluate"
