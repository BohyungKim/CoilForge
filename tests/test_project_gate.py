"""Constant-time project review gate (`review/project_gate.py`).

The gate collapses per-coil review into an exceptions-only rollup by triangulating
three independent computations of each dimension (engine / checklist / CCSI). These
tests pin the two-comparisons-two-meanings rule and — critically — that the human
review load K stays independent of coil count on a clean project.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.review.project_gate import (  # noqa: E402
    _base,
    build_project_gate,
)


def _page(tag: str, params: dict, *, template_drawing: dict | None = None) -> dict:
    """A coil page carrying its engine panel + template drawing. Defaults to a coil
    that produced a drawing (non-empty svg) so it isn't flagged for a missing drawing;
    pass ``template_drawing`` to model an un-drawn coil."""
    return {
        "tag": tag,
        "workflow": {
            "drawing_parameter_set": {
                "parameters": {k: (v if isinstance(v, dict) else {"value": v}) for k, v in params.items()}
            },
            "template_drawing": template_drawing if template_drawing is not None else {"svg": "<svg/>"},
        },
    }


def _clean_coil(tag: str) -> dict:
    return _page(tag, {"CD": 6.5, "I": 3.0, "S": 2.75, "O": 3.25, "R": 1.3125})


def _checklist(tag: str, comparisons: list[dict]) -> dict:
    return {"sheets": [{"tag": tag, "comparisons": comparisons}]}


def _audit(tag: str, fields: list[dict]) -> list[dict]:
    return [{"tag": tag, "fields": fields}]


def _verdict(gate: dict, tag: str) -> str:
    return next(c["verdict"] for c in gate["coils"] if c["tag"] == tag)


# ---- the base helper --------------------------------------------------------

def test_base_strips_header_index() -> None:
    assert _base("R2") == "R"
    assert _base("HD") == "HD"
    assert _base("HDx1") == "HDx"
    assert _base("CD") == "CD"


# ---- classification ---------------------------------------------------------

def test_clean_coil_passes_and_contributes_zero_to_k() -> None:
    result = {"pdf_coil_pages": [_clean_coil("CDXC-1")]}
    gate = build_project_gate(result)
    assert _verdict(gate, "CDXC-1") == "pass"
    assert gate["summary"]["exceptions_K"] == 0


def test_engine_vs_checklist_mismatch_is_an_exception() -> None:
    result = {"pdf_coil_pages": [_clean_coil("CDXC-1")]}
    review = _checklist("CDXC-1", [
        {"label": "CD", "coilforge": 6.5, "checklist": 6.5, "verdict": "match"},
        {"label": "S", "coilforge": 2.75, "checklist": 3.10, "verdict": "mismatch"},
    ])
    gate = build_project_gate(result, checklist_review=review)
    assert _verdict(gate, "CDXC-1") == "exception"
    assert gate["summary"]["exceptions_K"] == 1
    coil = gate["coils"][0]
    assert coil["exceptions"][0]["key"] == "S"
    assert coil["exceptions"][0]["reason"] == "engine_vs_checklist"


def test_engine_vs_ccsi_mismatch_is_an_acknowledged_override_not_an_exception() -> None:
    result = {"pdf_coil_pages": [_clean_coil("CDXC-1")]}
    # R diverges from CCSI — the known-accepted return-spacing override.
    audit = _audit("CDXC-1", [
        {"key": "CD", "coilforge": 6.5, "ccsi": 6.5, "verdict": "match"},
        {"key": "R", "coilforge": 1.3125, "ccsi": 3.317, "verdict": "mismatch"},
    ])
    gate = build_project_gate(result, audit_reports=audit)
    assert _verdict(gate, "CDXC-1") == "override"
    assert gate["summary"]["exceptions_K"] == 0  # override never inflates K
    ov = gate["coils"][0]["overrides"][0]
    assert ov["key"] == "R" and ov["acknowledged"] is True


def test_coil_without_a_drawing_is_an_exception() -> None:
    # We ship CoilForge's own drawing, so a coil with no generated drawing must be flagged.
    page = _page("CDXC-1", {"CD": 6.5}, template_drawing={"svg": "", "template_found": False})
    gate = build_project_gate({"pdf_coil_pages": [page]})
    assert _verdict(gate, "CDXC-1") == "exception"
    exc = [e for e in gate["coils"][0]["exceptions"] if e["reason"] == "no_drawing"]
    assert exc and "template" in exc[0]["detail"].lower()


def test_blocked_engine_value_is_an_exception() -> None:
    page = _page("CDXC-1", {
        "CD": 6.5,
        "R": {"value": None, "blocked_reason": "Needs the return connection size."},
    })
    gate = build_project_gate({"pdf_coil_pages": [page]})
    assert _verdict(gate, "CDXC-1") == "exception"
    exc = gate["coils"][0]["exceptions"][0]
    assert exc["key"] == "R" and exc["reason"] == "blocked"


def test_k_is_independent_of_coil_count() -> None:
    small = {"pdf_coil_pages": [_clean_coil(f"CDXC-{i}") for i in range(10)]}
    big = {"pdf_coil_pages": [_clean_coil(f"CDXC-{i}") for i in range(50)]}
    assert build_project_gate(small)["summary"]["exceptions_K"] == 0
    assert build_project_gate(big)["summary"]["exceptions_K"] == 0
    # 50 clean coils cost John the same review (zero) as 10 — the whole point.
    assert build_project_gate(big)["summary"]["coils"] == 50


def test_sources_flags_reflect_what_was_supplied() -> None:
    result = {"pdf_coil_pages": [_clean_coil("CDXC-1")]}
    engine_only = build_project_gate(result)["summary"]["sources"]
    assert engine_only == {"engine": True, "checklist": False, "ccsi": False}
    full = build_project_gate(
        result,
        checklist_review=_checklist("CDXC-1", []),
        audit_reports=_audit("CDXC-1", []),
    )["summary"]["sources"]
    assert full == {"engine": True, "checklist": True, "ccsi": True}


def test_common_exception_key_surfaced_once_across_all_coils() -> None:
    # Same key blocked on every coil = one structural finding, not N.
    pages = [
        _page(f"CDXC-{i}", {"CD": 6.5, "S": {"value": None}})
        for i in range(4)
    ]
    gate = build_project_gate({"pdf_coil_pages": pages})
    assert gate["summary"]["common_exception_keys"] == ["S"]
    assert gate["summary"]["exceptions_K"] == 4


def test_safety_flags_present() -> None:
    gate = build_project_gate({"pdf_coil_pages": [_clean_coil("CDXC-1")]})
    assert gate["review_aid_only"] is True
    assert gate["export_allowed"] is False
    assert gate["production_drawing_approval_claimed"] is False


# ---- endpoint contract ------------------------------------------------------

def test_endpoint_returns_engine_only_gate(monkeypatch) -> None:
    import pytest

    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import coilforge.web_app as web_app

    canned = {"pdf_coil_pages": [
        _clean_coil("CDXC-1"),
        _page("CDXC-2", {"CD": 6.5, "R": {"value": None, "blocked_reason": "no conn size"}}),
    ]}
    monkeypatch.setattr(web_app, "run_pdf_to_drawing_workflow", lambda *a, **k: canned)

    client = TestClient(web_app.app)
    resp = client.post("/api/review/project", content=b"%PDF-fake")
    assert resp.status_code == 200
    body = resp.json()
    assert body["export_allowed"] is False
    assert body["summary"]["coils"] == 2
    assert body["summary"]["exceptions_K"] == 1  # only CDXC-2 needs eyes
    assert body["summary"]["sources"]["checklist"] is False


def test_endpoint_rejects_empty_body() -> None:
    import pytest

    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import coilforge.web_app as web_app

    client = TestClient(web_app.app)
    resp = client.post("/api/review/project", content=b"")
    assert resp.status_code == 400
