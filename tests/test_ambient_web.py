"""Phase 5 — /api/ambient/* route contract (TestClient; parsing monkeypatched).

Avoids committing a customer PDF: the baseline/Ambient parse functions are patched to
return candidates built from the sanitized report text, so the route wiring, safety
flags, cache, kill-switch, and never-raise contract are all exercised.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import coilforge.web_app as web
from coilforge.ambient.pdf_intake import AmbientIntakeResult, _parse_report_page
from tests.test_ambient_pdf_intake import _DX_TEXT


@pytest.fixture
def client():
    web.clear_ambient_cache()
    return TestClient(web.app)


def _dx():
    return _parse_report_page(_DX_TEXT, page_number=1, source_id="B")


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(web, "_baseline_candidates", lambda *a, **k: [_dx()])
    monkeypatch.setattr(
        web, "parse_ambient_pdf",
        lambda *a, **k: AmbientIntakeResult(coils=[_dx()], warnings=[], engine="stub"),
    )


def test_kill_switch_disables_routes(client, monkeypatch):
    monkeypatch.setenv("COILFORGE_AMBIENT", "0")
    r = client.post("/api/ambient/compare", files={"baseline": ("b.pdf", b"x"), "ambient": ("a.pdf", b"y")})
    assert r.status_code == 503


def test_missing_file_is_400(client):
    r = client.post("/api/ambient/compare", files={"baseline": ("b.pdf", b"x")})
    assert r.status_code == 400


def test_happy_path_payload_and_safety_flags(client, patched):
    r = client.post(
        "/api/ambient/compare",
        files={"baseline": ("b.pdf", b"%PDF-1"), "ambient": ("a.pdf", b"%PDF-2")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["export_allowed"] is False
    assert data["production_drawing_approval_claimed"] is False
    assert data["raw_private_data_returned"] is False
    assert data["mismatch_total"] == 0
    assert data["coils"] and data["coils"][0]["tag"] == "CDXC-1"


def test_cache_reuse_is_identical(client, patched):
    files = {"baseline": ("b.pdf", b"%PDF-1"), "ambient": ("a.pdf", b"%PDF-2")}
    a = client.post("/api/ambient/compare", files=files).json()
    b = client.post("/api/ambient/compare", files=files).json()
    assert a == b


def test_garbage_pdf_never_500_crashes(client):
    # Real (un-patched) parse of non-PDF bytes must degrade to a clean 4xx/5xx JSON error,
    # never an unhandled crash.
    r = client.post(
        "/api/ambient/compare",
        files={"baseline": ("b.pdf", b"not a pdf"), "ambient": ("a.pdf", b"also not")},
    )
    assert r.status_code in (400, 500)
    assert "detail" in r.json()


def test_rfq_returns_targets(client, patched):
    r = client.post("/api/ambient/rfq", content=b"%PDF-1", headers={"content-type": "application/pdf"})
    assert r.status_code == 200
    data = r.json()
    assert data["export_allowed"] is False
    assert data["coils"][0]["tag"] == "CDXC-1"
    assert "targets" in data["coils"][0]
