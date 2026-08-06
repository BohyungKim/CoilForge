"""Excel writer for the Coil Checklist (I/O layer — Windows + Excel COM only).

Consumes a pure ``ChecklistFill`` and produces a filled COPY of the template in
the Downloads folder. The source template is NEVER modified: Excel opens it
read-only (or reuses the already-open instance) and ``SaveCopyAs`` writes the copy;
all edits happen on the copy.

Native checkboxes (Collared Holes, W/HGRH, ...) are plain boolean cell values, so
setting one is just writing ``True``/``False`` to its column-C cell — the cell's
checkbox format is preserved. Fields are located by scanning column B for their
label, so the per-sheet layout differences don't need hardcoded addresses.

Normally only INPUT cells are written and the sheet's own formulas compute the lower
dimensions — that independence is what makes the engine-vs-checklist comparison a real
check. The one exception is a manual override: a dim the engineer corrected in the
browser is overwritten with the drawn value, but only AFTER the formula's own result has
been read back (see ``write_checklist`` steps 4-5), so the comparison keeps both numbers
and a cell comment records what was replaced.

This module imports ``win32com`` lazily so the package imports on any platform;
callers on non-Windows get a clear RuntimeError only when they actually write.
"""
from __future__ import annotations

import os
from typing import Any

from coilforge.checklist import template_map as T
from coilforge.checklist.model import ChecklistFill, SheetFill
from coilforge.common.excel_lock import excel_single_flight

_VALUE_COL = 3  # column C ("SUBMITTAL")
_LABEL_COL = 2  # column B
_INVALID_SHEET = set(r'[]:*?/\\')


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
    base = dest_name or "Coil Checklist (filled).xlsx"
    if not base.lower().endswith(".xlsx"):
        base += ".xlsx"
    path = os.path.join(folder, base)
    # Re-filling the same submittal REPLACES its copy (John 2026-07-30). Auto-refill after
    # a manual override used to leave "... (2).xlsx", "... (3).xlsx" piling up in Downloads
    # and the engineer then had to work out which one was current. Pre-flight the replace:
    # if the previous copy is open in Excel the delete raises, and no clobber is possible,
    # so fall back to a numbered name rather than failing the whole fill.
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            stem, ext = os.path.splitext(path)
            n = 2
            while os.path.exists(path):
                path = f"{stem} ({n}){ext}"
                n += 1
    return path


def _win32():
    try:
        import win32com.client as win32
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Excel COM (pywin32) is required to write the checklist; install pywin32"
        ) from exc
    return win32


def _copy_template(win32, edit_app, template_path: str, dest: str) -> None:
    """SaveCopyAs the template to ``dest`` without touching the original.

    Prefers opening it read-only in our isolated edit instance. If that fails
    (e.g. exclusive lock held by the user's open copy), falls back to the running
    Excel instance and SaveCopyAs from the already-open workbook — still read-only.
    """
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
            rows.setdefault(T.normalize_label(label), r)
    return rows


def _coerce(value: Any) -> Any:
    """COM-friendly value: bools stay bools (checkbox), ints stay ints, else passthrough."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _fill_sheet(ws, sheet: SheetFill) -> list[str]:
    """Write a sheet's cells; return labels that had no matching row (skipped)."""
    rows = _label_rows(ws)
    missing: list[str] = []
    for cell in sheet.cells:
        if cell.value is None:
            continue  # leave blank — never guess
        row = rows.get(T.normalize_label(cell.label))
        if row is None:
            missing.append(cell.label)
            continue
        ws.Cells(row, _VALUE_COL).Value = _coerce(cell.value)
    return missing


def _set_comment(cell, text: str) -> None:
    """Attach (replacing any existing) a note to a cell — best-effort.

    Excel raises if a comment already exists, so clear first. The whole thing is
    swallowed: an annotation failing must never lose the engineer's filled workbook.
    """
    try:
        cell.ClearComments()
        comment = cell.AddComment(text)
        comment.Visible = False
    except Exception:  # noqa: BLE001 — annotation is a nicety, the values are the point
        pass


def _annotate_input_overrides(ws, sheet: SheetFill) -> None:
    """Note on every Tier-A input cell the engineer manually supplied."""
    rows = _label_rows(ws)
    for cell in sheet.cells:
        if cell.override is None:
            continue
        row = rows.get(T.normalize_label(cell.label))
        if row is None:
            continue
        was = "blank" if cell.override.previous_value in (None, "") else cell.override.previous_value
        reason = f' · reason: "{cell.override.reason}"' if cell.override.reason else ""
        _set_comment(
            ws.Cells(row, _VALUE_COL),
            f"CoilForge manual override — submittal read {was}, using {cell.value}"
            f"{reason} · review aid, not approved",
        )


def _apply_dim_overrides(ws, sheet: SheetFill, formula_values: dict[str, Any]) -> list[dict[str, Any]]:
    """Overwrite each manually overridden dimension with the value CoilForge is drawing.

    ORDER IS LOAD-BEARING: the caller reads ``formula_values`` back BEFORE this runs, so
    the sheet's own formula result is captured before it is replaced — that reading is
    what keeps the engine-vs-checklist cross-check alive (``compare.build_review`` shows
    it against the override as verdict ``overridden``). The comment records the same pair
    inside the workbook, for whoever opens the .xlsx without the app.
    """
    rows = _label_rows(ws)
    applied: list[dict[str, Any]] = []
    for dim in sheet.compare_dims:
        if dim.override is None or dim.coilforge_value is None:
            continue
        row = rows.get(T.normalize_label(dim.label))
        if row is None:
            continue
        formula_value = formula_values.get(dim.label)
        ws.Cells(row, _VALUE_COL).Value = _coerce(dim.coilforge_value)
        reason = f' · reason: "{dim.override.reason}"' if dim.override.reason else ""
        _set_comment(
            ws.Cells(row, _VALUE_COL),
            f"CoilForge manual override — this sheet's formula computed {formula_value}, "
            f"using {dim.coilforge_value}{reason} · review aid, not approved",
        )
        applied.append(
            {
                "tag": sheet.sheet_tag,
                "label": dim.label,
                "value": dim.coilforge_value,
                "formula_value": formula_value,
                "reason": dim.override.reason,
            }
        )
    return applied


# Late-bound COM has no constants module; xlCalculationManual is -4135.
_XL_CALCULATION_MANUAL = -4135


def write_checklist(
    fill: ChecklistFill,
    *,
    template_path: str = T.DEFAULT_TEMPLATE_PATH,
    dest_dir: str | None = None,
    dest_name: str | None = None,
    visible: bool = False,
) -> dict[str, Any]:
    """Write a filled copy of the checklist and return a small result dict.

    Result: ``{saved_path, sheets:[{tag,category}], removed:[...], skipped_labels:[...],
    overridden_dims:[...], warnings:[...], export_allowed: False}``. The source template
    is untouched.

    Serialized against every other Excel COM write — in this process and in any other
    CoilForge server (``run_server.bat`` takes a port, so parallel projects are normal).
    Raises ``ExcelBusyError`` if the guard is still held after the bounded wait; the
    routes map that to HTTP 409, distinct from the 501 that means Excel is absent.
    """
    with excel_single_flight(label="Coil Checklist"):
        return _write_checklist_unlocked(
            fill,
            template_path=template_path,
            dest_dir=dest_dir,
            dest_name=dest_name,
            visible=visible,
        )


def _write_checklist_unlocked(
    fill: ChecklistFill,
    *,
    template_path: str = T.DEFAULT_TEMPLATE_PATH,
    dest_dir: str | None = None,
    dest_name: str | None = None,
    visible: bool = False,
) -> dict[str, Any]:
    """The real writer. Call ``write_checklist`` — this one assumes the guard is held."""
    if not fill.sheets:
        raise ValueError("nothing to write — no coil sheets in the fill")

    win32 = _win32()
    dest = _dest_path(dest_dir, dest_name)

    # COM must be initialized per thread. The web app calls this off the event
    # loop (a worker thread with no COM), so initialize here; harmless on the main
    # thread (returns S_FALSE). Matched CoUninitialize in the outer finally.
    import pythoncom  # part of pywin32

    com_initialized = False
    try:
        pythoncom.CoInitialize()
        com_initialized = True
    except Exception:  # noqa: BLE001 — already initialized in this thread
        pass

    # Dedicated, isolated Excel instance — never touches the user's open Excel.
    app = win32.DispatchEx("Excel.Application")
    app.DisplayAlerts = False
    app.Visible = bool(visible)

    # 1) Copy the template to Downloads (read-only; original untouched).
    _copy_template(win32, app, template_path, dest)

    # 2) Edit the copy in the isolated instance.
    wb = app.Workbooks.Open(dest)
    skipped: list[str] = []
    removed: list[str] = []
    overridden_dims: list[dict[str, Any]] = []
    result_sheets: list[dict[str, str]] = []
    try:
        # P1-C: during the many per-cell writes, suppress intermediate recalcs and
        # screen/event churn. The single app.CalculateFull() below still does a FULL
        # formula recompute, so every computed dim read back is byte-identical to before
        # — this only removes redundant recalcs, not the accuracy-critical final one.
        # The isolated instance is Quit in the finally, so no restore is required.
        app.Calculation = _XL_CALCULATION_MANUAL
        app.ScreenUpdating = False
        app.EnableEvents = False

        taken = {ws.Name for ws in wb.Worksheets}

        # Group coils by source sheet so multiple same-category coils each get a
        # CLEAN clone of the pristine template sheet (cloned before any fill, so a
        # blank input on one coil never inherits another coil's value). Clones are
        # taken via object refs + ActiveSheet — never by re-looking-up a renamed
        # sheet by name string (that COM lookup throws DISP_E_BADINDEX).
        by_source: dict[str, list[SheetFill]] = {}
        for sheet in fill.sheets:
            by_source.setdefault(sheet.source_sheet, []).append(sheet)

        written: list[tuple[Any, SheetFill]] = []  # (worksheet COM obj, sheetfill)
        for source_name, sheetfills in by_source.items():
            base = wb.Worksheets(source_name)
            targets = [base]
            for _ in range(len(sheetfills) - 1):
                # NOTE: pass Before POSITIONALLY. The keyword form (After=base) does
                # NOT bind in late-bound COM and silently copies to a NEW workbook;
                # a positional location keeps the clone in THIS workbook. The clone
                # becomes the active sheet.
                base.Copy(base)
                targets.append(app.ActiveSheet)
            for ws, sheet in zip(targets, sheetfills):
                new_name = _safe_sheet_name(sheet.sheet_tag, taken - {ws.Name})
                taken.discard(ws.Name)
                ws.Name = new_name
                taken.add(new_name)
                skipped += [f"{new_name}:{lbl}" for lbl in _fill_sheet(ws, sheet)]
                result_sheets.append({"tag": new_name, "category": sheet.category})
                written.append((ws, sheet))

        # 3) Remove unused category sheets (NEVER the Units / Install support sheets).
        for name in fill.remove_sheets:
            if name in T.SUPPORT_SHEETS_KEEP:
                continue
            try:
                wb.Worksheets(name).Delete()
                removed.append(name)
            except Exception:  # noqa: BLE001 — sheet already gone / renamed
                pass

        # 4) Recalculate so the sheet's dim FORMULAS reflect the inputs we wrote,
        #    then read each computed dim back for the comparison view.
        app.CalculateFull()
        for entry, (ws, sheet) in zip(result_sheets, written):
            rows = _label_rows(ws)
            computed: dict[str, Any] = {}
            for dim in sheet.compare_dims:
                row = rows.get(T.normalize_label(dim.label))
                computed[dim.label] = ws.Cells(row, _VALUE_COL).Value if row else None
            entry["computed_dims"] = computed

        # 5) Manual overrides (John 2026-07-29). The formula results are already captured
        #    in `computed_dims` above, so replacing an overridden dim's formula with the
        #    value CoilForge is actually drawing costs nothing analytically and makes the
        #    filed .xlsx agree with the drawing. Both the replaced formula value and the
        #    reason are written into a cell comment. Then recalc AGAIN so the formulas
        #    that depend on an overridden dim (OAL/CH, the FIT checks) follow it.
        #    A fill with no overrides skips this block entirely (no extra label scans,
        #    no second recalc) — the pre-2026-07-29 path, unchanged.
        for entry, (ws, sheet) in zip(result_sheets, written):
            if not any(c.override for c in sheet.cells) and not any(
                d.override for d in sheet.compare_dims
            ):
                continue
            _annotate_input_overrides(ws, sheet)
            overridden_dims += _apply_dim_overrides(ws, sheet, entry["computed_dims"])
        if overridden_dims:
            app.CalculateFull()
            # 6) Re-read so the review table describes the workbook's FINAL state. A dim
            #    that merely DEPENDS on an override moves with it — this template's
            #    CH (= C13 + C27 + C28) follows TF — and leaving the pre-override reading
            #    in place would hide that from anyone reviewing the app instead of the
            #    file. The OVERRIDDEN dims are deliberately excluded: their pre-overwrite
            #    reading IS the cross-check, and re-reading would just echo the override
            #    back and turn every override into a self-confirming match.
            for entry, (ws, sheet) in zip(result_sheets, written):
                overridden_labels = {
                    T.normalize_label(d.label)
                    for d in sheet.compare_dims
                    if d.override is not None
                }
                rows = _label_rows(ws)
                for dim in sheet.compare_dims:
                    label = T.normalize_label(dim.label)
                    if label in overridden_labels:
                        continue
                    row = rows.get(label)
                    entry["computed_dims"][dim.label] = (
                        ws.Cells(row, _VALUE_COL).Value if row else None
                    )

        # Activate the first coil sheet for convenience (object ref, not name lookup).
        if written:
            written[0][0].Activate()
        wb.Save()
    finally:
        if visible:
            wb.Save()  # leave the copy open for the user to inspect
        else:
            wb.Close(SaveChanges=True)
            app.Quit()  # tear down the isolated instance (no orphan EXCEL.EXE)
        if com_initialized:
            pythoncom.CoUninitialize()

    return {
        "saved_path": dest,
        "sheets": result_sheets,
        "removed": removed,
        "skipped_labels": skipped,
        "overridden_dims": overridden_dims,
        "warnings": list(fill.warnings),
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
    }
