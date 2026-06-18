from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.adapters import (
    load_sanitized_ez_json,
    map_ez_json_to_canonical,
    map_ez_json_to_canonical_result,
)
from coilforge.direct_coil import map_canonical_to_direct_coil_draft
from coilforge.drawing import (
    create_drawing_intent_from_direct_coil,
    resolve_drawing_parameters,
)


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "sanitized"
    / "dx_header1_ezc0001_default.json"
)


def test_sanitized_ez_json_loads() -> None:
    payload = load_sanitized_ez_json(FIXTURE_PATH)

    assert payload["fixture_name"] == "sanitized_dx_header1_ezc0001_default"
    assert payload["source_case_id"] == "EZC-0001"
    assert payload["header_type"] == "Header 1"


def test_ez_json_maps_to_canonical_record() -> None:
    payload = load_sanitized_ez_json(FIXTURE_PATH)
    result = map_ez_json_to_canonical_result(payload)

    record = result.record
    assert record.record_id == "CCR-EZ-EZC-0001"
    assert record.geometry["rows_deep"].value == 4
    assert record.geometry["finned_height"].value == 12.0
    assert record.geometry["finned_length"].value == 15.0
    assert record.drawing_parameters["CD"].value == 5.5
    assert record.drawing_parameters["BF"].value == 0.63
    assert record.drawing_parameters["TF"].value == 0.63
    assert record.drawing_parameters["CH"].value == 13.25
    assert result.summary.validation_status == "review_required"


def test_source_evidence_is_preserved() -> None:
    record = map_ez_json_to_canonical(load_sanitized_ez_json(FIXTURE_PATH))

    fin_height = record.geometry["finned_height"]
    assert fin_height.source_evidence
    assert fin_height.source_evidence[0].source_type == "sanitized_ez_reference"
    assert fin_height.source_evidence[0].source_key == "fin_height"
    assert fin_height.source_evidence[0].source_value == 12.0


def test_unknown_ez_fields_are_preserved_as_unmapped() -> None:
    result = map_ez_json_to_canonical_result(load_sanitized_ez_json(FIXTURE_PATH))

    assert "fixture_name" in result.summary.unmapped_field_keys
    assert "fixture_status" in result.summary.unmapped_field_keys
    assert "circuiting_display" in result.summary.unmapped_field_keys
    assert "notes" in result.summary.unmapped_field_keys
    assert all(field.source_evidence for field in result.record.unmapped_fields)


def test_canonical_maps_to_direct_coil_input_draft() -> None:
    record = map_ez_json_to_canonical(load_sanitized_ez_json(FIXTURE_PATH))
    draft = map_canonical_to_direct_coil_draft(record)

    assert len(draft.fields) == 52
    assert draft.fields["rows_deep"].value == 4
    assert draft.fields["finned_height"].source_evidence
    assert draft.fields["CD"].value == 5.5
    assert draft.fields["header_type"].status == "review_required"
    assert draft.summary.blocked == 0


def test_drawing_intent_can_be_created_from_ez_direct_coil_draft() -> None:
    payload = load_sanitized_ez_json(FIXTURE_PATH)
    record = map_ez_json_to_canonical(payload)
    draft = map_canonical_to_direct_coil_draft(record)
    parameter_set = resolve_drawing_parameters(draft)
    intent = create_drawing_intent_from_direct_coil(
        draft,
        parameter_set,
        title_block={
            "coil_name": payload["coil_name"],
            "model_number": payload["model_number"],
            "source_case_id": payload["source_case_id"],
            "product_type": payload["coil_category"],
        },
    )

    assert parameter_set.preview_allowed is True
    assert intent.preview_allowed is True
    assert intent.export_allowed is False
    assert intent.coil_name == "SAMPLE_DX_HEADER1"
    assert intent.finned_height == 12.0


def test_unsupported_header_type_blocks_ez_path() -> None:
    payload = load_sanitized_ez_json(FIXTURE_PATH)
    payload["header_type"] = "Header 2"

    result = map_ez_json_to_canonical_result(payload)
    draft = map_canonical_to_direct_coil_draft(result.record)
    parameter_set = resolve_drawing_parameters(draft)
    intent = create_drawing_intent_from_direct_coil(draft, parameter_set)

    assert "header_type" in result.summary.blocked_fields
    assert draft.fields["header_type"].status == "blocked"
    assert intent.preview_allowed is False
    assert "header_type" in intent.blocked_reasons


def test_review_required_fields_remain_explicit() -> None:
    result = map_ez_json_to_canonical_result(load_sanitized_ez_json(FIXTURE_PATH))

    assert "product_type" in result.summary.review_required_fields
    assert "header_type" in result.summary.review_required_fields
    assert "geometry.finned_height" in result.summary.review_required_fields
    assert "drawing_parameters.CD" in result.summary.review_required_fields
