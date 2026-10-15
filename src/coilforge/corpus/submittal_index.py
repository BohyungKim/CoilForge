"""Download-free index of the submittal PDFs in the PO tree (and optional extra roots).

``scan`` walks directories with ``os.scandir`` and records metadata only -- it never
opens a PDF, so a cloud-only OneDrive file stays in the cloud. EVERY ``*.pdf`` is
indexed, not just names containing "submittal": signed-final copies are often named
``<number> - <project>.pdf`` and a name filter silently hides them (3232).

Project numbers:
* PO tree -- the project FOLDER's leading token is the project (``folder_number``).
* extra roots -- a filename number, only when unambiguous.
``filename_numbers`` counts a `` - ``-separated segment only when the WHOLE segment is
a 4-digit number (optional letter suffix), so a date (``2026-7-8 …``), an 8-digit rep
number (``26040533 - …``) or a prefixed segment (``SIGNED 2954``) is never read as one.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field

from coilforge.corpus.fs import atomic_write_text, is_cloud_only, long_path, strip_long_prefix

SCHEMA_VERSION = 1
INDEX_FILENAME = "index.json"
MAX_PATH = 260

SubfolderClass = Literal["final_working", "signed_final", "customer_po", "project_root", "other"]

# Same token semantics as pdf_intake._PROJECT_NUMBER_TOKEN_RE, anchored at the folder name.
_FOLDER_NUMBER_RE = re.compile(r"^([A-Za-z]{0,2}\d{3,6}[A-Za-z]?)(?![0-9])")
_FILENAME_NUMBER_SEGMENT_RE = re.compile(r"^\d{4}[A-Za-z]?$")
_SEGMENT_SPLIT_RE = re.compile(r"\s+-\s*|\s*-\s+")
# Applied to the STEM only: on the full name the optional letter group eats ".p" of
# ".pdf", ranking "Rev1.pdf" (1,'p') above "Rev1a.pdf" (1,'a').
_REV_RE = re.compile(r"(?<![a-z])rev(\d+)(?:\.?([a-z]))?(?![a-z])", re.IGNORECASE)
_REV_TOKEN_RE = re.compile(r"(?<![a-z])rev[\w.]*", re.IGNORECASE)
_AS_BUILT_RE = re.compile(r"(?<![a-z])as[\s_-]*built", re.IGNORECASE)
_OXYGEN8_NAMED_RE = re.compile(r"\b(?:oxygen8|o8)\s+submittal\b", re.IGNORECASE)
_ARCHIVED_DIR_RE = re.compile(r"\b(?:old|archived?|superseded)\b", re.IGNORECASE)


class SubmittalPdfEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    root: str
    project_folder: str | None = None
    folder_number: str | None = None
    filename_numbers: list[str] = Field(default_factory=list)
    project_number: str | None = None
    reasons: list[str] = Field(default_factory=list)
    subfolder: str | None = None
    subfolder_class: SubfolderClass = "other"
    archived: bool = False
    name_has_submittal: bool = False
    oxygen8_named: bool = False
    rev_token: str | None = None
    rev_key: tuple[int, str] | None = None
    as_built: bool = False
    size: int
    mtime_ns: int
    cloud_only_at_scan: bool
    long_path: bool


class ScanError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    error: str


class SubmittalIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    built_at: str
    roots: list[str]
    entries: list[SubmittalPdfEntry]
    scan_errors: list[ScanError] = Field(default_factory=list)


# --- name parsing (pure) ------------------------------------------------------------


def folder_number(folder_name: str) -> str | None:
    match = _FOLDER_NUMBER_RE.match(folder_name.strip())
    return match.group(1) if match else None


def filename_numbers(filename: str) -> list[str]:
    stem = Path(filename).stem
    found: list[str] = []
    for segment in _SEGMENT_SPLIT_RE.split(stem):
        token = segment.strip()
        if _FILENAME_NUMBER_SEGMENT_RE.match(token) and token not in found:
            found.append(token)
    return found


def rev_key(filename: str) -> tuple[int, str] | None:
    """``(number, letter or "")`` from the stem; ``None`` when absent or ambiguous.

    ``RevS0``/``RevS2a`` and bare as-built names return ``None``: their order relative
    to ``RevN`` is not known, so it is never guessed. Two different Rev tokens in one
    name also return ``None``.
    """
    keys = {
        (int(number), (letter or "").lower())
        for number, letter in _REV_RE.findall(Path(filename).stem)
    }
    return keys.pop() if len(keys) == 1 else None


def rev_token(filename: str) -> str | None:
    match = _REV_TOKEN_RE.search(Path(filename).stem)
    return match.group(0) if match else None


def is_as_built(filename: str) -> bool:
    return bool(_AS_BUILT_RE.search(Path(filename).stem))


def is_oxygen8_named(filename: str) -> bool:
    return bool(_OXYGEN8_NAMED_RE.search(filename))


def _digits(token: str) -> str:
    return re.sub(r"\D", "", token)


def subfolder_class(subfolder: str | None) -> SubfolderClass:
    if subfolder is None:
        return "project_root"
    folded = re.sub(r"[^a-z0-9]", "", subfolder.lower())
    if folded.startswith("finalworking"):
        return "final_working"
    if folded.startswith("signedfinal"):
        return "signed_final"
    if folded.startswith("customerpo"):
        return "customer_po"
    return "other"


def _entry(
    *,
    abs_path: str,
    root: str,
    rel_dirs: list[str],
    is_po_tree: bool,
    size: int,
    mtime_ns: int,
    attrs: int,
) -> SubmittalPdfEntry:
    name = os.path.basename(abs_path)
    numbers = filename_numbers(name)
    reasons: list[str] = []
    project_folder = rel_dirs[0] if (is_po_tree and rel_dirs) else None
    folder_no = folder_number(project_folder) if project_folder else None
    below = rel_dirs[1:] if is_po_tree else rel_dirs
    subfolder = below[0] if (is_po_tree and below) else None

    if is_po_tree:
        project = folder_no
        if folder_no is None:
            reasons.append("NO_NUMBER")
        else:
            reasons.append("FOLDER_NUMBER")
            if numbers and _digits(folder_no) not in {_digits(n) for n in numbers}:
                reasons.append("NUMBER_CONFLICT")
    else:
        distinct = {_digits(n) for n in numbers}
        if len(distinct) == 1:
            project = numbers[0]
            reasons.append("FILENAME_NUMBER")
        else:
            project = None
            reasons.append("FILENAME_NUMBER_AMBIGUOUS" if distinct else "NO_NUMBER")

    return SubmittalPdfEntry(
        path=abs_path,
        root=root,
        project_folder=project_folder,
        folder_number=folder_no,
        filename_numbers=numbers,
        project_number=project,
        reasons=reasons,
        subfolder=subfolder,
        subfolder_class=subfolder_class(subfolder) if is_po_tree else "other",
        archived=any(_ARCHIVED_DIR_RE.search(part) for part in below),
        name_has_submittal="submittal" in name.lower(),
        oxygen8_named=is_oxygen8_named(name),
        rev_token=rev_token(name),
        rev_key=rev_key(name),
        as_built=is_as_built(name),
        size=size,
        mtime_ns=mtime_ns,
        cloud_only_at_scan=is_cloud_only(attrs),
        long_path=len(abs_path) >= MAX_PATH,
    )


# --- scan (metadata only) -----------------------------------------------------------


def _walk(
    root: Path,
    *,
    is_po_tree: bool,
    entries: list[SubmittalPdfEntry],
    errors: list[ScanError],
    top_folders: list[str],
) -> None:
    root_text = os.path.abspath(os.fspath(root))
    stack: list[tuple[str, list[str]]] = [(long_path(root_text), [])]
    while stack:
        directory, rel_dirs = stack.pop()
        try:
            with os.scandir(directory) as iterator:
                children = list(iterator)
        except OSError as exc:
            errors.append(ScanError(path=strip_long_prefix(directory), error=repr(exc)))
            continue
        for child in children:
            try:
                if child.is_symlink():
                    continue
                if child.is_dir(follow_symlinks=False):
                    if is_po_tree and not rel_dirs:
                        top_folders.append(child.name)
                    stack.append((child.path, [*rel_dirs, child.name]))
                    continue
                if not (child.is_file(follow_symlinks=False) and child.name.lower().endswith(".pdf")):
                    continue
                stat = child.stat(follow_symlinks=False)
            except OSError as exc:
                errors.append(ScanError(path=strip_long_prefix(child.path), error=repr(exc)))
                continue
            entries.append(
                _entry(
                    abs_path=strip_long_prefix(child.path),
                    root=root_text,
                    rel_dirs=rel_dirs,
                    is_po_tree=is_po_tree,
                    size=stat.st_size,
                    mtime_ns=stat.st_mtime_ns,
                    attrs=getattr(stat, "st_file_attributes", 0),
                )
            )


def scan(
    po_base: str | os.PathLike[str] | None,
    extra_roots: Iterable[str | os.PathLike[str]] = (),
) -> SubmittalIndex:
    """Index every PDF under ``po_base`` (project-folder tree) and ``extra_roots``.

    Metadata only: no PDF is opened. Extra roots must be absolute -- a relative
    ``submittals/`` would silently resolve against whichever worktree runs the scan.
    """
    entries: list[SubmittalPdfEntry] = []
    errors: list[ScanError] = []
    roots: list[str] = []
    top_folders: list[str] = []
    if po_base is not None:
        roots.append(os.path.abspath(os.fspath(po_base)))
        _walk(Path(po_base), is_po_tree=True, entries=entries, errors=errors, top_folders=top_folders)
    for extra in extra_roots:
        if not os.path.isabs(os.fspath(extra)):
            raise ValueError(f"extra root must be an absolute path: {extra}")
        roots.append(os.path.abspath(os.fspath(extra)))
        _walk(Path(extra), is_po_tree=False, entries=entries, errors=errors, top_folders=[])

    folders_by_number: dict[str, set[str]] = defaultdict(set)
    for name in top_folders:
        number = folder_number(name)
        if number is not None:
            folders_by_number[number].add(name)
    duplicated = {number for number, names in folders_by_number.items() if len(names) > 1}
    for entry in entries:
        if entry.folder_number in duplicated:
            entry.reasons.append("DUPLICATE_FOLDER_NUMBER")

    entries.sort(key=lambda e: e.path.lower())
    return SubmittalIndex(
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        roots=roots,
        entries=entries,
        scan_errors=errors,
    )


def entries_for_project(index: SubmittalIndex, number: str) -> list[SubmittalPdfEntry]:
    return [entry for entry in index.entries if entry.project_number == number]


def write_index(index: SubmittalIndex, data_dir: str | os.PathLike[str]) -> Path:
    target = Path(data_dir) / INDEX_FILENAME
    atomic_write_text(target, index.model_dump_json())
    return target


def load_index(data_dir: str | os.PathLike[str]) -> SubmittalIndex:
    target = Path(data_dir) / INDEX_FILENAME
    with open(long_path(target), encoding="utf-8") as handle:
        return SubmittalIndex.model_validate_json(handle.read())
