"""Tests for the candidate -> coil-input adapter: per-coil product detection
(mixed-unit submittals), drain-pan partner inheritance, and circuits = QTY
CONN/HEADER when the CoilMaster prose lacks an explicit circuit count.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.checklist.from_workflow import coil_inputs_from_candidates


def _fv(value):
    return {"value": value, "source_evidence": [], "confidence": "inferred", "status": "ready"}


def _cand(tag, model, *, feeds=4, qty_conn=1, circuits=None):
    geom = {"finned_height": _fv(15.0), "finned_length": _fv(19.0),
            "rows_deep": _fv(6), "number_of_feeds": _fv(feeds)}
    if circuits is not None:
        geom["circuits"] = _fv(circuits)
    return {
        "tag": _fv(tag),
        "quantity": _fv(1),
        "notes": [f"Cover product/model code: {model}"] if model else [],
        "geometry": geom,
        "connections": {"coil_hand": _fv("L"), "suction_connection_size": _fv(0.875),
                        "qty_connections_per_header": _fv(qty_conn)},
        "manufacturing_options": {"coil_coating": _fv(None)},
    }


def _by_tag(coils):
    return {c["tag"]: c for c in coils}


def test_per_coil_detection_mixed_units():
    # One submittal, two different units: NOVA B20 pair + Terra H 024 pair.
    coils, _ = coil_inputs_from_candidates([
        _cand("CDXC-1", "B20_H_I_ERV"),
        _cand("RHHGRC-1", "B20_H_I_ERV", feeds=1),
        _cand("CDXC-2", "TR_C_024", feeds=6),
    ], pdf_text="")
    c = _by_tag(coils)
    assert (c["CDXC-1"]["product_label"], c["CDXC-1"]["unit_size"]) == ("NOVA", "B20")
    assert (c["CDXC-2"]["product_label"], c["CDXC-2"]["unit_size"]) == ("TERRA H", "024")


def test_partner_inherits_product_when_own_code_absent():
    # RHHGRC-2 has no model code -> inherits its DX partner CDXC-2 (Terra H 024).
    coils, _ = coil_inputs_from_candidates([
        _cand("CDXC-2", "TR_C_024", feeds=6),
        _cand("RHHGRC-2", None, feeds=3),
    ], pdf_text="")
    rh = _by_tag(coils)["RHHGRC-2"]
    assert (rh["product_label"], rh["unit_size"]) == ("TERRA H", "024")


def test_circuits_defaults_to_qty_conn_per_header():
    coils, _ = coil_inputs_from_candidates([_cand("CDXC-1", "B20_H_I_ERV", feeds=4, qty_conn=1)])
    assert _by_tag(coils)["CDXC-1"]["circuits"] == 1  # qty_conn, not feeds(4)


def test_explicit_prose_circuits_wins_over_qty_conn():
    coils, _ = coil_inputs_from_candidates([_cand("CDXC-1", "B20_H_I_ERV", qty_conn=1, circuits=2)])
    assert _by_tag(coils)["CDXC-1"]["circuits"] == 2  # prose circuit count preferred


def test_explicit_override_applies_to_all():
    coils, det = coil_inputs_from_candidates(
        [_cand("CDXC-1", "B20_H_I_ERV")], product_line="TERRA H", unit_size="024"
    )
    assert (coils[0]["product_label"], coils[0]["unit_size"]) == ("TERRA H", "024")
    assert det == ("TERRA H", "024")
