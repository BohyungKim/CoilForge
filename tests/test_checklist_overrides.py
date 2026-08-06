"""Manual browser fills carried into the Coil Checklist (pure; no Excel, no PDF).

Covers the 2026-07-29 fix for "the drawing updated but the checklist still shows the old
value": Tier-A engine inputs land in the sheet's INPUT cells, Tier-B drawing-param
overrides replace the matching dimension row (with the engine proposal preserved), and a
fill with NO overrides reproduces the previous ChecklistFill exactly.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.checklist.mapping import build_checklist_fill
from coilforge.checklist.overrides import (
    apply_engine_inputs,
    dim_overrides_by_slot,
    normalize_coil_overrides,
    param_slot,
)


def _dx_coil(**over):
    coil = {
        "tag": "CDXC-1", "coil_type": "DX", "product_label": "NOVA", "unit_size": "C24",
        "quantity": 1, "finned_height": 45.0, "finned_length": 54.0, "rows": 5,
        "feeds": 9, "circuits": 2, "suction_conn_size": 2.0, "qty_conn_per_header": 2,
        "coil_hand": "L", "coating": None,
    }
    coil.update(over)
    return coil


def _hwc_coil(**over):
    coil = {
        "tag": "HHWC-1", "coil_type": "HWC", "product_label": "NOVA", "unit_size": "C24",
        "quantity": 1, "finned_height": 30.0, "finned_length": 40.0, "rows": 2,
        "feeds": 4, "circuits": 1, "inlet_conn_size": 1.5, "outlet_conn_size": 1.5,
        "coil_hand": "L", "coating": None, "application": "STANDALONE",
    }
    coil.update(over)
    return coil


def _payload(tag, engine_inputs=None, param_overrides=None, reason="wrong on the submittal"):
    return [{
        "tag": tag,
        "engine_inputs": engine_inputs or {},
        "param_overrides": [
            {"key": k, "value": v, "unit": "in", "override_reason": reason}
            for k, v in (param_overrides or {}).items()
        ],
        "reason": reason,
    }]


def _cell(sheet, label):
    return next(c for c in sheet.cells if c.label.upper().replace(" ", "") == label.upper().replace(" ", ""))


def _dim(sheet, label):
    return next(d for d in sheet.compare_dims if d.label == label)


# --- normalization ---------------------------------------------------------
def test_normalize_reads_snake_case_and_camel_case():
    snake = normalize_coil_overrides(_payload("CDXC-1", {"rows": 6}, {"TF": 1.25}))
    camel = normalize_coil_overrides([{
        "tag": "CDXC-1",
        "engineInputs": {"rows": 6},
        "paramOverrides": [{"key": "TF", "value": 1.25, "override_reason": "r"}],
    }])
    assert snake["CDXC-1"].engine_inputs == {"rows": 6}
    assert camel["CDXC-1"].engine_inputs == {"rows": 6}
    assert snake["CDXC-1"].param_overrides == camel["CDXC-1"].param_overrides == {"TF": 1.25}


def test_normalize_drops_blanks_and_flags_fields_with_no_checklist_analog():
    got = normalize_coil_overrides(_payload("CDXC-1", {"rows": "", "header_count": 2, "feeds": 7}))
    ov = got["CDXC-1"]
    assert ov.engine_inputs == {"feeds": 7}       # blank input is not a fill
    assert ov.ignored_keys == ("header_count",)   # surfaced, never silently dropped
    assert normalize_coil_overrides(None) == {}
    assert normalize_coil_overrides([{"tag": "X"}]) == {}  # nothing filled -> no entry


def test_apply_engine_inputs_copies_and_records_previous():
    coil = _dx_coil()
    ov = normalize_coil_overrides(_payload("CDXC-1", {"rows": 6, "return_conn_size": 1.375}))["CDXC-1"]
    updated, notes = apply_engine_inputs(coil, ov, "DX")
    assert coil["rows"] == 5 and coil["suction_conn_size"] == 2.0  # caller's dict untouched
    assert updated["rows"] == 6
    # return_conn_size is the DX sheet's SUCTION CONN SZ, the HGRH sheet's CONN SZ.
    assert updated["suction_conn_size"] == 1.375
    assert notes["rows"].previous_value == 5
    assert notes["suction_conn_size"].key == "return_conn_size"


def test_return_conn_size_routes_per_category():
    ov = normalize_coil_overrides(_payload("X", {"return_conn_size": 0.875}))["X"]
    assert apply_engine_inputs({}, ov, "HGRH")[0]["conn_size"] == 0.875
    assert apply_engine_inputs({}, ov, "HWC")[0]["outlet_conn_size"] == 0.875


# --- Tier-B key -> slot (shared with the drawing path) ----------------------
def test_param_slot_matches_the_drawing_paths_mapping():
    assert param_slot("TF") == "slot.TF"
    assert param_slot("CD") == "slot.CD"
    assert param_slot("HDx1") == "slot.HDx1"
    assert param_slot("S") == "slot.S1"          # base key = header 1
    assert param_slot("O") == "slot.O2"
    assert param_slot("S2") == "slot.S3"         # logical header 2 -> parity supply id
    assert param_slot("HD2") == "slot.HD4"       # logical header 2 -> parity return id
    assert param_slot("ZD") is None              # owner-fixed constant, no slot


def test_dim_overrides_by_slot_reports_unmapped():
    ov = normalize_coil_overrides(_payload("X", None, {"TF": 1.25, "ZD": 4.5}))["X"]
    by_slot, unmapped = dim_overrides_by_slot(ov)
    assert by_slot["slot.TF"][0] == "TF" and by_slot["slot.TF"][1] == 1.25
    assert unmapped == ("ZD",)


# --- end-to-end through build_checklist_fill -------------------------------
def test_no_overrides_reproduces_the_original_fill():
    """H4-style regression guard: the pre-override path must be untouched."""
    coils = [_dx_coil()]
    assert build_checklist_fill(coils) == build_checklist_fill(coils, {})
    assert build_checklist_fill(coils) == build_checklist_fill(coils, None)
    sheet = build_checklist_fill(coils).sheets[0]
    assert all(c.override is None for c in sheet.cells)
    assert all(d.override is None for d in sheet.compare_dims)


def test_tier_a_input_lands_in_the_cell_and_is_marked_review_required():
    overrides = normalize_coil_overrides(
        _payload("CDXC-1", {"rows": 6, "coil_hand": "Right"}, reason="submittal misread")
    )
    sheet = build_checklist_fill([_dx_coil()], overrides).sheets[0]
    rows = _cell(sheet, "ROWS")
    assert rows.value == 6
    assert rows.status == "review_required"          # human-supplied is never 'ready'
    assert rows.source == "manual_override:rows"
    assert "was 5" in rows.note and "submittal misread" in rows.note
    assert rows.override.previous_value == 5
    hand = _cell(sheet, "HANDING")
    assert hand.value == "RH"                        # picker vocabulary is normalized
    assert hand.override is not None


def test_tier_a_engine_input_moves_the_compared_dimension_too():
    """The written input and the CoilForge compare column must not disagree: the engine
    pass runs on the corrected coil, so both move together."""
    base = build_checklist_fill([_dx_coil()]).sheets[0]
    overrides = normalize_coil_overrides(_payload("CDXC-1", {"circuits": 4}))
    bumped = build_checklist_fill([_dx_coil()], overrides).sheets[0]
    # circuits gate the "N/A beyond the circuit count" columns — with 2 circuits S5 is
    # N/A, with 4 it is a real (or at least non-N/A) dimension.
    assert _dim(base, "S5").coilforge_value == "N/A"
    assert _dim(bumped, "S5").coilforge_value != "N/A"


def test_application_override_beats_the_per_unit_constant():
    overrides = normalize_coil_overrides(_payload("CDXC-1", {"application": "INTEGRATED"}))
    sheet = build_checklist_fill([_dx_coil()], overrides).sheets[0]
    app = _cell(sheet, "APPLICATION")
    assert app.value == "INTEGRATED"       # NOVA's fixed DECOUPLED is overridden
    assert app.override is not None
    assert build_checklist_fill([_dx_coil()]).sheets[0]
    assert _cell(build_checklist_fill([_dx_coil()]).sheets[0], "APPLICATION").value == "DECOUPLED"


def test_tier_b_override_replaces_the_dim_and_keeps_the_engine_proposal():
    machine = _dim(build_checklist_fill([_dx_coil()]).sheets[0], "TF").coilforge_value
    overrides = normalize_coil_overrides(_payload("CDXC-1", None, {"TF": 9.75}))
    sheet = build_checklist_fill([_dx_coil()], overrides).sheets[0]
    tf = _dim(sheet, "TF")
    assert tf.coilforge_value == 9.75              # what the drawing shows
    assert tf.override.previous_value == machine   # what it replaced
    assert tf.override.key == "TF"
    # Only the overridden row is touched.
    assert _dim(sheet, "CD").override is None


def test_tier_b_multi_header_key_hits_the_parity_encoded_row():
    overrides = normalize_coil_overrides(_payload("CDXC-1", None, {"S2": 3.0, "HDx1": 5.0}))
    sheet = build_checklist_fill([_dx_coil()], overrides).sheets[0]
    assert _dim(sheet, "S3").coilforge_value == 3.0    # logical header 2 == parity id 3
    assert _dim(sheet, "HD1").coilforge_value == 5.0   # distributor HD is the odd row


def test_tier_b_water_coil_uses_the_water_sheets_labels():
    overrides = normalize_coil_overrides(_payload("HHWC-1", None, {"O": 2.75, "HD": 3.5}))
    sheet = build_checklist_fill([_hwc_coil()], overrides).sheets[0]
    assert _dim(sheet, "I/O").coilforge_value == 2.75   # water sheet names slot.O2 "I/O"
    assert _dim(sheet, "HD").coilforge_value == 3.5


def test_override_with_no_row_on_this_sheet_is_warned_not_dropped():
    overrides = normalize_coil_overrides(_payload("HHWC-1", {"header_count": 2}, {"ZD": 4.5}))
    fill = build_checklist_fill([_hwc_coil()], overrides)
    joined = " | ".join(fill.warnings)
    assert "ZD" in joined and "no checklist dimension row" in joined
    assert "header_count" in joined
