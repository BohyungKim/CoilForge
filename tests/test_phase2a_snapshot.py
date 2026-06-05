from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.phase2a.fixtures import load_default_dx_header1_state
from coilforge.phase2a.renderer import SvgRenderRequest, render_dx_header1_svg
from coilforge.phase2a.snapshot import (
    generate_checklist_snapshot,
    generate_drawing_metadata,
)
from coilforge.phase2a.validation import validate_dx_header1_state


def test_generate_checklist_snapshot_includes_required_fields() -> None:
    state = load_default_dx_header1_state()
    report = validate_dx_header1_state(state)

    snapshot = generate_checklist_snapshot(state, report)

    assert snapshot.snapshot_id.startswith("chk_phase2a_")
    assert snapshot.snapshot_status == "draft_review_aid"
    assert snapshot.source_fixture == "sanitized_dx_header1_ezc0001_default"
    assert snapshot.state.source_case_id == "EZC-0001"
    assert snapshot.validation_status == "pass_with_warnings"
    assert snapshot.created_by == "coilforge_local_mvp"


def test_generate_drawing_metadata_preserves_review_boundary() -> None:
    state = load_default_dx_header1_state()
    report = validate_dx_header1_state(state)
    renderer_response = render_dx_header1_svg(
        SvgRenderRequest(state=state, validation_report=report)
    )

    metadata = generate_drawing_metadata(
        state,
        report,
        renderer_metadata=renderer_response.metadata,
    )

    assert metadata.drawing_generation_run_id.startswith("draw_phase2a_")
    assert metadata.drawing_status == "generated_with_warnings"
    assert metadata.release_status == "review_aid_only"
    assert metadata.template_id == "phase2a_dx_header1_review_svg"
    assert metadata.viewBox == "0 0 1600 1200"
    assert metadata.source_case_id == "EZC-0001"
    assert metadata.warnings
    assert metadata.john_review_required is True
