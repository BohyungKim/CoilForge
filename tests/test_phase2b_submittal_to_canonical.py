from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.submittal import SubmittalCoilCandidate, load_submittal_candidate_fixture
from coilforge.submittal.to_canonical import (
    map_submittal_candidate_to_canonical,
    map_submittal_candidate_to_canonical_result,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "submittal_candidate_dx_header1_default.json"
)


def test_sanitized_candidate_maps_to_canonical_record() -> None:
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)

    record = map_submittal_candidate_to_canonical(
        candidate,
        record_id="CCR-MAPPED-SANITIZED-001",
    )

    assert record.record_id == "CCR-MAPPED-SANITIZED-001"
    assert record.coil_identity["tag"].value == "COIL-TAG-001"
    assert record.product_type is not None
    assert record.product_type.value == "DX"
    assert record.geometry["rows_deep"].value == 4


def test_source_evidence_is_preserved() -> None:
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)

    record = map_submittal_candidate_to_canonical(candidate)

    evidence_ids = {evidence.evidence_id for evidence in record.source_evidence}
    assert "EV-TAG-001" in evidence_ids
    assert "EV-GEOM-FH-001" in evidence_ids
    assert record.geometry["finned_height"].source_evidence[0].evidence_id == "EV-GEOM-FH-001"


def test_unmapped_fields_are_preserved() -> None:
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)

    record = map_submittal_candidate_to_canonical(candidate)

    assert len(record.unmapped_fields) == 1
    assert record.unmapped_fields[0].source_key == "sanitized_extra_schedule_note"


def test_review_required_fields_remain_explicit() -> None:
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)

    record = map_submittal_candidate_to_canonical(candidate)

    assert "product_type" in record.review_required_fields
    assert "coil_type" in record.review_required_fields
    assert "header_type" in record.review_required_fields
    assert "connections.return_connection_size" in record.review_required_fields


def test_missing_required_tag_blocks() -> None:
    payload = _load_fixture_payload()
    payload["tag"] = None
    candidate = SubmittalCoilCandidate.model_validate(payload)

    result = map_submittal_candidate_to_canonical_result(candidate)

    assert "coil_identity.tag" in result.summary.blocked_fields
    assert result.summary.validation_status == "blocked"


def test_unsupported_header_type_blocks() -> None:
    payload = _load_fixture_payload()
    header = dict(payload["header_type"])
    header["value"] = "Header 2"
    header["source_evidence"] = [
        dict(item, source_value="Header 2", normalized_value="Header 2")
        for item in header["source_evidence"]
    ]
    payload["header_type"] = header
    candidate = SubmittalCoilCandidate.model_validate(payload)

    result = map_submittal_candidate_to_canonical_result(candidate)

    assert "header_type" in result.summary.blocked_fields
    assert result.summary.validation_status == "blocked"


def test_missing_required_numeric_units_block() -> None:
    payload = _load_fixture_payload()
    payload["geometry"]["finned_height"]["unit"] = None
    candidate = SubmittalCoilCandidate.model_validate(payload)

    result = map_submittal_candidate_to_canonical_result(candidate)

    assert "geometry.finned_height" in result.summary.blocked_fields
    assert result.summary.validation_status == "blocked"


def test_missing_optional_numeric_units_are_review_required() -> None:
    payload = _load_fixture_payload()
    payload["airside_conditions"]["total_air_flow_cfm"]["unit"] = None
    candidate = SubmittalCoilCandidate.model_validate(payload)

    result = map_submittal_candidate_to_canonical_result(candidate)

    assert "airside_conditions.total_air_flow_cfm" in result.summary.review_required_fields


def _load_fixture_payload() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
