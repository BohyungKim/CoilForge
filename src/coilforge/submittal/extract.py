from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from coilforge.contracts import FieldValue, SourceEvidence
from coilforge.submittal.candidate import SubmittalCoilCandidate, UnmappedField
from coilforge.submittal.rules import SubmittalFieldRule, get_submittal_field_rule, normalize_source_key


_KEY_VALUE_PATTERN = re.compile(r"^\s*([A-Za-z0-9 _-]+)\s*[:=]\s*(.*?)\s*$")
_NUMBER_UNIT_PATTERN = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*([A-Za-z%\"]+)?\s*$")
_FRACTION_UNIT_PATTERN = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*([A-Za-z%\"]+)?\s*$")
_MIXED_FRACTION_UNIT_PATTERN = re.compile(
    r"^\s*(-?\d+)\s+(\d+)\s*/\s*(\d+)\s*([A-Za-z%\"]+)?\s*$"
)


@dataclass(frozen=True)
class SanitizedSubmittalLine:
    source_key: str
    source_value: str
    line_number: int
    source_page: int | None = None
    source_section: str = "sanitized_text_intake"
    source_location: str | None = None


def extract_submittal_candidates_from_text(
    text: str,
    *,
    source_id: str = "SANITIZED-SOURCE-DOC-INTAKE-001",
) -> list[SubmittalCoilCandidate]:
    """Parse narrow sanitized key/value text into review-first candidates."""

    lines = _parse_key_value_lines(text)
    return [extract_submittal_candidate_from_structured(lines, source_id=source_id)]


def extract_submittal_candidate_from_structured(
    payload: Mapping[str, Any] | list[SanitizedSubmittalLine],
    *,
    source_id: str = "SANITIZED-SOURCE-DOC-INTAKE-001",
    field_rules: Mapping[str, SubmittalFieldRule] | None = None,
) -> SubmittalCoilCandidate:
    lines = _coerce_structured_lines(payload)
    candidate_payload: dict[str, Any] = {
        "candidate_id": "SCC-SANITIZED-INTAKE-001",
        "tag": None,
        "quantity": None,
        "product_type": None,
        "coil_type": None,
        "header_type": None,
        "geometry": {},
        "airside_conditions": {},
        "refrigerant_conditions": {},
        "materials_construction": {},
        "connections": {},
        "manufacturing_options": {},
        "performance": {},
        "drawing_parameters": {},
        "source_evidence": [],
        "review_required_fields": [],
        "blocked_fields": [],
        "unmapped_fields": [],
        "notes": ["Created by sanitized Phase 2B.9 intake adapter."],
        "review_status": "unreviewed",
    }

    for line in lines:
        rule = _get_field_rule(line.source_key, field_rules)
        if rule is None:
            candidate_payload["unmapped_fields"].append(
                _build_unmapped_field(line, source_id)
            )
            continue

        field_value = _build_field_value(line, rule, source_id)
        if rule.target in {"tag", "quantity", "product_type", "coil_type", "header_type"}:
            candidate_payload[rule.target] = field_value
            candidate_payload["review_required_fields"].append(rule.target)
        else:
            candidate_payload[rule.target][rule.target_key] = field_value
            candidate_payload["review_required_fields"].append(
                f"{rule.target}.{rule.target_key}"
            )

    _apply_inference_defaults(candidate_payload, source_id)
    return SubmittalCoilCandidate.model_validate(candidate_payload)


def _get_field_rule(
    source_key: str,
    field_rules: Mapping[str, SubmittalFieldRule] | None,
) -> SubmittalFieldRule | None:
    if field_rules is None:
        return get_submittal_field_rule(source_key)
    return field_rules.get(normalize_source_key(source_key))


def _parse_key_value_lines(text: str) -> list[SanitizedSubmittalLine]:
    lines: list[SanitizedSubmittalLine] = []
    for index, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _KEY_VALUE_PATTERN.match(line)
        if match is None:
            lines.append(
                SanitizedSubmittalLine(
                    source_key=f"UNMATCHED_LINE_{index}",
                    source_value=line,
                    line_number=index,
                )
            )
            continue
        lines.append(
            SanitizedSubmittalLine(
                source_key=normalize_source_key(match.group(1)),
                source_value=match.group(2).strip(),
                line_number=index,
            )
        )
    return lines


def _coerce_structured_lines(
    payload: Mapping[str, Any] | list[SanitizedSubmittalLine],
) -> list[SanitizedSubmittalLine]:
    if isinstance(payload, list):
        return payload
    lines = []
    for index, (key, value) in enumerate(payload.items(), start=1):
        lines.append(
            SanitizedSubmittalLine(
                source_key=normalize_source_key(str(key)),
                source_value=str(value).strip(),
                line_number=index,
            )
        )
    return lines


def _build_field_value(
    line: SanitizedSubmittalLine,
    rule: SubmittalFieldRule,
    source_id: str,
) -> FieldValue:
    value, observed_unit = _normalize_value(line.source_value)
    unit = rule.unit or observed_unit
    confidence = rule.confidence
    status = "review_required"
    blocked_reason = None
    if rule.source_key == "HEADER_WALL_SCHEDULE":
        # Resolve the per-value confidence tier and block unknowns. The review gate stays
        # hardcoded (review_required=True). Function-local import: pdf_intake imports this
        # module, so a top-level import would be circular.
        from coilforge.submittal.pdf_intake import (
            _normalize_header_wall_schedule,
            header_wall_schedule_confidence,
        )

        canonical = _normalize_header_wall_schedule(line.source_value)
        confidence = header_wall_schedule_confidence(line.source_value)
        if canonical is None:
            value = None
            status = "blocked"
            blocked_reason = "Unrecognized header wall schedule source; no approved (L)/(K) mapping."
        else:
            value = canonical
    evidence = _build_source_evidence(
        line,
        source_id,
        normalized_value=value,
        unit=unit,
        confidence=confidence,
        notes=[rule.review_note],
    )
    return FieldValue(
        value=value,
        unit=unit,
        source_evidence=[evidence],
        confidence=confidence,
        status=status,
        review_required=True,
        blocked_reason=blocked_reason,
        manual_override=False,
        notes=[rule.review_note],
    )


def _build_unmapped_field(
    line: SanitizedSubmittalLine,
    source_id: str,
) -> UnmappedField:
    evidence = _build_source_evidence(
        line,
        source_id,
        normalized_value=None,
        unit=None,
        confidence="ambiguous",
        notes=["No approved Phase 2B.9 intake mapping rule."],
    )
    return UnmappedField(
        source_key=normalize_source_key(line.source_key),
        source_value=line.source_value,
        reason="No approved Phase 2B.9 intake mapping rule.",
        source_evidence=[evidence],
    )


def _build_source_evidence(
    line: SanitizedSubmittalLine,
    source_id: str,
    *,
    normalized_value: Any,
    unit: str | None,
    confidence: str,
    notes: list[str],
) -> SourceEvidence:
    source_key = normalize_source_key(line.source_key)
    return SourceEvidence(
        evidence_id=f"EV-INTAKE-{source_key}-{line.line_number}",
        source_type="submittal_pdf_candidate",
        source_id=source_id,
        source_location=line.source_location or f"sanitized-text-line-{line.line_number}",
        source_page=line.source_page,
        source_section=line.source_section,
        source_table=None,
        source_key=source_key,
        source_value=line.source_value,
        normalized_value=normalized_value,
        unit=unit,
        confidence=confidence,
        review_status="unreviewed",
        evidence_status="candidate",
        notes=notes,
    )


def _normalize_value(raw_value: str) -> tuple[Any, str | None]:
    mixed_fraction_match = _MIXED_FRACTION_UNIT_PATTERN.match(raw_value)
    if mixed_fraction_match is not None and int(mixed_fraction_match.group(3)) != 0:
        whole = int(mixed_fraction_match.group(1))
        numerator = int(mixed_fraction_match.group(2))
        denominator = int(mixed_fraction_match.group(3))
        sign = -1 if whole < 0 else 1
        value = whole + sign * (numerator / denominator)
        return value, _normalize_observed_unit(mixed_fraction_match.group(4))

    match = _NUMBER_UNIT_PATTERN.match(raw_value)
    if match is not None:
        numeric = float(match.group(1))
        value: int | float = int(numeric) if numeric.is_integer() else numeric
        return value, _normalize_observed_unit(match.group(2))

    fraction_match = _FRACTION_UNIT_PATTERN.match(raw_value)
    if fraction_match is not None and int(fraction_match.group(2)) != 0:
        value = int(fraction_match.group(1)) / int(fraction_match.group(2))
        return value, _normalize_observed_unit(fraction_match.group(3))
    return raw_value.strip(), None


def _normalize_observed_unit(unit: str | None) -> str | None:
    if unit in (None, ""):
        return None
    normalized = unit.strip()
    if normalized in {'"', "in", "inch", "inches"}:
        return "in"
    return normalized


def _apply_inference_defaults(candidate_payload: dict[str, Any], source_id: str) -> None:
    if candidate_payload["product_type"] is None and candidate_payload["coil_type"] is not None:
        candidate_payload["product_type"] = _inferred_classification(
            "PRODUCT_TYPE",
            "DX",
            "Product type inferred from sanitized coil type candidate.",
            source_id,
        )
        candidate_payload["review_required_fields"].append("product_type")

    if candidate_payload["coil_type"] is None and candidate_payload["product_type"] is not None:
        product_value = candidate_payload["product_type"].value
        inferred = (
            "DX_HEADER1_WORKFLOW_CANDIDATE"
            if str(product_value).upper() == "DX"
            else "UNKNOWN"
        )
        candidate_payload["coil_type"] = _inferred_classification(
            "COIL_TYPE",
            inferred,
            "Coil type inferred from sanitized product type candidate.",
            source_id,
        )
        candidate_payload["review_required_fields"].append("coil_type")

    if candidate_payload["header_type"] is None:
        candidate_payload["header_type"] = FieldValue(
            value=None,
            unit=None,
            source_evidence=[],
            confidence="missing",
            status="review_required",
            review_required=True,
            notes=["Header type missing from sanitized intake input."],
        )
        candidate_payload["review_required_fields"].append("header_type")


def _inferred_classification(
    source_key: str,
    value: str,
    note: str,
    source_id: str,
) -> FieldValue:
    line = SanitizedSubmittalLine(source_key=source_key, source_value=value, line_number=0)
    evidence = _build_source_evidence(
        line,
        source_id,
        normalized_value=value,
        unit=None,
        confidence="inferred",
        notes=[note],
    )
    return FieldValue(
        value=value,
        unit=None,
        source_evidence=[evidence],
        confidence="inferred",
        status="review_required",
        review_required=True,
        notes=[note],
    )
