"""Pure / filesystem layer for finalizing a DirectCoil deliverable.

- ``deliverable_subject`` / ``short_project_name`` — build the email subject
  ``Coils: <number> - <clean name>`` from the intake's project number/name,
  trimming "Ship To / Revision …" cruft. Presentation only (the draft is
  editable) — never an engineering value.
- ``resolve_directcoil_folder`` — locate ``…/02 - POs/<number…>/Accessory Order
  Forms/DirectCoil`` under the SharePoint base, creating ONLY the ``DirectCoil``
  leaf if absent; fails loudly (never invents a project/AOF folder) otherwise.
  Both the AOF and DirectCoil names are matched case/space-insensitively, and a
  DirectCoil spelled some other way (``Direct Coil``, ``direct_coil``) is
  RENAMED to ``DirectCoil`` and reused rather than left beside a new one.
- ``plan_placements`` / ``commit_placements`` — decide every destination BEFORE
  writing any of them, so one name collision stops the whole deliverable instead
  of half-filing it. A collision is same-name-AND-different-content; a
  byte-identical file already there is ``already_filed``, not a conflict, which
  is what lets "Build" file the docs and a later "Open Outlook draft" run over
  the same three files without arguing about them.
- ``retire_download`` — the "move, don't copy" half for the two PDFs, which
  reach us as bytes and never as a path: the Downloads original is deleted ONLY
  when its sha256 matches what we just filed.

No Outlook/COM here so this imports and tests on any platform.
"""
from __future__ import annotations

import glob as _glob
import hashlib
import os
import re
import shutil
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# SharePoint-synced base, hardcoded like ``checklist.template_map.DEFAULT_TEMPLATE_PATH``.
DEFAULT_PO_BASE = (
    r"C:\Users\JohnKim\OneDrive - Oxygen8\Oxygen8 SharePoint Shortcuts"
    r"\Sales - Documents\02 - POs"
)

# Trim the name at the first "administrative" marker so the subject stays clean.
_CRUFT_MARKER = re.compile(
    r"\s+(?:ship\s+to|revision|rev\b|rev\.|no\.\s*:|\(|-\s*rev)\b.*$",
    re.IGNORECASE,
)

# Placement states (see ``plan_placements``).
NEW = "new"
ALREADY_FILED = "already_filed"
CONFLICT = "conflict"

_AOF_NAMES = {"accessoryorderforms", "accessoryorderform"}
_DIRECTCOIL_NAMES = {"directcoil"}
_DIRECTCOIL_CANONICAL = "DirectCoil"
_NORM_RE = re.compile(r"[\s_\-]+")


class FinalizeError(RuntimeError):
    """A deliverable could not be filed for a reportable, user-facing reason
    (folder missing / ambiguous). Distinct from COM/RuntimeError failures."""


def short_project_name(project_number: str | None, project_name: str | None) -> str:
    """Clean short name for the subject: drop a leading ``<number> -`` and trim
    trailing admin cruft (``Ship To``, ``Revision``, ``No.:``, ``(…``)."""
    name = (project_name or "").strip()
    num = (project_number or "").strip()
    if num and name.startswith(num):
        name = name[len(num):].lstrip().lstrip("-").lstrip()
    match = _CRUFT_MARKER.search(name)
    if match:
        name = name[: match.start()]
    return name.strip(" -–—:")


def deliverable_subject(project_number: str | None, project_name: str | None) -> str:
    """``Coils: <number> - <clean name>`` (drops whichever part is missing)."""
    num = (project_number or "").strip()
    short = short_project_name(project_number, project_name)
    if num and short:
        return f"Coils: {num} - {short}"
    if num:
        return f"Coils: {num}"
    return f"Coils: {short}" if short else "Coils:"


# ---- folder resolution ------------------------------------------------------


def _norm(name: str) -> str:
    """Fold a folder name for matching: lowercase, spaces/underscores/hyphens out."""
    return _NORM_RE.sub("", name).lower()


def _child_by_normalized(parent: Path, accepted: set[str], label: str) -> Path | None:
    """The one child folder of ``parent`` whose folded name is in ``accepted``.

    More than one (``DirectCoil`` beside ``Direct Coil``) is ambiguous: which one
    is the real one is John's call, not the code's, so this raises rather than
    picking a winner and filing into the wrong half of a split folder.
    """
    hits = sorted(
        (p for p in parent.iterdir() if p.is_dir() and _norm(p.name) in accepted),
        key=lambda p: p.name,
    )
    if len(hits) > 1:
        names = ", ".join(p.name for p in hits)
        raise FinalizeError(
            f"multiple '{label}' folders in {parent.name}: {names} "
            "— merge them into one and retry"
        )
    return hits[0] if hits else None


def _rename_to_canonical(found: Path, target: Path) -> Path:
    """Rename ``found`` to ``target`` in place, tolerating a case-only change.

    A case-only rename (``directcoil`` -> ``DirectCoil``) is refused by some
    filesystems because the target "already exists" — the same folder under
    another case — so fall back to a two-step rename through a temp name, and put
    the original name back if the second step fails.
    """
    try:
        found.rename(target)
        return target
    except OSError:
        pass
    tmp = found.with_name(found.name + ".__coilforge_rename__")
    try:
        found.rename(tmp)
    except OSError as exc:
        raise FinalizeError(
            f"could not rename '{found.name}' to '{target.name}' in "
            f"{found.parent.name}: {exc}"
        ) from exc
    try:
        tmp.rename(target)
    except OSError as exc:
        try:  # leave the tree exactly as we found it
            tmp.rename(found)
        except OSError:
            pass
        raise FinalizeError(
            f"could not rename '{found.name}' to '{target.name}' in "
            f"{found.parent.name}: {exc}"
        ) from exc
    return target


def resolve_directcoil_folder(
    project_number: str | None,
    *,
    base_dir: str = DEFAULT_PO_BASE,
    create: bool = True,
) -> Path:
    """Return the ``…/<number…>/Accessory Order Forms/DirectCoil`` folder.

    Creates ONLY the ``DirectCoil`` leaf if absent, and renames an existing
    differently-spelled one (``Direct Coil``…) to ``DirectCoil`` rather than
    filing beside it. Raises ``FinalizeError`` (never invents a folder) when the
    base, the project folder, or ``Accessory Order Forms`` is missing, when more
    than one project folder starts with the number, or when two spellings of a
    folder coexist.
    """
    num = (project_number or "").strip()
    if not num:
        raise FinalizeError("no project number — cannot locate the PO folder")
    base = Path(base_dir)
    if not base.is_dir():
        raise FinalizeError(f"PO base folder not found: {base}")

    matches = [p for p in base.iterdir() if p.is_dir() and p.name.startswith(num)]
    if not matches:
        raise FinalizeError(
            f"no project folder under '02 - POs' starting with {num}"
        )
    if len(matches) > 1:
        # Prefer a folder where the number is a whole leading token ("2572 - …"),
        # not just a prefix ("25720…"), before giving up as ambiguous.
        exact = [p for p in matches if re.match(rf"^{re.escape(num)}(\D|$)", p.name)]
        if len(exact) == 1:
            matches = exact
        else:
            names = ", ".join(sorted(p.name for p in matches))
            raise FinalizeError(f"multiple project folders start with {num}: {names}")

    project_dir = matches[0]
    # Matched loosely but NEVER renamed: John's rule is that a missing AOF means we
    # probably grabbed the wrong project folder, and that error only carries meaning
    # if a mere spelling variant ("Accessory Order Form") cannot trigger it.
    aof = _child_by_normalized(project_dir, _AOF_NAMES, "Accessory Order Forms")
    if aof is None:
        raise FinalizeError(
            f"'Accessory Order Forms' not found in {project_dir.name}"
        )

    found = _child_by_normalized(aof, _DIRECTCOIL_NAMES, _DIRECTCOIL_CANONICAL)
    if found is None:
        if not create:
            raise FinalizeError(f"DirectCoil folder absent in {project_dir.name}")
        directcoil = aof / _DIRECTCOIL_CANONICAL
        directcoil.mkdir(parents=True, exist_ok=True)
        return directcoil
    if found.name != _DIRECTCOIL_CANONICAL:
        return _rename_to_canonical(found, aof / _DIRECTCOIL_CANONICAL)
    return found


# ---- filing (all-or-nothing; a collision stops the deliverable) --------------


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class Placement:
    """One document's decided destination, resolved BEFORE anything is written.

    ``state`` is ``new`` (nothing there), ``already_filed`` (byte-identical file
    already at the destination — filing it again is a no-op, not a collision) or
    ``conflict`` (same name, different content: John decides).
    """

    filename: str
    dest: Path
    state: str
    data: bytes | None = None
    src_path: Path | None = None

    @property
    def is_conflict(self) -> bool:
        return self.state == CONFLICT


def plan_placements(
    folder: Path | str,
    items: Sequence[tuple[str, bytes | str | Path]],
) -> list[Placement]:
    """Decide every destination up front.

    ``items`` are ``(filename, payload)`` where the payload is either the bytes to
    write or the path of a file to move in. Nothing is written here — that split
    is the whole point, since "stop and ask" is only honest if the answer is known
    before the first byte lands.
    """
    target = Path(folder)
    placements: list[Placement] = []
    for filename, payload in items:
        safe = Path(filename).name  # strip any path components from the client name
        dest = target / safe
        data: bytes | None = None
        src_path: Path | None = None
        if isinstance(payload, (bytes, bytearray)):
            data = bytes(payload)
            digest = _sha256_bytes(data)
        else:
            src_path = Path(payload)
            digest = _sha256_file(src_path)
        if not dest.exists():
            state = NEW
        elif _sha256_file(dest) == digest:
            state = ALREADY_FILED
        else:
            state = CONFLICT
        placements.append(Placement(safe, dest, state, data, src_path))
    return placements


def commit_placements(
    placements: list[Placement], *, overwrite: bool = False
) -> list[str]:
    """Write/move every placement and return the destination paths.

    Refuses outright when a conflict is present and ``overwrite`` is False — the
    caller is expected to have surfaced the conflict list to John first; this is
    the backstop that makes a half-filed folder unreachable.
    """
    conflicts = [p.filename for p in placements if p.is_conflict]
    if conflicts and not overwrite:
        raise FinalizeError(
            "refusing to file over existing files: " + ", ".join(conflicts)
        )
    written: list[str] = []
    for placement in placements:
        if placement.data is not None:
            if placement.state != ALREADY_FILED:
                placement.dest.write_bytes(placement.data)
        elif placement.src_path is not None:
            src = placement.src_path
            if placement.state != ALREADY_FILED:
                # copy+unlink rather than shutil.move: it overwrites cleanly and
                # works across volumes (Downloads and OneDrive need not share one).
                shutil.copyfile(src, placement.dest)
            if src.exists():
                try:
                    if not src.samefile(placement.dest):
                        src.unlink()
                except OSError:
                    pass  # the copy is filed; a locked source is reported upstream
        written.append(str(placement.dest))
    return written


# ---- Downloads retirement ("move", for the docs we only hold as bytes) ------


def _downloads_dir() -> str:
    """The same ``~/Downloads`` rule the checklist writer saves into.

    Imported lazily from that writer so the two can never drift, and so this
    module keeps its promise of importing on any platform.
    """
    from coilforge.checklist.excel_writer import _downloads_dir as _writer_downloads

    return _writer_downloads()


def retire_download(
    filename: str,
    data: bytes,
    *,
    wait_s: float = 0.0,
    downloads_dir: str | Path | None = None,
) -> str:
    """Delete the Downloads copy of a document we just filed — content-verified.

    The browser hands us bytes, never a path, so the source is reconstructed as
    ``~/Downloads/<filename>`` plus Chrome's ``<stem> (1)<ext>`` duplicates. A
    candidate is deleted ONLY when its sha256 matches ``data``, which makes
    deleting an unrelated same-named file structurally impossible.

    ``wait_s`` bounds a poll for a download that may not have reached disk yet
    (the browser saves the revised PDF asynchronously moments before we run).
    Returns a status string; never raises.
    """
    folder = Path(downloads_dir) if downloads_dir is not None else Path(_downloads_dir())
    safe = Path(filename).name
    stem, ext = os.path.splitext(safe)
    digest = _sha256_bytes(data)
    pattern = f"{_glob.escape(stem)} (*){ext}" if ext else f"{_glob.escape(stem)} (*)"
    deadline = time.monotonic() + max(0.0, wait_s)
    candidates: list[Path] = []
    while True:
        try:
            candidates = [folder / safe] + sorted(folder.glob(pattern))
        except OSError:
            return "Downloads folder unreadable — left in place"
        matched = [p for p in candidates if p.is_file() and _sha256_file(p) == digest]
        if matched:
            failures = []
            for path in matched:
                try:
                    path.unlink()
                except OSError as exc:
                    failures.append(f"{path.name}: {exc}")
            return "moved" if not failures else "could not delete " + "; ".join(failures)
        if time.monotonic() >= deadline:
            break
        time.sleep(0.25)
    if any(p.is_file() for p in candidates):
        return "differs — left in place"
    return "not found — left in place"
