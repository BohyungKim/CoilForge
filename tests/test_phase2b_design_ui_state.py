from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from coilforge.web_app import app


client = TestClient(app)


def test_ui_default_route_returns_sanitized_state() -> None:
    response = client.get("/api/ui/default")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project"]["project_name"] == "Sanitized CoilForge Demo"
    assert payload["project"]["coil_tag"] == "COIL-TAG-001"
    assert payload["import_summary"]["raw_private_data_included"] is False
    assert payload["import_summary"]["pdf_parser_enabled"] is False
    assert payload["import_summary"]["ocr_enabled"] is False


def test_ui_state_contains_required_sections() -> None:
    payload = client.get("/api/ui/default").json()

    assert {
        "project",
        "import_summary",
        "direct_coil_draft",
        "readiness_report",
        "drawing_intent",
        "drawing_parameters",
        "performance_summary",
        "validation",
        "source_evidence",
    }.issubset(payload.keys())


def test_export_pdf_is_disabled_in_ui_state() -> None:
    payload = client.get("/api/ui/default").json()

    assert payload["actions"]["export_pdf"]["enabled"] is False
    assert payload["actions"]["export_pdf"]["placeholder"] is True
    assert payload["direct_coil_draft"]["export_status"] == "not_implemented"
    assert payload["drawing_preview"]["export_allowed"] is False


def test_direct_coil_draft_fields_can_be_represented() -> None:
    payload = client.get("/api/ui/default").json()
    draft = payload["direct_coil_draft"]

    assert len(draft["fields"]) == 52
    assert "Coil Geometry" in draft["groups"]
    assert "rows_deep" in draft["groups"]["Coil Geometry"]
    assert draft["fields"]["rows_deep"]["label"] == "Rows deep"
    assert draft["fields"]["rows_deep"]["value"] == 4


def test_validation_summary_can_be_represented() -> None:
    payload = client.get("/api/ui/default").json()
    validation = payload["validation"]

    assert validation["workflow_status"] == "blocked"
    assert validation["export_status"] == "not_implemented"
    assert validation["readiness_counts"]["ready"] == 0
    assert validation["readiness_counts"]["review_required"] == 12
    assert validation["readiness_counts"]["blocked"] == 4
    assert validation["readiness_counts"]["unmapped"] == 36
    assert {"CD", "BF", "TF", "CH"}.issubset(set(validation["blocked_fields"]))
    assert validation["unmapped_field_count"] == 36
