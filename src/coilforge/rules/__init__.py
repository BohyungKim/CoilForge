"""Centralized CoilForge mapping rule registry."""

from coilforge.rules.registry import (
    MappingRule,
    MappingRuleLookupResult,
    MappingRuleRegistry,
    MappingRuleSummary,
    find_mapping_rules,
    get_mapping_rule,
    is_rule_approved,
    list_mapping_rules,
    load_mapping_rule_registry,
)

__all__ = [
    "MappingRule",
    "MappingRuleLookupResult",
    "MappingRuleRegistry",
    "MappingRuleSummary",
    "find_mapping_rules",
    "get_mapping_rule",
    "is_rule_approved",
    "list_mapping_rules",
    "load_mapping_rule_registry",
]
