"""Layer 3 — SVG backend (the only place pixels exist).

Consumes an inch-based :class:`ViewLayout` (front OR side) and presents it with a single,
**uniform** ``px_per_inch``: one scale for both axes (the fix for ``phase2a/renderer.py``'s
x18/x16 distortion). The scale is **fit-to-canvas** (Phase 1.5): each drawing fills the
canvas to ``TARGET_FILL`` of the available area; ``MIN_PPI``/``MAX_PPI`` are degenerate
guardrails only.

Geometry scales; annotations do not. HOW a dimension is drawn is decided here: an overall
dimension whose rendered span is long gets extension lines + double arrowheads; anything
short (every flange offset / header offset, or a tiny overall) gets a leader to a label on
its tier. The function is pure: layout in, result object out, no file writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from coilforge.drawing.schematic_layout import Dimension, ViewLayout
from coilforge.phase2a.renderer import REVIEW_WATERMARK, _esc, _fmt, _text_line

# Scale guardrails (px per inch). Fit-to-canvas normally governs; these only catch
# degenerate extents. MAX is huge so small coils fill the canvas.
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

# Feature -> rect CSS class (front + side casings, finned face).
_RECT_CLASS = {"casing": "casing", "finned": "finned"}
# Feature -> circle CSS class (headers vs connection bubble).
_CIRCLE_CLASS = {"connection": "connection"}
# Feature -> segment CSS class (tube rows / header stub / airflow arrow).
_SEGMENT_CLASS = {"row": "row", "airflow": "airflow"}


@dataclass(frozen=True)
class SvgBackendResult:
    """An SVG render plus the realized scale, for verification and the orchestrator."""

    svg: str
    px_per_inch: float
    casing_px: tuple[float, float, float, float]  # x, y, w, h (px); zeros if omitted
    finned_px: tuple[float, float, float, float] | None
    rects_px: dict[str, tuple[float, float, float, float]]  # feature -> px rect


def render_view_svg(
    view: ViewLayout,
    *,
    watermark: str = REVIEW_WATERMARK,
    canvas_w: int = DEFAULT_CANVAS_W,
    canvas_h: int = DEFAULT_CANVAS_H,
) -> SvgBackendResult:
    avail_w = canvas_w - 2 * PAD_PX
    avail_h = canvas_h - 2 * PAD_PX

    # Uniform fit-to-canvas scale. min() over both axes preserves aspect; TARGET_FILL
    # leaves a margin; the clamp is a degenerate-scale guardrail only.
    fit = min(avail_w / view.extent_w, avail_h / view.extent_h)
    ppi = max(MIN_PPI, min(MAX_PPI, TARGET_FILL * fit))

    drawn_w = view.extent_w * ppi
    drawn_h = view.extent_h * ppi
    off_x = PAD_PX + (avail_w - drawn_w) / 2.0
    off_y = PAD_PX + (avail_h - drawn_h) / 2.0

    def x_px(inch: float) -> float:
        return off_x + inch * ppi

    def y_px(inch: float) -> float:
        return off_y + inch * ppi

    parts: list[str] = []
    rects_px: dict[str, tuple[float, float, float, float]] = {}

    for lr in view.rects:
        r = lr.rect
        px = (x_px(r.x), y_px(r.y), r.w * ppi, r.h * ppi)
        rects_px[lr.feature] = px
        cls = _RECT_CLASS.get(lr.feature, "casing")
        parts.append(
            f'<rect data-feature="{_esc(lr.feature)}" x="{px[0]:.2f}" y="{px[1]:.2f}" '
            f'width="{px[2]:.2f}" height="{px[3]:.2f}" class="{cls}"/>'
        )

    for s in view.segments:
        cls = _SEGMENT_CLASS.get(s.feature, "stub")
        parts.append(
            f'<line data-feature="{_esc(s.feature)}" x1="{x_px(s.x1):.2f}" y1="{y_px(s.y1):.2f}" '
            f'x2="{x_px(s.x2):.2f}" y2="{y_px(s.y2):.2f}" class="{cls}"/>'
        )

    for c in view.circles:
        cls = _CIRCLE_CLASS.get(c.feature, "header-pipe")
        parts.append(
            f'<circle data-feature="{_esc(c.feature)}" cx="{x_px(c.cx):.2f}" cy="{y_px(c.cy):.2f}" '
            f'r="{c.r * ppi:.2f}" class="{cls}"/>'
        )

    for lb in view.labels:
        parts.append(
            f'<text data-label="{_esc(lb.feature)}" x="{x_px(lb.x):.2f}" y="{y_px(lb.y):.2f}" '
            f'text-anchor="middle" class="callout">{_esc(lb.text)}</text>'
        )

    for dim in view.dimensions:
        parts.append(_dimension_svg(dim, x_px, y_px))

    omitted_y = PAD_PX + 18
    omitted_parts = [
        _text_line(PAD_PX, omitted_y + idx * (FONT_PX + 4), note, "omitted")
        for idx, note in enumerate(view.omitted_notes)
    ]

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {canvas_h}" role="img" aria-label="CoilForge parametric {_esc(view.view)} view (review aid)">
  <defs>
    <marker id="schem-arrow" markerWidth="{ARROW_PX}" markerHeight="{ARROW_PX}" refX="{ARROW_PX - 1}" refY="{ARROW_PX / 2:.1f}" orient="auto">
      <path d="M 0 0 L {ARROW_PX} {ARROW_PX / 2:.1f} L 0 {ARROW_PX} z" fill="#242092"/>
    </marker>
    <marker id="airflow-arrow" markerWidth="{ARROW_PX + 3}" markerHeight="{ARROW_PX + 3}" refX="{ARROW_PX + 1}" refY="{(ARROW_PX + 3) / 2:.1f}" orient="auto">
      <path d="M 0 0 L {ARROW_PX + 3} {(ARROW_PX + 3) / 2:.1f} L 0 {ARROW_PX + 3} z" fill="#64748b"/>
    </marker>
    <style>
      .casing {{ fill: #fbfbfb; stroke: #1f2937; stroke-width: 2; }}
      .finned {{ fill: #eef2ff; stroke: #4b5563; stroke-width: 1.5; }}
      .header-pipe {{ fill: #e0e7ff; stroke: #1f2937; stroke-width: 1.5; }}
      .connection {{ fill: #ffffff; stroke: #4b5563; stroke-width: 1.5; }}
      .stub {{ stroke: #1f2937; stroke-width: 1.5; fill: none; }}
      .row {{ stroke: #c7cce8; stroke-width: 0.8; fill: none; }}
      .airflow {{ stroke: #64748b; stroke-width: 1.6; fill: none; marker-end: url(#airflow-arrow); }}
      .ext-line {{ stroke: #9aa0c4; stroke-width: 0.8; fill: none; }}
      .dim-arrows {{ stroke: #242092; stroke-width: 1.2; fill: none; marker-start: url(#schem-arrow); marker-end: url(#schem-arrow); }}
      .witness {{ stroke: #242092; stroke-width: 1.1; fill: none; }}
      .leader {{ stroke: #242092; stroke-width: 0.9; fill: none; }}
      .dim-label {{ fill: #0d0877; font: 700 {FONT_PX}px Arial, sans-serif; }}
      .callout {{ fill: #1f2937; font: 600 {FONT_PX}px Arial, sans-serif; }}
      .omitted {{ fill: #92400e; font: 700 {FONT_PX}px Arial, sans-serif; }}
      .watermark {{ fill: #b91c1c; font: 800 16px Arial, sans-serif; }}
      .meta {{ fill: #475569; font: 11px Arial, sans-serif; }}
    </style>
  </defs>
  <g id="zone.{_esc(view.view)}_view">
    {''.join(parts)}
  </g>
  <g id="zone.annotations">
    {''.join(omitted_parts)}
  </g>
  <g id="zone.review">
    <text x="{PAD_PX}" y="{canvas_h - 26}" class="watermark">{_esc(watermark)}</text>
    <text x="{PAD_PX}" y="{canvas_h - 10}" class="meta">REVIEW AID — NOT TO STANDARD SCALE | view={_esc(view.view)} | px_per_inch={_fmt(round(ppi, 4))} | export_allowed=false | john_review_required=true</text>
  </g>
</svg>"""

    return SvgBackendResult(
        svg=svg,
        px_per_inch=ppi,
        casing_px=rects_px.get("casing", (0.0, 0.0, 0.0, 0.0)),
        finned_px=rects_px.get("finned"),
        rects_px=rects_px,
    )


# Back-compat alias: the front view is just a view.
render_front_view_svg = render_view_svg


def _label_svg(x: float, y: float, anchor: str, text: str) -> str:
    return f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" class="dim-label">{_esc(text)}</text>'


def _dim_text(dim: Dimension) -> str:
    """The visible dimension callout. Numbers-only for direct-coil ordering: show the
    measured value, not the label code (the code stays on the ``data-dim`` attribute).
    Falls back to the code only if no value was carried (should not happen for real dims).
    """
    return _fmt(dim.value) if dim.value is not None else dim.label


def _dimension_svg(dim: Dimension, x_px, y_px) -> str:  # noqa: ANN001 - local px mappers
    ax, ay = x_px(dim.ax), y_px(dim.ay)
    bx, by = x_px(dim.bx), y_px(dim.by)
    horizontal_edge = dim.edge in ("top", "bottom")
    tp = y_px(dim.tier_pos) if horizontal_edge else x_px(dim.tier_pos)

    span_px = hypot(bx - ax, by - ay)
    arrows = dim.kind == "overall" and span_px >= LEADER_THRESHOLD_PX

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

    if arrows:
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

    body.append(_label_svg(lx, ly, anchor, _dim_text(dim)))
    return f'<g data-dim="{_esc(dim.label)}" data-style="{style}">{"".join(body)}</g>'
