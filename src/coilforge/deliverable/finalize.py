"""Pure / filesystem layer for finalizing a DirectCoil deliverable.

- ``deliverable_subject`` / ``short_project_name`` — build the email subject
  ``Coils: <number> - <clean name>`` from the intake's project number/name,
  trimming "Ship To / Revision …" cruft. Presentation only (the draft is
  editable) — never an engineering value.
- ``resolve_directcoil_folder`` — locate ``…/02 - POs/<number…>/Accessory Order
  Forms/DirectCoil`` under the SharePoint base, creating ONLY the ``DirectCoil``
  leaf if absent; fails loudly (never invents a project/AOF folder) otherwise.
- ``place_bytes`` / ``place_copy`` — write the docs into the folder without ever
  clobbering an existing file (appends `` (2)``, `` (3)``…), mirroring
  ``checklist.excel_writer._dest_path``.

No Outlook/COM here so this imports and tests on any platform.
"""
from __future__ import annotations

import os
import re
import shutil
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


def resolve_directcoil_folder(
    project_number: str | None,
    *,
    base_dir: str = DEFAULT_PO_BASE,
    create: bool = True,
) -> Path:
    """Return the ``…/<number…>/Accessory Order Forms/DirectCoil`` folder.

    Creates ONLY the ``DirectCoil`` leaf if absent. Raises ``FinalizeError`` (never
    invents a folder) when the base, the project folder, or ``Accessory Order
    Forms`` is missing, or when more than one project folder starts with the number.
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
    aof = project_dir / "Accessory Order Forms"
    if not aof.is_dir():
        raise FinalizeError(
            f"'Accessory Order Forms' not found in {project_dir.name}"
        )
    directcoil = aof / "DirectCoil"
    if not directcoil.exists():
        if not create:
            raise FinalizeError(f"DirectCoil folder absent in {project_dir.name}")
        directcoil.mkdir(parents=True, exist_ok=True)
    return directcoil


def _nonclobber(folder: Path, filename: str) -> Path:
    """Destination path in ``folder`` that never overwrites an existing file."""
    safe = Path(filename).name  # strip any path components from the client name
    path = folder / safe
    stem, ext = os.path.splitext(safe)
    n = 2
    while path.exists():
        path = folder / f"{stem} ({n}){ext}"
        n += 1
    return path


def place_bytes(folder: Path | str, filename: str, data: bytes) -> str:
    """Write ``data`` into ``folder`` under ``filename`` (never clobbers)."""
    dest = _nonclobber(Path(folder), filename)
    dest.write_bytes(data)
    return str(dest)


def place_copy(folder: Path | str, filename: str, src_path: str) -> str:
    """Copy ``src_path`` into ``folder`` under ``filename`` (never clobbers)."""
    dest = _nonclobber(Path(folder), filename)
    shutil.copyfile(src_path, dest)
    return str(dest)
