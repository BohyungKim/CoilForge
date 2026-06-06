from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from coilforge.contracts.evidence import SourceEvidence
from coilforge.direct_coil.draft import DirectCoilDraftField, DirectCoilInputDraft
from coilforge.interfaces.direct_coil import DIRECT_COIL_FIELD_REGISTRY


class DirectCoilReadinessField(BaseModel):
    """Report-facing view of one Direct Coil draft field."""

    model_config = ConfigDict(extra="forbid")

    field_key: str
    label: str
    group: str
    required: bool
    value: object = None
    unit: str | None = None
    status: str
    blocked_reason: str | None = None
    review_required: bool
    manual_override: bool
    source_evidence: list[SourceEvidence] = Field(default_factory=list)


class SourceEvidenceSummary(BaseModel):
    fields_with_source_evidence: int
    total_source_evidence_refs: int
    evidence_ids_by_field: dict[str, list[str]]


class DrawingParameterSummary(BaseModel):
    total: int
    ready: int
    review_required: int
    blocked: int
    unmapped: int
    blocked_fields: list[str]


class DirectCoilReadinessReport(BaseModel):
    """Review packet for Direct Coil draft readiness. This is not an export."""

    model_config = ConfigDict(extra="forbid")

    draft_id: str
    source_canonical_record_id: str
    total_fields: int
    summary_counts: dict[str, int]
    ready_fields: list[DirectCoilReadinessField]
    review_required_fields: list[DirectCoilReadinessField]
    blocked_fields: list[DirectCoilReadinessField]
    unmapped_fields: list[DirectCoilReadinessField]
    required_missing_fields: list[DirectCoilReadinessField]
    source_evidence_summary: SourceEvidenceSummary
    drawing_parameter_summary: DrawingParameterSummary
    export_status: str


def build_direct_coil_readiness_report(
    draft: DirectCoilInputDraft,
) -> DirectCoilReadinessReport:
    fields = [_build_report_field(field) for field in draft.fields.values()]
    ready_fields = _fields_with_status(fields, "ready")
    review_required_fields = _fields_with_status(fields, "review_required")
    blocked_fields = _fields_with_status(fields, "blocked")
    unmapped_fields = _fields_with_status(fields, "unmapped")

    return DirectCoilReadinessReport(
        draft_id=draft.draft_id,
        source_canonical_record_id=draft.source_canonical_record_id,
        total_fields=len(fields),
        summary_counts={
            "ready": draft.summary.ready,
            "review_required": draft.summary.review_required,
            "blocked": draft.summary.blocked,
            "unmapped": draft.summary.unmapped,
            "manual_override": draft.summary.manual_override,
        },
        ready_fields=ready_fields,
        review_required_fields=review_required_fields,
        blocked_fields=blocked_fields,
        unmapped_fields=unmapped_fields,
        required_missing_fields=[
            field
            for field in blocked_fields
            if field.required and field.value in (None, "")
        ],
        source_evidence_summary=_build_source_evidence_summary(fields),
        drawing_parameter_summary=_build_drawing_parameter_summary(fields),
        export_status=draft.export_status,
    )


def _build_report_field(field: DirectCoilDraftField) -> DirectCoilReadinessField:
    definition = DIRECT_COIL_FIELD_REGISTRY[field.field_key]
    return DirectCoilReadinessField(
        field_key=field.field_key,
        label=field.label,
        group=field.group,
        required=definition.required,
        value=field.value,
        unit=field.unit,
        status=field.status,
        blocked_reason=field.blocked_reason,
        review_required=field.review_required,
        manual_override=field.manual_override,
        source_evidence=list(field.source_evidence),
    )


def _fields_with_status(
    fields: list[DirectCoilReadinessField],
    status: str,
) -> list[DirectCoilReadinessField]:
    return [field for field in fields if field.status == status]


def _build_source_evidence_summary(
    fields: list[DirectCoilReadinessField],
) -> SourceEvidenceSummary:
    evidence_ids_by_field = {
        field.field_key: [evidence.evidence_id for evidence in field.source_evidence]
        for field in fields
        if field.source_evidence
    }
    return SourceEvidenceSummary(
        fields_with_source_evidence=len(evidence_ids_by_field),
        total_source_evidence_refs=sum(
            len(evidence_ids) for evidence_ids in evidence_ids_by_field.values()
        ),
        evidence_ids_by_field=evidence_ids_by_field,
    )


def _build_drawing_parameter_summary(
    fields: list[DirectCoilReadinessField],
) -> DrawingParameterSummary:
    drawing_fields = [
        field for field in fields if field.group == "Drawing Parameters"
    ]
    return DrawingParameterSummary(
        total=len(drawing_fields),
        ready=len(_fields_with_status(drawing_fields, "ready")),
        review_required=len(_fields_with_status(drawing_fields, "review_required")),
        blocked=len(_fields_with_status(drawing_fields, "blocked")),
        unmapped=len(_fields_with_status(drawing_fields, "unmapped")),
        blocked_fields=[
            field.field_key
            for field in drawing_fields
            if field.status == "blocked"
        ],
    )
