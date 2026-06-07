from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from coilforge.compatibility.decision_review import (
    BASELINE_DRAWING_FIELDS,
    DecisionMatrixReviewSurface,
    DecisionReviewItem,
)


ProposedDecision = Literal[
    "keep_review_required",
    "keep_blocked",
    "accept_for_review_only",
    "request_more_source_evidence",
    "request_unit_conversion_rule",
    "request_drawing_semantics_review",
    "request_manual_engineering_override",
    "mark_not_applicable",
    "defer_decision",
]

ProposedDecisionStatus = Literal[
    "pending_review",
    "proposed",
    "needs_john_review",
    "needs_engineering_review",
    "rejected",
    "deferred",
]


ALLOWED_PROPOSED_DECISIONS: tuple[ProposedDecision, ...] = (
    "keep_review_required",
    "keep_blocked",
    "accept_for_review_only",
    "request_more_source_evidence",
    "request_unit_conversion_rule",
    "request_drawing_semantics_review",
    "request_manual_engineering_override",
    "mark_not_applicable",
    "defer_decision",
)

ALLOWED_PROPOSED_DECISION_STATUSES: tuple[ProposedDecisionStatus, ...] = (
    "pending_review",
    "proposed",
    "needs_john_review",
    "needs_engineering_review",
    "rejected",
    "deferred",
)

DECISION_CAPTURE_SECTION_KEYS = (
    "exact_matches",
    "submittal_only_values",
    "ez_only_values",
    "missing_both_fields",
    "drawing_impacting_fields",
    "required_direct_coil_fields",
    "pos_supported_fields",
    "pos_needs_review_logic",
    "cd_bf_tf_ch",
)


@dataclass(frozen=True)
class DecisionCaptureItem:
    decision_id: str
    field_key: str
    direct_coil_group: str
    canonical_path: str
    comparison_category: str
    current_policy: str
    current_approval_state: str
    proposed_decision: ProposedDecision
    proposed_decision_status: ProposedDecisionStatus
    decision_owner: str
    decision_reason: str
    decision_scope: str
    drawing_impact: bool
    direct_coil_impact: str
    quote_impact: str
    source_evidence_summary: str
    created_from_phase: str
    export_allowed_after_decision: bool
    pdf_export_allowed_after_decision: bool
    direct_coil_final_export_allowed_after_decision: bool
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "field_key": self.field_key,
            "direct_coil_group": self.direct_coil_group,
            "canonical_path": self.canonical_path,
            "comparison_category": self.comparison_category,
            "current_policy": self.current_policy,
            "current_approval_state": self.current_approval_state,
            "proposed_decision": self.proposed_decision,
            "proposed_decision_status": self.proposed_decision_status,
            "decision_owner": self.decision_owner,
            "decision_reason": self.decision_reason,
            "decision_scope": self.decision_scope,
            "drawing_impact": self.drawing_impact,
            "direct_coil_impact": self.direct_coil_impact,
            "quote_impact": self.quote_impact,
            "source_evidence_summary": self.source_evidence_summary,
            "created_from_phase": self.created_from_phase,
            "export_allowed_after_decision": self.export_allowed_after_decision,
            "pdf_export_allowed_after_decision": self.pdf_export_allowed_after_decision,
            "direct_coil_final_export_allowed_after_decision": (
                self.direct_coil_final_export_allowed_after_decision
            ),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class DecisionCaptureSection:
    section_id: str
    title: str
    field_keys: tuple[str, ...]
    currently_known: str
    current_policy: str
    recommended_proposed_decision: ProposedDecision
    required_owner: str
    risk_if_skipped: str

    def to_dict(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "field_keys": list(self.field_keys),
            "currently_known": self.currently_known,
            "current_policy": self.current_policy,
            "recommended_proposed_decision": self.recommended_proposed_decision,
            "required_owner": self.required_owner,
            "risk_if_skipped": self.risk_if_skipped,
        }


@dataclass(frozen=True)
class DecisionCapturePacket:
    case_id: str
    summary: dict[str, int | bool | str]
    items: tuple[DecisionCaptureItem, ...]
    sections: dict[str, DecisionCaptureSection]
    counts_by_proposed_decision: dict[str, int]
    counts_by_proposed_decision_status: dict[str, int]
    cd_bf_tf_ch_status: dict[str, dict[str, object]]
    allowed_proposed_decisions: tuple[ProposedDecision, ...]
    allowed_proposed_decision_statuses: tuple[ProposedDecisionStatus, ...]
    export_allowed: bool
    pdf_export_enabled: bool
    direct_coil_final_export_available: bool
    raw_private_data_returned: bool
    decisions_apply_downstream: bool

    def by_field_key(self) -> dict[str, DecisionCaptureItem]:
        return {item.field_key: item for item in self.items}

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "summary": dict(self.summary),
            "items": [item.to_dict() for item in self.items],
            "sections": {
                section_id: section.to_dict()
                for section_id, section in self.sections.items()
            },
            "counts_by_proposed_decision": dict(self.counts_by_proposed_decision),
            "counts_by_proposed_decision_status": dict(
                self.counts_by_proposed_decision_status
            ),
            "cd_bf_tf_ch_status": self.cd_bf_tf_ch_status,
            "allowed_proposed_decisions": list(self.allowed_proposed_decisions),
            "allowed_proposed_decision_statuses": list(
                self.allowed_proposed_decision_statuses
            ),
            "export_allowed": self.export_allowed,
            "pdf_export_enabled": self.pdf_export_enabled,
            "direct_coil_final_export_available": (
                self.direct_coil_final_export_available
            ),
            "raw_private_data_returned": self.raw_private_data_returned,
            "decisions_apply_downstream": self.decisions_apply_downstream,
        }


def build_john_decision_capture_packet(
    review_surface: DecisionMatrixReviewSurface,
) -> DecisionCapturePacket:
    """Build disabled John/engineering decision-capture metadata from M3 review data."""

    items = tuple(_build_capture_item(item) for item in review_surface.items)
    return DecisionCapturePacket(
        case_id=review_surface.case_id,
        summary=_summary(review_surface, items),
        items=items,
        sections=_sections(review_surface, items),
        counts_by_proposed_decision=_count_by_proposed_decision(items),
        counts_by_proposed_decision_status=_count_by_proposed_decision_status(items),
        cd_bf_tf_ch_status=_baseline_field_status(items),
        allowed_proposed_decisions=ALLOWED_PROPOSED_DECISIONS,
        allowed_proposed_decision_statuses=ALLOWED_PROPOSED_DECISION_STATUSES,
        export_allowed=False,
        pdf_export_enabled=False,
        direct_coil_final_export_available=False,
        raw_private_data_returned=False,
        decisions_apply_downstream=False,
    )


def build_decision_capture_template(
    review_surface: DecisionMatrixReviewSurface,
) -> dict[str, object]:
    packet = build_john_decision_capture_packet(review_surface)
    return {
        **packet.to_dict(),
        "template_mode": "disabled_placeholder",
        "save_enabled": False,
        "engineering_approval_enabled": False,
        "production_persistence_enabled": False,
    }


def _build_capture_item(item: DecisionReviewItem) -> DecisionCaptureItem:
    proposed_decision = _proposed_decision(item)
    return DecisionCaptureItem(
        decision_id=f"phase2c-m4:{item.field_key}",
        field_key=item.field_key,
        direct_coil_group=item.direct_coil_group,
        canonical_path=item.canonical_path,
        comparison_category=item.comparison_category,
        current_policy=item.current_policy,
        current_approval_state=item.approval_state,
        proposed_decision=proposed_decision,
        proposed_decision_status=_proposed_decision_status(item, proposed_decision),
        decision_owner=_decision_owner(item, proposed_decision),
        decision_reason=_decision_reason(item, proposed_decision),
        decision_scope=_decision_scope(item),
        drawing_impact=item.drawing_impact,
        direct_coil_impact=item.direct_coil_impact,
        quote_impact=item.quote_impact,
        source_evidence_summary=_source_evidence_summary(item),
        created_from_phase="Phase 2C-M3 decision review surface",
        export_allowed_after_decision=False,
        pdf_export_allowed_after_decision=False,
        direct_coil_final_export_allowed_after_decision=False,
        notes=_notes(item, proposed_decision),
    )


def _proposed_decision(item: DecisionReviewItem) -> ProposedDecision:
    if item.current_policy.startswith("blocked_requires_explicit_conversion_rule"):
        return "request_unit_conversion_rule"
    if item.approval_state == "blocked":
        return "keep_blocked"
    if item.field_key in BASELINE_DRAWING_FIELDS:
        return "request_drawing_semantics_review"
    if item.pos_logic_status == "pos_logic_needs_john_review":
        return "keep_review_required"
    if item.pos_logic_status.startswith("pos_supported"):
        return "accept_for_review_only"
    if item.comparison_category == "exact_match":
        return "accept_for_review_only"
    if item.comparison_category in {"submittal_only", "ez_only"}:
        return "request_more_source_evidence"
    if item.comparison_category == "missing_both":
        if item.drawing_impact or item.direct_coil_impact.startswith("required"):
            return "request_manual_engineering_override"
        return "defer_decision"
    if item.drawing_impact:
        return "request_drawing_semantics_review"
    return "keep_review_required"


def _proposed_decision_status(
    item: DecisionReviewItem,
    proposed_decision: ProposedDecision,
) -> ProposedDecisionStatus:
    if proposed_decision in {
        "request_unit_conversion_rule",
        "request_drawing_semantics_review",
        "request_manual_engineering_override",
    }:
        return "needs_engineering_review"
    if proposed_decision in {"request_more_source_evidence", "keep_review_required"}:
        return "needs_john_review"
    if proposed_decision == "keep_blocked":
        return "pending_review"
    if proposed_decision == "defer_decision":
        return "deferred"
    if item.comparison_category == "exact_match":
        return "proposed"
    return "pending_review"


def _decision_owner(
    item: DecisionReviewItem,
    proposed_decision: ProposedDecision,
) -> str:
    if proposed_decision in {
        "request_unit_conversion_rule",
        "request_drawing_semantics_review",
        "request_manual_engineering_override",
    }:
        return "engineering"
    if item.required_owner == "john_or_engineering":
        return "john_or_engineering"
    return item.required_owner


def _decision_reason(
    item: DecisionReviewItem,
    proposed_decision: ProposedDecision,
) -> str:
    reasons = {
        "keep_review_required": "Keep the field visible for John review; no downstream use.",
        "keep_blocked": "Keep the field blocked until the blocking condition is resolved.",
        "accept_for_review_only": (
            "Allow John/engineering to treat this as a review candidate only."
        ),
        "request_more_source_evidence": (
            "The current source coverage is one-sided or insufficient."
        ),
        "request_unit_conversion_rule": (
            "A unit conversion rule must be explicitly approved before use."
        ),
        "request_drawing_semantics_review": (
            "The field can affect drawing meaning and needs engineering review."
        ),
        "request_manual_engineering_override": (
            "A missing required or drawing field needs a manual engineering decision."
        ),
        "mark_not_applicable": "Reserved for a future explicit not-applicable decision.",
        "defer_decision": "Optional unmapped field can remain deferred for this phase.",
    }
    return f"{reasons[proposed_decision]} current_policy={item.current_policy}"


def _decision_scope(item: DecisionReviewItem) -> str:
    if item.pos_logic_status.startswith("pos_supported"):
        return "recommended_for_rule_review_not_ready"
    if item.pos_logic_status == "pos_logic_needs_john_review":
        return "po_logic_review_signal_only"
    if item.field_key in BASELINE_DRAWING_FIELDS:
        return "drawing_baseline_review_only"
    if item.drawing_impact:
        return "drawing_semantics_review_only"
    return "field_review_only"


def _source_evidence_summary(item: DecisionReviewItem) -> str:
    return (
        f"submittal_status={item.submittal_status}; "
        f"ez_status={item.ez_status}; raw_text_excluded=true"
    )


def _notes(
    item: DecisionReviewItem,
    proposed_decision: ProposedDecision,
) -> tuple[str, ...]:
    notes = [
        "Captured decision is proposed/pending only.",
        "Captured decision does not enable export, PDF export, or final Direct Coil export.",
    ]
    if item.comparison_category == "exact_match":
        notes.append("Exact match remains not engineering approved.")
    if item.comparison_category in {"submittal_only", "ez_only"}:
        notes.append("Source-only value remains review required.")
    if item.field_key in BASELINE_DRAWING_FIELDS:
        notes.append("CD/BF/TF/CH baseline drawing value remains review required or blocked.")
    if item.pos_logic_status.startswith("pos_supported"):
        notes.append("POs-supported logic is recommended for rule review, not ready.")
    if proposed_decision == "request_unit_conversion_rule":
        notes.append("Unit conversion remains blocked until a future rule is approved.")
    return tuple(notes)


def _summary(
    review_surface: DecisionMatrixReviewSurface,
    items: tuple[DecisionCaptureItem, ...],
) -> dict[str, int | bool | str]:
    counts = dict(review_surface.field_category_counts)
    return {
        "case_id": review_surface.case_id,
        "total_decision_items": len(items),
        "decision_packet_status": "disabled_review_outcome_capture_only",
        "sections": len(DECISION_CAPTURE_SECTION_KEYS),
        "exact_match": int(counts.get("exact_match", 0)),
        "submittal_only": int(counts.get("submittal_only", 0)),
        "ez_only": int(counts.get("ez_only", 0)),
        "missing_both": int(counts.get("missing_both", 0)),
        "drawing_impacting": int(counts.get("drawing_impacting", 0)),
        "required_direct_coil": int(counts.get("required_direct_coil", 0)),
        "pos_supported": int(counts.get("pos_supported", 0)),
        "pos_needs_john_review": int(counts.get("pos_needs_john_review", 0)),
        "export_allowed": False,
        "pdf_export_enabled": False,
        "direct_coil_final_export_available": False,
        "decisions_apply_downstream": False,
    }


def _sections(
    review_surface: DecisionMatrixReviewSurface,
    items: tuple[DecisionCaptureItem, ...],
) -> dict[str, DecisionCaptureSection]:
    groups = review_surface.groups
    pos_supported = tuple(
        item.field_key for item in items if item.decision_scope == "recommended_for_rule_review_not_ready"
    )
    pos_needs_review = tuple(
        item.field_key for item in items if item.decision_scope == "po_logic_review_signal_only"
    )
    baseline_fields = tuple(
        field_key for field_key in BASELINE_DRAWING_FIELDS if field_key in review_surface.by_field_key()
    )

    return {
        "exact_matches": DecisionCaptureSection(
            section_id="exact_matches",
            title="Exact matches",
            field_keys=tuple(groups["exact_match"]),
            currently_known="Both sanitized paths provide matching normalized values.",
            current_policy="confirmed_for_review_not_engineering_approved",
            recommended_proposed_decision="accept_for_review_only",
            required_owner="john_or_engineering",
            risk_if_skipped="Exact matches may be mistaken for engineering approval.",
        ),
        "submittal_only_values": DecisionCaptureSection(
            section_id="submittal_only_values",
            title="Submittal-only values",
            field_keys=tuple(groups["submittal_only"]),
            currently_known="Only the sanitized submittal path has a visible value.",
            current_policy="review_required_source_only",
            recommended_proposed_decision="request_more_source_evidence",
            required_owner="john_or_engineering",
            risk_if_skipped="A one-sided source value could be used without review.",
        ),
        "ez_only_values": DecisionCaptureSection(
            section_id="ez_only_values",
            title="EZ-only values",
            field_keys=tuple(groups["ez_only"]),
            currently_known="Only the sanitized EZ reference path has a visible value.",
            current_policy="review_required_source_only",
            recommended_proposed_decision="request_more_source_evidence",
            required_owner="john_or_engineering",
            risk_if_skipped="Legacy reference values could be treated as confirmed logic.",
        ),
        "missing_both_fields": DecisionCaptureSection(
            section_id="missing_both_fields",
            title="Missing-both fields",
            field_keys=tuple(groups["missing_both"]),
            currently_known="Neither sanitized path provides a mapped value.",
            current_policy="review_required_missing_both",
            recommended_proposed_decision="defer_decision",
            required_owner="john",
            risk_if_skipped="Unmapped fields could disappear from John review.",
        ),
        "drawing_impacting_fields": DecisionCaptureSection(
            section_id="drawing_impacting_fields",
            title="Drawing-impacting fields",
            field_keys=tuple(groups["drawing_impacting"]),
            currently_known="These fields can affect drawing interpretation or geometry.",
            current_policy="needs_john_review_or_review_required",
            recommended_proposed_decision="request_drawing_semantics_review",
            required_owner="john_or_engineering",
            risk_if_skipped="Drawing semantics could be implied without approval.",
        ),
        "required_direct_coil_fields": DecisionCaptureSection(
            section_id="required_direct_coil_fields",
            title="Required Direct Coil fields",
            field_keys=tuple(groups["required_direct_coil"]),
            currently_known="These fields are required by the Direct Coil draft contract.",
            current_policy="review_required_before_final_input",
            recommended_proposed_decision="request_manual_engineering_override",
            required_owner="john_or_engineering",
            risk_if_skipped="Required inputs may remain unresolved for future final export.",
        ),
        "pos_supported_fields": DecisionCaptureSection(
            section_id="pos_supported_fields",
            title="POs-supported fields",
            field_keys=pos_supported,
            currently_known="Safe PO logic can support later rule review metadata only.",
            current_policy="recommended_for_rule_review_not_ready",
            recommended_proposed_decision="accept_for_review_only",
            required_owner="john",
            risk_if_skipped="PO logic support may be over-read as production readiness.",
        ),
        "pos_needs_review_logic": DecisionCaptureSection(
            section_id="pos_needs_review_logic",
            title="POs-needs-review logic",
            field_keys=pos_needs_review,
            currently_known="POs/BOM logic may be useful as quote metadata only.",
            current_policy="po_logic_review_signal_only",
            recommended_proposed_decision="keep_review_required",
            required_owner="john",
            risk_if_skipped="Quote/BOM signals could be mixed with drawing semantics.",
        ),
        "cd_bf_tf_ch": DecisionCaptureSection(
            section_id="cd_bf_tf_ch",
            title="CD/BF/TF/CH",
            field_keys=baseline_fields,
            currently_known="Baseline drawing fields are EZ-only in the M3 review surface.",
            current_policy="review_required_or_blocked_not_downstream_approved",
            recommended_proposed_decision="request_drawing_semantics_review",
            required_owner="engineering",
            risk_if_skipped="Baseline drawing dimensions may be treated as approved output.",
        ),
    }


def _count_by_proposed_decision(
    items: tuple[DecisionCaptureItem, ...],
) -> dict[str, int]:
    counts = {decision: 0 for decision in ALLOWED_PROPOSED_DECISIONS}
    for item in items:
        counts[item.proposed_decision] += 1
    return counts


def _count_by_proposed_decision_status(
    items: tuple[DecisionCaptureItem, ...],
) -> dict[str, int]:
    counts = {status: 0 for status in ALLOWED_PROPOSED_DECISION_STATUSES}
    for item in items:
        counts[item.proposed_decision_status] += 1
    return counts


def _baseline_field_status(
    items: tuple[DecisionCaptureItem, ...],
) -> dict[str, dict[str, object]]:
    by_field = {item.field_key: item for item in items}
    return {
        field_key: {
            "comparison_category": item.comparison_category,
            "current_policy": item.current_policy,
            "current_approval_state": item.current_approval_state,
            "proposed_decision": item.proposed_decision,
            "proposed_decision_status": item.proposed_decision_status,
            "drawing_impact": item.drawing_impact,
            "export_allowed_after_decision": item.export_allowed_after_decision,
        }
        for field_key in BASELINE_DRAWING_FIELDS
        if (item := by_field.get(field_key)) is not None
    }
