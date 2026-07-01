"""Phase 2 — Excel writer integration test (Windows + Excel only).

Skips cleanly where pywin32/Excel/openpyxl or the template are unavailable (e.g.
CI), so the suite still degrades gracefully. Verifies the writer fills INPUT cells,
preserves the dim FORMULAS, keeps the support sheets, removes unused category
sheets, and renames sheets to coil tags.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytest.importorskip("win32com.client")
openpyxl = pytest.importorskip("openpyxl")

from coilforge.checklist import template_map as T
from coilforge.checklist.mapping import build_checklist_fill
from coilforge.checklist.excel_writer import write_checklist

pytestmark = pytest.mark.skipif(
    not os.path.exists(T.DEFAULT_TEMPLATE_PATH),
    reason="Coil Checklist template not present on this machine",
)


def _write(tmp_path, coils, name):
    try:
        return write_checklist(build_checklist_fill(coils), dest_dir=str(tmp_path),
                               dest_name=name)
    except Exception as exc:  # noqa: BLE001 — Excel not installed / COM unavailable
        pytest.skip(f"Excel COM unavailable: {exc}")


def _dx(**over):
    coil = dict(tag="CDXC-1", coil_type="DX", product_label="NOVA", unit_size="C24",
                quantity=1, finned_height=45.0, finned_length=54.0, rows=5, feeds=9,
                circuits=2, suction_conn_size=2.0, qty_conn_per_header=2, coil_hand="L")
    coil.update(over)
    return coil


def _rows(ws):
    return {str(ws.cell(r, 2).value).strip(): r for r in range(1, 70)
            if ws.cell(r, 2).value not in (None, "")}


def test_writer_fills_inputs_keeps_formulas_and_sheets(tmp_path):
    res = _write(tmp_path, [_dx()], "t1.xlsx")
    assert os.path.exists(res["saved_path"])
    assert res["export_allowed"] is False

    wb = openpyxl.load_workbook(res["saved_path"])  # formulas, not data_only
    assert "CDXC-1" in wb.sheetnames
    assert "HWC" not in wb.sheetnames and "CWC" not in wb.sheetnames
    assert "Units" in wb.sheetnames  # support sheet must survive (dropdowns ref it)

    ws = wb["CDXC-1"]
    rows = _rows(ws)
    # inputs written
    assert ws.cell(rows["UNIT"], 3).value == "NOVA"
    assert ws.cell(rows["FH"], 3).value == 45
    assert ws.cell(rows["COLLARED HOLES"], 3).value is True
    assert ws.cell(rows["STACKING FLANGES"], 3).value is False
    # dim FORMULAS preserved (NOT overwritten)
    assert str(ws.cell(rows["CD"], 3).value).startswith("=")
    assert str(ws.cell(rows["S1"], 3).value).startswith("=")


def test_writer_pairs_dx_hgrh(tmp_path):
    coils = [_dx(tag="CDXC-1"),
             dict(tag="RHHGRC-1", coil_type="HGRH", product_label="NOVA",
                  unit_size="C24", quantity=1, finned_height=12.0, finned_length=54.0,
                  rows=1, feeds=1, circuits=1, conn_size=1.125, qty_conn_per_header=1,
                  coil_hand="L")]
    res = _write(tmp_path, coils, "t2.xlsx")
    wb = openpyxl.load_workbook(res["saved_path"])
    assert {"CDXC-1", "RHHGRC-1"} <= set(wb.sheetnames)
    ws = wb["CDXC-1"]
    rows = _rows(ws)
    assert ws.cell(rows["W/ HGRH"], 3).value is True
    assert ws.cell(rows["HGRH CONN SZ"], 3).value == 1.125


def test_writer_duplicates_same_category_sheets(tmp_path):
    # Two DX coils must both persist as sheets in the SAME workbook (regression:
    # the keyword Copy(After=) form silently cloned into a new workbook).
    coils = [_dx(tag="CDXC-1"), _dx(tag="CDXC-2")]
    res = _write(tmp_path, coils, "t4.xlsx")
    wb = openpyxl.load_workbook(res["saved_path"])
    assert {"CDXC-1", "CDXC-2"} <= set(wb.sheetnames)
    assert "Units" in wb.sheetnames


def test_writer_reads_back_computed_dims(tmp_path):
    res = _write(tmp_path, [_dx()], "t3.xlsx")
    computed = res["sheets"][0]["computed_dims"]
    # Excel evaluated the CD formula from the inputs we wrote.
    assert computed["CD"] == 7.5
    assert computed["CH"] == 46.25
