"""Excel COM single-flight guard (pure; no Excel, no COM).

The guard exists because ``run_server.bat`` now takes a port argument, so two CoilForge
servers driving Excel at the same time is the normal case rather than an accident.
These tests pin the properties the HTTP layer depends on:

- ``ExcelBusyError`` is NOT a ``RuntimeError`` — the routes map ``RuntimeError`` to 501
  ("Excel is absent") and the busy guard to 409 ("retry"), and a subclass relationship
  would silently collapse the two into the wrong diagnosis;
- a lock whose owner process is gone is reclaimed rather than wedging the box;
- releasing never deletes a lock that a different owner has since taken;
- the kill switch really disables the guard.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from coilforge.common import excel_lock
from coilforge.common.excel_lock import ExcelBusyError, excel_single_flight


@pytest.fixture(autouse=True)
def _isolated_lock(tmp_path, monkeypatch):
    """Point the guard at a per-test lock file; never touch the real one in %TEMP%."""
    monkeypatch.setattr(excel_lock, "lock_path", lambda: tmp_path / "coilforge_excel.lock")
    monkeypatch.delenv("COILFORGE_EXCEL_LOCK", raising=False)
    yield


def test_busy_error_is_not_a_runtime_error():
    """Load-bearing for the 409/501 split at every call site."""
    assert not issubclass(ExcelBusyError, RuntimeError)
    assert issubclass(ExcelBusyError, Exception)


def test_guard_releases_on_success_and_on_exception(tmp_path):
    path = tmp_path / "coilforge_excel.lock"

    with excel_single_flight(label="A"):
        assert path.exists()
    assert not path.exists()

    with pytest.raises(ValueError):
        with excel_single_flight(label="A"):
            raise ValueError("writer blew up")
    assert not path.exists(), "a failed write must not leave the guard held"


def test_second_thread_waits_then_gives_up_with_busy_error():
    """A concurrent write serializes; if it cannot get in, it raises Busy — not a hang."""
    holder_in = threading.Event()
    holder_may_exit = threading.Event()
    outcome: dict[str, object] = {}

    def hold():
        with excel_single_flight(label="holder"):
            holder_in.set()
            holder_may_exit.wait(5)

    def contend():
        try:
            with excel_single_flight(label="contender", timeout_s=0.6):
                outcome["result"] = "acquired"
        except ExcelBusyError as exc:
            outcome["result"] = "busy"
            outcome["message"] = str(exc)

    t1 = threading.Thread(target=hold)
    t1.start()
    assert holder_in.wait(5), "holder never acquired the guard"

    t2 = threading.Thread(target=contend)
    t2.start()
    t2.join(10)

    holder_may_exit.set()
    t1.join(10)

    assert outcome["result"] == "busy"
    assert "contender" in str(outcome["message"])  # the label names the caller


def test_stale_lock_from_a_dead_owner_is_reclaimed(tmp_path):
    """A crashed server must not wedge Excel for everyone else."""
    path = tmp_path / "coilforge_excel.lock"
    # pid 1 with a creation time that cannot match anything live on this box.
    path.write_text("1|1|0.0", encoding="utf-8")

    with excel_single_flight(label="after crash", timeout_s=3):
        assert path.read_text(encoding="utf-8").startswith(f"{os.getpid()}|")
    assert not path.exists()


def test_corrupt_lock_file_is_reclaimed(tmp_path):
    path = tmp_path / "coilforge_excel.lock"
    path.write_text("not-a-token", encoding="utf-8")

    with excel_single_flight(label="after corruption", timeout_s=3):
        pass
    assert not path.exists()


def test_release_does_not_delete_a_lock_someone_else_now_owns(tmp_path):
    """We may lose a lock (reclaimed as stale); we must not delete its new owner's."""
    path = tmp_path / "coilforge_excel.lock"
    with excel_single_flight(label="A"):
        path.write_text("999999|123456|1.0", encoding="utf-8")  # a different owner
    assert path.exists(), "released a guard that had been taken over by another owner"
    assert path.read_text(encoding="utf-8") == "999999|123456|1.0"


def test_kill_switch_disables_the_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("COILFORGE_EXCEL_LOCK", "0")
    path = tmp_path / "coilforge_excel.lock"
    with excel_single_flight(label="disabled"):
        assert not path.exists(), "kill switch must not create a lock file"


def test_unverifiable_owner_is_respected_until_it_goes_stale(tmp_path):
    """Never reclaim on a guess: an owner we cannot verify still holds the guard."""
    path = tmp_path / "coilforge_excel.lock"
    # No creation ticks recorded -> identity unverifiable; taken just now -> still live.
    path.write_text(f"999999||{time.time():.3f}", encoding="utf-8")
    with pytest.raises(ExcelBusyError):
        with excel_single_flight(label="polite", timeout_s=0.4):
            pass

    # The same owner, recorded long ago, is stale and may be reclaimed.
    old = time.time() - excel_lock._UNVERIFIABLE_STALE_AFTER_S - 60
    path.write_text(f"999999||{old:.3f}", encoding="utf-8")
    with excel_single_flight(label="polite", timeout_s=3):
        pass


def test_both_excel_writers_enter_through_the_shared_guard():
    """The guard is worthless if only one of the two COM writers uses it."""
    src = Path(__file__).resolve().parents[1] / "src" / "coilforge"
    for module in ("checklist/excel_writer.py", "ambient/excel_writer.py"):
        text = (src / module).read_text(encoding="utf-8")
        assert "from coilforge.common.excel_lock import excel_single_flight" in text, module
        assert "with excel_single_flight(" in text, module


def _web_app_source() -> str:
    return (
        Path(__file__).resolve().parents[1] / "src" / "coilforge" / "web_app.py"
    ).read_text(encoding="utf-8")


def test_busy_is_handled_before_runtime_error_at_both_excel_call_sites():
    """Clause ORDER is the whole fix.

    ``RuntimeError`` maps to 501 "Excel unavailable" and the trailing
    ``except Exception`` maps to 500 "Excel write failed". A busy guard reaching
    either of those is the exact misdiagnosis this guard was added to remove — the
    engineer would read "Excel is broken" when the truth is "your other tab is
    mid-write". Both call sites must catch it first.
    """
    source = _web_app_source()
    busy_at = [i for i in range(len(source)) if source.startswith("except ExcelBusyError", i)]
    runtime_at = [i for i in range(len(source)) if source.startswith("except RuntimeError", i)]

    assert len(busy_at) == 2, (
        "expected an ExcelBusyError handler at BOTH Excel call sites "
        "(_run_or_reuse_checklist and the ambient-excel route)"
    )
    for busy in busy_at:
        following = [r for r in runtime_at if r > busy]
        assert following, "an ExcelBusyError handler with no RuntimeError clause after it"
        between = source[busy:following[0]]
        assert "409" in between, "the ExcelBusyError handler must map to HTTP 409"


def test_finalize_refuses_to_file_a_deliverable_without_its_checklist():
    """A transient busy guard must not turn into an order folder with no .xlsx.

    Everywhere else a checklist failure degrades into ``checklist_status``; finalize
    files the DirectCoil documents regardless. That was safe while failures meant
    "Excel is absent" — the guard adds a *transient* failure, so finalize special-cases it.
    """
    source = _web_app_source()
    marker = "if checklist_outcome.http_status == 409:"
    assert marker in source
    guard_at = source.index(marker)
    status_at = source.index("checklist_status = ", guard_at - 4000)
    assert guard_at < status_at, "the 409 guard must precede the degrade-to-status path"
