"""Build a ``/derive`` spec from a template-drawing result the way the browser does.

A Python mirror of ``web/app.js::deriveSpecFromTemplate`` for tests that need a SECOND
request. The browser never builds one from scratch: it persists the last result and
reads the next request's values back out of it (``extracted`` is the frozen path's echo
of what it was sent, ``panel`` likewise). A hand-written second spec is clean in exactly
the places the round trip is dirty, so a "type a value, then clear it" test built by
hand passes while the real page keeps the cleared value.
"""
from __future__ import annotations

from typing import Any

MANUAL_INPUT_KEYS = ("rows", "feeds", "finned_height", "finned_length", "return_conn_size")


def spec_from_template_drawing(
    td: dict[str, Any], engine_inputs: dict[str, Any] | None = None, **extra: Any
) -> dict[str, Any]:
    """``engine_inputs`` is the browser's fill store (``page.manualFills.engineInputs``)."""
    ex = td.get("extracted") or {}
    fills = engine_inputs or {}

    def pick(key: str, fallback: Any) -> Any:
        value = fills.get(key)
        return value if value not in (None, "") else fallback

    spec = {
        "coil_category": pick("coil_category", ex.get("coil_category")),
        "coil_hand": pick("coil_hand", ex.get("hand")),
        "circuits": pick("circuits", ex.get("circuits")),
        "special_feature": ex.get("special_feature"),
        "tag": ex.get("tag"),
        "rows": ex.get("rows"),
        "feeds": ex.get("feeds"),
        "finned_height": ex.get("finned_height"),
        "finned_length": ex.get("finned_length"),
        "suction_conn_size": ex.get("return_conn_size"),
        "manual_inputs": {
            key: fills[key] for key in MANUAL_INPUT_KEYS if fills.get(key) not in (None, "")
        },
        "input_baseline": td.get("input_baseline"),
        "coating": pick("coating", ex.get("coating")),
        "product_type": td.get("product_type"),
        "unit_size": td.get("unit_size"),
        "application": fills.get("application"),
        "header_count": fills.get("header_count"),
        "qty_conn_per_header": fills.get("qty_conn_per_header"),
        "inlet_conn_size": fills.get("inlet_conn_size"),
        "outlet_conn_size": fills.get("outlet_conn_size"),
        "water_conn_extracted": td.get("water_conn_extracted"),
        "stated_qty_conn_per_header": td.get("qty_conn_per_header_stated"),
        "panel": td.get("panel"),
    }
    spec.update(extra)
    return spec
