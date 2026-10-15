"""CCSI selection-report parser + revision choice (the coil-data cross-check's source of truth).

Fixtures imitate the real report LAYOUT (two columns of label/value pairs, section headers with
no value, one coil per page) with synthetic values and no project identity."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ccsi import selection_report as sr  # noqa: E402
from coilforge.ccsi.coil_data_map import load_coil_data_map  # noqa: E402
from coilforge.ccsi.crosscheck import crosscheck_coil  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

HEADER = """{title} COIL REPORT
Company:
Date:
9/10/2026, 5:22:14 PM
Contact:
Reference:
SAMPLE
Tel:
PreparedBy:
Sample Engineer
Fax or Email:
Project Name:
SAMPLE - Rev 0
Coil Tag: {tag}
Coil Model Number: {model}
Hand: Right
Physical Data
"""

CONDENSER = HEADER.format(title="CONDENSER", tag="RHHGRC-1", model="3DC-01-21.0-11-32.0-2") + """Number Of Coils
1
Tube Diameter
3/8 1.00 x 0.866
Fin Height (Per Coil)
21.000"
Tube Material
Copper - 0.016 Plain
Fin Length (Per Coil)
32.000"
Fin Material
Aluminum 0.008
Number Of Rows Deep
1
Fin Style
Corrugated
Circuit Ratio
0.1
Connection Type
Sweat Copper
Fins Per Inch
11
Supply Connection Size
5/8"
Return Connection Size
1/2"
Casing Style
Standard
Header Material
Copper (L)
Casing Material
Galvanized Steel 16 gauge
System Type
Single-Circuit
Air Data
Refrigerant Data
Total Air Flow (All Coils)
2,000 ACFM
Refrigerant
R-32
Air Flow (Per Coil)
2,000 ACFM
Vapor Temperature
140.00 °F
Face Velocity
429 FPM
Condensing Temperature
115.00 °F
Altitude
0.00 FT
Subcooling
18.00 °F
Entering Dry Bulb
51.00 °F
Leaving Dry Bulb
70.88 °F
Fouling Factor
0.0000 ft²·°F·h/Btu
Capacity
Condenser Capacity /Coil (Total)
41.15 MBH (41.15)
Total Capacity /Coil (Total)
44.00 MBH (44.00)
Notes:
Coil is outside the scope of AHRI Standard 410.
"""

DX = HEADER.format(title="DX", tag="CDXC-1 (107A)", model="3DX-04-21.0-13-32.0-8") + """Number Of Coils
1
Tube Diameter
3/8 1.00 x 0.866
Fin Height (Per Coil)
21.000"
Tube Material
Copper - 0.016 Plain
Fin Length (Per Coil)
32.000"
Fin Material
Aluminum 0.008
Number Of Rows Deep
4
Fin Style
Corrugated
Number Of Feeds
8
Fins Per Inch
13
Supply Connection Size
2 x 1/2"
System Type
Dual-Circuit Intertwined
Return Connection Size
2 x 7/8"
Dist-1/Dist-2/Dist-3/Dist-4
(feeds)
2/2/2/2
Connection Type
Sweat Copper
Casing Style
Standard
Header Material
Copper (L)
Casing Material
Galvanized Steel 16 gauge
Air Data
Refrigerant Data
Total Air Flow (All Coils)
2,000 ACFM
Refrigerant
R-410A
Suction Temperature
43 °F
Face Velocity
429 FPM
Liquid Temperature
77 °F
Altitude
0.00 FT
Superheat
9 °F
Entering Dry Bulb
-7.60 °F
Entering Wet Bulb
68.44 °F
Leaving Dry Bulb
50.75 °F
Fouling Factor
0.0000 ft²·°F·h/Btu
Capacity
Total Capacity Per Coil (Total)
242.05 MBH (242.05)
Notes:
"""

HOT_WATER_QTY3 = HEADER.format(title="HOT WATER", tag="HHWC-1", model="5W-01-10.5-08-14.3-1") + """Number Of Coils
3
Tube Diameter
5/8 1.50 x 1.299
Fin Height (Per Coil)
10.500"
Tube Turbulators
No
Fin Length (Per Coil)
14.250"
Tube Material
Copper/Nickel 90/10 - 0.035 Plain
Number Of Rows Deep
1
Fin Material
Aluminum 0.008
Fin Style
Flat
Fins Per Inch
8
Connection Type
MPT Steel
Supply Connection Size
1"
Return Connection Size
1"
Header Material
Copper (L)
Casing Style
Standard
Casing Material
Galvanized Steel 16 gauge
Air Data
Fluid Data
Total Air Flow (All Coils)
1,200 SCFM
Fluid Type
Propylene Glycol
Air Flow (Per Coil)
400 SCFM
Fluid Ratio
40 %
Altitude
13.00 FT
Entering Fluid Temp
105.00 °F
Entering Dry Bulb
15.80 °F
Leaving Fluid Temp
90.00 °F
Leaving Dry Bulb
30.85 °F
Fluid Flow Rate Per Coil (Total)
6.83 GPM (20.49)
Fouling Factor
0.0000 ft²·°F·h/Btu
Fouling Factor
0.0005 ft²·°F·h/Btu
Capacity
Capacity Per Coil (Total)
43.51 MBH (130.54)
Notes:
"""

CHILLED_WATER = HEADER.format(title="CHILLED WATER", tag="CCWC-1", model="5W-06-18.0-10-36.0-9") + """Number Of Coils
1
Tube Material
Copper - 0.020 Plain
Fin Height (Per Coil)
18.000"
Number Of Rows Deep
6
Fin Length (Per Coil)
36.000"
Fins Per Inch
10
Fin Style
Flat
Air Data
Fluid Data
Entering Wet Bulb
67.00 °F
Total Capacity Per Coil (Total)
150.00 MBH (150.00)
Fouling Factor
0.0000 ft²·°F·h/Btu
Fouling Factor
0.0000 ft²·°F·h/Btu
Notes:
"""


def _parse(text: str) -> dict:
    record = sr.parse_report_page(text)
    assert record is not None
    return record


def _values(record: dict) -> dict:
    return {k: v["value"] for k, v in record["fields"].items()}


def test_condenser_page_lands_on_the_hgrh_maps_own_option_texts() -> None:
    rec = _parse(CONDENSER)
    assert rec["coil_type"] == "HGRH" and rec["component_type"] == "CondenserCoil"
    assert rec["base_tag"] == "RHHGRC-1" and not rec["multi_tag"] and rec["date"] == "2026-09-10T17:22:14"
    v = _values(rec)
    assert v["TubeMaterial"] == "Copper 0.016 Plain"  # the printed " - " separator is not the option text
    assert v["HeaderMaterial"] == "Copper" and v["HeaderWallSchedule"] == "(L)"
    assert v["RefrigerantConnectionType"] == "Sweat" and v["ConnectionMaterial"] == "Copper"
    assert v["Refrigerant"] == "R32" and v["TotalAirFlow"] == "2000" and v["LeavingDryBulb"] == "70.88"
    assert v["CoilHand"] == "Right" and v["Tag"] == "RHHGRC-1"
    assert v["Capacity"] == "44"  # Q1 ruled 2026-09-30 (John): the TOTAL line, not the condenser line
    assert "Condenser Capacity /Coil (Total)" in rec["unmapped_labels"]
    assert rec["unknown_labels"] == {} and "parse_inconsistent" not in rec["flags"]
    assert "outside the scope" in rec["notes"]


def test_dx_page_numbers_tags_and_wrapped_distributor_label() -> None:
    rec = _parse(DX)
    v = _values(rec)
    assert rec["base_tag"] == "CDXC-1" and rec["tag"] == "CDXC-1 (107A)"
    assert v["EnteringDryBulb"] == "-7.6"  # the sign is kept
    assert v["DXReturnConnectionSize"] == '7/8"'  # "2 x 7/8\"" -> the per-connection option
    assert v["Refrigerant"] == "R410a"  # the map's own option text, not the report's "R-410A"
    assert v["EvaporatingTemperature"] == "43" and v["Capacity"] == "242.05" and v["NumberOfFeeds"] == "8"
    assert "Dist-1/Dist-2/Dist-3/Dist-4 (feeds)" in rec["unmapped_labels"]
    assert rec["unknown_labels"] == {} and not [f for f in rec["flags"] if f.startswith("unmatched")]


def test_hot_water_takes_the_all_coils_flow_and_splits_mpt_steel() -> None:
    rec = _parse(HOT_WATER_QTY3)
    v = _values(rec)
    assert v["FluidFlowRate"] == "20.49"  # bracketed all-coils total; the map's GPM is (All Coils)
    assert v["Capacity"] == "43.51"  # capacity stays per coil
    assert v["TubeMaterial"] == "Copper/Nickel 90/10 - 0.035 Plain"  # an option that itself has " - "
    assert v["ConnectionType"] == "MPT" and v["ConnectionMaterial"] == "Steel"
    assert v["GlycolRatio"] == "40" and v["CoilQuantity"] == "3" and v["TotalAirFlow"] == "1200"
    # two different fouling factors: order does not say which is air side -> neither is emitted
    assert "AirSideFoulingFactor" not in v and "ambiguous_duplicate:Fouling Factor" in rec["flags"]
    assert "parse_inconsistent" not in rec["flags"]  # model 14.3 vs printed 14.25 is rounding


def test_equal_duplicate_fouling_fills_both_sides_and_missing_values_are_none() -> None:
    rec = _parse(CHILLED_WATER)
    v = _values(rec)
    assert v["AirSideFoulingFactor"] == "0" and v["TubeSideFoulingFactor"] == "0"
    assert v["EnteringWetBulb"] == "67" and v["Capacity"] == "150"


def test_a_label_with_no_value_does_not_shift_the_pairs() -> None:
    text = CONDENSER.replace("Fins Per Inch\n11\n", "Fins Per Inch\n")
    v = _values(_parse(text))
    assert "FinsPerInch" not in v and v["TubeDiameter"] == "3/8 1.00 x 0.866"
    assert v["CasingStyle"] == "Standard"  # the next pair still reads correctly


def test_model_number_catches_a_mispaired_value() -> None:
    rec = _parse(CONDENSER.replace("3DC-01-21.0-11-32.0-2", "3DC-01-21.0-12-32.0-2"))
    assert "parse_inconsistent" in rec["flags"]


def test_unknown_labels_are_reported_not_dropped() -> None:
    rec = _parse(CONDENSER.replace("Circuit Ratio\n0.1\n", "Brand New Label\nsomething\n"))
    assert rec["unknown_labels"] == {"Brand New Label": "something"}
    assert _values(rec)["RefrigerantConnectionType"] == "Sweat"  # re-synchronised on the next label


def test_values_off_the_map_are_flagged_never_the_nearest_option() -> None:
    rec = _parse(CONDENSER.replace("Copper - 0.016 Plain", "Copper - 0.018 Plain"))
    assert rec["fields"]["TubeMaterial"]["value"] == "Copper - 0.018 Plain"
    assert "unmatched_option:TubeMaterial" in rec["flags"]


@pytest.mark.parametrize(("raw", "tag", "multi"), [
    ("CDXC-1", "CDXC-1", False), ("CDXC-1 (107A)", "CDXC-1", False), ("rhhgrh-2", "RHHGRH-2", False),
    ("CDXC-1, CDXC-2", None, True), ("HGRH-1,2 (qty2)", "HGRH-1", True), ("OAU-1_DX", None, False),
])
def test_base_tag_and_multi_tag_selections(raw, tag, multi) -> None:
    assert sr.base_tag(raw) == (tag, multi)


def test_non_report_pages_and_unsupported_types() -> None:
    assert sr.parse_report_page("COIL QUOTE\nsomething") is None
    rec = sr.parse_report_page("HEAT PUMP COIL REPORT\nCoil Tag: HP-1\n")
    assert rec is not None and rec["coil_type"] is None and rec["flags"] == ["unsupported_type:HEAT PUMP"]
    records = sr.parse_report_pages(["COIL QUOTE", CONDENSER, DX])
    assert [r["page"] for r in records] == [2, 3]


def test_every_mapped_label_targets_an_id_of_that_types_map() -> None:
    for coil_type, table in sr.LABEL_TABLE.items():
        ids = set(load_coil_data_map(coil_type).fields)
        for label, (ccsi_id, _how) in table.items():
            assert ccsi_id in ids, f"{coil_type}: {label} -> {ccsi_id} is not a map id"
    assert "Fluid Pressure Drop" in sr.KNOWN_UNMAPPED_LABELS  # a result, never MaxFluidPressureDrop


def test_the_date_parser_reads_both_locales() -> None:
    assert sr.report_date("Date:\n9/9/2026, 1:47:30 PM") == datetime(2026, 9, 9, 13, 47, 30)
    assert sr.report_date("Date:\n2026-06-05, 3:01:04 p.m.") == datetime(2026, 6, 5, 15, 1, 4)


# --- the parsed record feeds the existing cross-check unchanged ---------------------------

def test_a_parsed_report_drives_crosscheck_coil_with_reason_codes() -> None:
    rec = _parse(CONDENSER)
    sources = {
        "tag": "RHHGRC-1",
        "coil_quantity": 1,
        "finned_height": {"value": 21, "status": "review_required"},
        "tube_material": {"value": 0.016, "unit": "Copper", "status": "review_required"},
        "materials_construction.tube_surface": {"value": "Smooth", "status": "review_required"},
        "fin_material": {"value": 0.008, "unit": "Aluminum", "status": "review_required"},
        "total_air_flow_cfm": {"value": 2000, "status": "review_required"},
        "entering_dry_bulb_f": {"value": 51, "status": "review_required"},
        "refrigerant": {"value": "R-32", "status": "review_required"},
    }
    rows = {r["ccsi_id"]: r for r in crosscheck_coil(rec, sources, coil_type="HGRH")}
    for ccsi_id in ("TubeMaterial", "FinMaterial", "FinnedHeight", "TotalAirFlow", "EnteringDryBulb", "Refrigerant"):
        assert rows[ccsi_id]["verdict"] == "match", (ccsi_id, rows[ccsi_id])
    assert rows["HeaderMaterial"]["reason_code"] == "CCSI_DEFAULT_PROFILE"  # a default, not an extraction
    assert rows["CoilType"]["verdict"] == "absent_on_form"  # the report never prints it


# --- revision choice ----------------------------------------------------------------------

def _rf(rel: str, rev: int, *, sha: str = "a", date: datetime | None = datetime(2026, 9, 1), pages: int = 2,
        stem: str = "p_x") -> sr.ReportFile:
    return sr.ReportFile(rel_path=rel, rev=rev, stem=stem, sha256=sha, date=date, coil_pages=pages)


@pytest.mark.parametrize(("rel", "expected"), [
    ("Accessory Order Forms/DirectCoil/P_X_REV1_9_9_2026,__47_30_PM.pdf", (1, "p_x")),
    ("Accessory Order Forms/Direct Coil/P_X_REV2_9_9_2026,1_47_30_PM (2).pdf", (2, "p_x")),
    ("Accessory Order Forms/P_X_REV0_6_30_2026,9_23_51_AM [Kieran Selection].pdf", (0, "p_x")),
    ("Accessory Order Forms/!Obsolete/P_X_REV1_9_9_2026.pdf", "archived_subfolder"),
    ("Accessory Order Forms/DirectCoil/P_X_REV1_9_9_2026_Revised.pdf", "coilforge_output_or_copy"),
    ("Accessory Order Forms/DirectCoil/P_X_REV1_9_9_2026 Revi - Copy.pdf", "coilforge_output_or_copy"),
    ("Accessory Order Forms/DirectCoil/DC1-11111_TO_DC1-22222_REV01.pdf", (1, "dc1-11111_to_dc1-22222")),
])
def test_classify_report_path(rel, expected) -> None:
    assert sr.classify_report_path(rel) == expected


def test_highest_rev_is_the_truth_and_rev0_is_the_auxiliary_original() -> None:
    picked = sr.pick_revisions([_rf("a", 0, sha="0"), _rf("b", 1, sha="1")])
    assert picked["truth"].rel_path == "b" and picked["rev0"].rel_path == "a" and picked["kind"] == "order"
    only0 = sr.pick_revisions([_rf("a", 0)])
    assert only0["truth"].rel_path == "a" and only0["rev0"] is None and only0["kind"] == "quote_only"


def test_same_rev_exports_pick_the_latest_in_pdf_date_and_duplicates_collapse() -> None:
    early, late = datetime(2026, 9, 28, 17, 15, 33), datetime(2026, 9, 28, 17, 20, 6)
    picked = sr.pick_revisions([_rf("late", 1, sha="2", date=late), _rf("early", 1, sha="1", date=early),
                                _rf("dup", 1, sha="2", date=late)])
    assert picked["truth"].sha256 == "2" and picked["skip"] is None
    tie = sr.pick_revisions([_rf("a", 1, sha="1"), _rf("b", 1, sha="2")])
    assert tie["skip"] == "ambiguous_export" and tie["truth"] is None


def test_image_only_files_and_mixed_projects_are_skipped() -> None:
    # an image-only order document named REV01 must never outrank the text report
    picked = sr.pick_revisions([_rf("text", 1, sha="1"), _rf("image", 1, sha="2", pages=0, stem="dc1")])
    assert picked["truth"].rel_path == "text"
    assert sr.pick_revisions([_rf("img", 1, pages=0)])["skip"] == "no_text_layer"
    mixed = sr.pick_revisions([_rf("a", 1, sha="1", stem="one"), _rf("b", 1, sha="2", stem="two")])
    assert mixed["skip"] == "multiple_ccsi_projects"


def test_crosscheck_outputs_are_gitignored() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "outputs/ccsi_report_crosscheck/" in ignore and "outputs/ccsi_crosscheck/" in ignore
