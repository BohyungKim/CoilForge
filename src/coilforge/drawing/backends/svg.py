"""Layer 3 — SVG backend (the only place pixels exist).

Consumes an inch-based :class:`FrontViewLayout` and presents it with a single,
**uniform** ``px_per_inch`` (clamped via the ``max(min(...))`` idiom), fit-to-canvas
and centered. One scale for both axes is the whole point: it is the fix for
``phase2a/renderer.py``'s x18 (width) / x16 (height) distortion — a skinny coil renders
skinny, a wide coil wide.

Geometry scales; annotations do not. Dimension text, arrowheads and witness-line labels
are drawn at a fixed pixel size, anchored to datums. The function is pure: layout in,
result object out, no file writes.
"""

from __future__ import annotations

from dataclasses import dataclass

from coilforge.drawing.schematic_layout import DimLine, FrontViewLayout
from coilforge.phase2a.renderer import REVIEW_WATERMARK, _esc, _fmt, _text_line

# Uniform scale clamps (px per inch). MAX_PPI keeps small coils legible; MIN_PPI keeps
# huge coils on the canvas. Fit-to-canvas chooses between them.
MIN_PPI = 0.4
MAX_PPI = 4.0

DEFAULT_CANVAS_W = 1000
DEFAULT_CANVAS_H = 780
PAD_PX = 48  # fixed pixel border reserving room for fixed-size annotations
FONT_PX = 13
ARROW_PX = 9


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

    # Uniform fit-to-canvas scale, clamped. min() over both axes preserves aspect.
    fit = min(avail_w / layout.extent_w, avail_h / layout.extent_h)
    ppi = max(MIN_PPI, min(MAX_PPI, fit))

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

    for dim in layout.dim_lines:
        parts.append(_dim_svg(dim, x_px, y_px))

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
      .dim-line {{ stroke: #242092; stroke-width: 1.2; fill: none; marker-start: url(#schem-arrow); marker-end: url(#schem-arrow); }}
      .dim-label {{ fill: #0d0877; font: 700 {FONT_PX}px Arial, sans-serif; text-anchor: middle; }}
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
    <text x="{PAD_PX}" y="{canvas_h - 10}" class="meta">px_per_inch={_fmt(round(ppi, 4))} | export_allowed=false | john_review_required=true</text>
  </g>
</svg>"""

    return SvgBackendResult(svg=svg, px_per_inch=ppi, casing_px=casing_px, finned_px=finned_px)


def _dim_svg(dim: DimLine, x_px, y_px) -> str:  # noqa: ANN001 - local px mappers
    x1, y1 = x_px(dim.x1), y_px(dim.y1)
    x2, y2 = x_px(dim.x2), y_px(dim.y2)
    # Nudge the fixed-size label clear of its line by a fixed pixel amount.
    if dim.orient == "v":
        lx, ly = x_px(dim.lx) - 6, y_px(dim.ly)
    else:
        lx, ly = x_px(dim.lx), y_px(dim.ly) - 6
    return (
        f'<g data-dim="{_esc(dim.label)}">'
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" class="dim-line"/>'
        f'<text x="{lx:.2f}" y="{ly:.2f}" class="dim-label">{_esc(dim.label)}</text>'
        f"</g>"
    )
