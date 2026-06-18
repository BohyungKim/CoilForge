from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.direct_coil import DirectCoilInputDraft, map_canonical_to_direct_coil_draft
from coilforge.interfaces.direct_coil import DIRECT_COIL_FIELD_REGISTRY
from coilforge.submittal import SubmittalCoilCandidate, load_submittal_candidate_fixture
from coilforge.submittal.to_canonical import map_submittal_candidate_to_canonical


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "submittal_candidate_dx_header1_default.json"
)


def test_direct_coil_input_draft_includes_all_registry_fields() -> None:
    draft = _build_draft_from_sanitized_candidate()

    assert isinstance(draft, DirectCoilInputDraft)
    assert len(DIRECT_COIL_FIELD_REGISTRY) == 52
    assert len(draft.fields) == 52
    assert set(draft.fields) == set(DIRECT_COIL_FIELD_REGISTRY)


def test_canonical_record_maps_to_direct_coil_draft() -> None:
    draft = _build_draft_from_sanitized_candidate()

    assert draft.fields["rows_deep"].value == 4
    assert draft.fields["rows_deep"].mapping_rule == "canonical:geometry.rows_deep"
    assert draft.fields["header_type"].value == "Header 1"
    assert draft.fields["return_connection_size"].value == 0.625


def test_source_evidence_is_preserved() -> None:
    draft = _build_draft_from_sanitized_candidate()

    assert draft.fields["finned_height"].source_evidence
    assert draft.fields["finned_height"].source_evidence[0].evidence_id == "EV-GEOM-FH-001"
    assert draft.fields["header_type"].source_evidence[0].evidence_id == "EV-HEADER-001"


def test_required_missing_fields_are_blocked() -> None:
    draft = _build_draft_from_sanitized_candidate()

    assert draft.fields["CD"].status == "blocked"
    assert draft.fields["CD"].blocked_reason == "required canonical field missing"
    assert draft.fields["BF"].status == "blocked"
    assert draft.fields["TF"].status == "blocked"
    assert draft.fields["CH"].status == "blocked"


def test_inferred_fields_are_review_required() -> None:
    draft = _build_draft_from_sanitized_candidate()

    assert draft.fields["header_type"].status == "review_required"
    assert draft.fields["airflow_direction"].status == "review_required"
    assert draft.fields["return_connection_size"].status == "review_required"


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
    record = map_submittal_candidate_to_canonical(candidate)

    draft = map_canonical_to_direct_coil_draft(record)

    assert draft.fields["header_type"].status == "blocked"
    assert draft.fields["header_type"].blocked_reason == "unsupported header_type is blocked"


def test_unit_mismatch_blocks_without_approved_rule() -> None:
    payload = _load_fixture_payload()
    payload["geometry"]["finned_height"]["unit"] = "mm"
    candidate = SubmittalCoilCandidate.model_validate(payload)
    record = map_submittal_candidate_to_canonical(candidate)

    draft = map_canonical_to_direct_coil_draft(record)

    assert draft.fields["finned_height"].status == "blocked"
    assert draft.fields["finned_height"].blocked_reason == (
        "unit mismatch without approved conversion rule"
    )


def test_summary_counts_are_correct_for_sanitized_fixture() -> None:
    draft = _build_draft_from_sanitized_candidate()

    assert draft.summary.ready == 0
    assert draft.summary.review_required == 12
    assert draft.summary.blocked == 4
    assert draft.summary.unmapped == 36
    assert draft.summary.manual_override == 0
    assert (
        draft.summary.ready
        + draft.summary.review_required
        + draft.summary.blocked
        + draft.summary.unmapped
        + draft.summary.manual_override
        == 52
    )


def test_no_final_export_method_is_implemented() -> None:
    draft = _build_draft_from_sanitized_candidate()

    assert draft.export_status == "not_implemented"
    assert not hasattr(draft, "export")
    assert not hasattr(draft, "to_direct_coil_export")


def _build_draft_from_sanitized_candidate() -> DirectCoilInputDraft:
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)
    record = map_submittal_candidate_to_canonical(candidate)
    return map_canonical_to_direct_coil_draft(record)


def _load_fixture_payload() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
