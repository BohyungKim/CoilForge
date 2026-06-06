from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


DirectCoilGroup = Literal[
    "Coil Geometry",
    "Materials & Construction",
    "Airside Conditions",
    "Refrigerant Conditions",
    "Manufacturing Options",
    "Drawing Parameters",
]


@dataclass(frozen=True)
class DirectCoilFieldDefinition:
    field_key: str
    label: str
    group: DirectCoilGroup
    data_type: str
    unit: str | None
    required: bool
    allowed_values: tuple[str, ...] = field(default_factory=tuple)
    source_required: bool = True
    review_policy: str = "review_required"
    blocked_conditions: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""


DIRECT_COIL_FIELD_GROUPS: tuple[DirectCoilGroup, ...] = (
    "Coil Geometry",
    "Materials & Construction",
    "Airside Conditions",
    "Refrigerant Conditions",
    "Manufacturing Options",
    "Drawing Parameters",
)

SUPPORTED_HEADER_TYPES = ("Header 1",)
KNOWN_FUTURE_HEADER_TYPES = ("Header 2", "Header 3", "Header 4")
AIRFLOW_DIRECTION_VALUES = ("left_to_right", "right_to_left")
COIL_HAND_VALUES = ("Left", "Right")
DRAWING_PARAMETER_MODE_VALUES = (
    "auto",
    "manual",
    "review_required",
    "blocked",
)

DIRECT_COIL_SOURCE_TRACE_POLICY = {
    "imported_or_prepopulated_values": "source_trace_required",
    "manual_entry_values": "source_trace_optional_but_entry_metadata_required",
    "required_trace_fields": (
        "source_type",
        "source_id",
        "source_location",
        "source_value",
        "normalized_value",
        "review_status",
    ),
    "allowed_source_types": (
        "manual_entry",
        "sanitized_ez_reference",
        "coilforge_json_import",
        "submittal_pdf_candidate",
    ),
    "policy": (
        "Imported and prepopulated values must preserve source evidence. "
        "Manual values must be flagged as manual_entry and kept distinct from imported values."
    ),
}

MANUAL_OVERRIDE_POLICY = {
    "status": "manual_override",
    "required_metadata": (
        "previous_value",
        "override_value",
        "override_reason",
        "reviewed_by",
        "review_status",
    ),
    "policy": (
        "Manual overrides are allowed only as explicit review decisions. "
        "They must not erase imported source evidence."
    ),
}


def _field(
    field_key: str,
    label: str,
    group: DirectCoilGroup,
    data_type: str,
    unit: str | None,
    required: bool,
    *,
    allowed_values: tuple[str, ...] = (),
    source_required: bool = True,
    review_policy: str = "review_required",
    blocked_conditions: tuple[str, ...] = (),
    notes: str = "",
) -> DirectCoilFieldDefinition:
    return DirectCoilFieldDefinition(
        field_key=field_key,
        label=label,
        group=group,
        data_type=data_type,
        unit=unit,
        required=required,
        allowed_values=allowed_values,
        source_required=source_required,
        review_policy=review_policy,
        blocked_conditions=blocked_conditions,
        notes=notes,
    )


_DRAWING_BLOCKERS = (
    "auto mode blocked when no approved canonical source or derived rule exists",
    "manual mode requires explicit review metadata",
)

_FIELDS: tuple[DirectCoilFieldDefinition, ...] = (
    _field("tube_diameter_od", "Tube diameter OD", "Coil Geometry", "number", "in", False),
    _field("tube_geometry", "Tube geometry", "Coil Geometry", "string", None, False),
    _field("rows_deep", "Rows deep", "Coil Geometry", "integer", "rows", True),
    _field("fins_per_inch", "Fins per inch", "Coil Geometry", "number", "fpi", True),
    _field("tubes_high", "Tubes high", "Coil Geometry", "integer", "tubes", False),
    _field("finned_height", "Finned height", "Coil Geometry", "number", "in", True),
    _field("finned_length", "Finned length", "Coil Geometry", "number", "in", True),
    _field("number_of_feeds", "Number of feeds", "Coil Geometry", "integer", "feeds", False),
    _field(
        "airflow_direction",
        "Airflow direction",
        "Coil Geometry",
        "string",
        None,
        True,
        allowed_values=AIRFLOW_DIRECTION_VALUES,
        blocked_conditions=("missing airflow_direction is blocked",),
        notes="Must remain explicit; do not infer silently.",
    ),
    _field(
        "header_type",
        "Header type",
        "Coil Geometry",
        "string",
        None,
        True,
        allowed_values=SUPPORTED_HEADER_TYPES,
        blocked_conditions=("unsupported header_type is blocked",),
        notes="Phase 2A supports Header 1 only; Header 2-4 are future review items.",
    ),
    _field("tube_material", "Tube material", "Materials & Construction", "string", None, False),
    _field("fin_material", "Fin material", "Materials & Construction", "string", None, False),
    _field("fin_surface", "Fin surface", "Materials & Construction", "string", None, False),
    _field("header_material", "Header material", "Materials & Construction", "string", None, False),
    _field(
        "connection_material",
        "Connection material",
        "Materials & Construction",
        "string",
        None,
        False,
    ),
    _field("connection_type", "Connection type", "Materials & Construction", "string", None, False),
    _field(
        "supply_connection_size",
        "Supply connection size",
        "Materials & Construction",
        "number",
        "in",
        False,
    ),
    _field(
        "return_connection_size",
        "Return connection size",
        "Materials & Construction",
        "number",
        "in",
        True,
    ),
    _field("casing_material", "Casing material", "Materials & Construction", "string", None, False),
    _field("casing_style", "Casing style", "Materials & Construction", "string", None, False),
    _field("connection_ends", "Connection ends", "Materials & Construction", "string", None, False),
    _field(
        "coil_hand",
        "Coil hand",
        "Materials & Construction",
        "string",
        None,
        True,
        allowed_values=COIL_HAND_VALUES,
    ),
    _field("total_air_flow_cfm", "Total air flow", "Airside Conditions", "number", "cfm", False),
    _field("face_velocity_fpm", "Face velocity", "Airside Conditions", "number", "fpm", False),
    _field("altitude_ft", "Altitude", "Airside Conditions", "number", "ft", False),
    _field(
        "entering_dry_bulb_f",
        "Entering dry bulb",
        "Airside Conditions",
        "number",
        "degF",
        False,
    ),
    _field(
        "entering_wet_bulb_f",
        "Entering wet bulb",
        "Airside Conditions",
        "number",
        "degF",
        False,
    ),
    _field(
        "leaving_dry_bulb_f",
        "Leaving dry bulb",
        "Airside Conditions",
        "number",
        "degF",
        False,
    ),
    _field(
        "relative_humidity_pct",
        "Relative humidity",
        "Airside Conditions",
        "number",
        "pct",
        False,
    ),
    _field("total_capacity_mbh", "Total capacity", "Airside Conditions", "number", "MBH", False),
    _field("refrigerant", "Refrigerant", "Refrigerant Conditions", "string", None, False),
    _field(
        "evaporating_temp_f",
        "Evaporating temperature",
        "Refrigerant Conditions",
        "number",
        "degF",
        False,
    ),
    _field("liquid_temp_f", "Liquid temperature", "Refrigerant Conditions", "number", "degF", False),
    _field("superheat_f", "Superheat", "Refrigerant Conditions", "number", "degF", False),
    _field(
        "dx_dist_capillary_size",
        "DX distributor capillary size",
        "Refrigerant Conditions",
        "string",
        None,
        False,
    ),
    _field("drain_pan_type", "Drain pan type", "Manufacturing Options", "string", None, False),
    _field("coil_coating", "Coil coating", "Manufacturing Options", "string", None, False),
    _field("system_type", "System type", "Manufacturing Options", "string", None, False),
    _field(
        "distributor_notes",
        "Distributor notes",
        "Manufacturing Options",
        "string",
        None,
        False,
        review_policy="review_note_only",
    ),
    *(
        _field(
            key,
            key,
            "Drawing Parameters",
            "number",
            "in",
            key in {"CD", "BF", "TF", "CH"},
            allowed_values=DRAWING_PARAMETER_MODE_VALUES,
            review_policy="auto_or_manual_review_required",
            blocked_conditions=_DRAWING_BLOCKERS,
            notes="Supports auto/manual mode metadata; no export or PDF generation is implemented.",
        )
        for key in ("CD", "I", "S", "O", "R", "BF", "HD", "HF", "TF", "RF", "CH", "SL", "ZD")
    ),
)

DIRECT_COIL_FIELD_REGISTRY: dict[str, DirectCoilFieldDefinition] = {
    definition.field_key: definition for definition in _FIELDS
}

REQUIRED_DIRECT_COIL_FIELDS: tuple[str, ...] = tuple(
    definition.field_key for definition in _FIELDS if definition.required
)

DRAWING_PARAMETER_FIELD_KEYS: tuple[str, ...] = tuple(
    definition.field_key for definition in _FIELDS if definition.group == "Drawing Parameters"
)


def get_field(field_key: str) -> DirectCoilFieldDefinition:
    return DIRECT_COIL_FIELD_REGISTRY[field_key]


def get_fields_by_group(group: DirectCoilGroup) -> tuple[DirectCoilFieldDefinition, ...]:
    return tuple(definition for definition in _FIELDS if definition.group == group)


def is_header_type_supported(header_type: str) -> bool:
    return header_type in SUPPORTED_HEADER_TYPES
