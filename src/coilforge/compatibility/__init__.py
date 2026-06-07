"""Review-only compatibility comparison helpers."""

from coilforge.compatibility.mapping_rules import (
    MappingRuleRegistry,
    MappingRuleRegistrySummary,
    SourceMappingRule,
    build_mapping_rule_registry,
)
from coilforge.compatibility.reconciliation import (
    ReconciliationDecision,
    ReconciliationPlan,
    ReconciliationSummary,
    build_reconciliation_plan,
)
from coilforge.compatibility.regression import (
    CompatibilityCategory,
    CompatibilityComparison,
    CompatibilityRegressionReport,
    CompatibilitySourceSummary,
    compare_submittal_and_ez,
)
from coilforge.compatibility.review_packet import build_compatibility_diff_review_packet

__all__ = [
    "CompatibilityComparison",
    "CompatibilityCategory",
    "CompatibilityRegressionReport",
    "CompatibilitySourceSummary",
    "MappingRuleRegistry",
    "MappingRuleRegistrySummary",
    "ReconciliationDecision",
    "ReconciliationPlan",
    "ReconciliationSummary",
    "SourceMappingRule",
    "build_mapping_rule_registry",
    "build_compatibility_diff_review_packet",
    "build_reconciliation_plan",
    "compare_submittal_and_ez",
]
