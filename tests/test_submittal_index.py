"""Submittal PDF index: metadata-only scan of a fake PO tree.

Pins the name parsing on REAL filename shapes (always with ``.pdf`` attached -- a
regex applied to the full name once read ``Rev1.pdf`` as ``(1,'p')`` and ranked it
above ``Rev1a``), the project-number rules, the no-bytes-read guarantee, long paths,
and the out-of-repo data directory.
"""
from __future__ import annotations

import builtins
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.corpus import fs  # noqa: E402
from coilforge.corpus.fs import (  # noqa: E402
    SubmittalIndexConfigError,
    default_data_dir,
    is_cloud_only,
    long_path,
)
from coilforge.corpus.submittal_index import (  # noqa: E402
    entries_for_project,
    filename_numbers,
    is_as_built,
    is_oxygen8_named,
    load_index,
    rev_key,
    scan,
    write_index,
)


@pytest.fixture(autouse=True)
def _isolated_index_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(fs.ENV_INDEX_DIR, str(tmp_path / "index_data"))


def _touch(path: Path, data: bytes = b"%PDF-1.4 fake") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


# --- rev_key: full filenames, ordering ------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("3232 - Oxygen8 Submittal - Brooks - 3232 - E-One Plant 4 - Rev1.pdf", (1, "")),
        ("X - Oxygen8 Submittal - Rev0a.pdf", (0, "a")),
        ("X - Oxygen8 Submittal - Rev0.a.pdf", (0, "a")),
        ("11 - 1110 Lovett - Oxygen8_DOAS - Submittal rev2.pdf", (2, "")),
        ("X - Oxygen8 Submittal - Rev3_AsBuilt.pdf", (3, "")),
        ("X - Oxygen8 Submittal - RevS0.pdf", None),
        ("X - Oxygen8 Submittal - RevS2a.pdf", None),
        ("X - Oxygen8 Submittal - As built.pdf", None),
        ("X - Oxygen8 Submittal - Preview.pdf", None),
        ("X - Rev1 - Rev2.pdf", None),
    ],
)
def test_rev_key_on_real_name_shapes(name, expected):
    assert rev_key(name) == expected


def test_rev_key_never_reads_the_pdf_extension_as_a_letter():
    # The BLOCKER regression: ".p" of ".pdf" must not become the revision letter.
    assert rev_key("2496 - Oxygen8 Submittal - Rev4.pdf") == (4, "")
    assert rev_key("2496 - Oxygen8 Submittal - Rev4.pdf") != (4, "p")


def test_rev_key_ordering_on_full_filenames():
    assert rev_key("A - Rev0.pdf") < rev_key("A - Rev0a.pdf")
    assert rev_key("A - Rev2.a.pdf") == rev_key("A - Rev2a.pdf")
    assert rev_key("A - Rev3.pdf") < rev_key("A - Rev3a.pdf")
    assert rev_key("A - Rev4.pdf") < rev_key("A - Rev4a.pdf")  # no TypeError
    assert rev_key("A - Rev9b.pdf") < rev_key("A - Rev10.pdf")


def test_as_built_and_oxygen8_name_flags():
    assert is_as_built("X - Rev3_AsBuilt.pdf")
    assert is_as_built("3031 - Oxygen8 Submittal - As built.pdf")
    assert not is_as_built("X - Phase Built - Rev1.pdf")
    assert is_oxygen8_named("2727 - O8 Submittal - Stinebaugh - Rev1.pdf")
    assert is_oxygen8_named("3232 - Oxygen8 Submittal - Brooks - Rev1.pdf")
    assert not is_oxygen8_named("11 - 1110 Lovett - Oxygen8_DOAS - Submittal rev2.pdf")
    assert not is_oxygen8_named("Residential Submittal Cover Page - 3154 - Rev0.pdf")


# --- filename numbers -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("26040533 - Oxygen8 Submittal - NSW Climatec - Anaheim - 3262 - LA Care - Rev3.pdf", ["3262"]),
        ("2026-7-8 Oxygen8 Submittal - Rep - 3064 - Job - Rev0.pdf", ["3064"]),
        ("SIGNED 2808 - Oxygen8 Submittal - Mechanical Sales - 2808 - Premiere - Rev0.pdf", ["2808"]),
        ("Oxygen8 Submittal - TriState - 2572 - Bowie State - Rev4a - Approved.pdf", ["2572"]),
        ("2131a - Oxygen8 Submittal - Rep - Rev0.pdf", ["2131a"]),
        ("20260417100514146.pdf", []),
        ("3232 - E-One Plant 4.pdf", ["3232"]),
    ],
)
def test_filename_numbers_count_whole_segments_only(name, expected):
    assert filename_numbers(name) == expected


# --- scan -------------------------------------------------------------------------------


@pytest.fixture()
def po_tree(tmp_path) -> Path:
    base = tmp_path / "02 - POs"
    fw = "Final Working"
    sf = "Signed Final Submittal"
    _touch(base / "3232 - Brooks - E-One Plant 4" / fw / "3232 - Oxygen8 Submittal - Brooks - 3232 - E-One Plant 4 - Rev1.pdf")
    _touch(base / "3232 - Brooks - E-One Plant 4" / sf / "3232 - E-One Plant 4.pdf")
    _touch(base / "2954 - Rep - Job" / fw / "Rev3 6" / "2955 - Oxygen8 Submittal - Rep - 2955 - DRY - Rev6.pdf")
    _touch(base / "2954 - Rep - Job" / fw / "Old" / "2954 - Oxygen8 Submittal - Rep - Rev0.pdf")
    _touch(base / "3262 - NSW - LA Care" / fw / "26040533 - Oxygen8 Submittal - NSW - 3262 - LA Care - Rev3.pdf")
    _touch(base / "3079 -" / "3079 - Oxygen8 Submittal - Loose - Rev0.pdf")
    _touch(base / "2082" / "Customer PO and Quote" / "2082 - Oxygen8 Submittal - Rev0.pdf")
    _touch(base / "1901 - First" / fw / "1901 - Oxygen8 Submittal - Rev0.pdf")
    _touch(base / "1901 - Second" / fw / "1901 - Oxygen8 Submittal - Rev1.pdf")
    _touch(base / "X#### - REP FIRM - PROJECT NAME" / fw / "template.pdf")
    _touch(base / "New folder" / "stray.pdf")
    _touch(base / "3232 - Brooks - E-One Plant 4" / fw / "notes.txt")
    return base


def test_scan_indexes_every_pdf_with_project_rules(po_tree):
    index = scan(po_tree)
    by_name = {Path(e.path).name: e for e in index.entries}

    assert "notes.txt" not in by_name
    assert len(index.entries) == 11
    assert index.scan_errors == []

    signed = by_name["3232 - E-One Plant 4.pdf"]
    assert signed.project_number == "3232"
    assert signed.subfolder_class == "signed_final"
    assert signed.name_has_submittal is False  # indexed anyway
    assert signed.oxygen8_named is False

    rep_first = by_name["26040533 - Oxygen8 Submittal - NSW - 3262 - LA Care - Rev3.pdf"]
    assert rep_first.project_number == "3262"
    assert rep_first.reasons == ["FOLDER_NUMBER"]

    conflict = by_name["2955 - Oxygen8 Submittal - Rep - 2955 - DRY - Rev6.pdf"]
    assert conflict.project_number == "2954"
    assert "NUMBER_CONFLICT" in conflict.reasons
    assert conflict.subfolder == "Final Working"
    assert conflict.archived is False

    archived = by_name["2954 - Oxygen8 Submittal - Rep - Rev0.pdf"]
    assert archived.archived is True

    assert by_name["3079 - Oxygen8 Submittal - Loose - Rev0.pdf"].subfolder_class == "project_root"
    assert by_name["3079 - Oxygen8 Submittal - Loose - Rev0.pdf"].project_number == "3079"
    assert by_name["2082 - Oxygen8 Submittal - Rev0.pdf"].subfolder_class == "customer_po"
    assert by_name["template.pdf"].reasons == ["NO_NUMBER"]
    assert by_name["stray.pdf"].project_number is None

    dup = [e for e in index.entries if e.folder_number == "1901"]
    assert len(dup) == 2 and all("DUPLICATE_FOLDER_NUMBER" in e.reasons for e in dup)
    assert "DUPLICATE_FOLDER_NUMBER" not in signed.reasons

    assert {Path(e.path).name for e in entries_for_project(index, "3232")} == {
        "3232 - Oxygen8 Submittal - Brooks - 3232 - E-One Plant 4 - Rev1.pdf",
        "3232 - E-One Plant 4.pdf",
    }


def test_scan_reads_no_pdf_bytes(po_tree, monkeypatch):
    real_open = builtins.open

    def guarded_open(file, *args, **kwargs):
        if str(file).lower().endswith(".pdf"):
            raise AssertionError(f"scan opened a PDF: {file}")
        return real_open(file, *args, **kwargs)

    def guarded_read_bytes(self):
        raise AssertionError(f"scan read bytes: {self}")

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    assert len(scan(po_tree).entries) == 11


def test_extra_roots_use_filename_numbers_and_must_be_absolute(tmp_path):
    extra = tmp_path / "submittals"
    _touch(extra / "2775 - Oxygen8 Submittal - Air Reps - 2775 CBRE - Airline 2 - Rev0.pdf")
    _touch(extra / "20260417100514146.pdf")
    _touch(extra / "2954, 2955 - Two - 2954 - 2955 - Rev0.pdf")

    index = scan(None, [extra])
    by_name = {Path(e.path).name: e for e in index.entries}
    assert by_name["2775 - Oxygen8 Submittal - Air Reps - 2775 CBRE - Airline 2 - Rev0.pdf"].project_number == "2775"
    assert by_name["20260417100514146.pdf"].reasons == ["NO_NUMBER"]
    ambiguous = by_name["2954, 2955 - Two - 2954 - 2955 - Rev0.pdf"]
    assert ambiguous.project_number is None
    assert ambiguous.reasons == ["FILENAME_NUMBER_AMBIGUOUS"]

    with pytest.raises(ValueError):
        scan(None, ["relative/submittals"])


def test_cloud_only_truth_table():
    assert is_cloud_only(0x400020)
    assert is_cloud_only(0x40000)
    assert is_cloud_only(0x1000)
    assert not is_cloud_only(0x20)
    assert not is_cloud_only(0)


@pytest.mark.skipif(os.name != "nt", reason="MAX_PATH is a Windows limit")
def test_long_path_is_indexed_and_readable(tmp_path):
    base = tmp_path / "02 - POs"
    deep = base / "3999 - Rep - Long"
    for _ in range(12):
        deep = deep / ("x" * 20)
    target = Path(long_path(deep / "3999 - Oxygen8 Submittal - Rev0.pdf"))
    os.makedirs(target.parent, exist_ok=True)
    target.write_bytes(b"%PDF long")
    try:
        index = scan(base)
        assert len(index.entries) == 1
        entry = index.entries[0]
        assert entry.long_path is True
        assert not entry.path.startswith("\\\\?\\")
        assert fs.read_pdf_bytes(entry.path) == b"%PDF long"
    finally:
        shutil.rmtree(long_path(base))  # pytest's own cleanup cannot remove >260 paths


def test_index_round_trip_and_failed_write_keeps_previous(tmp_path, po_tree, monkeypatch):
    data_dir = tmp_path / "data"
    index = scan(po_tree)
    write_index(index, data_dir)
    assert load_index(data_dir) == index

    def failing_replace(*_args, **_kwargs):
        raise OSError("replace refused")

    monkeypatch.setattr(os, "replace", failing_replace)
    with pytest.raises(OSError):
        write_index(scan(None, []), data_dir)
    monkeypatch.undo()
    assert load_index(data_dir) == index
    assert [p.name for p in data_dir.iterdir()] == ["index.json"]  # temp file cleaned up


def _fake_checkout(tmp_path: Path) -> Path:
    """A directory that looks like a git checkout (a ``.git`` marker), so the guard is
    tested without depending on where this test file happens to live."""
    repo = tmp_path / "checkout"
    (repo / ".git").mkdir(parents=True)
    return repo


def test_data_dir_defaults_outside_repo_and_refuses_a_repo_path(tmp_path, monkeypatch):
    monkeypatch.delenv(fs.ENV_INDEX_DIR, raising=False)
    assert default_data_dir() == Path.home() / "CoilForgeData" / "submittal_index"

    monkeypatch.setenv(fs.ENV_INDEX_DIR, str(_fake_checkout(tmp_path) / "outputs" / "submittal_index"))
    with pytest.raises(SubmittalIndexConfigError, match=fs.ENV_INDEX_DIR):
        default_data_dir()


def test_explicit_index_dir_is_guarded_too(tmp_path):
    # --index-dir must not be a way to write raw submittal text into the checkout.
    with pytest.raises(SubmittalIndexConfigError):
        fs.resolve_data_dir(_fake_checkout(tmp_path) / "outputs" / "x")
    assert fs.resolve_data_dir(tmp_path / "ok") == tmp_path / "ok"
