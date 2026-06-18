from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.contracts.canonical import CanonicalCoilRecord
from coilforge.interfaces.direct_coil import REQUIRED_DIRECT_COIL_FIELDS
from coilforge.submittal import load_submittal_candidate_fixture
from coilforge.validation import (
    CANONICAL_DIRECT_COIL_FIELD_MAP,
    CANONICAL_REQUIRED_GROUPS,
    apply_canonical_validation,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "submittal_candidate_dx_header1_default.json"
)


def test_canonical_coil_record_can_be_created_from_sanitized_values() -> None:
    record = _build_canonical_record_from_sanitized_candidate()

    assert record.record_id == "CCR-SANITIZED-DX-H1-001"
    assert record.product_type is not None
    assert record.product_type.value == "DX"
    assert record.coil_identity["tag"].value == "COIL-TAG-001"
    assert record.unmapped_fields


def test_required_groups_exist() -> None:
    record = _build_canonical_record_from_sanitized_candidate()

    for group_name in CANONICAL_REQUIRED_GROUPS:
        assert hasattr(record, group_name), group_name


def test_required_direct_coil_fields_are_representable() -> None:
    missing = set(REQUIRED_DIRECT_COIL_FIELDS) - set(CANONICAL_DIRECT_COIL_FIELD_MAP)

    assert not missing
    for field_key in REQUIRED_DIRECT_COIL_FIELDS:
        assert CANONICAL_DIRECT_COIL_FIELD_MAP[field_key]


def test_missing_required_field_can_be_blocked() -> None:
    record = _build_canonical_record_from_sanitized_candidate()
    record.geometry.pop("rows_deep")

    validated = apply_canonical_validation(record)

    assert "geometry.rows_deep" in validated.blocked_fields
    assert validated.validation_status == "blocked"


def test_unsupported_header_type_can_be_blocked() -> None:
    record = _build_canonical_record_from_sanitized_candidate()
    assert record.header_type is not None
    record.header_type = record.header_type.model_copy(update={"value": "Header 2"})

    validated = apply_canonical_validation(record)

    assert "header_type" in validated.blocked_fields
    assert validated.validation_status == "blocked"


def test_unmapped_fields_are_preserved() -> None:
    record = _build_canonical_record_from_sanitized_candidate()

    assert len(record.unmapped_fields) == 1
    assert record.unmapped_fields[0].source_key == "sanitized_extra_schedule_note"


def test_source_evidence_is_attached_to_imported_values() -> None:
    record = _build_canonical_record_from_sanitized_candidate()

    assert record.geometry["finned_height"].source_evidence
    assert record.connections["return_connection_size"].source_evidence
    assert record.product_type is not None
    assert record.product_type.source_evidence


def test_review_required_fields_are_explicit() -> None:
    record = _build_canonical_record_from_sanitized_candidate()
    validated = apply_canonical_validation(record)

    assert "product_type" in validated.review_required_fields
    assert "coil_type" in validated.review_required_fields
    assert "header_type" in validated.review_required_fields
    assert "connections.return_connection_size" in validated.review_required_fields


def test_unitless_required_numeric_value_can_be_blocked() -> None:
    record = _build_canonical_record_from_sanitized_candidate()
    record.geometry["finned_height"] = record.geometry["finned_height"].model_copy(
        update={"unit": None}
    )

    validated = apply_canonical_validation(record)

    assert "geometry.finned_height" in validated.blocked_fields


def _build_canonical_record_from_sanitized_candidate() -> CanonicalCoilRecord:
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)
    assert candidate.tag is not None

    return CanonicalCoilRecord(
        record_id="CCR-SANITIZED-DX-H1-001",
        project={},
        coil_identity={"tag": candidate.tag},
        product_type=candidate.product_type,
        coil_type=candidate.coil_type,
        header_type=candidate.header_type,
        geometry=dict(candidate.geometry),
        airside_conditions=dict(candidate.airside_conditions),
        refrigerant_conditions=dict(candidate.refrigerant_conditions),
        materials_construction=dict(candidate.materials_construction),
        connections=dict(candidate.connections),
        manufacturing_options={},
        drawing_parameters=dict(candidate.drawing_parameters),
        performance=dict(candidate.performance),
        source_evidence=list(candidate.source_evidence),
        unmapped_fields=list(candidate.unmapped_fields),
        review_required_fields=list(candidate.review_required_fields),
        blocked_fields=list(candidate.blocked_fields),
        manual_overrides=[],
        validation_status="not_validated",
    )
