from __future__ import annotations

from dataclasses import dataclass

from coilforge.contracts.canonical import CanonicalCoilRecord
from coilforge.contracts.evidence import SourceEvidence
from coilforge.contracts.field_value import FieldValue
from coilforge.submittal.candidate import SubmittalCoilCandidate
from coilforge.validation import apply_canonical_validation


@dataclass(frozen=True)
class SubmittalToCanonicalSummary:
    validation_status: str
    review_required_fields: tuple[str, ...]
    blocked_fields: tuple[str, ...]
    unmapped_field_count: int


@dataclass(frozen=True)
class SubmittalToCanonicalResult:
    record: CanonicalCoilRecord
    summary: SubmittalToCanonicalSummary


def map_submittal_candidate_to_canonical(
    candidate: SubmittalCoilCandidate,
    *,
    record_id: str | None = None,
) -> CanonicalCoilRecord:
    """Convert a sanitized submittal candidate into the shared canonical record."""

    result = map_submittal_candidate_to_canonical_result(
        candidate,
        record_id=record_id,
    )
    return result.record


def map_submittal_candidate_to_canonical_result(
    candidate: SubmittalCoilCandidate,
    *,
    record_id: str | None = None,
) -> SubmittalToCanonicalResult:
    canonical = CanonicalCoilRecord(
        record_id=record_id or f"CCR-{candidate.candidate_id}",
        project={},
        coil_identity=_build_coil_identity(candidate),
        product_type=_keep_candidate_classification(candidate.product_type),
        coil_type=_keep_candidate_classification(candidate.coil_type),
        header_type=_keep_candidate_classification(candidate.header_type),
        geometry=dict(candidate.geometry),
        airside_conditions=dict(candidate.airside_conditions),
        refrigerant_conditions=dict(candidate.refrigerant_conditions),
        materials_construction=dict(candidate.materials_construction),
        connections=dict(candidate.connections),
        manufacturing_options=dict(candidate.manufacturing_options),
        drawing_parameters=dict(candidate.drawing_parameters),
        performance=dict(candidate.performance),
        source_evidence=_collect_source_evidence(candidate),
        unmapped_fields=list(candidate.unmapped_fields),
        review_required_fields=list(candidate.review_required_fields),
        blocked_fields=_translate_candidate_blockers(candidate.blocked_fields),
        manual_overrides=[],
        validation_status="not_validated",
    )
    validated = apply_canonical_validation(canonical)
    return SubmittalToCanonicalResult(
        record=validated,
        summary=SubmittalToCanonicalSummary(
            validation_status=validated.validation_status,
            review_required_fields=tuple(validated.review_required_fields),
            blocked_fields=tuple(validated.blocked_fields),
            unmapped_field_count=len(validated.unmapped_fields),
        ),
    )


def _build_coil_identity(candidate: SubmittalCoilCandidate) -> dict[str, FieldValue]:
    identity = {}
    if candidate.tag is not None:
        identity["tag"] = candidate.tag
    if candidate.quantity is not None:
        identity["coil_quantity"] = candidate.quantity
    return identity


def _keep_candidate_classification(field_value: FieldValue | None) -> FieldValue | None:
    if field_value is None:
        return None
    if field_value.confidence in {"inferred", "ambiguous", "missing"}:
        return field_value.model_copy(
            update={"status": "review_required", "review_required": True}
        )
    if any(evidence.review_status == "unreviewed" for evidence in field_value.source_evidence):
        return field_value.model_copy(
            update={"status": "review_required", "review_required": True}
        )
    return field_value


def _collect_source_evidence(candidate: SubmittalCoilCandidate) -> list[SourceEvidence]:
    collected: dict[str, SourceEvidence] = {
        evidence.evidence_id: evidence for evidence in candidate.source_evidence
    }

    for field_value in (
        candidate.tag,
        candidate.quantity,
        candidate.product_type,
        candidate.coil_type,
        candidate.header_type,
    ):
        _add_field_evidence(collected, field_value)

    for group in (
        candidate.geometry,
        candidate.airside_conditions,
        candidate.refrigerant_conditions,
        candidate.materials_construction,
        candidate.connections,
        candidate.manufacturing_options,
        candidate.performance,
        candidate.drawing_parameters,
    ):
        for field_value in group.values():
            _add_field_evidence(collected, field_value)

    for unmapped_field in candidate.unmapped_fields:
        for evidence in unmapped_field.source_evidence:
            collected[evidence.evidence_id] = evidence

    return list(collected.values())


def _add_field_evidence(
    collected: dict[str, SourceEvidence],
    field_value: FieldValue | None,
) -> None:
    if field_value is None:
        return
    for evidence in field_value.source_evidence:
        collected[evidence.evidence_id] = evidence


def _translate_candidate_blockers(blocked_fields: list[str]) -> list[str]:
    translated = []
    for field_path in blocked_fields:
        if field_path == "tag":
            translated.append("coil_identity.tag")
        else:
            translated.append(field_path)
    return list(dict.fromkeys(translated))
