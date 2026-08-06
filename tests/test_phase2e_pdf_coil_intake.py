from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from coilforge.submittal.pdf_intake import (
    _candidate_from_cover_row,
    _CoverRow,
    _cover_row_from_text_line,
    _match_detail_label,
    _cover_row_summary,
    _detail_lines_by_cover_row,
    _detail_table_field_pairs,
    _is_cover_coil_row,
    _normalize_fin_surface,
    coil_tag_rejection_reason,
    is_coil_tag,
    _OcrPageResult,
    _package_hgbp_pages,
    _TextPage,
    _extract_detail_lines_from_page,
    detect_cover_page_from_pdf_pages,
    extract_coil_candidate_from_pdf_bytes,
    extract_coil_lines_from_pdf_text,
)
from coilforge.web_app import app
from coilforge.workflows import run_pdf_to_drawing_workflow
from coilforge.workflows.submittal_to_drawing import _template_header_context_from_candidate


client = TestClient(app)


def test_pdf_intake_extracts_tag_qty_handing_and_specs() -> None:
    result = extract_coil_candidate_from_pdf_bytes(_sample_pdf_bytes())
    candidate = result.candidate

    assert result.summary.pdf_pages == 1
    assert result.summary.cover_page_detected is False
    assert result.summary.cover_page_ocr_required is True
    assert result.summary.cover_page_user_input_required is True
    assert result.summary.raw_private_data_returned is False
    assert result.summary.raw_pdf_stored is False
    assert candidate.tag is not None
    assert candidate.tag.value == "CDXC-1"
    assert candidate.quantity is not None
    assert candidate.quantity.value == 2
    assert candidate.connections["coil_hand"].value == "Left"
    assert candidate.geometry["rows_deep"].value == 5
    assert candidate.geometry["fins_per_inch"].value == 10
    assert candidate.geometry["finned_height"].value == 18
    assert candidate.geometry["finned_length"].value == 36
    assert candidate.geometry["number_of_feeds"].value == 9
    assert candidate.connections["return_connection_size"].value == 0.875
    assert candidate.connections["return_connection_size"].unit == "in"
    assert candidate.materials_construction["tube_material"].value == "Copper"
    assert candidate.refrigerant_conditions["refrigerant"].value == "R410A"
    assert candidate.drawing_parameters["CD"].value == 6.375


def test_ez_dx_model_suffix_maps_left_single_circuit_for_template_gate() -> None:
    result = extract_coil_candidate_from_pdf_bytes(
        _make_text_pdf(
            [
                "Tag: CDXC-1",
                "DX-F-S-04-13-12.00x15.00-L",
                "HF 1.50",
            ]
        )
    )
    candidate = result.candidate

    assert candidate.product_type is not None
    assert candidate.product_type.value == "DX"
    assert candidate.header_type is not None
    assert candidate.header_type.value == "Header 1"
    assert candidate.connections["coil_hand"].value == "Left"
    assert candidate.manufacturing_options["system_type"].value == "Single-Circuit"
    assert candidate.manufacturing_options["coil_model"].value == "DX-F-S-04-13-12.00x15.00-L"
    assert candidate.connections["coil_hand"].status == "review_required"
    assert candidate.manufacturing_options["system_type"].status == "review_required"


def test_pdf_intake_surfaces_project_context_without_raw_pdf_storage() -> None:
    result = extract_coil_candidate_from_pdf_bytes(
        _make_text_pdf(
            [
                "Project Number: 2755",
                "Project Name: Project Gumbo",
                "Tag CDXC-1",
                "Coil Quantity 1",
                "Handing Right",
            ]
        ),
        source_filename="9999 - Oxygen8 Submittal - Filename Project - As built.pdf",
    )

    assert result.summary.project_number == "2755"
    assert result.summary.project_name == "Project Gumbo"
    assert result.summary.project_context_source == "pdf_text_label"
    assert result.summary.raw_private_data_returned is False
    assert result.summary.raw_pdf_stored is False


def test_cover_page_table_signature_is_detected_and_preferred_for_coil_rows() -> None:
    page = _TextPage(
        page_number=2,
        text="",
        tables=(
            (
                (
                    "Qty",
                    "Tag",
                    "Item",
                    "Model",
                    "Voltage",
                    "Controls\nPreference",
                    "Installation",
                    "Duct Connection",
                    "Handing",
                ),
                ("1", "DOAS-1", "AHU", "TR_C_015", "208V/1ph/60Hz", "Constant Volume", "Horizontal", "S1", "LH"),
                ("1", "CDXC-1", "DXC Cooling", "TR_C_015", "", "", "", "", "LH"),
                ("1", "RHHGRC-1", "HGRC Reheat", "TR_C_015", "", "", "", "", "LH"),
            ),
        ),
    )

    detection = detect_cover_page_from_pdf_pages([_TextPage(page_number=1, text=""), page])
    lines = extract_coil_lines_from_pdf_text([page], cover_detection=detection)
    values = {line.source_key: line.source_value for line in lines}

    assert detection.detected is True
    assert detection.page_number == 2
    assert detection.detection_method == "pdfplumber_table_header"
    assert len(detection.rows) == 2
    assert values["COIL_TAG"] == "CDXC-1"
    assert values["COIL_QUANTITY"] == "1"
    assert values["COIL_TYPE"] == "DX COIL"
    assert values["PRODUCT_TYPE"] == "DX"
    assert values["HANDING"] == "Left"


def test_borderless_coil_table_without_header_row_is_detected_positionally() -> None:
    # Regression: some submittals render the Qty/Tag/Item/... columns as a borderless
    # table whose header band is dropped during extraction, so the table starts directly
    # at data rows. The coil (here a preheat coil listed beneath its parent ERV unit)
    # must still be detected by canonical column order; the parent unit and a valve row
    # must be excluded as non-coil rows.
    page = _TextPage(
        page_number=2,
        text="",
        tables=(
            (
                ("1", "ERV-02", "ERV", "MODEL_A", "208V/3ph/60Hz", "Constant Volume", "Horizontal", "S1", "LH"),
                ("1", "PHWC-2", "HWC Pre-Heat", "MODEL_A", "", "", "", "Coupled to ERV", "RH"),
                ("1", "PHWCV-2", "HWC Pre-Heat Valve", "2-Way", "24VAC", "Modulating", "Ship Loose", "", ""),
            ),
        ),
    )

    detection = detect_cover_page_from_pdf_pages([_TextPage(page_number=1, text=""), page])
    lines = extract_coil_lines_from_pdf_text([page], cover_detection=detection)
    values = {line.source_key: line.source_value for line in lines}

    assert detection.detected is True
    assert detection.detection_method == "pdfplumber_table_positional_no_header"
    assert [row.tag for row in detection.rows] == ["PHWC-2"]
    assert values["COIL_TAG"] == "PHWC-2"
    assert values["PRODUCT_TYPE"] == "HW"
    assert values["COIL_TYPE"] == "Hot Water Coil"
    assert values["HANDING"] == "Right"


def test_line_fallback_prioritizes_coil_component_over_parent_unit_tag() -> None:
    # Regression: with no cover table (PyPDF2 fallback / image page), the generic Qty/Tag
    # row rule captures the parent unit (ERV/AHU) first. A coil component on a later line
    # must override that unit tag so the actual coil is selected, not the air handler.
    page = _TextPage(
        page_number=1,
        text="\n".join(
            [
                "1 ERV-02 ERV MODEL_A 208V/3ph/60Hz Constant Volume Horizontal S1 LH",
                "1 PHWC-2 HWC Pre-Heat MODEL_A Coupled to ERV RH",
            ]
        ),
    )

    detection = detect_cover_page_from_pdf_pages([page])
    lines = extract_coil_lines_from_pdf_text([page], cover_detection=detection)
    values = {line.source_key: line.source_value for line in lines}

    assert detection.detected is False
    assert values["COIL_TAG"] == "PHWC-2"
    assert values["COIL_QUANTITY"] == "1"


def test_cover_page_rows_generate_separate_pdf_coil_candidates() -> None:
    result = extract_coil_candidate_from_pdf_bytes(_cover_page_pdf_bytes())

    assert result.summary.cover_page_detected is True
    assert result.summary.cover_page_row_count == 2
    assert [row.tag for row in result.summary.cover_page_rows] == ["CDXC-1", "RHHGRC-1"]
    assert [candidate.tag.value for candidate in result.cover_candidates if candidate.tag] == [
        "CDXC-1",
        "RHHGRC-1",
    ]


def test_cover_page_detects_rhhgrh_reheat_tag_spelling() -> None:
    # Regression for the 2766 Olympic-Broadway submittal: the two reheat coils are tagged
    # RHHGRH-1/-2 (trailing ...RH), not the RHHGRC spelling the table previously knew, so
    # they were silently dropped while CDXC-1/-2 were detected. RHHGRH is the same HGRH
    # category as RHHGRC (John-confirmed 2026-06-26).
    pdf = _make_text_pdf(
        [
            "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
            "1 CDXC-1 DXC Cooling TR_C_015 LH",
            "1 RHHGRH-1 Hot Gas Reheat TR_C_015 LH",
            "1 CDXC-2 DXC Cooling TR_C_016 LH",
            "1 RHHGRH-2 Hot Gas Reheat TR_C_016 LH",
        ]
    )
    result = extract_coil_candidate_from_pdf_bytes(pdf)

    assert [row.tag for row in result.summary.cover_page_rows] == [
        "CDXC-1",
        "RHHGRH-1",
        "CDXC-2",
        "RHHGRH-2",
    ]
    # The RHHGRH rows classify into the existing HGRH path (same as RHHGRC).
    rhhgrh = [row for row in result.summary.cover_page_rows if row.tag.startswith("RHHGRH-")]
    assert [row.product_type for row in rhhgrh] == ["HGRC", "HGRC"]
    assert [row.coil_format for row in rhhgrh] == ["condensing", "condensing"]
    assert [c.coil_type.value for c in result.cover_candidates if c.coil_type] == [
        "DX COIL",
        "HGRH COIL",
        "DX COIL",
        "HGRH COIL",
    ]


def test_cover_page_detects_bare_hgrh_alias() -> None:
    # The bare HGRH-N alias (mirroring how HGRC aliases RHHGRC) also classifies as HGRH.
    pdf = _make_text_pdf(
        [
            "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
            "1 CDXC-1 DXC Cooling TR_C_015 LH",
            "1 HGRH-1 Hot Gas Reheat TR_C_015 LH",
        ]
    )
    result = extract_coil_candidate_from_pdf_bytes(pdf)

    assert [row.tag for row in result.summary.cover_page_rows] == ["CDXC-1", "HGRH-1"]
    assert [c.coil_type.value for c in result.cover_candidates if c.coil_type] == [
        "DX COIL",
        "HGRH COIL",
    ]


def test_cover_page_rows_classify_four_direct_coil_formats() -> None:
    result = extract_coil_candidate_from_pdf_bytes(_four_format_cover_page_pdf_bytes())

    assert [row.tag for row in result.summary.cover_page_rows] == [
        "CDXC-1",
        "RHHGRC-1",
        "CCWC-1",
        "PHWC-1",
        "HHWC-1",
    ]
    assert [row.product_type for row in result.summary.cover_page_rows] == [
        "DX",
        "HGRC",
        "CHW",
        "HW",
        "HW",
    ]
    assert [row.coil_format for row in result.summary.cover_page_rows] == [
        "dx",
        "condensing",
        "cooling_chilled_water",
        "preheat_hot_water",
        "heating_hot_water",
    ]
    assert [candidate.tag.value for candidate in result.cover_candidates if candidate.tag] == [
        "CDXC-1",
        "RHHGRC-1",
        "CCWC-1",
        "PHWC-1",
        "HHWC-1",
    ]
    assert [candidate.coil_type.value for candidate in result.cover_candidates if candidate.coil_type] == [
        "DX COIL",
        "HGRH COIL",
        "Chilled Water Coil",
        "Hot Water Coil",
        "Hot Water Coil",
    ]


def test_cover_page_detection_handles_spaced_tags_and_continuation_pages() -> None:
    first_page = _TextPage(
        page_number=1,
        text="\n".join(
            [
                "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
                "1 CDXC- 1 DXC Cooling A16_V_I_ERV LH",
                "1 RHHGRC-1 HGRC Reheat A16_V_I_ERV LH",
            ]
        ),
    )
    continuation_page = _TextPage(
        page_number=2,
        text="\n".join(
            [
                "1 CDXC-2 DXC Cooling TR_C_018 LH",
                "1 RHHGRC-2 HGRC Reheat TR_C_018 LH",
                "Qty 1: OA Sensor - not a coil row",
            ]
        ),
    )
    detail_page = _TextPage(page_number=3, text="Cooling DX\nFin Height (in): 12")

    detection = detect_cover_page_from_pdf_pages([first_page, continuation_page, detail_page])

    assert detection.detected is True
    assert detection.page_number == 1
    assert [row.tag for row in detection.rows] == [
        "CDXC-1",
        "RHHGRC-1",
        "CDXC-2",
        "RHHGRC-2",
    ]
    assert [row.handing for row in detection.rows] == ["LH", "LH", "LH", "LH"]


def test_cover_page_ordered_detail_blocks_are_merged_into_matching_coil_candidates() -> None:
    workflow = run_pdf_to_drawing_workflow(_cover_page_with_ordered_detail_blocks_pdf_bytes())
    pages = workflow["pdf_coil_pages"]

    cdx_fields = pages[0]["workflow"]["direct_coil_input_draft"]["fields"]
    hgrh_fields = pages[1]["workflow"]["direct_coil_input_draft"]["fields"]

    assert [page["tag"] for page in pages] == ["CDXC-1", "RHHGRC-1"]
    assert pages[0]["workflow"]["candidates"][0]["coil_type"]["value"] == "DX COIL"
    assert pages[1]["workflow"]["candidates"][0]["coil_type"]["value"] == "HGRH COIL"
    assert cdx_fields["rows_deep"]["value"] == 5
    assert cdx_fields["fins_per_inch"]["value"] == 10
    assert cdx_fields["finned_height"]["value"] == 18
    assert cdx_fields["finned_length"]["value"] == 36
    assert hgrh_fields["rows_deep"]["value"] == 1
    assert hgrh_fields["fins_per_inch"]["value"] == 12
    assert hgrh_fields["finned_height"]["value"] == 9
    assert hgrh_fields["finned_length"]["value"] == 36


def test_oxygen8_cooling_dx_and_hgrh_sections_extract_detail_fields_until_stop_headers() -> None:
    workflow = run_pdf_to_drawing_workflow(_oxygen8_cooling_dx_and_hgrh_pdf_bytes())
    pages = workflow["pdf_coil_pages"]
    cdx_candidate = pages[0]["workflow"]["candidates"][0]
    hgrh_candidate = pages[1]["workflow"]["candidates"][0]
    cdx_fields = pages[0]["workflow"]["direct_coil_input_draft"]["fields"]
    hgrh_fields = pages[1]["workflow"]["direct_coil_input_draft"]["fields"]

    assert [page["tag"] for page in pages] == ["CDXC-1", "RHHGRC-1"]
    assert cdx_candidate["airside_conditions"]["altitude_ft"]["value"] == 0
    assert cdx_candidate["airside_conditions"]["total_air_flow_cfm"]["value"] == 3735
    assert cdx_candidate["airside_conditions"]["entering_dry_bulb_f"]["value"] == 95
    assert cdx_candidate["airside_conditions"]["entering_wet_bulb_f"]["value"] == 78
    assert cdx_candidate["geometry"]["rows_deep"]["value"] == 6
    assert cdx_candidate["geometry"]["number_of_feeds"]["value"] == 18
    assert cdx_candidate["geometry"]["face_area_sqft"]["value"] == 8
    assert cdx_candidate["connections"]["return_connection_size"]["value"] == 1.125
    assert cdx_candidate["connections"]["qty_connections_per_header"]["value"] == 4
    assert cdx_candidate["materials_construction"]["tube_surface"]["value"] == "Smooth"
    assert cdx_candidate["manufacturing_options"]["coil_model"]["value"] == "3DX-06.24. 0-11.48.0-18"
    assert cdx_candidate["manufacturing_options"]["vrv_kit_model"]["value"] == "EKEXVA72U"
    assert cdx_candidate["refrigerant_conditions"]["refrigerant"]["value"] == "R-32"
    assert cdx_candidate["refrigerant_conditions"]["evaporating_temp_f"]["value"] == 43
    assert cdx_candidate["refrigerant_conditions"]["liquid_temp_f"]["value"] == 77
    assert cdx_candidate["refrigerant_conditions"]["superheat_f"]["value"] == 9
    assert cdx_candidate["performance"]["nominal_cooling_capacity_mbh"]["value"] == 388.51
    assert cdx_candidate["performance"]["total_capacity_mbh"]["value"] == 329.48
    assert cdx_candidate["performance"]["sensible_capacity_mbh"]["value"] == 168.26
    assert cdx_candidate["performance"]["air_pressure_drop_iwg"]["value"] == 0.38
    assert cdx_candidate["performance"]["internal_volume_cuin"]["value"] == 741.87
    assert cdx_candidate["performance"]["refrigerant_pressure_drop_psi"]["value"] == 7.39
    assert cdx_fields["altitude_ft"]["value"] == 0
    assert cdx_fields["face_velocity_fpm"]["value"] == 466.88
    assert cdx_fields["rows_deep"]["value"] == 6

    assert hgrh_candidate["geometry"]["rows_deep"]["value"] == 1
    assert hgrh_candidate["geometry"]["number_of_feeds"]["value"] == 3
    assert hgrh_candidate["refrigerant_conditions"]["condensing_temp_f"]["value"] == 115
    assert hgrh_candidate["refrigerant_conditions"]["subcooling_f"]["value"] == 18
    assert hgrh_candidate["performance"]["total_capacity_mbh"]["value"] == 60.85
    assert hgrh_candidate["performance"]["air_pressure_drop_iwg"]["value"] == 0.03
    assert hgrh_fields["rows_deep"]["value"] == 1
    assert hgrh_fields["face_velocity_fpm"]["value"] == 466.88


def test_each_cover_coil_links_to_its_drawing_template_from_classification() -> None:
    """Regression for the real Oxygen8 submittal: every cover coil gets its OWN
    template_drawing, linked from the candidate's coil type / hand / header qty
    (not the as-built model-number parse, which a submittal does not satisfy)."""
    workflow = run_pdf_to_drawing_workflow(_oxygen8_cooling_dx_and_hgrh_pdf_bytes())
    pages = workflow["pdf_coil_pages"]

    dx = pages[0]["workflow"]["template_drawing"]
    hgrh = pages[1]["workflow"]["template_drawing"]

    assert dx["template_found"] is True
    # The DX coil's Coil Style is "Interlaced 4 Circuits", so the circuit count is
    # derived (was silently defaulting to 1) and selects the 4-circuit template.
    assert dx["extracted"]["circuits"] == 4
    assert dx["template_id"] == "coilmaster_dx_lh_header4"
    assert dx["extracted"]["coil_category"] == "DX"
    assert dx["extracted"]["tag"] == "CDXC-1"

    assert hgrh["template_found"] is True
    assert hgrh["template_id"] == "coilmaster_hgrh_lh_header1"
    assert hgrh["extracted"]["coil_category"] == "HGRH"
    assert hgrh["extracted"]["tag"] == "RHHGRC-1"

    # The selected (top-level) template_drawing matches the selected coil page,
    # and stays review-aid only.
    assert workflow["template_drawing"]["export_allowed"] is False


def test_combined_detail_header_extracts_entering_values_without_max_db_overwrite() -> None:
    workflow = run_pdf_to_drawing_workflow(_oxygen8_combined_detail_header_pdf_bytes())
    candidate = workflow["pdf_coil_pages"][0]["workflow"]["candidates"][0]

    assert candidate["airside_conditions"]["total_air_flow_cfm"]["value"] == 2750
    assert candidate["airside_conditions"]["entering_dry_bulb_f"]["value"] == 95
    assert candidate["airside_conditions"]["entering_wet_bulb_f"]["value"] == 78
    assert candidate["refrigerant_conditions"]["evaporating_temp_f"]["value"] == 43
    assert candidate["refrigerant_conditions"]["liquid_temp_f"]["value"] == 77
    assert candidate["refrigerant_conditions"]["superheat_f"]["value"] == 9
    # "Max Coil Performance" DB/WB is the coil's LEAVING air (John 2026-07-22): it maps to
    # airside leaving_dry/wet_bulb_f, not the vestigial performance.max_*_bulb_f.
    assert candidate["airside_conditions"]["leaving_dry_bulb_f"]["value"] == 49.73
    assert candidate["airside_conditions"]["leaving_wet_bulb_f"]["value"] == 49.52
    assert candidate["airside_conditions"]["entering_dry_bulb_f"]["value"] != candidate["airside_conditions"]["leaving_dry_bulb_f"]["value"]


def test_attached_oxygen8_pdf_text_spacing_extracts_entering_and_refrigerant_values() -> None:
    workflow = run_pdf_to_drawing_workflow(_oxygen8_attached_pdf_text_spacing_bytes())
    candidate = workflow["pdf_coil_pages"][0]["workflow"]["candidates"][0]

    assert candidate["airside_conditions"]["total_air_flow_cfm"]["value"] == 850
    assert candidate["airside_conditions"]["entering_dry_bulb_f"]["value"] == 86.1
    assert candidate["airside_conditions"]["entering_wet_bulb_f"]["value"] == 85.9
    assert candidate["refrigerant_conditions"]["evaporating_temp_f"]["value"] == 43
    assert candidate["refrigerant_conditions"]["liquid_temp_f"]["value"] == 77
    assert candidate["refrigerant_conditions"]["superheat_f"]["value"] == 9
    # "Max Coil Performance" DB/WB is the coil's LEAVING air (John 2026-07-22).
    assert candidate["airside_conditions"]["leaving_dry_bulb_f"]["value"] == 49.77
    assert candidate["airside_conditions"]["leaving_wet_bulb_f"]["value"] == 49.67
    assert candidate["airside_conditions"]["entering_dry_bulb_f"]["value"] != candidate["airside_conditions"]["leaving_dry_bulb_f"]["value"]


def test_hgrh_reheat_coil_extracts_leaving_dry_bulb_from_max_performance() -> None:
    """The RHHGRC (HGRH reheat) coil's "Max Coil Performance" DB is its LEAVING dry
    bulb — coil-agnostic, same rule as the DX path (John 2026-07-23). A reheat coil
    is sensible-only, so its Max Coil Performance block reports DB with NO WB; the
    leaving wet bulb stays honestly absent (None), never invented."""
    workflow = run_pdf_to_drawing_workflow(_oxygen8_cooling_dx_and_hgrh_pdf_bytes())
    pages = workflow["pdf_coil_pages"]

    hgrh = pages[1]["workflow"]["candidates"][0]
    assert pages[1]["tag"] == "RHHGRC-1"
    air = hgrh["airside_conditions"]
    # Max Coil Performance "DB (F): 71.29" surfaces as leaving air, distinct from the
    # entering DB (55), proving it is not mistaken for the entering condition.
    assert air["leaving_dry_bulb_f"]["value"] == 71.29
    assert air["entering_dry_bulb_f"]["value"] == 55
    assert air["leaving_dry_bulb_f"]["value"] != air["entering_dry_bulb_f"]["value"]
    # Reheat coil has no leaving WB in the source -> absent, not guessed.
    assert air.get("leaving_wet_bulb_f") is None


# The Oxygen8 detail grid stacks "Coil Operating Setpoint" ABOVE "Max Coil Performance"
# in the SAME column. Transcribed from the real 2949 Ferguson Theatre submittal p9
# ("Heating HWC"); the DX page p8 has the identical shape. Reading one context per column
# matched every max-performance row against the operating-setpoint label map, so the whole
# block was dropped. On DX the text-line parser rescued it (those rows sit on otherwise
# empty lines); on a water coil the denser "Coil" column collides with them, so nothing did.
_STACKED_SECTION_TABLE: tuple[tuple[str, ...], ...] = (
    ("Heating HWC", "", "", "", "", "", "", "", ""),
    ("", "", "", "", "", "", "", "", ""),
    ("Coil", "", "", "", "Entering", "", "", "Coil Operating Setpoint", ""),
    ("Model:", "5W-01-36.0-12-33.0-2", "", "", "Airflow (CFM):", "3500", "", "DB (F):", "95"),
    ("", "", "", "", "DB (F):", "58.2", "", "", ""),
    ("Fin Surface:", "Corrugated", "", "", "Fluid Type:", "Water", "", "Max Coil Performance", ""),
    ("Fin Height (in):", "36", "", "", "", "", "", "Airflow (CFM):", "3500"),
    ("Fin Length (in):", "33", "", "", "Fluid Ent Temp (F):", "160", "", "Capacity (MBH):", "142.31"),
    ("Face Area (sq.ft):", "8.2", "", "", "Fluid Lvg Temp (F):", "130", "", "DB (F):", "95"),
    ("FPI:", "12", "", "", "", "", "", "Air Vel (FPM):", "424"),
    ("Rows:", "1", "", "", "", "", "", "Air PD (inWG):", "0.07"),
    ("Circuits:", "2", "", "", "", "", "", "Fluid Flow Rate (GPM):", "9.69"),
    ("Coil Weight (lbs):", "57.79", "", "", "", "", "", "Fluid PD (ftWG):", "8.79"),
    ("Inlet Conn. Size (in):", "1", "", "", "", "", "", "Fluid Vel (fps):", "5.34"),
)


def test_stacked_sections_in_one_column_read_against_their_own_labels() -> None:
    """A column holding two sections stacked vertically must switch label maps at the
    second section header — otherwise the lower block is matched against the upper
    block's labels and vanishes (John 2026-07-28, 2949 Ferguson Theatre HWC)."""
    pairs = {key: value for key, value, _row, _col in _detail_table_field_pairs(_STACKED_SECTION_TABLE)}

    # The whole "Max Coil Performance" block now resolves.
    assert pairs["TOTAL_CAPACITY_MBH"] == "142.31"
    assert pairs["FACE_VELOCITY_FPM"] == "424"
    assert pairs["AIR_PRESSURE_DROP_IWG"] == "0.07"
    assert pairs["FLUID_FLOW_RATE_GPM"] == "9.69"
    assert pairs["FLUID_PRESSURE_DROP_FTWG"] == "8.79"
    assert pairs["FLUID_VELOCITY_FPS"] == "5.34"
    # The neighbouring columns are unaffected.
    assert pairs["FINNED_HEIGHT"] == "36"
    assert pairs["INLET_CONNECTION_SIZE"] == "1"
    assert pairs["FLUID_ENTERING_TEMP_F"] == "160"


def test_same_label_resolves_per_section_not_per_column() -> None:
    """"DB (F):" appears in BOTH stacked sections of the same column. Under the operating
    setpoint it is the setpoint; under Max Coil Performance it is the LEAVING dry bulb.
    This pair is the whole reason the context must be row-aware rather than column-aware."""
    by_key: dict[str, list[int]] = {}
    for key, _value, row, _col in _detail_table_field_pairs(_STACKED_SECTION_TABLE):
        by_key.setdefault(key, []).append(row)

    assert by_key["OPERATING_SETPOINT_DB_F"] == [3]   # under "Coil Operating Setpoint"
    assert by_key["LEAVING_DRY_BULB_F"] == [8]        # under "Max Coil Performance"


def test_single_section_per_column_table_is_unchanged() -> None:
    """Behaviour preservation: a table whose columns each carry exactly one section
    reads exactly as before, including rows ABOVE the section-header row."""
    table = (
        ("Cooling DX", "", "", ""),
        ("Coil", "", "Entering", ""),
        ("Fin Height (in):", "36", "Airflow (CFM):", "3500"),
        ("Rows:", "3", "DB (F):", "77.41"),
    )
    pairs = {key: value for key, value, _row, _col in _detail_table_field_pairs(table)}
    assert pairs == {
        "FINNED_HEIGHT": "36",
        "ROWS_DEEP": "3",
        "TOTAL_AIR_FLOW_CFM": "3500",
        "ENTERING_DRY_BULB_F": "77.41",
    }


def test_chilled_water_extracts_leaving_wet_bulb_but_hot_water_has_none() -> None:
    """Leaving WB is physics-gated by coil type (John 2026-07-24): chilled water
    dehumidifies so its "Max Coil Performance" reports both DB and WB, but hot water
    is sensible-only (DB only). The extraction is coil-agnostic; the water mirror
    surfaces the leaving WB row for chilled water only, matching this asymmetry."""
    workflow = run_pdf_to_drawing_workflow(_cwc_and_hwc_sections_pdf_bytes())
    pages = workflow["pdf_coil_pages"]

    cwc = pages[0]["workflow"]["candidates"][0]["airside_conditions"]
    assert pages[0]["tag"] == "CCWC-1"
    assert cwc["leaving_dry_bulb_f"]["value"] == 64.1
    assert cwc["leaving_wet_bulb_f"]["value"] == 62.9

    hwc = pages[1]["workflow"]["candidates"][0]["airside_conditions"]
    assert pages[1]["tag"] == "HHWC-1"
    assert hwc["leaving_dry_bulb_f"]["value"] == 85.8
    # Hot water is sensible-only -> no leaving WB in the source, not invented.
    assert hwc.get("leaving_wet_bulb_f") is None


def test_cwc_and_hwc_cover_rows_match_cooling_cwc_and_heating_hwc_sections() -> None:
    workflow = run_pdf_to_drawing_workflow(_cwc_and_hwc_sections_pdf_bytes())
    pages = workflow["pdf_coil_pages"]
    cwc_candidate = pages[0]["workflow"]["candidates"][0]
    hwc_candidate = pages[1]["workflow"]["candidates"][0]

    assert [page["tag"] for page in pages] == ["CCWC-1", "HHWC-1"]
    assert [page["coil_format"] for page in pages] == [
        "cooling_chilled_water",
        "heating_hot_water",
    ]
    assert cwc_candidate["geometry"]["finned_height"]["value"] == 16.5
    assert cwc_candidate["geometry"]["rows_deep"]["value"] == 4
    assert cwc_candidate["geometry"]["circuits"]["value"] == 3
    assert cwc_candidate["connections"]["inlet_connection_size"]["value"] == 0.875
    assert cwc_candidate["connections"]["outlet_connection_size"]["value"] == 0.875
    assert cwc_candidate["airside_conditions"]["fluid_type"]["value"] == "Propylene Glycol"
    assert cwc_candidate["airside_conditions"]["fluid_entering_temp_f"]["value"] == 45
    assert cwc_candidate["airside_conditions"]["fluid_leaving_temp_f"]["value"] == 57
    assert cwc_candidate["performance"]["total_capacity_mbh"]["value"] == 50.7
    assert cwc_candidate["connections"]["valve_size"]["value"] == 0.75

    assert hwc_candidate["geometry"]["finned_height"]["value"] == 18
    assert hwc_candidate["geometry"]["rows_deep"]["value"] == 2
    assert hwc_candidate["airside_conditions"]["fluid_type"]["value"] == "Water"
    assert hwc_candidate["airside_conditions"]["fluid_entering_temp_f"]["value"] == 140
    assert hwc_candidate["airside_conditions"]["fluid_leaving_temp_f"]["value"] == 110
    assert hwc_candidate["performance"]["total_capacity_mbh"]["value"] == 41.9
    assert hwc_candidate["connections"]["valve_size"]["value"] == 0.5


def test_repeated_phwc_and_hhwc_rows_consume_next_matching_hwc_sections_in_order() -> None:
    workflow = run_pdf_to_drawing_workflow(_repeated_preheat_and_heating_hwc_pdf_bytes())
    pages = workflow["pdf_coil_pages"]
    candidates = [page["workflow"]["candidates"][0] for page in pages]

    assert [page["tag"] for page in pages] == ["PHWC-1", "HHWC-1", "PHWC-2", "HHWC-2"]
    assert [page["quantity"] for page in pages] == [1, 1, 2, 2]
    assert [page["coil_format"] for page in pages] == [
        "preheat_hot_water",
        "heating_hot_water",
        "preheat_hot_water",
        "heating_hot_water",
    ]
    assert [candidate["geometry"]["finned_height"]["value"] for candidate in candidates] == [
        10.5,
        10.5,
        12.5,
        13.5,
    ]
    assert [candidate["geometry"]["rows_deep"]["value"] for candidate in candidates] == [2, 3, 4, 5]
    assert [candidate["performance"]["total_capacity_mbh"]["value"] for candidate in candidates] == [
        23,
        13.1,
        31,
        21,
    ]


def test_cover_page_multi_tag_row_splits_only_when_qty_matches_tag_count() -> None:
    page = _TextPage(
        page_number=1,
        text="",
        tables=(
            (
                (
                    "Qty",
                    "Tag",
                    "Item",
                    "Model",
                    "Voltage",
                    "Controls Preference",
                    "Installation",
                    "Duct Connection",
                    "Handing",
                ),
                ("2", "CDXC-1, CDXC-2", "DXC Cooling", "TR_C_015", "", "", "", "", "RH"),
            ),
        ),
    )

    detection = detect_cover_page_from_pdf_pages([page])

    assert detection.detected is True
    assert [row.tag for row in detection.rows] == ["CDXC-1", "CDXC-2"]
    assert [row.qty for row in detection.rows] == [1, 1]


def test_cover_page_not_detected_requests_user_page_input_for_ocr_path() -> None:
    detection = detect_cover_page_from_pdf_pages([_TextPage(page_number=1, text="")])

    assert detection.detected is False
    assert detection.ocr_required is True
    assert detection.user_page_input_required is True
    assert "request user page input" in detection.review_note


def test_cover_page_manual_hint_marks_page_for_ocr_capture() -> None:
    detection = detect_cover_page_from_pdf_pages(
        [_TextPage(page_number=1, text="")],
        cover_page_hint=3,
    )

    assert detection.detected is False
    assert detection.page_number == 3
    assert detection.detection_method == "manual_page_input_ocr_required"
    assert detection.ocr_required is True
    assert detection.user_page_input_required is False


def test_pdf_workflow_prepopulates_direct_coil_draft_and_paste_surface() -> None:
    workflow = run_pdf_to_drawing_workflow(_sample_pdf_bytes(), source_filename="sample.pdf")
    draft = workflow["direct_coil_input_draft"]
    draft_fields = draft["fields"]
    paste_rows = {
        row["direct_coil_label"]: row for row in workflow["direct_coil_paste_ready"]["fields"]
    }

    assert workflow["pdf_intake_summary"]["source_filename"] == "sample.pdf"
    assert workflow["pdf_intake_summary"]["project_number"] is None
    assert workflow["pdf_intake_summary"]["project_name"] is None
    assert workflow["pdf_intake_summary"]["raw_pdf_stored"] is False
    assert workflow["validation"]["raw_private_data_returned"] is False
    assert workflow["validation"]["export_status"] == "not_implemented"
    assert workflow["validation"]["export_allowed"] is False
    assert draft["coil_quantity"]["value"] == 2
    assert draft_fields["coil_hand"]["value"] == "Left"
    assert draft_fields["rows_deep"]["value"] == 5
    assert draft_fields["finned_height"]["value"] == 18
    assert draft_fields["finned_length"]["value"] == 36
    assert draft_fields["fins_per_inch"]["value"] == 10
    assert draft_fields["number_of_feeds"]["value"] == 9
    assert draft_fields["return_connection_size"]["value"] == 0.875
    assert paste_rows["Coil Quantity"]["display_value"] == "2"
    assert paste_rows["Finned Height(In)"]["display_value"] == "18"
    assert paste_rows["Finned Length(In)"]["display_value"] == "36"
    assert paste_rows["Rows Deep"]["display_value"] == "5"
    assert paste_rows["Fins Per Inch"]["display_value"] == "10"
    assert paste_rows["Number Of Feeds(Total)"]["display_value"] == "9"
    assert paste_rows["Coil Hand"]["display_value"] == "Left"
    assert paste_rows["CD"]["display_value"] == "6.375"


def test_pdf_workflow_uses_filename_project_context_fallback() -> None:
    workflow = run_pdf_to_drawing_workflow(
        _sample_pdf_bytes(),
        source_filename="2755 - Oxygen8 Submittal - Daikin Applied Atlanta - Project Gumbo - As built.pdf",
    )

    assert workflow["pdf_intake_summary"]["project_number"] == "2755"
    assert workflow["pdf_intake_summary"]["project_name"] == "Project Gumbo"
    assert workflow["pdf_intake_summary"]["project_context_source"] == "source_filename"


def test_pdf_to_drawing_api_accepts_pdf_bytes_without_enabling_export() -> None:
    response = client.post(
        "/api/workflow/pdf-to-drawing",
        content=_sample_pdf_bytes(),
        headers={
            "content-type": "application/pdf",
            "x-coilforge-filename": "sample.pdf",
            "x-coilforge-source-id": "PDF-TEST-001",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pdf_intake_summary"]["source_id"] == "PDF-TEST-001"
    assert payload["selected_candidate_summary"]["tag"] == "CDXC-1"
    assert payload["selected_candidate_summary"]["quantity"] == 2
    assert payload["direct_coil_input_draft"]["coil_quantity"]["value"] == 2
    assert payload["direct_coil_input_draft"]["fields"]["coil_hand"]["value"] == "Left"
    assert payload["validation"]["export_allowed"] is False
    assert payload["validation"]["raw_pdf_stored"] is False
    assert payload["validation"]["drawing_approval_claimed"] is False


def test_pdf_to_drawing_api_accepts_cover_page_hint_for_ocr_fallback() -> None:
    response = client.post(
        "/api/workflow/pdf-to-drawing",
        content=_sample_pdf_bytes(),
        headers={
            "content-type": "application/pdf",
            "x-coilforge-cover-page": "3",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pdf_intake_summary"]["cover_page_detected"] is False
    assert payload["pdf_intake_summary"]["cover_page_number"] == 3
    assert payload["pdf_intake_summary"]["cover_page_detection_method"] == "manual_page_input_ocr_required"
    assert payload["pdf_intake_summary"]["cover_page_ocr_required"] is True
    assert payload["pdf_intake_summary"]["cover_page_user_input_required"] is False


def test_pdf_intake_uses_llm_ocr_when_manual_cover_page_hint_is_supplied(monkeypatch) -> None:
    def fake_ocr(pdf_bytes: bytes, page_number: int) -> _OcrPageResult:
        assert pdf_bytes.startswith(b"%PDF")
        assert page_number == 1
        return _OcrPageResult(
            page_number=1,
            text="\n".join(
                [
                    "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
                    "1 CDXC-9 DXC Cooling TR_C_015 208V Constant Volume Horizontal S1 RH",
                    "Rows Deep 6",
                    "Finned Height 24 in",
                    "Finned Length 48 in",
                    "Total Air Flow 3100 cfm",
                ]
            ),
            model="gpt-test",
            status="completed",
        )

    monkeypatch.setattr(
        "coilforge.submittal.pdf_intake._extract_page_text_with_llm_ocr",
        fake_ocr,
    )

    result = extract_coil_candidate_from_pdf_bytes(
        _make_text_pdf(["image-only placeholder"]),
        cover_page_hint=1,
    )

    assert result.summary.extraction_engine.endswith("+llm_ocr")
    assert result.summary.ocr_enabled is True
    assert result.summary.ocr_attempted is True
    assert result.summary.ocr_status == "completed"
    assert result.summary.ocr_model == "gpt-test"
    assert result.summary.ocr_page_number == 1
    assert result.summary.cover_page_detected is True
    assert result.summary.cover_page_detection_method == "text_header_signature"
    assert result.summary.cover_page_ocr_required is False
    assert result.summary.cover_page_row_count == 1
    assert result.candidate.tag is not None
    assert result.candidate.tag.value == "CDXC-9"
    assert result.candidate.connections["coil_hand"].value == "Right"
    assert result.candidate.geometry["rows_deep"].value == 6


def test_pdf_intake_reports_missing_openai_key_without_returning_raw_pdf_text(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("coilforge.submittal.pdf_intake._load_dotenv_if_available", lambda: None)

    result = extract_coil_candidate_from_pdf_bytes(
        _make_text_pdf(["image-only placeholder"]),
        cover_page_hint=1,
    )

    assert result.summary.ocr_enabled is False
    assert result.summary.ocr_attempted is True
    assert result.summary.ocr_status == "skipped_missing_openai_api_key"
    assert result.summary.ocr_error == "OPENAI_API_KEY was not found in environment or .env."
    assert result.summary.raw_private_data_returned is False
    assert result.summary.raw_pdf_stored is False


def test_pdf_to_drawing_api_returns_one_review_page_per_cover_coil_row() -> None:
    response = client.post(
        "/api/workflow/pdf-to-drawing",
        content=_cover_page_pdf_bytes(),
        headers={
            "content-type": "application/pdf",
            "x-coilforge-filename": "cover-page.pdf",
            "x-coilforge-source-id": "PDF-COVER-001",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    pages = payload["pdf_coil_pages"]

    assert payload["selected_candidate_summary"]["tag"] == "CDXC-1"
    assert payload["pdf_intake_summary"]["cover_page_row_count"] == 2
    assert [page["tag"] for page in pages] == ["CDXC-1", "RHHGRC-1"]
    assert [page["quantity"] for page in pages] == [1, 1]
    assert pages[0]["workflow"]["selected_candidate_summary"]["tag"] == "CDXC-1"
    assert pages[1]["workflow"]["selected_candidate_summary"]["tag"] == "RHHGRC-1"
    assert pages[0]["workflow"]["validation"]["export_allowed"] is False
    assert pages[1]["workflow"]["validation"]["export_allowed"] is False


def test_pdf_to_drawing_api_returns_four_format_review_pages() -> None:
    response = client.post(
        "/api/workflow/pdf-to-drawing",
        content=_four_format_cover_page_pdf_bytes(),
        headers={
            "content-type": "application/pdf",
            "x-coilforge-filename": "four-formats.pdf",
            "x-coilforge-source-id": "PDF-FOUR-FORMATS-001",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    pages = payload["pdf_coil_pages"]

    assert [page["tag"] for page in pages] == ["CDXC-1", "RHHGRC-1", "CCWC-1", "PHWC-1", "HHWC-1"]
    assert [page["product_type"] for page in pages] == ["DX", "HGRC", "CHW", "HW", "HW"]
    assert [page["coil_format"] for page in pages] == [
        "dx",
        "condensing",
        "cooling_chilled_water",
        "preheat_hot_water",
        "heating_hot_water",
    ]
    assert [page["workflow"]["selected_candidate_summary"]["tag"] for page in pages] == [
        "CDXC-1",
        "RHHGRC-1",
        "CCWC-1",
        "PHWC-1",
        "HHWC-1",
    ]
    assert all(page["workflow"]["validation"]["export_allowed"] is False for page in pages)


def test_pdf_to_drawing_api_rejects_invalid_pdf_bytes() -> None:
    response = client.post(
        "/api/workflow/pdf-to-drawing",
        content=b"not a pdf",
        headers={"content-type": "application/pdf"},
    )

    assert response.status_code == 400
    assert "Unable to extract text from PDF bytes" in response.json()["detail"]


def test_coil_drawing_product_options_endpoint() -> None:
    response = client.get("/api/coil-drawing/product-options")
    assert response.status_code == 200
    lines = response.json()["product_lines"]
    assert set(lines) == {"NOVA", "TERRA H", "TERRA V", "VENTUM_H", "VENTUM_PLUS"}
    assert "A16" in lines["NOVA"]


def test_coil_drawing_derive_endpoint_runs_engine_with_chosen_product_size() -> None:
    response = client.post(
        "/api/coil-drawing/derive",
        json={
            "coil_category": "DX", "coil_hand": "RH", "circuits": 1, "tag": "CDXC-1",
            "rows": 6, "feeds": 4, "finned_height": 12, "finned_length": 22,
            "product_type": "NOVA", "unit_size": "A16",
        },
    )
    assert response.status_code == 200
    td = response.json()
    assert td["template_id"] == "coilmaster_dx_rh_header1"
    assert td["header_engine_used"] is True
    assert td["drawing_value_source"] == "logic_derived"
    assert td["slot_values"]["slot.TF"] == 0.625
    assert td["export_allowed"] is False


def test_web_shell_wires_pdf_upload_to_pdf_workflow_endpoint() -> None:
    index = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(
        encoding="utf-8"
    )
    app_js = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(
        encoding="utf-8"
    )
    style = (Path(__file__).resolve().parents[1] / "web" / "style.css").read_text(
        encoding="utf-8"
    )

    assert 'id="pdf-intake-file"' in index
    assert 'id="pdf-drop-zone"' in index
    assert 'id="pdf-file-name"' in index
    assert 'id="pdf-cover-page-input"' in index
    assert 'id="project-tree"' in index
    assert 'id="analyze-pdf"' in index
    assert 'id="calculate-button"' not in index
    assert 'id="export-button"' not in index
    assert 'id="save-draft"' not in index
    assert 'id="apply-draft"' not in index
    assert 'id="update-drawing"' not in index
    assert 'id="export-pdf"' not in index
    assert "PDF Coil Intake" in index
    assert "COIL-TAG-001" not in index
    assert "Start here" in index
    assert "Drop PDF" in index
    assert "Browse PDF" in index
    # Single-scroll per-coil review order: PDF intake first, then spec/performance,
    # then drawing parameters + drawing, then the paste-ready fields (collapsed below).
    assert index.index('class="pdf-intake-panel primary-intake-panel"') < index.index(
        'id="direct-coil-screen-mirror"'
    )
    assert index.index('id="direct-coil-screen-mirror"') < index.index('id="drawing-parameters"')
    assert index.index('id="drawing-parameters"') < index.index('id="paste-ready-fields"')
    # Build quote package is the FINAL step: a dedicated quote-PDF input at the very
    # bottom (after the paste-ready fields), NOT inside the top intake panel.
    assert 'id="quote-pdf-file"' in index
    assert 'id="quote-package-section"' in index
    assert index.index('id="paste-ready-fields"') < index.index('id="quote-package-section"')
    assert index.index('id="checklist-section"') < index.index('id="build-quote-package"')
    assert (
        index.index('id="build-quote-package"') > index.index('id="quote-package-section"')
    )
    assert ".quote-package-section" in style
    assert "runWorkflowFromPdf" in app_js
    assert '"/api/workflow/pdf-to-drawing"' in app_js
    # Per-coil product line + unit size picker that unlocks the engine dims.
    assert "templateDrawingPicker" in app_js
    assert "ensureProductOptions" in app_js
    assert '"/api/coil-drawing/product-options"' in app_js
    assert '"/api/coil-drawing/derive"' in app_js
    assert "coil-product-line" in app_js
    assert "coil-unit-size" in app_js
    assert ".coil-drawing-picker" in style
    assert '"Content-Type": "application/pdf"' in app_js
    assert "formatPdfAnalysisError" in app_js
    assert "text could not be extracted from this PDF" in app_js
    assert "scanned/image PDF" in app_js
    assert "payload?.detail" in app_js
    assert "body.classList.toggle(\"is-init-stage\"" in app_js
    assert "buildDirectCoilFieldLookup" in app_js
    assert "addCandidateFallbackFields" in app_js
    assert "DIRECT_COIL_STANDARD_TUBE_DIAMETER = \"3/8 1.00 x 0.866\"" in app_js
    assert "DIRECT_COIL_TUBE_DIAMETER_OPTIONS" in app_js
    assert "\"1/2 1.25 x 1.0825\"" in app_js
    assert "DIRECT_COIL_TUBE_MATERIAL_OPTIONS" in app_js
    assert "\"Copper 0.016 Plain\"" in app_js
    assert "DIRECT_COIL_SYSTEM_TYPE_OPTIONS" in app_js
    assert "\"Dual-Circuit Intertwined\"" in app_js
    assert "isDxPdfCandidate" in app_js
    assert "addDxOptionsFallbackFields" in app_js
    assert "pdf_tube_material_to_direct_coil_tube_material" in app_js
    assert "Galvanized Steel 16 gauge" in app_js
    assert "Same End Only" in app_js
    assert "pdf_qty_connections_per_header_to_direct_coil_system_type" in app_js
    assert "candidateHasCoatingReviewSignal" in app_js
    assert "Coating-related PDF text detected" in app_js
    assert "Cover-page handing was mapped into Coil Hand" in app_js
    assert "REGISTERED_DRAWING_TEMPLATE_LABEL" in app_js
    assert "DX / Coil Hand Left / System Type Single-Circuit" in app_js
    assert "Template not registered" in app_js
    assert "coilmaster_dx_lh_header1" in app_js
    assert "DIRECT_COIL_FIXED_DRAWING_VALUES" in app_js
    assert 'connections: "0-Standard"' in app_js
    assert 'mountingholes: "None"' in app_js
    assert 'distributorleadareamaxx: "0"' in app_js
    assert 'distributorleadareamaxy: "0"' in app_js
    assert 'cyclevalveleadlength: "0"' in app_js
    assert "applyventinganddrainingioconstraints: true" in app_js
    assert "limitsrtostandardpositionsforeaseofmanufacture: false" in app_js
    assert "renderDcEmbeddedDrawingPreview" in app_js
    assert "drawingTemplateState" in app_js
    # PDF-reproduction template drawing is carried into uiState and rendered.
    assert "template_drawing: workflow.template_drawing || null" in app_js
    assert "renderTemplateDrawingPreview" in app_js
    # Classification-first rendering: the drawing links from the submittal coil
    # type / hand / header qty, and the dimension state is reported honestly.
    assert "coilClassificationSummary" in app_js
    assert "logic-derived drawing" in app_js
    assert "no matching drawing template registered" in app_js
    assert "Review-aid only — never manufacturing-approved." in app_js
    assert "templateDrawingBody" in app_js
    assert 'id="drawing-template-status"' in index
    assert index.index('id="drawing-parameters"') < index.index('id="drawing-preview"')
    assert "addDxAirFallbackFields" in app_js
    assert "pdf_entering_airflow_to_direct_coil_airflow" in app_js
    assert "pdf_airflow_geometry_to_direct_coil_face_velocity" in app_js
    assert "psychrometric_db_wb_to_relative_humidity" in app_js
    assert "direct_coil_dx_capacity_review_default" in app_js
    assert "DIRECT_COIL_DX_DIST_CAPILLARY_SIZE = \"1/4 x 0.025\"" in app_js
    assert "DIRECT_COIL_DX_DIST_CAPILLARY_OPTIONS" in app_js
    assert "addDxRefrigerantAndFoulingFallbackFields" in app_js
    assert "direct_coil_dx_dist_capillary_company_rule" in app_js
    assert "direct_coil_air_side_fouling_company_rule" in app_js
    assert "Air Side Fouling Factor(ft² °F h/Btu)" in app_js
    assert "calculateRelativeHumidityPct" in app_js
    assert "Face Velocity calculated from Airflow CFM" in app_js
    assert "sensible_capacity_airflow_to_leaving_dry_bulb" not in app_js
    assert "Leaving DB predicted from entering DB" not in app_js
    assert "setDcFieldAlias" in app_js
    assert "direct_coil_company_rule" in app_js
    assert "candidateFallbackField(candidate.tag, \"tag\")" in app_js
    assert "candidateFallbackField(candidate.quantity, \"coil_quantity\")" in app_js
    assert "pdf_candidate_review_fallback" in app_js
    assert "candidate.geometry, \"finned_height\", [\"Finned Height(In)\", \"Tubes High\"]" in app_js
    assert "candidate.geometry, \"finned_length\", [\"Finned Length(In)\"]" in app_js
    assert "candidate.geometry, \"number_of_feeds\", [\"Number Of Feeds(Total)\", \"Number Of Feeds\"]" in app_js
    assert "candidate.geometry, \"fins_per_inch\"" in app_js
    assert "candidate.refrigerant_conditions, \"condensing_temp_f\"" in app_js
    assert "candidate.airside_conditions, \"fluid_type\"" in app_js
    # Leaving DB/WB are wired in the coil-agnostic fallback (not just the DX helper) so the
    # condensing (HGRH/RHHGRC) mirror surfaces them; the mirror carries a Leaving Wet Bulb row.
    assert "candidate.airside_conditions, \"leaving_dry_bulb_f\", [\"Leaving Dry Bulb(°F)\", \"Leaving Dry Bulb\"]" in app_js
    assert "candidate.airside_conditions, \"leaving_wet_bulb_f\", [\"Leaving Wet Bulb(°F)\", \"Leaving Wet Bulb\"]" in app_js
    assert app_js.count("[\"Leaving Wet Bulb(°F)\", \"input\"]") >= 1
    # Water mirror gates the leaving WB row to chilled water (hot water is sensible-only).
    assert "isHotWater ? [] : [[\"Leaving Wet Bulb(°F)\", \"input\"]]" in app_js
    assert "workflowToUiState(state.ui, workflow, null)" in app_js
    assert "state.pdfCoilPages = workflow.pdf_coil_pages || []" in app_js
    assert "selectPdfCoilPage" in app_js
    assert "renderPdfCoilReviewPages" in app_js
    assert "Detected Coil Review Pages" in app_js
    assert "Extracted Candidate Data" in app_js
    assert "Mapped Direct Coil Draft Fields" in app_js
    assert "Project Number" in app_js
    assert "Project Name" in app_js
    assert "pdfProjectDisplayName" in app_js
    assert 'class="pdf-review-page" ${active ? "open" : ""}' not in app_js
    assert 'class="pdf-review-section" open' not in app_js
    assert "scrollIntoView" in app_js
    assert "CONDENSING COIL DATA" in app_js
    assert "CHILLED WATER COIL DATA" in app_js
    assert "HOT WATER COIL DATA" in app_js
    assert "PRE HOT WATER COIL DATA" in app_js
    assert "POST HOT WATER COIL DATA" in app_js
    assert "directCoilMirrorFormat" in app_js
    assert "COOLING_CHILLED_WATER" in app_js
    assert "PREHEAT_HOT_WATER" in app_js
    assert "HEATING_HOT_WATER" in app_js
    assert 'typeText.includes("REHEAT")' not in app_js
    assert "Saturated Suction Temperature" in app_js
    assert "FLUID DATA" in app_js
    assert "pdf_upload_candidate" in app_js
    assert "sanitizeHeaderValue(file.name)" in app_js
    assert "X-CoilForge-Cover-Page" in app_js
    assert "coverPageStatus" in app_js
    assert "setSelectedPdfFile" in app_js
    assert "dataTransfer?.files?.[0]" in app_js
    assert "setPdfAnalysisLoading(true)" in app_js
    assert "setPdfAnalysisLoading(false)" in app_js
    assert "Extracting PDF data..." in app_js
    # Determinate progress: a % bar with a rotating step label (replaces the old
    # looping spinner + static "Reading cover rows..." copy).
    assert 'data-role="fill"' in app_js
    assert "pdfProgress" in app_js
    assert "aria-busy" in app_js
    assert ".pdf-loading-indicator" in style
    assert ".pdf-progress" in style
    assert ".pdf-progress-fill" in style
    # Init stage hides the per-coil review flow until a PDF is analyzed.
    assert "body.is-init-stage .review-flow" in style
    assert ".coil-review-nav" in style
    assert "body.is-init-stage .status-ribbon" in style


def test_web_shell_disables_static_asset_caching_for_pdf_ui_updates() -> None:
    index_response = client.get("/")
    app_response = client.get("/static/app.js?v=phase2f-four-coil-layout-20260609-003")

    assert index_response.status_code == 200
    assert app_response.status_code == 200
    assert index_response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert app_response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert "PDF Coil Intake" in index_response.text
    assert "runWorkflowFromPdf" in app_response.text


def _sample_pdf_bytes() -> bytes:
    return _make_text_pdf(
        [
            "Tag CDXC-1",
            "Coil Quantity 2",
            "Handing Left",
            "Rows Deep 5",
            "Fins Per Inch 10",
            "Finned Height 18 in",
            "Finned Length 36 in",
            "Number Of Feeds 9",
            "Tube Material Copper",
            "Fin Material Aluminum 0.008",
            "Fin Surface Flat",
            "Header Material Copper",
            "Connection Material Copper",
            "Connection Type Sweat",
            'Return Connection Size 7/8"',
            "Casing Material Galvanized Steel",
            "Casing Style Standard",
            "Total Air Flow 2200 cfm",
            "Entering Dry Bulb 80 F",
            "Refrigerant R410A",
            "Evaporating Temperature 45 F",
            "Liquid Temperature 105 F",
            "Superheat 9 F",
            "DXDistCapillarySize 1/4 x 0.025",
            "CD 6.375",
            "BF 0.625",
            "TF 0.625",
            "CH 19.25",
        ]
    )


def _cover_page_pdf_bytes() -> bytes:
    return _make_text_pdf(
        [
            "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
            "1 CDXC-1 DXC Cooling TR_C_015 LH",
            "1 RHHGRC-1 HGRC Reheat TR_C_015 LH",
        ]
    )


def _cover_page_with_ordered_detail_blocks_pdf_bytes() -> bytes:
    return _make_text_pdf(
        [
            "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
            "1 CDXC-1 DXC Cooling TR_C_015 LH",
            "1 RHHGRC-1 HGRH Reheat TR_C_015 LH",
            "CONDENSING COIL DATA",
            "Rows Deep 5",
            "Fins Per Inch 10",
            "Finned Height(In) 18",
            "Finned Length(In) 36",
            "Tube Material Copper",
            "Refrigerant R410A",
            "HGRH COIL DATA",
            "Rows Deep 1",
            "Fins Per Inch 12",
            "Finned Height(In) 9",
            "Finned Length(In) 36",
            "Tube Material Copper",
        ]
    )


def _oxygen8_cooling_dx_and_hgrh_pdf_bytes() -> bytes:
    return _make_text_pdf(
        [
            "Unit Details",
            "Altitude (ft): 0",
            "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
            "1 CDXC-1 DXC Cooling TR_C_040 LH",
            "1 RHHGRC-1 HGRH Reheat TR_C_040 LH",
            "Cooling DX",
            "Coil",
            "Model: 3DX-06.24. 0-11.48.0-18",
            "Fin Height (in): 24",
            "Fin Length (in): 48",
            "Face Area (sq.ft): 8",
            "FPI: 11",
            "Rows: 6",
            "Total Feeds: 18",
            "Fin Surface: Flat",
            "Fin Material: 0.0075 Aluminium",
            "Tube Material: 0.016 Copper",
            "Tube Surface: Smooth",
            "Coil Weight (lbs): 153",
            "Suction Size (in): 1.125",
            "Coil Style: Interlaced 4 Circuits",
            "Qty Conn. / Header: 4",
            "Entering",
            "Airflow (CFM): 3735",
            "DB (F): 95",
            "WB (F): 78",
            "Refrigerant: R-32",
            "Refrig. Suction Temp (F): 43",
            "Refrig. Liquid Temp (F): 77",
            "Refrig. Superheat Temp (F): 9",
            "Coil Operating Setpoint",
            "Nominal Cooling Capacity (MBH): 388.51",
            "DB (F): 55",
            "Max Coil Performance",
            "Capacity (MBH): 329.48",
            "Capacity Sensible (MBH): 168.26",
            "DB (F): 53.44",
            "WB (F): 52.66",
            "Air Vel (FPM): 466.88",
            "Air PD (IWG): 0.38",
            "Internal Vol (cu.in): 741.87",
            "Refrig. PD (psi): 7.39",
            "VRV Integration Kit",
            "Type: AHU Integration Valve Kit",
            "Manufacturer: Daikin",
            "Daikin System Type: Heat Recovery System",
            "Model: EKEXVA72U",
            "Qty of Valves: 4",
            "Nominal Tonnage: 6 tons x 4",
            "Heating DX",
            "Coil",
            "Rows: 99",
            "Fin Height (in): 99",
            "Reheat Hot Gas Reheat Coil",
            "Coil",
            "Model: 3DC-01.24. 0-11.48.0-2",
            "Fin Height (in): 24",
            "Fin Length (in): 48",
            "Face Area (sq.ft): 8",
            "FPI: 11",
            "Rows: 1",
            "Total Feeds: 3",
            "Fin Surface: Flat",
            "Fin Material: 0.0075 Aluminium",
            "Tube Material: 0.016 Copper",
            "Tube Surface: Smooth",
            "Coil Weight (lbs): 41",
            "Suction Size (in): 0.625",
            "Coil Style: Standard",
            "Qty Conn. / Header: 1",
            "Entering",
            "Airflow (CFM): 3735",
            "DB (F): 55",
            "Refrigerant: R-32",
            "Refrig. Cond. Temp (F): 115",
            "Refrig. Subcooling Temp (F): 18",
            "Coil Operating Setpoint",
            "DB (F): 70",
            "Max Coil Performance",
            "Capacity (MBH): 60.85",
            "DB (F): 71.29",
            "Air Vel (FPM): 466.88",
            "Air PD (IWG): 0.03",
            "Internal Vol (cu.in): 123.96",
            "Refrig. PD (psi): 3.82",
            "Supply Fan",
            "Model: GR40C-ZID.DG.CR",
            "Rows: 77",
        ]
    )


def _oxygen8_combined_detail_header_pdf_bytes() -> bytes:
    return _make_text_pdf(
        [
            "Unit Details",
            "Altitude (ft): 43",
            "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
            "1 CDXC-1 DXC Cooling TR_C_009 RH",
            "Cooling DX",
            "Coil Entering Coil Operating Setpoint",
            "Model: DXM08C14-24.00x39.00R",
            "Fin Height (in): 24",
            "Fin Length (in): 39",
            "Face Area (sq.ft): 6.5",
            "FPI: 14",
            "Rows: 8",
            "Total Feeds: 16",
            "Fin Surface: Flat",
            "Fin Material: 0.0075 Aluminium",
            "Tube Material: 0.016 Copper",
            "Tube Surface: Smooth",
            "Coil Weight (lbs): 142.06",
            "Suction Size (in): 1.125",
            "Coil Style: Interlaced 3 Circuits",
            "Qty Conn. / Header: 3",
            "Airflow (CFM): 2750",
            "DB (F): 95",
            "WB (F): 78",
            "Refrigerant: R-32",
            "Refrig. Suction Temp (F): 43",
            "Refrig. Liquid Temp (F): 77",
            "Refrig. Superheat Temp (F): 9",
            "Max Coil Performance",
            "Capacity (MBH): 263.63",
            "Capacity Sensible (MBH): 137.45",
            "DB (F): 49.73",
            "WB (F): 49.52",
            "Air Vel (FPM): 423.08",
            "Air PD (IWG): 0.54",
            "Internal Vol (cu.in): 816.89",
            "Refrig. PD (psi): 4.99",
        ]
    )


def _oxygen8_attached_pdf_text_spacing_bytes() -> bytes:
    return _make_text_pdf(
        [
            "Unit Details",
            "Altitude (ft): 43",
            "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
            "1 CDXC-1 DXC Cooling H05_I_ERV RH",
            "Cooling DX",
            "Coil",
            "Model: DXM08C14-",
            "24.00x39.00R",
            "Fin Height (in): 24",
            "Fin Length (in): 39",
            "Face Area (sq.ft): 6.5",
            "FPI: 14",
            "Rows: 8",
            "Total Feeds: 16",
            "Fin Surface: Flat",
            "Fin Material: 0.0075 Aluminium",
            "Tube Material: 0.016 Copper",
            "Tube Surface: Smooth",
            "Coil Weight (lbs) 67",
            "Suction Size (in): 0.875",
            "Coil Style: Interlaced 2 Circuits",
            "Qty Conn. / Header 2Entering",
            "Airflow (CFM): 850",
            "DB (F): 86.1",
            "WB (F) 85.9",
            "Refrigerant: R-32",
            "Refrig. Suction Temp (F): 43",
            "Refrig. Liquid Temp (F): 77",
            "Refrig. Superheat Temp (F): 9Coil Operating Setpoint",
            "DB (F): 52",
            "Max Coil Performance",
            "Capacity (MBH): 116.23",
            "Capacity Sensible (MBH): 34.87",
            "DB (F): 49.77",
            "WB (F) 49.67",
            "Air Vel (FPM): 463.64",
            "Air PD (IWG): 0.66",
            "Internal Vol (cu.in): 224.07",
            "Refrig. PD (psi): 4.25",
        ]
    )


def _cwc_and_hwc_sections_pdf_bytes() -> bytes:
    return _make_text_pdf(
        [
            "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
            "1 CCWC-1 CWC Cooling B20_V_I_ERV LH",
            "1 HHWC-1 HWC Heating B20_V_I_ERV LH",
            "Cooling CWC",
            "Coil",
            "Model: CWD04C14-16.50x24.00R",
            "Fin Surface: Flat",
            "Fin Height (in): 16.5",
            "Fin Length (in): 24",
            "Face Area (sq.ft): 2.8",
            "FPI: 14",
            "Rows: 4",
            "Circuits: 3",
            "Fin Thickness (in): 0.0075",
            "Coil Depth (in): 7.5",
            "Coil Weight (lbs): 50.4",
            'Inlet Conn. Size (in): 7/8"',
            'Outlet Conn. Size (in): 7/8"',
            "Entering",
            "Airflow (CFM): 1095",
            "DB (F): 86.4",
            "WB (F): 75.2",
            "Fluid Type: Propylene Glycol",
            "Fluid Percent (%): 30",
            "Fluid Ent Temp (F): 45",
            "Fluid Lvg Temp (F): 57",
            "Coil Operating Setpoint",
            "DB (F): 70",
            "Max Coil Performance",
            "Airflow (CFM): 1095",
            "Capacity (MBH): 50.7",
            "DB (F): 64.1",
            "WB (F): 62.9",
            "Air Vel (FPM): 398",
            "Air PD (inWG): 0.403",
            "Fluid Flow Rate (GPM): 9.01",
            "Fluid PD (ftWG): 11.16",
            "Fluid Vel (fps): 3.32",
            "Valve & Actuator",
            "Valve Spec: Brass Trim, Normally Closed, SAS, 0-10V",
            "Actuator: SAS-61.33U",
            "Valve Size (in): 3/4",
            "Control Valve (Cv): 6.3",
            "Description: 2WNC BR FxF 0.75/6.3 + SAS61.33U",
            "Heating HWC",
            "Coil",
            "Model: HWD02C08-18.00x30.00R",
            "Fin Surface: Flat",
            "Fin Height (in): 18",
            "Fin Length (in): 30",
            "Face Area (sq.ft): 3.8",
            "FPI: 8",
            "Rows: 2",
            "Circuits: 1",
            "Fin Thickness (in): 0.0075",
            "Coil Depth (in): 5.5",
            "Coil Weight (lbs): 32.8",
            "Inlet Conn. Size (in): 0.75",
            "Outlet Conn. Size (in): 0.75",
            "Entering",
            "Airflow (CFM): 1095",
            "DB (F): 50.4",
            "Fluid Type: Water",
            "Fluid Percent (%): 100",
            "Fluid Ent Temp (F): 140",
            "Fluid Lvg Temp (F): 110",
            "Coil Operating Setpoint",
            "DB (F): 85",
            "Max Coil Performance",
            "Airflow (CFM): 1095",
            "Capacity (MBH): 41.9",
            "DB (F): 85.8",
            "Air Vel (FPM): 292",
            "Air PD (inWG): 0.047",
            "Fluid Flow Rate (GPM): 2.82",
            "Fluid PD (ftWG): 6.5",
            "Fluid Vel (fps): 3.04",
            "Valve & Actuator",
            "Valve Size (in): 1/2",
        ]
    )


def _repeated_preheat_and_heating_hwc_pdf_bytes() -> bytes:
    return _make_text_pdf(
        [
            "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
            "1 PHWC-1 HWC Pre-Heat H05_I_ERV_BP LH",
            "1 HHWC-1 HWC Heating H05_I_ERV_BP LH",
            "2 PHWC-2 HWC Pre-Heat H05_I_ERV_BP LH",
            "2 HHWC-2 HWC Heating H05_I_ERV_BP LH",
            "Preheat HWC",
            "Coil",
            "Fin Height (in): 10.5",
            "Fin Length (in): 14.25",
            "Rows: 2",
            "Max Coil Performance",
            "Capacity (MBH): 23",
            "Heating HWC",
            "Coil",
            "Fin Height (in): 10.5",
            "Fin Length (in): 14.25",
            "Rows: 3",
            "Max Coil Performance",
            "Capacity (MBH): 13.1",
            "Supply Fan",
            "Rows: 77",
            "Preheat HWC",
            "Coil",
            "Fin Height (in): 12.5",
            "Fin Length (in): 20",
            "Rows: 4",
            "Max Coil Performance",
            "Capacity (MBH): 31",
            "Heating HWC",
            "Coil",
            "Fin Height (in): 13.5",
            "Fin Length (in): 21",
            "Rows: 5",
            "Max Coil Performance",
            "Capacity (MBH): 21",
            "Supply Fan",
            "Rows: 88",
        ]
    )


def _four_format_cover_page_pdf_bytes() -> bytes:
    return _make_text_pdf(
        [
            "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
            "1 CDXC-1 DXC Cooling TR_C_015 LH",
            "1 RHHGRC-1 HGRC Reheat TR_C_015 LH",
            "1 CCWC-1 Chilled Water Coil TR_C_015 LH",
            "1 PHWC-1 Pre Hot Water Coil TR_C_015 LH",
            "1 HHWC-1 Post Hot Water Coil TR_C_015 LH",
        ]
    )


def _make_text_pdf(lines: list[str]) -> bytes:
    text_ops = ["BT", "/F1 12 Tf", "72 720 Td"]
    first = True
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if not first:
            text_ops.append("0 -16 Td")
        text_ops.append(f"({safe}) Tj")
        first = False
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("latin-1")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        (
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        ),
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        f"5 0 obj << /Length {len(stream)} >> stream\n".encode("ascii")
        + stream
        + b"\nendstream endobj\n",
    ]
    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = []
    for obj in objects:
        offsets.append(output.tell())
        output.write(obj)
    xref_offset = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return output.getvalue()


# --------------------------------------------------------------------------- #
# Structured-table detail mapping: pdfplumber's side-by-side section columns must
# map each value to the right field instead of letting the flattened text line
# bleed neighbouring columns together (the "Finned Height = '12 WB (F) 80 DB (F):
# 55'" bug). Fixtures are synthetic — no customer data.
# --------------------------------------------------------------------------- #
def _detail_lines_as_dict(page: _TextPage) -> dict[str, str]:
    return {line.source_key: line.source_value for line in _extract_detail_lines_from_page(page)}


def test_detail_table_maps_side_by_side_section_columns() -> None:
    # Mirrors the real submittal grid: col0/1 = Coil, col4/5 = Entering,
    # col7/8 = Coil Operating Setpoint (spacer columns between).
    table = (
        ("Cooling DX", "", "", "", "", "", "", "", ""),
        ("", "", "", "", "", "", "", "", ""),
        ("Coil", "", "", "", "Entering", "", "", "Coil Operating Setpoint", ""),
        ("Model:", "DXM06C11", "", "", "Airflow (CFM):", "690", "", "Nominal Cooling Capacity (MBH)", "71.92"),
        ("", "", "", "", "DB (F):", "95", "", "", ""),
        ("Fin Height (in):", "12", "", "", "WB (F)", "80", "", "DB (F):", "55"),
        ("Fin Length (in):", "22", "", "", "Refrigerant:", "R-32", "", "", ""),
        ("FPI", "11", "", "", "", "", "", "", ""),
        ("Rows", "6", "", "", "", "", "", "", ""),
        ("Total Feeds", "4", "", "", "", "", "", "", ""),
    )
    page = _TextPage(page_number=4, text="", tables=(table,))
    fields = _detail_lines_as_dict(page)

    # Finned height is the number, NOT the bled "12 WB (F) 80 DB (F): 55" string.
    assert fields["FINNED_HEIGHT"] == "12"
    assert fields["FINNED_LENGTH"] == "22"
    assert fields["FINS_PER_INCH"] == "11"
    assert fields["ROWS_DEEP"] == "6"
    assert fields["NUMBER_OF_FEEDS_TOTAL"] == "4"
    # Entering vs Operating Setpoint "DB (F)" disambiguated by section column.
    assert fields["ENTERING_DRY_BULB_F"] == "95"
    assert fields["ENTERING_WET_BULB_F"] == "80"
    assert fields["OPERATING_SETPOINT_DB_F"] == "55"
    assert fields["TOTAL_AIR_FLOW_CFM"] == "690"
    assert fields["REFRIGERANT"] == "R-32"


def test_detail_table_plain_two_column_label_value() -> None:
    # No section header row -> defaults to a single 'coil' label column at col0.
    table = (
        ("Fin Height (in):", "14"),
        ("Fin Length (in):", "30"),
        ("Rows", "8"),
    )
    page = _TextPage(page_number=2, text="", tables=(table,))
    fields = _detail_lines_as_dict(page)

    assert fields["FINNED_HEIGHT"] == "14"
    assert fields["FINNED_LENGTH"] == "30"
    assert fields["ROWS_DEEP"] == "8"


def test_detail_text_fallback_when_no_tables() -> None:
    # Empty tables -> the existing text-line parser still maps fields (no regression).
    page = _TextPage(
        page_number=3,
        text="Coil\nFin Height (in): 16\nFin Length (in): 40",
        tables=(),
    )
    fields = _detail_lines_as_dict(page)

    assert fields["FINNED_HEIGHT"] == "16"
    assert fields["FINNED_LENGTH"] == "40"


# --------------------------------------------------------------------------- #
# Cover-row product code -> product line + unit size: the cover model code
# (e.g. "TR_C_040") drives the CoilForge product line (Terra H) + R-076 unit
# size, surfaced in the cover summary and carried into the drawing context so
# the rule engine can run without a manual pick. Review-aid, overridable.
# --------------------------------------------------------------------------- #
def test_cover_row_summary_derives_product_line_and_size_from_model_code() -> None:
    summary = _cover_row_summary(
        _CoverRow(page_number=1, row_number=2, qty=1, tag="CDXC-1",
                  item="DX Cooling Coil", model="TR_C_040", handing="RH")
    )
    assert summary.product_type == "DX"      # coil family unchanged
    assert summary.product_line == "TERRA H"  # from the cover model code
    assert summary.unit_size == "040"


def test_cover_row_product_code_flows_into_drawing_context() -> None:
    candidate = _candidate_from_cover_row(
        _CoverRow(page_number=1, row_number=2, qty=1, tag="CDXC-1",
                  item="DX Cooling Coil", model="TR_V_012", handing="LH"),
        source_id="TEST", index=1,
    )
    ctx = _template_header_context_from_candidate(candidate)
    assert ctx["product_type"] == "TERRA V"   # engine product line, from the code
    assert ctx["unit_size"] == "012"


# --------------------------------------------------------------------------- #
# Continuation-page cover rows must keep their `model` code. When the cover
# schedule spills onto a 2nd page, that page rarely repeats the column header,
# so it is parsed by the header-less positional table parser. The continuation
# scan used to fall back to the text-line parser, which never captures `model`
# -- so a coil on page 2 lost its product/model code and could not resolve its
# product line + unit size (real symptom: a "TV_B_024" DX showing "needs coil
# type + product line + unit size to evaluate fit"). Table-first fixes it.
# --------------------------------------------------------------------------- #
_COVER_HEADER_CELLS = (
    "Qty", "Tag", "Item", "Model", "Voltage",
    "Controls Preference", "Installation", "Duct Connection", "Handing",
)


def test_continuation_page_cover_row_keeps_model_code() -> None:
    header_page = _TextPage(
        page_number=1,
        text="Coil Schedule",
        tables=(
            (
                _COVER_HEADER_CELLS,
                ("1", "CDXC-2", "DXC Cooling", "TV_B_012",
                 "208/60/3", "BMS", "Vertical", "S2", "LH"),
            ),
        ),
    )
    # Page 2: the schedule continues but the header band is gone -> a header-less
    # positional table (col0=qty, col1=tag, col3=model), exactly the real PDF shape.
    continuation_page = _TextPage(
        page_number=2,
        text="1 CDXC-3 DXC Cooling",  # text line carries NO model (the old bug path)
        tables=(
            (
                ("1", "CDXC-3", "DXC Cooling", "TV_B_024",
                 "208/60/3", "BMS", "Vertical", "S2", "LH"),
            ),
        ),
    )

    detection = detect_cover_page_from_pdf_pages([header_page, continuation_page])

    by_tag = {row.tag: row for row in detection.rows}
    assert set(by_tag) == {"CDXC-2", "CDXC-3"}
    # The continuation row keeps its model (was "" before the table-first fix)...
    assert by_tag["CDXC-3"].model == "TV_B_024"
    # ...so its product line + unit size resolve just like a first-page row.
    summary = _cover_row_summary(by_tag["CDXC-3"])
    assert summary.product_line == "TERRA V"
    assert summary.unit_size == "024"


# --------------------------------------------------------------------------- #
# Valve / EEV accessory rows must NOT be detected as coils. An electronic
# expansion valve kit tagged "EKEXV-CDXC-1" with item "EKEXV Valve (DX Coil)"
# previously slipped through the coil filter on the "dxcoil" substring and then
# stole the second DX detail block, leaving CDXC-2 empty.
# --------------------------------------------------------------------------- #
def test_is_cover_coil_row_rejects_eev_valve_accessory_rows() -> None:
    assert _is_cover_coil_row("CDXC-1", "DXC Cooling") is True
    assert _is_cover_coil_row("CDXC-2", "DXC Cooling") is True
    # EKEXV tag prefix is rejected even when the item text mentions a DX coil.
    assert _is_cover_coil_row("EKEXV-CDXC-1", "EKEXV Valve (DX Coil)") is False
    assert _is_cover_coil_row("EKEXV-CDXC-1", "DX Coil") is False
    # A plain valve item is rejected via the item-token guard.
    assert _is_cover_coil_row("PHWCV-2", "HWC Pre-Heat Valve") is False


def test_is_coil_tag_structural_predicate() -> None:
    """A coil tag is EXACTLY <coil-prefix>-<seq>. Everything else is an accessory,
    a unit, or a mangled read -- and none of those may become a coil.

    The rejected spellings are not hypothetical variants: this codebase names the
    expansion-valve kit ``EKEXVA{n}U``, so a submittal tagging it ``EKEXVA-CDXC-1``
    walked straight past the old three-string denylist.
    """
    for tag in ("CDXC-1", "RHHGRH-2", "RHHGRC-10", "ccwc-3", "PHWC - 4", " HHWC-1 "):
        assert is_coil_tag(tag) is True, tag
    for tag in (
        "EKEXV-CDXC-1",     # the reported case
        "EKEXVA-CDXC-1",    # spelling variant the denylist never listed
        "EKEXVA72U-CDXC-1",
        "EEVK-CDXC-1",
        "TXV-CDXC-1",
        "PHWCV-2",          # valve tag that merely starts like a coil prefix
        "ERV-02",           # parent unit, not a coil
        "DOAS-1",
        "660024-001",       # a part number (the HGBP adder line)
        "CDXC",             # no sequence
        "CDXC-1-EXTRA",     # trailing segment -- old split("-")[0] read this as a coil
        "",
    ):
        assert is_coil_tag(tag) is False, tag


def test_coil_tag_rejection_reason_names_the_tag_and_the_cause() -> None:
    """Every rejection is explainable. A row that vanishes without a reason reads as
    'not in the submittal', which is the failure this filter must not cause."""
    assert coil_tag_rejection_reason("CDXC-1", "DXC Cooling") is None

    structural = coil_tag_rejection_reason("EKEXV-CDXC-1", "DX Coil")
    assert structural is not None
    assert "EKEXV-CDXC-1" in structural and "not a coil tag" in structural

    # A structurally-VALID coil tag whose item names an accessory: the item-token
    # signal is the only thing that catches this, so it must survive independently.
    item_based = coil_tag_rejection_reason("CDXC-1", "EEV Kit")
    assert item_based is not None
    assert "accessory" in item_based

    # A multi-tag cover cell (qty 2, two coils on one row) is a coil row; a cell with
    # any accessory member is not. _expand_cover_tags splits the accepted one later.
    assert coil_tag_rejection_reason("CDXC-1, CDXC-2", "DXC Cooling") is None
    assert coil_tag_rejection_reason("CDXC-1, EKEXV-CDXC-1", "DXC Cooling") is not None


def test_cover_item_canonicalization_cannot_launder_a_valve_row() -> None:
    """The text-line cover path canonicalizes the item BEFORE the coil test, so
    "EKEXV Valve (DX Coil)" arrives as "DX Coil" with the 'valve'/'ekexv' tokens
    already destroyed. The structural tag rule is what closes that asymmetry (the
    table path passes the raw cell and never had it)."""
    page = _TextPage(page_number=1, text="")
    assert _cover_row_from_text_line(
        page, 1, "1 EKEXV-CDXC-1 EKEXV Valve (DX Coil) EKEXVA72U LH"
    ) is None
    # The real coil on the same cover still parses.
    rows = _cover_row_from_text_line(page, 2, "1 CDXC-1 DXC Cooling TR_C_032 LH")
    assert rows is not None and [r.tag for r in rows] == ["CDXC-1"]


def test_eev_valve_dropped_and_second_dx_section_reaches_cdxc_2() -> None:
    pdf_bytes = _cdxc1_eev_cdxc2_two_dx_sections_pdf_bytes()

    pages = detect_cover_page_from_pdf_pages(_pages_from_pdf_text(pdf_bytes))
    # EKEXV-CDXC-1 is dropped; only the two real coils survive.
    assert [row.tag for row in pages.rows] == ["CDXC-1", "CDXC-2"]

    workflow = run_pdf_to_drawing_workflow(pdf_bytes)
    coil_pages = workflow["pdf_coil_pages"]
    assert [page["tag"] for page in coil_pages] == ["CDXC-1", "CDXC-2"]

    cdxc1_fields = coil_pages[0]["workflow"]["direct_coil_input_draft"]["fields"]
    cdxc2_fields = coil_pages[1]["workflow"]["direct_coil_input_draft"]["fields"]
    # CDXC-1 keeps the first DX section; CDXC-2 now receives the second section
    # (the block the phantom EKEXV row used to steal) instead of coming back empty.
    assert cdxc1_fields["rows_deep"]["value"] == 6
    assert cdxc1_fields["finned_height"]["value"] == 24
    assert cdxc2_fields["rows_deep"]["value"] == 4
    assert cdxc2_fields["finned_height"]["value"] == 18
    # Header wall schedule defaults to "(L)" for both coils (review-required) on the
    # canonical candidate.
    cdxc1_candidate = coil_pages[0]["workflow"]["candidates"][0]
    cdxc2_candidate = coil_pages[1]["workflow"]["candidates"][0]
    assert cdxc1_candidate["materials_construction"]["header_wall_schedule"]["value"] == "(L)"
    assert cdxc2_candidate["materials_construction"]["header_wall_schedule"]["value"] == "(L)"


@pytest.mark.parametrize(
    "source, expected",
    [
        ("Sine", "Corrugated"),
        ("Sine Wave", "Corrugated"),
        ("wavy", "Corrugated"),
        ("Sinusoidal", "Corrugated"),
        ("Lanced", "Lanced"),
        ("Louvered", "Lanced"),
        ("Flat", "Flat"),
        ("Plain", "Flat"),
        ("Aluminum Mystery", "Manual Review Required"),
    ],
)
def test_normalize_fin_surface_maps_source_terms(source: str, expected: str) -> None:
    assert _normalize_fin_surface(source) == expected


def _pages_from_pdf_text(pdf_bytes: bytes) -> list[_TextPage]:
    from coilforge.submittal.pdf_intake import extract_text_pages_from_pdf_bytes

    pages, _engine = extract_text_pages_from_pdf_bytes(pdf_bytes)
    return pages


def _cdxc1_eev_cdxc2_two_dx_sections_pdf_bytes() -> bytes:
    return _make_text_pdf(
        [
            "Unit Details",
            "Altitude (ft): 0",
            "Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing",
            "1 CDXC-1 DXC Cooling TR_C_040 LH",
            "1 EKEXV-CDXC-1 EKEXV Valve (DX Coil) EKEXVA72U LH",
            "1 CDXC-2 DXC Cooling TR_C_041 LH",
            "Cooling DX",
            "Coil",
            "Fin Height (in): 24",
            "Fin Length (in): 48",
            "FPI: 11",
            "Rows: 6",
            "Total Feeds: 18",
            "Cooling DX",
            "Coil",
            "Fin Height (in): 18",
            "Fin Length (in): 36",
            "FPI: 13",
            "Rows: 4",
            "Total Feeds: 9",
        ]
    )


def test_unrecognised_model_code_leaves_product_line_blank() -> None:
    summary = _cover_row_summary(
        _CoverRow(page_number=1, row_number=3, qty=1, tag="CDXC-2",
                  item="DX Cooling", model="DXM06C11")
    )
    assert summary.product_line == ""
    assert summary.unit_size == ""


def test_suntion_size_misspelling_maps_to_return_connection_size() -> None:
    """HGRH reheat tables mis-spell "Suction" as "Suntion" (John 2026-06-25). The
    detail-label match is exact, so without the variant the connection size is
    dropped and the drawing "R" (= conn size) renders blank. Lock the mapping."""
    for label in ("Suntion Size (in)", "Suntion Size"):
        assert _match_detail_label(label, "coil") == "RETURN_CONNECTION_SIZE"
    # The known-good spellings still resolve.
    assert _match_detail_label("Suction Size (in)", "coil") == "RETURN_CONNECTION_SIZE"
    assert _match_detail_label("Sunction Size (in)", "coil") == "RETURN_CONNECTION_SIZE"


def test_plain_connection_size_label_maps_to_return_connection_size() -> None:
    """HGRH reheat blocks label their single connection plainly "Connection Size (in)"
    (not "Suction/Suntion Size") — e.g. 2766 Olympic RHHGRH-2. Without this mapping the
    connection size (and thus drawing "R" via R-052) is dropped (John 2026-06-27)."""
    assert _match_detail_label("Connection Size (in)", "coil") == "RETURN_CONNECTION_SIZE"
    assert _match_detail_label("Connection Size", "coil") == "RETURN_CONNECTION_SIZE"
    # Exact-match only: must NOT swallow the qualified supply/return connection labels.
    assert _match_detail_label("Supply Connection Size", "coil") != "RETURN_CONNECTION_SIZE"


# --------------------------------------------------------------------------- #
# Hot gas bypass (HGBP / ASC) is quoted as a PROJECT-level cover line item, never
# as a coil row -- "660024-001 HGBP VALVE - DANFOSS AXV-H and hot-gas bypass
# stub-out on coils adder". That row is correctly discarded as an accessory by
# _is_cover_coil_row (the "valve" token), so the flag is read from page TEXT and
# applied package-wide to DX coils only. Real source: 2910 Airreps WA / CBRE
# Hilltop KS submittal (John 2026-07-15).
# --------------------------------------------------------------------------- #
_HGBP_COVER_LINE = (
    "1 Miscellaneous 660024-001 HGBP VALVE - DANFOSS AXV-H "
    "and hot-gas bypass stub-out on coils adder"
)


# The SAME words in a consulting engineer's spec narrative name the field refrigerant
# PIPE, not the quoted option. Real source: 2968 HTS Houston / College of the Mainland,
# Addendum No. 1 p.12 (2.2 COMPRESSOR item E) -- 9 pages BEFORE the p.21 cover schedule.
# It tagged both DX coils in that package HGBP, and the Nova/Ventum-H product-line gate
# then withheld the Terra H drawing (John 2026-07-31).
_HGBP_SPEC_PROSE_LINE = (
    "expansion valve, liquid line, insulated hot gas bypass line, "
    "insulated hot gas line and insulated suction line."
)


def test_package_hgbp_detected_from_real_cover_line_item() -> None:
    pages = [
        _TextPage(page_number=1, text="1 CDXC-1 DX Cooling Coil"),
        _TextPage(page_number=2, text=_HGBP_COVER_LINE),
    ]
    assert _package_hgbp_pages(pages, cover_page=1) == (2,)


def test_package_hgbp_detected_on_continuation_page_yielding_no_coil_rows() -> None:
    """The adder sits on a later page that produces NO coil rows. The continuation
    scan breaks on the first such page, so the HGBP read must not depend on it --
    which is why the cover-page scan window has no upper bound."""
    pages = [
        _TextPage(page_number=1, text="1 CDXC-1 DX Cooling Coil"),
        _TextPage(page_number=2, text="Notes    Start Up Assistance"),  # no coil rows
        _TextPage(page_number=3, text=_HGBP_COVER_LINE),
    ]
    assert _package_hgbp_pages(pages, cover_page=1) == (3,)


def test_package_hgbp_ignores_spec_narrative_before_the_cover_page() -> None:
    """The 2968 regression. The option is a cover LINE ITEM, so a spec section ahead
    of the cover schedule cannot state it -- scanning it blanket-tagged every DX coil
    in the package and got their drawings withheld."""
    pages = [
        _TextPage(page_number=12, text=_HGBP_SPEC_PROSE_LINE),
        _TextPage(page_number=21, text="1 CDXC-1 DXC Cooling TR_C_032 LH"),
    ]
    assert _package_hgbp_pages(pages, cover_page=21) == ()


def test_package_hgbp_ignores_the_piping_run_form_inside_the_scan_window() -> None:
    """Second, independent guard: "<token> line" is a refrigerant PIPE, never the
    quoted option -- so the prose is ignored even when it lands at/after the cover."""
    pages = [_TextPage(page_number=1, text=_HGBP_SPEC_PROSE_LINE)]
    assert _package_hgbp_pages(pages, cover_page=1) == ()
    assert _package_hgbp_pages(pages) == ()  # and under the no-cover whole-doc scan


def test_package_hgbp_line_item_still_wins_on_a_page_that_also_has_the_prose() -> None:
    """Recall guard: excluding the piping-run form must not cost a real adder that
    shares its page."""
    pages = [
        _TextPage(
            page_number=2, text=f"{_HGBP_SPEC_PROSE_LINE}\n{_HGBP_COVER_LINE}"
        ),
    ]
    assert _package_hgbp_pages(pages, cover_page=1) == (2,)


def test_package_hgbp_ignores_asc_count_on_a_coil_drawing_page() -> None:
    """The EZ drawing states hot gas bypass as an ASC COUNT, not the HGBP token.
    The package scan spans the whole document, so it must ignore ASC entirely --
    otherwise one HGBP coil's drawing page would blanket every DX in the package.
    Excluding ASC is what makes the whole-document scan safe."""
    pages = [
        _TextPage(page_number=1, text="1 CDXC-1 DX Cooling Coil"),
        _TextPage(page_number=2, text="DISTRIBUTORS (1)501-2-3/16-1.5(1 ASC) OD:5/8"),
        _TextPage(page_number=3, text="DISTRIBUTORS (1)501-2-3/16-1.5(0 ASC) OD:5/8"),
    ]
    assert _package_hgbp_pages(pages) == ()


def test_package_hgbp_absent_when_no_option_stated() -> None:
    pages = [_TextPage(page_number=1, text="1 CDXC-1 DX Cooling Coil")]
    assert _package_hgbp_pages(pages) == ()


def test_cover_hgbp_note_flows_into_dx_drawing_context_as_special_feature() -> None:
    """End-to-end producer -> consumer: the intake note carries the package fact and
    _detect_hgbp reads it back off the candidate notes. Guards note/regex drift."""
    candidate = _candidate_from_cover_row(
        _CoverRow(page_number=1, row_number=1, qty=1, tag="CDXC-1",
                  item="DX Cooling Coil", model="DXM05C13", handing="LH"),
        source_id="TEST", index=1, package_hgbp_pages=(3,),
    )
    assert any("HGBP" in note for note in candidate.notes)
    ctx = _template_header_context_from_candidate(candidate)
    assert ctx["special_feature"] == "HGBP"


@pytest.mark.parametrize(
    "tag, item",
    [
        ("RHHGRC-1", "HGRH Coil"),
        ("HHWC-1", "Hot Water Coil"),
        ("CCWC-1", "Chilled Water Coil"),
    ],
)
def test_cover_hgbp_never_tags_water_or_reheat_coils(tag: str, item: str) -> None:
    """Only DX has an HGBP template bucket (_entry_for_dx_hgbp). Tagging a water or
    reheat coil HGBP would match no bucket and blank its drawing silently, so the
    package flag must stop at DX."""
    candidate = _candidate_from_cover_row(
        _CoverRow(page_number=1, row_number=1, qty=1, tag=tag, item=item, handing="LH"),
        source_id="TEST", index=1, package_hgbp_pages=(3,),
    )
    assert not any("HGBP" in note for note in candidate.notes)
    ctx = _template_header_context_from_candidate(candidate)
    assert "special_feature" not in ctx


def test_cover_row_without_package_hgbp_gets_no_note() -> None:
    """Regression guard: a coil in a package with no HGBP adder is unchanged."""
    candidate = _candidate_from_cover_row(
        _CoverRow(page_number=1, row_number=1, qty=1, tag="CDXC-1",
                  item="DX Cooling Coil", handing="LH"),
        source_id="TEST", index=1,
    )
    assert not any("HGBP" in note for note in candidate.notes)
    assert "special_feature" not in _template_header_context_from_candidate(candidate)


def test_drawing_notes_never_diverge_from_the_drawings_own_notes() -> None:
    """The paste "Drawing Notes" field and the drawing's slot.NOTES are assembled from
    the same engine call and must never disagree — that is the promise in
    `_engine_drawing_notes`'s docstring, and it was broken (John 2026-07-29).

    The notes were gated on the CANDIDATE's product line + unit size, but a candidate can
    lack both while the drawing still resolves them from the full-PDF model-code scan.
    On 2949 Ferguson Theatre every HWC coil hit exactly that: the drawing carried the
    vent/drain note while the panel read "unmapped". This asserts the invariant rather
    than the one shape of the bug, so any future gate that resolves for one surface and
    not the other trips it."""
    workflow = run_pdf_to_drawing_workflow(_cwc_and_hwc_sections_pdf_bytes())

    checked = 0
    for page in workflow["pdf_coil_pages"]:
        wf = page["workflow"]
        slot_notes = (wf["template_drawing"].get("slot_values") or {}).get("slot.NOTES")
        if not slot_notes:
            continue
        paste = [
            f for f in wf["direct_coil_paste_ready"]["fields"]
            if f["normalized_key"] == "drawing_notes"
        ]
        assert paste, page["tag"]
        value = paste[0]["value"]
        assert value, f"{page['tag']}: drawing carries notes but the panel is empty"
        # Same sentences, whatever the joiner (drawing joins with " ", paste with "\n").
        for sentence in str(value).split("\n"):
            assert sentence.strip() and sentence.strip() in str(slot_notes), page["tag"]
        checked += 1

    assert checked, "fixture produced no drawing notes — the guard would be vacuous"


# --------------------------------------------------------------------------- #
# Custom coil coating: the submittal states it as an ASTERISK-DELIMITED annotation
# inside the coil detail block, not as a "Coil Coating: <value>" label line. Missing
# it made every coated coil read as the "Plain" Direct Coil default AND dropped the
# R-080/R-081 "Do Not Coat Last 5-6 inches..." note, which fires `only_when:
# coating_set`. Real source: 2968 HTS Houston / College of the Mainland p.26 (Cooling
# DX, standalone) and p.27 (Reheat HGRH, trailing a Coil Weight line) -- John
# 2026-07-31. Fixtures are synthetic.
# --------------------------------------------------------------------------- #
def test_detail_coating_annotation_extracted_when_standalone() -> None:
    page = _TextPage(
        page_number=26,
        text="Cooling DX\nRows: 6\n*Finkote2 Epoxy Coil Coating*\n",
    )
    assert _detail_lines_as_dict(page)["COIL_COATING"] == "Finkote2 Epoxy Coil Coating"


def test_detail_coating_annotation_does_not_consume_its_host_line() -> None:
    """On the HGRH page the annotation trails a real label/value pair. Both readings are
    wanted: the coating comes off the flattened text line while Coil Weight comes off the
    structured cell (tables are seeded first and `_add_line` is first-wins), so neither
    displaces the other. Verified against the real 2968 p.27 -- COIL_WEIGHT_LBS reads
    '32.94', not the annotation-polluted text-line form."""
    table = (
        ("Reheat Hot Gas Reheat Coil", "", ""),
        ("", "", ""),
        ("Coil", "", ""),
        ("Coil Weight (lbs)", "32.94", ""),
    )
    page = _TextPage(
        page_number=27,
        text=(
            "Reheat Hot Gas Reheat Coil\n"
            "Coil Entering Coil Operating Setpoint\n"  # sets the "coil" label context
            "Coil Weight (lbs) 32.94 *Finkote2 Epoxy Coil Coating*\n"
        ),
        tables=(table,),
    )
    fields = _detail_lines_as_dict(page)
    assert fields["COIL_COATING"] == "Finkote2 Epoxy Coil Coating"
    assert fields["COIL_WEIGHT_LBS"] == "32.94"


def test_detail_coating_annotation_ignores_unterminated_footnote_markers() -> None:
    """The detail block also carries one-sided footnote markers. Requiring the CLOSING
    asterisk is what separates the coating annotation from those."""
    page = _TextPage(
        page_number=27,
        text=(
            "Reheat Hot Gas Reheat Coil\nRows: 1\n"
            "*Separate electrical connection required for heater\n"
        ),
    )
    assert "COIL_COATING" not in _detail_lines_as_dict(page)


def test_detail_coating_annotation_absent_on_an_uncoated_coil() -> None:
    """Regression guard: Oxygen8 submittals simply omit the annotation when there is no
    coating, and a missing value must keep reading as "no coating" (R-080/R-081 stay
    silent) rather than being invented."""
    page = _TextPage(page_number=26, text="Cooling DX\nRows: 6\nTotal Feeds: 18\n")
    assert "COIL_COATING" not in _detail_lines_as_dict(page)
