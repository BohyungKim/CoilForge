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
        lambda coils: types.SimpleNamespace(sheets=[], warnings=[]),
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
