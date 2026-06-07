"""Review-only compatibility comparison helpers."""

from coilforge.compatibility.mapping_rules import (
    MappingRuleRegistry,
    MappingRuleRegistrySummary,
    SourceMappingRule,
    build_mapping_rule_registry,
)
from coilforge.compatibility.decision_matrix import (
    FieldDecisionItem,
    FieldDecisionMatrix,
    build_field_decision_matrix,
)
from coilforge.compatibility.decision_review import (
    DecisionMatrixReviewSurface,
    DecisionReviewItem,
    build_decision_matrix_review_surface,
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
    "FieldDecisionItem",
    "FieldDecisionMatrix",
    "DecisionMatrixReviewSurface",
    "DecisionReviewItem",
    "MappingRuleRegistry",
    "MappingRuleRegistrySummary",
    "ReconciliationDecision",
    "ReconciliationPlan",
    "ReconciliationSummary",
    "SourceMappingRule",
    "build_mapping_rule_registry",
    "build_field_decision_matrix",
    "build_decision_matrix_review_surface",
    "build_compatibility_diff_review_packet",
    "build_reconciliation_plan",
    "compare_submittal_and_ez",
]
