from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.direct_coil import map_canonical_to_direct_coil_draft
from coilforge.drawing import PreviewDefaultValue, render_direct_coil_svg_preview, resolve_drawing_parameters
from coilforge.drawing.svg_regression import (
    normalize_svg_for_regression,
    normalize_svg_metadata_for_regression,
)
from coilforge.review import build_review_packet
from coilforge.submittal import SubmittalCoilCandidate
from coilforge.submittal.to_canonical import map_submittal_candidate_to_canonical
from coilforge.workflows import (
    build_default_demo_workflow_input,
    run_submittal_to_drawing_workflow,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "submittal_candidate_dx_header1_default.json"
)


def test_svg_normalization_helper_stabilizes_whitespace_attributes_and_volatile_values() -> None:
    raw_svg = """
    <svg xmlns="http://www.w3.org/2000/svg" data-generated-at="2026-06-08T10:11:12Z" viewBox="0 0 10 10">
      <text id="title">  Coil   A  </text>
      <g data-run-id="123e4567-e89b-12d3-a456-426614174000" class="x"></g>
    </svg>
    """

    normalized = normalize_svg_for_regression(raw_svg)

    assert '<svg data-generated-at="<TIMESTAMP>" viewBox="0 0 10 10">' in normalized
    assert '<text id="title">Coil A</text>' in normalized
    assert 'data-run-id="<UUID>"' in normalized


def test_watermark_remains_visible_in_normalized_svg_and_metadata() -> None:
    preview = _preview_with_defaults()
    normalized_svg = normalize_svg_for_regression(preview.svg)
    metadata = normalize_svg_metadata_for_regression(preview.metadata)

    assert "REVIEW AID - NOT FOR MANUFACTURING" in normalized_svg
    assert metadata["release_status"] == "review_aid_only"
    assert metadata["john_review_required"] is True


def test_coil_name_change_affects_normalized_svg_or_metadata() -> None:
    first = _preview_with_defaults(title_block={"coil_name": "M2 PREVIEW COIL A"})
    second = _preview_with_defaults(title_block={"coil_name": "M2 PREVIEW COIL B"})

    assert normalize_svg_for_regression(first.svg) != normalize_svg_for_regression(second.svg)
    assert "M2 PREVIEW COIL A" in normalize_svg_for_regression(first.svg)
    assert "M2 PREVIEW COIL B" in normalize_svg_for_regression(second.svg)


def test_finned_height_change_affects_normalized_svg_or_metadata() -> None:
    base = _preview_with_defaults()
    changed = _preview_with_defaults(
        geometry_updates={
            "finned_height": {
                "value": 14.0,
                "source_value": 14.0,
                "normalized_value": 14.0,
            }
        }
    )

    assert normalize_svg_for_regression(base.svg) != normalize_svg_for_regression(changed.svg)
    assert "FH 14 in" in normalize_svg_for_regression(changed.svg)


def test_finned_length_change_affects_normalized_svg_or_metadata() -> None:
    base = _preview_with_defaults()
    changed = _preview_with_defaults(
        geometry_updates={
            "finned_length": {
                "value": 18.0,
                "source_value": 18.0,
                "normalized_value": 18.0,
            }
        }
    )

    assert normalize_svg_for_regression(base.svg) != normalize_svg_for_regression(changed.svg)
    assert "FL 18 in" in normalize_svg_for_regression(changed.svg)


def test_airflow_direction_is_present_as_current_review_preview_policy() -> None:
    preview = _preview_with_defaults()
    normalized_svg = normalize_svg_for_regression(preview.svg)

    assert "AIRFLOW left to right" in normalized_svg
    assert preview.intent.review_status == "review_required"


def test_unsupported_header_remains_blocked_with_explicit_reason() -> None:
    draft = _build_draft(header_type="Header 2")
    parameter_set = resolve_drawing_parameters(draft, default_preview_values=_preview_defaults())
    preview = render_direct_coil_svg_preview(draft, parameter_set)

    assert preview.intent.preview_allowed is False
    assert preview.svg == ""
    assert preview.metadata["drawing_status"] == "preview_blocked"
    assert "header_type" in preview.blocked_fields


def test_cd_bf_tf_ch_unresolved_status_remains_visible_in_review_packet() -> None:
    packet = _default_review_packet()

    assert set(packet.cd_bf_tf_ch_status) == {"CD", "BF", "TF", "CH"}
    assert {
        item["review_status"] for item in packet.cd_bf_tf_ch_status.values()
    } == {"review_required_or_blocked"}
    assert all(
        item["production_approved"] is False
        for item in packet.cd_bf_tf_ch_status.values()
    )


def test_export_pdf_and_direct_coil_final_export_remain_disabled() -> None:
    packet = _default_review_packet()
    preview = _preview_with_defaults()

    assert preview.intent.export_allowed is False
    assert preview.metadata["export_allowed"] is False
    assert packet.export_status.export_allowed is False
    assert packet.export_status.pdf_export_enabled is False
    assert packet.export_status.direct_coil_final_export_available is False
    assert packet.export_status.production_drawing_approval_claimed is False
    assert packet.quote_prep_status["final_quote"] is False


def test_review_packet_exposes_drawing_summary_without_raw_svg_or_final_status() -> None:
    packet = _default_review_packet()
    packet_json = json.dumps(packet.to_dict())

    assert packet.drawing_intent_summary["available"] is True
    assert packet.drawing_intent_summary["preview_allowed"] is True
    assert packet.drawing_intent_summary["export_allowed"] is False
    assert packet.svg_metadata_summary["available"] is True
    assert packet.svg_metadata_summary["raw_svg_included"] is False
    assert packet.packet_status == "quote_prep_review_only"
    assert "<svg" not in packet_json
    assert "final_quote" in packet.quote_prep_status


def test_review_packet_exposes_drawing_related_unresolved_items() -> None:
    packet = _default_review_packet()
    unresolved = "\n".join(packet.unresolved_review_items)

    assert "CD/BF/TF/CH" in unresolved
    assert "22 drawing-impacting fields" in unresolved
    assert packet.drawing_impacting_field_summary["field_count"] == 22
    assert packet.drawing_impacting_field_summary["production_drawing_approval_claimed"] is False


def _default_review_packet():
    workflow_input = build_default_demo_workflow_input()["input"]
    workflow_output = run_submittal_to_drawing_workflow(workflow_input)
    return build_review_packet(workflow_output)


def _preview_with_defaults(
    *,
    title_block: dict[str, object] | None = None,
    geometry_updates: dict[str, dict[str, object]] | None = None,
):
    draft = _build_draft(geometry_updates=geometry_updates)
    parameter_set = resolve_drawing_parameters(draft, default_preview_values=_preview_defaults())
    return render_direct_coil_svg_preview(
        draft,
        parameter_set,
        title_block=title_block or {"coil_name": "M2 DRAWING REGRESSION PREVIEW"},
    )


def _build_draft(
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
        field["value"] = updates["value"]
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
