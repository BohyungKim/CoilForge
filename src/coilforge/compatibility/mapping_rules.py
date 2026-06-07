from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from coilforge.adapters.ez_to_canonical import EZ_FIELD_RULES
from coilforge.submittal.rules import SUBMITTAL_FIELD_RULES
from coilforge.validation import CANONICAL_DIRECT_COIL_FIELD_MAP


MappingCoverage = Literal[
    "both_sources",
    "submittal_only",
    "ez_only",
    "unmapped",
]

MappingApprovalStatus = Literal[
    "not_approved_review_required",
    "not_mapped",
]


@dataclass(frozen=True)
class SourceMappingRule:
    field_key: str
    canonical_path: str
    coverage: MappingCoverage
    approval_status: MappingApprovalStatus
    submittal_source_keys: tuple[str, ...]
    ez_source_keys: tuple[str, ...]
    review_required: bool
    note: str


@dataclass(frozen=True)
class MappingRuleRegistrySummary:
    total_direct_coil_fields: int
    both_sources: int
    submittal_only: int
    ez_only: int
    unmapped: int
    approved: int
    review_required: int


@dataclass(frozen=True)
class MappingRuleRegistry:
    rules: tuple[SourceMappingRule, ...]
    summary: MappingRuleRegistrySummary

    def by_field_key(self) -> dict[str, SourceMappingRule]:
        return {rule.field_key: rule for rule in self.rules}


def build_mapping_rule_registry() -> MappingRuleRegistry:
    """Build the Phase 2C review registry from current source mapping rules."""

    submittal_by_path = _submittal_source_keys_by_canonical_path()
    ez_by_path = _ez_source_keys_by_canonical_path()
    rules = tuple(
        _build_rule(field_key, canonical_path, submittal_by_path, ez_by_path)
        for field_key, canonical_path in CANONICAL_DIRECT_COIL_FIELD_MAP.items()
    )
    return MappingRuleRegistry(
        rules=rules,
        summary=_summarize(rules),
    )


def _build_rule(
    field_key: str,
    canonical_path: str,
    submittal_by_path: dict[str, list[str]],
    ez_by_path: dict[str, list[str]],
) -> SourceMappingRule:
    submittal_keys = tuple(submittal_by_path.get(canonical_path, []))
    ez_keys = tuple(ez_by_path.get(canonical_path, []))
    if submittal_keys and ez_keys:
        coverage: MappingCoverage = "both_sources"
    elif submittal_keys:
        coverage = "submittal_only"
    elif ez_keys:
        coverage = "ez_only"
    else:
        coverage = "unmapped"

    approval_status: MappingApprovalStatus = (
        "not_mapped" if coverage == "unmapped" else "not_approved_review_required"
    )
    return SourceMappingRule(
        field_key=field_key,
        canonical_path=canonical_path,
        coverage=coverage,
        approval_status=approval_status,
        submittal_source_keys=submittal_keys,
        ez_source_keys=ez_keys,
        review_required=approval_status == "not_approved_review_required",
        note=_note(coverage),
    )


def _submittal_source_keys_by_canonical_path() -> dict[str, list[str]]:
    by_path: dict[str, list[str]] = {}
    for source_key, rule in SUBMITTAL_FIELD_RULES.items():
        canonical_path = _canonical_path(rule.target, rule.target_key)
        by_path.setdefault(canonical_path, []).append(source_key)
    return by_path


def _ez_source_keys_by_canonical_path() -> dict[str, list[str]]:
    by_path: dict[str, list[str]] = {}
    for source_key, rule in EZ_FIELD_RULES.items():
        target_key = rule.target_key or rule.target
        canonical_path = _canonical_path(rule.target, target_key)
        by_path.setdefault(canonical_path, []).append(source_key)
    return by_path


def _canonical_path(target: str, target_key: str) -> str:
    if target in {"tag", "product_type", "coil_type", "header_type"}:
        return target
    return f"{target}.{target_key}"


def _summarize(rules: tuple[SourceMappingRule, ...]) -> MappingRuleRegistrySummary:
    coverage_counts = {
        "both_sources": 0,
        "submittal_only": 0,
        "ez_only": 0,
        "unmapped": 0,
    }
    review_required = 0
    approved = 0
    for rule in rules:
        coverage_counts[rule.coverage] += 1
        if rule.review_required:
            review_required += 1
        if rule.approval_status == "not_approved_review_required":
            continue
    return MappingRuleRegistrySummary(
        total_direct_coil_fields=len(rules),
        both_sources=coverage_counts["both_sources"],
        submittal_only=coverage_counts["submittal_only"],
        ez_only=coverage_counts["ez_only"],
        unmapped=coverage_counts["unmapped"],
        approved=approved,
        review_required=review_required,
    )


def _note(coverage: MappingCoverage) -> str:
    notes = {
        "both_sources": "Both sanitized source paths map this Direct Coil field, but approval is still required.",
        "submittal_only": "Only the sanitized submittal path maps this Direct Coil field.",
        "ez_only": "Only the sanitized EZ path maps this Direct Coil field.",
        "unmapped": "No current sanitized source mapping rule reaches this Direct Coil field.",
    }
    return notes[coverage]
