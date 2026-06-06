from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.interfaces.direct_coil import (
    DIRECT_COIL_FIELD_GROUPS,
    DIRECT_COIL_FIELD_REGISTRY,
    DIRECT_COIL_SOURCE_TRACE_POLICY,
    DRAWING_PARAMETER_FIELD_KEYS,
    DRAWING_PARAMETER_MODE_VALUES,
    MANUAL_OVERRIDE_POLICY,
    REQUIRED_DIRECT_COIL_FIELDS,
    get_field,
    get_fields_by_group,
    is_header_type_supported,
)


def test_field_registry_loads() -> None:
    assert DIRECT_COIL_FIELD_REGISTRY
    assert get_field("header_type").label == "Header type"


def test_required_groups_exist() -> None:
    for group in DIRECT_COIL_FIELD_GROUPS:
        assert get_fields_by_group(group), group


def test_required_fields_are_defined() -> None:
    assert {
        "rows_deep",
        "fins_per_inch",
        "finned_height",
        "finned_length",
        "airflow_direction",
        "header_type",
        "return_connection_size",
        "coil_hand",
    }.issubset(set(REQUIRED_DIRECT_COIL_FIELDS))


def test_units_exist_for_dimensional_and_performance_fields() -> None:
    unit_required_fields = [
        "tube_diameter_od",
        "rows_deep",
        "fins_per_inch",
        "finned_height",
        "finned_length",
        "return_connection_size",
        "total_air_flow_cfm",
        "face_velocity_fpm",
        "altitude_ft",
        "entering_dry_bulb_f",
        "evaporating_temp_f",
        "CD",
    ]

    for field_key in unit_required_fields:
        assert get_field(field_key).unit, field_key


def test_drawing_parameters_exist() -> None:
    expected = {"CD", "I", "S", "O", "R", "BF", "HD", "HF", "TF", "RF", "CH", "SL", "ZD"}

    assert expected == set(DRAWING_PARAMETER_FIELD_KEYS)
    assert "auto" in DRAWING_PARAMETER_MODE_VALUES
    assert "manual" in DRAWING_PARAMETER_MODE_VALUES
    assert get_field("CD").review_policy == "auto_or_manual_review_required"


def test_unsupported_header_type_can_be_blocked() -> None:
    header = get_field("header_type")

    assert is_header_type_supported("Header 1")
    assert not is_header_type_supported("Header 2")
    assert "unsupported header_type is blocked" in header.blocked_conditions


def test_source_trace_policy_exists() -> None:
    assert (
        DIRECT_COIL_SOURCE_TRACE_POLICY["imported_or_prepopulated_values"]
        == "source_trace_required"
    )
    assert "source_type" in DIRECT_COIL_SOURCE_TRACE_POLICY["required_trace_fields"]
    assert "manual_entry" in DIRECT_COIL_SOURCE_TRACE_POLICY["allowed_source_types"]


def test_manual_override_policy_exists() -> None:
    assert MANUAL_OVERRIDE_POLICY["status"] == "manual_override"
    assert "override_reason" in MANUAL_OVERRIDE_POLICY["required_metadata"]
