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
