from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from coilforge.web_app import app


client = TestClient(app)


def test_full_workflow_route_is_available() -> None:
    response = client.post("/api/workflow/submittal-to-drawing", json=_default_workflow_input())

    assert response.status_code == 200
    assert response.json()["validation"]["export_status"] == "not_implemented"


def test_ui_can_load_default_demo_state() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "edit-finned-height" in response.text
    assert "edit-finned-length" in response.text
    assert "edit-coil-name" in response.text
    assert "manual-drawing-mode" in response.text


def test_workflow_response_includes_direct_coil_input_draft() -> None:
    payload = _drawing_workflow()

    draft = payload["direct_coil_input_draft"]
    assert len(draft["fields"]) == 52
    assert draft["fields"]["finned_height"]["value"] == 12.0
    assert draft["fields"]["finned_length"]["value"] == 15.0


def test_workflow_response_includes_readiness_report() -> None:
    payload = _drawing_workflow()

    readiness = payload["readiness_report"]
    assert readiness["total_fields"] == 52
    assert readiness["summary_counts"]["review_required"] == 12
    assert readiness["summary_counts"]["blocked"] == 4
    assert {"CD", "BF", "TF", "CH"}.issubset(
        {field["field_key"] for field in readiness["blocked_fields"]}
    )


def test_workflow_response_includes_svg_or_blocked_preview_response() -> None:
    payload = _drawing_workflow()

    assert "svg" in payload
    assert "metadata" in payload
    assert payload["validation"]["preview_allowed"] is True
    assert "<svg" in payload["svg"]


def test_editing_finned_height_changes_request_payload_and_svg_metadata() -> None:
    original = _drawing_workflow()
    edited_input = _default_workflow_input()
    edited_input["submittal_text"] = edited_input["submittal_text"].replace(
        "FINNED_HEIGHT: 12.0 in",
        "FINNED_HEIGHT: 14.5 in",
    )

    response = client.post("/api/workflow/submittal-to-drawing", json=edited_input)

    assert response.status_code == 200
    payload = response.json()
    assert payload["direct_coil_input_draft"]["fields"]["finned_height"]["value"] == 14.5
    assert payload["drawing_intent"]["finned_height"] == 14.5
    assert payload["svg"] != original["svg"]


def test_export_pdf_is_disabled() -> None:
    payload = client.get("/api/ui/default").json()

    assert payload["actions"]["export_pdf"]["enabled"] is False
    assert payload["drawing_preview"]["export_allowed"] is False
    assert payload["direct_coil_draft"]["export_status"] == "not_implemented"


def test_blocked_fields_remain_visible_in_ui_state() -> None:
    payload = client.get("/api/ui/default").json()

    assert {"CD", "BF", "TF", "CH"}.issubset(set(payload["validation"]["blocked_fields"]))
    assert {"CD", "BF", "TF", "CH"}.issubset(
        {field["field_key"] for field in payload["readiness_report"]["blocked_fields"]}
    )


def test_review_watermark_remains_visible_if_svg_is_returned() -> None:
    payload = _drawing_workflow()

    assert payload["validation"]["preview_allowed"] is True
    assert "REVIEW AID - NOT FOR MANUFACTURING" in payload["svg"]
    assert payload["drawing_intent"]["export_allowed"] is False


def _default_workflow_input() -> dict[str, object]:
    return client.get("/api/workflow/default-demo").json()["input"]


def _drawing_workflow() -> dict[str, object]:
    return client.post("/api/workflow/submittal-to-drawing", json=_default_workflow_input()).json()
