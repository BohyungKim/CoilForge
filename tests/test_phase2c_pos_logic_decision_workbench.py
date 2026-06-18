from __future__ import annotations

import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.adapters import load_sanitized_ez_json
from coilforge.compatibility import (
    build_field_decision_matrix,
    build_mapping_rule_registry,
    build_reconciliation_plan,
    compare_submittal_and_ez,
)
from coilforge.submittal import (
    build_po_logic_intake_summary,
    default_po_logic_source_paths,
    load_submittal_candidate_fixture,
)


ROOT = Path(__file__).resolve().parents[1]
SANITIZED_DIR = ROOT / "examples" / "sanitized"
PO_LOGIC_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "po_logic"


def _po_logic_summary():
    """Hermetic PO-logic summary built from the in-repo sanitized fixture.

    Avoids depending on the private external sibling project being present on
    disk, so the asserted ``found`` rule set is produced on any machine.
    """

    return build_po_logic_intake_summary(
        default_po_logic_source_paths(PO_LOGIC_FIXTURE_ROOT)
    )
EXPECTED = json.loads(
    (
        ROOT
        / "tests"
        / "fixtures"
        / "compatibility"
        / "field_decision_matrix_expected.json"
    ).read_text(encoding="utf-8")
)


def _candidate():
    return load_submittal_candidate_fixture(
        SANITIZED_DIR / "submittal_candidate_dx_header1_default.json"
    )


def _ez_payload():
    return load_sanitized_ez_json(SANITIZED_DIR / "dx_header1_ezc0001_default.json")


def _matrix(candidate=None, ez_payload=None):
    report = compare_submittal_and_ez(candidate or _candidate(), ez_payload or _ez_payload())
    registry = build_mapping_rule_registry()
    plan = build_reconciliation_plan(report, registry)
    return build_field_decision_matrix(report, registry, plan)


def test_po_logic_intake_summary_can_be_generated_safely() -> None:
    summary = _po_logic_summary()
    payload = summary.to_dict()

    assert payload["raw_private_source_data_read"] is False
    assert payload["export_enabled"] is False
    assert payload["pdf_parsing_enabled"] is False
    assert "reusable_now" in payload["classification_counts"]
    assert any(
        rule["rule_id"] == "po_review_before_export_gate"
        and rule["classification"] == "reusable_now"
        for rule in payload["rule_summaries"]
    )


def test_missing_po_source_path_is_handled_safely(tmp_path: Path) -> None:
    summary = build_po_logic_intake_summary([tmp_path / "missing_po_logic.py"])
    payload = summary.to_dict()

    assert payload["source_status"] == "not_found"
    assert payload["classification_counts"]["not_found"] == 1
    assert payload["raw_private_source_data_read"] is False
    assert payload["rule_summaries"][0]["rule_id"] == "po_logic_source_not_found"


def test_decision_matrix_is_generated_from_compatibility_result() -> None:
    matrix = _matrix()
    payload = matrix.to_dict()

    assert payload["case_id"] == EXPECTED["case_id"]
    assert payload["summary"] == EXPECTED["summary"]
    assert len(payload["items"]) == EXPECTED["summary"]["total_fields"]


def test_exact_match_is_not_treated_as_engineering_approved() -> None:
    rows_deep = _matrix().by_field_key()["rows_deep"]

    assert rows_deep.comparison_category == "exact_match"
    assert rows_deep.selected_policy == "confirmed_for_review_not_engineering_approved"
    assert rows_deep.recommended_decision != "engineering_approved"
    assert rows_deep.export_allowed is False


def test_source_only_values_remain_review_required() -> None:
    cd = _matrix().by_field_key()["CD"]

    assert cd.comparison_category == "ez_only"
    assert cd.selected_policy == "review_required_source_only"
    assert cd.required_decision_owner == "john_or_engineering"
    assert cd.export_allowed is False


def test_unit_mismatch_policy_is_blocked() -> None:
    candidate = _candidate().model_copy(deep=True)
    candidate.geometry["finned_height"] = candidate.geometry["finned_height"].model_copy(
        update={"unit": "mm"}
    )
    finned_height = _matrix(candidate=candidate).by_field_key()["finned_height"]

    assert finned_height.comparison_category == "unit_mismatch"
    assert finned_height.selected_policy == "blocked_requires_explicit_conversion_rule"
    assert finned_height.recommended_decision == "block_until_conversion_rule_is_approved"
    assert finned_height.required_decision_owner == "engineering"


def test_drawing_impacting_fields_are_flagged() -> None:
    matrix = _matrix()

    assert matrix.summary["drawing_impacting"] > 0
    assert matrix.by_field_key()["finned_height"].drawing_impact is True
    assert "drawing_impacting" in matrix.by_field_key()["finned_height"].decision_tags


def test_cd_bf_tf_ch_are_included_if_still_missing_or_blocked() -> None:
    by_field = _matrix().by_field_key()

    for field_key, expected in EXPECTED["required_drawing_baseline_fields"].items():
        item = by_field[field_key]
        assert item.comparison_category == expected["comparison_category"]
        assert item.selected_policy == expected["selected_policy"]
        assert item.drawing_impact is expected["drawing_impact"]
        assert item.submittal_status == expected["submittal_status"]


def test_raw_private_source_text_is_absent() -> None:
    matrix_json = json.dumps(_matrix().to_dict())
    po_summary_json = json.dumps(_po_logic_summary().to_dict())

    assert "FINNED_HEIGHT:" not in matrix_json
    assert "submittal_text" not in matrix_json
    assert _matrix().raw_private_data_returned is False
    assert "FINNED_HEIGHT:" not in po_summary_json


def test_export_and_pdf_export_remain_disabled() -> None:
    matrix = _matrix()

    assert matrix.export_allowed is False
    assert matrix.pdf_export_enabled is False
    assert matrix.direct_coil_final_export_available is False
    assert all(item.export_allowed is False for item in matrix.items)
    assert all(item.pdf_export_enabled is False for item in matrix.items)
