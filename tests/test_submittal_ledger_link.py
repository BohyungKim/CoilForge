"""Ledger link + primary selection (John's rule, 2026-09-30).

Every test builds its OWN ledger through ``capture.db.connect`` (real migrations) at a
per-test path -- the conftest ledger is session-wide and route tests write into it, so
asserting exact contents there would depend on test order.

The folder shapes are the real ones found in the PO tree: 3232 (signed copy not named
as a submittal + hash-named twin), 3031 (As built / RevS*), 3183 (``Submittal rev2``),
3154 (Cover Page beside the Oxygen8 Rev0), 2954 (a 2955 file inside), 2496 (archived
higher Rev).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.capture import db  # noqa: E402
from coilforge.corpus import fs  # noqa: E402
from coilforge.corpus.ledger_link import (  # noqa: E402
    Assignment,
    LedgerPdf,
    LedgerState,
    PrimarySelection,
    ledger_candidates,
    ledger_path,
    load_assignments,
    load_ledger_pdfs,
    load_primaries,
    normalize_upload_name,
    select_primary,
    upload_name_hashes,
    write_assignments,
    write_primaries,
)
from coilforge.corpus.submittal_index import SubmittalPdfEntry, scan  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv(fs.ENV_INDEX_DIR, str(tmp_path / "index_data"))
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(tmp_path / "ledger" / "capture.sqlite3"))
    db.reset_caches_for_tests()
    yield
    db.reset_caches_for_tests()


def _ledger_run(conn, run_id, *, pdf: bytes, name: str | None, ts: str, project: str = "Dock Type"):
    conn.execute(
        "INSERT INTO run (run_id, ts_utc, milestone, input_hash, source_filename, code_version,"
        " capture_schema_version, project_number) VALUES (?,?,?,?,?,?,?,?)",
        (run_id, ts, "intake_drawing", hashlib.sha1(pdf).hexdigest(),
         db.sha256_text(name) if name else None, "test", 1, project),
    )
    conn.execute(
        "INSERT INTO artifact (run_id, kind, sha256, byte_len) VALUES (?,?,?,?)",
        (run_id, "submittal_pdf", hashlib.sha256(pdf).hexdigest(), len(pdf)),
    )


def _entry(path: str, *, cls="final_working", archived=False, o8=True, rev=(0, ""),
           as_built=False, reasons=("FOLDER_NUMBER",), size=100) -> SubmittalPdfEntry:
    return SubmittalPdfEntry(
        path=path, root="R", project_folder="P", folder_number="1000", project_number="1000",
        reasons=list(reasons), subfolder="S", subfolder_class=cls, archived=archived,
        name_has_submittal=True, oxygen8_named=o8, rev_key=rev, as_built=as_built,
        size=size, mtime_ns=0, cloud_only_at_scan=False, long_path=False,
    )


# --- ledger reading -------------------------------------------------------------------


def test_ledger_path_env_then_home_constant(monkeypatch, tmp_path):
    assert ledger_path() == tmp_path / "ledger" / "capture.sqlite3"
    monkeypatch.delenv(db.ENV_CAPTURE_DB)
    assert ledger_path() == Path.home() / "CoilForgeData" / "capture" / "coilforge.sqlite3"


def test_load_ledger_pdfs_groups_by_sha1_readonly(tmp_path):
    conn = db.connect()
    _ledger_run(conn, "r1", pdf=b"AAA", name="3232 - Rev1.pdf", ts="2026-09-01T00:00:00+00:00")
    _ledger_run(conn, "r2", pdf=b"AAA", name="renamed copy.pdf", ts="2026-09-03T00:00:00+00:00")
    _ledger_run(conn, "r3", pdf=b"BBBB", name=None, ts="2026-09-02T00:00:00+00:00")
    conn.execute(
        "INSERT INTO run (run_id, ts_utc, milestone, input_hash, code_version, capture_schema_version)"
        " VALUES ('r4','2026-09-04T00:00:00+00:00','mechanical_fit',NULL,'test',1)"
    )
    conn.commit()
    conn.close()

    pdfs = load_ledger_pdfs()
    a = pdfs[hashlib.sha1(b"AAA").hexdigest()]
    assert a.byte_len == 3
    assert a.name_sha256s == {db.sha256_text("3232 - Rev1.pdf"), db.sha256_text("renamed copy.pdf")}
    assert a.last_ts_utc == "2026-09-03T00:00:00+00:00"
    assert len(pdfs) == 2  # the hash-less run contributes nothing

    missing = tmp_path / "nope" / "capture.sqlite3"
    with pytest.raises(Exception):
        load_ledger_pdfs(missing)
    assert not missing.exists()  # mode=ro never creates a ledger


def test_normalize_upload_name_mirrors_sanitize_header_value():
    assert normalize_upload_name("a\r\nb.pdf") == "a  b.pdf"
    long_name = "x" * 200 + ".pdf"
    assert normalize_upload_name(long_name) == "x" * 180
    assert upload_name_hashes("short.pdf") == {db.sha256_text("short.pdf")}
    assert len(upload_name_hashes(long_name)) == 2


def test_candidates_by_name_hash_or_size(tmp_path):
    base = tmp_path / "02 - POs"
    (base / "3232 - Brooks" / "Final Working").mkdir(parents=True)
    (base / "3232 - Brooks" / "Final Working" / "3232 - Rev1.pdf").write_bytes(b"AAA")
    (base / "3232 - Brooks" / "Final Working" / "same size other.pdf").write_bytes(b"ZZZ")
    (base / "3232 - Brooks" / "Final Working" / "unrelated.pdf").write_bytes(b"QQQQQQ")
    index = scan(base)
    ledger = {
        hashlib.sha1(b"AAA").hexdigest(): LedgerPdf(
            sha1=hashlib.sha1(b"AAA").hexdigest(), sha256="x", byte_len=3,
            name_sha256s={db.sha256_text("3232 - Rev1.pdf")},
        )
    }
    candidates = ledger_candidates(index, ledger)
    names = sorted(Path(e.path).name for e in candidates[hashlib.sha1(b"AAA").hexdigest()])
    # the size twin is only a CANDIDATE; confirmation is by sha1 in the batch
    assert names == ["3232 - Rev1.pdf", "same size other.pdf"]


# --- select_primary: assignment ---------------------------------------------------------


def test_john_assignment_wins_and_survives_recompute():
    entries = [_entry("P/fw/Rev1.pdf", rev=(1, "")), _entry("P/sf/signed.pdf", cls="signed_final", o8=False)]
    assignment = Assignment(project="1000", path="P/sf/signed.pdf", sha1="s1", assigned_at="t")
    state = LedgerState(confirmed={"P/fw/Rev1.pdf": "l1"}, ledger={"l1": LedgerPdf("l1", "x", 1)})
    first = select_primary("1000", entries, state, assignment)
    assert first.reason == "JOHN_ASSIGNED" and first.primary_path == "P/sf/signed.pdf"
    # not hashed this run (e.g. cloud-only) -> John's pick, but unverified: not usable
    assert first.provisional and not first.usable
    # recompute after the batch read it: still John's pick, now verified and usable
    state.file_sha1["P/sf/signed.pdf"] = "s1"
    verified = select_primary("1000", entries, state, assignment)
    assert verified.reason == "JOHN_ASSIGNED" and verified.usable


def test_assignment_goes_stale_when_the_file_changes():
    assignment = Assignment(project="1000", path="P/sf/signed.pdf", sha1="s1", assigned_at="t")
    state = LedgerState(file_sha1={"P/sf/signed.pdf": "s2"})
    result = select_primary("1000", [_entry("P/sf/signed.pdf")], state, assignment)
    assert result.reason == "ASSIGNMENT_STALE" and result.primary_path is None and result.fail_closed


# --- select_primary: ledger (rule 1) ----------------------------------------------------


def test_ledger_match_even_when_archived():
    entries = [_entry("P/fw/Old/Rev0.pdf", archived=True), _entry("P/fw/Rev1.pdf", rev=(1, ""))]
    state = LedgerState(confirmed={"P/fw/Old/Rev0.pdf": "l0"}, ledger={"l0": LedgerPdf("l0", "x", 1)})
    result = select_primary("1000", entries, state)
    assert result.reason == "LEDGER_MATCH" and result.primary_path == "P/fw/Old/Rev0.pdf"


def test_ledger_several_sha1_latest_wins_and_copies_grouped():
    entries = [
        _entry("P/fw/Rev0.pdf"),
        _entry("P/fw/Rev1.pdf", rev=(1, "")),
        _entry("P/sf/Rev1.pdf", cls="signed_final", rev=(1, "")),
    ]
    ledger = {
        "l0": LedgerPdf("l0", "x", 1, last_ts_utc="2026-09-01"),
        "l1": LedgerPdf("l1", "x", 1, last_ts_utc="2026-09-05"),
    }
    state = LedgerState(
        ledger=ledger, confirmed={"P/fw/Rev0.pdf": "l0", "P/fw/Rev1.pdf": "l1", "P/sf/Rev1.pdf": "l1"}
    )
    result = select_primary("1000", entries, state)
    assert result.reason == "LEDGER_MATCH_LATEST"
    assert result.primary_sha1 == "l1"
    assert result.primary_path == "P/sf/Rev1.pdf"  # signed_final copy ranks first
    assert result.copies == ["P/fw/Rev1.pdf"]
    assert [r.reason for r in result.rejected] == ["LEDGER_OLDER"]


def test_ledger_file_with_number_conflict_is_fail_closed():
    entries = [_entry("P/fw/2955 - Rev6.pdf", reasons=("FOLDER_NUMBER", "NUMBER_CONFLICT"))]
    state = LedgerState(confirmed={"P/fw/2955 - Rev6.pdf": "l5"}, ledger={"l5": LedgerPdf("l5", "x", 1)})
    result = select_primary("2954", entries, state)
    assert result.reason == "NUMBER_CONFLICT" and result.primary_path is None and result.fail_closed


def test_ledger_provisional_for_cloud_only_candidate():
    entries = [_entry("P/fw/Rev1.pdf", rev=(1, ""))]
    result = select_primary("1000", entries, LedgerState(provisional={"P/fw/Rev1.pdf"}))
    assert result.reason == "LEDGER_PROVISIONAL" and result.provisional
    assert not result.usable  # a name/size candidate is never consumable as final


# --- select_primary: signed final / final working (rules 2, 3) -----------------------------


def test_signed_final_highest_eligible_rev():
    entries = [
        _entry("P/sf/Rev3.pdf", cls="signed_final", rev=(3, "")),
        _entry("P/sf/Rev3a.pdf", cls="signed_final", rev=(3, "a")),
        _entry("P/sf/HRU-06 PRF Rev3a.pdf", cls="signed_final", o8=False, rev=(3, "a")),
        _entry("P/fw/Rev6.pdf", rev=(6, "")),
    ]
    result = select_primary("2954", entries, LedgerState())
    assert result.reason == "SIGNED_FINAL" and result.primary_path == "P/sf/Rev3a.pdf"
    assert {(r.path, r.reason) for r in result.rejected} == {
        ("P/sf/HRU-06 PRF Rev3a.pdf", "NOT_OXYGEN8_NAMED"),
        ("P/sf/Rev3.pdf", "LOWER_REV"),
    }


def test_3232_shape_signed_unrecognized_does_not_fall_through():
    entries = [
        _entry("P/fw/Rev1.pdf", rev=(1, "")),
        _entry("P/sf/3232 - E-One Plant 4.pdf", cls="signed_final", o8=False, rev=None),
        _entry("P/sf/d625655dc9.pdf", cls="signed_final", o8=False, rev=None),
    ]
    result = select_primary("3232", entries, LedgerState())
    assert result.reason == "SIGNED_FINAL_UNRECOGNIZED" and result.primary_path is None
    assert {r.reason for r in result.rejected} == {"NOT_OXYGEN8_NAMED"}


def test_3031_shape_project_and_file_reasons():
    entries = [
        _entry("P/fw/RevS0.pdf", rev=None),
        _entry("P/sf/As built.pdf", cls="signed_final", rev=None, as_built=True),
        _entry("P/sf/Archive/RevS2a.pdf", cls="signed_final", rev=None, archived=True),
        _entry("P/sf/ProductionRelease.pdf", cls="signed_final", o8=False, rev=None),
    ]
    result = select_primary("3031", entries, LedgerState())
    assert result.reason == "SIGNED_FINAL_UNRECOGNIZED"
    assert {(Path(r.path).name, r.reason) for r in result.rejected} == {
        ("As built.pdf", "AS_BUILT"),
        ("RevS2a.pdf", "ARCHIVED"),
        ("ProductionRelease.pdf", "NOT_OXYGEN8_NAMED"),
    }


def test_3183_shape_submittal_rev2_is_not_oxygen8_named():
    entries = [
        _entry("P/fw/Rev1.pdf", rev=(1, "")),
        _entry("P/sf/11 - Lovett - Oxygen8_DOAS - Submittal rev2.pdf", cls="signed_final", o8=False, rev=(2, "")),
    ]
    assert select_primary("3183", entries, LedgerState()).reason == "SIGNED_FINAL_UNRECOGNIZED"


def test_as_built_with_a_rev_is_never_auto_picked():
    entries = [_entry("P/fw/Rev3_AsBuilt.pdf", rev=(3, ""), as_built=True)]
    result = select_primary("1000", entries, LedgerState())
    assert result.reason == "NO_SUBMITTAL" and result.rejected[0].reason == "AS_BUILT"


def test_3154_shape_cover_page_is_ineligible_and_final_working_picks_rev0():
    entries = [
        _entry("P/fw/3154 - Oxygen8 Submittal - Rev0.pdf"),
        _entry("P/fw/Residential Submittal Cover Page - 3154 - Rev0.pdf", o8=False),
    ]
    result = select_primary("3154", entries, LedgerState())
    assert result.reason == "FINAL_WORKING_LATEST_REV"
    assert result.primary_path == "P/fw/3154 - Oxygen8 Submittal - Rev0.pdf"


def test_2496_shape_archived_higher_rev_is_fail_closed():
    entries = [
        _entry("P/sf/Archive/Rev4.pdf", cls="signed_final", rev=(4, ""), archived=True),
        _entry("P/sf/Rev1a.pdf", cls="signed_final", rev=(1, "a")),
    ]
    result = select_primary("2496", entries, LedgerState())
    assert result.reason == "ARCHIVED_HIGHER_REV" and result.primary_path is None


def test_tie_is_ambiguous_unless_known_identical_copies():
    entries = [
        _entry("P/fw/A - Rev2.pdf", rev=(2, "")),
        _entry("P/fw/B - Rev2.pdf", rev=(2, "")),
    ]
    assert select_primary("1000", entries, LedgerState()).reason == "REVISION_AMBIGUOUS"
    different = LedgerState(file_sha1={"P/fw/A - Rev2.pdf": "h1", "P/fw/B - Rev2.pdf": "h2"})
    assert select_primary("1000", entries, different).reason == "REVISION_AMBIGUOUS"
    same = LedgerState(file_sha1={"P/fw/A - Rev2.pdf": "h1", "P/fw/B - Rev2.pdf": "h1"})
    result = select_primary("1000", entries, same)
    assert result.reason == "FINAL_WORKING_LATEST_REV" and len(result.copies) == 1


def test_no_submittal_and_duplicate_folder_flag():
    assert select_primary("1000", [], LedgerState()).reason == "NO_SUBMITTAL"
    entries = [_entry("P/fw/Rev0.pdf", reasons=("FOLDER_NUMBER", "DUPLICATE_FOLDER_NUMBER"))]
    result = select_primary("1901", entries, LedgerState())
    assert result.reason == "FINAL_WORKING_LATEST_REV" and result.duplicate_folder_number
    assert result.usable


def test_two_folders_sharing_a_number_are_fail_closed_for_tiers_but_not_ledger():
    dup = ("FOLDER_NUMBER", "DUPLICATE_FOLDER_NUMBER")
    first = _entry("A/fw/1901 - Oxygen8 Submittal - Rev0.pdf", reasons=dup)
    second = _entry("B/fw/1901 - Oxygen8 Submittal - Rev3.pdf", rev=(3, ""), reasons=dup)
    first = first.model_copy(update={"project_folder": "1901 - First"})
    second = second.model_copy(update={"project_folder": "1901 - Second"})
    result = select_primary("1901", [first, second], LedgerState())
    # Rev3 must not win just because it sits in the other project's folder.
    assert result.reason == "DUPLICATE_FOLDER_NUMBER" and result.fail_closed and not result.usable
    # The exact file CoilForge saw is still a sound pick.
    state = LedgerState(confirmed={first.path: "l0"}, ledger={"l0": LedgerPdf("l0", "x", 1)})
    assert select_primary("1901", [first, second], state).reason == "LEDGER_MATCH"


# --- persistence ------------------------------------------------------------------------


def test_primaries_and_assignments_round_trip(tmp_path):
    data = tmp_path / "data"
    selections = [
        PrimarySelection(project="3232", reason="SIGNED_FINAL_UNRECOGNIZED"),
        PrimarySelection(project="2954", primary_path="p", reason="SIGNED_FINAL"),
    ]
    target = write_primaries(selections, data)
    loaded = load_primaries(data)
    assert list(loaded) == ["2954", "3232"] and loaded["3232"].fail_closed
    # consumers that read the JSON (not the model) get the same verdict
    rows = {row["project"]: row["usable"] for row in json.loads(target.read_text(encoding="utf-8"))}
    assert rows == {"2954": True, "3232": False}

    assert load_assignments(data) == {}
    assignments = {"3232": Assignment(project="3232", path="p", sha1="s", assigned_at="t")}
    write_assignments(assignments, data)
    assert load_assignments(data) == assignments
