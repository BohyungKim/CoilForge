from __future__ import annotations

import json
from pathlib import Path

import sys

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from coilforge.adapters import load_sanitized_ez_json
from coilforge.compatibility import (
    build_compatibility_diff_review_packet,
    build_mapping_rule_registry,
    build_reconciliation_plan,
    compare_submittal_and_ez,
)
from coilforge.rules import is_rule_approved, load_mapping_rule_registry
from coilforge.submittal import load_submittal_candidate_fixture
from coilforge.web_app import app


ROOT = Path(__file__).resolve().parents[1]
SANITIZED_DIR = ROOT / "examples" / "sanitized"
EXPECTED = json.loads(
    (ROOT / "tests" / "fixtures" / "compatibility" / "submittal_vs_ez_expected.json")
    .read_text(encoding="utf-8")
)


def _candidate():
    return load_submittal_candidate_fixture(
        SANITIZED_DIR / "submittal_candidate_dx_header1_default.json"
    )


def _ez_payload():
    return load_sanitized_ez_json(SANITIZED_DIR / "dx_header1_ezc0001_default.json")


def _report():
    return compare_submittal_and_ez(_candidate(), _ez_payload())


def test_submittal_vs_ez_comparison_runs_and_matches_expected_fixture() -> None:
    report = _report()

    assert report.case_id == EXPECTED["case_id"]
    assert report.category_counts == EXPECTED["category_counts"]
    assert list(report.required_field_issues) == EXPECTED["required_field_issues"]
    assert len(report.drawing_impacting_issues) == EXPECTED["drawing_impacting_issue_count"]
    assert report.export_allowed is EXPECTED["export_allowed"]
    assert report.submittal.canonical_summary["validation_status"] == "blocked"
    assert report.ez.readiness_counts["blocked"] == 0
    assert report.drawing_intent_comparison["available"] is True


def test_difference_categories_required_and_drawing_impacting_fields_are_produced() -> None:
    report = _report()

    assert "exact_match" in set(report.categories_by_field.values())
    assert "submittal_only" in set(report.categories_by_field.values())
    assert "ez_only" in set(report.categories_by_field.values())
    assert report.categories_by_field["rows_deep"] == "exact_match"
    assert report.categories_by_field["CD"] == "ez_only"
    assert "CD" in report.required_field_issues
    assert "finned_height" not in report.required_field_issues
    assert "finned_height" not in report.drawing_impacting_issues
    assert "CD" in report.drawing_impacting_issues


def test_review_packet_is_safe_grouped_and_review_only() -> None:
    packet = build_compatibility_diff_review_packet(_report())

    assert "## Grouped differences" in packet
    assert "## Required Direct Coil field issues" in packet
    assert "## Drawing-impacting issues" in packet
    assert "Raw/private source text is excluded" in packet
    assert "Production drawing approval: `not_requested_not_granted`" in packet
    assert "FINNED_HEIGHT:" not in packet


def test_mapping_rule_registry_loads_unique_ids_and_drafts_are_not_approved() -> None:
    registry = load_mapping_rule_registry()
    rule_ids = [rule.rule_id for rule in registry.rules]

    assert len(rule_ids) == len(set(rule_ids))
    assert {"submittal_to_canonical", "ez_to_canonical", "canonical_to_direct_coil", "direct_coil_to_drawing_intent"}.issubset(
        registry.summary.by_rule_type
    )
    assert registry.summary.approved_count == 0
    assert all(
        not is_rule_approved(rule)
        for rule in registry.rules
        if rule.approval_status in {"draft", "review_required"}
    )


def test_reconciliation_policy_keeps_conflicts_review_required_or_blocked() -> None:
    ez_payload = _ez_payload()
    ez_payload["fin_height"] = 12.5
    value_report = compare_submittal_and_ez(_candidate(), ez_payload)
    value_plan = build_reconciliation_plan(value_report, build_mapping_rule_registry())

    value_decision = value_plan.by_field_key()["finned_height"]
    assert value_report.categories_by_field["finned_height"] == "value_mismatch"
    assert value_decision.result_status == "review_required"
    assert value_decision.downstream_allowed is False

    candidate = _candidate().model_copy(deep=True)
    candidate.geometry["finned_height"] = candidate.geometry["finned_height"].model_copy(
        update={"unit": "mm"}
    )
    unit_report = compare_submittal_and_ez(candidate, _ez_payload())
    unit_plan = build_reconciliation_plan(unit_report, build_mapping_rule_registry())

    unit_decision = unit_plan.by_field_key()["finned_height"]
    assert unit_report.categories_by_field["finned_height"] == "unit_mismatch"
    assert unit_decision.result_status == "blocked"
    assert unit_decision.downstream_allowed is False


def test_compatibility_api_returns_safe_summary_and_export_stays_disabled() -> None:
    client = TestClient(app)

    default_response = client.get("/api/compatibility/default-demo")
    compare_response = client.post("/api/compatibility/compare", json={})
    packet_response = client.post("/api/compatibility/review-packet", json={})

    assert default_response.status_code == 200
    assert compare_response.status_code == 200
    assert packet_response.status_code == 200
    payload = default_response.json()
    assert payload["safe_summary"]["raw_private_data_returned"] is False
    assert payload["safe_summary"]["raw_source_text_returned"] is False
    assert payload["safe_summary"]["export_allowed"] is False
    assert payload["safe_summary"]["pdf_export_enabled"] is False
    assert payload["safe_summary"]["direct_coil_final_export_available"] is False
    assert payload["report"]["export_allowed"] is False
    assert payload["reconciliation_plan"]["export_allowed"] is False

    response_text = default_response.text + compare_response.text + packet_response.text
    assert "submittal_text" not in response_text
    assert "FINNED_HEIGHT:" not in response_text
    assert "raw_private" in response_text
