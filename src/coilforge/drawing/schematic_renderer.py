"""Orchestrator — gated slot_values -> to-scale DX front + side SVGs (review aid).

Wires the three never-collapsed layers together and nothing more:

    slot_values
      -> CoilGeometry.from_slot_values   (L1 model, inches)
      -> build_dx_views                  (L2 layout, inches; front + side; hand mirror)
      -> render_view_svg                 (L3 SVG backend, pixels)
      -> SchematicResult

Phase 2 builds the DX front view AND the header/side view, mirrored for LH/RH. A non-DX
category still renders the generic boxes with a Phase-3-deferred note so missing
category-specific features are visible, never silently dropped. Output is a review aid:
``export_allowed`` is always ``False`` and the watermark is always present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from coilforge.drawing.backends.svg import REVIEW_WATERMARK, render_view_svg
from coilforge.drawing.schematic_layout import build_dx_views
from coilforge.drawing.schematic_model import CoilGeometry


@dataclass(frozen=True)
class SchematicResult:
    svg: str  # front view (primary / back-compat)
    side_svg: str  # header/side view
    metadata: dict[str, Any]
    omitted_features: tuple[str, ...]
    export_allowed: bool  # always False
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
    views = build_dx_views(geom)
    front = render_view_svg(views["front"])
    side = render_view_svg(views["side"])

    # Per-view omission notes (deduped across views).
    omitted = list(dict.fromkeys([*views["front"].omitted_notes, *views["side"].omitted_notes]))
    is_dx = coil_category.strip().upper() == "DX"
    if not is_dx:
        omitted.append(
            f"{coil_category} category-specific features deferred to Phase 3 "
            "(generic boxes shown)"
        )

    metadata: dict[str, Any] = {
        "views": ("front", "side"),
        "coil_category": coil_category,
        "coil_hand": coil_hand,
        "header_type": header_type,
        "special_feature": special_feature,
        "front_px_per_inch": front.px_per_inch,
        "side_px_per_inch": side.px_per_inch,
        "px_per_inch": front.px_per_inch,  # back-compat (front)
        "casing_px": front.casing_px,
        "finned_px": front.finned_px,
        "side_casing_px": side.casing_px,
        "omitted_count": len(omitted),
        "export_allowed": False,
        "john_review_required": True,
        "phase3_deferred": not is_dx,
    }

    return SchematicResult(
        svg=front.svg,
        side_svg=side.svg,
        metadata=metadata,
        omitted_features=tuple(omitted),
        export_allowed=False,
        watermark=REVIEW_WATERMARK,
    )
