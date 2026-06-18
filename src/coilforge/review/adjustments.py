from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from coilforge.contracts import SourceEvidence
from coilforge.interfaces.direct_coil import (
    DIRECT_COIL_FIELD_REGISTRY,
    DRAWING_PARAMETER_FIELD_KEYS,
)


AdjustmentReviewStatus = Literal["review_required", "blocked", "rejected"]

DRAWING_INTENT_FIELD_KEYS = {
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

DRAWING_IMPACTING_FIELD_KEYS = set(DRAWING_PARAMETER_FIELD_KEYS).union(
    DRAWING_INTENT_FIELD_KEYS
)


class EngineeringAdjustment(BaseModel):
    """Manual engineering adjustment record for review-only override capture."""

    model_config = ConfigDict(extra="forbid")

    adjustment_id: str
    field_key: str
    field_group: str
    original_value: Any = None
    adjusted_value: Any = None
    unit: str | None = None
    reason: str
    adjusted_by: str
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    review_status: AdjustmentReviewStatus = "review_required"
    drawing_impact: bool = False
    direct_coil_impact: str = "review_required_no_downstream_change"
    quote_impact: str = "quote_prep_review_only"
    created_from_phase: str = "Phase 2D-M1"
    downstream_applied: bool = False

    @model_validator(mode="after")
    def enforce_phase2d_review_only_policy(self) -> EngineeringAdjustment:
        if self.downstream_applied:
            raise ValueError("Phase 2D adjustments must not be downstream_applied")
        if self.review_status not in {"review_required", "blocked", "rejected"}:
            raise ValueError("Phase 2D adjustments cannot be engineering approved")
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def build_engineering_adjustment(
    *,
    adjustment_id: str,
    field_key: str,
    original_value: Any,
    adjusted_value: Any,
    reason: str,
    adjusted_by: str,
    source_evidence: list[SourceEvidence] | None = None,
    unit: str | None = None,
    field_group: str | None = None,
    review_status: AdjustmentReviewStatus = "review_required",
) -> EngineeringAdjustment:
    definition = DIRECT_COIL_FIELD_REGISTRY.get(field_key)
    resolved_group = field_group or (definition.group if definition else "Unmapped")
    drawing_impact = field_key in DRAWING_IMPACTING_FIELD_KEYS
    direct_coil_impact = (
        "drawing_impacting_direct_coil_review_required"
        if drawing_impact
        else "direct_coil_review_required"
    )
    quote_impact = (
        "drawing_or_quote_prep_review_required"
        if drawing_impact
        else "quote_prep_review_only"
    )
    return EngineeringAdjustment(
        adjustment_id=adjustment_id,
        field_key=field_key,
        field_group=resolved_group,
        original_value=original_value,
        adjusted_value=adjusted_value,
        unit=unit or (definition.unit if definition else None),
        reason=reason,
        adjusted_by=adjusted_by,
        source_evidence=list(source_evidence or []),
        review_status=review_status,
        drawing_impact=drawing_impact,
        direct_coil_impact=direct_coil_impact,
        quote_impact=quote_impact,
        created_from_phase="Phase 2D-M1",
        downstream_applied=False,
    )


def resolve_conflicting_adjustments(
    adjustments: list[EngineeringAdjustment],
) -> list[EngineeringAdjustment]:
    """Mark same-field conflicting adjusted values as blocked."""

    conflicts = _conflicting_field_keys(adjustments)
    resolved = []
    for adjustment in adjustments:
        if adjustment.field_key not in conflicts:
            resolved.append(adjustment)
            continue
        resolved.append(
            adjustment.model_copy(
                update={
                    "review_status": "blocked",
                    "direct_coil_impact": "blocked_conflicting_manual_overrides",
                    "quote_impact": "blocked_conflicting_manual_overrides",
                    "downstream_applied": False,
                }
            )
        )
    return resolved


def _conflicting_field_keys(adjustments: list[EngineeringAdjustment]) -> set[str]:
    values_by_field: dict[str, set[str]] = {}
    for adjustment in adjustments:
        values_by_field.setdefault(adjustment.field_key, set()).add(
            repr(adjustment.adjusted_value)
        )
    return {
        field_key
        for field_key, values in values_by_field.items()
        if len(values) > 1
    }
