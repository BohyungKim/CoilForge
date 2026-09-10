"""DirectCoil deliverable finalize — subject cleaning, folder resolution, filing,
and the endpoint contract.

Pure/filesystem behaviour is tested without Outlook/COM; the endpoint test
monkeypatches the workflow + COM draft so it exercises the wiring, safety flags,
and never-invent folder rules without a real Outlook.

NOTE (2026-08-30): the old ``test_place_bytes_never_clobbers`` is gone with
``place_bytes``/``place_copy``. Its coverage — a same-named file silently becoming
``… (2).pdf`` — was deliberately dropped: John's rule is now "stop and ask", so the
same ground is covered by the conflict / already-filed / overwrite tests below.
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.deliverable.finalize import (  # noqa: E402
    ALREADY_FILED,
    CONFLICT,
    NEW,
    FinalizeError,
    commit_placements,
    deliverable_subject,
    plan_placements,
    resolve_directcoil_folder,
    retire_download,
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

def _po_base(
    tmp_path: Path,
    project_folder: str,
    *,
    with_aof: bool = True,
    aof_name: str = "Accessory Order Forms",
) -> Path:
    base = tmp_path / "02 - POs"
    proj = base / project_folder
    (proj / aof_name).mkdir(parents=True) if with_aof else proj.mkdir(parents=True)
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


# ---- folder-name variants (John 2026-08-30) ---------------------------------

@pytest.mark.parametrize("existing", ["Direct Coil", "direct_coil", "DIRECT COIL"])
def test_existing_directcoil_variant_is_renamed_not_duplicated(
    tmp_path: Path, existing: str
) -> None:
    """A differently-spelled DirectCoil is renamed and reused, keeping the file
    history John already has in it — never left beside a fresh empty one."""
    base = _po_base(tmp_path, "2572 - Bowie State")
    aof = base / "2572 - Bowie State" / "Accessory Order Forms"
    (aof / existing).mkdir()
    (aof / existing / "old-quote.pdf").write_bytes(b"already here")

    folder = resolve_directcoil_folder("2572", base_dir=str(base))

    assert folder.name == "DirectCoil"
    assert (folder / "old-quote.pdf").read_bytes() == b"already here"
    assert sorted(p.name for p in aof.iterdir()) == ["DirectCoil"]


def test_two_directcoil_spellings_are_ambiguous_not_guessed(tmp_path: Path) -> None:
    base = _po_base(tmp_path, "2572 - Bowie State")
    aof = base / "2572 - Bowie State" / "Accessory Order Forms"
    (aof / "DirectCoil").mkdir()
    (aof / "Direct Coil").mkdir()
    with pytest.raises(FinalizeError, match="multiple 'DirectCoil' folders"):
        resolve_directcoil_folder("2572", base_dir=str(base))


def test_singular_accessory_order_form_still_resolves(tmp_path: Path) -> None:
    """The AOF-missing error only means "wrong project folder" if a mere spelling
    variant cannot trigger it."""
    base = _po_base(tmp_path, "2572 - Bowie State", aof_name="Accessory Order Form")
    folder = resolve_directcoil_folder("2572", base_dir=str(base))
    assert folder.name == "DirectCoil"
    assert folder.parent.name == "Accessory Order Form"  # matched, never renamed


def test_two_aof_spellings_are_ambiguous(tmp_path: Path) -> None:
    base = _po_base(tmp_path, "2572 - Bowie State")
    proj = base / "2572 - Bowie State"
    (proj / "Accessory Order Form").mkdir()
    with pytest.raises(FinalizeError, match="multiple 'Accessory Order Forms' folders"):
        resolve_directcoil_folder("2572", base_dir=str(base))


# ---- filing: all-or-nothing, conflict = same name AND different content ------

def test_plan_marks_new_already_filed_and_conflict(tmp_path: Path) -> None:
    (tmp_path / "same.pdf").write_bytes(b"identical")
    (tmp_path / "other.pdf").write_bytes(b"the older revision")
    plans = plan_placements(
        tmp_path,
        [("fresh.pdf", b"new"), ("same.pdf", b"identical"), ("other.pdf", b"a revision")],
    )
    assert [p.state for p in plans] == [NEW, ALREADY_FILED, CONFLICT]


def test_conflict_writes_nothing_at_all(tmp_path: Path) -> None:
    """One collision must stop the WHOLE deliverable — a half-filed folder is worse
    than an unfiled one, because it looks finished."""
    (tmp_path / "quote.pdf").write_bytes(b"the older revision")
    plans = plan_placements(
        tmp_path, [("revised.pdf", b"brand new"), ("quote.pdf", b"a revision")]
    )
    with pytest.raises(FinalizeError, match="refusing to file over"):
        commit_placements(plans)
    assert (tmp_path / "quote.pdf").read_bytes() == b"the older revision"
    assert not (tmp_path / "revised.pdf").exists()  # the non-conflicting one too


def test_already_filed_is_not_rewritten(tmp_path: Path) -> None:
    dest = tmp_path / "quote.pdf"
    dest.write_bytes(b"identical")
    os.utime(dest, (1_600_000_000, 1_600_000_000))
    written = commit_placements(plan_placements(tmp_path, [("quote.pdf", b"identical")]))
    assert written == [str(dest)]
    assert dest.stat().st_mtime == pytest.approx(1_600_000_000, abs=2)


def test_overwrite_replaces_the_conflicting_file(tmp_path: Path) -> None:
    (tmp_path / "quote.pdf").write_bytes(b"the older revision")
    plans = plan_placements(tmp_path, [("quote.pdf", b"a revision")])
    commit_placements(plans, overwrite=True)
    assert (tmp_path / "quote.pdf").read_bytes() == b"a revision"


def test_path_payload_is_moved_not_copied(tmp_path: Path) -> None:
    """The checklist is the one doc whose real path we know — so it is a true move."""
    src = tmp_path / "downloads" / "2572 - Coil Checklist.xlsx"
    src.parent.mkdir()
    src.write_bytes(b"xlsx bytes")
    folder = tmp_path / "DirectCoil"
    folder.mkdir()
    written = commit_placements(plan_placements(folder, [(src.name, src)]))
    assert Path(written[0]).read_bytes() == b"xlsx bytes"
    assert not src.exists()


def test_already_filed_path_payload_still_clears_downloads(tmp_path: Path) -> None:
    src = tmp_path / "downloads" / "sheet.xlsx"
    src.parent.mkdir()
    src.write_bytes(b"xlsx bytes")
    folder = tmp_path / "DirectCoil"
    folder.mkdir()
    (folder / "sheet.xlsx").write_bytes(b"xlsx bytes")
    commit_placements(plan_placements(folder, [(src.name, src)]))
    assert not src.exists()  # the duplicate in Downloads is still retired


# ---- Downloads retirement (content-verified) --------------------------------

def test_retire_download_deletes_only_a_content_match(tmp_path: Path) -> None:
    (tmp_path / "quote.pdf").write_bytes(b"filed bytes")
    assert retire_download("quote.pdf", b"filed bytes", downloads_dir=tmp_path) == "moved"
    assert not (tmp_path / "quote.pdf").exists()


def test_retire_download_leaves_an_unrelated_same_named_file(tmp_path: Path) -> None:
    """The browser gives bytes, never a path — so a name match alone must never be
    enough to delete. This is the guard that makes the reconstruction safe."""
    (tmp_path / "quote.pdf").write_bytes(b"somebody else's quote")
    status = retire_download("quote.pdf", b"filed bytes", downloads_dir=tmp_path)
    assert status == "differs — left in place"
    assert (tmp_path / "quote.pdf").read_bytes() == b"somebody else's quote"


def test_retire_download_reports_a_missing_original(tmp_path: Path) -> None:
    status = retire_download("quote.pdf", b"filed bytes", downloads_dir=tmp_path)
    assert status == "not found — left in place"


def test_retire_download_catches_the_chrome_duplicate_suffix(tmp_path: Path) -> None:
    """Chrome saves over an existing name as "x (1).pdf" — retiring only the exact
    name would strand the copy it actually just wrote."""
    (tmp_path / "2572 - Bowie_Revised.pdf").write_bytes(b"an older download")
    (tmp_path / "2572 - Bowie_Revised (1).pdf").write_bytes(b"filed bytes")
    status = retire_download(
        "2572 - Bowie_Revised.pdf", b"filed bytes", downloads_dir=tmp_path
    )
    assert status == "moved"
    assert not (tmp_path / "2572 - Bowie_Revised (1).pdf").exists()
    assert (tmp_path / "2572 - Bowie_Revised.pdf").exists()  # not ours, untouched


# ---- endpoint contract ------------------------------------------------------

def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _stub_endpoint(monkeypatch, tmp_path: Path):
    """Canned intake + temp DirectCoil folder + stubbed Outlook/Downloads.

    ``retire_download`` is stubbed so a test never scans (let alone deletes from) the
    real ``~/Downloads``; its own behaviour is covered by the unit tests above.
    """
    pytest.importorskip("fastapi")
    import coilforge.web_app as web_app
    import coilforge.deliverable.finalize as finalize_mod
    import coilforge.deliverable.outlook_draft as draft_mod

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

    directcoil = tmp_path / "DirectCoil"
    directcoil.mkdir()
    monkeypatch.setattr(finalize_mod, "resolve_directcoil_folder", lambda *a, **k: directcoil)
    monkeypatch.setattr(finalize_mod, "retire_download", lambda *a, **k: "moved")
    calls: dict = {}
    monkeypatch.setattr(draft_mod, "open_deliverable_draft", lambda **kw: calls.update(kw))
    return web_app, directcoil, calls


_BODY = {
    "submittal_pdf_base64": _b64(b"%PDF-sub"),
    "submittal_filename": "2572 - Oxygen8 Submittal.pdf",
    "quote_pdf_base64": _b64(b"%PDF-quote"),
    "quote_filename": "2572 - Bowie.pdf",
    "revised_pdf_base64": _b64(b"%PDF-revised"),
}


def test_finalize_endpoint_files_docs_and_drafts_email(monkeypatch, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    web_app, directcoil, calls = _stub_endpoint(monkeypatch, tmp_path)
    resp = TestClient(web_app.app).post("/api/deliverable/finalize", json=dict(_BODY))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "filed"
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
    # Both PDFs reported as retired from Downloads.
    assert [e["status"] for e in body["downloads_cleanup"]] == ["moved", "moved"]


def test_finalize_endpoint_skip_draft_files_without_outlook(monkeypatch, tmp_path: Path) -> None:
    """What the Build button sends: file the docs, leave the email to John's button."""
    from fastapi.testclient import TestClient

    web_app, directcoil, calls = _stub_endpoint(monkeypatch, tmp_path)
    resp = TestClient(web_app.app).post(
        "/api/deliverable/finalize", json={**_BODY, "skip_draft": True}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "filed"
    assert len(body["files_written"]) == 2
    assert body["draft_opened"] is False and body["draft_status"] == "skipped"
    assert calls == {}  # Outlook never touched


def test_finalize_endpoint_rerun_over_identical_files_is_not_a_conflict(
    monkeypatch, tmp_path: Path
) -> None:
    """Build files the docs, then the draft button re-runs over the same three. That
    must sail through — this is what keeps the two-button flow working."""
    from fastapi.testclient import TestClient

    web_app, directcoil, calls = _stub_endpoint(monkeypatch, tmp_path)
    client = TestClient(web_app.app)
    client.post("/api/deliverable/finalize", json={**_BODY, "skip_draft": True})
    resp = client.post("/api/deliverable/finalize", json=dict(_BODY))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "filed"
    assert body["conflicts"] == []
    assert body["draft_opened"] is True


def test_finalize_endpoint_stops_and_asks_on_a_real_conflict(
    monkeypatch, tmp_path: Path
) -> None:
    from fastapi.testclient import TestClient

    web_app, directcoil, calls = _stub_endpoint(monkeypatch, tmp_path)
    (directcoil / "2572 - Bowie.pdf").write_bytes(b"%PDF-an-older-quote")

    resp = TestClient(web_app.app).post("/api/deliverable/finalize", json=dict(_BODY))
    assert resp.status_code == 200  # a decision for John, not an error
    body = resp.json()
    assert body["status"] == "conflict"
    assert [c["name"] for c in body["conflicts"]] == ["2572 - Bowie.pdf"]
    assert body["files_written"] == []
    assert body["draft_opened"] is False
    assert calls == {}
    # Nothing written — not even the non-conflicting revised PDF.
    assert (directcoil / "2572 - Bowie.pdf").read_bytes() == b"%PDF-an-older-quote"
    assert not (directcoil / "2572 - Bowie_Revised.pdf").exists()


def test_finalize_endpoint_overwrite_resolves_the_conflict(
    monkeypatch, tmp_path: Path
) -> None:
    from fastapi.testclient import TestClient

    web_app, directcoil, calls = _stub_endpoint(monkeypatch, tmp_path)
    (directcoil / "2572 - Bowie.pdf").write_bytes(b"%PDF-an-older-quote")

    resp = TestClient(web_app.app).post(
        "/api/deliverable/finalize", json={**_BODY, "overwrite": True}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "filed"
    assert (directcoil / "2572 - Bowie.pdf").read_bytes() == b"%PDF-quote"


def _stub_checklist(monkeypatch, web_app, saved_path: Path):
    """Make the endpoint see an auto-generated checklist at ``saved_path``."""

    async def _cached(*a, **k):
        return web_app._ChecklistOutcome(
            review={"rows": []}, saved_path=str(saved_path), reason=None, http_status=None
        )

    monkeypatch.setattr(web_app, "_run_or_reuse_checklist", _cached)


def test_finalize_endpoint_moves_the_checklist_out_of_downloads(
    monkeypatch, tmp_path: Path
) -> None:
    from fastapi.testclient import TestClient

    web_app, directcoil, _ = _stub_endpoint(monkeypatch, tmp_path)
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    sheet = downloads / "2572 - Coil Checklist.xlsx"
    sheet.write_bytes(b"xlsx bytes")
    _stub_checklist(monkeypatch, web_app, sheet)

    body = TestClient(web_app.app).post(
        "/api/deliverable/finalize", json={**_BODY, "skip_draft": True}
    ).json()

    assert body["checklist_status"] == "ok"
    assert len(body["files_written"]) == 3
    assert (directcoil / sheet.name).read_bytes() == b"xlsx bytes"
    assert not sheet.exists()  # moved, not copied
    assert {e["name"]: e["status"] for e in body["downloads_cleanup"]}[sheet.name] == "moved"


def test_finalize_endpoint_says_already_filed_when_the_sheet_was_moved_earlier(
    monkeypatch, tmp_path: Path
) -> None:
    """Second run of the real flow: Build MOVED the sheet, so the memoized
    ``saved_path`` now points at nothing. That is a completed move, not a missing
    checklist — reporting "unavailable" here would read as a filing failure."""
    from fastapi.testclient import TestClient

    web_app, directcoil, _ = _stub_endpoint(monkeypatch, tmp_path)
    gone = tmp_path / "downloads" / "2572 - Coil Checklist.xlsx"
    (directcoil / gone.name).write_bytes(b"xlsx bytes")
    _stub_checklist(monkeypatch, web_app, gone)

    body = TestClient(web_app.app).post(
        "/api/deliverable/finalize", json={**_BODY, "skip_draft": True}
    ).json()

    assert body["checklist_status"] == "already filed"
    assert len(body["files_written"]) == 2  # the two PDFs; no phantom third entry
    assert body["status"] == "filed"


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


# ---- the checklist must never go missing quietly (2026-09-09) ---------------
#
# The two PDFs reach the server as BYTES in the request body, so they are always in
# `items`. The checklist reaches it as a Downloads PATH that finalize re-derives per
# request -- so every failure to re-derive it dropped the .xlsx while both PDFs filed
# cleanly. These pin the invariant that makes that visible.


def test_pathless_cache_entry_is_not_reused_as_a_success(monkeypatch) -> None:
    """A memoized entry with no ``saved_path`` must regenerate, not report success.

    Reusing it returned ``review != None`` with ``saved_path=None``; finalize then had
    no file to file AND left ``checklist_status`` at "ok", so the deliverable went out
    without the sheet and the UI showed no warning at all.
    """
    pytest.importorskip("fastapi")
    import asyncio
    import hashlib

    import coilforge.web_app as web_app

    web_app.clear_checklist_cache()
    key = (hashlib.sha1(b"%PDF-x").hexdigest(), None, None, None, None)
    web_app._CHECKLIST_CACHE[key] = {"review": {"rows": []}, "saved_path": None}

    calls: list[int] = []

    def _regenerated(*a, **k):
        calls.append(1)
        raise ValueError("regenerated")

    monkeypatch.setattr(web_app, "run_pdf_to_drawing_workflow", _regenerated)

    outcome = asyncio.run(web_app._run_or_reuse_checklist(b"%PDF-x"))

    assert calls, "a pathless entry must fall through to a fresh generation"
    assert outcome.review is None and outcome.saved_path is None
    assert key not in web_app._CHECKLIST_CACHE
    web_app.clear_checklist_cache()


def test_checklist_status_is_never_ok_when_the_sheet_was_not_filed(
    monkeypatch, tmp_path: Path
) -> None:
    """THE invariant: not in ``files_written`` -> the status names why, never "ok"."""
    from fastapi.testclient import TestClient

    web_app, _directcoil, _ = _stub_endpoint(monkeypatch, tmp_path)

    async def _no_sheet(*a, **k):
        return web_app._ChecklistOutcome(
            review=None,
            saved_path=None,
            reason="Excel COM (pywin32) is required to write the checklist",
            http_status=501,
        )

    monkeypatch.setattr(web_app, "_run_or_reuse_checklist", _no_sheet)

    body = TestClient(web_app.app).post(
        "/api/deliverable/finalize", json={**_BODY, "skip_draft": True}
    ).json()

    assert body["status"] == "filed"
    assert len(body["files_written"]) == 2  # the PDFs still file
    assert body["checklist_status"] != "ok"
    assert "pywin32" in body["checklist_status"]
    assert "not filed" in body["checklist_status"]


def test_checklist_status_names_a_missing_path_even_with_a_review(
    monkeypatch, tmp_path: Path
) -> None:
    """review present + no path: the old code called this "ok" and warned about nothing."""
    from fastapi.testclient import TestClient

    web_app, _directcoil, _ = _stub_endpoint(monkeypatch, tmp_path)

    async def _review_without_path(*a, **k):
        return web_app._ChecklistOutcome(
            review={"rows": []}, saved_path=None, reason=None, http_status=None
        )

    monkeypatch.setattr(web_app, "_run_or_reuse_checklist", _review_without_path)

    body = TestClient(web_app.app).post(
        "/api/deliverable/finalize", json={**_BODY, "skip_draft": True}
    ).json()

    assert body["checklist_status"] == "checklist path unavailable — not filed"
    checklist = next(d for d in body["documents"] if d["kind"] == "checklist")
    assert checklist["filed"] is False


def test_finalize_passes_the_cover_page_hint_to_the_checklist(
    monkeypatch, tmp_path: Path
) -> None:
    """The hint is part of the checklist cache key. Dropping it here guaranteed a miss
    on every hand-selected cover page, re-deriving the coils without it."""
    from fastapi.testclient import TestClient

    web_app, _directcoil, _ = _stub_endpoint(monkeypatch, tmp_path)
    seen: dict = {}

    async def _capture(pdf_bytes, **kwargs):
        seen.update(kwargs)
        return web_app._ChecklistOutcome(None, None, "no coils", 400)

    monkeypatch.setattr(web_app, "_run_or_reuse_checklist", _capture)

    TestClient(web_app.app).post(
        "/api/deliverable/finalize",
        json={**_BODY, "skip_draft": True, "cover_page": "7"},
    )
    assert seen["cover_page_hint"] == 7


def test_finalize_rejects_a_nonsense_cover_page(monkeypatch, tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    web_app, _directcoil, _ = _stub_endpoint(monkeypatch, tmp_path)
    resp = TestClient(web_app.app).post(
        "/api/deliverable/finalize", json={**_BODY, "cover_page": "0"}
    )
    assert resp.status_code == 400


def test_documents_log_reports_each_document_separately(
    monkeypatch, tmp_path: Path
) -> None:
    """The per-document log the status panel renders: kind, filed, state, downloads."""
    from fastapi.testclient import TestClient

    web_app, _directcoil, _ = _stub_endpoint(monkeypatch, tmp_path)
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    sheet = downloads / "2572 - Coil Checklist.xlsx"
    sheet.write_bytes(b"xlsx bytes")
    _stub_checklist(monkeypatch, web_app, sheet)

    body = TestClient(web_app.app).post(
        "/api/deliverable/finalize", json={**_BODY, "skip_draft": True}
    ).json()

    docs = {d["kind"]: d for d in body["documents"]}
    assert set(docs) == {"quote", "revised", "checklist"}
    assert all(d["filed"] for d in docs.values())
    assert docs["quote"]["name"] == "2572 - Bowie.pdf"
    assert docs["revised"]["name"] == "2572 - Bowie_Revised.pdf"
    assert docs["checklist"]["name"] == sheet.name
    assert docs["checklist"]["downloads"] == "moved"
    assert all(d["state"] == "new" for d in docs.values())
    assert all(d["detail"] is None for d in docs.values())


def test_a_copy_failure_is_a_named_error_not_a_bare_oserror(tmp_path: Path) -> None:
    """The commit loop has no rollback and path payloads come last, so an OSError there
    surfaced as an unnamed 500 with earlier documents already on disk."""
    folder = tmp_path / "dest"
    folder.mkdir()
    missing = tmp_path / "gone.xlsx"
    missing.write_bytes(b"x")
    placements = plan_placements(folder, [("gone.xlsx", missing)])
    missing.unlink()  # vanishes between plan and commit

    with pytest.raises(FinalizeError) as excinfo:
        commit_placements(placements)
    assert "gone.xlsx" in str(excinfo.value)


# ---- opening the filed folder (a browser-supplied path is never trusted) ----


def test_open_folder_refuses_a_path_outside_the_po_base(tmp_path: Path) -> None:
    from coilforge.deliverable.open_folder import open_deliverable_folder

    base = tmp_path / "base"
    (base / "inside").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(FinalizeError):
        open_deliverable_folder(outside, base_dir=str(base))
    # ...and traversal back out of the base is normalized BEFORE the check, not after.
    with pytest.raises(FinalizeError):
        open_deliverable_folder(
            base / "inside" / ".." / ".." / "outside", base_dir=str(base)
        )


def test_open_folder_refuses_an_empty_or_vanished_folder(tmp_path: Path) -> None:
    from coilforge.deliverable.open_folder import open_deliverable_folder

    base = tmp_path / "base"
    base.mkdir()
    with pytest.raises(FinalizeError):
        open_deliverable_folder("", base_dir=str(base))
    with pytest.raises(FinalizeError):
        open_deliverable_folder(base / "never-made", base_dir=str(base))


def test_open_folder_opens_a_folder_inside_the_base(monkeypatch, tmp_path: Path) -> None:
    from coilforge.deliverable import open_folder as mod

    base = tmp_path / "base"
    target = base / "3121" / "Accessory Order Forms" / "DirectCoil"
    target.mkdir(parents=True)
    opened: list[str] = []
    monkeypatch.setattr(mod.os, "startfile", opened.append, raising=False)

    result = mod.open_deliverable_folder(target, base_dir=str(base))
    assert opened == [str(target.resolve())]
    assert result == str(target.resolve())
