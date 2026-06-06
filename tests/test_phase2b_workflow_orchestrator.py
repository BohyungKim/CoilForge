from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from coilforge.web_app import app


client = TestClient(app)


def test_default_demo_route_works() -> None:
    response = client.get("/api/workflow/default-demo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["input_type"] == "sanitized_text"
    assert payload["summary"]["raw_private_data_included"] is False
    assert payload["summary"]["pdf_parser_enabled"] is False
    assert payload["summary"]["ocr_enabled"] is False
    assert "COIL_TAG: COIL-TAG-001" in payload["input"]["submittal_text"]


def test_sanitized_submittal_input_returns_direct_coil_input_draft() -> None:
    workflow_input = _default_workflow_input()

    response = client.post("/api/workflow/submittal-to-direct-draft", json=workflow_input)

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_candidate_summary"]["tag"] == "COIL-TAG-001"
    assert len(payload["direct_coil_input_draft"]["fields"]) == 52
    assert payload["direct_coil_input_draft"]["fields"]["rows_deep"]["value"] == 4


def test_workflow_returns_readiness_report() -> None:
    response = client.post(
        "/api/workflow/submittal-to-direct-draft",
        json=_default_workflow_input(),
    )

    payload = response.json()
    readiness = payload["readiness_report"]
    assert readiness["total_fields"] == 52
    assert readiness["summary_counts"]["review_required"] == 12
    assert readiness["summary_counts"]["blocked"] == 4
    assert readiness["drawing_parameter_summary"]["blocked_fields"] == ["CD", "BF", "TF", "CH"]


def test_workflow_returns_svg_when_preview_allowed() -> None:
    response = client.post(
        "/api/workflow/submittal-to-drawing",
        json=_default_workflow_input(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation"]["preview_allowed"] is True
    assert "<svg" in payload["svg"]
    assert "REVIEW AID - NOT FOR MANUFACTURING" in payload["svg"]
    assert payload["metadata"]["export_allowed"] is False


def test_blocked_drawing_params_reflected_when_preview_not_allowed() -> None:
    workflow_input = _default_workflow_input()
    workflow_input["preview_defaults"] = []

    response = client.post("/api/workflow/submittal-to-drawing", json=workflow_input)

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation"]["preview_allowed"] is False
    assert payload["svg"] == ""
    assert {"CD", "BF", "TF", "CH"}.issubset(set(payload["validation"]["blocked_fields"]))


def test_source_evidence_is_preserved() -> None:
    response = client.post(
        "/api/workflow/submittal-to-direct-draft",
        json=_default_workflow_input(),
    )

    payload = response.json()
    tag = payload["candidates"][0]["tag"]
    rows = payload["direct_coil_input_draft"]["fields"]["rows_deep"]
    assert tag["source_evidence"][0]["evidence_id"] == "EV-INTAKE-COIL_TAG-3"
    assert rows["source_evidence"][0]["source_key"] == "ROWS_DEEP"
    assert payload["readiness_report"]["source_evidence_summary"]["fields_with_source_evidence"] == 12


def test_export_status_remains_not_implemented() -> None:
    response = client.post(
        "/api/workflow/submittal-to-drawing",
        json=_default_workflow_input(),
    )

    payload = response.json()
    assert payload["direct_coil_input_draft"]["export_status"] == "not_implemented"
    assert payload["readiness_report"]["export_status"] == "not_implemented"
    assert payload["drawing_intent"]["export_allowed"] is False
    assert payload["validation"]["export_status"] == "not_implemented"
    assert payload["validation"]["drawing_approval_claimed"] is False


def _default_workflow_input() -> dict[str, object]:
    return client.get("/api/workflow/default-demo").json()["input"]
