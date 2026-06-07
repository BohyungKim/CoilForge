from __future__ import annotations

import json
from pathlib import Path

import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.adapters import load_sanitized_ez_json
from coilforge.compatibility import (
    build_decision_matrix_review_surface,
    build_field_decision_matrix,
    build_mapping_rule_registry,
    build_reconciliation_plan,
    compare_submittal_and_ez,
)
from coilforge.submittal import build_po_logic_intake_summary, load_submittal_candidate_fixture


ROOT = Path(__file__).resolve().parents[1]
SANITIZED_DIR = ROOT / "examples" / "sanitized"
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


def _surface():
    return build_decision_matrix_review_surface(
        _matrix(),
        build_po_logic_intake_summary(),
    )


def test_decision_review_summary_can_be_generated_from_expected_fixture() -> None:
    surface = _surface()
    payload = surface.to_dict()

    assert payload["case_id"] == EXPECTED["case_id"]
    assert payload["field_category_counts"]["total_fields"] == EXPECTED["summary"]["total_fields"]
    assert payload["field_category_counts"]["exact_match"] == EXPECTED["summary"]["exact_match"]
    assert payload["field_category_counts"]["ez_only"] == EXPECTED["summary"]["ez_only"]
    assert len(payload["items"]) == EXPECTED["summary"]["total_fields"]
    assert set(payload["groups"]).issuperset(
        {
            "exact_match",
            "submittal_only",
            "ez_only",
            "missing_both",
            "status_mismatch",
            "drawing_impacting",
            "required_direct_coil",
            "needs_john_review",
            "blocked",
        }
    )


def test_exact_match_is_confirmed_for_review_not_engineering_approved() -> None:
    rows_deep = _surface().by_field_key()["rows_deep"]

    assert rows_deep.comparison_category == "exact_match"
    assert rows_deep.approval_state == "confirmed_for_review"
    assert rows_deep.current_policy == "confirmed_for_review_not_engineering_approved"
    assert rows_deep.approval_state != "engineering_approved"
    assert rows_deep.recommended_decision != "engineering_approved"
    assert rows_deep.export_allowed is False


def test_source_only_values_remain_review_required() -> None:
    cd = _surface().by_field_key()["CD"]

    assert cd.comparison_category == "ez_only"
    assert cd.current_policy == "review_required_source_only"
    assert cd.approval_state == "needs_john_review"
    assert cd.required_owner == "john_or_engineering"


def test_cd_bf_tf_ch_are_present_and_review_required_or_blocked() -> None:
    surface = _surface()

    for field_key in ("CD", "BF", "TF", "CH"):
        item = surface.by_field_key()[field_key]
        assert item.approval_state in {"needs_john_review", "blocked"}
        assert item.current_policy in {
            "review_required_source_only",
            "blocked_requires_explicit_conversion_rule",
            "blocked_no_merged_value",
        }
        assert item.drawing_impact is True
        assert "baseline_drawing_field" in item.highlight_reasons


def test_drawing_impacting_fields_are_highlighted() -> None:
    surface = _surface()

    assert surface.field_category_counts["drawing_impacting"] == EXPECTED["summary"]["drawing_impacting"]
    assert set(surface.groups["drawing_impacting"]).issubset(surface.highlighted_field_keys)
    assert "drawing_impacting" in surface.by_field_key()["finned_height"].highlight_reasons


def test_pos_supported_fields_are_visible_review_only() -> None:
    surface = _surface()

    assert surface.field_category_counts["pos_supported"] >= 1
    assert "header_type" in surface.pos_logic_summary["supported_field_keys"]
    assert surface.by_field_key()["header_type"].pos_logic_status.startswith("pos_supported")
    assert surface.by_field_key()["header_type"].export_allowed is False


def test_pos_needs_review_logic_is_visible_without_downstream_use() -> None:
    surface = _surface()

    assert "po_bom_linestring_decisions" in surface.pos_logic_summary["needs_review_rule_ids"]
    assert surface.field_category_counts["pos_needs_john_review"] >= 1
    assert "distributor_notes" in surface.pos_logic_summary["needs_review_field_keys"]
    assert (
        surface.by_field_key()["distributor_notes"].pos_logic_status
        == "pos_logic_needs_john_review"
    )


def test_raw_private_source_text_is_absent_from_review_surface() -> None:
    surface_json = json.dumps(_surface().to_dict())

    assert "FINNED_HEIGHT:" not in surface_json
    assert "submittal_text" not in surface_json
    assert "raw_pdf" not in surface_json.lower()
    assert _surface().raw_private_data_returned is False
    assert all(item.raw_text_excluded for item in _surface().items)


def test_export_pdf_and_final_export_remain_disabled() -> None:
    surface = _surface()

    assert surface.export_allowed is False
    assert surface.pdf_export_enabled is False
    assert surface.direct_coil_final_export_available is False
    assert all(item.export_allowed is False for item in surface.items)
    assert all(item.pdf_export_enabled is False for item in surface.items)
    assert all(item.direct_coil_final_export_available is False for item in surface.items)


def test_approval_state_policy_does_not_include_engineering_approval() -> None:
    policy = _surface().approval_state_policy

    assert set(policy) == {
        "pending_review",
        "confirmed_for_review",
        "needs_john_review",
        "blocked",
        "not_approved",
    }
    assert "engineering_approved" not in json.dumps(policy)


def test_untracked_ui_compatibility_files_are_classified_in_m3_doc() -> None:
    doc = (ROOT / "docs" / "PHASE2C_M3_DECISION_MATRIX_REVIEW_SURFACE.md").read_text(
        encoding="utf-8"
    )

    assert "docs/PHASE2C_UI_COMPATIBILITY_PANEL.md" in doc
    assert "tests/test_phase2c_ui_compatibility_panel.py" in doc
    assert "duplicate_of_committed_workbench" in doc
    assert "useful_content_to_absorb" in doc
    assert "outputs/ remains unstaged" in doc


def test_decision_review_api_is_read_only_if_fastapi_is_available() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from coilforge.web_app import app

    client = TestClient(app)
    matrix_response = client.get("/api/compatibility/decision-matrix")
    review_response = client.get("/api/compatibility/decision-review")

    assert matrix_response.status_code == 200
    assert review_response.status_code == 200
    assert matrix_response.json()["export_allowed"] is False
    review_payload = review_response.json()
    assert review_payload["export_allowed"] is False
    assert review_payload["pdf_export_enabled"] is False
    assert review_payload["direct_coil_final_export_available"] is False
