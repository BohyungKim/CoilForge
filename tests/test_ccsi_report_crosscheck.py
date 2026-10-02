"""The report cross-check batch: its safety boundary (no ledger/journal writers, no LLM OCR) and
its pure pieces (coil pairing, submittal choice, aggregation). No PO folder is touched."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import ccsi_report_crosscheck as batch  # noqa: E402  # pyright: ignore[reportMissingImports]

from coilforge.submittal import pdf_intake  # noqa: E402

SCRIPT = (ROOT / "scripts" / "ccsi_report_crosscheck.py").read_text(encoding="utf-8")


def test_the_batch_never_imports_a_ledger_or_journal_writer() -> None:
    imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", SCRIPT, re.M)
    for forbidden in ("coilforge.web_app", "coilforge.case_journal", "coilforge.capture.record",
                      "coilforge.workflows"):
        assert not any(i.startswith(forbidden) for i in imports), forbidden
    assert 'os.environ["COILFORGE_CAPTURE"] = "0"' in SCRIPT


def test_importing_the_batch_does_not_switch_capture_off_for_the_process() -> None:
    """The guard is set inside main(), never at import: at import it leaked into the whole pytest
    process and silently disabled every later capture-ledger test (2026-09-30)."""
    assert not re.search(r'^os\.environ\["COILFORGE_CAPTURE"\]', SCRIPT, re.M)
    main_body = SCRIPT[SCRIPT.index("def main() -> int:"):]
    assert main_body.index('os.environ["COILFORGE_CAPTURE"] = "0"') < main_body.index("ProcessPoolExecutor(")


def test_the_extraction_cache_key_is_a_fingerprint_taken_once_at_import() -> None:
    """code_version() stays "-dirty" across uncommitted edits, so an intake fix used to reuse the old
    extraction; reading the runner's own bytes per call let a mid-batch edit mislabel old results."""
    assert re.fullmatch(r"[0-9a-f]{12}", batch.EXTRACTION_FINGERPRINT)
    extract = SCRIPT[SCRIPT.index("def extract_submittal"):SCRIPT.index("def _extract_job")]
    assert "EXTRACTION_FINGERPRINT" in extract and "__file__" not in extract


def test_the_ocr_guard_makes_llm_ocr_a_no_op(monkeypatch) -> None:
    # pre-register both so monkeypatch restores them after the guard overwrites them
    monkeypatch.setattr(pdf_intake, "_extract_page_text_with_llm_ocr_uncached",
                        pdf_intake._extract_page_text_with_llm_ocr_uncached)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    batch.install_ocr_guard()
    result = pdf_intake._extract_page_text_with_llm_ocr_uncached(b"%PDF", 3)
    assert result.status == batch._OCR_BLOCKED_STATUS and result.text == "" and result.page_number == 3
    import os
    assert os.environ["OPENAI_API_KEY"] == ""


def _coil(coil_type: str, tag: str | None, key: str = "base_tag") -> dict:
    return {"coil_type": coil_type, key: tag}


def test_pairing_by_tag_alias_then_single_of_type_never_by_guess() -> None:
    report = [_coil("HGRH", "RHHGRH-1"), _coil("DX", "CDXC-1"), _coil("CWC", None)]
    submittal = [_coil("HGRH", "RHHGRC-1", "tag"), _coil("DX", "CDXC-9", "tag"), _coil("CWC", "CCWC-1", "tag")]
    pairs = {(c["coil_type"]): (p, m) for c, p, m in batch.pair_coils(report, submittal, "base_tag", "tag")}
    assert pairs["HGRH"][1] == "tag"  # RHHGRH == RHHGRC spelling variant
    assert pairs["DX"][1] == "single_of_type" and pairs["CWC"][1] == "single_of_type"
    two = [_coil("DX", "CDXC-1"), _coil("DX", "CDXC-2")]
    unmatched = batch.pair_coils(two, [_coil("DX", "CDXC-7", "tag"), _coil("DX", "CDXC-8", "tag")], "base_tag", "tag")
    assert [m for _c, p, m in unmatched if p is None] == ["no_tag_match", "no_tag_match"]


def test_changed_at_order_compares_numbers_and_option_keys() -> None:
    assert batch._changed("6", "7") and not batch._changed("21", "21.0")
    assert not batch._changed("Copper - 0.016 Plain", "Copper 0.016 Plain")
    assert batch._changed("Copper 0.016 Plain", "Copper 0.020 Plain")
    assert not batch._changed(None, "7")


def _touch(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_submittal_choice_prefers_the_ledger_hash_then_the_highest_rev(tmp_path) -> None:
    fw = tmp_path / "Final Working"
    rev0 = _touch(fw / "P - Oxygen8 Submittal - X - Rev0.pdf", b"rev0")
    _touch(fw / "P - Oxygen8 Submittal - X - Rev1.pdf", b"rev1")
    _touch(fw / "P - Oxygen8 Submittal - X - Rev2 - COMMENTS.pdf", b"comments")
    _touch(tmp_path / "Signed Final Submittal" / "P - Oxygen8 Submittal - X - Rev3_AsBuilt.pdf", b"asbuilt")
    import hashlib
    ledger = {hashlib.sha1(b"rev0").hexdigest(): "2026-09-01T00:00:00Z"}
    assert batch.pick_submittal(tmp_path, ledger) == (rev0, "ledger_hash")
    path, how = batch.pick_submittal(tmp_path, {})
    assert how == "heuristic_highest_rev" and path.name.endswith("Rev1.pdf")  # COMMENTS / AsBuilt excluded


def test_submittal_choice_refuses_a_tie(tmp_path) -> None:
    _touch(tmp_path / "Final Working" / "A - Oxygen8 Submittal - Rev1.pdf", b"one")
    _touch(tmp_path / "Final Working" / "nested" / "B - Oxygen8 Submittal - Rev1.pdf", b"two")
    assert batch.pick_submittal(tmp_path, {}) == (None, "ambiguous_submittal")
    assert batch.pick_submittal(tmp_path / "missing", {}) == (None, "no_submittal")


def test_aggregate_counts_projects_and_keeps_not_printed_fields_out_of_the_mismatch_list() -> None:
    rows = [
        {"ccsi_id": "Tag", "verdict": "match", "reason_code": "CCSI_NOT_VALIDATED"},
        {"ccsi_id": "TubeMaterial", "verdict": "match", "reason_code": "CCSI_OK"},
        {"ccsi_id": "HeaderMaterial", "verdict": "match", "reason_code": "CCSI_DEFAULT_PROFILE"},
        {"ccsi_id": "CoilType", "verdict": "absent_on_form", "reason_code": "CCSI_DEFAULT_PROFILE"},
        {"ccsi_id": "NumberOfFeeds", "verdict": "mismatch", "reason_code": "CCSI_OK", "changed_at_order": True,
         "coilforge": "6", "ccsi": "7", "rev0": "6"},
    ]
    results = [{"coils": [{"project": "P1", "tag": "CDXC-1", "coil_type": "DX", "rows": rows}]},
               {"coils": [{"project": "P2", "tag": "CDXC-1", "coil_type": "DX", "rows": rows[:2]}]}]
    dx = batch.aggregate(results)["DX"]
    assert dx["coils"] == 2 and dx["projects"] == 2 and "Tag" not in dx["fields"]
    assert dx["fields"]["TubeMaterial"] == {"match": 2}
    assert dx["fields"]["HeaderMaterial"] == {"match [CCSI_DEFAULT_PROFILE]": 1}
    assert dx["fields"]["CoilType"] == {"not_on_report [CCSI_DEFAULT_PROFILE]": 1}
    assert dx["fields"]["NumberOfFeeds"] == {"mismatch (changed at order)": 1}
    assert [r["ccsi_id"] for r in dx["rows"]] == ["NumberOfFeeds"]
    assert "changed at order" in batch.render_markdown("DX", dx)


def _pretend_cloud_only(monkeypatch, names: set[str]) -> None:
    monkeypatch.setattr(batch, "_is_cloud_only", lambda entry: entry.name in names)


def test_a_cloud_only_submittal_is_never_read(tmp_path, monkeypatch) -> None:
    fw = tmp_path / "Final Working"
    _touch(fw / "P - Oxygen8 Submittal - X - Rev0.pdf", b"rev0")
    _touch(fw / "P - Oxygen8 Submittal - X - Rev1.pdf", b"rev1")
    _pretend_cloud_only(monkeypatch, {"P - Oxygen8 Submittal - X - Rev1.pdf"})
    reads: list[str] = []
    real_sha1 = batch._sha1
    monkeypatch.setattr(batch, "_sha1", lambda p: reads.append(p.name) or real_sha1(p))
    # the highest Rev is a placeholder: skipping beats silently falling back to Rev0
    assert batch.pick_submittal(tmp_path, {}) == (None, "cloud_only_submittal")
    assert "P - Oxygen8 Submittal - X - Rev1.pdf" not in reads


def test_a_project_with_a_cloud_only_report_is_not_judged_locally(tmp_path, monkeypatch) -> None:
    forms = tmp_path / "Accessory Order Forms"
    _touch(forms / "DirectCoil" / "P_X_REV1_9_9_2026,1_47_30_PM.pdf", b"not really a pdf")
    _pretend_cloud_only(monkeypatch, {"P_X_REV1_9_9_2026,1_47_30_PM.pdf"})
    scanned = batch.scan_reports(tmp_path)
    assert scanned["skip"] == "cloud_only_reports"
    assert scanned["cloud_only"] == ["Accessory Order Forms/DirectCoil/P_X_REV1_9_9_2026,1_47_30_PM.pdf"]


def test_degraded_pages_only_block_when_they_reach_the_coil_pages() -> None:
    cand = {"tag": {"value": "CDXC-1", "source_evidence": [{"source_page": 4}]},
            "geometry": {"rows": {"source_evidence": [{"source_page": 5}, {"source_page": None}]}}}
    assert batch.coil_page_reach([cand], cover_page=2) == 5 + batch._COIL_PAGE_MARGIN
    assert batch.coil_page_reach([{"tag": None}], cover_page=None) is None  # no evidence -> nothing proven


def test_long_paths_get_the_extended_prefix_on_windows() -> None:
    import os
    text = batch.long_path(Path("C:/x") / ("a" * 300))
    assert text.startswith("\\\\?\\") if os.name == "nt" else text.endswith("a" * 300)


@pytest.mark.parametrize("out_dir", [batch.OUT_DIR])
def test_output_dir_is_gitignored(out_dir) -> None:
    rel = out_dir.relative_to(ROOT).as_posix() + "/"
    assert rel in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


# --- Signed Final by cover (John 2026-10-01, decision A) --------------------------------------------
def _covers(monkeypatch, mapping: dict[str, str | tuple[str, tuple[int, str, int]]]) -> list[str]:
    """Pretend these Signed Final file names carry an Oxygen8 cover: project, or (project, cover Rev)."""
    opened: list[str] = []

    def fake(path):
        opened.append(path.name)
        value = mapping.get(path.name)
        return None if value is None else (value if isinstance(value, tuple) else (value, (0, "", 0)))

    monkeypatch.setattr(batch, "signed_cover", fake)
    return opened


def test_a_signed_copy_with_this_projects_cover_beats_the_final_working_name_pick(tmp_path, monkeypatch) -> None:
    """2982: the engineer-named As-built copy (CDXC-2 RH, as ordered) lost to Final Working Rev0 (LH)."""
    _touch(tmp_path / "Final Working" / "2982 - Oxygen8 Submittal - X - RevS0.pdf", b"rev0")
    signed = _touch(tmp_path / "Signed Final Submittal" / "95 Berkely - ERVs REV0 - AAN (002).pdf", b"signed")
    _touch(tmp_path / "Signed Final Submittal" / "ProductionRelease - 2982 - ERV-2.pdf", b"release")
    _covers(monkeypatch, {"95 Berkely - ERVs REV0 - AAN (002).pdf": "2982"})
    assert batch.pick_submittal(tmp_path, {}, "2982") == (signed, "signed_final_cover")
    # without a project number the content tier cannot run: the name rules decide, as before
    assert batch.pick_submittal(tmp_path, {})[1] == "heuristic_highest_rev"


def test_a_cover_for_another_project_is_not_this_projects_submittal(tmp_path, monkeypatch) -> None:
    _touch(tmp_path / "Final Working" / "P - Oxygen8 Submittal - X - Rev1.pdf", b"rev1")
    _touch(tmp_path / "Signed Final Submittal" / "shop drawings.pdf", b"other")
    _covers(monkeypatch, {"shop drawings.pdf": "2955"})
    assert batch.pick_submittal(tmp_path, {}, "2954")[1] == "heuristic_highest_rev"


def test_two_different_covered_signed_copies_are_never_guessed_between(tmp_path, monkeypatch) -> None:
    _touch(tmp_path / "Signed Final Submittal" / "a.pdf", b"one")
    _touch(tmp_path / "Signed Final Submittal" / "b.pdf", b"two")
    _covers(monkeypatch, {"a.pdf": "3001", "b.pdf": "3001"})
    assert batch.pick_submittal(tmp_path, {}, "3001") == (None, "ambiguous_submittal")


def test_the_oxygen8_original_beats_any_stamped_copy_and_the_highest_revision_wins_among_originals(
        tmp_path, monkeypatch) -> None:
    """A stamp over the text can split numbers (2814's stamped Rev0 read 2300 CFM as "2"), so an
    Oxygen8-named original wins whenever one is filed; the stamped copy only when none is (2982)."""
    sf = tmp_path / "Signed Final Submittal"
    rev1 = _touch(sf / "P - Oxygen8 Submittal - X - Rev1.pdf", b"rev1")
    as_built = _touch(sf / "P - Oxygen8 Submittal - X - Rev1_AsBuilt.pdf", b"asbuilt")
    stamped = _touch(sf / "2814 SIGNED - Closed.pdf", b"stamped")
    _covers(monkeypatch, {rev1.name: ("2814", (1, "", 0)), as_built.name: ("2814", (1, "", 1)),
                          stamped.name: ("2814", (5, "", 0))})
    assert batch.pick_submittal(tmp_path, {}, "2814") == (as_built, "signed_final_cover")
    _covers(monkeypatch, {stamped.name: ("2814", (0, "", 0))})
    assert batch.pick_submittal(tmp_path, {}, "2814") == (stamped, "signed_final_cover")


def test_the_cover_revision_is_read_from_the_revision_no_field() -> None:
    """3031's As-built footer says "Rev #0" while its Revision No. is 2a; 2814 prints "1_AsBuilt"."""
    key = batch.cover_revision_key
    assert key("Ship To Revision No.: 2a\nDate") == (2, "a", 0)
    assert key("Revision No.: 1_AsBuilt") == (1, "", 1)
    assert key("Project: 2982 Ship To Revision No.: As built") == (-1, "", 1)
    assert key("Revision No.: 0") == (0, "", 0)
    assert key("no field here") == (-1, "", 0)
    assert key("Revision No.: 1_AsBuilt") > key("Revision No.: 1") > key("Revision No.: 0a")


def test_a_cloud_only_signed_copy_is_never_opened_and_the_ledger_still_wins(tmp_path, monkeypatch) -> None:
    import hashlib
    fw = _touch(tmp_path / "Final Working" / "P - Oxygen8 Submittal - X - Rev0.pdf", b"rev0")
    _touch(tmp_path / "Signed Final Submittal" / "signed.pdf", b"signed")
    _pretend_cloud_only(monkeypatch, {"signed.pdf"})
    opened = _covers(monkeypatch, {"signed.pdf": "3001"})
    assert batch.pick_submittal(tmp_path, {}, "3001")[1] == "heuristic_highest_rev"
    assert "signed.pdf" not in opened
    ledger = {hashlib.sha1(b"rev0").hexdigest(): "2026-09-01T00:00:00Z"}
    assert batch.pick_submittal(tmp_path, ledger, "3001") == (fw, "ledger_hash")


def test_the_cover_markers_match_a_real_oxygen8_cover_line() -> None:
    page = ("Qty Tag Item Model Voltage Installation Duct Connection Handing\n"
            "1 CDXC-2 DXC Cooling V60_O_ERV RH\nVersion 1.0.0.10 Project #2982 / Rev #0")
    assert batch._O8_COVER_HEADER.search(page)
    assert batch._O8_COVER_FOOTER.search(page).group(1) == "2982"
    assert not batch._O8_COVER_FOOTER.search("ProductionRelease - 2982 - 95 Berkeley - ERV-2")


def test_the_ledger_match_needs_no_submittal_name(tmp_path) -> None:
    """The sha1 of the file CoilForge ran on decides, whatever the engineer named the signed copy."""
    import hashlib
    _touch(tmp_path / "Final Working" / "P - Oxygen8 Submittal - X - Rev1.pdf", b"rev1")
    signed = _touch(tmp_path / "Signed Final Submittal" / "NFCS-237433-001-02-DA_CER.pdf", b"ran-this")
    ledger = {hashlib.sha1(b"ran-this").hexdigest(): "2026-09-20T00:00:00Z"}
    assert batch.pick_submittal(tmp_path, ledger) == (signed, "ledger_hash")
