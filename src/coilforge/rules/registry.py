from __future__ import annotations

from dataclasses import dataclass

from coilforge.rules.mapping_rules import (
    ApprovalStatus,
    MappingRule,
    RuleType,
    build_initial_mapping_rules,
)


@dataclass(frozen=True)
class MappingRuleLookupResult:
    found: bool
    rule: MappingRule | None
    reason: str


@dataclass(frozen=True)
class MappingRuleSummary:
    total_rules: int
    by_rule_type: dict[str, int]
    by_approval_status: dict[str, int]
    approved_count: int
    review_required_count: int
    blocked_count: int


@dataclass(frozen=True)
class MappingRuleRegistry:
    registry_id: str
    schema_version: str
    rules: tuple[MappingRule, ...]
    summary: MappingRuleSummary

    def by_rule_id(self) -> dict[str, MappingRule]:
        return {rule.rule_id: rule for rule in self.rules}


def load_mapping_rule_registry() -> MappingRuleRegistry:
    rules = build_initial_mapping_rules()
    return MappingRuleRegistry(
        registry_id="coilforge-phase2c4-mapping-rule-registry",
        schema_version="phase2c.4",
        rules=rules,
        summary=_summarize(rules),
    )


def list_mapping_rules(
    *,
    rule_type: RuleType | None = None,
    approval_status: ApprovalStatus | None = None,
) -> tuple[MappingRule, ...]:
    return tuple(
        rule
        for rule in load_mapping_rule_registry().rules
        if (rule_type is None or rule.rule_type == rule_type)
        and (approval_status is None or rule.approval_status == approval_status)
    )


def get_mapping_rule(rule_id: str) -> MappingRuleLookupResult:
    rule = load_mapping_rule_registry().by_rule_id().get(rule_id)
    if rule is None:
        return MappingRuleLookupResult(
            found=False,
            rule=None,
            reason="No mapping rule exists; caller must treat lookup as review_required or blocked.",
        )
    return MappingRuleLookupResult(found=True, rule=rule, reason="Mapping rule found.")


def find_mapping_rules(
    *,
    rule_type: RuleType | None = None,
    source_system: str | None = None,
    source_field: str | None = None,
    canonical_path: str | None = None,
    target_system: str | None = None,
    target_field: str | None = None,
) -> tuple[MappingRule, ...]:
    return tuple(
        rule
        for rule in load_mapping_rule_registry().rules
        if (rule_type is None or rule.rule_type == rule_type)
        and (source_system is None or rule.source_system == source_system)
        and (source_field is None or rule.source_field == source_field)
        and (canonical_path is None or rule.canonical_path == canonical_path)
        and (target_system is None or rule.target_system == target_system)
        and (target_field is None or rule.target_field == target_field)
    )


def is_rule_approved(rule: MappingRule) -> bool:
    return rule.approval_status == "approved" and bool(rule.approved_by)


def _summarize(rules: tuple[MappingRule, ...]) -> MappingRuleSummary:
    by_rule_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for rule in rules:
        by_rule_type[rule.rule_type] = by_rule_type.get(rule.rule_type, 0) + 1
        by_status[rule.approval_status] = by_status.get(rule.approval_status, 0) + 1
    return MappingRuleSummary(
        total_rules=len(rules),
        by_rule_type=by_rule_type,
        by_approval_status=by_status,
        approved_count=by_status.get("approved", 0),
        review_required_count=by_status.get("review_required", 0),
        blocked_count=by_status.get("blocked", 0),
    )
