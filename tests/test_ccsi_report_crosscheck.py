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
