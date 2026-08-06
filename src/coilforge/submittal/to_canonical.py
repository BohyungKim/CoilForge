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
    engine_dims: dict[str, Any] | None = None,
    engine_notes: str | None = None,
) -> SubmittalToCanonicalResult:
    connections = dict(candidate.connections)
    _ensure_return_connection_size(connections)
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
        connections=connections,
        manufacturing_options=_manufacturing_options_with_engine_notes(
            candidate, engine_notes
        ),
        drawing_parameters=_drawing_parameters_with_engine_dims(candidate, engine_dims),
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


# Logical drawing-dimension keys that have a Direct Coil "DRAWING / DIMENSION"
# review field (validation.canonical_rules.CANONICAL_DIRECT_COIL_FIELD_MAP →
# drawing_parameters.<KEY>). The header-2..N logical keys (I2/S2/O2/...) have no
# paste-ready draft_field_key, so they stay out of scope.
_REVIEWABLE_DRAWING_DIMS = frozenset(
    {"CD", "BF", "TF", "CH", "RF", "HF", "SL", "I", "S", "O", "R", "HD", "ZD"}
)


def _drawing_parameters_with_engine_dims(
    candidate: SubmittalCoilCandidate,
    engine_dims: dict[str, Any] | None,
) -> dict[str, FieldValue]:
    """Surface engine-derived drawing dimensions in the canonical record.

    The rule engine already computes these dimensions and renders them on the SVG
    (they live in the template drawing's ``slot_values``), but they were never
    written back into ``drawing_parameters``, so the paste-ready "DRAWING /
    DIMENSION" review fields read blank. Wire the SAME values through the canonical
    record so the review table mirrors the drawing. Every value stays
    ``review_required`` (never auto-confirmed) and carries engine source evidence;
    a submittal-stated value, if any, is never overridden. Only dimensions the
    engine actually produced are added — Bucket-B dims stay review-required/empty.
    """
    drawing_parameters = dict(candidate.drawing_parameters)
    if not engine_dims:
        return drawing_parameters
    for key, value in engine_dims.items():
        if key not in _REVIEWABLE_DRAWING_DIMS or value in (None, ""):
            continue
        if drawing_parameters.get(key) is not None:
            continue
        drawing_parameters[key] = FieldValue(
            value=value,
            unit="in",
            confidence="inferred",
            status="review_required",
            review_required=True,
            source_evidence=[
                SourceEvidence(
                    evidence_id=f"EV-ENGINE-DIM-{key}",
                    source_type="engine_rule",
                    source_id="coil-header-prepopulate-engine",
                    source_location="template drawing slot_values",
                    source_key=key,
                    source_value=value,
                    normalized_value=value,
                    unit="in",
                )
            ],
        )
    return drawing_parameters


def _manufacturing_options_with_engine_notes(
    candidate: SubmittalCoilCandidate,
    engine_notes: str | None,
) -> dict[str, FieldValue]:
    """Surface the engine-assembled drawing notes in the canonical record.

    The rule engine assembles the drawing notes (copper straps / coating / distributor
    extension — R-007/008/080/081/035) and renders them on the SVG, but they were never
    written back into ``manufacturing_options``, so the paste-ready "Drawing Notes" field
    (which reads ``distributor_notes`` — the codebase's legacy name for this field) read
    blank. Wire the SAME string through the CANONICAL record so the review surface mirrors
    the drawing. Value stays ``review_required`` (never auto-confirmed) with engine source
    evidence; a submittal-stated value, if any, is never overridden.

    Safe re: the drawing's distributor callout: both drawing renderers read
    ``slot.DISTRIBUTORS`` from the RAW candidate (``pdf_to_template_drawing`` via the
    candidate panel) or not at all (the parametric preview uses typed draft fields, never
    ``distributor_notes``). This injection touches only the CANONICAL copy, which feeds the
    paste-ready review surface — so the notes reach the review field without ever reaching
    a rendered distributor callout.
    """
    manufacturing_options = dict(candidate.manufacturing_options)
    if not engine_notes:
        return manufacturing_options
    if manufacturing_options.get("distributor_notes") is not None:
        return manufacturing_options
    manufacturing_options["distributor_notes"] = FieldValue(
        value=engine_notes,
        confidence="inferred",
        status="review_required",
        review_required=True,
        source_evidence=[
            SourceEvidence(
                evidence_id="EV-ENGINE-NOTES",
                source_type="engine_rule",
                source_id="coil-header-prepopulate-engine",
                source_location="header prepopulate engine notes assembly",
                source_key="distributor_notes",
                source_value=engine_notes,
                normalized_value=engine_notes,
            )
        ],
    )
    return manufacturing_options


def _ensure_return_connection_size(connections: dict[str, FieldValue]) -> None:
    """Water coils (CWC/HWC/PHWC) state Inlet/Outlet connection sizes and carry no
    "Suction/Return" label, so the canonical ``return_connection_size`` — which the
    Direct Coil "Return Connection Size" field reads — is left empty and the field
    blocks, even though the drawing slot is filled (it already falls back to
    inlet/outlet via ``submittal_to_drawing._candidate_connection_size``). Mirror
    that fallback at the canonical layer so the paste-ready surface agrees with the
    drawing: derive it from the stated outlet (the return side), then inlet,
    reusing that field's real source evidence so nothing is invented. Surfaced
    review-required."""
    existing = connections.get("return_connection_size")
    if existing is not None and existing.value not in (None, ""):
        return
    for key in ("outlet_connection_size", "inlet_connection_size"):
        source = connections.get(key)
        if source is not None and source.value not in (None, ""):
            connections["return_connection_size"] = source.model_copy(
                update={"status": "review_required", "review_required": True}
            )
            return


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
