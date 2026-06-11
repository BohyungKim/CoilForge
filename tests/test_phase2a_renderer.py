from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.phase2a.fixtures import load_default_dx_header1_state
from coilforge.phase2a.models import DxHeader1ParameterState
from coilforge.phase2a.renderer import (
    DEFAULT_VIEWBOX,
    REVIEW_WATERMARK,
    SvgRenderRequest,
    render_dx_header1_svg,
)
from coilforge.phase2a.validation import validate_dx_header1_state


REQUIRED_ZONE_IDS = [
    "zone.sheet_frame",
    "zone.title_block",
    "zone.front_view",
    "zone.side_header_view",
    "zone.right_panel",
    "zone.bottom_dimension_table",
    "zone.review_metadata",
    "markup.review",
]


def test_renderer_includes_required_svg_zones_and_review_language() -> None:
    state = load_default_dx_header1_state()
    report = validate_dx_header1_state(state)

    response = render_dx_header1_svg(
        SvgRenderRequest(state=state, validation_report=report)
    )

    assert "<svg" in response.svg
    assert f'viewBox="{DEFAULT_VIEWBOX}"' in response.svg
    for zone_id in REQUIRED_ZONE_IDS:
        assert f'id="{zone_id}"' in response.svg
    assert REVIEW_WATERMARK in response.svg
    assert "OAL" in response.svg
    assert "REVIEW REQUIRED" in response.svg
    assert response.metadata["release_status"] == "review_aid_only"
    assert response.metadata["drawing_status"] == "generated_with_warnings"


def test_renderer_uses_ez_coil_style_grid_and_evidence_bindings() -> None:
    state = load_default_dx_header1_state()
    response = render_dx_header1_svg(
        SvgRenderRequest(state=state, validation_report=validate_dx_header1_state(state))
    )

    for expected in [
        'data-grid-style="ez_coil_dx_header1_candidate"',
        'id="zone.ez_right_spec_grid"',
        'id="zone.ez_bottom_grid"',
        "3.50 HD2",
        "4.50 HDx1",
        "8.00 SL2",
        "3.00 I1",
        "2.75 S1",
        "2.00 O2",
        "0.63 R2",
        "20.25 OAL",
        "TUBE MATERIAL",
        "FIN MATERIAL",
        "RETURN CONN SIZE",
    ]:
        assert expected in response.svg

    assert response.metadata["grid_style_id"] == "ez_coil_dx_header1_candidate"
    assert response.metadata["grid_source_case_id"] == "EZC-0001"
    assert response.metadata["oal_review_status"] == "observed_candidate_review_required"
    labels = {binding["label"]: binding for binding in response.metadata["grid_bindings"]}
    assert labels["I1"]["json_paths"] == ("Geometry.Headers[0].IO[0]",)
    assert labels["BF"]["json_paths"] == ("Geometry.BSP",)
    assert labels["OAL"]["review_status"] == "observed_candidate_review_required"


def test_renderer_changes_when_parameter_values_change() -> None:
    state = load_default_dx_header1_state()
    changed = DxHeader1ParameterState.model_validate(
        {
            **state.model_dump(),
            "coil_name": "FIELD_EDITED_COIL",
            "model_number": "DX-EDITED",
            "rows": 8,
            "fin_height": 20.5,
            "fin_length": 31.75,
            "fin_density_fpi": 14.0,
            "casing_height": 22.0,
            "casing_length": 35.0,
            "casing_depth": 7.25,
            "top_flange": 0.75,
            "bottom_flange": 0.5,
            "return_bend_allowance": 2.25,
            "coil_hand": "Right",
            "airflow_direction": "right_to_left",
            "return_connection_size": 0.875,
            "circuiting_display": "Edited circuiting",
            "notes": ["Edited note"],
        }
    )

    svg = render_dx_header1_svg(
        SvgRenderRequest(
            state=changed,
            validation_report=validate_dx_header1_state(changed),
        )
    ).svg

    for expected in [
        "FIELD_EDITED_COIL",
        "DX-EDITED",
        "ROWS: 8",
        "FH 20.5 in",
        "FL 31.75 in",
        "FPI: 14",
        "CH 22 in",
        "CL 35 in",
        "CD 7.25 in",
        "TF 0.75 in",
        "BF 0.5 in",
        "RB 2.25 in",
        "HAND Right",
        "AIRFLOW right_to_left",
        "RETURN 0.875 in",
        "Edited circuiting",
        "Edited note",
    ]:
        assert expected in svg


def test_renderer_marks_blocked_scope_as_generation_blocked() -> None:
    payload = load_default_dx_header1_state().model_dump()
    payload["header_type"] = "Header 2"
    state = DxHeader1ParameterState.model_validate(payload)
    report = validate_dx_header1_state(payload)

    response = render_dx_header1_svg(
        SvgRenderRequest(state=state, validation_report=report)
    )

    assert response.metadata["drawing_status"] == "generation_blocked"
    assert "GENERATION BLOCKED - REVIEW REQUIRED" in response.svg
    assert "header_type" in response.blocked_fields


def test_renderer_draws_multi_header_arrays_as_review_surface() -> None:
    base = load_default_dx_header1_state().model_dump()
    base.update(
        {
            "source_case_id": "EZC-0011",
            "header_type": "Header 2",
            "rows": 4,
            "header_assemblies": [
                {"ID": 1, "IsSupply": True, "IsDistributor": True, "HD": 4.5, "SL": [0.0, 0.0, 0.0], "SR": 1.875, "IO": [3.0, 0.0, 0.0], "Diameter": 0.88, "ConnectionSize": [0.0, 0.0, 0.0]},
                {"ID": 2, "IsSupply": False, "IsDistributor": False, "HD": 3.5, "SL": [8.0, 0.0, 0.0], "SR": 1.125, "IO": [2.0, 0.0, 0.0], "Diameter": 1.125, "ConnectionSize": [1.125, 0.0, 0.0]},
                {"ID": 3, "IsSupply": True, "IsDistributor": True, "HD": 4.5, "SL": [0.0, 0.0, 0.0], "SR": 3.625, "IO": [3.0, 0.0, 0.0], "Diameter": 0.88, "ConnectionSize": [0.0, 0.0, 0.0]},
                {"ID": 4, "IsSupply": False, "IsDistributor": False, "HD": 3.5, "SL": [8.0, 0.0, 0.0], "SR": 3.75, "IO": [2.0, 0.0, 0.0], "Diameter": 1.125, "ConnectionSize": [1.125, 0.0, 0.0]},
            ],
        }
    )
    state = DxHeader1ParameterState.model_validate(base)
    response = render_dx_header1_svg(
        SvgRenderRequest(state=state, validation_report=validate_dx_header1_state(state))
    )

    assert 'data-header-assembly-count="4"' in response.svg
    assert response.metadata["header_assembly_count"] == 4
    assert response.metadata["header_pair_count"] == 2
    for expected in [
        'id="header.side.1"',
        'id="header.side.4"',
        "4.50 HDx3",
        "8.00 SL4",
        "3.00 I3",
        "3.63 S3",
        "2.00 O4",
        "3.75 R4",
    ]:
        assert expected in response.svg


def test_renderer_draws_header3_suffixes_from_six_header_case() -> None:
    base = load_default_dx_header1_state().model_dump()
    base.update(
        {
            "source_case_id": "EZC-0007",
            "header_type": "Header 3",
            "rows": 5,
            "header_assemblies": [
                {"ID": 1, "IsSupply": True, "IsDistributor": True, "HD": 4.5, "SL": [0.0, 0.0, 0.0], "SR": 1.75, "IO": [3.0, 0.0, 0.0], "Diameter": 1.06, "ConnectionSize": [0.0, 0.0, 0.0]},
                {"ID": 2, "IsSupply": False, "IsDistributor": False, "HD": 3.5, "SL": [8.0, 0.0, 0.0], "SR": 1.125, "IO": [2.0, 0.0, 0.0], "Diameter": 1.125, "ConnectionSize": [1.125, 0.0, 0.0]},
                {"ID": 3, "IsSupply": True, "IsDistributor": True, "HD": 4.5, "SL": [0.0, 0.0, 0.0], "SR": 4.375, "IO": [3.0, 0.0, 0.0], "Diameter": 1.06, "ConnectionSize": [0.0, 0.0, 0.0]},
                {"ID": 4, "IsSupply": False, "IsDistributor": False, "HD": 3.5, "SL": [8.0, 0.0, 0.0], "SR": 3.75, "IO": [2.0, 0.0, 0.0], "Diameter": 1.125, "ConnectionSize": [1.125, 0.0, 0.0]},
                {"ID": 5, "IsSupply": True, "IsDistributor": True, "HD": 4.5, "SL": [0.0, 0.0, 0.0], "SR": 7.0, "IO": [3.0, 0.0, 0.0], "Diameter": 1.06, "ConnectionSize": [0.0, 0.0, 0.0]},
                {"ID": 6, "IsSupply": False, "IsDistributor": False, "HD": 3.5, "SL": [8.0, 0.0, 0.0], "SR": 6.375, "IO": [2.0, 0.0, 0.0], "Diameter": 1.125, "ConnectionSize": [1.125, 0.0, 0.0]},
            ],
        }
    )
    state = DxHeader1ParameterState.model_validate(base)
    response = render_dx_header1_svg(
        SvgRenderRequest(state=state, validation_report=validate_dx_header1_state(state))
    )

    assert 'data-header-assembly-count="6"' in response.svg
    assert response.metadata["header_assembly_count"] == 6
    assert response.metadata["header_pair_count"] == 3
    for expected in [
        'id="header.side.6"',
        "4.50 HDx5",
        "3.00 I5",
        "7.00 S5",
        "2.00 O6",
        "6.38 R6",
    ]:
        assert expected in response.svg
