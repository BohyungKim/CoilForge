"""Excel writer for the Ambient comparison workbook (I/O layer — Windows + Excel COM).

Consumes a pure ``AmbientExcelFill`` and produces a filled COPY of the template in the
Downloads folder. The source template is NEVER modified: Excel opens it read-only (or reuses
the already-open instance) and ``SaveCopyAs`` writes the copy; all edits happen on the copy.

Mirrors ``checklist/excel_writer.py`` exactly (isolated ``DispatchEx``, ``base.Copy(base)``
positional clone + ``ActiveSheet``, column-B label scan, ``Quit()`` teardown so no orphan
EXCEL.EXE), with two differences:
- fills BOTH column **C** (ours) and **D** (Ambient) per coil sheet;
- before writing any cell, skips it if it ``HasFormula`` — so the template's computed cells
  (Coil Volume C+D, HGRH Super Heat D, HGRH Vapor Temp C) are never overwritten, and the
  cloned formulas recompute via ``CalculateFull``.

Imports ``win32com`` lazily so the package imports on any platform; non-Windows callers get a
clear RuntimeError only when they actually write. Review aid only (``export_allowed=False``).
"""
from __future__ import annotations

import os
from typing import Any

from coilforge.ambient.excel_map import AmbientExcelFill, ExcelSheetFill
from coilforge.common.excel_lock import excel_single_flight

# The master template (per-category sheets CDXC-1 = DX, RHHGRC-1 = HGRH). XXXX is the
# project-number placeholder in the real template's filename.
DEFAULT_TEMPLATE_PATH = r"C:\Users\JohnKim\Desktop\Bins\XXXX - Coilmaster-Ambiant Dynamics Coil Comparison.xlsx"

_C_COL = 3  # column C ("Coilmaster" / ours)
_D_COL = 4  # column D ("Ambiant Dynamics")
_LABEL_COL = 2  # column B
_MASTER_SHEETS = ("CDXC-1", "RHHGRC-1")
_INVALID_SHEET = set(r'[]:*?/\\')


def _normalize_label(label: Any) -> str:
    return " ".join(str(label).split()).strip().lower()


def _safe_sheet_name(tag: str, taken: set[str]) -> str:
    """Excel sheet name: <=31 chars, no []:*?/\\, unique within the workbook."""
    name = "".join("-" if ch in _INVALID_SHEET else ch for ch in str(tag)).strip()[:31] or "Sheet"
    candidate, n = name, 2
    while candidate.upper() in {t.upper() for t in taken}:
        suffix = f" ({n})"
        candidate = name[: 31 - len(suffix)] + suffix
        n += 1
    taken.add(candidate)
    return candidate


def _downloads_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "Downloads")


def _dest_path(dest_dir: str | None, dest_name: str | None) -> str:
    folder = dest_dir or _downloads_dir()
    base = dest_name or "Coilmaster-Ambiant Dynamics Coil Comparison (filled).xlsx"
    if not base.lower().endswith(".xlsx"):
        base += ".xlsx"
    path = os.path.join(folder, base)
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(path):  # never clobber a previous fill
        path = f"{stem} ({n}){ext}"
        n += 1
    return path


def _win32():
    try:
        import win32com.client as win32
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Excel COM (pywin32) is required to write the Ambient comparison; install pywin32"
        ) from exc
    return win32


def _copy_template(win32, edit_app, template_path: str, dest: str) -> None:
    """SaveCopyAs the template to ``dest`` without touching the original (read-only)."""
    src_basename = os.path.basename(template_path).lower()
    try:
        src = edit_app.Workbooks.Open(template_path, ReadOnly=True, UpdateLinks=0)
        try:
            src.SaveCopyAs(dest)
        finally:
            src.Close(SaveChanges=False)
        return
    except Exception:  # noqa: BLE001 — locked; reuse the user's open instance read-only
        running = win32.GetActiveObject("Excel.Application")
        src = next(w for w in running.Workbooks if w.Name.lower() == src_basename)
        src.SaveCopyAs(dest)


def _label_rows(ws) -> dict[str, int]:
    """Map normalized column-B label -> row number for one worksheet."""
    used = ws.UsedRange
    last = used.Row + used.Rows.Count - 1
    rows: dict[str, int] = {}
    for r in range(1, last + 1):
        label = ws.Cells(r, _LABEL_COL).Value
        if label not in (None, ""):
            rows.setdefault(_normalize_label(label), r)
    return rows


def _coerce(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _instance_pid(app) -> int | None:
    """PID of this isolated Excel instance (from its main-window handle), or None.

    Pinned BEFORE teardown so a leaked invisible instance can be terminated by PID — only
    ever OUR DispatchEx instance, never the user's interactive Excel (see status_board lock)."""
    try:
        import win32process
        _tid, pid = win32process.GetWindowThreadProcessId(app.Hwnd)
        return int(pid) or None
    except Exception:  # noqa: BLE001
        return None


def _terminate_pid(pid: int | None) -> None:
    """Force-terminate our own leaked Excel PID if COM ``Quit`` left it alive. No-op if the
    process already exited (OpenProcess returns NULL)."""
    if not pid:
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
        if handle:
            k32.TerminateProcess(handle, 0)
            k32.CloseHandle(handle)
    except Exception:  # noqa: BLE001 — best-effort orphan sweep
        pass


def _fill_sheet(ws, sheet: ExcelSheetFill) -> list[str]:
    """Write C+D cells; skip None (never guess) and formula cells (never overwrite).
    Return labels that had no matching column-B row (surfaced, never miswritten)."""
    rows = _label_rows(ws)
    missing: list[str] = []
    for cell in sheet.cells:
        row = rows.get(_normalize_label(cell.label))
        if row is None:
            if cell.c is not None or cell.d is not None:
                missing.append(cell.label)
            continue
        for col, value in ((_C_COL, cell.c), (_D_COL, cell.d)):
            if value is None:
                continue
            target = ws.Cells(row, col)
            if target.HasFormula:  # protect template-computed cells
                continue
            target.Value = _coerce(value)
    return missing


def write_ambient_excel(
    fill: AmbientExcelFill,
    *,
    template_path: str = DEFAULT_TEMPLATE_PATH,
    dest_dir: str | None = None,
    dest_name: str | None = None,
    visible: bool = False,
) -> dict[str, Any]:
    """Write a filled COPY of the comparison workbook; the source template is untouched.

    Result: ``{saved_path, sheets:[{tag,category}], skipped_labels:[...], warnings:[...],
    export_allowed: False, production_drawing_approval_claimed: False}``.

    Shares the Excel single-flight guard with the Coil Checklist writer, so a checklist
    fill running in this (or another) CoilForge server cannot collide with this one.
    Raises ``ExcelBusyError`` after the bounded wait; the route maps it to HTTP 409."""
    with excel_single_flight(label="Ambient comparison"):
        return _write_ambient_excel_unlocked(
            fill,
            template_path=template_path,
            dest_dir=dest_dir,
            dest_name=dest_name,
            visible=visible,
        )


def _write_ambient_excel_unlocked(
    fill: AmbientExcelFill,
    *,
    template_path: str = DEFAULT_TEMPLATE_PATH,
    dest_dir: str | None = None,
    dest_name: str | None = None,
    visible: bool = False,
) -> dict[str, Any]:
    """The real writer. Call ``write_ambient_excel`` — this one assumes the guard is held."""
    if not fill.sheets:
        raise ValueError("nothing to write — no coil sheets in the fill")

    win32 = _win32()
    dest = _dest_path(dest_dir, dest_name)

    import pythoncom  # part of pywin32

    com_initialized = False
    try:
        pythoncom.CoInitialize()
        com_initialized = True
    except Exception:  # noqa: BLE001 — already initialized in this thread
        pass

    app = win32.DispatchEx("Excel.Application")
    app.DisplayAlerts = False
    app.Visible = bool(visible)
    pid = _instance_pid(app)  # pin our PID before any teardown (orphan sentinel)

    _copy_template(win32, app, template_path, dest)

    wb = app.Workbooks.Open(dest)
    skipped: list[str] = []
    result_sheets: list[dict[str, str]] = []
    base = None
    targets: list[Any] = []
    try:
        taken = {ws.Name for ws in wb.Worksheets}

        # Group coils by master sheet so each same-category coil gets a CLEAN clone of the
        # pristine master (cloned before any fill). Clones are taken via object refs +
        # ActiveSheet, never by re-looking-up a renamed sheet by name string.
        by_source: dict[str, list[ExcelSheetFill]] = {}
        for sheet in fill.sheets:
            by_source.setdefault(sheet.source_sheet, []).append(sheet)

        for source_name, sheetfills in by_source.items():
            base = wb.Worksheets(source_name)
            targets = [base]
            for _ in range(len(sheetfills) - 1):
                base.Copy(base)  # positional Before -> clone stays in THIS workbook, becomes active
                targets.append(app.ActiveSheet)
            for ws, sheet in zip(targets, sheetfills):
                new_name = _safe_sheet_name(sheet.tag, taken - {ws.Name})
                taken.discard(ws.Name)
                ws.Name = new_name
                taken.add(new_name)
                skipped += [f"{new_name}:{lbl}" for lbl in _fill_sheet(ws, sheet)]
                result_sheets.append({"tag": new_name, "category": sheet.category})

        # Remove any pristine master sheet that no coil consumed (e.g. HGRH master when the
        # project has only DX coils).
        for master in _MASTER_SHEETS:
            try:
                wb.Worksheets(master).Delete()
            except Exception:  # noqa: BLE001 — already consumed/renamed
                pass

        # Recalculate so cloned formula cells (Coil Volume, ...) reflect their own inputs
        # rather than inheriting the master's cached value.
        app.CalculateFull()
        wb.Save()
    finally:
        if visible:
            wb.Save()  # leave the copy open for the user to inspect
        else:
            wb.Close(SaveChanges=True)
            app.Quit()
            # Release every COM ref so the invisible instance can actually exit; a lingering
            # worksheet/workbook ref keeps EXCEL.EXE alive as a headless zombie that locks the
            # file (status_board_excel_lock). gc first, then PID sentinel as a hard backstop.
            base = None
            targets = []
            wb = None
            app_ref, app = app, None
            del app_ref
            import gc
            gc.collect()
            _terminate_pid(pid)
        if com_initialized:
            pythoncom.CoUninitialize()

    return {
        "saved_path": dest,
        "sheets": result_sheets,
        "skipped_labels": skipped,
        "warnings": list(fill.warnings),
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
    }
