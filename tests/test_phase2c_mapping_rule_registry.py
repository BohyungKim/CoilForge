from __future__ import annotations

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.compatibility import build_mapping_rule_registry


def test_mapping_rule_registry_covers_all_direct_coil_fields() -> None:
    registry = build_mapping_rule_registry()

    assert registry.summary.total_direct_coil_fields == 52
    assert len(registry.rules) == 52
    assert registry.summary.approved == 0
    assert registry.summary.review_required == 18


def test_registry_identifies_both_source_compatibility_fields() -> None:
    by_field = build_mapping_rule_registry().by_field_key()

    rows = by_field["rows_deep"]
    assert rows.coverage == "both_sources"
    assert rows.approval_status == "not_approved_review_required"
    assert rows.submittal_source_keys == ("ROWS_DEEP",)
    assert rows.ez_source_keys == ("rows",)

    header = by_field["header_type"]
    assert header.coverage == "both_sources"
    assert header.review_required is True


def test_registry_marks_source_only_and_unmapped_fields() -> None:
    by_field = build_mapping_rule_registry().by_field_key()

    assert by_field["CD"].coverage == "ez_only"
    assert by_field["CD"].ez_source_keys == ("casing_depth",)
    assert by_field["total_air_flow_cfm"].coverage == "submittal_only"
    assert by_field["tube_material"].coverage == "unmapped"
    assert by_field["tube_material"].approval_status == "not_mapped"


def test_registry_summary_matches_current_sanitized_rule_coverage() -> None:
    summary = build_mapping_rule_registry().summary

    assert summary.both_sources == 8
    assert summary.submittal_only == 4
    assert summary.ez_only == 6
    assert summary.unmapped == 34
