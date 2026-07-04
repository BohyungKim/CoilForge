"""CCSI-vs-CoilForge compare core (Phase 3): reuses the checklist comparator, so a
divergence between the two engines is flagged before the CCSI record is saved."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from coilforge.ccsi.compare import compare_ccsi_fields
from coilforge.web_app import app

client = TestClient(app)


def test_numbers_agree_within_tolerance() -> None:
    # 6.1875 (engine 4dp) vs 6.188 (CCSI 3dp) -> within 0.01" -> match, no false red.
    r = compare_ccsi_fields([{"key": "S", "coilforge": 6.1875, "ccsi": 6.188}])
    assert r["fields"][0]["verdict"] == "match"
    assert r["mismatch_count"] == 0


def test_real_r_divergence_flags_mismatch() -> None:
    # The observed CDXC-1 case: CoilForge R=1.3125 vs CCSI R=3.317 -> must go red.
    r = compare_ccsi_fields([{"key": "R", "coilforge": 1.3125, "ccsi": 3.317}])
    assert r["fields"][0]["verdict"] == "mismatch"
    assert r["mismatch_count"] == 1


def test_ccsi_dom_string_values_are_coerced() -> None:
    # Values read out of the CCSI DOM arrive as strings; they must still compare.
    r = compare_ccsi_fields([{"key": "CD", "coilforge": 7.5, "ccsi": "7.500"}])
    assert r["fields"][0]["verdict"] == "match"


def test_missing_one_and_both_missing() -> None:
    r = compare_ccsi_fields(
        [
            {"key": "O", "coilforge": 2.75, "ccsi": None},
            {"key": "HD", "coilforge": None, "ccsi": None},
        ]
    )
    verdicts = {f["key"]: f["verdict"] for f in r["fields"]}
    assert verdicts["O"] == "missing_one"
    assert verdicts["HD"] == "both_missing"
    assert r["mismatch_count"] == 0  # missing is not a mismatch


def test_empty_input_is_safe() -> None:
    r = compare_ccsi_fields([])
    assert r["compared"] == 0 and r["mismatch_count"] == 0


def test_route_returns_verdicts_and_safety_flags() -> None:
    resp = client.post(
        "/api/ccsi-compare",
        json={
            "fields": [
                {"key": "R", "coilforge": 1.3125, "ccsi": 3.317},
                {"key": "S", "coilforge": 6.1875, "ccsi": 6.188},
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mismatch_count"] == 1
    assert body["compared"] == 2
    # Review aid only — never an export approval.
    assert body["export_allowed"] is False
    assert body["review_aid_only"] is True
    assert body["production_drawing_approval_claimed"] is False
    by_key = {f["key"]: f["verdict"] for f in body["fields"]}
    assert by_key["R"] == "mismatch" and by_key["S"] == "match"


def test_route_empty_body_ok() -> None:
    resp = client.post("/api/ccsi-compare", json={})
    assert resp.status_code == 200
    assert resp.json()["compared"] == 0
