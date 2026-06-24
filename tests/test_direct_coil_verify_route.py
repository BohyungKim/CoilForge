"""/api/direct-coil/verify wiring: route -> candidate adapter -> comparator.

Exercises the full request path (page_text parse + candidate -> canonical record ->
diff) without needing a PDF, using the sanitized default submittal candidate as the
CoilForge side. Confirms the route shape, the 400 on missing inputs, and that the
safety flags survive the round trip.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from coilforge.submittal import load_submittal_candidate_fixture  # noqa: E402
from coilforge.web_app import app  # noqa: E402

client = TestClient(app)

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "sanitized"
    / "submittal_candidate_dx_header1_default.json"
)


def _candidate_dict() -> dict:
    return load_submittal_candidate_fixture(_FIXTURE).model_dump(mode="json")


def test_verify_route_returns_report_with_safety_flags() -> None:
    candidate = _candidate_dict()
    response = client.post(
        "/api/direct-coil/verify",
        json={"entered": {"coil_hand": "Left"}, "candidate": candidate},
    )
    assert response.status_code == 200
    report = response.json()
    assert "discrepancies" in report
    assert report["export_allowed"] is False
    assert report["production_drawing_approval_claimed"] is False
    assert report["raw_private_data_returned"] is False
    assert report["fields_expected"] > 0


def test_verify_route_parses_page_text() -> None:
    candidate = _candidate_dict()
    response = client.post(
        "/api/direct-coil/verify",
        json={"page_text": "Coil Hand: Left\nRows Deep: 4\n", "candidate": candidate},
    )
    assert response.status_code == 200
    report = response.json()
    # Something was read off the page and compared (matched, mismatched, or flagged).
    assert report["fields_read"] >= 1


def test_verify_route_requires_an_entry_source() -> None:
    response = client.post("/api/direct-coil/verify", json={"candidate": _candidate_dict()})
    assert response.status_code == 400


def test_verify_route_requires_a_coilforge_source() -> None:
    response = client.post("/api/direct-coil/verify", json={"entered": {"coil_hand": "Left"}})
    assert response.status_code == 400
