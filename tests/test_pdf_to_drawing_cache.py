"""R12b: bounded sha1 memoization of run_pdf_to_drawing_workflow.

The case deep-link / re-analyze flows re-run the SAME submittal PDF repeatedly,
paying 30-60s of OCR/analysis each time. These tests assert the workflow is
memoized (a repeat call is a cache HIT that skips the expensive intake) AND that
the cache key includes every argument (same bytes + different source_id must NOT
cross-contaminate).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.workflows import submittal_to_drawing as workflow_mod
from coilforge.workflows import run_pdf_to_drawing_workflow


def _make_text_pdf(lines: list[str]) -> bytes:
    text_ops = ["BT", "/F1 12 Tf", "72 720 Td"]
    first = True
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if not first:
            text_ops.append("0 -16 Td")
        text_ops.append(f"({safe}) Tj")
        first = False
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("latin-1")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        (
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        ),
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(stream)} >> stream\n".encode("ascii")
        + stream
        + b"\nendstream endobj\n",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj
    xref_pos = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode("ascii")
    pdf += (
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    return pdf


def _sample_pdf_bytes() -> bytes:
    return _make_text_pdf(
        [
            "Tag CDXC-1",
            "Coil Quantity 2",
            "Handing Left",
            "Rows Deep 5",
            "Fins Per Inch 10",
            "Finned Height 18 in",
            "Finned Length 36 in",
            "Number Of Feeds 9",
            "Connection Type Sweat",
            "CD 6.375",
            "CH 19.25",
        ]
    )


@pytest.fixture(autouse=True)
def _clean_cache():
    """Every test starts and ends with an empty workflow cache (no cross-test bleed)."""
    workflow_mod.clear_pdf_to_drawing_workflow_cache()
    yield
    workflow_mod.clear_pdf_to_drawing_workflow_cache()


def _count_intake(monkeypatch) -> list[int]:
    """Wrap the expensive intake call with a counter, delegating to the real impl."""
    calls = [0]
    real = workflow_mod.extract_coil_candidate_from_pdf_bytes

    def _counting(*args, **kwargs):
        calls[0] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(
        workflow_mod, "extract_coil_candidate_from_pdf_bytes", _counting
    )
    return calls


def _embedded_source_id(result: dict) -> str:
    """The source_id stamped into the result's provenance (pdf_intake_summary).

    A bytes-only cache key would hand a second caller the FIRST caller's payload,
    so this embedded id would read SRC-A for a SRC-B request — exactly the silent
    cross-contamination the cache key must prevent.
    """
    return result["pdf_intake_summary"]["source_id"]


def test_identical_input_runs_analysis_once(monkeypatch) -> None:
    calls = _count_intake(monkeypatch)
    pdf = _sample_pdf_bytes()

    first = run_pdf_to_drawing_workflow(pdf, source_id="SRC-A")
    second = run_pdf_to_drawing_workflow(pdf, source_id="SRC-A")

    # Second call is a cache HIT: the expensive intake ran exactly once.
    assert calls[0] == 1
    # Same logical result on the hit...
    assert first["svg"] == second["svg"]
    # ...but never the same object (callers mutate the result in place).
    assert first is not second
    assert first["validation"] is not second["validation"]


def test_same_bytes_different_source_id_do_not_cross_contaminate(monkeypatch) -> None:
    calls = _count_intake(monkeypatch)
    pdf = _sample_pdf_bytes()

    result_a = run_pdf_to_drawing_workflow(pdf, source_id="SRC-A")
    result_b = run_pdf_to_drawing_workflow(pdf, source_id="SRC-B")

    # Different source_id => different cache key => both analyzed (no stale hit).
    assert calls[0] == 2
    # Each result carries its OWN source_id (embedded in every field's
    # source_evidence) — a bytes-only cache key would have handed result_b the
    # SRC-A payload (silent cross-contamination).
    assert _embedded_source_id(result_a) == "SRC-A"
    assert _embedded_source_id(result_b) == "SRC-B"


def test_cache_hit_mutation_does_not_poison_stored_result(monkeypatch) -> None:
    _count_intake(monkeypatch)
    pdf = _sample_pdf_bytes()

    first = run_pdf_to_drawing_workflow(pdf, source_id="SRC-A")
    # Emulate web_app.py::workflow_case_to_drawing mutating the returned dict.
    first["brain_case"] = {"case_id": "SHOULD-NOT-LEAK"}

    second = run_pdf_to_drawing_workflow(pdf, source_id="SRC-A")
    # The mutation on the first copy must not leak into the cached result.
    assert "brain_case" not in second


def test_cache_is_bounded(monkeypatch) -> None:
    _count_intake(monkeypatch)
    # Distinct source_ids => distinct keys; exceed the bound and confirm it caps.
    overflow = workflow_mod._WORKFLOW_CACHE_MAXSIZE + 5
    pdf = _sample_pdf_bytes()
    for i in range(overflow):
        run_pdf_to_drawing_workflow(pdf, source_id=f"SRC-{i}")
    assert len(workflow_mod._WORKFLOW_CACHE) <= workflow_mod._WORKFLOW_CACHE_MAXSIZE
