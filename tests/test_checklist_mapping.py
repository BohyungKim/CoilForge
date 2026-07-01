"""Phase 1 — pure checklist mapping tests (no Excel).

Covers: sheet selection / removal, UNIT/SIZE token translation, deterministic
APPLICATION, DX<->HGRH pairing (W/HGRH + HGRH CONN SZ), collared-holes-on /
stacking-flanges-off constants, header passthroughs, and engine-resolved dims
mirroring the drawing. The DX coil mirrors the live-workbook Terra V example.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.checklist.mapping import build_checklist_fill, _to_size, _dim_slot
from coilforge.checklist import template_map as T


def _cells(sheet):
    return {c.label: c for c in sheet.cells}


def _dx_coil(**over):
    coil = dict(
        tag="CDXC-1", coil_type="DX", product_label="NOVA", unit_size="C24",
        quantity=1, finned_height=45.0, finned_length=54.0, rows=5, feeds=9,
        circuits=2, suction_conn_size=2.0, qty_conn_per_header=2, coil_hand="L",
        coating=None,
    )
    coil.update(over)
    return coil


# --- token translation -----------------------------------------------------
def test_size_token_translation():
    assert _to_size("NOVA", "C24") == "C24"
    assert _to_size("VENTUM H", "H05") == "H05"
    assert _to_size("VENTUM+", "V20") == "V20"
    assert _to_size("TERRA H", "009") == 9          # numeric dropdown
    assert _to_size("TERRA V", "084") == "TV084"    # TV-prefixed dropdown
    assert _to_size("NOVA", "ZZZ") is None          # not a valid option


def test_dim_slot_mapping():
    assert _dim_slot("CD") == "slot.CD"
    assert _dim_slot("RB") == "slot.RB"
    assert _dim_slot("I1") == "slot.I1"
    assert _dim_slot("S3") == "slot.S3"
    assert _dim_slot("O2") == "slot.O2"
    assert _dim_slot("R4") == "slot.R4"
    assert _dim_slot("HD2") == "slot.HD2"   # even -> return header
    assert _dim_slot("HD1") == "slot.HDx1"  # odd -> distributor
    assert _dim_slot("DIST EXTENTION") == "slot.DIST_EXT"
    assert _dim_slot("I/O") == "slot.O2"
    assert _dim_slot("DIST ORIENTATION") is None


# --- single DX coil --------------------------------------------------------
def test_single_dx_keeps_only_dx_and_renames():
    fill = build_checklist_fill([_dx_coil()])
    assert [s.category for s in fill.sheets] == ["DX"]
    assert fill.sheets[0].sheet_tag == "CDXC-1"
    assert fill.sheets[0].source_sheet == "DX"
    # The other three category sheets are removed; support sheets are never listed.
    assert set(fill.remove_sheets) == {"HWC", "CWC", "HGRH"}


def test_dx_header_passthroughs_and_constants():
    fill = build_checklist_fill([_dx_coil()])
    cells = _cells(fill.sheets[0])
    assert cells["UNIT"].value == "NOVA" and cells["UNIT"].status == "detected"
    assert cells["SIZE"].value == "C24"
    assert cells["APPLICATION"].value == "DECOUPLED"  # fixed for DX NOVA
    assert cells["COATING"].value == "NONE"
    assert cells["COIL TAG"].value == "CDXC-1"
    assert cells["QTY"].value == 1
    assert cells["FH"].value == 45.0 and cells["FL"].value == 54.0
    assert cells["ROWS"].value == 5
    assert cells["FEEDS/CIRCUITS"].value == 9
    assert cells["SUCTION CONN SZ"].value == 2.0
    assert cells["QTY CONN /HEADER"].value == 2
    assert cells["HANDING"].value == "LH"
    # constants John pinned
    assert cells["COLLARED HOLES"].value is True
    assert cells["STACKING FLANGES"].value is False
    # ASC is a sheet formula (=Hot Gas Bypass), so it must NOT be a written cell.
    assert "ASC" not in cells


def test_rb_is_written_input_not_compared():
    # RB is a direct-coil value (John 2026-07-01): DX/HGRH=1.5. It must be WRITTEN
    # (overwriting the stale template formula), not left as a formula to compare.
    fill = build_checklist_fill([_dx_coil()])
    cells = _cells(fill.sheets[0])
    comp = _compare(fill.sheets[0])
    assert cells["RB"].value == 1.5
    assert cells["RB"].source.startswith("engine:slot.RB")
    assert "RB" not in comp  # not double-counted as a formula comparison


def test_dx_special_coating_passthrough():
    fill = build_checklist_fill([_dx_coil(coating="ELECTROFIN")])
    cells = _cells(fill.sheets[0])
    assert cells["COATING"].value == "ELECTROFIN"
    assert cells["COATING"].status == "review_required"


def _compare(sheet):
    return {d.label: d for d in sheet.compare_dims}


def test_lower_dims_are_not_written_but_compared():
    # Lower dims are Excel formulas — they must NOT appear as written input cells,
    # but DO appear as comparison dims carrying CoilForge's engine value.
    fill = build_checklist_fill([_dx_coil()])
    cells = _cells(fill.sheets[0])
    comp = _compare(fill.sheets[0])
    assert "CD" not in cells  # never overwrite the CD formula
    assert comp["CD"].slot == "slot.CD"
    assert comp["CD"].coilforge_value is not None  # NOVA C24 DX resolves CD


def test_dx_dims_beyond_circuit_count_are_na_in_compare():
    # circuits=2 -> circuit slots for k>2 (e.g. O6 -> k=3) are N/A in the comparison.
    comp = _compare(build_checklist_fill([_dx_coil(circuits=2)]).sheets[0])
    assert comp["O6"].coilforge_value == "N/A"
    assert comp["O8"].coilforge_value == "N/A"


# --- DX + HGRH pairing -----------------------------------------------------
def test_dx_hgrh_pairing_sets_whgrh_and_conn():
    coils = [
        _dx_coil(tag="CDXC-1"),
        dict(tag="RHHGRC-1", coil_type="HGRH", product_label="NOVA",
             unit_size="C24", quantity=1, finned_height=12.0, finned_length=54.0,
             rows=1, feeds=1, circuits=1, conn_size=1.125, qty_conn_per_header=1,
             coil_hand="L"),
    ]
    fill = build_checklist_fill(coils)
    cats = {s.category: s for s in fill.sheets}
    assert set(cats) == {"DX", "HGRH"}
    assert set(fill.remove_sheets) == {"HWC", "CWC"}
    dx = _cells(cats["DX"])
    assert dx["W/ HGRH"].value is True
    assert dx["HGRH CONN SZ"].value == 1.125


def test_dx_alone_has_whgrh_false():
    fill = build_checklist_fill([_dx_coil()])
    assert _cells(fill.sheets[0])["W/ HGRH"].value is False


# --- unknown product -> flagged, not crashed -------------------------------
def test_unknown_product_flags_unit_and_dims():
    fill = build_checklist_fill([_dx_coil(product_label=None, unit_size=None)])
    cells = _cells(fill.sheets[0])
    comp = _compare(fill.sheets[0])
    assert cells["UNIT"].value is None and cells["UNIT"].status == "blocked"
    # No engine -> CD comparison value is unresolved (None), never guessed.
    assert comp["CD"].coilforge_value is None
    assert any("UNIT not detected" in w for w in fill.warnings)


def test_export_flags_are_review_aid():
    fill = build_checklist_fill([_dx_coil()])
    assert fill.export_allowed is False
    assert fill.production_drawing_approval_claimed is False
