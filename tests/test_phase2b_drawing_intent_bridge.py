from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.direct_coil import map_canonical_to_direct_coil_draft
from coilforge.drawing import (
    PreviewDefaultValue,
    create_drawing_intent_from_direct_coil,
    render_direct_coil_svg_preview,
    resolve_drawing_parameters,
)
from coilforge.drawing.parameters import DrawingParameter
from coilforge.phase2a.drawing_populator import build_phase2a_state_from_drawing_intent
from coilforge.submittal import SubmittalCoilCandidate, load_submittal_candidate_fixture
from coilforge.submittal.to_canonical import map_submittal_candidate_to_canonical


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "submittal_candidate_dx_header1_default.json"
)


def test_direct_coil_input_draft_can_create_drawing_intent() -> None:
    draft = _build_draft_from_payload()
    parameter_set = resolve_drawing_parameters(draft, default_preview_values=_preview_defaults())

    intent = create_drawing_intent_from_direct_coil(
        draft,
        parameter_set,
        title_block={"coil_name": "SANITIZED DRAWING PREVIEW"},
    )

    assert intent.coil_name == "SANITIZED DRAWING PREVIEW"
    assert intent.header_type == "Header 1"
    assert intent.finned_height == 12.0
    assert intent.finned_length == 15.0
    assert intent.rows_deep == 4
    assert intent.preview_allowed is True


def test_drawing_intent_preserves_source_evidence_summary() -> None:
    draft = _build_draft_from_payload()
    parameter_set = resolve_drawing_parameters(draft, default_preview_values=_preview_defaults())

    intent = create_drawing_intent_from_direct_coil(draft, parameter_set)

    assert intent.source_evidence_summary["finned_height"] == ["EV-GEOM-FH-001"]
    assert intent.source_evidence_summary["header_type"] == ["EV-HEADER-001"]


def test_missing_required_drawing_params_blocks_preview_without_defaults() -> None:
    draft = _build_draft_from_payload()
    parameter_set = resolve_drawing_parameters(draft)

    preview = render_direct_coil_svg_preview(draft, parameter_set)

    assert preview.intent.preview_allowed is False
    assert preview.svg == ""
    assert preview.metadata["drawing_status"] == "preview_blocked"
    assert {"CD", "BF", "TF", "CH"}.issubset(set(preview.blocked_fields))


def test_finned_height_change_affects_svg_preview() -> None:
    base = render_direct_coil_svg_preview(
        _build_draft_from_payload(),
        resolve_drawing_parameters(_build_draft_from_payload(), default_preview_values=_preview_defaults()),
    )
    changed_draft = _build_draft_from_payload(
        geometry_updates={"finned_height": {"value": 14.0, "source_value": 14.0, "normalized_value": 14.0}}
    )
    changed = render_direct_coil_svg_preview(
        changed_draft,
        resolve_drawing_parameters(changed_draft, default_preview_values=_preview_defaults()),
    )

    assert base.svg != changed.svg
    assert "FH 14 in" in changed.svg


def test_finned_length_change_affects_svg_preview() -> None:
    base = render_direct_coil_svg_preview(
        _build_draft_from_payload(),
        resolve_drawing_parameters(_build_draft_from_payload(), default_preview_values=_preview_defaults()),
    )
    changed_draft = _build_draft_from_payload(
        geometry_updates={"finned_length": {"value": 18.0, "source_value": 18.0, "normalized_value": 18.0}}
    )
    changed = render_direct_coil_svg_preview(
        changed_draft,
        resolve_drawing_parameters(changed_draft, default_preview_values=_preview_defaults()),
    )

    assert base.svg != changed.svg
    assert "FL 18 in" in changed.svg


def test_coil_name_change_affects_title_block() -> None:
    draft = _build_draft_from_payload()
    parameter_set = resolve_drawing_parameters(draft, default_preview_values=_preview_defaults())

    first = render_direct_coil_svg_preview(
        draft,
        parameter_set,
        title_block={"coil_name": "PREVIEW COIL A"},
    )
    second = render_direct_coil_svg_preview(
        draft,
        parameter_set,
        title_block={"coil_name": "PREVIEW COIL B"},
    )

    assert "PREVIEW COIL A" in first.svg
    assert "PREVIEW COIL B" in second.svg
    assert first.svg != second.svg


def test_review_watermark_remains_visible() -> None:
    draft = _build_draft_from_payload()
    parameter_set = resolve_drawing_parameters(draft, default_preview_values=_preview_defaults())

    preview = render_direct_coil_svg_preview(draft, parameter_set)

    assert "REVIEW AID - NOT FOR MANUFACTURING" in preview.svg
    assert preview.metadata["release_status"] == "review_aid_only"


def test_export_allowed_remains_false() -> None:
    draft = _build_draft_from_payload()
    parameter_set = resolve_drawing_parameters(draft, default_preview_values=_preview_defaults())

    preview = render_direct_coil_svg_preview(draft, parameter_set)

    assert preview.intent.export_allowed is False
    assert preview.metadata["export_allowed"] is False


def test_unsupported_header_type_blocks_preview() -> None:
    draft = _build_draft_from_payload(header_type="Header 2")
    parameter_set = resolve_drawing_parameters(draft, default_preview_values=_preview_defaults())

    preview = render_direct_coil_svg_preview(draft, parameter_set)

    assert preview.intent.preview_allowed is False
    assert "header_type" in preview.intent.blocked_reasons
    assert preview.svg == ""


def test_unparseable_numeric_field_gates_preview_without_crashing() -> None:
    """A submittal cell PDF text extraction concatenated into a numeric field
    ("24 WB (F) 75 DB (F): 55") must gate the preview as review-required, not
    crash the whole PDF analysis with a float() ValueError."""
    bad = "24 WB (F) 75 DB (F): 55"
    draft = _build_draft_from_payload(
        geometry_updates={
            "finned_height": {"value": bad, "source_value": bad, "normalized_value": bad}
        }
    )
    parameter_set = resolve_drawing_parameters(draft, default_preview_values=_preview_defaults())

    # Must not raise.
    preview = render_direct_coil_svg_preview(draft, parameter_set)

    assert preview.intent.preview_allowed is False
    assert "finned_height" in preview.intent.blocked_reasons
    assert preview.svg == ""


def test_drawing_follows_parameters_not_title_block() -> None:
    """The Drawing Parameters set is the single source of truth: when title_block
    carries different positional/header dims, the rendered state must use the
    parameter values (and distributor HD must come from HDx1, not HD)."""
    draft = _build_draft_from_payload()
    parameter_set = resolve_drawing_parameters(
        draft, default_preview_values=_full_preview_defaults()
    )
    # HDx1 (distributor HD) is an extra drawing-output param, injected as the
    # workflow does; give it a value distinct from HD (the return header).
    parameter_set.parameters["HDx1"] = DrawingParameter(
        key="HDx1",
        label="HDx1",
        value=4.5,
        unit="in",
        mode="default",
        status="review_required",
        review_required=True,
    )

    # Stale title_block values that must NOT win.
    title_block = {
        "coil_name": "PARAM PRECEDENCE",
        "return_header_diameter": 9.9,
        "distributor_header_diameter": 9.9,
        "return_stub_length": 9.9,
        "supply_offset_i1": 9.9,
        "supply_spacing_s1": 9.9,
        "return_offset_o2": 9.9,
        "return_spacing_r2": 9.9,
        "header_face": 9.9,
        "return_face": 9.9,
    }
    intent = create_drawing_intent_from_direct_coil(
        draft, parameter_set, title_block=title_block
    )
    state = build_phase2a_state_from_drawing_intent(intent)

    assert state.return_header_diameter == 3.5  # param HD
    assert state.distributor_header_diameter == 4.5  # param HDx1, NOT HD or 9.9
    assert state.return_stub_length == 8.0  # param SL
    assert state.supply_offset_i1 == 3.0  # param I
    assert state.supply_spacing_s1 == 2.75  # param S
    assert state.return_offset_o2 == 2.0  # param O
    assert state.return_spacing_r2 == 0.63  # param R
    assert state.header_face == 1.5  # param HF
    assert state.return_face == 1.5  # param RF
    # CD/TF/BF/CH were already param-sourced and stay aligned.
    assert state.casing_depth == 5.5
    assert state.casing_height == 13.25


def test_title_block_used_only_when_param_value_absent() -> None:
    """With no parameter value for a positional dim, title_block remains the
    fallback so existing title-block-driven drafts still render."""
    draft = _build_draft_from_payload()
    parameter_set = resolve_drawing_parameters(
        draft, default_preview_values=_preview_defaults()
    )  # no HD/SL/I/... defaults -> those params have no value

    intent = create_drawing_intent_from_direct_coil(
        draft,
        parameter_set,
        title_block={"coil_name": "FALLBACK", "return_header_diameter": 7.0},
    )
    state = build_phase2a_state_from_drawing_intent(intent)

    assert state.return_header_diameter == 7.0


def _full_preview_defaults() -> list[PreviewDefaultValue]:
    return [
        PreviewDefaultValue(key="CD", value=5.5),
        PreviewDefaultValue(key="BF", value=0.63),
        PreviewDefaultValue(key="TF", value=0.63),
        PreviewDefaultValue(key="CH", value=13.25),
        PreviewDefaultValue(key="HD", value=3.5),
        PreviewDefaultValue(key="SL", value=8.0),
        PreviewDefaultValue(key="I", value=3.0),
        PreviewDefaultValue(key="S", value=2.75),
        PreviewDefaultValue(key="O", value=2.0),
        PreviewDefaultValue(key="R", value=0.63),
        PreviewDefaultValue(key="HF", value=1.5),
        PreviewDefaultValue(key="RF", value=1.5),
    ]


def _build_draft_from_payload(
    *,
    header_type: str = "Header 1",
    geometry_updates: dict[str, dict[str, object]] | None = None,
):
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if header_type != "Header 1":
        header = dict(payload["header_type"])
        header["value"] = header_type
        header["source_evidence"] = [
            dict(item, source_value=header_type, normalized_value=header_type)
            for item in header["source_evidence"]
        ]
        payload["header_type"] = header
    for field_key, updates in (geometry_updates or {}).items():
        field = dict(payload["geometry"][field_key])
        field.update({"value": updates["value"]})
        field["source_evidence"] = [
            {
                **item,
                "source_value": updates.get("source_value", updates["value"]),
                "normalized_value": updates.get("normalized_value", updates["value"]),
            }
            for item in field["source_evidence"]
        ]
        payload["geometry"][field_key] = field
    candidate = SubmittalCoilCandidate.model_validate(payload)
    record = map_submittal_candidate_to_canonical(candidate)
    return map_canonical_to_direct_coil_draft(record)


def _preview_defaults() -> list[PreviewDefaultValue]:
    return [
        PreviewDefaultValue(key="CD", value=5.5),
        PreviewDefaultValue(key="BF", value=0.63),
        PreviewDefaultValue(key="TF", value=0.63),
        PreviewDefaultValue(key="CH", value=13.25),
    ]
