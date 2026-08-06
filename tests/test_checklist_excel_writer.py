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


# --- manual overrides (John 2026-07-29) ------------------------------------
def _write_with_overrides(tmp_path, coils, name, payload):
    from coilforge.checklist.overrides import normalize_coil_overrides

    fill = build_checklist_fill(coils, normalize_coil_overrides(payload))
    try:
        return write_checklist(fill, dest_dir=str(tmp_path), dest_name=name)
    except Exception as exc:  # noqa: BLE001 — Excel not installed / COM unavailable
        pytest.skip(f"Excel COM unavailable: {exc}")


def _override_payload(tag, params, reason="engineer correction"):
    return [{"tag": tag, "engine_inputs": {}, "reason": reason,
             "param_overrides": [{"key": k, "value": v, "override_reason": reason}
                                 for k, v in params.items()]}]


def test_writer_overwrites_an_overridden_dim_but_reads_the_formula_first(tmp_path):
    """The formula's own result must be captured BEFORE it is replaced — that read-back
    is what keeps the engine-vs-checklist cross-check meaningful."""
    res = _write_with_overrides(tmp_path, [_dx()], "t5.xlsx",
                                _override_payload("CDXC-1", {"CD": 10.0}))
    # Baseline preserved: the sheet's own CD formula still computed 7.5.
    assert res["sheets"][0]["computed_dims"]["CD"] == 7.5
    assert res["overridden_dims"] == [
        {"tag": "CDXC-1", "label": "CD", "value": 10.0, "formula_value": 7.5,
         "reason": "engineer correction"}
    ]
    # The saved cell is now the value CoilForge draws, not the formula.
    wb = openpyxl.load_workbook(res["saved_path"])
    ws = wb["CDXC-1"]
    rows = _rows(ws)
    assert ws.cell(rows["CD"], 3).value == 10
    assert not str(ws.cell(rows["CD"], 3).value).startswith("=")
    # Untouched dims keep their formulas.
    assert str(ws.cell(rows["S1"], 3).value).startswith("=")


def test_writer_recalculates_formulas_that_depend_on_an_overridden_dim(tmp_path):
    """S1 is derived from CD by the sheet's own formula, so overriding CD must move it —
    proof the second CalculateFull ran after the overwrite."""
    plain = _write(tmp_path, [_dx()], "t6.xlsx")
    bumped = _write_with_overrides(tmp_path, [_dx()], "t7.xlsx",
                                   _override_payload("CDXC-1", {"CD": 10.0}))
    base_s1 = openpyxl.load_workbook(plain["saved_path"], data_only=True)["CDXC-1"]
    new_s1 = openpyxl.load_workbook(bumped["saved_path"], data_only=True)["CDXC-1"]
    rows = _rows(base_s1)
    assert new_s1.cell(rows["S1"], 3).value != base_s1.cell(rows["S1"], 3).value


def test_writer_annotates_the_override_with_the_value_it_replaced(tmp_path):
    res = _write_with_overrides(tmp_path, [_dx()], "t8.xlsx",
                                _override_payload("CDXC-1", {"CD": 10.0}, "shop measured"))
    ws = openpyxl.load_workbook(res["saved_path"])["CDXC-1"]
    comment = ws.cell(_rows(ws)["CD"], 3).comment
    assert comment is not None
    assert "7.5" in comment.text and "10" in comment.text
    assert "shop measured" in comment.text
    assert "not approved" in comment.text  # the review-aid contract travels with the file


def test_review_shows_dims_that_moved_because_of_an_override(tmp_path):
    """A dim that DEPENDS on an override must report its post-override value, while the
    overridden dim itself keeps the formula reading it replaced.

    This template's CH is `= C13 + C27 + C28` and C27 is TF, so overriding TF moves CH.
    Reporting the stale CH would hide the knock-on from anyone reviewing the app instead
    of opening the workbook (John 2026-07-30, found on the real 2901 submittal).
    """
    plain = _write(tmp_path, [_dx()], "t10.xlsx")
    base = plain["sheets"][0]["computed_dims"]
    bumped = _write_with_overrides(tmp_path, [_dx()], "t11.xlsx",
                                   _override_payload("CDXC-1", {"TF": base["TF"] + 1.0}))
    got = bumped["sheets"][0]["computed_dims"]

    # The overridden dim reports what the sheet's own formula said — NOT the override,
    # which would make every override a self-confirming match.
    assert got["TF"] == base["TF"]
    # ...but CH followed the override.
    assert got["CH"] == base["CH"] + 1.0
    # An unrelated dim is untouched.
    assert got["CD"] == base["CD"]


def test_refill_replaces_the_previous_copy(tmp_path):
    """Same submittal filled twice -> ONE file, not '... (2).xlsx' (John 2026-07-30)."""
    first = _write(tmp_path, [_dx()], "t12.xlsx")
    second = _write_with_overrides(tmp_path, [_dx()], "t12.xlsx",
                                   _override_payload("CDXC-1", {"TF": 9.5}))
    assert first["saved_path"] == second["saved_path"]
    assert len(list(tmp_path.glob("t12*.xlsx"))) == 1
    # And the surviving file is the LATEST one (the override), not the first write.
    ws = openpyxl.load_workbook(second["saved_path"])["CDXC-1"]
    assert ws.cell(_rows(ws)["TF"], 3).value == 9.5


def test_locked_previous_copy_falls_back_to_a_numbered_name(tmp_path, monkeypatch):
    """If the previous copy is open in Excel the replace is impossible — fall back to a
    numbered name rather than losing the engineer's fill."""
    from coilforge.checklist import excel_writer

    first = _write(tmp_path, [_dx()], "t13.xlsx")
    real_remove = os.remove

    def _locked(path, *a, **k):
        if str(path) == first["saved_path"]:
            raise PermissionError("open in Excel")
        return real_remove(path, *a, **k)

    monkeypatch.setattr(excel_writer.os, "remove", _locked)
    second = _write(tmp_path, [_dx()], "t13.xlsx")
    assert second["saved_path"] != first["saved_path"]
    assert second["saved_path"].endswith("(2).xlsx")
    assert os.path.exists(first["saved_path"])  # the locked file is left alone


def test_writer_without_overrides_writes_no_comments(tmp_path):
    res = _write(tmp_path, [_dx()], "t9.xlsx")
    ws = openpyxl.load_workbook(res["saved_path"])["CDXC-1"]
    assert res["overridden_dims"] == []
    assert ws.cell(_rows(ws)["CD"], 3).comment is None
