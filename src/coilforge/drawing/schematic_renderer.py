"""Orchestrator — gated slot_values -> to-scale DX front + side SVGs (review aid).

Wires the three never-collapsed layers together and nothing more:

    slot_values
      -> CoilGeometry.from_slot_values   (L1 model, inches)
      -> resolve_topology + build_views  (L2 layout, inches; table-driven; hand mirror)
      -> render_view_svg                 (L3 SVG backend, pixels)
      -> SchematicResult

Phase 5a makes composition table-driven (docs/design/ez-drawing-model.md §7): the
``(category, header_type, special)`` topology row selects the views + supply kind. DX
(``distributor`` supply) is byte-identical to Phase 4; HGRH/CWC/HWC use a ``plain_header``
supply (a plain port reusing the existing connection primitive — the styled per-category
glyphs are Phase 5b). An UNKNOWN coil type is fail-closed: a geometry-free, annotated result
(no DX fallback). Output is a review aid: ``export_allowed`` is always ``False`` and the
watermark is always present.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from coilforge.drawing.backends.svg import REVIEW_WATERMARK, render_view_svg
from coilforge.drawing.schematic_layout import build_views
from coilforge.drawing.schematic_model import CoilGeometry
from coilforge.drawing.topology import UnknownTopologyError, resolve_topology


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
    topo_review: Mapping[str, Any] | None = None,
    topo_blocked: Sequence[str] | None = None,
) -> SchematicResult:
    """Render the front + side + V3 plan views from gated ``slot_values``, table-driven by the
    coil-type topology.

    ``dist_review`` carries the Phase-4a review-bucket distributor values (``slot.DistModel{id}`` /
    ``slot.DistOD{id}``) so the plan view draws them FLAGGED; ``dist_blocked`` lists blocked
    distributor slots (e.g. a conflicted ``slot.DistExtension{id}``) to omit + annotate.
    ``topo_review`` / ``topo_blocked`` carry the Phase-5a per-category topology data the same way
    (``slot.vent_drain`` review; ``asc_orientation`` / Terra V ``slot.vent_drain`` blocked). All are
    plain dicts — the engine never reads the sourcing layer. HIGH slots (``slot.AIRFLOW`` /
    ``slot.DistExtension{id}`` / ``slot.conn_angle`` / ``slot.HGBP``) ride in ``slot_values``."""
    geom = CoilGeometry.from_slot_values(
        slot_values,
        coil_category=coil_category,
        coil_hand=coil_hand,
        header_type=header_type,
        special_feature=special_feature,
        dist_review=dist_review,
        dist_blocked=dist_blocked,
        topo_review=topo_review,
        topo_blocked=topo_blocked,
    )

    try:
        topology = resolve_topology(coil_category, header_type, special_feature)
    except UnknownTopologyError as exc:
        # Fail-closed: no DX fallback. Emit a geometry-free, annotated review result.
        note = f"no topology defined for ({coil_category}/{header_type}/{special_feature}) — review required"
        return SchematicResult(
            svg="", side_svg="", plan_svg="",
            metadata={
                "coil_category": coil_category, "coil_hand": coil_hand,
                "header_type": header_type, "special_feature": special_feature,
                "topology_resolved": False, "topology_error": str(exc),
                "omitted_count": 1, "export_allowed": False, "john_review_required": True,
            },
            omitted_features=(note,),
            export_allowed=False,
            watermark=REVIEW_WATERMARK,
        )

    views = build_views(geom, topology)
    rendered = {name: render_view_svg(view) for name, view in views.items()}
    front = rendered.get("front")
    side = rendered.get("side")
    plan = rendered.get("plan")

    # Per-view omission notes (deduped across views), then the blocked topology slots
    # (omit + annotate; their rendering glyphs are deferred to Phase 5b).
    omitted = list(dict.fromkeys(
        note for view in views.values() for note in view.omitted_notes
    ))
    for slot in geom.topo_blocked:
        omitted.append(f"{slot}: blocked (review required) — omitted (glyph deferred to 5b)")

    # DX (implemented, no new primitives) is byte-identical; other categories defer their styled
    # glyphs to 5b (plain port shown now).
    glyphs_deferred = bool(topology.new_primitives)

    metadata: dict[str, Any] = {
        "views": tuple(views.keys()),
        "coil_category": coil_category,
        "coil_hand": coil_hand,
        "header_type": header_type,
        "special_feature": special_feature,
        "topology_resolved": True,
        "topology_id": topology.id,
        "supply_kind": topology.supply,
        "front_px_per_inch": front.px_per_inch if front else None,
        "side_px_per_inch": side.px_per_inch if side else None,
        "plan_px_per_inch": plan.px_per_inch if plan else None,
        "px_per_inch": front.px_per_inch if front else None,  # back-compat (front)
        "casing_px": front.casing_px if front else None,
        "finned_px": front.finned_px if front else None,
        "side_casing_px": side.casing_px if side else None,
        "plan_casing_px": plan.casing_px if plan else None,
        "omitted_count": len(omitted),
        "export_allowed": False,
        "john_review_required": True,
        "phase3_deferred": glyphs_deferred,
    }

    return SchematicResult(
        svg=front.svg if front else "",
        side_svg=side.svg if side else "",
        plan_svg=plan.svg if plan else "",
        metadata=metadata,
        omitted_features=tuple(omitted),
        export_allowed=False,
        watermark=REVIEW_WATERMARK,
    )
