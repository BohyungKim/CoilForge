from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from coilforge.web_app import REVIEW_WATERMARK, app


client = TestClient(app)


def test_get_index_serves_ui_shell() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Parameter Editor" in response.text
    assert "Validation Panel" in response.text
    assert "SVG Preview" in response.text
    assert "Snapshot / Metadata" in response.text


def test_default_state_loads_sanitized_fixture() -> None:
    response = client.get("/api/default-state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["source_case_id"] == "EZC-0001"
    assert payload["state"]["coil_category"] == "DX"
    assert payload["state"]["header_type"] == "Header 1"
    assert payload["state"]["release_status"] == "review_aid_only"
    assert payload["state"]["drawing_status"] == "not_generated"
    assert payload["fixture"]["fixture_name"] == "sanitized_dx_header1_ezc0001_default"


def test_validate_returns_contract_shaped_report() -> None:
    state = client.get("/api/default-state").json()["state"]

    response = client.post("/api/validate", json=state)

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation_status"] == "pass_with_warnings"
    assert payload["summary"]["warn_count"] >= 1
    assert any(
        check["check_id"] == "phase2a_oal_not_approved"
        for check in payload["checks"]
    )
    assert payload["blocked_fields"] == []


def test_render_svg_returns_review_aid_svg() -> None:
    state = client.get("/api/default-state").json()["state"]
    validation_report = client.post("/api/validate", json=state).json()

    response = client.post(
        "/api/render-svg",
        json={
            "state": state,
            "validation_report": validation_report,
            "render_options": {
                "viewBox": "0 0 1600 1200",
                "include_review_watermark": True,
                "include_markup_layer": True,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "<svg" in payload["svg"]
    assert 'viewBox="0 0 1600 1200"' in payload["svg"]
    assert REVIEW_WATERMARK in payload["svg"]
    assert payload["metadata"]["release_status"] == "review_aid_only"
    assert payload["metadata"]["drawing_status"] == "generated_with_warnings"
    assert "OAL" in payload["svg"]
    assert "REVIEW REQUIRED" in payload["svg"]


def test_generate_snapshot_returns_contract_shaped_review_package() -> None:
    state = client.get("/api/default-state").json()["state"]
    validation_report = client.post("/api/validate", json=state).json()
    renderer_payload = client.post(
        "/api/render-svg",
        json={"state": state, "validation_report": validation_report},
    ).json()

    response = client.post(
        "/api/generate-snapshot",
        json={
            "state": state,
            "validation_report": validation_report,
            "renderer_metadata": renderer_payload["metadata"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["checklist_snapshot"]["snapshot_status"] == "draft_review_aid"
    assert payload["checklist_snapshot"]["state"]["source_case_id"] == "EZC-0001"
    assert payload["drawing_metadata"]["release_status"] == "review_aid_only"
    assert payload["drawing_metadata"]["john_review_required"] is True
