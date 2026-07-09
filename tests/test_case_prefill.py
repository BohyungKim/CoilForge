"""PO Release board case prefill (?case= deep link).

POST /api/workflow/case-to-drawing resolves a Brain case's staged submittal
PDF (read-only, direct file read via brain_case.py) and runs the standard
pdf-to-drawing workflow on it; GET /api/case/{id}/submittal-pdf returns the
raw bytes so the frontend can restore its File object. All tests point the
cases/intake/journal env vars at tmp dirs — the real Brain board and journal
must never be touched by the suite.
"""

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from coilforge import brain_case
from coilforge.web_app import app

client = TestClient(app)


# --------------------------------------------------------------------------- #
# Fixtures: a tmp Brain board (cases/ + intake/) and a tmp journal dir.
# --------------------------------------------------------------------------- #

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
    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = []
    for obj in objects:
        offsets.append(output.tell())
        output.write(obj)
    xref_offset = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return output.getvalue()


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
            "Tube Material Copper",
            "Fin Material Aluminum 0.008",
            "Fin Surface Flat",
            "Header Material Copper",
            "Connection Material Copper",
            "Connection Type Sweat",
            'Return Connection Size 7/8"',
            "Casing Material Galvanized Steel",
            "Casing Style Standard",
            "Total Air Flow 2200 cfm",
            "Entering Dry Bulb 80 F",
            "Refrigerant R410A",
            "Evaporating Temperature 45 F",
            "Liquid Temperature 105 F",
            "Superheat 9 F",
            "DXDistCapillarySize 1/4 x 0.025",
            "CD 6.375",
            "BF 0.625",
            "TF 0.625",
            "CH 19.25",
        ]
    )


def _case_json(intake_path: Path | None, file_name: str = "sub.pdf") -> dict:
    events = []
    if file_name:
        events.append({
            "field": "intake_requested",
            "ts": "2026-07-08T14:56:11+00:00",
            "value": {
                "file_name": file_name,
                "intake_path": str(intake_path) if intake_path else "",
            },
        })
    events.append({
        "field": "coil_requirement",
        "ts": "2026-07-09T04:26:43+00:00",
        "value": {
            "coils": [{"tag": "CDXC-1", "qty": 2, "category": "DX COIL"}],
            "source_file": file_name,
        },
    })
    return {
        "case_id": "PRC-2819",
        "identity": {
            "project_number": "2819",
            "project_name": "New Caney MUD Office",
        },
        "events": events,
    }


@pytest.fixture()
def brain_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """tmp PO Release board: cases/ + intake/ + isolated journal dir."""
    cases = tmp_path / "cases"
    intake = tmp_path / "intake"
    (intake / "processed").mkdir(parents=True)
    cases.mkdir()
    monkeypatch.setenv("PO_RELEASE_CASE_CASES_DIR", str(cases))
    # Isolate journaling: the injected Brain identity would otherwise make the
    # workflow write a coil_milestone line into the REAL Brain journal.
    monkeypatch.setenv("PO_RELEASE_CASE_JOURNAL_DIR", str(tmp_path / "journal"))
    return tmp_path


def _write_case(root: Path, case: dict) -> None:
    (root / "cases" / "PRC-2819.json").write_text(
        json.dumps(case), encoding="utf-8")


# --------------------------------------------------------------------------- #
# POST /api/workflow/case-to-drawing
# --------------------------------------------------------------------------- #

def test_case_to_drawing_prefills_and_injects_brain_identity(brain_board: Path) -> None:
    pdf_path = brain_board / "intake" / "sub.pdf"
    pdf_path.write_bytes(_sample_pdf_bytes())
    _write_case(brain_board, _case_json(pdf_path))

    response = client.post("/api/workflow/case-to-drawing",
                           json={"case_id": "PRC-2819"})

    assert response.status_code == 200
    payload = response.json()
    # Same shape as /api/workflow/pdf-to-drawing ...
    assert payload["candidates"]
    assert payload["pdf_coil_pages"]
    summary = payload["pdf_intake_summary"]
    # ... but the Brain identity is authoritative (the tiny PDF carries none).
    assert summary["project_number"] == "2819"
    assert summary["project_name"] == "New Caney MUD Office"
    assert summary["project_context_source"] == "po_release_case_board"
    assert summary["source_filename"] == "sub.pdf"
    brain_block = payload["brain_case"]
    assert brain_block["case_id"] == "PRC-2819"
    assert brain_block["label"] == "2819 - New Caney MUD Office"
    assert brain_block["expected_coils"] == [
        {"tag": "CDXC-1", "qty": 2, "category": "DX COIL"}]

    journal_files = list((brain_board / "journal").glob("coil-*.jsonl"))
    assert len(journal_files) == 1
    event = json.loads(journal_files[0].read_text(encoding="utf-8").splitlines()[0])
    assert event["identity"]["project_number"] == "2819"
    assert event["value"]["milestone"] == "intake_drawing"
    assert event["value"]["brain_case_id"] == "PRC-2819"


def test_case_to_drawing_falls_back_to_processed_dir(brain_board: Path) -> None:
    # Staged PDFs move to intake\processed\ after extraction; the journaled
    # intake_path goes stale, so the processed fallback is load-bearing.
    stale_path = brain_board / "intake" / "sub.pdf"  # never written
    (brain_board / "intake" / "processed" / "sub.pdf").write_bytes(_sample_pdf_bytes())
    _write_case(brain_board, _case_json(stale_path))

    response = client.post("/api/workflow/case-to-drawing",
                           json={"case_id": "PRC-2819"})

    assert response.status_code == 200
    assert response.json()["brain_case"]["source_filename"] == "sub.pdf"


def test_case_to_drawing_unknown_case_is_404(brain_board: Path) -> None:
    response = client.post("/api/workflow/case-to-drawing",
                           json={"case_id": "PRC-9999"})
    assert response.status_code == 404
    assert "PRC-9999" in response.json()["detail"]


def test_case_to_drawing_without_staged_pdf_is_409(brain_board: Path) -> None:
    case = _case_json(None, file_name="")  # no intake_requested event at all
    _write_case(brain_board, case)

    response = client.post("/api/workflow/case-to-drawing",
                           json={"case_id": "PRC-2819"})

    assert response.status_code == 409
    assert "Drop the PDF manually" in response.json()["detail"]


def test_case_to_drawing_rejects_path_traversal(brain_board: Path) -> None:
    for bad in ("../evil", "PRC\\evil", "a/b", ""):
        response = client.post("/api/workflow/case-to-drawing",
                               json={"case_id": bad})
        assert response.status_code == 400, bad


# --------------------------------------------------------------------------- #
# GET /api/case/{case_id}/submittal-pdf
# --------------------------------------------------------------------------- #

def test_submittal_pdf_roundtrips_raw_bytes(brain_board: Path) -> None:
    pdf_bytes = _sample_pdf_bytes()
    (brain_board / "intake" / "sub.pdf").write_bytes(pdf_bytes)
    _write_case(brain_board, _case_json(brain_board / "intake" / "sub.pdf"))

    response = client.get("/api/case/PRC-2819/submittal-pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == pdf_bytes


# --------------------------------------------------------------------------- #
# brain_case reader unit coverage (no web app involved)
# --------------------------------------------------------------------------- #

def test_expected_coils_latest_event_wins_and_drops_tagless() -> None:
    case = {
        "events": [
            {"field": "coil_requirement", "ts": "2026-07-01T00:00:00+00:00",
             "value": {"coils": [{"tag": "OLD-1", "qty": 1}]}},
            {"field": "coil_requirement", "ts": "2026-07-09T00:00:00+00:00",
             "value": {"coils": [{"tag": "CDXC-1", "qty": 2, "category": "DX COIL"},
                                  {"tag": "", "qty": 9}]}},
        ],
    }
    assert brain_case.expected_coils(case) == [
        {"tag": "CDXC-1", "qty": 2, "category": "DX COIL"}]


def test_load_case_missing_or_unsafe_returns_none(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PO_RELEASE_CASE_CASES_DIR", str(tmp_path))
    assert brain_case.load_case("PRC-404") is None
    assert brain_case.load_case("..") is None
    assert brain_case.load_case("a/b") is None
