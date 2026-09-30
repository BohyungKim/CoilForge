"""CCSI harvest cross-check (Step C) + the harvest's read-only guarantee."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ccsi.crosscheck import crosscheck_coil  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HARVEST = json.loads((ROOT / "examples/sanitized/ccsi_harvest_dx_sample.json").read_text(encoding="utf-8"))

SOURCES = {
    "tag": "CDXC-1",
    "coil_quantity": 1,
    "finned_height": {"value": 30, "status": "review_required"},
    "finned_length": {"value": 33, "status": "review_required"},
    "rows_deep": {"value": 6, "status": "review_required"},
    "fins_per_inch": {"value": 11, "status": "review_required"},  # CCSI saved 12 -> mismatch
    "number_of_feeds": {"value": 15, "status": "review_required"},
    "fin_material": {"value": "0.008", "status": "review_required"},  # thickness only -> off vocabulary
    "fin_surface": {"value": "Flat", "status": "review_required"},
    "coil_hand": {"value": "Left", "status": "review_required"},
    "return_connection_size": {"value": 1.125, "status": "review_required"},
    "total_air_flow_cfm": {"value": 2660, "status": "review_required"},
    "entering_dry_bulb_f": {"value": 95, "status": "review_required"},
    "leaving_dry_bulb_f": {"value": 52.18, "status": "review_required"},
    "total_capacity_mbh": {"value": 242.05, "status": "review_required"},
    "refrigerant": {"value": "R-32", "status": "review_required"},
    "evaporating_temp_f": {"value": 43, "status": "review_required"},
    "superheat_f": {"value": 9, "status": "review_required"},
}


def _rows(**kw):
    return {r["ccsi_id"]: r for r in crosscheck_coil(HARVEST, SOURCES, coil_type="DX", **kw)}


def test_matches_after_normalization() -> None:
    rows = _rows()
    for ccsi_id in ("Tag", "FinnedHeight", "RowsDeep", "FinSurface", "CoilHand", "DXReturnConnectionSize",
                    "TotalAirFlow", "EnteringDryBulb", "Refrigerant", "Superheat"):
        assert rows[ccsi_id]["verdict"] == "match", (ccsi_id, rows[ccsi_id])


def test_each_verdict_class_is_produced() -> None:
    rows = _rows()
    assert rows["FinsPerInch"]["verdict"] == "mismatch"
    assert rows["FinMaterial"]["verdict"] == "off_vocabulary"
    assert rows["FinMaterial"]["coilforge"] == "0.008"  # raw source value kept as evidence
    assert rows["EnteringWetBulb"]["verdict"] == "submittal_missing"
    assert rows["RefrigerationSystemType"]["verdict"] == "submittal_missing"  # D6: needs circuits
    assert rows["MysteryOption"]["verdict"] == "unmapped_ccsi_field"
    assert rows["Capacity"]["verdict"] == "not_persisted"
    assert rows["TubeMaterial"]["verdict"] == "absent_on_form"


def test_a_fin_with_its_material_matches_the_ccsi_option() -> None:
    # D1: the ledger keeps the material in the draft field's unit ("0.008" + "Aluminum")
    sources = {**SOURCES, "fin_material": {"value": 0.008, "unit": "Aluminum", "status": "review_required"}}
    row = {r["ccsi_id"]: r for r in crosscheck_coil(HARVEST, sources, coil_type="DX")}["FinMaterial"]
    assert row["verdict"] == "match" and row["coilforge"] == "Aluminum 0.008"


def test_a_value_ccsi_left_blank_is_not_called_both_missing() -> None:
    harvest = {"fields": {"EnteringDryBulb": {"label": "EDB", "kind": "number", "value": "", "ro": False}}}
    rows = {r["ccsi_id"]: r for r in crosscheck_coil(harvest, SOURCES, coil_type="DX")}
    assert rows["EnteringDryBulb"]["verdict"] == "ccsi_blank"


def test_a_size_ccsi_calculates_reads_as_not_persisted() -> None:
    options = ["Calculate", '7/8"']
    harvest = {"fields": {"DXReturnConnectionSize": {"label": "Return", "kind": "select", "value": "Calculate",
                                                     "ro": False, "options": options}}}
    src = {**SOURCES, "return_connection_size": {"value": 0.875, "status": "review_required"}}
    rows = {r["ccsi_id"]: r for r in crosscheck_coil(harvest, src, coil_type="DX")}
    assert rows["DXReturnConnectionSize"]["verdict"] == "not_persisted"


def test_computed_values_use_a_relative_band() -> None:
    assert _rows()["LeavingDryBulb"]["verdict"] == "match"  # 52.18 vs 52.3 within 1%


def test_dimension_fields_can_be_excluded() -> None:
    assert "HS" in _rows()
    assert "HS" not in _rows(ignore_ids=frozenset({"HS"}))


def test_unknown_coil_type_reports_every_field_unmapped() -> None:
    rows = crosscheck_coil(HARVEST, SOURCES, coil_type="NOPE")
    assert rows and {r["verdict"] for r in rows} == {"unmapped_ccsi_field"}


def test_crosscheck_script_groups_by_category_and_lists_unmatched() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import ccsi_crosscheck as script  # pyright: ignore[reportMissingImports]

    ledger = {"DX": [{"project": "SAMPLE", "tag": "CDXC-1", "sources": SOURCES}]}
    stray = {**HARVEST, "tag": "CDXC-9"}
    report = script.build([HARVEST, stray], ledger)
    assert len(report["DX"]["coils"]) == 1
    assert "HS" not in report["DX"]["fields"]  # drawing dims belong to the dimension map
    assert report["_unmatched_harvests"]["unmatched"] == ["SAMPLE/CDXC-9"]
    assert "`FinsPerInch`" in script.render_markdown("DX", report["DX"])


# --- read-only guarantee ------------------------------------------------------------

_WRITE_PATTERNS = [
    r"\.value\s*=(?!=)",
    r"\.checked\s*=(?!=)",
    r"selectedIndex\s*=(?!=)",
    r"dispatchEvent",
    r"\.click\(",
    r"\.submit\(",
    r"new Event\(",
    r"fetch\(",
    r"XMLHttpRequest",
]


def test_harvest_snippet_never_writes_to_the_page() -> None:
    js = (ROOT / "web/ccsi/ccsi_harvest_snippet.js").read_text(encoding="utf-8")
    code = "\n".join(line for line in js.splitlines() if not line.strip().startswith("//"))
    for pattern in _WRITE_PATTERNS:
        assert not re.search(pattern, code), pattern


def test_harvest_skill_forbids_mutations_and_uses_the_snippet() -> None:
    skill = (ROOT / ".claude/commands/ccsi-harvest.md").read_text(encoding="utf-8")
    assert "ccsi_harvest_snippet.js" in skill
    for word in ("Calculate", "Save", "Apply", "Cancel"):
        assert word in skill  # each named explicitly as forbidden
    assert "READ-ONLY" in skill
