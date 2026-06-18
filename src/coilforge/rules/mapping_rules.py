from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from coilforge.adapters.ez_to_canonical import EZ_FIELD_RULES
from coilforge.direct_coil.from_canonical import map_canonical_to_direct_coil_draft
from coilforge.drawing.from_direct_coil import create_drawing_intent_from_direct_coil
from coilforge.interfaces.direct_coil import DIRECT_COIL_FIELD_REGISTRY
from coilforge.submittal.rules import SUBMITTAL_FIELD_RULES
from coilforge.validation import CANONICAL_DIRECT_COIL_FIELD_MAP


RuleType = Literal[
    "submittal_to_canonical",
    "ez_to_canonical",
    "canonical_to_direct_coil",
    "direct_coil_to_drawing_intent",
    "canonical_to_drawing_intent",
]

ApprovalStatus = Literal[
    "draft",
    "review_required",
    "approved",
    "deprecated",
    "blocked",
]


@dataclass(frozen=True)
class MappingRule:
    rule_id: str
    rule_type: RuleType
    source_system: str
    source_field: str
    canonical_path: str | None
    target_system: str
    target_field: str
    unit_policy: str
    conversion_policy: str
    confidence_policy: str
    review_policy: str
    approval_status: ApprovalStatus
    approved_by: str | None
    notes: tuple[str, ...]
    fixture_refs: tuple[str, ...]


SANITIZED_FIXTURE_REFS = (
    "examples/sanitized/submittal_candidate_dx_header1_default.json",
    "examples/sanitized/dx_header1_ezc0001_default.json",
)

DIRECT_TO_DRAWING_INTENT_FIELDS: dict[str, str] = {
    "header_type": "header_type",
    "airflow_direction": "airflow_direction",
    "finned_height": "finned_height",
    "finned_length": "finned_length",
    "rows_deep": "rows_deep",
    "fins_per_inch": "fins_per_inch",
    "tubes_high": "tubes_high",
    "coil_hand": "coil_hand",
    "return_connection_size": "return_connection_size",
}


def build_initial_mapping_rules() -> tuple[MappingRule, ...]:
    rules = [
        *_submittal_to_canonical_rules(),
        *_ez_to_canonical_rules(),
        *_canonical_to_direct_coil_rules(),
        *_direct_coil_to_drawing_intent_rules(),
        *_canonical_to_drawing_intent_rules(),
    ]
    return tuple(rules)


def _submittal_to_canonical_rules() -> list[MappingRule]:
    return [
        MappingRule(
            rule_id=f"SUBMITTAL_CANONICAL_{source_key}",
            rule_type="submittal_to_canonical",
            source_system="submittal",
            source_field=source_key,
            canonical_path=_canonical_path(rule.target, rule.target_key),
            target_system="canonical",
            target_field=_canonical_path(rule.target, rule.target_key),
            unit_policy=_unit_policy(rule.unit),
            conversion_policy=_conversion_policy(rule.unit),
            confidence_policy=rule.confidence,
            review_policy=rule.review_note,
            approval_status="review_required",
            approved_by=None,
            notes=("Sanitized submittal candidate mapping; not a PDF parser rule.",),
            fixture_refs=(SANITIZED_FIXTURE_REFS[0],),
        )
        for source_key, rule in SUBMITTAL_FIELD_RULES.items()
    ]


def _ez_to_canonical_rules() -> list[MappingRule]:
    return [
        MappingRule(
            rule_id=f"EZ_CANONICAL_{source_key.upper()}",
            rule_type="ez_to_canonical",
            source_system="ez_json",
            source_field=source_key,
            canonical_path=_canonical_path(rule.target, rule.target_key or rule.target),
            target_system="canonical",
            target_field=_canonical_path(rule.target, rule.target_key or rule.target),
            unit_policy=_unit_policy(rule.unit),
            conversion_policy=_conversion_policy(rule.unit),
            confidence_policy=rule.confidence,
            review_policy=rule.review_note,
            approval_status="review_required",
            approved_by=None,
            notes=("Sanitized EZ reference mapping; not final engineering approval.",),
            fixture_refs=(SANITIZED_FIXTURE_REFS[1],),
        )
        for source_key, rule in EZ_FIELD_RULES.items()
    ]


def _canonical_to_direct_coil_rules() -> list[MappingRule]:
    return [
        MappingRule(
            rule_id=f"CANONICAL_DIRECT_{field_key}",
            rule_type="canonical_to_direct_coil",
            source_system="canonical",
            source_field=canonical_path,
            canonical_path=canonical_path,
            target_system="direct_coil",
            target_field=field_key,
            unit_policy=_unit_policy(DIRECT_COIL_FIELD_REGISTRY[field_key].unit),
            conversion_policy=_conversion_policy(DIRECT_COIL_FIELD_REGISTRY[field_key].unit),
            confidence_policy="preserve_field_confidence",
            review_policy=DIRECT_COIL_FIELD_REGISTRY[field_key].review_policy,
            approval_status="review_required",
            approved_by=None,
            notes=(
                "Direct Coil draft values remain review-only and export is not implemented.",
            ),
            fixture_refs=SANITIZED_FIXTURE_REFS,
        )
        for field_key, canonical_path in CANONICAL_DIRECT_COIL_FIELD_MAP.items()
    ]


def _direct_coil_to_drawing_intent_rules() -> list[MappingRule]:
    return [
        MappingRule(
            rule_id=f"DIRECT_DRAWING_INTENT_{field_key}",
            rule_type="direct_coil_to_drawing_intent",
            source_system="direct_coil",
            source_field=field_key,
            canonical_path=CANONICAL_DIRECT_COIL_FIELD_MAP.get(field_key),
            target_system="drawing_intent",
            target_field=target_field,
            unit_policy=_unit_policy(DIRECT_COIL_FIELD_REGISTRY[field_key].unit),
            conversion_policy=_conversion_policy(DIRECT_COIL_FIELD_REGISTRY[field_key].unit),
            confidence_policy="preserve_direct_coil_status",
            review_policy="drawing_intent_review_aid_only",
            approval_status="review_required",
            approved_by=None,
            notes=(
                f"Implemented through {create_drawing_intent_from_direct_coil.__name__}; export remains disabled.",
            ),
            fixture_refs=SANITIZED_FIXTURE_REFS,
        )
        for field_key, target_field in DIRECT_TO_DRAWING_INTENT_FIELDS.items()
    ]


def _canonical_to_drawing_intent_rules() -> list[MappingRule]:
    return [
        MappingRule(
            rule_id=f"CANONICAL_DRAWING_INTENT_{field_key}",
            rule_type="canonical_to_drawing_intent",
            source_system="canonical",
            source_field=canonical_path,
            canonical_path=canonical_path,
            target_system="drawing_intent",
            target_field=target_field,
            unit_policy=_unit_policy(DIRECT_COIL_FIELD_REGISTRY[field_key].unit),
            conversion_policy=_conversion_policy(DIRECT_COIL_FIELD_REGISTRY[field_key].unit),
            confidence_policy="requires_canonical_review_state",
            review_policy="bridge_via_direct_coil_draft_review_aid_only",
            approval_status="draft",
            approved_by=None,
            notes=(
                f"Documented bridge through {map_canonical_to_direct_coil_draft.__name__}; no direct export path.",
            ),
            fixture_refs=SANITIZED_FIXTURE_REFS,
        )
        for field_key, target_field in DIRECT_TO_DRAWING_INTENT_FIELDS.items()
        for canonical_path in (CANONICAL_DIRECT_COIL_FIELD_MAP[field_key],)
    ]


def _canonical_path(target: str, target_key: str) -> str:
    if target in {"tag", "product_type", "coil_type", "header_type"}:
        return target
    return f"{target}.{target_key}"


def _unit_policy(unit: str | None) -> str:
    if unit is None:
        return "not_applicable_text_or_enum"
    return f"source_unit_must_match_expected_unit:{unit}"


def _conversion_policy(unit: str | None) -> str:
    if unit is None:
        return "not_applicable_no_numeric_conversion"
    return "blocked_without_explicit_conversion_rule"
