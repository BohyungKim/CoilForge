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
