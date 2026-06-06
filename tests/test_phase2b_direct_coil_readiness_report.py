from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.direct_coil import map_canonical_to_direct_coil_draft
from coilforge.direct_coil.readiness import (
    DirectCoilReadinessReport,
    build_direct_coil_readiness_report,
)
from coilforge.interfaces.direct_coil import DIRECT_COIL_FIELD_REGISTRY
from coilforge.submittal import load_submittal_candidate_fixture
from coilforge.submittal.to_canonical import map_submittal_candidate_to_canonical


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "submittal_candidate_dx_header1_default.json"
)
REPORT_FIXTURE_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "direct_coil_readiness_dx_header1_default.json"
)


def test_readiness_report_includes_all_direct_coil_fields() -> None:
    report = _build_report_from_sanitized_fixture()
    reported_field_keys = _reported_field_keys(report)

    assert report.total_fields == 52
    assert len(reported_field_keys) == 52
    assert reported_field_keys == set(DIRECT_COIL_FIELD_REGISTRY)


def test_summary_counts_are_correct_for_sanitized_fixture() -> None:
    report = _build_report_from_sanitized_fixture()

    assert report.summary_counts["ready"] == 0
    assert report.summary_counts["review_required"] == 12
    assert report.summary_counts["blocked"] == 4
    assert report.summary_counts["unmapped"] == 36
    assert report.summary_counts["manual_override"] == 0


def test_blocked_fields_include_required_drawing_parameters() -> None:
    report = _build_report_from_sanitized_fixture()
    blocked_field_keys = {field.field_key for field in report.blocked_fields}

    assert {"CD", "BF", "TF", "CH"}.issubset(blocked_field_keys)
    assert report.drawing_parameter_summary.blocked_fields == ["CD", "BF", "TF", "CH"]
    assert report.drawing_parameter_summary.total == 13
    assert report.drawing_parameter_summary.blocked == 4
    assert report.drawing_parameter_summary.unmapped == 9


def test_review_required_fields_include_source_evidence_where_available() -> None:
    report = _build_report_from_sanitized_fixture()
    review_fields_by_key = {
        field.field_key: field for field in report.review_required_fields
    }

    assert review_fields_by_key["header_type"].source_evidence
    assert review_fields_by_key["header_type"].source_evidence[0].evidence_id == "EV-HEADER-001"
    assert review_fields_by_key["return_connection_size"].source_evidence
    assert (
        review_fields_by_key["return_connection_size"].source_evidence[0].evidence_id
        == "EV-CONN-RETURN-001"
    )
    assert report.source_evidence_summary.fields_with_source_evidence == 12
    assert report.source_evidence_summary.total_source_evidence_refs == 12


def test_unmapped_optional_fields_are_preserved() -> None:
    report = _build_report_from_sanitized_fixture()
    unmapped_fields_by_key = {field.field_key: field for field in report.unmapped_fields}

    assert "tube_diameter_od" in unmapped_fields_by_key
    assert unmapped_fields_by_key["tube_diameter_od"].required is False
    assert "I" in unmapped_fields_by_key
    assert unmapped_fields_by_key["I"].group == "Drawing Parameters"


def test_export_status_is_not_implemented() -> None:
    report = _build_report_from_sanitized_fixture()

    assert report.export_status == "not_implemented"


def test_sanitized_readiness_report_fixture_loads() -> None:
    report = DirectCoilReadinessReport.model_validate_json(
        REPORT_FIXTURE_PATH.read_text(encoding="utf-8")
    )

    assert report.total_fields == 52
    assert report.summary_counts["review_required"] == 12
    assert report.summary_counts["blocked"] == 4
    assert report.summary_counts["unmapped"] == 36
    assert report.export_status == "not_implemented"


def test_required_missing_fields_are_explicit() -> None:
    report = _build_report_from_sanitized_fixture()
    required_missing_keys = {field.field_key for field in report.required_missing_fields}

    assert required_missing_keys == {"CD", "BF", "TF", "CH"}
    for field in report.required_missing_fields:
        assert field.required is True
        assert field.blocked_reason == "required canonical field missing"


def _build_report_from_sanitized_fixture() -> DirectCoilReadinessReport:
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)
    record = map_submittal_candidate_to_canonical(candidate)
    draft = map_canonical_to_direct_coil_draft(record)
    return build_direct_coil_readiness_report(draft)


def _reported_field_keys(report: DirectCoilReadinessReport) -> set[str]:
    return {
        field.field_key
        for field in (
            report.ready_fields
            + report.review_required_fields
            + report.blocked_fields
            + report.unmapped_fields
        )
    }
