from __future__ import annotations

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.adapters import load_sanitized_ez_json
from coilforge.compatibility import (
    build_mapping_rule_registry,
    build_reconciliation_plan,
    compare_submittal_and_ez,
)
from coilforge.submittal import load_submittal_candidate_fixture


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "examples" / "sanitized"
SUBMITTAL_FIXTURE = FIXTURE_DIR / "submittal_candidate_dx_header1_default.json"
EZ_FIXTURE = FIXTURE_DIR / "dx_header1_ezc0001_default.json"


def _build_current_plan():
    return build_reconciliation_plan(
        compare_submittal_and_ez(
            load_submittal_candidate_fixture(SUBMITTAL_FIXTURE),
            load_sanitized_ez_json(EZ_FIXTURE),
        ),
        build_mapping_rule_registry(),
    )


def test_reconciliation_plan_is_review_only_and_export_disabled() -> None:
    plan = _build_current_plan()

    assert plan.case_id == "SCC-SANITIZED-DX-H1-001__EZC-0001"
    assert plan.policy_status == "review_required_no_auto_merge"
    assert plan.export_allowed is False
    assert plan.summary.downstream_allowed == 0
    assert plan.summary.review_required == 52


def test_matching_values_are_candidates_not_approved_values() -> None:
    by_field = _build_current_plan().by_field_key()

    rows = by_field["rows_deep"]
    assert rows.action == "use_matched_candidate_for_review"
    assert rows.selected_source == "both"
    assert rows.candidate_value == 4
    assert rows.downstream_allowed is False
    assert rows.mapping_approval_status == "not_approved_review_required"


def test_source_only_values_are_held_for_review() -> None:
    by_field = _build_current_plan().by_field_key()

    cd = by_field["CD"]
    assert cd.action == "hold_source_only_for_review"
    assert cd.selected_source == "ez"
    assert cd.candidate_value == 5.5
    assert cd.downstream_allowed is False


def test_mismatches_do_not_select_a_merged_value() -> None:
    candidate = load_submittal_candidate_fixture(SUBMITTAL_FIXTURE)
    ez_payload = load_sanitized_ez_json(EZ_FIXTURE)
    ez_payload["fin_height"] = 12.5
    report = compare_submittal_and_ez(candidate, ez_payload)
    plan = build_reconciliation_plan(report, build_mapping_rule_registry())

    decision = plan.by_field_key()["finned_height"]
    assert decision.action == "hold_mismatch_for_review"
    assert decision.selected_source == "none"
    assert decision.candidate_value is None
    assert plan.summary.mismatches_held == 1
