from __future__ import annotations

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.adapters import load_sanitized_ez_json
from coilforge.compatibility import compare_submittal_and_ez
from coilforge.submittal import load_submittal_candidate_fixture


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "examples" / "sanitized"
SUBMITTAL_FIXTURE = FIXTURE_DIR / "submittal_candidate_dx_header1_default.json"
EZ_FIXTURE = FIXTURE_DIR / "dx_header1_ezc0001_default.json"


def test_submittal_and_ez_compatibility_report_is_review_only() -> None:
    report = compare_submittal_and_ez(
        load_submittal_candidate_fixture(SUBMITTAL_FIXTURE),
        load_sanitized_ez_json(EZ_FIXTURE),
    )

    assert report.case_id == "SCC-SANITIZED-DX-H1-001__EZC-0001"
    assert report.review_status == "compatibility_review_required"
    assert report.export_allowed is False
    assert report.submittal.validation_status == "blocked"
    assert report.ez.validation_status == "review_required"


def test_common_direct_coil_fields_match_between_sanitized_sources() -> None:
    report = compare_submittal_and_ez(
        load_submittal_candidate_fixture(SUBMITTAL_FIXTURE),
        load_sanitized_ez_json(EZ_FIXTURE),
    )

    assert "rows_deep" in report.matching_field_keys
    assert "finned_height" in report.matching_field_keys
    assert "finned_length" in report.matching_field_keys
    assert "fins_per_inch" in report.matching_field_keys
    assert "airflow_direction" in report.matching_field_keys
    assert "coil_hand" in report.matching_field_keys
    assert "return_connection_size" in report.matching_field_keys
    assert "header_type" in report.matching_field_keys
    assert report.mismatch_field_keys == ()


def test_ez_only_drawing_parameters_are_reported_without_approval() -> None:
    report = compare_submittal_and_ez(
        load_submittal_candidate_fixture(SUBMITTAL_FIXTURE),
        load_sanitized_ez_json(EZ_FIXTURE),
    )

    assert {"CD", "BF", "TF", "CH", "SL", "R"}.issubset(report.ez_only_field_keys)
    assert report.submittal.draft_summary.blocked > 0
    assert report.ez.draft_summary.blocked == 0


def test_mismatch_is_a_stop_for_compatibility_review_status() -> None:
    candidate = load_submittal_candidate_fixture(SUBMITTAL_FIXTURE)
    ez_payload = load_sanitized_ez_json(EZ_FIXTURE)
    ez_payload["fin_height"] = 12.5

    report = compare_submittal_and_ez(candidate, ez_payload)

    assert "finned_height" in report.mismatch_field_keys
    assert report.review_status == "mismatch_review_required"
    finned_height = [
        item for item in report.comparisons if item.field_key == "finned_height"
    ][0]
    assert finned_height.review_required is True
    assert finned_height.submittal_value == 12.0
    assert finned_height.ez_value == 12.5
