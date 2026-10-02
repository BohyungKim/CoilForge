"""Link the capture ledger's submittal PDFs to indexed files, and pick each project's
primary submittal by John's rule (2026-09-30).

The ledger stores no path: only ``run.input_hash`` (sha1 of the bytes),
``run.source_filename`` (sha256 of the uploaded NAME) and the ``submittal_pdf``
artifact's ``byte_len``. Candidates are narrowed without any download by name hash or
size, then CONFIRMED by sha1 (local files immediately; cloud-only files when the batch
reads them). A size match alone never counts -- 1,078 sizes are shared in the PO tree.

``select_primary`` is John's rule and nothing more:
  0. John's explicit assignment (``--assign``) wins over every rule.
  1. ledger match (the exact file CoilForge saw); several -> latest ``ts_utc``.
  2. Signed Final Submittal, highest Rev among ELIGIBLE files.
  3. Final Working, highest Rev among ELIGIBLE files.
Eligible (2/3 only) = not archived, Oxygen8-named, parseable Rev, not as-built, no
number conflict. Anything else is fail-closed: no pick, a reason, and John assigns.
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from coilforge.capture.db import sha256_text
from coilforge.corpus.fs import atomic_write_text, long_path
from coilforge.corpus.submittal_index import SubmittalIndex, SubmittalPdfEntry

ENV_CAPTURE_DB = "COILFORGE_CAPTURE_DB"
PRIMARIES_FILENAME = "primaries.json"
ASSIGNMENTS_FILENAME = "assignments.json"

# Only runs that carried submittal bytes have this artifact (intake_draft / intake_drawing /
# checklist_filled / project_review); input_hash is sha1 of the same bytes.
_LEDGER_PDFS_SQL = """
select r.input_hash, r.source_filename, r.ts_utc, a.sha256, a.byte_len
from run r
join artifact a on a.run_id = r.run_id and a.kind = 'submittal_pdf'
where r.input_hash is not null
"""

ProjectReason = Literal[
    "JOHN_ASSIGNED",
    "ASSIGNMENT_STALE",
    "LEDGER_MATCH",
    "LEDGER_MATCH_LATEST",
    "LEDGER_PROVISIONAL",
    "SIGNED_FINAL",
    "FINAL_WORKING_LATEST_REV",
    "SIGNED_FINAL_UNRECOGNIZED",
    "NUMBER_CONFLICT",
    "REVISION_AMBIGUOUS",
    "ARCHIVED_HIGHER_REV",
    "DUPLICATE_FOLDER_NUMBER",
    "NO_SUBMITTAL",
]
FAIL_CLOSED_REASONS = frozenset(
    {
        "ASSIGNMENT_STALE",
        "SIGNED_FINAL_UNRECOGNIZED",
        "NUMBER_CONFLICT",
        "REVISION_AMBIGUOUS",
        "ARCHIVED_HIGHER_REV",
        "DUPLICATE_FOLDER_NUMBER",
        "NO_SUBMITTAL",
    }
)


def ledger_path() -> Path:
    """``COILFORGE_CAPTURE_DB`` or ``~/CoilForgeData/capture/coilforge.sqlite3``.

    Deliberately NOT ``capture.db.capture_db_path()`` (whose committed default was
    ``%LOCALAPPDATA%`` -- the MSIX redirect trap) and never a command-line argument
    (the ledger filename contains ``sqlite3``, which the protected-asset hook reads
    in command text).
    """
    raw = os.environ.get(ENV_CAPTURE_DB, "").strip()
    return Path(raw) if raw else Path.home() / "CoilForgeData" / "capture" / "coilforge.sqlite3"


def normalize_upload_name(name: str) -> str:
    """Mirror ``web/app.js::sanitizeHeaderValue``: CR/LF -> space, first 180 UTF-16 units."""
    text = str(name or "").replace("\r", " ").replace("\n", " ")
    encoded = text.encode("utf-16-le", "surrogatepass")
    if len(encoded) > 360:
        text = encoded[:360].decode("utf-16-le", "surrogatepass")
    return text


def upload_name_hashes(name: str) -> set[str]:
    """Hashes the ledger could hold for a file of this name: the browser upload path
    (sanitized header) and the case path (``pdf_path.name`` as-is)."""
    return {sha256_text(name), sha256_text(normalize_upload_name(name))}


@dataclass
class LedgerPdf:
    sha1: str
    sha256: str
    byte_len: int | None
    name_sha256s: set[str] = field(default_factory=set)
    last_ts_utc: str = ""


def load_ledger_pdfs(path: Path | None = None) -> dict[str, LedgerPdf]:
    """Read the ledger's submittal PDFs, read-only (``mode=ro`` cannot create a file)."""
    target = path or ledger_path()
    uri = Path(target).resolve().as_uri() + "?mode=ro"  # as_uri percent-encodes ?, #, %
    conn = sqlite3.connect(uri, uri=True)
    try:
        rows = conn.execute(_LEDGER_PDFS_SQL).fetchall()
    finally:
        conn.close()
    pdfs: dict[str, LedgerPdf] = {}
    for sha1, name_hash, ts, sha256, byte_len in rows:
        pdf = pdfs.setdefault(sha1, LedgerPdf(sha1=sha1, sha256=sha256, byte_len=byte_len))
        if name_hash:
            pdf.name_sha256s.add(name_hash)
        if ts and ts > pdf.last_ts_utc:
            pdf.last_ts_utc = ts
    return pdfs


def ledger_candidates(
    index: SubmittalIndex, ledger: dict[str, LedgerPdf]
) -> dict[str, list[SubmittalPdfEntry]]:
    """Entries that MAY be a ledger PDF (name hash or size), keyed by ledger sha1."""
    by_name: dict[str, set[str]] = {}
    by_size: dict[int, set[str]] = {}
    for pdf in ledger.values():
        for name_hash in pdf.name_sha256s:
            by_name.setdefault(name_hash, set()).add(pdf.sha1)
        if pdf.byte_len is not None:
            by_size.setdefault(pdf.byte_len, set()).add(pdf.sha1)
    candidates: dict[str, list[SubmittalPdfEntry]] = {}
    for entry in index.entries:
        hits = set(by_size.get(entry.size, set()))
        for name_hash in upload_name_hashes(os.path.basename(entry.path)):
            hits |= by_name.get(name_hash, set())
        for sha1 in hits:
            candidates.setdefault(sha1, []).append(entry)
    return candidates


# --- assignments --------------------------------------------------------------------


class Assignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: str
    path: str
    sha1: str
    assigned_at: str


class SelectionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    reason: str


class PrimarySelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: str
    primary_path: str | None = None
    primary_sha1: str | None = None
    reason: ProjectReason
    provisional: bool = False
    duplicate_folder_number: bool = False
    copies: list[str] = Field(default_factory=list)
    rejected: list[SelectionRecord] = Field(default_factory=list)

    @property
    def fail_closed(self) -> bool:
        return self.reason in FAIL_CLOSED_REASONS

    @property
    def usable(self) -> bool:
        """The ONLY state a consumer may act on: a pick that is neither fail-closed nor
        provisional (unconfirmed ledger candidate, unverified assignment, or a primary
        that changed after the table John approved)."""
        return self.primary_path is not None and not self.provisional and not self.fail_closed


def load_assignments(data_dir: Path) -> dict[str, Assignment]:
    target = Path(data_dir) / ASSIGNMENTS_FILENAME
    if not os.path.exists(long_path(target)):
        return {}
    with open(long_path(target), encoding="utf-8") as handle:
        rows = json.load(handle)
    return {row["project"]: Assignment.model_validate(row) for row in rows}


def write_assignments(assignments: dict[str, Assignment], data_dir: Path) -> None:
    rows = [assignments[key].model_dump() for key in sorted(assignments)]
    atomic_write_text(Path(data_dir) / ASSIGNMENTS_FILENAME, json.dumps(rows, indent=1))


def write_primaries(selections: Iterable[PrimarySelection], data_dir: Path) -> Path:
    rows = [{**s.model_dump(), "usable": s.usable} for s in sorted(selections, key=lambda s: s.project)]
    target = Path(data_dir) / PRIMARIES_FILENAME
    atomic_write_text(target, json.dumps(rows, indent=1))
    return target


def load_primaries(data_dir: Path) -> dict[str, PrimarySelection]:
    with open(long_path(Path(data_dir) / PRIMARIES_FILENAME), encoding="utf-8") as handle:
        rows = json.load(handle)
    return {
        row["project"]: PrimarySelection.model_validate({k: v for k, v in row.items() if k != "usable"})
        for row in rows
    }


# --- selection (pure) ---------------------------------------------------------------


@dataclass
class LedgerState:
    """What is known about ledger PDFs at selection time.

    ``confirmed``: path -> ledger sha1 for files whose bytes were hashed and matched.
    ``provisional``: paths still cloud-only that name/size-match a ledger PDF.
    ``ledger``: the ledger PDFs (for ``ts_utc``).
    ``file_sha1``: path -> sha1 for any file hashed so far (assignment staleness).
    """

    ledger: dict[str, LedgerPdf] = field(default_factory=dict)
    confirmed: dict[str, str] = field(default_factory=dict)
    provisional: set[str] = field(default_factory=set)
    file_sha1: dict[str, str] = field(default_factory=dict)


def _copy_rank(entry: SubmittalPdfEntry) -> tuple:
    order = {"signed_final": 0, "final_working": 1}
    return (entry.archived, order.get(entry.subfolder_class, 2), len(entry.path), entry.path.lower())


def _ineligible_reason(entry: SubmittalPdfEntry) -> str | None:
    if entry.archived:
        return "ARCHIVED"
    if not entry.oxygen8_named:
        return "NOT_OXYGEN8_NAMED"
    if "NUMBER_CONFLICT" in entry.reasons:
        return "NUMBER_CONFLICT"
    if entry.as_built:
        return "AS_BUILT"
    if entry.rev_key is None:
        return "REV_UNPARSEABLE"
    return None


def select_primary(
    project: str,
    entries: list[SubmittalPdfEntry],
    state: LedgerState,
    assignment: Assignment | None = None,
) -> PrimarySelection:
    dup = any("DUPLICATE_FOLDER_NUMBER" in e.reasons for e in entries)

    def make(reason: ProjectReason, **fields: Any) -> PrimarySelection:
        return PrimarySelection(project=project, duplicate_folder_number=dup, reason=reason, **fields)

    # 0. John's assignment.
    if assignment is not None:
        current = state.file_sha1.get(assignment.path)
        if current is not None and current != assignment.sha1:
            return make("ASSIGNMENT_STALE", rejected=[SelectionRecord(path=assignment.path, reason="SHA1_CHANGED")])
        # Unhashed this run (e.g. still cloud-only): John's pick stands, but it is not
        # usable until the file is read and still matches the pinned sha1.
        return make(
            "JOHN_ASSIGNED", primary_path=assignment.path, primary_sha1=assignment.sha1,
            provisional=current is None,
        )

    # 1. Ledger match -- archived allowed (it is the file CoilForge actually saw).
    confirmed = [e for e in entries if e.path in state.confirmed]
    if confirmed:
        by_sha1: dict[str, list[SubmittalPdfEntry]] = {}
        for entry in confirmed:
            by_sha1.setdefault(state.confirmed[entry.path], []).append(entry)
        latest = max(by_sha1, key=lambda s: (state.ledger[s].last_ts_utc if s in state.ledger else "", s))
        copies = sorted(by_sha1[latest], key=_copy_rank)
        chosen = copies[0]
        rejected = [
            SelectionRecord(path=e.path, reason="LEDGER_OLDER")
            for sha1, group in by_sha1.items() if sha1 != latest for e in group
        ]
        if "NUMBER_CONFLICT" in chosen.reasons:
            return make(
                "NUMBER_CONFLICT",
                rejected=[SelectionRecord(path=chosen.path, reason="NUMBER_CONFLICT"), *rejected],
            )
        return make(
            "LEDGER_MATCH_LATEST" if len(by_sha1) > 1 else "LEDGER_MATCH",
            primary_path=chosen.path,
            primary_sha1=latest,
            copies=[e.path for e in copies[1:]],
            rejected=rejected,
        )
    provisional = sorted((e for e in entries if e.path in state.provisional), key=_copy_rank)
    if provisional:
        # Not usable: a name/size candidate until its bytes are read and matched.
        return make(
            "LEDGER_PROVISIONAL", primary_path=provisional[0].path, provisional=True,
            copies=[e.path for e in provisional[1:]],
        )

    # 2 / 3. Signed Final, then Final Working -- eligible files only, fail-closed.
    # Two project folders sharing one number are two candidate sets; ranking Revs across
    # them could hand one project another's submittal.
    tiered = [e for e in entries if e.subfolder_class in ("signed_final", "final_working")]
    if len({e.project_folder for e in tiered}) > 1:
        return make(
            "DUPLICATE_FOLDER_NUMBER",
            rejected=[SelectionRecord(path=e.path, reason="DUPLICATE_FOLDER_NUMBER") for e in tiered],
        )
    tiers: tuple[tuple[str, ProjectReason], ...] = (
        ("signed_final", "SIGNED_FINAL"),
        ("final_working", "FINAL_WORKING_LATEST_REV"),
    )
    for tier, tier_reason in tiers:
        tier_entries = [e for e in entries if e.subfolder_class == tier]
        if not tier_entries:
            continue
        rejected: list[SelectionRecord] = []
        eligible: list[SubmittalPdfEntry] = []
        for entry in tier_entries:
            why = _ineligible_reason(entry)
            if why is None:
                eligible.append(entry)
            else:
                rejected.append(SelectionRecord(path=entry.path, reason=why))
        if not eligible:
            if tier == "signed_final":
                return make("SIGNED_FINAL_UNRECOGNIZED", rejected=rejected)
            return make("NO_SUBMITTAL", rejected=rejected)
        best_key = max(e.rev_key for e in eligible)  # type: ignore[type-var]
        best = [e for e in eligible if e.rev_key == best_key]
        rejected += [SelectionRecord(path=e.path, reason="LOWER_REV") for e in eligible if e.rev_key != best_key]
        archived_higher = [
            e for e in tier_entries
            if e.archived and e.oxygen8_named and e.rev_key is not None and e.rev_key > best_key
        ]
        if archived_higher:
            return make("ARCHIVED_HIGHER_REV", rejected=rejected)
        # Byte-identical copies are one file, not a tie -- but only when every copy's
        # sha1 is KNOWN and equal. Equal size is not proof; an unhashed (cloud-only)
        # member keeps the tie ambiguous and John assigns.
        sha1s = {state.file_sha1.get(e.path) for e in best}
        if len(best) > 1 and (None in sha1s or len(sha1s) > 1):
            return make(
                "REVISION_AMBIGUOUS",
                rejected=[*rejected, *(SelectionRecord(path=e.path, reason="TIED_REV") for e in best)],
            )
        ordered = sorted(best, key=_copy_rank)
        return make(
            tier_reason, primary_path=ordered[0].path,
            copies=[e.path for e in ordered[1:]], rejected=rejected,
        )
    return make("NO_SUBMITTAL")
