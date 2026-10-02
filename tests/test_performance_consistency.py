from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from coilforge.coil_utilities import performance_consistency as pc  # noqa: E402
from coilforge.coil_utilities.geometry import heating_capacity_mbh  # noqa: E402
from coilforge.coil_utilities.performance_consistency import (  # noqa: E402
    ConsistencyFinding,
    PerformanceConsistencyReport,
    check_performance_consistency,
    parse_number,
)


def _air(cfm, edb, ldb, capacity, altitude=None, **more):
    sources = {"total_air_flow_cfm": cfm, "entering_dry_bulb_f": edb, "leaving_dry_bulb_f": ldb,
               "total_capacity_mbh": capacity}
    if altitude is not None:
        sources["altitude_ft"] = altitude
    sources.update(more)
    return sources


def _water(fluid, percent, gpm, ewt, lwt, capacity, **more):
    return {"airside_conditions.fluid_type": fluid, "airside_conditions.fluid_percent": percent,
            "airside_conditions.fluid_flow_rate_gpm": gpm, "airside_conditions.fluid_entering_temp_f": ewt,
            "airside_conditions.fluid_leaving_temp_f": lwt, "total_capacity_mbh": capacity, **more}


def _finding(sources, coil_type, check) -> ConsistencyFinding:
    report = check_performance_consistency(sources, coil_type=coil_type)
    return next(f for f in report.findings if f.check == check)


# --- air-side sensible balance: per-coil numbers typed from real ordered coils ---------------

@pytest.mark.parametrize(
    ("label", "coil_type", "sources", "verdict", "basis", "k"),
    [
        ("3237 RHHGRC-1", "HGRH", _air(2000, 51, 70.88, 44.58, 0), "consistent", "actual", 1.121),
        ("2706 RHHGRC-1", "HGRH", _air(680, 53, 70.5, 12.85, 164), "consistent", "standard", 1.080),
        ("2949 HHWC-3", "HWC", _air(5500, 70, 95, 149.0, 180), "consistent", "indeterminate", 1.084),
        ("2755 RHHGRC-2", "HGRH", _air(1030, 54, 76.76, 27.64, 43), "inconsistent", None, 1.179),
        ("3058 RHHGRC-2", "HGRH", _air(4800, 53, 66.7, 68.76, 20), "inconsistent", None, 1.046),
    ],
)
def test_heating_sensible_balance_on_real_coils(label, coil_type, sources, verdict, basis, k):
    finding = _finding(sources, coil_type, "air_sensible_balance")
    assert finding.verdict == verdict, label
    assert finding.air_basis == basis, label
    assert finding.observed == pytest.approx(k, abs=0.001), label
    assert finding.reason_code == ("PERF_OK" if verdict == "consistent" else "PERF_MISMATCH")


def test_missing_altitude_never_becomes_zero():
    # 2755 RHHGRC-2 without its altitude: Standard misses, and Actual cannot be ruled out.
    finding = _finding(_air(1030, 54, 76.76, 27.64), "HGRH", "air_sensible_balance")
    assert finding.verdict == "cannot_evaluate"
    assert finding.reason_code == "PERF_SOURCE_MISSING"
    assert finding.missing == ["altitude_ft"]
    assert "actual" not in finding.expected


def test_missing_altitude_with_a_standard_match_is_not_counted_as_standard():
    finding = _finding(_air(680, 53, 70.5, 12.85), "HGRH", "air_sensible_balance")
    assert finding.verdict == "consistent"
    assert finding.air_basis == "standard_only"


@pytest.mark.parametrize(
    ("altitude", "code"),
    [("1,200", "PERF_VALUE_UNPARSEABLE"), ({"value": 366, "unit": "m"}, "PERF_UNIT_UNEXPECTED")],
)
def test_unusable_altitude_is_treated_like_a_missing_one(altitude, code):
    finding = _finding(_air(1030, 54, 76.76, 27.64, altitude), "HGRH", "air_sensible_balance")
    assert (finding.verdict, finding.reason_code) == ("cannot_evaluate", code)
    assert "actual" not in finding.expected


def test_dx_sensible_balance_uses_the_sensible_capacity():
    # 2755 CDXC-2: 40.29 MBH sensible against 1030 CFM cooled 86.1 -> 52.27.
    sources = _air(1030, 86.1, 52.27, 134.31, 43, **{"performance.sensible_capacity_mbh": 40.29})
    finding = _finding(sources, "DX", "air_sensible_balance")
    assert finding.verdict == "inconsistent"
    assert finding.observed == pytest.approx(1.156, abs=0.001)
    assert "sensible_capacity_mbh" in finding.inputs_used
    assert "total_capacity_mbh" not in finding.inputs_used


def test_cooling_coil_without_sensible_capacity_cannot_be_balanced():
    # No CWC in the corpus states a sensible capacity; total capacity carries latent load.
    finding = _finding(_air(3000, 80, 55, 120.0, 100), "CWC", "air_sensible_balance")
    assert finding.verdict == "cannot_evaluate"
    assert finding.reason_code == "PERF_SOURCE_MISSING"
    assert finding.missing == ["sensible_capacity_mbh"]


def test_tolerance_edge_is_inclusive():
    at_edge = _air(1000, 50, 70, (pc.SENSIBLE_FACTOR + pc.K_TOLERANCE) * 20, 0)
    beyond = _air(1000, 50, 70, (pc.SENSIBLE_FACTOR - pc.K_TOLERANCE - 0.0001) * 20, 0)  # Actual is ~1.128 at 50 degF
    assert _finding(at_edge, "HGRH", "air_sensible_balance").verdict == "consistent"
    assert _finding(beyond, "HGRH", "air_sensible_balance").verdict == "inconsistent"


def test_wrong_direction_is_left_to_the_direction_check():
    sources = _air(1000, 70, 55, 20.0, 0)  # a "heating" coil that cools the air
    assert _finding(sources, "HGRH", "air_sensible_balance").reason_code == "PERF_DEGENERATE"
    direction = _finding(sources, "HGRH", "air_temp_direction")
    assert direction.verdict == "inconsistent"
    assert _finding(sources, "DX", "air_temp_direction").verdict == "consistent"


# --- cooling: one-sided total, sensible <= total ----------------------------------------------

def test_cooling_total_must_cover_the_sensible_load():
    covered = _air(1030, 86.1, 52.27, 134.31, 43)
    short = _air(1030, 86.1, 52.27, 30.0, 43)
    assert _finding(covered, "DX", "air_total_vs_sensible").verdict == "consistent"
    assert _finding(short, "DX", "air_total_vs_sensible").verdict == "inconsistent"


def test_an_over_read_total_capacity_is_not_detected():
    # The documented nominal-for-total misread (365.85 instead of 123.88) passes: stated limit.
    sources = _air(4000, 80, 55, 365.85, 0, **{"performance.sensible_capacity_mbh": 108.5})
    report = check_performance_consistency(sources, coil_type="DX")
    assert not [f for f in report.findings if f.verdict == "inconsistent"]


def test_sensible_above_total_is_inconsistent():
    sources = _air(1000, 80, 55, 20.0, 0, **{"performance.sensible_capacity_mbh": 27.1})
    assert _finding(sources, "DX", "sensible_le_total").verdict == "inconsistent"


# --- fluid side: captured bands ---------------------------------------------------------------

@pytest.mark.parametrize(
    ("label", "coil_type", "sources", "factor"),
    [
        ("3031 PHWC-1", "HWC", _water("Propylene Glycol", 40, 12.2, 115, 95, 113.27), 464.2),
        ("2954 CCWC-1", "CWC", _water("Water", 100, 16.1, 44, 54, 80.65), 500.9),
        # Three coils on the tag: every submittal value is per coil, so quantity must not be applied.
        ("3154 HHWC-1", "HWC", _water("Water", 100, 0.66, 122, 104, 5.8, coil_quantity=3), 488.2),
    ],
)
def test_fluid_heat_balance_on_real_coils(label, coil_type, sources, factor):
    finding = _finding(sources, coil_type, "fluid_heat_balance")
    assert finding.verdict == "consistent", label
    assert finding.observed == pytest.approx(factor, abs=0.1), label
    assert finding.reference_status == "captured"


@pytest.mark.parametrize(
    ("fluid", "percent", "factor"),
    [("Water", 100, 488.22), ("Water", 100, 502.05), ("Propylene Glycol", 40, 457.57),
     ("Propylene Glycol", 40, 466.20), ("Propylene Glycol", 50, 443.75), ("Propylene Glycol", 50, 452.51)],
)
def test_every_measured_extreme_sits_inside_its_own_band(monkeypatch, fluid, percent, factor):
    monkeypatch.setattr(pc, "FLUID_BAND_MARGIN", 0.0)  # the band itself, without the margin
    sources = _water(fluid, percent, 10.0, 120, 100, factor * 10.0 * 20 / 1000.0)
    assert _finding(sources, "HWC", "fluid_heat_balance").verdict == "consistent"


def test_outside_the_captured_range_has_its_own_reason_code():
    sources = _water("Water", 100, 4.14, 140, 123.6, 76.9)  # ~1133: far outside 488-503 +/- 3 %
    finding = _finding(sources, "HWC", "fluid_heat_balance")
    assert finding.verdict == "inconsistent"
    assert finding.reason_code == "PERF_OUTSIDE_CAPTURED_RANGE"


def test_margin_reaches_just_past_the_band():
    inside = _water("Water", 100, 10.0, 180, 160, 475.0 * 10.0 * 20 / 1000.0)   # 488 x 0.97 = 473.4
    outside = _water("Water", 100, 10.0, 180, 160, 470.0 * 10.0 * 20 / 1000.0)
    assert _finding(inside, "HWC", "fluid_heat_balance").verdict == "consistent"
    assert _finding(outside, "HWC", "fluid_heat_balance").verdict == "inconsistent"


@pytest.mark.parametrize(
    ("fluid", "percent"),
    [("Propylene Glycol", 35), ("Propylene Glycol", 30), ("Ethylene Glycol", 40), ("Water", 60)],
)
def test_no_reference_is_never_filled_in(fluid, percent):
    finding = _finding(_water(fluid, percent, 10.0, 120, 100, 90.0), "HWC", "fluid_heat_balance")
    assert finding.verdict == "cannot_evaluate"
    assert finding.reason_code == "PERF_NO_REFERENCE"


def test_bare_propylene_is_the_same_fluid():
    sources = _water("Propylene", 40, 12.2, 115, 95, 113.27)
    assert _finding(sources, "HWC", "fluid_heat_balance").verdict == "consistent"


# --- face velocity and wet bulb ---------------------------------------------------------------

def test_face_velocity_is_computed_from_height_and_length():
    base = {"total_air_flow_cfm": 600, "finned_height": 12, "finned_length": 15}
    assert _finding({**base, "face_velocity_fpm": 480}, "DX", "face_velocity").verdict == "consistent"
    off = _finding({**base, "face_velocity_fpm": 450}, "DX", "face_velocity")  # 2873 CDXC-1
    assert off.verdict == "inconsistent"
    assert off.expected["computed"] == pytest.approx(480.0)


def test_wet_bulb_above_dry_bulb():
    assert _finding({"entering_dry_bulb_f": 80, "entering_wet_bulb_f": 67}, "DX", "wet_bulb_le_dry_bulb").verdict == "consistent"
    assert _finding({"entering_dry_bulb_f": 80, "entering_wet_bulb_f": 85}, "DX", "wet_bulb_le_dry_bulb").verdict == "inconsistent"
    absent = _finding({"entering_dry_bulb_f": 55}, "HGRH", "wet_bulb_le_dry_bulb")
    assert (absent.verdict, absent.reason_code) == ("cannot_evaluate", "PERF_NOT_APPLICABLE")


# --- input contract ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw", ["3,735", "95.0 °F", "N/A", "-", "1e3", "", "nan", "inf", "1_000", "５５", True, None, [1]])
def test_parse_number_refuses_anything_not_plainly_numeric(raw):
    assert parse_number(raw) is None


@pytest.mark.parametrize(("raw", "value"), [(55, 55.0), (-40.2, -40.2), (" 70.88 ", 70.88), ("-12", -12.0), (".5", 0.5)])
def test_parse_number_accepts_plain_numbers(raw, value):
    assert parse_number(raw) == value


def test_negative_entering_air_is_a_valid_input():
    finding = _finding(_air(1000, -10, 10, 1.085 * 20, 0), "HWC", "air_sensible_balance")
    assert finding.verdict == "consistent"


def test_unparseable_value_is_reported_not_cleaned():
    finding = _finding(_air("3,735", 50, 70, 80.0, 0), "HGRH", "air_sensible_balance")
    assert (finding.verdict, finding.reason_code) == ("cannot_evaluate", "PERF_VALUE_UNPARSEABLE")
    assert finding.missing == ["airflow_cfm"]


class _Field(BaseModel):
    value: float | None = None
    unit: str | None = None
    status: str = "review_required"


def test_accepts_models_dicts_and_bare_values():
    sources = {
        "total_air_flow_cfm": _Field(value=2000, unit="cfm"),
        "entering_dry_bulb_f": {"value": 51, "unit": "degF", "status": "review_required"},
        "leaving_dry_bulb_f": "70.88",
        "total_capacity_mbh": {"value": 44.58, "unit": "MBH"},
        "altitude_ft": 0,
    }
    finding = _finding(sources, "hgrh", "air_sensible_balance")  # coil type is case-insensitive
    assert (finding.verdict, finding.air_basis) == ("consistent", "actual")
    assert finding.source_keys["airflow_cfm"] == "total_air_flow_cfm"


def test_blocked_source_is_not_used():
    sources = _air({"value": 2000, "unit": "cfm", "status": "blocked"}, 51, 70.88, 44.58, 0)
    finding = _finding(sources, "HGRH", "air_sensible_balance")
    assert (finding.verdict, finding.reason_code) == ("cannot_evaluate", "PERF_SOURCE_BLOCKED")


def test_unexpected_unit_is_not_converted():
    sources = _air(2000, {"value": 10.6, "unit": "degC"}, 70.88, 44.58, 0)
    finding = _finding(sources, "HGRH", "air_sensible_balance")
    assert (finding.verdict, finding.reason_code) == ("cannot_evaluate", "PERF_UNIT_UNEXPECTED")


def test_draft_key_wins_and_a_null_draft_key_falls_through():
    sources = _air(2000, 51, 70.88, 44.58, 0)
    sources["airside_conditions.total_air_flow_cfm"] = 9999
    assert _finding(sources, "HGRH", "air_sensible_balance").inputs_used["airflow_cfm"] == 2000
    sources["total_air_flow_cfm"] = {"value": None, "status": "unmapped"}
    fallen = _finding(sources, "HGRH", "air_sensible_balance")
    assert fallen.inputs_used["airflow_cfm"] == 9999
    assert fallen.source_keys["airflow_cfm"] == "airside_conditions.total_air_flow_cfm"


def test_unknown_coil_type_runs_only_the_type_free_checks():
    sources = {**_air(600, 80, 55, 30.0, 0), "finned_height": 12, "finned_length": 15, "face_velocity_fpm": 480}
    report = check_performance_consistency(sources, coil_type=None)
    codes = {f.check: f.reason_code for f in report.findings}
    assert codes["air_sensible_balance"] == "PERF_COIL_TYPE_UNKNOWN"
    assert codes["face_velocity"] == "PERF_OK"


def test_every_check_is_always_reported():
    report = check_performance_consistency({}, coil_type="HGRH")
    assert [f.check for f in report.findings] == [
        "air_sensible_balance", "air_total_vs_sensible", "sensible_le_total", "fluid_heat_balance",
        "face_velocity", "air_temp_direction", "wet_bulb_le_dry_bulb",
    ]
    assert report.counts == {"consistent": 0, "inconsistent": 0, "cannot_evaluate": 7}
    by_check = {f.check: f.reason_code for f in report.findings}
    assert by_check["fluid_heat_balance"] == "PERF_NOT_APPLICABLE"
    assert by_check["air_sensible_balance"] == "PERF_SOURCE_MISSING"


# --- invariants -------------------------------------------------------------------------------

def test_sources_are_not_mutated_and_values_are_not_corrected():
    sources = _air(1030, {"value": 54, "unit": "degF"}, 76.76, 27.64, 43)
    before = copy.deepcopy(sources)
    check_performance_consistency(sources, coil_type="HGRH")
    assert sources == before


def test_report_is_a_review_aid():
    report = check_performance_consistency(_air(2000, 51, 70.88, 44.58, 0), coil_type="HGRH")
    assert report.review_aid_only is True
    assert report.export_allowed is False
    assert all(f.review_required is True for f in report.findings)
    # Neither at construction nor afterwards: the models are frozen.
    with pytest.raises(ValidationError):
        report.export_allowed = True
    with pytest.raises(ValidationError):
        report.findings[0].review_required = False
    with pytest.raises(ValidationError):
        report.findings[0].verdict = "consistent"
    with pytest.raises(ValidationError):
        PerformanceConsistencyReport(coil_type="DX", findings=[], counts={}, export_allowed=True)
    with pytest.raises(ValidationError):
        ConsistencyFinding(check="x", verdict="consistent", reason_code="PERF_OK", reason="", approved=True)


def test_sensible_factor_is_the_repo_constant():
    # heating_capacity_mbh hard-codes the workbook's 1.085; this module must not drift from it.
    assert heating_capacity_mbh(eat_f=0, lat_f=1, cfm=1000) == pytest.approx(pc.SENSIBLE_FACTOR, abs=1e-4)


def test_module_is_pure_and_has_no_eval():
    source = Path(pc.__file__).read_text(encoding="utf-8")
    assert "eval(" not in source and "exec(" not in source
    # A fresh interpreter: inside pytest other tests have already imported coilforge.submittal.
    probe = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "import coilforge.coil_utilities.performance_consistency; "
        "bad = [m for m in sys.modules if m.startswith(('coilforge.submittal', 'coilforge.ccsi', "
        "'coilforge.validation', 'coilforge.contracts'))]; "
        "print(bad); sys.exit(1 if bad else 0)"
    )
    done = subprocess.run([sys.executable, "-c", probe, str(SRC)], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


def test_parse_number_refuses_a_string_too_long_to_be_finite():
    assert parse_number("9" * 400) is None
