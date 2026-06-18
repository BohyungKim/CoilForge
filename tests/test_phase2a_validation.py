from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.phase2a.fixtures import load_default_dx_header1_state
from coilforge.phase2a.validation import validate_dx_header1_state


def _check(report, check_id: str):
    return next(check for check in report.checks if check.check_id == check_id)


def test_default_state_passes_with_oal_warning() -> None:
    report = validate_dx_header1_state(load_default_dx_header1_state())

    assert report.validation_status == "pass_with_warnings"
    assert _check(report, "phase2a_required_coil_name").status == "pass"
    assert _check(report, "phase2a_category_dx").status == "pass"
    assert _check(report, "phase2a_header1_only").status == "pass"
    assert _check(report, "phase2a_required_airflow_direction").status == "pass"
    assert _check(report, "phase2a_oal_not_approved").status == "warn"
    assert _check(report, "phase2a_full_json_adapter_not_applicable").status == "not_applicable"


def test_unsupported_category_is_blocked() -> None:
    payload = load_default_dx_header1_state().model_dump()
    payload["coil_category"] = "HGRH"

    report = validate_dx_header1_state(payload)

    assert report.validation_status == "blocked"
    assert _check(report, "phase2a_category_dx").status == "blocked"
    assert "coil_category" in report.blocked_fields


def test_unsupported_header_is_blocked() -> None:
    payload = load_default_dx_header1_state().model_dump()
    payload["header_type"] = "Header 2"

    report = validate_dx_header1_state(payload)

    assert report.validation_status == "blocked"
    assert _check(report, "phase2a_header1_only").status == "blocked"
    assert "header_type" in report.blocked_fields


def test_missing_airflow_direction_is_blocked() -> None:
    payload = load_default_dx_header1_state().model_dump()
    payload["airflow_direction"] = ""

    report = validate_dx_header1_state(payload)

    assert report.validation_status == "blocked"
    assert _check(report, "phase2a_required_airflow_direction").status == "blocked"
    assert "airflow_direction" in report.blocked_fields


def test_oal_active_generation_is_blocked() -> None:
    payload = load_default_dx_header1_state().model_dump()
    payload["oal_generation_requested"] = True

    report = validate_dx_header1_state(payload)

    assert report.validation_status == "blocked"
    assert _check(report, "phase2a_oal_not_approved").status == "blocked"
    assert "OAL" in report.blocked_fields


def test_manufacturing_release_status_is_blocked() -> None:
    payload = load_default_dx_header1_state().model_dump()
    payload["release_status"] = "approved_for_manufacturing"

    report = validate_dx_header1_state(payload)

    assert report.validation_status == "blocked"
    assert _check(report, "phase2a_release_status_safe").status == "blocked"
    assert "release_status" in report.blocked_fields
