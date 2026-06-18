from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from coilforge.adapters import map_ez_json_to_canonical_result
from coilforge.contracts.canonical import CanonicalCoilRecord
from coilforge.contracts.field_value import FieldValue
from coilforge.direct_coil import map_canonical_to_direct_coil_draft
from coilforge.direct_coil.draft import DirectCoilDraftField, DirectCoilDraftSummary
from coilforge.direct_coil.readiness import build_direct_coil_readiness_report
from coilforge.drawing import create_drawing_intent_from_direct_coil, resolve_drawing_parameters
from coilforge.interfaces.direct_coil import (
    DIRECT_COIL_FIELD_REGISTRY,
    DRAWING_PARAMETER_FIELD_KEYS,
    REQUIRED_DIRECT_COIL_FIELDS,
)
from coilforge.submittal.candidate import SubmittalCoilCandidate
from coilforge.submittal.to_canonical import map_submittal_candidate_to_canonical_result
from coilforge.workflows.submittal_to_drawing import DEFAULT_PREVIEW_VALUES
from coilforge.validation import CANONICAL_DIRECT_COIL_FIELD_MAP


CompatibilityCategory = Literal[
    "exact_match",
    "submittal_only",
    "ez_only",
    "value_mismatch",
    "unit_mismatch",
    "status_mismatch",
    "evidence_mismatch",
    "blocked_mismatch",
]

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
    group: str
    status: CompatibilityStatus
    category: CompatibilityCategory
    submittal_value: Any
    ez_value: Any
    submittal_unit: str | None
    ez_unit: str | None
    submittal_status: str | None
    ez_status: str | None
    submittal_evidence_ids: tuple[str, ...]
    ez_evidence_ids: tuple[str, ...]
    required_direct_coil_field: bool
    drawing_impacting_field: bool
    review_required: bool
    note: str


@dataclass(frozen=True)
class CompatibilitySourceSummary:
    canonical_record_id: str
    validation_status: str
    review_required_count: int
    blocked_count: int
    unmapped_count: int
    canonical_summary: dict[str, Any]
    draft_summary: DirectCoilDraftSummary
    readiness_counts: dict[str, int]
    drawing_intent_summary: dict[str, Any] | None


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
    category_counts: dict[str, int]
    categories_by_field: dict[str, str]
    required_field_issues: tuple[str, ...]
    drawing_impacting_issues: tuple[str, ...]
    drawing_intent_comparison: dict[str, Any]
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
    submittal_draft = map_canonical_to_direct_coil_draft(submittal_result.record)
    ez_draft = map_canonical_to_direct_coil_draft(ez_result.record)
    comparisons = tuple(
        _compare_field(
            field_key,
            canonical_path,
            submittal_result.record,
            ez_result.record,
            submittal_draft.fields[field_key],
            ez_draft.fields[field_key],
        )
        for field_key, canonical_path in CANONICAL_DIRECT_COIL_FIELD_MAP.items()
    )
    status_groups = _group_statuses(comparisons)
    category_counts = _category_counts(comparisons)
    required_field_issues = tuple(
        comparison.field_key
        for comparison in comparisons
        if comparison.required_direct_coil_field and comparison.category != "exact_match"
    )
    drawing_impacting_issues = tuple(
        comparison.field_key
        for comparison in comparisons
        if comparison.drawing_impacting_field and comparison.category != "exact_match"
    )
    review_status = (
        "mismatch_review_required"
        if any(
            category_counts[category]
            for category in (
                "value_mismatch",
                "unit_mismatch",
                "blocked_mismatch",
            )
        )
        else "compatibility_review_required"
    )
    return CompatibilityRegressionReport(
        case_id=case_id or _case_id(candidate, ez_payload),
        submittal=_source_summary(submittal_result.record, submittal_draft),
        ez=_source_summary(ez_result.record, ez_draft),
        comparisons=comparisons,
        matching_field_keys=tuple(status_groups["match"]),
        mismatch_field_keys=tuple(status_groups["mismatch"]),
        submittal_only_field_keys=tuple(status_groups["submittal_only"]),
        ez_only_field_keys=tuple(status_groups["ez_only"]),
        missing_both_field_keys=tuple(status_groups["missing_both"]),
        category_counts=category_counts,
        categories_by_field={
            comparison.field_key: comparison.category for comparison in comparisons
        },
        required_field_issues=required_field_issues,
        drawing_impacting_issues=drawing_impacting_issues,
        drawing_intent_comparison=_drawing_intent_comparison(
            _drawing_intent_summary(submittal_draft),
            _drawing_intent_summary(ez_draft),
        ),
        export_allowed=False,
        review_status=review_status,
    )


def _compare_field(
    field_key: str,
    canonical_path: str,
    submittal_record: CanonicalCoilRecord,
    ez_record: CanonicalCoilRecord,
    submittal_draft_field: DirectCoilDraftField,
    ez_draft_field: DirectCoilDraftField,
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

    category = _comparison_category(
        submittal_value,
        ez_value,
        submittal_draft_field,
        ez_draft_field,
        status,
    )
    return CompatibilityComparison(
        field_key=field_key,
        canonical_path=canonical_path,
        group=DIRECT_COIL_FIELD_REGISTRY[field_key].group,
        status=status,
        category=category,
        submittal_value=submittal_value.value if submittal_value else None,
        ez_value=ez_value.value if ez_value else None,
        submittal_unit=submittal_value.unit if submittal_value else None,
        ez_unit=ez_value.unit if ez_value else None,
        submittal_status=_combined_status(submittal_value, submittal_draft_field),
        ez_status=_combined_status(ez_value, ez_draft_field),
        submittal_evidence_ids=_evidence_ids(submittal_value, submittal_draft_field),
        ez_evidence_ids=_evidence_ids(ez_value, ez_draft_field),
        required_direct_coil_field=field_key in REQUIRED_DIRECT_COIL_FIELDS,
        drawing_impacting_field=_is_drawing_impacting_field(field_key),
        review_required=_review_required(submittal_value, ez_value, status, category),
        note=_comparison_note(category),
    )


def _source_summary(
    record: CanonicalCoilRecord,
    draft,
) -> CompatibilitySourceSummary:
    readiness = build_direct_coil_readiness_report(draft)
    return CompatibilitySourceSummary(
        canonical_record_id=record.record_id,
        validation_status=record.validation_status,
        review_required_count=len(record.review_required_fields),
        blocked_count=len(record.blocked_fields),
        unmapped_count=len(record.unmapped_fields),
        canonical_summary={
            "validation_status": record.validation_status,
            "review_required_fields": list(record.review_required_fields),
            "blocked_fields": list(record.blocked_fields),
            "unmapped_field_count": len(record.unmapped_fields),
        },
        draft_summary=draft.summary,
        readiness_counts=dict(readiness.summary_counts),
        drawing_intent_summary=_drawing_intent_summary(draft),
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


def _category_counts(
    comparisons: tuple[CompatibilityComparison, ...],
) -> dict[str, int]:
    categories = {
        "exact_match": 0,
        "submittal_only": 0,
        "ez_only": 0,
        "value_mismatch": 0,
        "unit_mismatch": 0,
        "status_mismatch": 0,
        "evidence_mismatch": 0,
        "blocked_mismatch": 0,
    }
    for comparison in comparisons:
        categories[comparison.category] += 1
    return categories


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
    category: CompatibilityCategory,
) -> bool:
    if status != "match" or category != "exact_match":
        return True
    return bool(
        (submittal_value and submittal_value.review_required)
        or (ez_value and ez_value.review_required)
    )


def _comparison_category(
    submittal_value: FieldValue | None,
    ez_value: FieldValue | None,
    submittal_draft_field: DirectCoilDraftField,
    ez_draft_field: DirectCoilDraftField,
    status: CompatibilityStatus,
) -> CompatibilityCategory:
    if status == "submittal_only":
        return "submittal_only"
    if status == "ez_only":
        return "ez_only"
    if status == "missing_both":
        return "status_mismatch"
    if submittal_value is None or ez_value is None:
        return "status_mismatch"
    if submittal_value.unit != ez_value.unit:
        return "unit_mismatch"
    if _blocked_mismatch(submittal_value, ez_value, submittal_draft_field, ez_draft_field):
        return "blocked_mismatch"
    if submittal_value.value != ez_value.value:
        return "value_mismatch"
    if _combined_status(submittal_value, submittal_draft_field) != _combined_status(
        ez_value,
        ez_draft_field,
    ):
        return "status_mismatch"
    if _evidence_presence(submittal_value, submittal_draft_field) != _evidence_presence(
        ez_value,
        ez_draft_field,
    ):
        return "evidence_mismatch"
    return "exact_match"


def _blocked_mismatch(
    submittal_value: FieldValue,
    ez_value: FieldValue,
    submittal_draft_field: DirectCoilDraftField,
    ez_draft_field: DirectCoilDraftField,
) -> bool:
    submittal_blocked = (
        submittal_value.status == "blocked" or submittal_draft_field.status == "blocked"
    )
    ez_blocked = ez_value.status == "blocked" or ez_draft_field.status == "blocked"
    return submittal_blocked != ez_blocked


def _combined_status(
    field_value: FieldValue | None,
    draft_field: DirectCoilDraftField,
) -> str | None:
    if field_value is None:
        return None
    return f"canonical:{field_value.status}|draft:{draft_field.status}"


def _evidence_ids(
    field_value: FieldValue | None,
    draft_field: DirectCoilDraftField,
) -> tuple[str, ...]:
    evidence = []
    if field_value is not None:
        evidence.extend(item.evidence_id for item in field_value.source_evidence)
    evidence.extend(item.evidence_id for item in draft_field.source_evidence)
    return tuple(sorted(set(evidence)))


def _evidence_presence(
    field_value: FieldValue | None,
    draft_field: DirectCoilDraftField,
) -> bool:
    return bool(_evidence_ids(field_value, draft_field))


def _is_drawing_impacting_field(field_key: str) -> bool:
    return field_key in DRAWING_PARAMETER_FIELD_KEYS or field_key in {
        "header_type",
        "airflow_direction",
        "finned_height",
        "finned_length",
        "rows_deep",
        "fins_per_inch",
        "tubes_high",
        "coil_hand",
        "return_connection_size",
    }


def _drawing_intent_summary(draft) -> dict[str, Any] | None:
    try:
        parameter_set = resolve_drawing_parameters(
            draft,
            default_preview_values=list(DEFAULT_PREVIEW_VALUES),
        )
        intent = create_drawing_intent_from_direct_coil(draft, parameter_set)
    except Exception as exc:  # pragma: no cover - defensive summary, not workflow control
        return {
            "available": False,
            "error": exc.__class__.__name__,
            "export_allowed": False,
        }

    return {
        "available": True,
        "review_status": intent.review_status,
        "preview_allowed": intent.preview_allowed,
        "export_allowed": intent.export_allowed,
        "blocked_reasons": list(intent.blocked_reasons),
        "drawing_parameter_count": len(intent.drawing_parameters),
        "summary_fields": {
            "header_type": intent.header_type,
            "airflow_direction": intent.airflow_direction,
            "finned_height": intent.finned_height,
            "finned_length": intent.finned_length,
            "rows_deep": intent.rows_deep,
            "fins_per_inch": intent.fins_per_inch,
            "coil_hand": intent.coil_hand,
            "return_connection_size": intent.return_connection_size,
        },
    }


def _drawing_intent_comparison(
    submittal_summary: dict[str, Any] | None,
    ez_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    if submittal_summary is None or ez_summary is None:
        return {
            "available": False,
            "matching_summary_fields": [],
            "mismatched_summary_fields": [],
            "export_allowed": False,
        }
    submittal_fields = submittal_summary.get("summary_fields") or {}
    ez_fields = ez_summary.get("summary_fields") or {}
    field_keys = sorted(set(submittal_fields) | set(ez_fields))
    matching = [
        key for key in field_keys if submittal_fields.get(key) == ez_fields.get(key)
    ]
    mismatched = [
        key for key in field_keys if submittal_fields.get(key) != ez_fields.get(key)
    ]
    return {
        "available": bool(submittal_summary.get("available") and ez_summary.get("available")),
        "matching_summary_fields": matching,
        "mismatched_summary_fields": mismatched,
        "submittal_preview_allowed": submittal_summary.get("preview_allowed"),
        "ez_preview_allowed": ez_summary.get("preview_allowed"),
        "export_allowed": False,
    }


def _comparison_note(category: CompatibilityCategory) -> str:
    notes = {
        "exact_match": "Sanitized submittal and EZ values agree but remain review-only.",
        "submittal_only": "Only sanitized submittal path provided this value.",
        "ez_only": "Only sanitized EZ path provided this value.",
        "value_mismatch": "Sanitized submittal and EZ values differ; engineering review required.",
        "unit_mismatch": "Units differ; field is blocked unless an explicit conversion rule is approved.",
        "status_mismatch": "Source readiness statuses differ; review is required.",
        "evidence_mismatch": "Source evidence coverage differs; review is required.",
        "blocked_mismatch": "One path is blocked and the other is not; review is required.",
    }
    return notes[category]


def _case_id(candidate: SubmittalCoilCandidate, ez_payload: dict[str, Any]) -> str:
    ez_case = str(ez_payload.get("source_case_id") or "EZ")
    return f"{candidate.candidate_id}__{ez_case}"
