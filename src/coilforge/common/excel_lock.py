"""Single-flight guard for the Excel COM writers (in-process + cross-process).

Two CoilForge features drive Excel through an isolated ``DispatchEx`` instance —
the Coil Checklist auto-fill (``checklist/excel_writer.py``) and the Ambient
comparison workbook (``ambient/excel_writer.py``). Two of them running at once
leave zombie Excel processes holding file locks, and since ``run_server.bat`` now
takes a port argument so several projects can run side by side, "at once" is the
normal case rather than an accident. Both writers therefore enter through here.

Two tiers, because they solve different problems:

- **In-process** ``threading.Lock`` — the web app calls the writers via
  ``asyncio.to_thread``, so overlapping requests land on DIFFERENT worker threads
  and a non-reentrant lock serializes them instead of self-deadlocking. (A caller
  that nested two guards on ONE thread would time out rather than hang forever —
  that is what the bounded wait below buys.)
- **Cross-process** lock file — a second uvicorn on another port is a different
  process, invisible to the threading lock. Ownership is recorded as
  ``pid + process creation time`` because Windows recycles pids: a bare pid check
  would mistake an unrelated new process for the live owner and wait out the full
  timeout every time.

**Acquisition blocks for a bounded wait and only then raises.** Fail-fast would be
wrong here: ``/api/deliverable/finalize`` absorbs a checklist failure into a status
string and files the order documents anyway, so a transient busy signal must not
turn into a filed package with no .xlsx. The routes map :class:`ExcelBusyError` to
HTTP 409 and finalize treats it as a hard error.

Set ``COILFORGE_EXCEL_LOCK=0`` to disable the guard entirely (rollback without
reverting), matching the ``COILFORGE_MANUAL_FILL`` idiom.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Iterator

__all__ = ["ExcelBusyError", "excel_single_flight", "lock_path"]

_LOCK_FILENAME = "coilforge_excel.lock"
DEFAULT_TIMEOUT_S = 120.0
_POLL_INTERVAL_S = 0.5
# A lock whose owner we cannot verify (non-Windows, or OpenProcess denied) is
# reclaimed once it is this old. Long enough that a genuinely slow multi-coil fill
# is never stolen from; short enough that a crashed process does not wedge the box.
_UNVERIFIABLE_STALE_AFTER_S = 30 * 60.0

_process_lock = Lock()


class ExcelBusyError(Exception):
    """Another Excel COM write holds the single-flight guard.

    Deliberately NOT a ``RuntimeError`` subclass: the web routes map
    ``RuntimeError`` to 501 ("Excel / pywin32 unavailable"), and a busy guard is a
    retryable 409, not a missing dependency. Keep the ``except`` clause for this
    class BEFORE the ``RuntimeError`` clause at every call site.
    """


def _enabled() -> bool:
    return (os.environ.get("COILFORGE_EXCEL_LOCK") or "1").strip() not in {"0", "false", "False"}


def lock_path() -> Path:
    """The cross-process lock file (temp dir, never inside the repo)."""
    import tempfile

    return Path(tempfile.gettempdir()) / _LOCK_FILENAME


def _process_creation_ticks(pid: int) -> int | None:
    """Windows process creation time in 100ns ticks, or ``None`` if unavailable.

    pids are recycled, so the creation time is what makes "is the recorded owner
    still the process that took the lock?" answerable. Uses ``ctypes`` so this
    module stays dependency-free (pywin32 is a writer concern, not a lock concern).
    """
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return None  # dead, or not ours to query
        try:
            created, exited, kernel_t, user_t = (wintypes.FILETIME() for _ in range(4))
            ok = kernel32.GetProcessTimes(
                handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel_t),
                ctypes.byref(user_t),
            )
            if not ok:
                return None
            return (created.dwHighDateTime << 32) | created.dwLowDateTime
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001 — the guard must never be the thing that fails
        return None


def _own_token() -> str:
    pid = os.getpid()
    ticks = _process_creation_ticks(pid)
    return f"{pid}|{'' if ticks is None else ticks}|{time.time():.3f}"


def _parse_token(raw: str) -> tuple[int, int | None, float] | None:
    parts = (raw or "").strip().split("|")
    if len(parts) != 3:
        return None
    try:
        pid = int(parts[0])
        ticks = int(parts[1]) if parts[1] else None
        taken_at = float(parts[2])
    except ValueError:
        return None
    return pid, ticks, taken_at


def _owner_is_live(raw: str) -> bool:
    """Is the process recorded in the lock file still the one that took the lock?

    Unknown owner (unparseable token, or a creation time we could not read) is
    treated as live until ``_UNVERIFIABLE_STALE_AFTER_S`` — never reclaim a lock on
    a guess, since the cost of guessing wrong is two Excel instances on one file.
    """
    parsed = _parse_token(raw)
    if parsed is None:
        return False  # corrupt sentinel — nothing to protect
    pid, ticks, taken_at = parsed
    if pid == os.getpid():
        return True  # our own process still holds it (the threading lock owns ordering)
    current = _process_creation_ticks(pid)
    if current is not None and ticks is not None:
        return current == ticks  # same pid AND same process -> genuinely live
    if current is None and ticks is not None:
        return False  # pid is gone (or unqueryable) while we DO know its identity
    return (time.time() - taken_at) < _UNVERIFIABLE_STALE_AFTER_S


def _try_take(path: Path, token: str) -> bool:
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except OSError:
        return False
    try:
        os.write(fd, token.encode("utf-8"))
    finally:
        os.close(fd)
    return True


def _reclaim_if_dead(path: Path) -> None:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except OSError:
        return
    if _owner_is_live(raw):
        return
    try:
        path.unlink()
    except OSError:  # someone else reclaimed it first — fine
        pass


def _release(path: Path, token: str) -> None:
    """Drop the lock, but only if the file still carries OUR token.

    A lock we already lost (reclaimed as stale by another process, which then took
    it) must not be deleted out from under its new owner.
    """
    try:
        if path.read_text(encoding="utf-8").strip() == token:
            path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


@contextmanager
def excel_single_flight(
    *, label: str = "Excel", timeout_s: float = DEFAULT_TIMEOUT_S
) -> Iterator[None]:
    """Serialize an Excel COM write across threads AND processes.

    Raises :class:`ExcelBusyError` if the guard is still held after ``timeout_s``.
    ``label`` names the caller in that message ("Coil Checklist", "Ambient").
    """
    if not _enabled():
        yield
        return

    deadline = time.monotonic() + timeout_s
    if not _process_lock.acquire(timeout=max(0.0, timeout_s)):
        raise ExcelBusyError(
            f"{label}: another Excel write in this server is still running "
            f"(waited {timeout_s:.0f}s). Try again once it finishes."
        )

    path = lock_path()
    token = _own_token()
    try:
        while True:
            if _try_take(path, token):
                break
            _reclaim_if_dead(path)
            if time.monotonic() >= deadline:
                raise ExcelBusyError(
                    f"{label}: another CoilForge session is using Excel "
                    f"(lock {path}, waited {timeout_s:.0f}s). Try again once it finishes."
                )
            time.sleep(_POLL_INTERVAL_S)
        try:
            yield
        finally:
            _release(path, token)
    finally:
        _process_lock.release()
