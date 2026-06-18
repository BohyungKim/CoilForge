"""Loader for the JSON -> drawing link-rule registry.

The registry (``rules/json_drawing_link_rules.yaml``) maps EZ Coil selection JSON
fields onto drawing labels/slots, with a confidence gate that mirrors the header
rule engine. Mapping candidates only; STRONG entries auto-populate, everything
else is review-required until John / engineering signs off.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_PATH = Path(__file__).resolve().parents[1] / "rules" / "json_drawing_link_rules.yaml"

CONFIDENCE_TIERS = frozenset(
    {"STRONG", "DERIVED", "UNCERTAIN", "FORBIDDEN", "DEFERRED"}
)


@lru_cache(maxsize=1)
def load_link_registry() -> dict[str, Any]:
    """Load and cache the link-rule registry YAML."""
    with _PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def iter_links() -> list[dict[str, Any]]:
    """Every entry carrying a ``link_id``, wherever it is nested in the registry."""
    found: list[dict[str, Any]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            if "link_id" in obj:
                found.append(obj)
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(load_link_registry())
    return found


def engine_slot_bridge() -> list[dict[str, str]]:
    """slot <-> header-prepopulation engine field mappings."""
    return list(load_link_registry().get("engine_slot_bridge", {}).get("mappings", []))
