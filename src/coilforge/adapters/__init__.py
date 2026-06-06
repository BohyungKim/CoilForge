"""Compatibility adapters that feed CoilForge canonical records."""

from coilforge.adapters.ez_json import load_sanitized_ez_json
from coilforge.adapters.ez_to_canonical import (
    EZJsonToCanonicalResult,
    EZJsonToCanonicalSummary,
    map_ez_json_to_canonical,
    map_ez_json_to_canonical_result,
)

__all__ = [
    "EZJsonToCanonicalResult",
    "EZJsonToCanonicalSummary",
    "load_sanitized_ez_json",
    "map_ez_json_to_canonical",
    "map_ez_json_to_canonical_result",
]
