"""Phase 3 — adapter + comparison tests (pure; no Excel, no PDF)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.checklist.compare import build_review, _match
from coilforge.checklist.from_workflow import coil_inputs_from_candidates
from coilforge.checklist.mapping import build_checklist_fill


def _fv(value):
    return {"value": value, "source_evidence": [], "confidence": "inferred", "status": "ready"}


def _dx_candidate():
    return {
        "tag": _fv("CDXC-1"),
        "quantity": _fv(1),
        "geometry": {
            "finned_height": _fv(45.0), "finned_length": _fv(54.0),
            "rows_deep": _fv(5), "number_of_feeds": _fv(9), "circuits": _fv(2),
        },
        "connections": {
            "coil_hand": _fv("L"), "suction_connection_size": _fv(2.0),
            "qty_connections_per_header": _fv(2),
        },
        "manufacturing_options": {"coil_coating": _fv(None)},
    }


# --- adapter ---------------------------------------------------------------
def test_adapter_builds_coil_inputs_with_override():
    coils, (line, size) = coil_inputs_from_candidates(
        [_dx_candidate()], product_line="NOVA", unit_size="C24"
    )
    assert (line, size) == ("NOVA", "C24")
    assert len(coils) == 1
    c = coils[0]
    assert c["tag"] == "CDXC-1" and c["coil_type"] == "DX"
    assert c["finned_height"] == 45.0 and c["circuits"] == 2
    assert c["suction_conn_size"] == 2.0 and c["coil_hand"] == "L"


def test_adapter_skips_unknown_category():
    coils, _ = coil_inputs_from_candidates(
        [{"tag": _fv("ZZZ-1")}], product_line="NOVA", unit_size="C24"
    )
    assert coils == []


# --- comparison ------------------------------------------------------------
def test_match_helper():
    assert _match(7.5, 7.5) == "match"
    assert _match(7.5, 7.51) == "match"        # within tolerance
    assert _match(59.0, 59.25) == "mismatch"
    assert _match("N/A", "N/A") == "match"
    assert _match(2.0, None) == "missing_one"


def test_build_review_flags_mismatch():
    coils, _ = coil_inputs_from_candidates([_dx_candidate()], product_line="NOVA",
                                           unit_size="C24")
    fill = build_checklist_fill(coils)
    # Simulate the writer's read-back: checklist OAL diverges from CoilForge.
    cf = {d.label: d.coilforge_value for d in fill.sheets[0].compare_dims}
    computed = dict(cf)
    computed["OAL"] = (cf.get("OAL") or 0) + 0.25  # inject the known RB-driven gap
    writer_result = {
        "saved_path": r"C:\Users\X\Downloads\demo.xlsx",
        "sheets": [{"tag": "CDXC-1", "category": "DX", "computed_dims": computed}],
        "removed": ["HWC", "CWC", "HGRH"], "skipped_labels": [],
    }
    review = build_review(fill, writer_result)
    assert review["export_allowed"] is False
    assert review["mismatch_total"] >= 1
    dx = review["sheets"][0]
    oal = next(c for c in dx["comparisons"] if c["label"] == "OAL")
    assert oal["verdict"] == "mismatch"
    cd = next(c for c in dx["comparisons"] if c["label"] == "CD")
    assert cd["verdict"] == "match"
    # input cells carried through with provenance
    assert any(i["label"] == "UNIT" and i["value"] == "NOVA" for i in dx["inputs"])
