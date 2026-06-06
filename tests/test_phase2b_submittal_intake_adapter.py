from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.submittal import (
    SubmittalCoilCandidate,
    extract_submittal_candidate_from_structured,
    extract_submittal_candidates_from_text,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "examples" / "sanitized" / "submittal_text_dx_header1_default.txt"


def test_sanitized_input_creates_submittal_candidate() -> None:
    candidates = extract_submittal_candidates_from_text(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert len(candidates) == 1
    assert isinstance(candidates[0], SubmittalCoilCandidate)
    assert candidates[0].candidate_id == "SCC-SANITIZED-INTAKE-001"


def test_candidate_has_tag_with_source_evidence() -> None:
    candidate = _load_candidate()

    assert candidate.tag is not None
    assert candidate.tag.value == "COIL-TAG-001"
    assert candidate.tag.source_evidence
    assert candidate.tag.source_evidence[0].source_key == "COIL_TAG"
    assert candidate.tag.source_evidence[0].source_location == "sanitized-text-line-3"


def test_extracted_fields_have_evidence_and_review_status() -> None:
    candidate = _load_candidate()

    assert candidate.product_type is not None
    assert candidate.product_type.status == "review_required"
    assert candidate.product_type.source_evidence
    assert candidate.geometry["rows_deep"].value == 4
    assert candidate.geometry["rows_deep"].unit == "rows"
    assert candidate.geometry["rows_deep"].source_evidence
    assert candidate.performance["total_capacity_mbh"].confidence == "ambiguous"


def test_unknown_fields_are_preserved_as_unmapped() -> None:
    candidate = _load_candidate()

    assert len(candidate.unmapped_fields) == 1
    unmapped = candidate.unmapped_fields[0]
    assert unmapped.source_key == "SANITIZED_EXTRA_NOTE"
    assert unmapped.source_value == "SANITIZED_NOTE_REQUIRES_REVIEW"
    assert unmapped.source_evidence


def test_missing_tag_blocks_candidate() -> None:
    candidate = extract_submittal_candidate_from_structured(
        {
            "PRODUCT_TYPE": "DX",
            "COIL_TYPE": "DX_HEADER1_WORKFLOW_CANDIDATE",
            "HEADER_TYPE": "Header 1",
            "ROWS_DEEP": "4 rows",
        }
    )

    assert "tag" in candidate.blocked_fields


def test_unsupported_header_type_blocks_candidate() -> None:
    candidate = extract_submittal_candidate_from_structured(
        {
            "COIL_TAG": "COIL-TAG-001",
            "PRODUCT_TYPE": "DX",
            "COIL_TYPE": "DX_HEADER1_WORKFLOW_CANDIDATE",
            "HEADER_TYPE": "Header 2",
        }
    )

    assert candidate.header_type is not None
    assert candidate.header_type.value == "Header 2"
    assert "header_type" in candidate.blocked_fields


def test_raw_private_text_is_absent_from_fixture() -> None:
    fixture_text = FIXTURE_PATH.read_text(encoding="utf-8").lower()
    forbidden_fragments = (
        "acme",
        "customer name",
        "project name",
        "project number",
        ".pdf",
        ".xlsx",
        ".xlsm",
        ".env",
    )

    for fragment in forbidden_fragments:
        assert fragment not in fixture_text


def test_structured_input_can_infer_missing_coil_type() -> None:
    candidate = extract_submittal_candidate_from_structured(
        {
            "COIL_TAG": "COIL-TAG-001",
            "PRODUCT_TYPE": "DX",
            "HEADER_TYPE": "Header 1",
        }
    )

    assert candidate.coil_type is not None
    assert candidate.coil_type.value == "DX_HEADER1_WORKFLOW_CANDIDATE"
    assert candidate.coil_type.status == "review_required"


def _load_candidate() -> SubmittalCoilCandidate:
    return extract_submittal_candidates_from_text(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )[0]
