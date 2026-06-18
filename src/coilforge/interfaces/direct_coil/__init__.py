"""Direct Coil interface field model."""

from coilforge.interfaces.direct_coil.fields import (
    DIRECT_COIL_FIELD_GROUPS,
    DIRECT_COIL_FIELD_REGISTRY,
    DIRECT_COIL_SOURCE_TRACE_POLICY,
    DRAWING_PARAMETER_FIELD_KEYS,
    DRAWING_PARAMETER_MODE_VALUES,
    MANUAL_OVERRIDE_POLICY,
    REQUIRED_DIRECT_COIL_FIELDS,
    DirectCoilFieldDefinition,
    get_field,
    get_fields_by_group,
    is_header_type_supported,
)

__all__ = [
    "DIRECT_COIL_FIELD_GROUPS",
    "DIRECT_COIL_FIELD_REGISTRY",
    "DIRECT_COIL_SOURCE_TRACE_POLICY",
    "DRAWING_PARAMETER_FIELD_KEYS",
    "DRAWING_PARAMETER_MODE_VALUES",
    "MANUAL_OVERRIDE_POLICY",
    "REQUIRED_DIRECT_COIL_FIELDS",
    "DirectCoilFieldDefinition",
    "get_field",
    "get_fields_by_group",
    "is_header_type_supported",
]
