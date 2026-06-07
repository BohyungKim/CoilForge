from __future__ import annotations

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.interfaces.direct_coil import REQUIRED_DIRECT_COIL_FIELDS
from coilforge.rules import (
    find_mapping_rules,
    get_mapping_rule,
    is_rule_approved,
    list_mapping_rules,
    load_mapping_rule_registry,
)


def test_mapping_rule_registry_loads() -> None:
    registry = load_mapping_rule_registry()

    assert registry.registry_id == "coilforge-phase2c4-mapping-rule-registry"
    assert registry.schema_version == "phase2c.4"
    assert registry.summary.total_rules > 80
    assert registry.summary.by_rule_type["submittal_to_canonical"] >= 16
    assert registry.summary.by_rule_type["ez_to_canonical"] >= 18
    assert registry.summary.by_rule_type["canonical_to_direct_coil"] == 52


def test_mapping_rule_ids_are_unique() -> None:
    rules = load_mapping_rule_registry().rules
    rule_ids = [rule.rule_id for rule in rules]

    assert len(rule_ids) == len(set(rule_ids))


def test_required_direct_coil_fields_have_mapping_rule_coverage() -> None:
    for field_key in REQUIRED_DIRECT_COIL_FIELDS:
        rules = find_mapping_rules(
            rule_type="canonical_to_direct_coil",
            target_system="direct_coil",
            target_field=field_key,
        )
        assert len(rules) == 1
        assert rules[0].canonical_path
        assert rules[0].approval_status == "review_required"


def test_unit_conversion_policy_is_explicit() -> None:
    numeric_rules = [
        rule
        for rule in load_mapping_rule_registry().rules
        if "expected_unit:" in rule.unit_policy
    ]

    assert numeric_rules
    assert all(
        rule.conversion_policy == "blocked_without_explicit_conversion_rule"
        for rule in numeric_rules
    )
    rows_rule = get_mapping_rule("CANONICAL_DIRECT_rows_deep").rule
    assert rows_rule is not None
    assert rows_rule.unit_policy == "source_unit_must_match_expected_unit:rows"


def test_draft_and_review_required_rules_are_not_treated_as_approved() -> None:
    registry = load_mapping_rule_registry()

    assert registry.summary.approved_count == 0
    assert list_mapping_rules(approval_status="approved") == ()
    for rule in registry.rules:
        if rule.approval_status in {"draft", "review_required"}:
            assert is_rule_approved(rule) is False


def test_unknown_rule_lookup_returns_safe_failure() -> None:
    result = get_mapping_rule("NO_SUCH_MAPPING_RULE")

    assert result.found is False
    assert result.rule is None
    assert "review_required or blocked" in result.reason


def test_registry_includes_drawing_intent_rule_types() -> None:
    registry = load_mapping_rule_registry()

    assert registry.summary.by_rule_type["direct_coil_to_drawing_intent"] >= 8
    assert registry.summary.by_rule_type["canonical_to_drawing_intent"] >= 8
    assert find_mapping_rules(
        rule_type="direct_coil_to_drawing_intent",
        source_field="finned_height",
        target_field="finned_height",
    )
