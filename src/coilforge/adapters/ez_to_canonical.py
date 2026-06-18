from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from coilforge.contracts import FieldValue, SourceEvidence
from coilforge.contracts.canonical import CanonicalCoilRecord
from coilforge.interfaces.direct_coil import is_header_type_supported
from coilforge.submittal.candidate import UnmappedField
from coilforge.validation import apply_canonical_validation


CanonicalGroup = Literal[
    "project",
    "coil_identity",
    "geometry",
    "airside_conditions",
    "refrigerant_conditions",
    "materials_construction",
    "connections",
    "manufacturing_options",
    "drawing_parameters",
    "performance",
]


@dataclass(frozen=True)
class EZFieldRule:
    source_key: str
    target: str
    target_key: str | None = None
    unit: str | None = None
    confidence: str = "confirmed"
    review_note: str = "Sanitized EZ JSON compatibility value requires review."


@dataclass(frozen=True)
class EZJsonToCanonicalSummary:
    validation_status: str
    review_required_fields: tuple[str, ...]
    blocked_fields: tuple[str, ...]
    unmapped_field_keys: tuple[str, ...]
    mapped_field_keys: tuple[str, ...]


@dataclass(frozen=True)
class EZJsonToCanonicalResult:
    record: CanonicalCoilRecord
    summary: EZJsonToCanonicalSummary


EZ_FIELD_RULES: dict[str, EZFieldRule] = {
    "source_case_id": EZFieldRule("source_case_id", "project", "source_case_id"),
    "coil_name": EZFieldRule("coil_name", "coil_identity", "coil_name"),
    "model_number": EZFieldRule("model_number", "coil_identity", "model_number"),
    "coil_category": EZFieldRule(
        "coil_category",
        "product_type",
        confidence="inferred",
        review_note="EZ coil category is a compatibility classification and requires review.",
    ),
    "header_type": EZFieldRule(
        "header_type",
        "header_type",
        confidence="inferred",
        review_note="EZ header type is a compatibility classification and requires review.",
    ),
    "rows": EZFieldRule("rows", "geometry", "rows_deep", "rows"),
    "fin_height": EZFieldRule("fin_height", "geometry", "finned_height", "in"),
    "fin_length": EZFieldRule("fin_length", "geometry", "finned_length", "in"),
    "fin_density_fpi": EZFieldRule("fin_density_fpi", "geometry", "fins_per_inch", "fpi"),
    "airflow_direction": EZFieldRule(
        "airflow_direction",
        "geometry",
        "airflow_direction",
        confidence="confirmed",
        review_note="EZ airflow direction is explicit but remains review-required.",
    ),
    "coil_hand": EZFieldRule(
        "coil_hand",
        "connections",
        "coil_hand",
        review_note="EZ coil hand is explicit but remains review-required.",
    ),
    "return_connection_size": EZFieldRule(
        "return_connection_size",
        "connections",
        "return_connection_size",
        "in",
    ),
    "casing_depth": EZFieldRule("casing_depth", "drawing_parameters", "CD", "in"),
    "top_flange": EZFieldRule("top_flange", "drawing_parameters", "TF", "in"),
    "bottom_flange": EZFieldRule("bottom_flange", "drawing_parameters", "BF", "in"),
    "casing_height": EZFieldRule("casing_height", "drawing_parameters", "CH", "in"),
    "casing_length": EZFieldRule("casing_length", "drawing_parameters", "SL", "in"),
    "return_bend_allowance": EZFieldRule(
        "return_bend_allowance",
        "drawing_parameters",
        "R",
        "in",
    ),
}


def map_ez_json_to_canonical(
    payload: dict[str, Any],
    *,
    record_id: str | None = None,
    source_id: str | None = None,
) -> CanonicalCoilRecord:
    return map_ez_json_to_canonical_result(
        payload,
        record_id=record_id,
        source_id=source_id,
    ).record


def map_ez_json_to_canonical_result(
    payload: dict[str, Any],
    *,
    record_id: str | None = None,
    source_id: str | None = None,
) -> EZJsonToCanonicalResult:
    source = source_id or str(payload.get("source_case_id") or "SANITIZED-EZ-JSON")
    canonical_payload: dict[str, Any] = {
        "record_id": record_id or f"CCR-EZ-{source}",
        "project": {},
        "coil_identity": {},
        "product_type": None,
        "coil_type": None,
        "header_type": None,
        "geometry": {},
        "airside_conditions": {},
        "refrigerant_conditions": {},
        "materials_construction": {},
        "connections": {},
        "manufacturing_options": {},
        "drawing_parameters": {},
        "performance": {},
        "source_evidence": [],
        "unmapped_fields": [],
        "review_required_fields": [],
        "blocked_fields": [],
        "manual_overrides": [],
        "validation_status": "not_validated",
    }
    mapped_keys: list[str] = []

    for key, value in payload.items():
        rule = EZ_FIELD_RULES.get(key)
        if rule is None:
            canonical_payload["unmapped_fields"].append(
                _build_unmapped_field(key, value, source)
            )
            continue

        mapped_keys.append(key)
        field_value = _build_field_value(rule, value, source)
        canonical_payload["source_evidence"].extend(field_value.source_evidence)
        if rule.target in {"product_type", "coil_type", "header_type"}:
            canonical_payload[rule.target] = field_value
            canonical_payload["review_required_fields"].append(rule.target)
        else:
            group = canonical_payload[rule.target]
            group[rule.target_key] = field_value
            canonical_payload["review_required_fields"].append(
                f"{rule.target}.{rule.target_key}"
            )

    header_type = canonical_payload["header_type"]
    if header_type is not None and header_type.value not in (None, ""):
        if not is_header_type_supported(str(header_type.value)):
            canonical_payload["blocked_fields"].append("header_type")

    canonical = CanonicalCoilRecord.model_validate(canonical_payload)
    validated = apply_canonical_validation(canonical)
    unmapped_keys = tuple(field.source_key for field in validated.unmapped_fields)
    return EZJsonToCanonicalResult(
        record=validated,
        summary=EZJsonToCanonicalSummary(
            validation_status=validated.validation_status,
            review_required_fields=tuple(validated.review_required_fields),
            blocked_fields=tuple(validated.blocked_fields),
            unmapped_field_keys=unmapped_keys,
            mapped_field_keys=tuple(mapped_keys),
        ),
    )


def _build_field_value(rule: EZFieldRule, value: Any, source_id: str) -> FieldValue:
    evidence = _build_source_evidence(
        rule.source_key,
        value,
        source_id,
        normalized_value=value,
        unit=rule.unit,
        confidence=rule.confidence,
        notes=[rule.review_note],
    )
    return FieldValue(
        value=value,
        unit=rule.unit,
        source_evidence=[evidence],
        confidence=rule.confidence,
        status="review_required",
        review_required=True,
        notes=[rule.review_note],
    )


def _build_unmapped_field(source_key: str, value: Any, source_id: str) -> UnmappedField:
    evidence = _build_source_evidence(
        source_key,
        value,
        source_id,
        normalized_value=None,
        unit=None,
        confidence="ambiguous",
        notes=["No approved Phase 2C EZ JSON compatibility mapping rule."],
    )
    return UnmappedField(
        source_key=source_key,
        source_value=value,
        reason="No approved Phase 2C EZ JSON compatibility mapping rule.",
        source_evidence=[evidence],
    )


def _build_source_evidence(
    source_key: str,
    source_value: Any,
    source_id: str,
    *,
    normalized_value: Any,
    unit: str | None,
    confidence: str,
    notes: list[str],
) -> SourceEvidence:
    return SourceEvidence(
        evidence_id=f"EV-EZ-{source_id}-{source_key}",
        source_type="sanitized_ez_reference",
        source_id=source_id,
        source_location=f"sanitized-ez-json:{source_key}",
        source_key=source_key,
        source_value=source_value,
        normalized_value=normalized_value,
        unit=unit,
        confidence=confidence,
        review_status="unreviewed",
        evidence_status="candidate",
        notes=notes,
    )
