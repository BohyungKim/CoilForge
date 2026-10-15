"""Filesystem helpers for the submittal corpus.

Three facts about the PO tree drive everything here:

* ``LongPathsEnabled=0`` on this machine and 268 submittal PDFs sit at 260+ characters.
  A plain ``open``/``stat`` on those raises ``FileNotFoundError [WinError 3]`` -- the
  ``\\\\?\\`` prefix is the only way to reach them.
* The tree is OneDrive Files-On-Demand. Reading a cloud-only file's bytes downloads
  it, but its attributes come from the directory listing, so ``is_cloud_only`` on a
  ``DirEntry.stat()`` result never triggers a download.
* The data directory names customer projects and holds raw submittal text, so it must
  never land inside a git checkout (same posture as the capture ledger).
"""
from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

from coilforge.capture.db import CaptureConfigError, assert_outside_repo

ENV_INDEX_DIR = "COILFORGE_SUBMITTAL_INDEX_DIR"

# Windows attributes meaning "the bytes are not on this disk" (OneDrive placeholder).
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
_CLOUD_ONLY_MASK = (
    FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_OPEN | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
)

_LONG_PREFIX = "\\\\?\\"
_UNC_LONG_PREFIX = "\\\\?\\UNC\\"


class SubmittalIndexConfigError(RuntimeError):
    """The submittal index data directory is misconfigured (e.g. inside a git repo)."""


def long_path(path: str | os.PathLike[str]) -> str:
    """Absolute path carrying the ``\\\\?\\`` prefix on Windows; unchanged elsewhere."""
    text = os.path.abspath(os.fspath(path))
    if os.name != "nt" or text.startswith(_LONG_PREFIX):
        return text
    if text.startswith("\\\\"):
        return _UNC_LONG_PREFIX + text[2:]
    return _LONG_PREFIX + text


def strip_long_prefix(text: str) -> str:
    """Inverse of ``long_path`` for display/storage: paths are kept unprefixed."""
    if text.startswith(_UNC_LONG_PREFIX):
        return "\\\\" + text[len(_UNC_LONG_PREFIX):]
    if text.startswith(_LONG_PREFIX):
        return text[len(_LONG_PREFIX):]
    return text


def is_cloud_only(attrs: int) -> bool:
    return bool(attrs & _CLOUD_ONLY_MASK)


def read_pdf_bytes(path: str | os.PathLike[str]) -> bytes:
    """Read a file through the long-path prefix (downloads a cloud-only file)."""
    with open(long_path(path), "rb") as handle:
        return handle.read()


def atomic_write_text(target: str | os.PathLike[str], text: str) -> None:
    """Write via a temp file in the same directory, then ``os.replace``.

    Raises on failure (including a replace refused because a reader holds the target
    open on Windows); the caller decides whether an existing target is acceptable.
    """
    target_path = Path(target)
    directory = long_path(target_path.parent)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=target_path.suffix, dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, long_path(target_path))
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def default_data_dir() -> Path:
    """``COILFORGE_SUBMITTAL_INDEX_DIR`` or ``~/CoilForgeData/submittal_index``.

    Never ``%LOCALAPPDATA%``: Store Python (MSIX) silently redirects it into a package
    container, which is how the capture ledger once split into two files.
    """
    raw = os.environ.get(ENV_INDEX_DIR, "").strip()
    return resolve_data_dir(raw or None)


def resolve_data_dir(explicit: str | os.PathLike[str] | None) -> Path:
    """An explicit ``--index-dir`` or the default -- either way refused inside a repo."""
    if explicit is None:
        raw = os.environ.get(ENV_INDEX_DIR, "").strip()
        path = Path(raw) if raw else Path.home() / "CoilForgeData" / "submittal_index"
    else:
        path = Path(explicit)
    try:
        assert_outside_repo(path)
    except CaptureConfigError as exc:
        raise SubmittalIndexConfigError(
            f"refusing submittal index dir inside a git repo: {path}. "
            f"Set {ENV_INDEX_DIR} to a path outside the checkout."
        ) from exc
    return path
