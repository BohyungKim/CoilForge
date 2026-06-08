from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from coilforge.contracts import SourceEvidence
from coilforge.submittal.candidate import SubmittalCoilCandidate
from coilforge.submittal.extract import extract_submittal_candidates_from_text
from coilforge.submittal.po_logic_bridge import (
    PoLogicIntakeSummary,
    PoLogicRuleSummary,
    build_po_logic_intake_summary,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SANITIZED_TEXT_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "submittal_text_dx_header1_default.txt"
)

PoBasedSignalStatus = Literal["review_required", "blocked", "unmapped"]

SAFE_POS_RULE_IDS = {
    "po_unit_tag_normalization",
    "po_review_before_export_gate",
    "po_cover_table_product_detection",
    "po_component_coil_detection",
}

POS_RULE_IDS_REQUIRING_REVIEW = {
    "po_bom_linestring_decisions",
}

POS_FINAL_SELECTION_RULE_IDS = {
    "po_application_team_selection",
    "po_bto_selection_workflow",
}

COMPONENT_LIKE_TAG_TOKENS = {
    "ACCESSORY",
    "ACC",
    "BOM",
    "DAMPER",
    "DMPR",
    "MOTOR",
    "PANEL",
}


class PoBasedIntakeSignal(BaseModel):
    """Review-only signal from safe summarized POs logic."""

    model_config = ConfigDict(extra="forbid")

    signal_id: str
    field_key: str
    po_rule_id: str
    classification: str
    source_value: Any = None
    normalized_value: Any = None
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    status: PoBasedSignalStatus = "review_required"
    approved_logic_applied: bool = False
    raw_text_excluded: bool = True
    notes: list[str] = Field(default_factory=list)


class PoBasedIntakeResult(BaseModel):
    """POs-aware intake result that remains on the sanitized review path."""

    model_config = ConfigDict(extra="forbid")

    intake_id: str
    candidate: SubmittalCoilCandidate
    po_logic_source_status: str
    po_logic_used: list[str]
    po_logic_not_used: list[str]
    final_selection_logic_available: bool
    fallback_used: bool
    fallback_reason: str
    signals: list[PoBasedIntakeSignal]
    review_required_fields: list[str]
    blocked_fields: list[str]
    unmapped_fields: list[str]
    source_evidence_ids: list[str]
    export_allowed: bool = False
    pdf_export_enabled: bool = False
    direct_coil_final_export_available: bool = False
    raw_private_data_read: bool = False
    raw_private_data_returned: bool = False
    raw_text_excluded: bool = True

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def normalize_po_unit_tag(value: Any) -> str:
    """Apply the Phase 2C-M2 safe unit-tag normalization summary."""

    text = "" if value is None else str(value).strip().upper()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def build_po_based_intake(
    payload: dict[str, Any] | None = None,
    *,
    po_logic_summary: PoLogicIntakeSummary | None = None,
) -> PoBasedIntakeResult:
    """Build a review-only POs-derived intake layer over sanitized submittal intake."""

    request = dict(payload or {})
    active_po_summary = po_logic_summary or build_po_logic_intake_summary()
    candidate = _candidate_from_request(request)
    rules_by_id = {rule.rule_id: rule for rule in active_po_summary.rule_summaries}
    final_selection_available = _final_selection_logic_available(rules_by_id)
    fallback_used = not final_selection_available

    signals = _build_safe_signals(candidate, rules_by_id)
    return PoBasedIntakeResult(
        intake_id=f"PO-INTAKE-{candidate.candidate_id}",
        candidate=candidate,
        po_logic_source_status=active_po_summary.source_status,
        po_logic_used=[
            rule_id for rule_id in SAFE_POS_RULE_IDS if rule_id in rules_by_id
        ],
        po_logic_not_used=_po_logic_not_used(active_po_summary),
        final_selection_logic_available=final_selection_available,
        fallback_used=fallback_used,
        fallback_reason=(
            "POs final selection logic was not found; sanitized submittal intake "
            "candidate remains the review source."
            if fallback_used
            else "Safe POs source summary is available, but final selection still remains review-only."
        ),
        signals=signals,
        review_required_fields=list(candidate.review_required_fields),
        blocked_fields=list(candidate.blocked_fields),
        unmapped_fields=[field.source_key for field in candidate.unmapped_fields],
        source_evidence_ids=_candidate_evidence_ids(candidate),
        export_allowed=False,
        pdf_export_enabled=False,
        direct_coil_final_export_available=False,
        raw_private_data_read=False,
        raw_private_data_returned=False,
        raw_text_excluded=True,
    )


def _candidate_from_request(request: dict[str, Any]) -> SubmittalCoilCandidate:
    candidate_payload = request.get("submittal_candidate") or request.get("candidate")
    if candidate_payload:
        return SubmittalCoilCandidate.model_validate(candidate_payload)

    source_id = str(request.get("source_id") or "SANITIZED-SOURCE-DOC-INTAKE-001")
    submittal_text = request.get("submittal_text")
    if submittal_text is None:
        submittal_text = DEFAULT_SANITIZED_TEXT_PATH.read_text(encoding="utf-8")
    return extract_submittal_candidates_from_text(
        str(submittal_text),
        source_id=source_id,
    )[0]


def _build_safe_signals(
    candidate: SubmittalCoilCandidate,
    rules_by_id: dict[str, PoLogicRuleSummary],
) -> list[PoBasedIntakeSignal]:
    signals: list[PoBasedIntakeSignal] = []

    unit_rule = rules_by_id.get("po_unit_tag_normalization")
    if unit_rule and candidate.tag is not None:
        normalized_tag = normalize_po_unit_tag(candidate.tag.value)
        status: PoBasedSignalStatus = (
            "blocked" if _looks_component_like(normalized_tag) else "review_required"
        )
        signals.append(
            PoBasedIntakeSignal(
                signal_id="pos-unit-tag-normalization",
                field_key="tag",
                po_rule_id=unit_rule.rule_id,
                classification=unit_rule.classification,
                source_value=candidate.tag.value,
                normalized_value=normalized_tag,
                source_evidence=list(candidate.tag.source_evidence),
                status=status,
                notes=[
                    "Normalized from sanitized candidate tag only.",
                    "Normalized tag is not engineering approval.",
                ],
            )
        )

    product_rule = rules_by_id.get("po_cover_table_product_detection")
    if product_rule and candidate.product_type is not None:
        signals.append(
            PoBasedIntakeSignal(
                signal_id="pos-product-detection-signal",
                field_key="product_type",
                po_rule_id=product_rule.rule_id,
                classification=product_rule.classification,
                source_value=candidate.product_type.value,
                normalized_value=candidate.product_type.value,
                source_evidence=list(candidate.product_type.source_evidence),
                status="review_required",
                notes=[
                    "Sanitized product detection is a candidate signal only.",
                    "No final selection logic is applied.",
                ],
            )
        )

    component_rule = rules_by_id.get("po_component_coil_detection")
    if component_rule and candidate.coil_type is not None:
        signals.append(
            PoBasedIntakeSignal(
                signal_id="pos-component-coil-detection-signal",
                field_key="coil_type",
                po_rule_id=component_rule.rule_id,
                classification=component_rule.classification,
                source_value=candidate.coil_type.value,
                normalized_value=candidate.coil_type.value,
                source_evidence=list(candidate.coil_type.source_evidence),
                status="review_required",
                notes=[
                    "Sanitized coil/component detection is a review signal only.",
                    "BOM or manufacturing disposition logic is not applied.",
                ],
            )
        )

    review_gate_rule = rules_by_id.get("po_review_before_export_gate")
    if review_gate_rule:
        signals.append(
            PoBasedIntakeSignal(
                signal_id="pos-review-before-export-gate",
                field_key="export_status",
                po_rule_id=review_gate_rule.rule_id,
                classification=review_gate_rule.classification,
                source_value="review_before_export",
                normalized_value="export_disabled_review_required",
                source_evidence=[],
                status="blocked",
                notes=[
                    "Review-before-export gate is enforced as no export in Phase 2D.",
                    "Direct Coil final export and PDF export remain unavailable.",
                ],
            )
        )

    return signals


def _looks_component_like(normalized_tag: str) -> bool:
    tokens = set(normalized_tag.split("-"))
    return bool(tokens.intersection(COMPONENT_LIKE_TAG_TOKENS))


def _final_selection_logic_available(
    rules_by_id: dict[str, PoLogicRuleSummary],
) -> bool:
    return any(
        rules_by_id.get(rule_id) is not None
        and rules_by_id[rule_id].classification != "not_found"
        for rule_id in POS_FINAL_SELECTION_RULE_IDS
    )


def _po_logic_not_used(summary: PoLogicIntakeSummary) -> list[str]:
    blocked = []
    for rule in summary.rule_summaries:
        if (
            rule.rule_id in POS_RULE_IDS_REQUIRING_REVIEW
            or rule.rule_id in POS_FINAL_SELECTION_RULE_IDS
            or rule.classification in {"needs_john_review", "not_safe_for_coilforge", "not_found"}
        ):
            blocked.append(rule.rule_id)
    return list(dict.fromkeys(blocked))


def _candidate_evidence_ids(candidate: SubmittalCoilCandidate) -> list[str]:
    evidence_ids: list[str] = []
    for evidence in candidate.source_evidence:
        evidence_ids.append(evidence.evidence_id)
    for field_value in _candidate_field_values(candidate):
        evidence_ids.extend(evidence.evidence_id for evidence in field_value.source_evidence)
    for unmapped in candidate.unmapped_fields:
        evidence_ids.extend(evidence.evidence_id for evidence in unmapped.source_evidence)
    return list(dict.fromkeys(evidence_ids))


def _candidate_field_values(candidate: SubmittalCoilCandidate) -> list[Any]:
    values = []
    for field_name in ("tag", "product_type", "coil_type", "header_type"):
        value = getattr(candidate, field_name)
        if value is not None:
            values.append(value)
    for group_name in (
        "geometry",
        "airside_conditions",
        "refrigerant_conditions",
        "materials_construction",
        "connections",
        "performance",
        "drawing_parameters",
    ):
        values.extend(getattr(candidate, group_name).values())
    return values
