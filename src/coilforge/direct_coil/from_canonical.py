from __future__ import annotations

from coilforge.contracts.canonical import CanonicalCoilRecord
from coilforge.contracts.field_value import FieldValue
from coilforge.direct_coil.draft import (
    DirectCoilDraftField,
    DirectCoilDraftSummary,
    DirectCoilInputDraft,
)
from coilforge.interfaces.direct_coil import (
    DIRECT_COIL_FIELD_GROUPS,
    DIRECT_COIL_FIELD_REGISTRY,
    is_header_type_supported,
)
from coilforge.validation import CANONICAL_DIRECT_COIL_FIELD_MAP


def map_canonical_to_direct_coil_draft(
    record: CanonicalCoilRecord,
    *,
    draft_id: str | None = None,
) -> DirectCoilInputDraft:
    """Build a review-only Direct Coil draft from a canonical record."""

    fields = {
        field_key: _build_draft_field(record, field_key)
        for field_key in DIRECT_COIL_FIELD_REGISTRY
    }
    groups = {
        group: [
            field_key
            for field_key, definition in DIRECT_COIL_FIELD_REGISTRY.items()
            if definition.group == group
        ]
        for group in DIRECT_COIL_FIELD_GROUPS
    }
    return DirectCoilInputDraft(
        draft_id=draft_id or f"DCI-{record.record_id}",
        source_canonical_record_id=record.record_id,
        groups=groups,
        fields=fields,
        summary=_summarize_fields(fields.values()),
        coil_quantity=_build_optional_identity_field(record, "coil_quantity", "Coil quantity"),
    )


def _build_draft_field(
    record: CanonicalCoilRecord,
    field_key: str,
) -> DirectCoilDraftField:
    definition = DIRECT_COIL_FIELD_REGISTRY[field_key]
    canonical_path = CANONICAL_DIRECT_COIL_FIELD_MAP.get(field_key)
    if canonical_path is None:
        return DirectCoilDraftField(
            field_key=field_key,
            label=definition.label,
            group=definition.group,
            value=None,
            unit=definition.unit,
            source_evidence=[],
            mapping_rule="unmapped",
            status="unmapped",
            review_required=False,
            blocked_reason=None,
            manual_override=False,
        )

    field_value = _get_record_field_value(record, canonical_path)
    if field_value is None or field_value.value in (None, ""):
        status = "blocked" if definition.required else "unmapped"
        blocked_reason = (
            "required canonical field missing" if definition.required else None
        )
        return DirectCoilDraftField(
            field_key=field_key,
            label=definition.label,
            group=definition.group,
            value=None,
            unit=definition.unit,
            source_evidence=[],
            mapping_rule=f"canonical:{canonical_path}",
            status=status,
            review_required=definition.required,
            blocked_reason=blocked_reason,
            manual_override=False,
        )

    status = _status_from_field_value(field_value)
    blocked_reason = field_value.blocked_reason

    if definition.unit and field_value.unit != definition.unit:
        status = "blocked"
        blocked_reason = "unit mismatch without approved conversion rule"

    if definition.source_required and not field_value.source_evidence:
        status = "blocked"
        blocked_reason = "source evidence required for mapped Direct Coil field"

    if field_key == "header_type" and not is_header_type_supported(str(field_value.value)):
        status = "blocked"
        blocked_reason = "unsupported header_type is blocked"

    return DirectCoilDraftField(
        field_key=field_key,
        label=definition.label,
        group=definition.group,
        value=field_value.value,
        unit=field_value.unit or definition.unit,
        source_evidence=list(field_value.source_evidence),
        mapping_rule=f"canonical:{canonical_path}",
        status=status,
        review_required=status == "review_required" or field_value.review_required,
        blocked_reason=blocked_reason,
        manual_override=field_value.manual_override,
    )


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


def _build_optional_identity_field(
    record: CanonicalCoilRecord,
    field_key: str,
    label: str,
) -> DirectCoilDraftField | None:
    field_value = _get_record_field_value(record, f"coil_identity.{field_key}")
    if field_value is None:
        return None
    status = _status_from_field_value(field_value)
    return DirectCoilDraftField(
        field_key=field_key,
        label=label,
        group="Coil Geometry",
        value=field_value.value,
        unit=field_value.unit,
        source_evidence=list(field_value.source_evidence),
        mapping_rule=f"canonical:coil_identity.{field_key}",
        status=status,
        review_required=status == "review_required" or field_value.review_required,
        blocked_reason=field_value.blocked_reason,
        manual_override=field_value.manual_override,
    )


def _status_from_field_value(field_value: FieldValue) -> str:
    if field_value.status == "blocked":
        return "blocked"
    if field_value.manual_override or field_value.status == "manual_override":
        return "manual_override"
    if (
        field_value.review_required
        or field_value.status == "review_required"
        or field_value.confidence in {"inferred", "ambiguous", "missing"}
        or any(evidence.review_status == "unreviewed" for evidence in field_value.source_evidence)
    ):
        return "review_required"
    return "ready"


def _summarize_fields(fields: object) -> DirectCoilDraftSummary:
    counts = {
        "ready": 0,
        "review_required": 0,
        "blocked": 0,
        "unmapped": 0,
        "manual_override": 0,
    }
    for field in fields:
        counts[field.status] += 1
    return DirectCoilDraftSummary(**counts)
