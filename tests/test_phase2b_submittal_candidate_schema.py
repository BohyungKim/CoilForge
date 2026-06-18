from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.contracts import FieldValue, SourceEvidence
from coilforge.submittal import SubmittalCoilCandidate, load_submittal_candidate_fixture


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "submittal_candidate_dx_header1_default.json"
)


def test_source_evidence_can_be_created_from_sanitized_data() -> None:
    evidence = SourceEvidence(
        evidence_id="EV-TEST-001",
        source_type="submittal_pdf_candidate",
        source_id="SANITIZED-SOURCE-DOC-001",
        source_location="sanitized-page-1-row-1",
        source_page=1,
        source_key="rows_deep",
        source_value=4,
        normalized_value=4,
        unit="rows",
        confidence="confirmed",
        review_status="unreviewed",
        evidence_status="candidate",
    )

    assert evidence.source_type == "submittal_pdf_candidate"
    assert evidence.source_id == "SANITIZED-SOURCE-DOC-001"
    assert evidence.source_location == "sanitized-page-1-row-1"


def test_field_value_requires_source_evidence_for_prepopulated_values() -> None:
    with pytest.raises(ValidationError):
        FieldValue(value=4, unit="rows", confidence="confirmed", status="review_required")


def test_submittal_candidate_loads_from_sanitized_fixture() -> None:
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)

    assert candidate.candidate_id == "SCC-SANITIZED-DX-H1-001"
    assert candidate.tag is not None
    assert candidate.tag.value == "COIL-TAG-001"
    assert candidate.header_type is not None
    assert candidate.header_type.value == "Header 1"


def test_candidate_defaults_to_unreviewed_or_review_required() -> None:
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)

    assert candidate.review_status == "unreviewed"
    assert candidate.product_type is not None
    assert candidate.product_type.status == "review_required"
    assert candidate.header_type is not None
    assert candidate.header_type.review_required is True


def test_unmapped_fields_are_preserved() -> None:
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)

    assert len(candidate.unmapped_fields) == 1
    assert candidate.unmapped_fields[0].source_key == "sanitized_extra_schedule_note"
    assert candidate.unmapped_fields[0].source_value == "SANITIZED_NOTE_REQUIRES_REVIEW"


def test_missing_required_tag_can_be_blocked() -> None:
    payload = _load_fixture_payload()
    payload["tag"] = None

    candidate = SubmittalCoilCandidate.model_validate(payload)

    assert "tag" in candidate.blocked_fields


def test_unsupported_header_type_can_be_blocked() -> None:
    payload = _load_fixture_payload()
    header = dict(payload["header_type"])
    header["value"] = "Header 2"
    header["source_evidence"] = [
        dict(item, source_value="Header 2", normalized_value="Header 2")
        for item in header["source_evidence"]
    ]
    payload["header_type"] = header

    candidate = SubmittalCoilCandidate.model_validate(payload)

    assert "header_type" in candidate.blocked_fields


def test_raw_private_text_is_absent_from_sanitized_fixture() -> None:
    fixture_text = FIXTURE_PATH.read_text(encoding="utf-8").lower()
    forbidden_fragments = (
        "acme",
        "customer name",
        "project name",
        "project number",
        "case/",
        "outputs/",
        ".pdf",
        ".xlsx",
        ".xlsm",
        ".env",
    )

    for fragment in forbidden_fragments:
        assert fragment not in fixture_text


def test_source_evidence_includes_required_location_fields() -> None:
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)
    assert candidate.tag is not None
    evidence = candidate.tag.source_evidence[0]

    assert evidence.source_type
    assert evidence.source_id
    assert evidence.source_location
    assert evidence.source_page == 1


def _load_fixture_payload() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
