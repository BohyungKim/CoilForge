from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from coilforge.adapters import map_ez_json_to_canonical_result
from coilforge.contracts.canonical import CanonicalCoilRecord
from coilforge.contracts.field_value import FieldValue
from coilforge.direct_coil import map_canonical_to_direct_coil_draft
from coilforge.direct_coil.draft import DirectCoilDraftSummary
from coilforge.submittal.candidate import SubmittalCoilCandidate
from coilforge.submittal.to_canonical import map_submittal_candidate_to_canonical_result
from coilforge.validation import CANONICAL_DIRECT_COIL_FIELD_MAP


CompatibilityStatus = Literal[
    "match",
    "mismatch",
    "submittal_only",
    "ez_only",
    "missing_both",
]


@dataclass(frozen=True)
class CompatibilityComparison:
    field_key: str
    canonical_path: str
    status: CompatibilityStatus
    submittal_value: Any
    ez_value: Any
    submittal_unit: str | None
    ez_unit: str | None
    review_required: bool
    note: str


@dataclass(frozen=True)
class CompatibilitySourceSummary:
    canonical_record_id: str
    validation_status: str
    review_required_count: int
    blocked_count: int
    unmapped_count: int
    draft_summary: DirectCoilDraftSummary


@dataclass(frozen=True)
class CompatibilityRegressionReport:
    case_id: str
    submittal: CompatibilitySourceSummary
    ez: CompatibilitySourceSummary
    comparisons: tuple[CompatibilityComparison, ...]
    matching_field_keys: tuple[str, ...]
    mismatch_field_keys: tuple[str, ...]
    submittal_only_field_keys: tuple[str, ...]
    ez_only_field_keys: tuple[str, ...]
    missing_both_field_keys: tuple[str, ...]
    export_allowed: bool
    review_status: str


def compare_submittal_and_ez(
    candidate: SubmittalCoilCandidate,
    ez_payload: dict[str, Any],
    *,
    case_id: str | None = None,
) -> CompatibilityRegressionReport:
    """Compare sanitized submittal and EZ paths without approving either source."""

    submittal_result = map_submittal_candidate_to_canonical_result(candidate)
    ez_result = map_ez_json_to_canonical_result(ez_payload)
    comparisons = tuple(
        _compare_field(
            field_key,
            canonical_path,
            submittal_result.record,
            ez_result.record,
        )
        for field_key, canonical_path in CANONICAL_DIRECT_COIL_FIELD_MAP.items()
    )
    status_groups = _group_statuses(comparisons)
    review_status = (
        "mismatch_review_required"
        if status_groups["mismatch"]
        else "compatibility_review_required"
    )
    return CompatibilityRegressionReport(
        case_id=case_id or _case_id(candidate, ez_payload),
        submittal=_source_summary(submittal_result.record),
        ez=_source_summary(ez_result.record),
        comparisons=comparisons,
        matching_field_keys=tuple(status_groups["match"]),
        mismatch_field_keys=tuple(status_groups["mismatch"]),
        submittal_only_field_keys=tuple(status_groups["submittal_only"]),
        ez_only_field_keys=tuple(status_groups["ez_only"]),
        missing_both_field_keys=tuple(status_groups["missing_both"]),
        export_allowed=False,
        review_status=review_status,
    )


def _compare_field(
    field_key: str,
    canonical_path: str,
    submittal_record: CanonicalCoilRecord,
    ez_record: CanonicalCoilRecord,
) -> CompatibilityComparison:
    submittal_value = _get_record_field_value(submittal_record, canonical_path)
    ez_value = _get_record_field_value(ez_record, canonical_path)
    submittal_present = _has_value(submittal_value)
    ez_present = _has_value(ez_value)

    if submittal_present and ez_present:
        status: CompatibilityStatus = (
            "match"
            if (
                submittal_value.value == ez_value.value
                and submittal_value.unit == ez_value.unit
            )
            else "mismatch"
        )
    elif submittal_present:
        status = "submittal_only"
    elif ez_present:
        status = "ez_only"
    else:
        status = "missing_both"

    return CompatibilityComparison(
        field_key=field_key,
        canonical_path=canonical_path,
        status=status,
        submittal_value=submittal_value.value if submittal_value else None,
        ez_value=ez_value.value if ez_value else None,
        submittal_unit=submittal_value.unit if submittal_value else None,
        ez_unit=ez_value.unit if ez_value else None,
        review_required=_review_required(submittal_value, ez_value, status),
        note=_comparison_note(status),
    )


def _source_summary(record: CanonicalCoilRecord) -> CompatibilitySourceSummary:
    draft = map_canonical_to_direct_coil_draft(record)
    return CompatibilitySourceSummary(
        canonical_record_id=record.record_id,
        validation_status=record.validation_status,
        review_required_count=len(record.review_required_fields),
        blocked_count=len(record.blocked_fields),
        unmapped_count=len(record.unmapped_fields),
        draft_summary=draft.summary,
    )


def _group_statuses(
    comparisons: tuple[CompatibilityComparison, ...],
) -> dict[CompatibilityStatus, list[str]]:
    groups: dict[CompatibilityStatus, list[str]] = {
        "match": [],
        "mismatch": [],
        "submittal_only": [],
        "ez_only": [],
        "missing_both": [],
    }
    for comparison in comparisons:
        groups[comparison.status].append(comparison.field_key)
    return groups


def _get_record_field_value(
    record: CanonicalCoilRecord,
    canonical_path: str,
) -> FieldValue | None:
    if "." not in canonical_path:
        value = getattr(record, canonical_path)
        return value if isinstance(value, FieldValue) else None
    group_name, field_key = canonical_path.split(".", 1)
    group = getattr(record, group_name)
    if not isinstance(group, dict):
        return None
    value = group.get(field_key)
    return value if isinstance(value, FieldValue) else None


def _has_value(field_value: FieldValue | None) -> bool:
    return field_value is not None and field_value.value not in (None, "")


def _review_required(
    submittal_value: FieldValue | None,
    ez_value: FieldValue | None,
    status: CompatibilityStatus,
) -> bool:
    if status != "match":
        return True
    return bool(
        (submittal_value and submittal_value.review_required)
        or (ez_value and ez_value.review_required)
    )


def _comparison_note(status: CompatibilityStatus) -> str:
    notes = {
        "match": "Sanitized submittal and EZ values agree but remain review-only.",
        "mismatch": "Sanitized submittal and EZ values differ; engineering review required.",
        "submittal_only": "Only sanitized submittal path provided this value.",
        "ez_only": "Only sanitized EZ path provided this value.",
        "missing_both": "Neither sanitized path provided this value.",
    }
    return notes[status]


def _case_id(candidate: SubmittalCoilCandidate, ez_payload: dict[str, Any]) -> str:
    ez_case = str(ez_payload.get("source_case_id") or "EZ")
    return f"{candidate.candidate_id}__{ez_case}"
