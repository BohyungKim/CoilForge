"""Layer 3 — SVG backend (the only place pixels exist).

Consumes an inch-based :class:`FrontViewLayout` and presents it with a single,
**uniform** ``px_per_inch``: one scale for both axes (the fix for ``phase2a/renderer.py``'s
x18/x16 distortion — a skinny coil renders skinny, a wide coil wide). The scale is
**fit-to-canvas** (Phase 1.5): each drawing fills the canvas to ``TARGET_FILL`` of the
available area, so a small real coil no longer floats at a clamp. ``MIN_PPI``/``MAX_PPI``
are degenerate-scale guardrails only.

Geometry scales; annotations do not. Dimension text and arrowheads are a fixed pixel
size. HOW a dimension is drawn is decided here: an overall dimension whose rendered span
is long gets extension lines + double arrowheads; anything short (every flange offset, or
a tiny overall) gets a leader to a label placed clear on its tier — never crammed
arrowheads. The function is pure: layout in, result object out, no file writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from coilforge.drawing.schematic_layout import Dimension, FrontViewLayout
from coilforge.phase2a.renderer import REVIEW_WATERMARK, _esc, _fmt, _text_line

# Scale guardrails (px per inch). Fit-to-canvas normally governs; these only catch
# degenerate extents. MAX is deliberately huge so small coils fill the canvas.
MIN_PPI = 0.05
MAX_PPI = 400.0
TARGET_FILL = 0.85  # fraction of the available canvas the drawing fills on its tight axis

DEFAULT_CANVAS_W = 1000
DEFAULT_CANVAS_H = 780
PAD_PX = 48  # fixed pixel border reserving room for fixed-size annotations
FONT_PX = 13
ARROW_PX = 7
# Below this rendered span (px) a dimension is drawn with a leader, not double arrowheads.
LEADER_THRESHOLD_PX = 28.0


@dataclass(frozen=True)
class SvgBackendResult:
    """An SVG render plus the realized scale, for verification and the orchestrator."""

    svg: str
    px_per_inch: float
    casing_px: tuple[float, float, float, float]  # x, y, w, h (px); zeros if omitted
    finned_px: tuple[float, float, float, float] | None


def render_front_view_svg(
    layout: FrontViewLayout,
    *,
    watermark: str = REVIEW_WATERMARK,
    canvas_w: int = DEFAULT_CANVAS_W,
    canvas_h: int = DEFAULT_CANVAS_H,
) -> SvgBackendResult:
    avail_w = canvas_w - 2 * PAD_PX
    avail_h = canvas_h - 2 * PAD_PX

    # Uniform fit-to-canvas scale. min() over both axes preserves aspect; TARGET_FILL
    # leaves a small breathing margin; the clamp is a degenerate-scale guardrail only.
    fit = min(avail_w / layout.extent_w, avail_h / layout.extent_h)
    ppi = max(MIN_PPI, min(MAX_PPI, TARGET_FILL * fit))

    # Center the drawn extent inside the padded canvas.
    drawn_w = layout.extent_w * ppi
    drawn_h = layout.extent_h * ppi
    off_x = PAD_PX + (avail_w - drawn_w) / 2.0
    off_y = PAD_PX + (avail_h - drawn_h) / 2.0

    def x_px(inch: float) -> float:
        return off_x + inch * ppi

    def y_px(inch: float) -> float:
        return off_y + inch * ppi

    parts: list[str] = []

    casing_px = (0.0, 0.0, 0.0, 0.0)
    if layout.casing is not None:
        c = layout.casing
        casing_px = (x_px(c.x), y_px(c.y), c.w * ppi, c.h * ppi)
        parts.append(
            f'<rect data-feature="casing" x="{casing_px[0]:.2f}" y="{casing_px[1]:.2f}" '
            f'width="{casing_px[2]:.2f}" height="{casing_px[3]:.2f}" class="casing"/>'
        )

    finned_px: tuple[float, float, float, float] | None = None
    if layout.finned is not None:
        f = layout.finned
        finned_px = (x_px(f.x), y_px(f.y), f.w * ppi, f.h * ppi)
        parts.append(
            f'<rect data-feature="finned" x="{finned_px[0]:.2f}" y="{finned_px[1]:.2f}" '
            f'width="{finned_px[2]:.2f}" height="{finned_px[3]:.2f}" class="finned"/>'
        )

    for dim in layout.dimensions:
        parts.append(_dimension_svg(dim, x_px, y_px))

    omitted_y = PAD_PX + 18
    omitted_parts = [
        _text_line(PAD_PX, omitted_y + idx * (FONT_PX + 4), note, "omitted")
        for idx, note in enumerate(layout.omitted_notes)
    ]

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {canvas_h}" role="img" aria-label="CoilForge parametric front view (review aid)">
  <defs>
    <marker id="schem-arrow" markerWidth="{ARROW_PX}" markerHeight="{ARROW_PX}" refX="{ARROW_PX - 1}" refY="{ARROW_PX / 2:.1f}" orient="auto">
      <path d="M 0 0 L {ARROW_PX} {ARROW_PX / 2:.1f} L 0 {ARROW_PX} z" fill="#242092"/>
    </marker>
    <style>
      .casing {{ fill: #fbfbfb; stroke: #1f2937; stroke-width: 2; }}
      .finned {{ fill: #eef2ff; stroke: #4b5563; stroke-width: 1.5; }}
      .ext-line {{ stroke: #9aa0c4; stroke-width: 0.8; fill: none; }}
      .dim-arrows {{ stroke: #242092; stroke-width: 1.2; fill: none; marker-start: url(#schem-arrow); marker-end: url(#schem-arrow); }}
      .witness {{ stroke: #242092; stroke-width: 1.1; fill: none; }}
      .leader {{ stroke: #242092; stroke-width: 0.9; fill: none; }}
      .dim-label {{ fill: #0d0877; font: 700 {FONT_PX}px Arial, sans-serif; }}
      .omitted {{ fill: #92400e; font: 700 {FONT_PX}px Arial, sans-serif; }}
      .watermark {{ fill: #b91c1c; font: 800 16px Arial, sans-serif; }}
      .meta {{ fill: #475569; font: 11px Arial, sans-serif; }}
    </style>
  </defs>
  <g id="zone.front_view">
    {''.join(parts)}
  </g>
  <g id="zone.annotations">
    {''.join(omitted_parts)}
  </g>
  <g id="zone.review">
    <text x="{PAD_PX}" y="{canvas_h - 26}" class="watermark">{_esc(watermark)}</text>
    <text x="{PAD_PX}" y="{canvas_h - 10}" class="meta">REVIEW AID — NOT TO STANDARD SCALE | px_per_inch={_fmt(round(ppi, 4))} | export_allowed=false | john_review_required=true</text>
  </g>
</svg>"""

    return SvgBackendResult(svg=svg, px_per_inch=ppi, casing_px=casing_px, finned_px=finned_px)


def _label_svg(x: float, y: float, anchor: str, text: str) -> str:
    return f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" class="dim-label">{_esc(text)}</text>'


def _dimension_svg(dim: Dimension, x_px, y_px) -> str:  # noqa: ANN001 - local px mappers
    ax, ay = x_px(dim.ax), y_px(dim.ay)
    bx, by = x_px(dim.bx), y_px(dim.by)
    horizontal_edge = dim.edge in ("top", "bottom")
    tp = y_px(dim.tier_pos) if horizontal_edge else x_px(dim.tier_pos)

    span_px = hypot(bx - ax, by - ay)
    arrows = dim.kind == "overall" and span_px >= LEADER_THRESHOLD_PX

    # Label anchor sits on the tier, centered on the measured span.
    if horizontal_edge:
        lpar = (ax + bx) / 2.0
        if dim.edge == "top":
            lx, ly, anchor = lpar, tp - 5, "middle"
        else:
            lx, ly, anchor = lpar, tp + FONT_PX + 2, "middle"
    else:
        lpar = (ay + by) / 2.0
        if dim.edge == "left":
            lx, ly, anchor = tp - 6, lpar + 4, "end"
        else:
            lx, ly, anchor = tp + 6, lpar + 4, "start"

    body: list[str]
    if arrows:
        # Extension lines from each feature point out to the tier, dimension line between.
        if horizontal_edge:
            body = [
                f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{ax:.2f}" y2="{tp:.2f}" class="ext-line"/>',
                f'<line x1="{bx:.2f}" y1="{by:.2f}" x2="{bx:.2f}" y2="{tp:.2f}" class="ext-line"/>',
                f'<line x1="{ax:.2f}" y1="{tp:.2f}" x2="{bx:.2f}" y2="{tp:.2f}" class="dim-arrows"/>',
            ]
        else:
            body = [
                f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{tp:.2f}" y2="{ay:.2f}" class="ext-line"/>',
                f'<line x1="{bx:.2f}" y1="{by:.2f}" x2="{tp:.2f}" y2="{by:.2f}" class="ext-line"/>',
                f'<line x1="{tp:.2f}" y1="{ay:.2f}" x2="{tp:.2f}" y2="{by:.2f}" class="dim-arrows"/>',
            ]
        style = "arrows"
    else:
        # Witness across the (small) span, plus a leader out to the tier label.
        mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
        if horizontal_edge:
            leader = f'<line x1="{mx:.2f}" y1="{my:.2f}" x2="{mx:.2f}" y2="{tp:.2f}" class="leader"/>'
        else:
            leader = f'<line x1="{mx:.2f}" y1="{my:.2f}" x2="{tp:.2f}" y2="{my:.2f}" class="leader"/>'
        body = [
            f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" y2="{by:.2f}" class="witness"/>',
            leader,
        ]
        style = "leader"

    body.append(_label_svg(lx, ly, anchor, dim.label))
    return f'<g data-dim="{_esc(dim.label)}" data-style="{style}">{"".join(body)}</g>'
