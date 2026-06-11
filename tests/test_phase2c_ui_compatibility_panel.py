from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from coilforge.web_app import app


client = TestClient(app)


def test_compatibility_review_api_returns_report_registry_and_plan() -> None:
    response = client.get("/api/compatibility/default-review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["case_id"] == "SCC-SANITIZED-DX-H1-001__EZC-0001"
    assert payload["report"]["mismatch_field_keys"] == []
    assert payload["registry"]["summary"]["both_sources"] == 8
    assert payload["reconciliation_plan"]["policy_status"] == "review_required_no_auto_merge"
    assert payload["reconciliation_plan"]["export_allowed"] is False


def test_web_shell_includes_compatibility_review_panel() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "Compatibility Review" in response.text
    assert 'data-tab="compatibility"' in response.text
    assert 'data-compat-filter="held"' in response.text


def test_static_app_loads_compatibility_review_endpoint() -> None:
    app_js = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(
        encoding="utf-8"
    )

    assert "/api/compatibility/default-review" in app_js
    assert "renderCompatibilityReview" in app_js
    assert "use_matched_candidate_for_review" in app_js
