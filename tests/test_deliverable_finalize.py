"""DirectCoil deliverable finalize — subject cleaning, folder resolution, filing,
and the endpoint contract.

Pure/filesystem behaviour is tested without Outlook/COM; the endpoint test
monkeypatches the workflow + COM draft so it exercises the wiring, safety flags,
and never-invent folder rules without a real Outlook.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.deliverable.finalize import (  # noqa: E402
    FinalizeError,
    deliverable_subject,
    place_bytes,
    resolve_directcoil_folder,
    short_project_name,
)


# ---- subject cleaning -------------------------------------------------------

def test_short_name_strips_number_prefix_and_admin_cruft() -> None:
    # The 2572 intake name carries a "Ship To Revision No.: 4a" tail we must drop.
    name = "2572 - Bowie State Tubman Ship To Revision No.: 4a"
    assert short_project_name("2572", name) == "Bowie State Tubman"


def test_subject_is_coils_number_dash_clean_name() -> None:
    name = "2572 - Bowie State Tubman Ship To Revision No.: 4a"
    assert deliverable_subject("2572", name) == "Coils: 2572 - Bowie State Tubman"


def test_subject_passes_through_already_clean_name() -> None:
    # John's 3025 example — already clean, must be preserved verbatim.
    assert (
        deliverable_subject("3025", "3025 - Bauducco Foods Zephyrhills")
        == "Coils: 3025 - Bauducco Foods Zephyrhills"
    )


def test_subject_handles_name_without_number_prefix() -> None:
    assert deliverable_subject("2572", "Bowie State") == "Coils: 2572 - Bowie State"


# ---- folder resolution ------------------------------------------------------

def _po_base(tmp_path: Path, project_folder: str, *, with_aof: bool = True) -> Path:
    base = tmp_path / "02 - POs"
    proj = base / project_folder
    (proj / "Accessory Order Forms").mkdir(parents=True) if with_aof else proj.mkdir(parents=True)
    return base


def test_resolve_creates_only_the_directcoil_leaf(tmp_path: Path) -> None:
    base = _po_base(tmp_path, "2572 - Bowie State")
    folder = resolve_directcoil_folder("2572", base_dir=str(base))
    assert folder.name == "DirectCoil"
    assert folder.parent.name == "Accessory Order Forms"
    assert folder.is_dir()
    # Idempotent — a second call reuses the existing leaf.
    assert resolve_directcoil_folder("2572", base_dir=str(base)) == folder


def test_resolve_fails_loudly_when_project_folder_absent(tmp_path: Path) -> None:
    base = tmp_path / "02 - POs"
    base.mkdir()
    with pytest.raises(FinalizeError, match="starting with 2572"):
        resolve_directcoil_folder("2572", base_dir=str(base))


def test_resolve_fails_loudly_when_accessory_order_forms_absent(tmp_path: Path) -> None:
    base = _po_base(tmp_path, "2572 - Bowie State", with_aof=False)
    with pytest.raises(FinalizeError, match="Accessory Order Forms"):
        resolve_directcoil_folder("2572", base_dir=str(base))


def test_resolve_fails_loudly_when_prefix_is_ambiguous(tmp_path: Path) -> None:
    base = tmp_path / "02 - POs"
    (base / "2572 - Bowie State" / "Accessory Order Forms").mkdir(parents=True)
    (base / "2572 - Other Job" / "Accessory Order Forms").mkdir(parents=True)
    with pytest.raises(FinalizeError, match="multiple project folders"):
        resolve_directcoil_folder("2572", base_dir=str(base))


# ---- filing (never clobber) -------------------------------------------------

def test_place_bytes_never_clobbers(tmp_path: Path) -> None:
    first = place_bytes(tmp_path, "quote.pdf", b"a")
    second = place_bytes(tmp_path, "quote.pdf", b"b")
    assert Path(first).name == "quote.pdf"
    assert Path(second).name == "quote (2).pdf"
    assert Path(first).read_bytes() == b"a" and Path(second).read_bytes() == b"b"


# ---- endpoint contract ------------------------------------------------------

def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def test_finalize_endpoint_files_docs_and_drafts_email(monkeypatch, tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import coilforge.web_app as web_app
    import coilforge.deliverable.finalize as finalize_mod
    import coilforge.deliverable.outlook_draft as draft_mod

    # Intake canned so no real PDF parsing is needed; no candidates -> checklist skipped.
    monkeypatch.setattr(
        web_app, "run_pdf_to_drawing_workflow",
        lambda *a, **k: {
            "pdf_intake_summary": {
                "project_number": "2572",
                "project_name": "2572 - Bowie State Tubman Ship To Revision No.: 4a",
            },
            "candidates": [],
        },
    )
    monkeypatch.setattr(web_app, "coil_inputs_from_candidates", lambda *a, **k: ([], {}))

    # Route into a temp DirectCoil folder and stub the Outlook draft.
    directcoil = tmp_path / "DirectCoil"
    directcoil.mkdir()
    monkeypatch.setattr(finalize_mod, "resolve_directcoil_folder", lambda *a, **k: directcoil)
    calls = {}
    monkeypatch.setattr(
        draft_mod, "open_deliverable_draft",
        lambda **kw: calls.update(kw),
    )

    client = TestClient(web_app.app)
    resp = client.post(
        "/api/deliverable/finalize",
        json={
            "submittal_pdf_base64": _b64(b"%PDF-sub"),
            "submittal_filename": "2572 - Oxygen8 Submittal.pdf",
            "quote_pdf_base64": _b64(b"%PDF-quote"),
            "quote_filename": "2572 - Bowie.pdf",
            "revised_pdf_base64": _b64(b"%PDF-revised"),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["export_allowed"] is False
    assert body["review_aid_only"] is True
    assert body["email_sent"] is False
    assert body["subject"] == "Coils: 2572 - Bowie State Tubman"
    # Original + revised filed (checklist skipped -> only 2 files).
    assert len(body["files_written"]) == 2
    assert Path(body["files_written"][0]).name == "2572 - Bowie.pdf"
    assert Path(body["files_written"][1]).name == "2572 - Bowie_Revised.pdf"
    assert (directcoil / "2572 - Bowie_Revised.pdf").read_bytes() == b"%PDF-revised"
    # Draft opened with the revised PDF attached, never sent.
    assert body["draft_opened"] is True
    assert calls["subject"] == "Coils: 2572 - Bowie State Tubman"
    assert calls["attachment_path"] == body["files_written"][1]


def test_finalize_endpoint_rejects_missing_pdf() -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import coilforge.web_app as web_app

    client = TestClient(web_app.app)
    resp = client.post("/api/deliverable/finalize", json={"quote_pdf_base64": "x"})
    assert resp.status_code == 400


def test_finalize_endpoint_reports_missing_folder(monkeypatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import coilforge.web_app as web_app
    import coilforge.deliverable.finalize as finalize_mod

    monkeypatch.setattr(
        web_app, "run_pdf_to_drawing_workflow",
        lambda *a, **k: {
            "pdf_intake_summary": {"project_number": "9999", "project_name": "9999 - Ghost"},
            "candidates": [],
        },
    )
    monkeypatch.setattr(web_app, "coil_inputs_from_candidates", lambda *a, **k: ([], {}))

    def _boom(*a, **k):
        raise finalize_mod.FinalizeError("no project folder under '02 - POs' starting with 9999")

    monkeypatch.setattr(finalize_mod, "resolve_directcoil_folder", _boom)

    client = TestClient(web_app.app)
    resp = client.post(
        "/api/deliverable/finalize",
        json={
            "submittal_pdf_base64": _b64(b"%PDF-sub"),
            "quote_pdf_base64": _b64(b"%PDF-quote"),
            "revised_pdf_base64": _b64(b"%PDF-revised"),
        },
    )
    assert resp.status_code == 409
    assert "9999" in resp.json()["detail"]
