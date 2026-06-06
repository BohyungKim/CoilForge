from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.accuracy import (
    build_submittal_to_drawing_summary,
    compare_accuracy_summary,
    load_expected_summary,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "accuracy"
    / "submittal_to_drawing_expected.json"
)


def test_regression_harness_loads_expected_fixture() -> None:
    expected = load_expected_summary(FIXTURE_PATH)

    assert expected["fixture_format_version"] == 1
    assert expected["workflow"] == "phase2b_submittal_to_drawing"
    assert expected["input_policy"]["source"] == "sanitized_demo"


def test_current_sanitized_workflow_matches_expected_field_counts() -> None:
    actual = build_submittal_to_drawing_summary()
    expected = load_expected_summary(FIXTURE_PATH)

    assert actual["direct_coil_draft"]["summary_counts"] == expected["direct_coil_draft"][
        "summary_counts"
    ]
    assert actual["readiness_report"]["summary_counts"] == expected["readiness_report"][
        "summary_counts"
    ]
    assert actual["readiness_report"]["total_fields"] == 52


def test_blocked_fields_match_expected_keys() -> None:
    actual = build_submittal_to_drawing_summary()
    expected = load_expected_summary(FIXTURE_PATH)

    assert actual["readiness_report"]["blocked_field_keys"] == expected["readiness_report"][
        "blocked_field_keys"
    ]
    assert actual["readiness_report"]["required_missing_field_keys"] == [
        "BF",
        "CD",
        "CH",
        "TF",
    ]


def test_source_evidence_exists_without_raw_private_text() -> None:
    actual = build_submittal_to_drawing_summary()

    assert actual["source_evidence"]["fields_with_source_evidence"] == 12
    assert actual["source_evidence"]["total_source_evidence_refs"] == 12
    assert actual["source_evidence"]["raw_private_text_present"] is False
    assert "submittal_text" not in actual
    assert actual["input_policy"]["raw_private_text_expected"] is False


def test_drawing_metadata_or_blocked_preview_response_matches_expected_status() -> None:
    actual = build_submittal_to_drawing_summary()
    expected = load_expected_summary(FIXTURE_PATH)

    assert actual["drawing"]["preview_allowed"] == expected["drawing"]["preview_allowed"]
    assert actual["drawing"]["metadata"] == expected["drawing"]["metadata"]
    assert actual["drawing"]["review_watermark_present"] is True
    assert actual["validation"]["workflow_status"] == "blocked"


def test_export_remains_disabled() -> None:
    actual = build_submittal_to_drawing_summary()

    assert actual["direct_coil_draft"]["export_status"] == "not_implemented"
    assert actual["readiness_report"]["export_status"] == "not_implemented"
    assert actual["drawing"]["export_allowed"] is False
    assert actual["validation"]["export_allowed"] is False
    assert actual["validation"]["drawing_approval_claimed"] is False


def test_full_accuracy_summary_matches_fixture_with_readable_diff() -> None:
    actual = build_submittal_to_drawing_summary()
    expected = load_expected_summary(FIXTURE_PATH)

    comparison = compare_accuracy_summary(actual, expected)

    assert comparison.passed, comparison.readable_diff()


def test_accuracy_mismatch_diff_is_readable() -> None:
    actual = build_submittal_to_drawing_summary()
    expected = load_expected_summary(FIXTURE_PATH)
    expected["readiness_report"]["summary_counts"]["blocked"] = 99

    comparison = compare_accuracy_summary(actual, expected)

    assert comparison.passed is False
    assert "$.readiness_report.summary_counts.blocked" in comparison.readable_diff()
