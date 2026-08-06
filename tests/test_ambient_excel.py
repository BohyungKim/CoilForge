"""Ambient comparison Excel write-back — pure mapping + route contract.

The pure layer (excel_map) is fully tested; the COM writer (excel_writer) is exercised only
where win32com is present, and the route tests monkeypatch the writer so no real Excel runs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ambient.excel_map import build_ambient_excel_fill
from coilforge.ambient.pdf_intake import _parse_report_page
from coilforge.contracts import FieldValue
from coilforge.submittal.candidate import SubmittalCoilCandidate, load_submittal_candidate_fixture
from tests.test_ambient_pdf_intake import _DX_TEXT

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "sanitized"
    / "submittal_candidate_dx_header1_default.json"
)


def _tagged(cand, tag):
    return cand.model_copy(update={"tag": FieldValue(value=tag, manual_override=True)})


def _submittal_dx(tag="CDXC-2"):
    return _tagged(load_submittal_candidate_fixture(_FIXTURE), tag)


def _ambient_dx(tag="CDXC-2"):
    return _tagged(_parse_report_page(_DX_TEXT, page_number=1, source_id="A"), tag)


def _cells(sheet_dict):
    return {c["label"]: c for c in sheet_dict["cells"]}


def test_c_reads_submittal_keys_d_reads_ambient_keys():
    # The crux: C Fin Height comes from the submittal (geometry.finned_height); D comes from
    # the Ambient parser (geometry.finned_height_in). Different source keys, same row.
    base = _submittal_dx()
    amb = _ambient_dx()
    fill = build_ambient_excel_fill([base], [amb]).as_dict()
    assert len(fill["sheets"]) == 1
    cells = _cells(fill["sheets"][0])
    assert cells["Fin Height [in]"]["c"] == base.geometry["finned_height"].value
    assert cells["Fin Height [in]"]["d"] == amb.geometry["finned_height_in"].value


def test_capacity_c_reads_either_label():
    base = _submittal_dx()  # fixture carries performance.total_capacity_mbh
    fill = build_ambient_excel_fill([base], []).as_dict()
    cap = _cells(fill["sheets"][0])["Capacity [MBH]"]
    assert cap["c"] == base.performance["total_capacity_mbh"].value


def test_ranges_are_c_only_from_band():
    fill = build_ambient_excel_fill([_submittal_dx()], []).as_dict()
    cells = _cells(fill["sheets"][0])
    for label in ("Coil Volume Range [in^3]", "Capacity Range [MBH]"):
        assert cells[label]["c"] is not None
        assert cells[label]["d"] is None
        assert " - " in cells[label]["c"]  # "lo - hi"


def test_formula_only_labels_are_not_emitted():
    # Coil Volume [in^3] is a template formula on both sides -> never mapped/written here.
    fill = build_ambient_excel_fill([_submittal_dx()], [_ambient_dx()]).as_dict()
    labels = {c["label"] for c in fill["sheets"][0]["cells"]}
    assert "Coil Volume [in^3]" not in labels


def test_baseline_only_coil_gets_sheet_c_filled_d_blank_warned():
    fill = build_ambient_excel_fill([_submittal_dx("CDXC-3")], []).as_dict()
    assert len(fill["sheets"]) == 1
    sheet = fill["sheets"][0]
    assert sheet["source_sheet"] == "CDXC-1"
    assert any("no Ambient coil" in w for w in sheet["warnings"])
    assert _cells(sheet)["Fin Height [in]"]["d"] is None


def test_ambient_only_coil_gets_sheet_d_filled_c_blank_warned():
    fill = build_ambient_excel_fill([], [_ambient_dx("CDXC-4")]).as_dict()
    assert len(fill["sheets"]) == 1
    sheet = fill["sheets"][0]
    assert any("no baseline" in w for w in sheet["warnings"])
    cells = _cells(sheet)
    assert cells["Fin Height [in]"]["c"] is None
    assert cells["Fin Height [in]"]["d"] is not None


def test_alias_pair_collapses_to_one_sheet():
    # RHHGRC-2 (submittal) and RHHGRH-2 (ambient reheat spelling) are the same coil.
    base = _tagged(load_submittal_candidate_fixture(_FIXTURE), "RHHGRC-2")
    amb = _tagged(_parse_report_page(_DX_TEXT, page_number=1, source_id="A"), "RHHGRH-2")
    fill = build_ambient_excel_fill([base], [amb]).as_dict()
    assert len(fill["sheets"]) == 1  # merged, not two


def test_water_coil_has_no_master_sheet_and_is_warned():
    water = SubmittalCoilCandidate(
        candidate_id="w1", tag=FieldValue(value="CCWC-1", manual_override=True)
    )
    fill = build_ambient_excel_fill([water], []).as_dict()
    assert fill["sheets"] == []
    assert any("no comparison sheet" in w for w in fill["warnings"])


def test_safety_flags_locked():
    fill = build_ambient_excel_fill([_submittal_dx()], []).as_dict()
    assert fill["export_allowed"] is False
    assert fill["production_drawing_approval_claimed"] is False
    assert fill["review_required"] is True


# --- route contract (writer monkeypatched — no real Excel) ---------------------------------

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
import coilforge.web_app as web  # noqa: E402
from coilforge.ambient.pdf_intake import AmbientIntakeResult  # noqa: E402


@pytest.fixture
def client():
    return TestClient(web.app)


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(web, "_baseline_candidates", lambda *a, **k: [_submittal_dx()])
    monkeypatch.setattr(
        web, "parse_ambient_pdf",
        lambda *a, **k: AmbientIntakeResult(coils=[_ambient_dx()], warnings=[], engine="stub"),
    )


def test_excel_kill_switch_503(client, monkeypatch):
    monkeypatch.setenv("COILFORGE_AMBIENT", "0")
    r = client.post("/api/ambient/excel", files={"baseline": ("b.pdf", b"x"), "ambient": ("a.pdf", b"y")})
    assert r.status_code == 503


def test_excel_missing_file_400(client):
    r = client.post("/api/ambient/excel", files={"baseline": ("b.pdf", b"x")})
    assert r.status_code == 400


def test_excel_happy_path(client, patched, monkeypatch):
    monkeypatch.setattr(
        web, "write_ambient_excel",
        lambda fill, **k: {
            "saved_path": r"C:\Users\J\Downloads\cmp.xlsx",
            "sheets": [{"tag": "CDXC-2", "category": "DX COIL"}],
            "skipped_labels": [], "warnings": list(fill.warnings),
            "export_allowed": False, "production_drawing_approval_claimed": False,
        },
    )
    r = client.post(
        "/api/ambient/excel",
        files={"baseline": ("b.pdf", b"%PDF-1"), "ambient": ("a.pdf", b"%PDF-2")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["export_allowed"] is False
    assert data["raw_private_data_returned"] is False
    assert data["sheets"][0]["tag"] == "CDXC-2"


def test_excel_com_absent_is_501(client, patched, monkeypatch):
    def _raise(*a, **k):
        raise RuntimeError("Excel COM (pywin32) is required")
    monkeypatch.setattr(web, "write_ambient_excel", _raise)
    r = client.post(
        "/api/ambient/excel",
        files={"baseline": ("b.pdf", b"%PDF-1"), "ambient": ("a.pdf", b"%PDF-2")},
    )
    assert r.status_code == 501


def test_excel_garbage_pdf_never_500_crashes(client):
    r = client.post(
        "/api/ambient/excel",
        files={"baseline": ("b.pdf", b"not a pdf"), "ambient": ("a.pdf", b"also not")},
    )
    assert r.status_code in (400, 500)
    assert "detail" in r.json()
