from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CandidateFieldTarget = Literal[
    "tag",
    "quantity",
    "product_type",
    "coil_type",
    "header_type",
    "geometry",
    "airside_conditions",
    "refrigerant_conditions",
    "materials_construction",
    "connections",
    "manufacturing_options",
    "performance",
    "drawing_parameters",
]


@dataclass(frozen=True)
class SubmittalFieldRule:
    source_key: str
    target: CandidateFieldTarget
    target_key: str
    unit: str | None = None
    confidence: str = "confirmed"
    review_note: str = "Sanitized intake value requires review."


SUBMITTAL_FIELD_RULES: dict[str, SubmittalFieldRule] = {
    "COIL_TAG": SubmittalFieldRule("COIL_TAG", "tag", "tag", confidence="confirmed"),
    "TAG": SubmittalFieldRule("TAG", "tag", "tag", confidence="confirmed"),
    "PRODUCT_TYPE": SubmittalFieldRule(
        "PRODUCT_TYPE",
        "product_type",
        "product_type",
        confidence="inferred",
        review_note="Product type is a candidate until reviewed.",
    ),
    "COIL_TYPE": SubmittalFieldRule(
        "COIL_TYPE",
        "coil_type",
        "coil_type",
        confidence="inferred",
        review_note="Coil type is not final engineering classification.",
    ),
    "HEADER_TYPE": SubmittalFieldRule(
        "HEADER_TYPE",
        "header_type",
        "header_type",
        confidence="inferred",
        review_note="Header type is a candidate until reviewed.",
    ),
    "ROWS_DEEP": SubmittalFieldRule("ROWS_DEEP", "geometry", "rows_deep", "rows"),
    "FINS_PER_INCH": SubmittalFieldRule("FINS_PER_INCH", "geometry", "fins_per_inch", "fpi"),
    "FINNED_HEIGHT": SubmittalFieldRule("FINNED_HEIGHT", "geometry", "finned_height", "in"),
    "FINNED_LENGTH": SubmittalFieldRule("FINNED_LENGTH", "geometry", "finned_length", "in"),
    "AIRFLOW_DIRECTION": SubmittalFieldRule(
        "AIRFLOW_DIRECTION",
        "geometry",
        "airflow_direction",
        confidence="inferred",
        review_note="Airflow direction must be confirmed before draft use.",
    ),
    "TOTAL_AIR_FLOW_CFM": SubmittalFieldRule(
        "TOTAL_AIR_FLOW_CFM",
        "airside_conditions",
        "total_air_flow_cfm",
        "cfm",
    ),
    "ENTERING_DRY_BULB_F": SubmittalFieldRule(
        "ENTERING_DRY_BULB_F",
        "airside_conditions",
        "entering_dry_bulb_f",
        "degF",
    ),
    "REFRIGERANT": SubmittalFieldRule("REFRIGERANT", "refrigerant_conditions", "refrigerant"),
    "COIL_HAND": SubmittalFieldRule(
        "COIL_HAND",
        "connections",
        "coil_hand",
        confidence="inferred",
    ),
    "RETURN_CONNECTION_SIZE": SubmittalFieldRule(
        "RETURN_CONNECTION_SIZE",
        "connections",
        "return_connection_size",
        "in",
        confidence="ambiguous",
        review_note="Connection role needs review.",
    ),
    "TOTAL_CAPACITY_MBH": SubmittalFieldRule(
        "TOTAL_CAPACITY_MBH",
        "performance",
        "total_capacity_mbh",
        "MBH",
        confidence="ambiguous",
        review_note="Capacity basis requires review.",
    ),
}


SUPPORTED_SANITIZED_TEXT_PREFIXES: tuple[str, ...] = tuple(SUBMITTAL_FIELD_RULES)


def normalize_source_key(source_key: str) -> str:
    return source_key.strip().upper().replace(" ", "_").replace("-", "_")


def get_submittal_field_rule(source_key: str) -> SubmittalFieldRule | None:
    return SUBMITTAL_FIELD_RULES.get(normalize_source_key(source_key))
