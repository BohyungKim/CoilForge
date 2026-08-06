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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from coilforge.drawing.backends.svg import REVIEW_WATERMARK, render_view_svg
from coilforge.drawing.schematic_layout import build_dx_views
from coilforge.drawing.schematic_model import CoilGeometry


@dataclass(frozen=True)
class SchematicResult:
    svg: str  # front view (primary / back-compat)
    side_svg: str  # header/side view
    plan_svg: str  # V3 distributor plan/top view
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
    dist_review: Mapping[str, Any] | None = None,
    dist_blocked: Sequence[str] | None = None,
) -> SchematicResult:
    """Render the DX front + side + V3 plan views from gated ``slot_values``.

    ``dist_review`` carries the Phase-4a review-bucket distributor values (``slot.DistModel{id}`` /
    ``slot.DistOD{id}``) so the plan view draws them FLAGGED; ``dist_blocked`` lists blocked
    distributor slots (e.g. a conflicted ``slot.DistExtension{id}``) to omit + annotate. Both are
    plain dicts — the engine never reads the sourcing layer. HIGH distributor slots
    (``slot.AIRFLOW`` / ``slot.DistExtension{id}``) ride in ``slot_values`` as usual."""
    geom = CoilGeometry.from_slot_values(
        slot_values,
        coil_category=coil_category,
        coil_hand=coil_hand,
        header_type=header_type,
        special_feature=special_feature,
        dist_review=dist_review,
        dist_blocked=dist_blocked,
    )
    views = build_dx_views(geom)
    front = render_view_svg(views["front"])
    side = render_view_svg(views["side"])
    plan = render_view_svg(views["plan"])

    # Per-view omission notes (deduped across views).
    omitted = list(dict.fromkeys(
        [*views["front"].omitted_notes, *views["side"].omitted_notes, *views["plan"].omitted_notes]
    ))
    is_dx = coil_category.strip().upper() == "DX"
    if not is_dx:
        omitted.append(
            f"{coil_category} category-specific features deferred to Phase 3 "
            "(generic boxes shown)"
        )

    metadata: dict[str, Any] = {
        "views": ("front", "side", "plan"),
        "coil_category": coil_category,
        "coil_hand": coil_hand,
        "header_type": header_type,
        "special_feature": special_feature,
        "front_px_per_inch": front.px_per_inch,
        "side_px_per_inch": side.px_per_inch,
        "plan_px_per_inch": plan.px_per_inch,
        "px_per_inch": front.px_per_inch,  # back-compat (front)
        "casing_px": front.casing_px,
        "finned_px": front.finned_px,
        "side_casing_px": side.casing_px,
        "plan_casing_px": plan.casing_px,
        "omitted_count": len(omitted),
        "export_allowed": False,
        "john_review_required": True,
        "phase3_deferred": not is_dx,
    }

    return SchematicResult(
        svg=front.svg,
        side_svg=side.svg,
        plan_svg=plan.svg,
        metadata=metadata,
        omitted_features=tuple(omitted),
        export_allowed=False,
        watermark=REVIEW_WATERMARK,
    )
