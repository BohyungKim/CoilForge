"""Extra coil-data fields from a CCSI report PDF's quote, drawing and notes (report_extras).

Page texts follow PyMuPDF's line layout of real reports (sanitized: no customer names).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ccsi.report_extras import extract_extras, merge_extras  # noqa: E402

QUOTE = "\n".join([
    "COIL QUOTE", "Project Name:", "SAMPLE - Rev 1",
    "1.", "3DX-05-12.0-11-36.0-6 DX Coil", "Handing:", "Left", "Quantity:", "One (1)", "Tagged:", "CDXC-1",
    "Tubes:", "3/8 1.00 x 0.866 x Copper - 0.016 Plain", "Casing:", "Galvanized Steel 16 gauge",
    "Coating:", "ElectroFin Coating", "Cost Each:", "CAN$1.00",
    "2.", "3DC-02-12.0-08-36.0-2 Condenser Coil", "Tagged:", "RHHGRC-1", "Tubes:", "3/8 1.00 x 0.866 x Copper - 0.016 Plain",
    "Cost Each:", "CAN$1.00", "Total Cost (All Items):",
])
DX_DRAWING = "\n".join([
    "5 1/2", "3.464 FIN", "ITEM TAG", "CDXC-1", "NOTES:Copper Straps Required",
    "0.008\" AL FLAT", "11", "GALV 16 GA.", "QTY 2 x 1620-4-1/4-J1/9-5/8 (18\" LEADS)",
    "5", "12", "(03+03INT)", "DIRECT COIL", "INC.",
])
HGRH_DRAWING = "\n".join([
    "ITEM TAG", "RHHGRC-1", "0.008\" AL FLAT", "8", "GALV 16 GA.", "1+2 - 0.625\" O.D. TYPE 'L' COPPER",
    "2", "12", "2", "DIRECT COIL", "INC.",
])
WATER_REPORT = "\n".join([
    "CHILLED WATER COIL REPORT", "Coil Tag: CCWC-1", "Physical Data", "Notes:", "**OPPOSITE END COIL REQUIRED**",
])
WATER_DRAWING = "\n".join([
    "ITEM TAG", "CCWC-1", "1/8\"FPT VENT + 1/8\"FPT DRAIN", "STEEL MPT CONNECTION 1 1/4\"", "2", "18", "5",
    "DIRECT COIL",
])


def _record(coil_type, tag, model=None, **fields):
    return {"coil_type": coil_type, "base_tag": tag, "model_number": model, "flags": [],
            "fields": {k: {"label": k, "kind": "number", "value": v} for k, v in fields.items()}}


def test_extras_are_read_from_quote_drawing_and_notes() -> None:
    extras = extract_extras([QUOTE, DX_DRAWING, HGRH_DRAWING, WATER_REPORT, WATER_DRAWING])
    assert extras["CDXC-1"]["CoilCoating"]["value"] == "ElectroFin Coating"
    assert extras["CDXC-1"]["DXDistCapillarySize"]["value"] == "1/4"
    assert extras["CDXC-1"]["_drawing_circuits"]["value"] == "6"      # (03+03INT), corroboration only
    assert extras["RHHGRC-1"]["_drawing_circuits"]["value"] == "2"
    assert "CoilCoating" not in extras["RHHGRC-1"]                      # no Coating line: nothing, not Plain
    # the report's OPPOSITE END note is not the form's Connection Ends (calibration, 2026-09-30)
    assert "ConnectionEnds" not in extras.get("CCWC-1", {})
    assert extras["CCWC-1"]["DrainAndVent"]["value"] == '1/8"'


def test_merge_resolves_map_options_and_flags_what_it_cannot() -> None:
    dx = _record("DX", "CDXC-1", RowsDeep="5", FinnedHeight="12", NumberOfFeeds="6")
    merge_extras([dx], [QUOTE, DX_DRAWING])
    assert dx["fields"]["DXDistCapillarySize"]["value"] == "1/4 x 0.025"
    assert dx["fields"]["NumberOfFeeds"]["value"] == "6"               # the report page's own value stays
    assert dx["fields"]["CoilCoating"]["value"] == "ElectroFin Coating"  # not a CCSI option: raw + flag
    assert "unmatched_option:CoilCoating" in dx["flags"]


def test_hgrh_feeds_come_from_the_model_number_and_the_drawing_must_agree() -> None:
    good = _record("HGRH", "RHHGRC-1", model="3DC-02-12.0-08-36.0-2", RowsDeep="2")
    merge_extras([good], [HGRH_DRAWING])
    assert good["fields"]["NumberOfFeeds"]["value"] == "2"
    assert good["flags"] == []
    clash = _record("HGRH", "RHHGRC-1", model="3DC-02-12.0-08-36.0-3", RowsDeep="2")
    merge_extras([clash], [HGRH_DRAWING])
    assert "NumberOfFeeds" not in clash["fields"]
    assert "extras_inconsistent:NumberOfFeeds" in clash["flags"]
    no_model = _record("HGRH", "RHHGRC-1", RowsDeep="2")
    merge_extras([no_model], [HGRH_DRAWING])
    assert "NumberOfFeeds" not in no_model["fields"]      # the drawing alone never states it


def test_water_extras_land_on_the_water_map_ids() -> None:
    cwc = _record("CWC", "CCWC-1", model="5W-02-27.0-08-72.0-5", RowsDeep="2")
    merge_extras([cwc], [WATER_REPORT, WATER_DRAWING])
    assert cwc["fields"]["NumberOfFeeds"]["value"] == "5"      # tubes high 18 != FH 27: not used
    assert "ConnectionEnds" not in cwc["fields"]      # the OPPOSITE END note never becomes it
    assert cwc["fields"]["DrainAndVent"]["value"] == '1/8"'
    assert cwc["flags"] == []


def test_a_drawing_naming_several_coils_is_never_attributed() -> None:
    two = DX_DRAWING.replace("ITEM TAG", "ITEM TAG\nCDXC-2")
    assert "CDXC-1" not in extract_extras([two]) and "CDXC-2" not in extract_extras([two])


def test_unequal_vent_and_drain_sizes_stay_raw() -> None:
    odd = WATER_DRAWING.replace('1/8"FPT DRAIN', '1/4"FPT DRAIN')
    cwc = _record("CWC", "CCWC-1")
    merge_extras([cwc], [odd])
    assert cwc["fields"]["DrainAndVent"]["value"].startswith('1/8"FPT VENT')
    assert "unmatched_option:DrainAndVent" in cwc["flags"]


def test_the_airflow_unit_on_the_report_is_cciss_air_flow_basis() -> None:
    def record(raw):
        rec = _record("DX", "CDXC-1")
        rec["fields"]["TotalAirFlow"] = {"label": "Total Air Flow (All Coils)", "kind": "number", "value": "2000",
                                         "raw": raw}
        return merge_extras([rec], [])[0]
    assert record("2,000 ACFM")["fields"]["ACFM"]["value"] == "Actual"
    assert record("1,000 SCFM")["fields"]["ACFM"]["value"] == "Standard"
    assert "ACFM" not in record("2,000")["fields"]          # no unit printed: nothing is assumed
