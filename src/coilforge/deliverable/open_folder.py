"""Open a filed deliverable's folder in Windows Explorer.

Mirrors ``deliverable.outlook_draft``: the OS call is imported lazily inside the
function so this module imports on any platform, and it is only ever reached from
an explicit click -- nothing opens a window on its own.

The path arrives from the BROWSER, so it is never trusted. ``open_deliverable_folder``
refuses anything that does not resolve inside the SharePoint PO base, which is what
keeps this from being a general "run this path" endpoint. Read-only: it opens a
folder and touches nothing inside it.
"""
from __future__ import annotations

import os
from pathlib import Path

from coilforge.deliverable.finalize import DEFAULT_PO_BASE, FinalizeError


def _is_within(candidate: Path, base: Path) -> bool:
    """True when ``candidate`` is ``base`` or sits under it.

    ``Path.is_relative_to`` on the RESOLVED paths, so ``..`` traversal and symlinks
    are normalized away before the comparison rather than after it.
    """
    try:
        return candidate == base or candidate.is_relative_to(base)
    except ValueError:  # different drives
        return False


def open_deliverable_folder(folder: str | Path, *, base_dir: str = DEFAULT_PO_BASE) -> str:
    """Open ``folder`` in Explorer and return the path opened.

    Raises ``FinalizeError`` when the path is empty, resolves outside ``base_dir``,
    or is not an existing directory. Raises ``RuntimeError`` where ``os.startfile``
    does not exist (non-Windows), matching how ``outlook_draft`` reports a missing
    platform dependency.
    """
    raw = str(folder or "").strip()
    if not raw:
        raise FinalizeError("no folder to open")

    target = Path(raw).resolve()
    base = Path(base_dir).resolve()
    if not _is_within(target, base):
        # Deliberately does NOT echo the rejected path back: the caller supplied it,
        # and reflecting an arbitrary path into the UI is how a probe gets confirmed.
        raise FinalizeError("refusing to open a folder outside the project PO base")
    if not target.is_dir():
        raise FinalizeError(f"folder no longer exists: {target}")

    startfile = getattr(os, "startfile", None)
    if startfile is None:  # pragma: no cover -- Windows-only in practice
        raise RuntimeError("opening a folder is only supported on Windows")
    startfile(str(target))
    return str(target)
