from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.adapters import load_sanitized_ez_json
from coilforge.compatibility import (
    build_decision_matrix_review_surface,
    build_field_decision_matrix,
    build_john_decision_capture_packet,
    build_mapping_rule_registry,
    build_reconciliation_plan,
    compare_submittal_and_ez,
)
from coilforge.submittal import (
    build_po_logic_intake_summary,
    default_po_logic_source_paths,
    load_submittal_candidate_fixture,
)
from coilforge.workflows import (
    build_default_demo_workflow_input,
    run_submittal_to_drawing_workflow,
)


ROOT = Path(__file__).resolve().parents[1]
SANITIZED_DIR = ROOT / "examples" / "sanitized"
PO_LOGIC_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "po_logic"


def _po_logic_summary():
    """Hermetic PO-logic summary built from the in-repo sanitized fixture."""

    return build_po_logic_intake_summary(
        default_po_logic_source_paths(PO_LOGIC_FIXTURE_ROOT)
    )


def _candidate():
    return load_submittal_candidate_fixture(
        SANITIZED_DIR / "submittal_candidate_dx_header1_default.json"
    )


def _ez_payload():
    return load_sanitized_ez_json(SANITIZED_DIR / "dx_header1_ezc0001_default.json")


def _surface(candidate=None, ez_payload=None):
    report = compare_submittal_and_ez(candidate or _candidate(), ez_payload or _ez_payload())
    registry = build_mapping_rule_registry()
    plan = build_reconciliation_plan(report, registry)
    matrix = build_field_decision_matrix(report, registry, plan)
    return build_decision_matrix_review_surface(
        matrix,
        _po_logic_summary(),
    )


def _packet(candidate=None, ez_payload=None):
    return build_john_decision_capture_packet(_surface(candidate, ez_payload))


def _workflow_payload() -> dict[str, object]:
    return build_default_demo_workflow_input()["input"]


def test_decision_capture_packet_can_be_generated_from_review_surface() -> None:
    packet = _packet()
    payload = packet.to_dict()

    assert payload["case_id"] == "SCC-SANITIZED-DX-H1-001__EZC-0001"
    assert payload["summary"]["total_decision_items"] == 52
    assert payload["summary"]["decision_packet_status"] == "disabled_review_outcome_capture_only"
    assert len(payload["items"]) == 52
    assert set(payload["sections"]) == {
        "exact_matches",
        "submittal_only_values",
        "ez_only_values",
        "missing_both_fields",
        "drawing_impacting_fields",
        "required_direct_coil_fields",
        "pos_supported_fields",
        "pos_needs_review_logic",
        "cd_bf_tf_ch",
    }


def test_exact_match_remains_not_engineering_approved() -> None:
    rows_deep = _packet().by_field_key()["rows_deep"]

    assert rows_deep.comparison_category == "exact_match"
    assert rows_deep.current_policy == "confirmed_for_review_not_engineering_approved"
    assert rows_deep.current_approval_state == "confirmed_for_review"
    assert rows_deep.proposed_decision == "accept_for_review_only"
    assert rows_deep.export_allowed_after_decision is False
    assert rows_deep.current_approval_state != "engineering_approved"


def test_source_only_values_remain_review_required() -> None:
    cd = _packet().by_field_key()["CD"]

    assert cd.comparison_category == "ez_only"
    assert cd.current_policy == "review_required_source_only"
    assert cd.current_approval_state in {"needs_john_review", "blocked"}
    assert cd.proposed_decision == "request_drawing_semantics_review"
    assert cd.export_allowed_after_decision is False


def test_pos_supported_values_are_not_automatically_approved() -> None:
    packet = _packet()
    header_type = packet.by_field_key()["header_type"]
    section = packet.sections["pos_supported_fields"]

    assert "header_type" in section.field_keys
    assert section.current_policy == "recommended_for_rule_review_not_ready"
    assert header_type.decision_scope == "recommended_for_rule_review_not_ready"
    assert header_type.proposed_decision == "accept_for_review_only"
    assert header_type.export_allowed_after_decision is False


def test_cd_bf_tf_ch_are_present_and_review_required_or_blocked() -> None:
    packet = _packet()

    assert set(packet.cd_bf_tf_ch_status) == {"CD", "BF", "TF", "CH"}
    for field_key in ("CD", "BF", "TF", "CH"):
        item = packet.by_field_key()[field_key]
        status = packet.cd_bf_tf_ch_status[field_key]
        assert item.current_approval_state in {"needs_john_review", "blocked"}
        assert item.current_policy in {
            "review_required_source_only",
            "blocked_requires_explicit_conversion_rule",
            "blocked_no_merged_value",
        }
        assert item.drawing_impact is True
        assert status["export_allowed_after_decision"] is False


def test_drawing_impacting_fields_require_john_or_engineering_review() -> None:
    packet = _packet()
    section = packet.sections["drawing_impacting_fields"]

    assert len(section.field_keys) == 22
    assert section.recommended_proposed_decision == "request_drawing_semantics_review"
    assert section.required_owner == "john_or_engineering"
    for field_key in section.field_keys:
        item = packet.by_field_key()[field_key]
        assert item.drawing_impact is True
        assert item.current_approval_state in {
            "confirmed_for_review",
            "needs_john_review",
            "pending_review",
            "blocked",
        }


def test_missing_both_fields_remain_not_approved() -> None:
    packet = _packet()
    section = packet.sections["missing_both_fields"]

    assert len(section.field_keys) == 34
    assert section.current_policy == "review_required_missing_both"
    for field_key in section.field_keys:
        item = packet.by_field_key()[field_key]
        assert item.comparison_category == "missing_both"
        assert item.current_approval_state == "pending_review"
        assert item.proposed_decision in {
            "defer_decision",
            "accept_for_review_only",
            "keep_review_required",
            "request_manual_engineering_override",
        }
        assert item.export_allowed_after_decision is False


def test_unit_conversion_decisions_remain_blocked_request_rule_only() -> None:
    candidate = _candidate().model_copy(deep=True)
    candidate.geometry["finned_height"] = candidate.geometry["finned_height"].model_copy(
        update={"unit": "mm"}
    )
    finned_height = _packet(candidate=candidate).by_field_key()["finned_height"]

    assert finned_height.comparison_category == "unit_mismatch"
    assert finned_height.current_policy == "blocked_requires_explicit_conversion_rule"
    assert finned_height.current_approval_state == "blocked"
    assert finned_height.proposed_decision == "request_unit_conversion_rule"
    assert finned_height.proposed_decision_status == "needs_engineering_review"
    assert finned_height.export_allowed_after_decision is False


def test_captured_proposed_decisions_do_not_change_export_allowed() -> None:
    packet = _packet()

    assert packet.export_allowed is False
    assert packet.pdf_export_enabled is False
    assert packet.direct_coil_final_export_available is False
    assert packet.decisions_apply_downstream is False
    assert all(item.export_allowed_after_decision is False for item in packet.items)
    assert all(item.pdf_export_allowed_after_decision is False for item in packet.items)
    assert all(
        item.direct_coil_final_export_allowed_after_decision is False
        for item in packet.items
    )


def test_captured_proposed_decisions_do_not_change_direct_coil_draft_readiness() -> None:
    before = run_submittal_to_drawing_workflow(_workflow_payload())
    _packet()
    after = run_submittal_to_drawing_workflow(_workflow_payload())

    assert before["direct_coil_input_draft"]["summary"] == after["direct_coil_input_draft"]["summary"]
    assert before["readiness_report"]["summary_counts"] == after["readiness_report"]["summary_counts"]
    assert after["direct_coil_input_draft"]["export_status"] == "not_implemented"
    assert after["readiness_report"]["export_status"] == "not_implemented"


def test_captured_proposed_decisions_do_not_change_drawing_intent_approval() -> None:
    before = run_submittal_to_drawing_workflow(_workflow_payload())
    _packet()
    after = run_submittal_to_drawing_workflow(_workflow_payload())

    assert before["drawing_intent"]["review_status"] == after["drawing_intent"]["review_status"]
    assert after["drawing_intent"]["review_status"] == "review_required"
    assert after["drawing_intent"]["export_allowed"] is False
    assert after["validation"]["drawing_approval_claimed"] is False


def test_raw_private_source_text_is_absent() -> None:
    packet_json = json.dumps(_packet().to_dict())

    assert "FINNED_HEIGHT:" not in packet_json
    assert "submittal_text" not in packet_json
    assert "raw_pdf" not in packet_json.lower()
    assert '"current_approval_state": "engineering_approved"' not in packet_json
    assert "engineering_approved" not in _packet().allowed_proposed_decision_statuses
    assert _packet().raw_private_data_returned is False


def test_decision_capture_api_returns_export_disabled_if_fastapi_is_available() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from coilforge.web_app import app

    client = TestClient(app)
    response = client.get("/api/compatibility/decision-capture")
    template_response = client.get("/api/compatibility/decision-capture/template")

    assert response.status_code == 200
    assert template_response.status_code == 200
    payload = response.json()
    template = template_response.json()
    assert payload["export_allowed"] is False
    assert payload["pdf_export_enabled"] is False
    assert payload["direct_coil_final_export_available"] is False
    assert payload["decisions_apply_downstream"] is False
    assert template["template_mode"] == "disabled_placeholder"
    assert template["save_enabled"] is False
    assert template["engineering_approval_enabled"] is False


def test_ui_placeholder_remains_disabled_if_ui_is_updated() -> None:
    index_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert "John Decision Capture" in index_html
    assert "decision-capture-summary" in index_html
    assert "/api/compatibility/decision-capture" in app_js
    assert "select disabled" in app_js
    assert "Proposed decisions are not applied" in index_html
    assert "save-to-production" not in app_js.lower()
