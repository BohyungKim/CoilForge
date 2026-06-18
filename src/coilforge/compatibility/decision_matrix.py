from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from coilforge.compatibility.mapping_rules import (
    MappingRuleRegistry,
    build_mapping_rule_registry,
)
from coilforge.compatibility.reconciliation import (
    ReconciliationPlan,
    build_reconciliation_plan,
)
from coilforge.compatibility.regression import (
    CompatibilityComparison,
    CompatibilityRegressionReport,
)
from coilforge.interfaces.direct_coil import DIRECT_COIL_FIELD_REGISTRY


DecisionComparisonCategory = Literal[
    "exact_match",
    "submittal_only",
    "ez_only",
    "value_mismatch",
    "unit_mismatch",
    "status_mismatch",
    "evidence_mismatch",
    "blocked_mismatch",
    "missing_both",
]


@dataclass(frozen=True)
class FieldDecisionItem:
    field_key: str
    group: str
    canonical_path: str
    direct_coil_field: str
    comparison_category: DecisionComparisonCategory
    submittal_status: str
    ez_status: str
    selected_policy: str
    recommended_decision: str
    required_decision_owner: str
    drawing_impact: bool
    direct_coil_impact: str
    quote_impact: str
    source_evidence_summary: str
    raw_text_excluded: bool
    decision_tags: tuple[str, ...]
    export_allowed: bool
    pdf_export_enabled: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "field_key": self.field_key,
            "group": self.group,
            "canonical_path": self.canonical_path,
            "direct_coil_field": self.direct_coil_field,
            "comparison_category": self.comparison_category,
            "submittal_status": self.submittal_status,
            "ez_status": self.ez_status,
            "selected_policy": self.selected_policy,
            "recommended_decision": self.recommended_decision,
            "required_decision_owner": self.required_decision_owner,
            "drawing_impact": self.drawing_impact,
            "direct_coil_impact": self.direct_coil_impact,
            "quote_impact": self.quote_impact,
            "source_evidence_summary": self.source_evidence_summary,
            "raw_text_excluded": self.raw_text_excluded,
            "decision_tags": list(self.decision_tags),
            "export_allowed": self.export_allowed,
            "pdf_export_enabled": self.pdf_export_enabled,
        }


@dataclass(frozen=True)
class FieldDecisionMatrix:
    case_id: str
    items: tuple[FieldDecisionItem, ...]
    summary: dict[str, int | bool | str]
    export_allowed: bool
    pdf_export_enabled: bool
    direct_coil_final_export_available: bool
    raw_private_data_returned: bool

    def by_field_key(self) -> dict[str, FieldDecisionItem]:
        return {item.field_key: item for item in self.items}

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "items": [item.to_dict() for item in self.items],
            "summary": dict(self.summary),
            "export_allowed": self.export_allowed,
            "pdf_export_enabled": self.pdf_export_enabled,
            "direct_coil_final_export_available": self.direct_coil_final_export_available,
            "raw_private_data_returned": self.raw_private_data_returned,
        }


def build_field_decision_matrix(
    report: CompatibilityRegressionReport,
    registry: MappingRuleRegistry | None = None,
    plan: ReconciliationPlan | None = None,
) -> FieldDecisionMatrix:
    """Build a review-only John/engineering decision matrix from compatibility output."""

    active_registry = registry or build_mapping_rule_registry()
    active_plan = plan or build_reconciliation_plan(report, active_registry)
    decisions_by_field = active_plan.by_field_key()
    rules_by_field = active_registry.by_field_key()
    items = tuple(
        _build_item(
            comparison,
            decisions_by_field[comparison.field_key],
            rules_by_field[comparison.field_key].coverage,
        )
        for comparison in report.comparisons
    )
    return FieldDecisionMatrix(
        case_id=report.case_id,
        items=items,
        summary=_summary(items),
        export_allowed=False,
        pdf_export_enabled=False,
        direct_coil_final_export_available=False,
        raw_private_data_returned=False,
    )


def _build_item(
    comparison: CompatibilityComparison,
    reconciliation_decision: object,
    mapping_coverage: str,
) -> FieldDecisionItem:
    field_definition = DIRECT_COIL_FIELD_REGISTRY[comparison.field_key]
    category = _matrix_category(comparison)
    selected_policy = _selected_policy(category, comparison.drawing_impacting_field)
    recommended_decision = _recommended_decision(category, comparison.drawing_impacting_field)
    owner = _decision_owner(category, comparison.drawing_impacting_field)
    tags = _decision_tags(category, comparison.drawing_impacting_field, field_definition.required)

    return FieldDecisionItem(
        field_key=comparison.field_key,
        group=comparison.group,
        canonical_path=comparison.canonical_path,
        direct_coil_field=field_definition.label,
        comparison_category=category,
        submittal_status=comparison.submittal_status or "missing",
        ez_status=comparison.ez_status or "missing",
        selected_policy=selected_policy,
        recommended_decision=recommended_decision,
        required_decision_owner=owner,
        drawing_impact=comparison.drawing_impacting_field,
        direct_coil_impact=_direct_coil_impact(field_definition.required, mapping_coverage),
        quote_impact=_quote_impact(comparison.group),
        source_evidence_summary=_source_evidence_summary(comparison),
        raw_text_excluded=True,
        decision_tags=tags,
        export_allowed=False,
        pdf_export_enabled=False,
    )


def _matrix_category(comparison: CompatibilityComparison) -> DecisionComparisonCategory:
    if comparison.status == "missing_both":
        return "missing_both"
    return comparison.category


def _selected_policy(category: str, drawing_impacting: bool) -> str:
    if category == "exact_match":
        return "confirmed_for_review_not_engineering_approved"
    if category == "unit_mismatch":
        return "blocked_requires_explicit_conversion_rule"
    if category == "blocked_mismatch":
        return "blocked_no_merged_value"
    if category in {"submittal_only", "ez_only"}:
        return "review_required_source_only"
    if category == "missing_both":
        return "review_required_missing_both"
    if drawing_impacting:
        return "review_required_drawing_semantics"
    return "review_required_no_auto_merge"


def _recommended_decision(category: str, drawing_impacting: bool) -> str:
    if category == "exact_match" and not drawing_impacting:
        return "candidate_can_be_presented_for_review"
    if category == "exact_match" and drawing_impacting:
        return "review_drawing_semantics_before_downstream_use"
    if category == "unit_mismatch":
        return "block_until_conversion_rule_is_approved"
    if category in {"submittal_only", "ez_only"}:
        return "john_or_engineering_select_source_policy"
    if category == "missing_both":
        return "collect_or_enter_required_value_with_source_trace"
    if drawing_impacting:
        return "hold_for_drawing_impact_review"
    return "hold_for_field_level_review"


def _decision_owner(category: str, drawing_impacting: bool) -> str:
    if category == "unit_mismatch":
        return "engineering"
    if drawing_impacting:
        return "john_or_engineering"
    if category in {"exact_match", "submittal_only", "ez_only", "missing_both"}:
        return "john"
    return "john_or_engineering"


def _decision_tags(
    category: str,
    drawing_impacting: bool,
    required_direct_coil_field: bool,
) -> tuple[str, ...]:
    tags = [category]
    if drawing_impacting:
        tags.append("drawing_impacting")
    if required_direct_coil_field:
        tags.append("required_direct_coil_field")
    return tuple(tags)


def _direct_coil_impact(required: bool, mapping_coverage: str) -> str:
    if required and mapping_coverage == "unmapped":
        return "required_unmapped"
    if required:
        return "required_field_review"
    if mapping_coverage == "unmapped":
        return "optional_unmapped"
    return "optional_field_review"


def _quote_impact(group: str) -> str:
    if group in {"Airside Conditions", "Refrigerant Conditions", "Manufacturing Options"}:
        return "possible_quote_review"
    if group == "Drawing Parameters":
        return "drawing_baseline_review"
    return "not_assessed_for_quote"


def _source_evidence_summary(comparison: CompatibilityComparison) -> str:
    submittal_count = len(comparison.submittal_evidence_ids)
    ez_count = len(comparison.ez_evidence_ids)
    return (
        f"submittal_evidence_ids={submittal_count}; "
        f"ez_evidence_ids={ez_count}; raw_text_excluded=true"
    )


def _summary(items: tuple[FieldDecisionItem, ...]) -> dict[str, int | bool | str]:
    counts: dict[str, int | bool | str] = {
        "total_fields": len(items),
        "exact_match": 0,
        "submittal_only": 0,
        "ez_only": 0,
        "value_mismatch": 0,
        "unit_mismatch": 0,
        "status_mismatch": 0,
        "evidence_mismatch": 0,
        "blocked_mismatch": 0,
        "missing_both": 0,
        "drawing_impacting": 0,
        "export_allowed": False,
        "pdf_export_enabled": False,
        "policy_status": "review_required_no_export",
    }
    for item in items:
        counts[item.comparison_category] = int(counts[item.comparison_category]) + 1
        if item.drawing_impact:
            counts["drawing_impacting"] = int(counts["drawing_impacting"]) + 1
    return counts
