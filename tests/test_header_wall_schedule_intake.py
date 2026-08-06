from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.submittal.extract import extract_submittal_candidate_from_structured
from coilforge.submittal.pdf_intake import PDF_INTAKE_FIELD_RULES


def _hw_schedule_field(value: str):
    payload = {"COIL_TAG": "CDXC-1", "HEADER_WALL_SCHEDULE": value}
    candidate = extract_submittal_candidate_from_structured(
        payload, field_rules=PDF_INTAKE_FIELD_RULES
    )
    return candidate, candidate.materials_construction["header_wall_schedule"]


def test_blank_source_defaults_to_l_inferred_review_required() -> None:
    # source_field_available: false -> the dominant path. Blank defaults to "(L)",
    # tracked as inferred, and still review-required per the confidence-gate invariant.
    _candidate, fv = _hw_schedule_field("")
    assert fv.value == "(L)"
    assert fv.confidence == "inferred"
    assert fv.status == "review_required"
    assert fv.review_required is True


def test_explicit_type_l_maps_confirmed() -> None:
    _candidate, fv = _hw_schedule_field("Type L")
    assert fv.value == "(L)"
    assert fv.confidence == "confirmed"
    assert fv.review_required is True


def test_heavy_wall_maps_to_k_confirmed() -> None:
    _candidate, fv = _hw_schedule_field("Heavy Wall")
    assert fv.value == "(K)"
    assert fv.confidence == "confirmed"


def test_unknown_source_is_blocked_ambiguous() -> None:
    candidate, fv = _hw_schedule_field("Schedule 40")
    assert fv.value is None
    assert fv.status == "blocked"
    assert fv.confidence == "ambiguous"
    assert fv.blocked_reason
    assert "materials_construction.header_wall_schedule" in candidate.blocked_fields
