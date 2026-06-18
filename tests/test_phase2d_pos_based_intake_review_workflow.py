from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.review import (
    build_engineering_adjustment,
    build_review_packet,
    resolve_conflicting_adjustments,
)
from coilforge.submittal.po_based_intake import (
    build_po_based_intake,
    normalize_po_unit_tag,
)
from coilforge.submittal.po_logic_bridge import build_po_logic_intake_summary
from coilforge.workflows import (
    build_default_demo_workflow_input,
    run_submittal_to_drawing_workflow,
)


def _po_summary_with_safe_sources(tmp_path: Path):
    paths = []
    for name in (
        "pdf_processing.py",
        "bom_ordering_rules.py",
        "EXTRACTION_CONTRACT.md",
        "PROJECT_CONTEXT.md",
    ):
        path = tmp_path / name
        path.write_text("# sanitized test placeholder\n", encoding="utf-8")
        paths.append(path)
    return build_po_logic_intake_summary(paths)


def _workflow_input() -> dict[str, object]:
    return build_default_demo_workflow_input()["input"]


def _workflow_output() -> dict[str, object]:
    return run_submittal_to_drawing_workflow(_workflow_input())


def _intake(tmp_path: Path):
    return build_po_based_intake(
        _workflow_input(),
        po_logic_summary=_po_summary_with_safe_sources(tmp_path),
    )


def test_pos_based_intake_uses_safe_reusable_logic_when_available(tmp_path: Path) -> None:
    intake = _intake(tmp_path)

    assert normalize_po_unit_tag(" coil tag 001 ") == "COIL-TAG-001"
    assert "po_unit_tag_normalization" in intake.po_logic_used
    assert "po_review_before_export_gate" in intake.po_logic_used
    assert {signal.po_rule_id for signal in intake.signals}.issuperset(
        {"po_unit_tag_normalization", "po_review_before_export_gate"}
    )
    assert all(signal.approved_logic_applied is False for signal in intake.signals)


def test_pos_based_intake_falls_back_when_final_selection_logic_unavailable(tmp_path: Path) -> None:
    intake = _intake(tmp_path)

    assert intake.final_selection_logic_available is False
    assert intake.fallback_used is True
    assert "sanitized submittal intake" in intake.fallback_reason
    assert intake.candidate.candidate_id == "SCC-SANITIZED-INTAKE-001"


def test_bom_linestring_logic_requiring_john_review_is_not_approved(tmp_path: Path) -> None:
    intake = _intake(tmp_path)

    assert "po_bom_linestring_decisions" in intake.po_logic_not_used
    assert all(signal.po_rule_id != "po_bom_linestring_decisions" for signal in intake.signals)
    packet = build_review_packet(_workflow_output(), intake_result=intake)
    assert (
        packet.pos_supported_field_summary["bom_linestring_logic_applied_as_approved"]
        is False
    )


def test_engineering_adjustment_preserves_original_value_and_source_evidence(tmp_path: Path) -> None:
    intake = _intake(tmp_path)
    source_evidence = intake.candidate.tag.source_evidence

    adjustment = build_engineering_adjustment(
        adjustment_id="ADJ-001",
        field_key="tag",
        original_value=intake.candidate.tag.value,
        adjusted_value="COIL-TAG-002",
        reason="Manual quote-prep test adjustment.",
        adjusted_by="engineering_review_demo",
        source_evidence=source_evidence,
    )

    assert adjustment.original_value == "COIL-TAG-001"
    assert adjustment.adjusted_value == "COIL-TAG-002"
    assert adjustment.source_evidence[0].evidence_id == source_evidence[0].evidence_id


def test_manual_override_defaults_to_review_required(tmp_path: Path) -> None:
    intake = _intake(tmp_path)
    adjustment = build_engineering_adjustment(
        adjustment_id="ADJ-002",
        field_key="rows_deep",
        original_value=4,
        adjusted_value=5,
        reason="Manual trial value.",
        adjusted_by="engineering_review_demo",
        source_evidence=intake.candidate.geometry["rows_deep"].source_evidence,
    )

    assert adjustment.review_status == "review_required"
    assert adjustment.downstream_applied is False
    assert adjustment.review_status != "engineering_approved"


def test_conflicting_adjustments_are_blocked(tmp_path: Path) -> None:
    intake = _intake(tmp_path)
    source_evidence = intake.candidate.geometry["rows_deep"].source_evidence
    first = build_engineering_adjustment(
        adjustment_id="ADJ-003A",
        field_key="rows_deep",
        original_value=4,
        adjusted_value=5,
        reason="First manual trial.",
        adjusted_by="engineering_review_demo",
        source_evidence=source_evidence,
    )
    second = build_engineering_adjustment(
        adjustment_id="ADJ-003B",
        field_key="rows_deep",
        original_value=4,
        adjusted_value=6,
        reason="Conflicting manual trial.",
        adjusted_by="engineering_review_demo",
        source_evidence=source_evidence,
    )

    resolved = resolve_conflicting_adjustments([first, second])

    assert {adjustment.review_status for adjustment in resolved} == {"blocked"}
    assert all(adjustment.downstream_applied is False for adjustment in resolved)


def test_drawing_impacting_override_is_flagged(tmp_path: Path) -> None:
    intake = _intake(tmp_path)
    adjustment = build_engineering_adjustment(
        adjustment_id="ADJ-004",
        field_key="CD",
        original_value=None,
        adjusted_value=5.5,
        reason="Manual drawing baseline trial.",
        adjusted_by="engineering_review_demo",
        source_evidence=intake.candidate.source_evidence,
    )

    assert adjustment.drawing_impact is True
    assert adjustment.direct_coil_impact == "drawing_impacting_direct_coil_review_required"


def test_review_packet_can_be_generated_from_existing_workflow_output(tmp_path: Path) -> None:
    packet = build_review_packet(_workflow_output(), intake_result=_intake(tmp_path))

    assert packet.packet_status == "quote_prep_review_only"
    assert packet.coil_identity["draft_id"] == "DCI-CCR-SCC-SANITIZED-INTAKE-001"


def test_review_packet_includes_direct_coil_draft_summary(tmp_path: Path) -> None:
    packet = build_review_packet(_workflow_output(), intake_result=_intake(tmp_path))

    assert packet.direct_coil_input_draft_summary["field_count"] == 52
    assert packet.direct_coil_input_draft_summary["is_export_payload"] is False
    assert packet.direct_coil_input_draft_summary["export_status"] == "not_implemented"


def test_review_packet_includes_readiness_report(tmp_path: Path) -> None:
    packet = build_review_packet(_workflow_output(), intake_result=_intake(tmp_path))

    assert packet.readiness_report_summary["total_fields"] == 52
    assert packet.readiness_report_summary["summary_counts"]["blocked"] == 4
    assert packet.readiness_report_summary["required_missing_fields"] == ["CD", "BF", "TF", "CH"]


def test_review_packet_includes_cd_bf_tf_ch_status(tmp_path: Path) -> None:
    packet = build_review_packet(_workflow_output(), intake_result=_intake(tmp_path))

    assert set(packet.cd_bf_tf_ch_status) == {"CD", "BF", "TF", "CH"}
    assert all(
        item["status"] == "blocked"
        for item in packet.cd_bf_tf_ch_status.values()
    )
    assert all(
        item["production_approved"] is False
        for item in packet.cd_bf_tf_ch_status.values()
    )


def test_review_packet_includes_drawing_impacting_field_summary(tmp_path: Path) -> None:
    packet = build_review_packet(_workflow_output(), intake_result=_intake(tmp_path))

    assert packet.drawing_impacting_field_summary["field_count"] == 22
    assert packet.drawing_impacting_field_summary["field_statuses"]["CD"] == "blocked"
    assert packet.drawing_impacting_field_summary["production_drawing_approval_claimed"] is False


def test_review_packet_includes_unresolved_john_engineering_review_items(tmp_path: Path) -> None:
    packet = build_review_packet(_workflow_output(), intake_result=_intake(tmp_path))
    unresolved = "\n".join(packet.unresolved_review_items)

    assert "CD/BF/TF/CH" in unresolved
    assert "22 drawing-impacting fields" in unresolved
    assert "POs-supported field adoption" in unresolved
    assert "unit conversion" in unresolved


def test_export_remains_disabled(tmp_path: Path) -> None:
    packet = build_review_packet(_workflow_output(), intake_result=_intake(tmp_path))

    assert packet.export_status.export_allowed is False
    assert packet.quote_prep_status["final_quote"] is False
    assert packet.quote_prep_status["quote_finalization_available"] is False


def test_pdf_export_remains_disabled(tmp_path: Path) -> None:
    packet = build_review_packet(_workflow_output(), intake_result=_intake(tmp_path))

    assert packet.export_status.pdf_export_enabled is False
    assert packet.svg_metadata_summary["pdf_export_enabled"] is False


def test_direct_coil_final_export_remains_unavailable(tmp_path: Path) -> None:
    packet = build_review_packet(_workflow_output(), intake_result=_intake(tmp_path))

    assert packet.export_status.direct_coil_final_export_available is False
    assert packet.export_status.production_drawing_approval_claimed is False


def test_raw_private_source_text_is_absent(tmp_path: Path) -> None:
    packet = build_review_packet(_workflow_output(), intake_result=_intake(tmp_path))
    packet_json = json.dumps(packet.to_dict())

    assert packet.raw_private_source_text_included is False
    assert "submittal_text" not in packet_json
    assert "FINNED_HEIGHT:" not in packet_json
    assert "raw_pdf" not in packet_json.lower()


def test_review_packet_api_routes_are_read_only(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from coilforge.web_app import app

    client = TestClient(app)
    response = client.get("/api/review/default-packet")

    assert response.status_code == 200
    payload = response.json()
    assert payload["packet_status"] == "quote_prep_review_only"
    assert payload["export_status"]["export_allowed"] is False
    assert payload["export_status"]["pdf_export_enabled"] is False
    assert payload["export_status"]["direct_coil_final_export_available"] is False
