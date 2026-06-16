"""Orchestrator — gated slot_values -> to-scale DX front-view SVG (review aid).

Wires the three never-collapsed layers together and nothing more:

    slot_values
      -> CoilGeometry.from_slot_values   (L1 model, inches)
      -> layout_dx_front_view            (L2 layout, inches)
      -> render_front_view_svg           (L3 SVG backend, pixels)
      -> SchematicResult

Phase 1 builds the DX front view only. A non-DX category still renders the generic
casing/finned front box, with a Phase-3-deferred note recorded so the missing
category-specific features are visible, never silently dropped. Output is a review aid:
``export_allowed`` is always ``False`` and the watermark is always present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from coilforge.drawing.backends.svg import REVIEW_WATERMARK, render_front_view_svg
from coilforge.drawing.schematic_layout import layout_dx_front_view
from coilforge.drawing.schematic_model import CoilGeometry


@dataclass(frozen=True)
class SchematicResult:
    svg: str
    metadata: dict[str, Any]
    omitted_features: tuple[str, ...]
    export_allowed: bool  # always False in Phase 1
    watermark: str


def render_scale_schematic(
    slot_values: dict[str, Any],
    *,
    coil_category: str,
    coil_hand: str,
    header_type: str,
    special_feature: str | None = None,
) -> SchematicResult:
    geom = CoilGeometry.from_slot_values(
        slot_values,
        coil_category=coil_category,
        coil_hand=coil_hand,
        header_type=header_type,
        special_feature=special_feature,
    )
    layout = layout_dx_front_view(geom)
    render = render_front_view_svg(layout)

    omitted = list(layout.omitted_notes)
    is_dx = coil_category.strip().upper() == "DX"
    if not is_dx:
        omitted.append(
            f"{coil_category} category-specific features deferred to Phase 3 "
            "(generic front-view box shown)"
        )

    metadata: dict[str, Any] = {
        "view": "dx_front",
        "coil_category": coil_category,
        "coil_hand": coil_hand,
        "header_type": header_type,
        "special_feature": special_feature,
        "px_per_inch": render.px_per_inch,
        "casing_px": render.casing_px,
        "finned_px": render.finned_px,
        "omitted_count": len(omitted),
        "export_allowed": False,
        "john_review_required": True,
        "phase3_deferred": not is_dx,
    }

    return SchematicResult(
        svg=render.svg,
        metadata=metadata,
        omitted_features=tuple(omitted),
        export_allowed=False,
        watermark=REVIEW_WATERMARK,
    )
