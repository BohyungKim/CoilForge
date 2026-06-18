from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from coilforge.compatibility.decision_matrix import FieldDecisionItem, FieldDecisionMatrix
from coilforge.submittal.po_logic_bridge import (
    PoLogicIntakeSummary,
    build_po_logic_intake_summary,
)


ApprovalState = Literal[
    "pending_review",
    "confirmed_for_review",
    "needs_john_review",
    "blocked",
    "not_approved",
]


REVIEW_GROUP_KEYS = (
    "exact_match",
    "submittal_only",
    "ez_only",
    "missing_both",
    "status_mismatch",
    "drawing_impacting",
    "required_direct_coil",
    "needs_john_review",
    "blocked",
)

APPROVAL_STATES: tuple[ApprovalState, ...] = (
    "pending_review",
    "confirmed_for_review",
    "needs_john_review",
    "blocked",
    "not_approved",
)

POS_SUPPORTED_FIELD_RULES = {
    "header_type": "po_component_coil_detection",
    "system_type": "po_cover_table_product_detection",
}

POS_NEEDS_REVIEW_FIELD_RULES = {
    "distributor_notes": "po_bom_linestring_decisions",
    "drain_pan_type": "po_bom_linestring_decisions",
}

BASELINE_DRAWING_FIELDS = ("CD", "BF", "TF", "CH")


@dataclass(frozen=True)
class DecisionReviewItem:
    field_key: str
    direct_coil_group: str
    canonical_path: str
    comparison_category: str
    submittal_status: str
    ez_status: str
    pos_logic_status: str
    current_policy: str
    recommended_decision: str
    required_owner: str
    drawing_impact: bool
    direct_coil_impact: str
    quote_impact: str
    approval_state: ApprovalState
    highlight_reasons: tuple[str, ...]
    raw_text_excluded: bool
    export_allowed: bool
    pdf_export_enabled: bool
    direct_coil_final_export_available: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "field_key": self.field_key,
            "direct_coil_group": self.direct_coil_group,
            "canonical_path": self.canonical_path,
            "comparison_category": self.comparison_category,
            "submittal_status": self.submittal_status,
            "ez_status": self.ez_status,
            "pos_logic_status": self.pos_logic_status,
            "current_policy": self.current_policy,
            "recommended_decision": self.recommended_decision,
            "required_owner": self.required_owner,
            "drawing_impact": self.drawing_impact,
            "direct_coil_impact": self.direct_coil_impact,
            "quote_impact": self.quote_impact,
            "approval_state": self.approval_state,
            "highlight_reasons": list(self.highlight_reasons),
            "raw_text_excluded": self.raw_text_excluded,
            "export_allowed": self.export_allowed,
            "pdf_export_enabled": self.pdf_export_enabled,
            "direct_coil_final_export_available": self.direct_coil_final_export_available,
        }


@dataclass(frozen=True)
class DecisionMatrixReviewSurface:
    case_id: str
    items: tuple[DecisionReviewItem, ...]
    groups: dict[str, tuple[str, ...]]
    field_category_counts: dict[str, int | bool | str]
    approval_state_counts: dict[str, int]
    highlighted_field_keys: tuple[str, ...]
    baseline_drawing_fields: dict[str, dict[str, object]]
    pos_logic_summary: dict[str, object]
    approval_state_policy: dict[str, str]
    export_allowed: bool
    pdf_export_enabled: bool
    direct_coil_final_export_available: bool
    raw_private_data_returned: bool

    def by_field_key(self) -> dict[str, DecisionReviewItem]:
        return {item.field_key: item for item in self.items}

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "items": [item.to_dict() for item in self.items],
            "groups": {key: list(value) for key, value in self.groups.items()},
            "field_category_counts": dict(self.field_category_counts),
            "approval_state_counts": dict(self.approval_state_counts),
            "highlighted_field_keys": list(self.highlighted_field_keys),
            "baseline_drawing_fields": self.baseline_drawing_fields,
            "pos_logic_summary": dict(self.pos_logic_summary),
            "approval_state_policy": dict(self.approval_state_policy),
            "export_allowed": self.export_allowed,
            "pdf_export_enabled": self.pdf_export_enabled,
            "direct_coil_final_export_available": self.direct_coil_final_export_available,
            "raw_private_data_returned": self.raw_private_data_returned,
        }


def build_decision_matrix_review_surface(
    matrix: FieldDecisionMatrix,
    po_logic_summary: PoLogicIntakeSummary | None = None,
) -> DecisionMatrixReviewSurface:
    """Build a John/engineering-facing review surface without approving field values."""

    active_po_summary = po_logic_summary or build_po_logic_intake_summary()
    items = tuple(_build_review_item(item, active_po_summary) for item in matrix.items)
    return DecisionMatrixReviewSurface(
        case_id=matrix.case_id,
        items=items,
        groups=_group_items(items),
        field_category_counts=_field_category_counts(items),
        approval_state_counts=_approval_state_counts(items),
        highlighted_field_keys=_highlighted_field_keys(items),
        baseline_drawing_fields=_baseline_drawing_fields(items),
        pos_logic_summary=_pos_logic_summary(items, active_po_summary),
        approval_state_policy=_approval_state_policy(),
        export_allowed=False,
        pdf_export_enabled=False,
        direct_coil_final_export_available=False,
        raw_private_data_returned=False,
    )


def _build_review_item(
    item: FieldDecisionItem,
    po_logic_summary: PoLogicIntakeSummary,
) -> DecisionReviewItem:
    approval_state = _approval_state(item)
    pos_logic_status = _pos_logic_status(item.field_key, po_logic_summary)
    highlight_reasons = _highlight_reasons(item, approval_state, pos_logic_status)

    return DecisionReviewItem(
        field_key=item.field_key,
        direct_coil_group=item.group,
        canonical_path=item.canonical_path,
        comparison_category=item.comparison_category,
        submittal_status=item.submittal_status,
        ez_status=item.ez_status,
        pos_logic_status=pos_logic_status,
        current_policy=item.selected_policy,
        recommended_decision=item.recommended_decision,
        required_owner=item.required_decision_owner,
        drawing_impact=item.drawing_impact,
        direct_coil_impact=item.direct_coil_impact,
        quote_impact=item.quote_impact,
        approval_state=approval_state,
        highlight_reasons=highlight_reasons,
        raw_text_excluded=True,
        export_allowed=False,
        pdf_export_enabled=False,
        direct_coil_final_export_available=False,
    )


def _approval_state(item: FieldDecisionItem) -> ApprovalState:
    if item.selected_policy.startswith("blocked_"):
        return "blocked"
    if item.comparison_category == "exact_match":
        return "confirmed_for_review"
    if item.comparison_category == "missing_both":
        return "pending_review"
    if item.comparison_category in {"submittal_only", "ez_only"}:
        return "needs_john_review"
    if item.selected_policy.startswith("review_required"):
        return "needs_john_review"
    return "not_approved"


def _pos_logic_status(
    field_key: str,
    po_logic_summary: PoLogicIntakeSummary,
) -> str:
    rule_ids = {rule.rule_id: rule for rule in po_logic_summary.rule_summaries}
    supported_rule_id = POS_SUPPORTED_FIELD_RULES.get(field_key)
    needs_review_rule_id = POS_NEEDS_REVIEW_FIELD_RULES.get(field_key)
    if supported_rule_id and supported_rule_id in rule_ids:
        classification = rule_ids[supported_rule_id].classification
        return f"pos_supported_{classification}"
    if needs_review_rule_id and needs_review_rule_id in rule_ids:
        return "pos_logic_needs_john_review"
    return "not_pos_supported"


def _highlight_reasons(
    item: FieldDecisionItem,
    approval_state: ApprovalState,
    pos_logic_status: str,
) -> tuple[str, ...]:
    reasons = []
    if item.field_key in BASELINE_DRAWING_FIELDS:
        reasons.append("baseline_drawing_field")
    if item.drawing_impact:
        reasons.append("drawing_impacting")
    if item.direct_coil_impact.startswith("required"):
        reasons.append("required_direct_coil")
    if pos_logic_status.startswith("pos_supported"):
        reasons.append("pos_supported")
    if pos_logic_status == "pos_logic_needs_john_review":
        reasons.append("pos_logic_needs_john_review")
    if approval_state in {"needs_john_review", "blocked"}:
        reasons.append(approval_state)
    if item.comparison_category in {"submittal_only", "ez_only"}:
        reasons.append("source_only")
    return tuple(dict.fromkeys(reasons))


def _group_items(items: tuple[DecisionReviewItem, ...]) -> dict[str, tuple[str, ...]]:
    groups: dict[str, list[str]] = {key: [] for key in REVIEW_GROUP_KEYS}
    for item in items:
        if item.comparison_category in groups:
            groups[item.comparison_category].append(item.field_key)
        if item.drawing_impact:
            groups["drawing_impacting"].append(item.field_key)
        if item.direct_coil_impact.startswith("required"):
            groups["required_direct_coil"].append(item.field_key)
        if "needs_john_review" in item.highlight_reasons:
            groups["needs_john_review"].append(item.field_key)
        if item.approval_state == "blocked":
            groups["blocked"].append(item.field_key)
    return {key: tuple(value) for key, value in groups.items()}


def _field_category_counts(
    items: tuple[DecisionReviewItem, ...],
) -> dict[str, int | bool | str]:
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
        "required_direct_coil": 0,
        "needs_john_review": 0,
        "blocked": 0,
        "pos_supported": 0,
        "pos_needs_john_review": 0,
        "export_allowed": False,
        "pdf_export_enabled": False,
        "policy_status": "review_required_no_export",
    }
    for item in items:
        counts[item.comparison_category] = int(counts[item.comparison_category]) + 1
        if item.drawing_impact:
            counts["drawing_impacting"] = int(counts["drawing_impacting"]) + 1
        if item.direct_coil_impact.startswith("required"):
            counts["required_direct_coil"] = int(counts["required_direct_coil"]) + 1
        if "needs_john_review" in item.highlight_reasons:
            counts["needs_john_review"] = int(counts["needs_john_review"]) + 1
        if item.approval_state == "blocked":
            counts["blocked"] = int(counts["blocked"]) + 1
        if item.pos_logic_status.startswith("pos_supported"):
            counts["pos_supported"] = int(counts["pos_supported"]) + 1
        if item.pos_logic_status == "pos_logic_needs_john_review":
            counts["pos_needs_john_review"] = int(counts["pos_needs_john_review"]) + 1
    return counts


def _approval_state_counts(items: tuple[DecisionReviewItem, ...]) -> dict[str, int]:
    counts = {state: 0 for state in APPROVAL_STATES}
    for item in items:
        counts[item.approval_state] += 1
    return counts


def _highlighted_field_keys(items: tuple[DecisionReviewItem, ...]) -> tuple[str, ...]:
    return tuple(item.field_key for item in items if item.highlight_reasons)


def _baseline_drawing_fields(
    items: tuple[DecisionReviewItem, ...],
) -> dict[str, dict[str, object]]:
    by_field = {item.field_key: item for item in items}
    return {
        field_key: {
            "comparison_category": by_field[field_key].comparison_category,
            "current_policy": by_field[field_key].current_policy,
            "approval_state": by_field[field_key].approval_state,
            "drawing_impact": by_field[field_key].drawing_impact,
            "submittal_status": by_field[field_key].submittal_status,
            "ez_status": by_field[field_key].ez_status,
        }
        for field_key in BASELINE_DRAWING_FIELDS
        if field_key in by_field
    }


def _pos_logic_summary(
    items: tuple[DecisionReviewItem, ...],
    po_logic_summary: PoLogicIntakeSummary,
) -> dict[str, object]:
    rules = [rule.to_dict() for rule in po_logic_summary.rule_summaries]
    return {
        "classification_counts": dict(po_logic_summary.classification_counts),
        "supported_field_keys": [
            item.field_key
            for item in items
            if item.pos_logic_status.startswith("pos_supported")
        ],
        "needs_review_field_keys": [
            item.field_key
            for item in items
            if item.pos_logic_status == "pos_logic_needs_john_review"
        ],
        "needs_review_rule_ids": [
            rule["rule_id"]
            for rule in rules
            if rule["classification"] == "needs_john_review"
        ],
        "not_found_rule_ids": [
            rule["rule_id"] for rule in rules if rule["classification"] == "not_found"
        ],
        "raw_private_source_data_read": po_logic_summary.raw_private_source_data_read,
        "export_enabled": po_logic_summary.export_enabled,
        "pdf_parsing_enabled": po_logic_summary.pdf_parsing_enabled,
    }


def _approval_state_policy() -> dict[str, str]:
    return {
        "pending_review": "Value or source coverage is not ready for approval.",
        "confirmed_for_review": (
            "May be presented to John/engineering; not engineering approved."
        ),
        "needs_john_review": "Explicit John or engineering decision is required.",
        "blocked": "No downstream use until a blocking rule or mismatch is resolved.",
        "not_approved": "No approval has been granted for downstream use.",
    }
