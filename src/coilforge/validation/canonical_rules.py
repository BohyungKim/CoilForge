from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from coilforge.contracts.canonical import CanonicalCoilRecord
from coilforge.contracts.field_value import FieldValue
from coilforge.interfaces.direct_coil import (
    DIRECT_COIL_FIELD_REGISTRY,
    REQUIRED_DIRECT_COIL_FIELDS,
    is_header_type_supported,
)


CANONICAL_REQUIRED_GROUPS: tuple[str, ...] = (
    "project",
    "coil_identity",
    "product_type",
    "coil_type",
    "header_type",
    "geometry",
    "airside_conditions",
    "refrigerant_conditions",
    "materials_construction",
    "connections",
    "manufacturing_options",
    "drawing_parameters",
    "performance",
)

CANONICAL_DIRECT_COIL_FIELD_MAP: dict[str, str] = {
    "tube_diameter_od": "geometry.tube_diameter_od",
    "tube_geometry": "geometry.tube_geometry",
    "rows_deep": "geometry.rows_deep",
    "fins_per_inch": "geometry.fins_per_inch",
    "tubes_high": "geometry.tubes_high",
    "finned_height": "geometry.finned_height",
    "finned_length": "geometry.finned_length",
    "number_of_feeds": "geometry.number_of_feeds",
    "airflow_direction": "geometry.airflow_direction",
    "header_type": "header_type",
    "tube_material": "materials_construction.tube_material",
    "fin_material": "materials_construction.fin_material",
    "fin_surface": "materials_construction.fin_surface",
    "header_material": "materials_construction.header_material",
    "connection_material": "connections.connection_material",
    "connection_type": "connections.connection_type",
    "supply_connection_size": "connections.supply_connection_size",
    "return_connection_size": "connections.return_connection_size",
    "casing_material": "materials_construction.casing_material",
    "casing_style": "materials_construction.casing_style",
    "connection_ends": "connections.connection_ends",
    "coil_hand": "connections.coil_hand",
    "total_air_flow_cfm": "airside_conditions.total_air_flow_cfm",
    "face_velocity_fpm": "airside_conditions.face_velocity_fpm",
    "altitude_ft": "airside_conditions.altitude_ft",
    "entering_dry_bulb_f": "airside_conditions.entering_dry_bulb_f",
    "entering_wet_bulb_f": "airside_conditions.entering_wet_bulb_f",
    "leaving_dry_bulb_f": "airside_conditions.leaving_dry_bulb_f",
    "relative_humidity_pct": "airside_conditions.relative_humidity_pct",
    "total_capacity_mbh": "performance.total_capacity_mbh",
    "refrigerant": "refrigerant_conditions.refrigerant",
    "evaporating_temp_f": "refrigerant_conditions.evaporating_temp_f",
    "liquid_temp_f": "refrigerant_conditions.liquid_temp_f",
    "superheat_f": "refrigerant_conditions.superheat_f",
    "dx_dist_capillary_size": "refrigerant_conditions.dx_dist_capillary_size",
    "drain_pan_type": "manufacturing_options.drain_pan_type",
    "coil_coating": "manufacturing_options.coil_coating",
    "system_type": "manufacturing_options.system_type",
    "distributor_notes": "manufacturing_options.distributor_notes",
    "CD": "drawing_parameters.CD",
    "I": "drawing_parameters.I",
    "S": "drawing_parameters.S",
    "O": "drawing_parameters.O",
    "R": "drawing_parameters.R",
    "BF": "drawing_parameters.BF",
    "HD": "drawing_parameters.HD",
    "HF": "drawing_parameters.HF",
    "TF": "drawing_parameters.TF",
    "RF": "drawing_parameters.RF",
    "CH": "drawing_parameters.CH",
    "SL": "drawing_parameters.SL",
    "ZD": "drawing_parameters.ZD",
}


@dataclass(frozen=True)
class CanonicalValidationResult:
    validation_status: str
    review_required_fields: tuple[str, ...]
    blocked_fields: tuple[str, ...]


def get_direct_coil_canonical_path(field_key: str) -> str:
    return CANONICAL_DIRECT_COIL_FIELD_MAP[field_key]


def validate_canonical_record(record: CanonicalCoilRecord) -> CanonicalValidationResult:
    review_required_fields = list(dict.fromkeys(record.review_required_fields))
    blocked_fields = list(dict.fromkeys(record.blocked_fields))

    for field_key in REQUIRED_DIRECT_COIL_FIELDS:
        canonical_path = get_direct_coil_canonical_path(field_key)
        field_value = _get_record_field_value(record, canonical_path)
        definition = DIRECT_COIL_FIELD_REGISTRY[field_key]

        if field_value is None or field_value.value in (None, ""):
            blocked_fields.append(canonical_path)
            continue

        if definition.unit and field_value.unit in (None, ""):
            if definition.required:
                blocked_fields.append(canonical_path)
            else:
                review_required_fields.append(canonical_path)

        if definition.source_required and not field_value.source_evidence:
            blocked_fields.append(canonical_path)

    if record.header_type is not None and record.header_type.value not in (None, ""):
        if not is_header_type_supported(str(record.header_type.value)):
            blocked_fields.append("header_type")

    for field_name in ("product_type", "coil_type", "header_type"):
        field_value = getattr(record, field_name)
        if field_value is not None and _is_inferred_or_unreviewed(field_value):
            review_required_fields.append(field_name)

    for field_key, canonical_path in CANONICAL_DIRECT_COIL_FIELD_MAP.items():
        field_value = _get_record_field_value(record, canonical_path)
        if field_value is None:
            continue
        definition = DIRECT_COIL_FIELD_REGISTRY[field_key]
        if definition.unit and field_value.value not in (None, "") and field_value.unit in (None, ""):
            if definition.required:
                blocked_fields.append(canonical_path)
            else:
                review_required_fields.append(canonical_path)
        if field_value.review_required:
            review_required_fields.append(canonical_path)
        if field_value.status == "blocked":
            blocked_fields.append(canonical_path)

    blocked = tuple(dict.fromkeys(blocked_fields))
    review_required = tuple(dict.fromkeys(review_required_fields))
    if blocked:
        status = "blocked"
    elif review_required:
        status = "review_required"
    else:
        status = "validated"

    return CanonicalValidationResult(
        validation_status=status,
        review_required_fields=review_required,
        blocked_fields=blocked,
    )


def apply_canonical_validation(record: CanonicalCoilRecord) -> CanonicalCoilRecord:
    result = validate_canonical_record(record)
    return record.model_copy(
        update={
            "validation_status": result.validation_status,
            "review_required_fields": list(result.review_required_fields),
            "blocked_fields": list(result.blocked_fields),
        }
    )


def _get_record_field_value(record: CanonicalCoilRecord, canonical_path: str) -> FieldValue | None:
    if "." not in canonical_path:
        value = getattr(record, canonical_path)
        return value if isinstance(value, FieldValue) else None
    group_name, field_key = canonical_path.split(".", 1)
    group = getattr(record, group_name)
    if not isinstance(group, dict):
        return None
    value = group.get(field_key)
    return value if isinstance(value, FieldValue) else None


def _is_inferred_or_unreviewed(field_value: FieldValue) -> bool:
    evidence_review_statuses = {
        evidence.review_status for evidence in field_value.source_evidence
    }
    return (
        field_value.confidence in {"inferred", "ambiguous", "missing"}
        or field_value.status == "review_required"
        or "unreviewed" in evidence_review_statuses
    )
