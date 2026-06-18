from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from coilforge.compatibility.mapping_rules import MappingRuleRegistry
from coilforge.compatibility.regression import (
    CompatibilityComparison,
    CompatibilityRegressionReport,
    CompatibilityStatus,
)


ReconciliationAction = Literal[
    "use_matched_candidate_for_review",
    "hold_mismatch_for_review",
    "hold_source_only_for_review",
    "block_unit_mismatch",
    "block_blocked_mismatch",
    "no_mapping_rule",
]

SelectedSource = Literal["both", "submittal", "ez", "none"]
ReconciliationResultStatus = Literal["confirmed_for_review", "review_required", "blocked"]


@dataclass(frozen=True)
class ReconciliationDecision:
    field_key: str
    canonical_path: str
    compatibility_status: CompatibilityStatus
    compatibility_category: str
    mapping_approval_status: str
    selected_source: SelectedSource
    candidate_value: Any
    action: ReconciliationAction
    result_status: ReconciliationResultStatus
    downstream_allowed: bool
    review_required: bool
    source_evidence_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ReconciliationSummary:
    total_fields: int
    matched_candidates: int
    mismatches_held: int
    source_only_held: int
    blocked_mismatches: int
    unmapped: int
    downstream_allowed: int
    review_required: int


@dataclass(frozen=True)
class ReconciliationPlan:
    case_id: str
    decisions: tuple[ReconciliationDecision, ...]
    summary: ReconciliationSummary
    export_allowed: bool
    policy_status: str

    def by_field_key(self) -> dict[str, ReconciliationDecision]:
        return {decision.field_key: decision for decision in self.decisions}


def build_reconciliation_plan(
    report: CompatibilityRegressionReport,
    registry: MappingRuleRegistry,
) -> ReconciliationPlan:
    """Apply review-first source reconciliation policy without mutating records."""

    registry_by_field = registry.by_field_key()
    decisions = tuple(
        _build_decision(comparison, registry_by_field[comparison.field_key])
        for comparison in report.comparisons
    )
    return ReconciliationPlan(
        case_id=report.case_id,
        decisions=decisions,
        summary=_summarize(decisions),
        export_allowed=False,
        policy_status="review_required_no_auto_merge",
    )


def _build_decision(
    comparison: CompatibilityComparison,
    mapping_rule: object,
) -> ReconciliationDecision:
    approval_status = mapping_rule.approval_status
    if comparison.category == "exact_match":
        selected_source: SelectedSource = "both"
        candidate_value = comparison.submittal_value
        action: ReconciliationAction = "use_matched_candidate_for_review"
        result_status: ReconciliationResultStatus = "confirmed_for_review"
        reason = "Sources agree; candidate may be presented for review only."
    elif comparison.category == "unit_mismatch":
        selected_source = "none"
        candidate_value = None
        action = "block_unit_mismatch"
        result_status = "blocked"
        reason = "Source units differ; explicit conversion rule is required before use."
    elif comparison.category == "blocked_mismatch":
        selected_source = "none"
        candidate_value = None
        action = "block_blocked_mismatch"
        result_status = "blocked"
        reason = "One source path is blocked; no merged value is selected."
    elif comparison.status == "mismatch":
        selected_source = "none"
        candidate_value = None
        action = "hold_mismatch_for_review"
        result_status = "review_required"
        reason = "Sources disagree; no merged value is selected."
    elif comparison.status == "match":
        selected_source = "both"
        candidate_value = comparison.submittal_value
        action = "use_matched_candidate_for_review"
        result_status = "review_required"
        reason = "Values align, but status or evidence differences still require review."
    elif comparison.status in {"submittal_only", "ez_only"}:
        selected_source = "submittal" if comparison.status == "submittal_only" else "ez"
        candidate_value = (
            comparison.submittal_value
            if comparison.status == "submittal_only"
            else comparison.ez_value
        )
        action = "hold_source_only_for_review"
        result_status = "review_required"
        reason = "Only one source provided this value; review is required before use."
    else:
        selected_source = "none"
        candidate_value = None
        action = "no_mapping_rule"
        result_status = "review_required"
        reason = "No current sanitized mapping reaches this field."

    downstream_allowed = (
        comparison.category == "exact_match"
        and approval_status != "not_mapped"
        and not comparison.review_required
    )
    return ReconciliationDecision(
        field_key=comparison.field_key,
        canonical_path=comparison.canonical_path,
        compatibility_status=comparison.status,
        compatibility_category=comparison.category,
        mapping_approval_status=approval_status,
        selected_source=selected_source,
        candidate_value=candidate_value,
        action=action,
        result_status=result_status if not downstream_allowed else "confirmed_for_review",
        downstream_allowed=downstream_allowed,
        review_required=not downstream_allowed,
        source_evidence_ids=tuple(
            sorted(set(comparison.submittal_evidence_ids + comparison.ez_evidence_ids))
        ),
        reason=reason,
    )


def _summarize(
    decisions: tuple[ReconciliationDecision, ...],
) -> ReconciliationSummary:
    return ReconciliationSummary(
        total_fields=len(decisions),
        matched_candidates=sum(
            1 for decision in decisions if decision.action == "use_matched_candidate_for_review"
        ),
        mismatches_held=sum(
            1 for decision in decisions if decision.action == "hold_mismatch_for_review"
        ),
        source_only_held=sum(
            1 for decision in decisions if decision.action == "hold_source_only_for_review"
        ),
        blocked_mismatches=sum(
            1 for decision in decisions if decision.result_status == "blocked"
        ),
        unmapped=sum(1 for decision in decisions if decision.action == "no_mapping_rule"),
        downstream_allowed=sum(1 for decision in decisions if decision.downstream_allowed),
        review_required=sum(1 for decision in decisions if decision.review_required),
    )
