"""Offline CCSI-export audit (`ccsi/export_audit.py`).

The audit reshapes a `run_pdf_to_drawing_workflow` result into the green/red
compare: each coil's engine value (CoilForge side, from the panel) paired with
the printed as-built value (CCSI side, from the drawing) and run through the
shared `compare_ccsi_fields` comparator (tol 0.01). These tests exercise the
reshape + the key->slot bridge on in-memory fixtures (pure — no PDF, no network),
plus the endpoint contract via monkeypatch.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ccsi.export_audit import (  # noqa: E402
    _slot_for_key,
    audit_coil,
    audit_export_result,
)


def _page(tag: str, category: str, params: dict, slot_sources: dict) -> dict:
    """One `pdf_coil_pages` entry: engine params (CoilForge side) + printed
    as-built values keyed by template slot (CCSI side)."""
    return {
        "tag": tag,
        "workflow": {
            "template_header_context": {"coil_category": category},
            "drawing_parameter_set": {
                "parameters": {k: {"value": v} for k, v in params.items()}
            },
            "template_drawing": {
                "slot_sources": {s: {"as_built": v} for s, v in slot_sources.items()}
            },
        },
    }


def _field_map(*keys: str) -> dict:
    return {"version": "test", "fields": {k: {} for k in keys}}


def _verdict(report: dict, key: str) -> str:
    return next(f["verdict"] for f in report["fields"] if f["key"] == key)


# ---- the key -> slot bridge -------------------------------------------------

def test_slot_for_key_bridges_base_and_parity_header_slots() -> None:
    # Base keys via PARAM_TO_SLOT.
    assert _slot_for_key("CD") == "slot.CD"
    assert _slot_for_key("R") == "slot.R2"
    assert _slot_for_key("I") == "slot.I1"
    # Logical header-2+ keys through the parity bridge: I2 -> supply id 3, R2/HD2 ->
    # return id 4 (logical header n == engine circuit n; supply=2n-1, return=2n).
    assert _slot_for_key("I2") == "slot.I3"
    assert _slot_for_key("R2") == "slot.R4"
    assert _slot_for_key("HD2") == "slot.HD4"
    # ZD is the owner constant with no slot (never printed) -> no CCSI side.
    assert _slot_for_key("ZD") is None
    assert _slot_for_key("ZD2") is None


# ---- core compare behaviour -------------------------------------------------

def test_matching_coil_has_zero_mismatches() -> None:
    page = _page(
        "CDXC-1", "DX",
        params={"CD": 6.5, "R": 1.3125},
        slot_sources={"slot.CD": 6.5, "slot.R2": 1.3125},
    )
    report = audit_coil(page, _field_map("CD", "R"))
    assert report["mismatch_count"] == 0
    assert _verdict(report, "CD") == "match"
    assert _verdict(report, "R") == "match"
    assert report["tag"] == "CDXC-1"
    assert report["coil_category"] == "DX"


def test_divergence_flags_red_and_tolerance_holds() -> None:
    # R diverges (CoilForge 1.3125 vs CCSI 3.317 — the live-compare R-family finding);
    # CD agrees within 0.01 (6.1875 vs 6.188) so it stays a match, not a false red.
    page = _page(
        "CDXC-1", "DX",
        params={"CD": 6.1875, "R": 1.3125},
        slot_sources={"slot.CD": 6.188, "slot.R2": 3.317},
    )
    report = audit_coil(page, _field_map("CD", "R"))
    assert report["mismatch_count"] == 1
    assert _verdict(report, "R") == "mismatch"
    assert _verdict(report, "CD") == "match"


def test_missing_as_built_is_missing_one_never_a_false_green() -> None:
    # CoilForge has I but the CCSI drawing did not print it -> missing_one, not match,
    # and not counted as a mismatch.
    page = _page("CDXC-1", "DX", params={"I": 3.0}, slot_sources={})
    report = audit_coil(page, _field_map("I"))
    assert _verdict(report, "I") == "missing_one"
    assert report["mismatch_count"] == 0


def test_multi_coil_returns_one_tagged_report_per_coil() -> None:
    result = {
        "pdf_coil_pages": [
            _page("CDXC-1", "DX", {"CD": 6.5}, {"slot.CD": 6.5}),
            _page("RHHGRC-1", "HGRH", {"CD": 4.0}, {"slot.CD": 9.9}),
        ]
    }
    reports = audit_export_result(result, _field_map("CD"))
    assert [r["tag"] for r in reports] == ["CDXC-1", "RHHGRC-1"]
    assert reports[0]["mismatch_count"] == 0
    assert reports[1]["mismatch_count"] == 1  # 4.0 vs 9.9
    assert reports[1]["coil_category"] == "HGRH"


def test_multi_header_keys_pair_through_parity_slots() -> None:
    # I2 pairs with slot.I3 (match), R2 pairs with slot.R4 (mismatch).
    page = _page(
        "CDXC-1", "DX",
        params={"I2": 3.0, "R2": 3.9375},
        slot_sources={"slot.I3": 3.0, "slot.R4": 5.0},
    )
    report = audit_coil(page, _field_map("I2", "R2"))
    assert _verdict(report, "I2") == "match"
    assert _verdict(report, "R2") == "mismatch"
    assert report["mismatch_count"] == 1


def test_empty_result_yields_no_reports() -> None:
    assert audit_export_result({}, _field_map("CD")) == []
    assert audit_export_result({"pdf_coil_pages": []}, _field_map("CD")) == []


def test_per_coil_report_carries_safety_flags() -> None:
    report = audit_coil(_page("CDXC-1", "DX", {"CD": 6.5}, {"slot.CD": 6.5}), _field_map("CD"))
    assert report["review_aid_only"] is True
    assert report["export_allowed"] is False
    assert report["production_drawing_approval_claimed"] is False


# ---- endpoint contract ------------------------------------------------------

def test_endpoint_returns_per_coil_audit_with_safety_flags(monkeypatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import coilforge.web_app as web_app

    canned = {
        "pdf_coil_pages": [
            _page("CDXC-1", "DX", {"CD": 6.5, "R": 1.3125}, {"slot.CD": 6.5, "slot.R2": 3.317}),
        ]
    }
    monkeypatch.setattr(web_app, "run_pdf_to_drawing_workflow", lambda *a, **k: canned)

    client = TestClient(web_app.app)
    resp = client.post("/api/ccsi/audit-export", content=b"%PDF-fake-bytes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["export_allowed"] is False
    assert body["review_aid_only"] is True
    assert len(body["coils"]) == 1
    coil = body["coils"][0]
    assert coil["tag"] == "CDXC-1"
    assert coil["mismatch_count"] == 1  # R diverges


def test_endpoint_rejects_empty_body() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import coilforge.web_app as web_app

    client = TestClient(web_app.app)
    resp = client.post("/api/ccsi/audit-export", content=b"")
    assert resp.status_code == 400
