"""Bounded sha1 memoization of the Coil Checklist fill (_run_or_reuse_checklist).

The checklist is auto-filled on analyze, then reused when the deliverable is
finalized. Generating it is the expensive step (an isolated Excel COM process), so
re-running it for the same submittal would double John's wait. These tests assert
the fill is memoized keyed on sha1(pdf_bytes) + product/size overrides, that a
finalize (different source_id, same bytes) REUSES the analyze-time fill (the core
anti-double-work guarantee), and that a deleted Downloads copy regenerates.

Every expensive boundary is mocked (workflow parse, candidate adapter, engine
fill, Excel writer) so the tests exercise ONLY the cache logic — no Excel needed.
"""
from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge import web_app


@pytest.fixture(autouse=True)
def _clean_cache():
    """Every test starts and ends with an empty checklist cache (no bleed)."""
    web_app.clear_checklist_cache()
    yield
    web_app.clear_checklist_cache()


def _stub_pipeline(monkeypatch, tmp_path, *, coils=("coil",), writer=None):
    """Mock the whole fill pipeline except the cache. Returns the write-call
    counter list so a test can assert how many times Excel would have run."""
    monkeypatch.setattr(
        web_app, "run_pdf_to_drawing_workflow",
        lambda *a, **k: {"candidates": ["candidate"]},
    )
    monkeypatch.setattr(
        web_app, "coil_inputs_from_candidates",
        lambda *a, **k: (list(coils), {}),
    )
    monkeypatch.setattr(
        web_app, "build_checklist_fill",
        lambda coils, overrides=None: types.SimpleNamespace(sheets=[], warnings=[]),
    )
    calls = [0]

    def _default_writer(fill, *, dest_name=None, **kwargs):
        calls[0] += 1
        path = tmp_path / (dest_name or "checklist.xlsx")
        path.write_text("stub", encoding="utf-8")
        return {"saved_path": str(path), "sheets": []}

    monkeypatch.setattr(web_app, "write_checklist", writer or _default_writer)
    return calls


def _run(pdf, **kwargs):
    return asyncio.run(web_app._run_or_reuse_checklist(pdf, **kwargs))


def test_same_pdf_reuses_and_writes_once(monkeypatch, tmp_path) -> None:
    calls = _stub_pipeline(monkeypatch, tmp_path)
    pdf = b"%PDF-sample-A"

    first = _run(pdf, filename="a.pdf")
    second = _run(pdf, filename="a.pdf")

    assert calls[0] == 1  # second call is a cache HIT — Excel ran exactly once
    assert first.review is not None and second.review is not None
    assert first.saved_path == second.saved_path
    assert first.review["export_allowed"] is False  # invariant preserved
    # Fresh fill journals; reuse does not (workflow_result only on generation).
    assert first.workflow_result is not None
    assert second.workflow_result is None
    # Cache returns deepcopies, never the same object.
    assert first.review is not second.review


def test_finalize_reuses_analyze_fill_despite_source_id(monkeypatch, tmp_path) -> None:
    """The core anti-double-work guarantee: analyze fills under one source_id, a
    later finalize with a DIFFERENT source_id + same bytes reuses it (no 2nd Excel)."""
    calls = _stub_pipeline(monkeypatch, tmp_path)
    pdf = b"%PDF-sample-B"

    analyze = _run(pdf, filename="sub.pdf", source_id="CHECKLIST-FILL-001")
    finalize = _run(pdf, filename="sub.pdf", source_id="DELIVERABLE-FINALIZE-001")

    assert calls[0] == 1
    assert analyze.saved_path == finalize.saved_path


def test_deleted_downloads_copy_regenerates(monkeypatch, tmp_path) -> None:
    calls = _stub_pipeline(monkeypatch, tmp_path)
    pdf = b"%PDF-sample-C"

    first = _run(pdf, filename="c.pdf")
    Path(first.saved_path).unlink()  # John cleared the file from Downloads
    second = _run(pdf, filename="c.pdf")

    assert calls[0] == 2  # stale entry dropped -> a fresh write
    assert Path(second.saved_path).exists()


def test_product_override_is_a_distinct_entry(monkeypatch, tmp_path) -> None:
    calls = _stub_pipeline(monkeypatch, tmp_path)
    pdf = b"%PDF-sample-D"

    _run(pdf, filename="d.pdf")
    _run(pdf, filename="d.pdf", product="NOVA")

    assert calls[0] == 2  # a product override changes the sheet -> separate key


def test_cover_page_hint_is_a_distinct_entry(monkeypatch, tmp_path) -> None:
    """Reselecting the cover page on the SAME bytes must not serve the stale fill
    computed under the previous selection (mirrors _WORKFLOW_CACHE's key)."""
    calls = _stub_pipeline(monkeypatch, tmp_path)
    pdf = b"%PDF-sample-H"

    _run(pdf, filename="h.pdf", cover_page_hint=3)
    _run(pdf, filename="h.pdf", cover_page_hint=5)

    assert calls[0] == 2  # different cover page => different key => regenerated


def _overrides(tag="CDXC-1", value=1.25):
    return [{"tag": tag, "engine_inputs": {},
             "param_overrides": [{"key": "TF", "value": value, "override_reason": "r"}]}]


def test_manual_override_is_a_distinct_entry(monkeypatch, tmp_path) -> None:
    """The bug this feature fixes: after a manual correction the SAME PDF must not serve
    the pre-override sheet back."""
    calls = _stub_pipeline(monkeypatch, tmp_path)
    pdf = b"%PDF-sample-J"

    _run(pdf, filename="j.pdf")
    _run(pdf, filename="j.pdf", coil_overrides=_overrides())
    _run(pdf, filename="j.pdf", coil_overrides=_overrides(value=2.5))

    assert calls[0] == 3  # no override / TF=1.25 / TF=2.5 are three different sheets


def test_same_overrides_still_reuse_one_fill(monkeypatch, tmp_path) -> None:
    """The fingerprint is order-independent, so the analyze-time fill and the finalize
    passing the same overrides share ONE Excel run (no double COM)."""
    calls = _stub_pipeline(monkeypatch, tmp_path)
    pdf = b"%PDF-sample-K"
    payload = [
        {"tag": "CDXC-1", "engine_inputs": {"rows": 6},
         "param_overrides": [{"key": "TF", "value": 1.25}]},
        {"tag": "RHHGRC-1", "engine_inputs": {}, "param_overrides": [{"key": "CD", "value": 3.0}]},
    ]
    analyze = _run(pdf, filename="k.pdf", coil_overrides=payload)
    finalize = _run(pdf, filename="k.pdf", coil_overrides=list(reversed(payload)),
                    source_id="DELIVERABLE-FINALIZE-001")

    assert calls[0] == 1
    assert analyze.saved_path == finalize.saved_path


def test_empty_override_payload_keys_like_no_override(monkeypatch, tmp_path) -> None:
    """An empty list must NOT split the cache — the plain analyze path is unchanged."""
    calls = _stub_pipeline(monkeypatch, tmp_path)
    pdf = b"%PDF-sample-L"

    _run(pdf, filename="l.pdf")
    _run(pdf, filename="l.pdf", coil_overrides=[])
    _run(pdf, filename="l.pdf", coil_overrides=[{"tag": "CDXC-1"}])  # nothing filled

    assert calls[0] == 1


def test_overwritten_copy_evicts_the_entry_that_pointed_at_it(monkeypatch, tmp_path) -> None:
    """A refill now REPLACES the previous .xlsx, so the older entry describes a file whose
    content has just been overwritten — reusing its saved_path would file the wrong
    workbook (finalize with no overrides picking up the override refill's file)."""
    calls = _stub_pipeline(monkeypatch, tmp_path)
    pdf = b"%PDF-sample-M"

    baseline = _run(pdf, filename="m.xlsx")
    override = _run(pdf, filename="m.xlsx", coil_overrides=_overrides())
    assert baseline.saved_path == override.saved_path  # same file, overwritten
    assert calls[0] == 2

    # The baseline key must NOT serve the (now overwritten) path back from cache.
    again = _run(pdf, filename="m.xlsx")
    assert calls[0] == 3  # regenerated instead of handing back the override's file


# --- the route's two body forms --------------------------------------------
def _capture_route_call(monkeypatch):
    """Replace the fill helper so a route test asserts what the ROUTE parsed and passed
    on, without touching the workflow/Excel machinery underneath it."""
    seen: dict = {}

    async def _fake(pdf_bytes, **kwargs):
        seen["pdf_bytes"] = pdf_bytes
        seen.update(kwargs)
        return web_app._ChecklistOutcome({"sheets": [], "export_allowed": False}, None, None, None)

    monkeypatch.setattr(web_app, "_run_or_reuse_checklist", _fake)
    return seen


def test_route_accepts_raw_pdf_body(monkeypatch) -> None:
    """The original contract, unchanged: raw bytes in, no overrides."""
    from fastapi.testclient import TestClient

    seen = _capture_route_call(monkeypatch)
    client = TestClient(web_app.app)
    res = client.post("/api/checklist/fill", content=b"%PDF-raw",
                      headers={"Content-Type": "application/pdf"})

    assert res.status_code == 200
    assert seen["pdf_bytes"] == b"%PDF-raw"
    assert seen["coil_overrides"] is None


def test_route_accepts_json_body_with_overrides(monkeypatch) -> None:
    import base64

    from fastapi.testclient import TestClient

    seen = _capture_route_call(monkeypatch)
    client = TestClient(web_app.app)
    overrides = [{"tag": "CDXC-1", "engine_inputs": {"rows": 6},
                  "param_overrides": [{"key": "TF", "value": 1.25}], "reason": "why"}]
    res = client.post("/api/checklist/fill", json={
        "submittal_pdf_base64": base64.b64encode(b"%PDF-json").decode(),
        "coil_overrides": overrides,
    })

    assert res.status_code == 200
    assert seen["pdf_bytes"] == b"%PDF-json"   # base64 round-trips to the same bytes
    assert seen["coil_overrides"] == overrides


def test_never_raises_on_workflow_failure(monkeypatch, tmp_path) -> None:
    """A non-ValueError parse hiccup must degrade to an outcome, never propagate —
    so it can't abort a whole finalize / project-review request."""
    _stub_pipeline(monkeypatch, tmp_path)
    monkeypatch.setattr(
        web_app, "run_pdf_to_drawing_workflow",
        lambda *a, **k: (_ for _ in ()).throw(KeyError("boom")),
    )

    outcome = _run(b"%PDF-sample-I", filename="i.pdf")

    assert outcome.review is None
    assert outcome.http_status == 500


def test_no_recognizable_coils_returns_400_reason(monkeypatch, tmp_path) -> None:
    calls = _stub_pipeline(monkeypatch, tmp_path, coils=())
    pdf = b"%PDF-sample-E"

    outcome = _run(pdf, filename="e.pdf")

    assert outcome.review is None
    assert outcome.http_status == 400
    assert "No recognizable coils" in (outcome.reason or "")
    assert calls[0] == 0  # never reached the Excel write


def test_excel_unavailable_returns_501(monkeypatch, tmp_path) -> None:
    def _raises(fill, *, dest_name=None, **kwargs):
        raise RuntimeError("pywin32/Excel unavailable")

    _stub_pipeline(monkeypatch, tmp_path, writer=_raises)
    pdf = b"%PDF-sample-F"

    outcome = _run(pdf, filename="f.pdf")

    assert outcome.review is None
    assert outcome.http_status == 501


def test_empty_bytes_returns_400(monkeypatch, tmp_path) -> None:
    _stub_pipeline(monkeypatch, tmp_path)

    outcome = _run(b"")

    assert outcome.review is None
    assert outcome.http_status == 400


def test_cache_is_bounded(monkeypatch, tmp_path) -> None:
    _stub_pipeline(monkeypatch, tmp_path)
    pdf = b"%PDF-sample-G"
    overflow = web_app._CHECKLIST_CACHE_MAXSIZE + 5
    # Distinct product overrides => distinct keys; exceed the bound and confirm cap.
    for i in range(overflow):
        _run(pdf, filename="g.pdf", product=f"P{i}")
    assert len(web_app._CHECKLIST_CACHE) <= web_app._CHECKLIST_CACHE_MAXSIZE


# ---------------------------------------------------------------------------
# Known-divergence annotation (Phase D) rides on BOTH cache paths.
#
# The checklist result is memoized by PDF bytes, so a ruling John records in the browser
# would never appear if annotation only ran on a fresh fill — he would re-analyze, hit the
# cache, and see his own decision do nothing.
# ---------------------------------------------------------------------------
_TERRA_V_COIL = {
    "tag": "RHHGRC-1", "coil_type": "HGRH", "product_label": "TERRA V", "unit_size": "072",
}


def _stub_review_with_cd_mismatch(monkeypatch):
    """A one-row review whose CD disagrees — the shape KD-001 rules on."""
    monkeypatch.setattr(
        web_app, "build_review",
        lambda fill, writer_result: {
            "saved_path": writer_result.get("saved_path"),
            "sheets": [{
                "tag": "RHHGRC-1", "category": "HGRH", "inputs": [],
                "comparisons": [{
                    "label": "CD", "slot": "slot.CD", "coilforge": 7.5,
                    "checklist": 6.0, "verdict": "mismatch", "override": None,
                }],
                "mismatch_count": 1, "override_count": 0,
            }],
            "warnings": [], "mismatch_total": 1, "override_total": 0,
            "export_allowed": False, "production_drawing_approval_claimed": False,
        },
    )


def test_a_ruling_annotates_on_the_fresh_fill(monkeypatch, tmp_path) -> None:
    _stub_pipeline(monkeypatch, tmp_path, coils=(_TERRA_V_COIL,))
    _stub_review_with_cd_mismatch(monkeypatch)

    outcome = _run(b"%PDF-divergence-A", filename="a.pdf")

    row = outcome.review["sheets"][0]["comparisons"][0]
    assert row["divergence"]["id"] == "KD-001"
    assert row["divergence"]["severity"] == "known_gap"


def test_a_ruling_also_annotates_on_a_cache_hit(monkeypatch, tmp_path) -> None:
    calls = _stub_pipeline(monkeypatch, tmp_path, coils=(_TERRA_V_COIL,))
    _stub_review_with_cd_mismatch(monkeypatch)
    pdf = b"%PDF-divergence-B"

    _run(pdf, filename="b.pdf")
    hit = _run(pdf, filename="b.pdf")

    assert calls[0] == 1, "still one Excel run — annotation must not defeat the cache"
    assert hit.review["sheets"][0]["comparisons"][0]["divergence"]["id"] == "KD-001"


def test_the_cached_original_stays_un_annotated_so_a_later_ruling_appears(
    monkeypatch, tmp_path
) -> None:
    """Bake the annotation into the cache and a NEW ruling is invisible until the entry
    expires — the engineer would record a decision and watch it do nothing."""
    from coilforge.review import divergence

    _stub_pipeline(monkeypatch, tmp_path, coils=(_TERRA_V_COIL,))
    monkeypatch.setattr(
        web_app, "build_review",
        lambda fill, writer_result: {
            "saved_path": writer_result.get("saved_path"),
            "sheets": [{
                "tag": "RHHGRC-1", "category": "HGRH", "inputs": [],
                "comparisons": [{
                    "label": "S5", "slot": "slot.S5", "coilforge": 1.5,
                    "checklist": 3.0, "verdict": "mismatch", "override": None,
                }],
                "mismatch_count": 1, "override_count": 0,
            }],
            "warnings": [], "mismatch_total": 1, "override_total": 0,
            "export_allowed": False, "production_drawing_approval_claimed": False,
        },
    )
    staging = tmp_path / "staging.yaml"
    monkeypatch.setattr(divergence, "_STAGING_PATH", staging)
    pdf = b"%PDF-divergence-C"

    first = _run(pdf, filename="c.pdf")
    assert "divergence" not in first.review["sheets"][0]["comparisons"][0]

    # John rules on it between the two renders.
    from coilforge.review.adjudicate import record_adjudication
    monkeypatch.setenv("COILFORGE_CAPTURE", "0")  # ledger is not what this test is about
    record_adjudication(
        {
            "coil_category": "HGRH", "product_family": "TERRA_V",
            "terra_variant": "TERRA_V", "unit_size_scope": "*", "slot": "slot.S5",
            "verdict": "both_defensible", "reason": "two valid spacing conventions",
        },
        staging_path=staging,
    )

    hit = _run(pdf, filename="c.pdf")
    assert hit.review["sheets"][0]["comparisons"][0]["divergence"]["applies"] is True, (
        "a ruling must change the very next render, cache hit or not"
    )
