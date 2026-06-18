from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from coilforge.interfaces.direct_coil import DRAWING_PARAMETER_FIELD_KEYS
from coilforge.review.adjustments import (
    DRAWING_IMPACTING_FIELD_KEYS,
    EngineeringAdjustment,
    resolve_conflicting_adjustments,
)
from coilforge.submittal.po_based_intake import (
    PoBasedIntakeResult,
    build_po_based_intake,
)
from coilforge.workflows import (
    build_default_demo_workflow_input,
    run_submittal_to_drawing_workflow,
)


BASELINE_DRAWING_FIELDS = ("CD", "BF", "TF", "CH")


class ReviewExportStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_allowed: bool = False
    pdf_export_enabled: bool = False
    direct_coil_final_export_available: bool = False
    production_drawing_approval_claimed: bool = False
    quote_finalization_available: bool = False


class ReviewPacket(BaseModel):
    """Quote-prep/review-only packet for Phase 2D MVP testing."""

    model_config = ConfigDict(extra="forbid")

    packet_id: str
    project: dict[str, Any]
    coil_identity: dict[str, Any]
    input_source_summary: dict[str, Any]
    po_based_intake_summary: dict[str, Any]
    direct_coil_input_draft_summary: dict[str, Any]
    readiness_report_summary: dict[str, Any]
    source_evidence_summary: dict[str, Any]
    drawing_intent_summary: dict[str, Any]
    svg_metadata_summary: dict[str, Any]
    engineering_adjustment_summary: dict[str, Any]
    review_required_fields: list[str]
    blocked_fields: list[str]
    unmapped_fields: list[str]
    cd_bf_tf_ch_status: dict[str, dict[str, Any]]
    drawing_impacting_field_summary: dict[str, Any]
    pos_supported_field_summary: dict[str, Any]
    unresolved_review_items: list[str]
    export_status: ReviewExportStatus = Field(default_factory=ReviewExportStatus)
    quote_prep_status: dict[str, Any]
    raw_private_source_text_included: bool = False
    packet_status: str = "quote_prep_review_only"

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def build_default_review_packet() -> ReviewPacket:
    workflow_input = build_default_demo_workflow_input()["input"]
    workflow_output = run_submittal_to_drawing_workflow(workflow_input)
    intake = build_po_based_intake(workflow_input)
    return build_review_packet(workflow_output, intake_result=intake)


def build_review_packet(
    workflow_output: dict[str, Any] | None = None,
    *,
    intake_result: PoBasedIntakeResult | None = None,
    adjustments: list[EngineeringAdjustment] | None = None,
) -> ReviewPacket:
    active_output = workflow_output or run_submittal_to_drawing_workflow(
        build_default_demo_workflow_input()["input"]
    )
    active_intake = intake_result or build_po_based_intake()
    resolved_adjustments = resolve_conflicting_adjustments(list(adjustments or []))

    draft = active_output.get("direct_coil_input_draft") or {}
    readiness = active_output.get("readiness_report") or {}
    fields = draft.get("fields") or {}
    metadata = active_output.get("metadata") or {}
    drawing_intent = active_output.get("drawing_intent") or {}
    validation = active_output.get("validation") or {}
    selected = active_output.get("selected_candidate_summary") or {}

    return ReviewPacket(
        packet_id=f"REVIEW-PACKET-{draft.get('draft_id', active_intake.intake_id)}",
        project={
            "project_name": "CoilForge",
            "phase": "Phase 2D-M1",
            "policy": "quote_prep_review_only",
        },
        coil_identity={
            "candidate_id": selected.get("candidate_id")
            or active_intake.candidate.candidate_id,
            "tag": selected.get("tag")
            or (
                None
                if active_intake.candidate.tag is None
                else active_intake.candidate.tag.value
            ),
            "draft_id": draft.get("draft_id"),
            "source_canonical_record_id": draft.get("source_canonical_record_id"),
        },
        input_source_summary={
            "input_type": "sanitized_submittal_review_path",
            "raw_private_data_included": False,
            "raw_private_data_returned": False,
            "pdf_parser_enabled": False,
            "ocr_enabled": False,
        },
        po_based_intake_summary=_po_based_intake_summary(active_intake),
        direct_coil_input_draft_summary=_direct_coil_draft_summary(draft),
        readiness_report_summary=_readiness_summary(readiness),
        source_evidence_summary=_source_evidence_summary(readiness, active_intake),
        drawing_intent_summary=_drawing_intent_summary(drawing_intent),
        svg_metadata_summary=_svg_metadata_summary(metadata),
        engineering_adjustment_summary=_adjustment_summary(resolved_adjustments),
        review_required_fields=_review_required_fields(readiness, active_intake),
        blocked_fields=_blocked_fields(readiness, active_intake),
        unmapped_fields=_unmapped_fields(readiness, active_intake),
        cd_bf_tf_ch_status=_baseline_drawing_status(fields, readiness),
        drawing_impacting_field_summary=_drawing_impacting_summary(fields),
        pos_supported_field_summary=_pos_supported_field_summary(active_intake),
        unresolved_review_items=_unresolved_review_items(active_intake),
        export_status=ReviewExportStatus(
            export_allowed=False,
            pdf_export_enabled=False,
            direct_coil_final_export_available=False,
            production_drawing_approval_claimed=False,
            quote_finalization_available=False,
        ),
        quote_prep_status={
            "status": "review_ready_for_mvp_testing",
            "final_quote": False,
            "quote_finalization_available": False,
            "review_required": True,
        },
        raw_private_source_text_included=False,
        packet_status="quote_prep_review_only",
    )


def _po_based_intake_summary(intake: PoBasedIntakeResult) -> dict[str, Any]:
    return {
        "intake_id": intake.intake_id,
        "po_logic_source_status": intake.po_logic_source_status,
        "po_logic_used": list(intake.po_logic_used),
        "po_logic_not_used": list(intake.po_logic_not_used),
        "final_selection_logic_available": intake.final_selection_logic_available,
        "fallback_used": intake.fallback_used,
        "fallback_reason": intake.fallback_reason,
        "signal_count": len(intake.signals),
        "signal_field_keys": [signal.field_key for signal in intake.signals],
        "raw_private_data_read": intake.raw_private_data_read,
    }


def _direct_coil_draft_summary(draft: dict[str, Any]) -> dict[str, Any]:
    fields = draft.get("fields") or {}
    return {
        "draft_id": draft.get("draft_id"),
        "source_canonical_record_id": draft.get("source_canonical_record_id"),
        "field_count": len(fields),
        "summary": dict(draft.get("summary") or {}),
        "export_status": draft.get("export_status", "not_implemented"),
        "is_export_payload": False,
    }


def _readiness_summary(readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "draft_id": readiness.get("draft_id"),
        "total_fields": readiness.get("total_fields", 0),
        "summary_counts": dict(readiness.get("summary_counts") or {}),
        "export_status": readiness.get("export_status", "not_implemented"),
        "required_missing_fields": [
            field.get("field_key")
            for field in readiness.get("required_missing_fields", [])
        ],
        "drawing_parameter_summary": dict(
            readiness.get("drawing_parameter_summary") or {}
        ),
    }


def _source_evidence_summary(
    readiness: dict[str, Any],
    intake: PoBasedIntakeResult,
) -> dict[str, Any]:
    readiness_summary = readiness.get("source_evidence_summary") or {}
    return {
        "fields_with_source_evidence": readiness_summary.get(
            "fields_with_source_evidence",
            0,
        ),
        "total_source_evidence_refs": readiness_summary.get(
            "total_source_evidence_refs",
            0,
        ),
        "evidence_ids_by_field": dict(
            readiness_summary.get("evidence_ids_by_field") or {}
        ),
        "po_intake_source_evidence_ids": list(intake.source_evidence_ids),
        "raw_source_values_included": False,
    }


def _drawing_intent_summary(drawing_intent: dict[str, Any]) -> dict[str, Any]:
    if not drawing_intent:
        return {
            "available": False,
            "review_status": "not_available",
            "export_allowed": False,
        }
    return {
        "available": True,
        "coil_name": drawing_intent.get("coil_name"),
        "review_status": drawing_intent.get("review_status"),
        "preview_allowed": drawing_intent.get("preview_allowed"),
        "export_allowed": False,
        "blocked_reasons": list(drawing_intent.get("blocked_reasons") or []),
        "drawing_parameter_count": len(
            drawing_intent.get("drawing_parameters") or {}
        ),
        "title_block_release_status": (
            drawing_intent.get("title_block") or {}
        ).get("release_status"),
    }


def _svg_metadata_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": bool(metadata),
        "drawing_status": metadata.get("drawing_status"),
        "export_allowed": False,
        "pdf_export_enabled": False,
        "template_id": metadata.get("template_id"),
        "raw_svg_included": False,
    }


def _adjustment_summary(adjustments: list[EngineeringAdjustment]) -> dict[str, Any]:
    return {
        "total_adjustments": len(adjustments),
        "review_required": sum(1 for item in adjustments if item.review_status == "review_required"),
        "blocked": sum(1 for item in adjustments if item.review_status == "blocked"),
        "drawing_impacting": sum(1 for item in adjustments if item.drawing_impact),
        "downstream_applied": any(item.downstream_applied for item in adjustments),
        "field_keys": [item.field_key for item in adjustments],
        "items": [item.to_dict() for item in adjustments],
    }


def _review_required_fields(
    readiness: dict[str, Any],
    intake: PoBasedIntakeResult,
) -> list[str]:
    keys = [field.get("field_key") for field in readiness.get("review_required_fields", [])]
    keys.extend(intake.review_required_fields)
    return _clean_keys(keys)


def _blocked_fields(
    readiness: dict[str, Any],
    intake: PoBasedIntakeResult,
) -> list[str]:
    keys = [field.get("field_key") for field in readiness.get("blocked_fields", [])]
    keys.extend(intake.blocked_fields)
    return _clean_keys(keys)


def _unmapped_fields(
    readiness: dict[str, Any],
    intake: PoBasedIntakeResult,
) -> list[str]:
    keys = [field.get("field_key") for field in readiness.get("unmapped_fields", [])]
    keys.extend(intake.unmapped_fields)
    return _clean_keys(keys)


def _baseline_drawing_status(
    fields: dict[str, dict[str, Any]],
    readiness: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    blocked_keys = {
        field.get("field_key")
        for field in readiness.get("blocked_fields", [])
    }
    return {
        field_key: {
            "status": (fields.get(field_key) or {}).get("status")
            or ("blocked" if field_key in blocked_keys else "missing"),
            "drawing_impact": True,
            "review_status": "review_required_or_blocked",
            "production_approved": False,
        }
        for field_key in BASELINE_DRAWING_FIELDS
    }


def _drawing_impacting_summary(fields: dict[str, dict[str, Any]]) -> dict[str, Any]:
    statuses = {
        field_key: (fields.get(field_key) or {}).get("status", "missing")
        for field_key in sorted(DRAWING_IMPACTING_FIELD_KEYS)
    }
    return {
        "field_count": len(DRAWING_IMPACTING_FIELD_KEYS),
        "drawing_parameter_field_count": len(DRAWING_PARAMETER_FIELD_KEYS),
        "field_statuses": statuses,
        "review_required": True,
        "production_drawing_approval_claimed": False,
    }


def _pos_supported_field_summary(intake: PoBasedIntakeResult) -> dict[str, Any]:
    signal_rules = {signal.po_rule_id for signal in intake.signals}
    return {
        "used_rule_ids": list(intake.po_logic_used),
        "signal_field_keys": [signal.field_key for signal in intake.signals],
        "supported_field_candidates": {
            "header_type": "po_component_coil_detection",
            "system_type": "po_cover_table_product_detection",
        },
        "needs_review_field_candidates": {
            "distributor_notes": "po_bom_linestring_decisions",
            "drain_pan_type": "po_bom_linestring_decisions",
        },
        "bom_linestring_logic_applied_as_approved": False,
        "safe_signal_rule_ids": sorted(signal_rules),
    }


def _unresolved_review_items(intake: PoBasedIntakeResult) -> list[str]:
    items = [
        "CD/BF/TF/CH drawing semantics remain unresolved.",
        "22 drawing-impacting fields require John or engineering review.",
        "POs-supported field adoption remains a review decision.",
        "Future unit conversion approval remains unresolved.",
        "BOM/linestring Required/Inventory/Manufactured/N/A logic is not applied.",
    ]
    if intake.fallback_used:
        items.append("Application-team/BTO final selection logic was not found.")
    return items


def _clean_keys(keys: list[Any]) -> list[str]:
    return list(dict.fromkeys(str(key) for key in keys if key))
