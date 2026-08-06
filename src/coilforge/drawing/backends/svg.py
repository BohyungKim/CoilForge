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

from dataclasses import dataclass, field
from math import hypot

from coilforge.drawing.schematic_layout import Dimension, ViewLayout
from coilforge.phase2a.renderer import REVIEW_WATERMARK, _esc, _fmt

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

# Unified label de-collision (Phase 2.7). Text metrics are px, so this lives in the backend.
CHAR_W_FACTOR = 0.6   # approx Arial advance width as a fraction of font size
LABEL_GAP = 2.0       # vertical clearance the de-collision resolves to
DECOLLIDE_STEP = 2.0  # px per nudge
LEADER_MIN_PX = 4.0   # draw a leader to the feature once the label sits at least this far off

# Feature -> rect CSS class (front + side casings, finned face).
_RECT_CLASS = {"casing": "casing", "finned": "finned"}
# Feature -> circle CSS class (headers vs connection bubble).
_CIRCLE_CLASS = {"connection": "connection"}
# Feature -> segment CSS class (tube rows / circuit tube runs are light; stub/nozzle dark).
# V3 plan-view glyphs (simplified symbols): nozzle funnel, feeder fan, distributor stem, end cap.
_SEGMENT_CLASS = {
    "row": "row", "tube_run": "row",
    "nozzle_body": "nozzle", "feeder_fan": "feeder", "dist_extension": "dist-ext",
    "stub_cap": "stub",
}
# Segment features that join the de-collision obstacle set (labels must clear these glyphs).
_GLYPH_OBSTACLE_FEATURES = ("distributor_supply", "stub", "nozzle_body", "feeder_fan",
                            "dist_extension", "stub_cap")


@dataclass(frozen=True)
class SvgBackendResult:
    """An SVG render plus the realized scale, for verification and the orchestrator."""

    svg: str
    px_per_inch: float
    casing_px: tuple[float, float, float, float]  # x, y, w, h (px); zeros if omitted
    finned_px: tuple[float, float, float, float] | None
    rects_px: dict[str, tuple[float, float, float, float]]  # feature -> px rect


@dataclass
class _Label:
    """A text label in px, collected for the unified de-collision pass (mutable y)."""

    x: float
    y: float
    anchor: str  # start | middle | end
    css: str  # dim-label | callout | omitted
    text: str
    connector: tuple[float, float] | None = None  # feature point to draw a leader to
    always_leader: bool = False  # leader-style dim / callout -> always connect
    feature: str | None = None  # for data-label on callouts
    y0: float = 0.0  # original y, to detect a nudge


def text_bbox(x: float, y: float, anchor: str, text: str, font_px: float = FONT_PX):
    """Approximate rendered text bounding box (x0, y0, x1, y1). Shared by the de-collision
    pass and the all-label overlap test so both agree."""
    w = max(1, len(text)) * font_px * CHAR_W_FACTOR
    if anchor == "middle":
        x0 = x - w / 2.0
    elif anchor == "end":
        x0 = x - w
    else:
        x0 = x
    return (x0, y - font_px * 0.8, x0 + w, y + font_px * 0.25)


def boxes_overlap(a, b, tol: float = 1.0) -> bool:  # noqa: ANN001
    ix = min(a[2], b[2]) - max(a[0], b[0])
    iy = min(a[3], b[3]) - max(a[1], b[1])
    return ix > tol and iy > tol


def _seg_box(x1: float, y1: float, x2: float, y2: float, pad: float = 1.5):
    """Axis-aligned bbox of a line segment, padded for its stroke width — so a segment can
    join the de-collision obstacle set (a label must clear lines, not just other labels)."""
    return (min(x1, x2) - pad, min(y1, y2) - pad, max(x1, x2) + pad, max(y1, y2) + pad)


def _vclear(a, b, gap: float) -> bool:  # noqa: ANN001
    """Two boxes are clear if they don't overlap in x, or are >= ``gap`` apart in y."""
    ix = min(a[2], b[2]) - max(a[0], b[0])
    if ix <= 0:
        return True
    iy = min(a[3], b[3]) - max(a[1], b[1])
    return iy <= -gap


def decollide(
    labels: list[_Label],
    center_x: float,
    obstacles: list[tuple[float, float, float, float]] | None = None,
    casing_y: tuple[float, float] | None = None,
) -> list[_Label]:
    """Deterministic, MIRROR-EQUIVARIANT, OBSTACLE-COMPLETE de-collision: nudge labels in y
    only, in a mirror-invariant order, so each label clears every other label AND every fixed
    ``obstacle`` (dimension / witness lines + connection glyph bboxes), not just other labels.

    ``casing_y`` = the box's (top, bottom) in px. A label that starts ABOVE the box is only
    ever pushed further UP, one BELOW only further DOWN — so labels stay on their side and
    never get shoved across the (open) coil interior into the opposite band. Since y and the
    region test are unaffected by the x-mirror, the same y-shifts apply to LH and RH.
    """
    order = sorted(
        range(len(labels)),
        key=lambda i: (round(labels[i].y, 1), round(abs(labels[i].x - center_x), 1), labels[i].text, i),
    )
    # Seed with the fixed obstacles: they are never moved, but every label must clear them.
    placed: list[tuple[float, float, float, float]] = list(obstacles) if obstacles else []
    top, bot = casing_y if casing_y is not None else (None, None)
    for i in order:
        lb = labels[i]
        box = text_bbox(lb.x, lb.y, lb.anchor, lb.text)
        bad = [p for p in placed if not _vclear(box, p, LABEL_GAP)]
        if bad:
            if top is not None and lb.y0 <= top:
                direction = -1.0  # above the box -> push further up (never across it)
            elif bot is not None and lb.y0 >= bot:
                direction = 1.0  # below the box -> push further down
            else:
                centroid = sum((p[1] + p[3]) / 2.0 for p in bad) / len(bad)
                direction = 1.0 if lb.y >= centroid else -1.0  # side labels: away from the crowd
            guard = 0
            while guard < 600 and any(not _vclear(box, p, LABEL_GAP) for p in placed):
                lb.y += direction * DECOLLIDE_STEP
                box = text_bbox(lb.x, lb.y, lb.anchor, lb.text)
                guard += 1
        placed.append(box)
    return labels


def _label_svg(lb: _Label) -> str:
    attr = f' data-label="{_esc(lb.feature)}"' if lb.feature else ""
    return (
        f'<text{attr} x="{lb.x:.2f}" y="{lb.y:.2f}" text-anchor="{lb.anchor}" '
        f'class="{lb.css}">{_esc(lb.text)}</text>'
    )


def _leader_svg(lb: _Label) -> str:
    """Redraw a leader from the label's connector to its FINAL position. It lands on the
    MIDPOINT of the box edge facing the connector (not a corner), so the connector clearly
    points into the label. A vertical-first dogleg (or straight line) keeps it tidy."""
    cx, cy = lb.connector  # type: ignore[misc]
    x0, y0, x1, y1 = text_bbox(lb.x, lb.y, lb.anchor, lb.text)
    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    if abs(cx - mx) >= abs(cy - my):
        ax, ay = (x1, my) if cx >= mx else (x0, my)  # near vertical edge, mid-height
    else:
        ax, ay = (mx, y1) if cy >= my else (mx, y0)  # near horizontal edge, mid-width
    if abs(ax - cx) < 0.5 or abs(ay - cy) < 0.5:
        return f'<line x1="{cx:.2f}" y1="{cy:.2f}" x2="{ax:.2f}" y2="{ay:.2f}" class="leader"/>'
    return f'<path d="M {cx:.2f} {cy:.2f} L {cx:.2f} {ay:.2f} L {ax:.2f} {ay:.2f}" class="leader"/>'


AIRFLOW_PX = 84.0  # fixed block-arrow length (annotation — never scaled with geometry)


def _airflow_svg(ax: float, ay: float, direction: str) -> str:
    """A fixed-size outlined block arrow + "AIRFLOW" text, centered at (ax, ay) px. Points right
    for ``left_to_right`` (air flowing rightward), left for ``right_to_left``. Direction comes
    from the explicit enum only — it is mirror-INVARIANT, so LH and RH read the same way."""
    points_left = str(direction).strip().lower() in ("right_to_left", "rtl", "left")
    sign = -1.0 if points_left else 1.0
    half, h, head = AIRFLOW_PX / 2.0, 7.0, 16.0  # shaft half-len, shaft half-height, head length
    tip = ax + sign * half
    neck = tip - sign * head
    tail = ax - sign * half
    pts = [
        (tail, ay - h), (neck, ay - h), (neck, ay - 2 * h), (tip, ay),
        (neck, ay + 2 * h), (neck, ay + h), (tail, ay + h),
    ]
    poly = " ".join(f"{px:.2f},{py:.2f}" for px, py in pts)
    return (
        f'<g data-feature="airflow_arrow" data-direction="{_esc(direction)}">'
        f'<polygon points="{poly}" class="airflow"/>'
        f'<text x="{ax:.2f}" y="{ay - 2 * h - 4:.2f}" text-anchor="middle" class="airflow-label">AIRFLOW</text>'
        f"</g>"
    )


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

    geom: list[str] = []  # rects, circles, segments, dimension lines (fixed geometry)
    rects_px: dict[str, tuple[float, float, float, float]] = {}

    for lr in view.rects:
        r = lr.rect
        px = (x_px(r.x), y_px(r.y), r.w * ppi, r.h * ppi)
        rects_px[lr.feature] = px
        cls = _RECT_CLASS.get(lr.feature, "casing")
        geom.append(
            f'<rect data-feature="{_esc(lr.feature)}" x="{px[0]:.2f}" y="{px[1]:.2f}" '
            f'width="{px[2]:.2f}" height="{px[3]:.2f}" class="{cls}"/>'
        )

    for s in view.segments:
        cls = _SEGMENT_CLASS.get(s.feature, "stub")
        geom.append(
            f'<line data-feature="{_esc(s.feature)}" x1="{x_px(s.x1):.2f}" y1="{y_px(s.y1):.2f}" '
            f'x2="{x_px(s.x2):.2f}" y2="{y_px(s.y2):.2f}" class="{cls}"/>'
        )

    for c in view.circles:
        cls = _CIRCLE_CLASS.get(c.feature, "header-pipe")
        geom.append(
            f'<circle data-feature="{_esc(c.feature)}" cx="{x_px(c.cx):.2f}" cy="{y_px(c.cy):.2f}" '
            f'r="{c.r * ppi:.2f}" class="{cls}"/>'
        )

    # AIRFLOW arrow (plan view) — a FIXED-size block arrow (annotation rule: never scaled),
    # pointing per the explicit stored direction enum (mirror-invariant; not derived from hand).
    if view.airflow and view.airflow_anchor is not None:
        geom.append(_airflow_svg(x_px(view.airflow_anchor[0]), y_px(view.airflow_anchor[1]), view.airflow))

    # Collect EVERY text label (dim labels, EZ callouts, notes) into one list, then run a
    # single OBSTACLE-COMPLETE de-collision over all of them. The obstacle set is the fixed
    # dimension/witness lines + the connection glyphs (return circles, nozzle + stub segments),
    # so a label clears lines and glyphs, not just other labels.
    labels: list[_Label] = []
    obstacles: list[tuple[float, float, float, float]] = []
    for dim in view.dimensions:
        group, lab, line_boxes = _dimension_parts(dim, x_px, y_px)
        geom.append(group)
        labels.append(lab)
        obstacles.extend(line_boxes)
    for c in view.circles:
        r = c.r * ppi
        obstacles.append((x_px(c.cx) - r, y_px(c.cy) - r, x_px(c.cx) + r, y_px(c.cy) + r))
    # Plan-view supply tubes run the full FL — they too are obstacles (gated to "plan" so the V2
    # side view's light circuit-tie tube_runs stay non-obstacles and V2 output is unchanged).
    glyph_features = _GLYPH_OBSTACLE_FEATURES + (("tube_run",) if view.view == "plan" else ())
    for s in view.segments:
        if s.feature in glyph_features:
            obstacles.append(_seg_box(x_px(s.x1), y_px(s.y1), x_px(s.x2), y_px(s.y2)))
    for lb in view.labels:
        conn = (x_px(lb.connector[0]), y_px(lb.connector[1])) if lb.connector is not None else None
        # Review-bucket distributor callouts (DistModel/DistOD) are drawn FLAGGED — distinct CSS
        # + an explicit marker so an unconfirmed value can never be mistaken for a confirmed one.
        flagged = lb.feature in view.review_labels
        css = "review" if flagged else "callout"
        text = f"{lb.text} (REVIEW)" if flagged else lb.text
        labels.append(_Label(x_px(lb.x), y_px(lb.y), lb.anchor, css, text, conn, True, lb.feature))
    omitted_y = PAD_PX + 18
    for idx, note in enumerate(view.omitted_notes):
        labels.append(_Label(float(PAD_PX), float(omitted_y + idx * (FONT_PX + 4)), "start", "omitted", note))

    for lb in labels:
        lb.y0 = lb.y
    cp = rects_px.get("casing")
    casing_y = (cp[1], cp[1] + cp[3]) if cp else None
    decollide(labels, canvas_w / 2.0, obstacles, casing_y)

    leader_parts = [
        _leader_svg(lb)
        for lb in labels
        if lb.connector is not None
        and (lb.always_leader or abs(lb.y - lb.y0) > 1.5)
        and hypot(lb.connector[0] - lb.x, lb.connector[1] - lb.y) > LEADER_MIN_PX
    ]
    text_parts = [_label_svg(lb) for lb in labels]

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {canvas_w} {canvas_h}" role="img" aria-label="CoilForge parametric {_esc(view.view)} view (review aid)">
  <defs>
    <marker id="schem-arrow" markerWidth="{ARROW_PX}" markerHeight="{ARROW_PX}" refX="{ARROW_PX - 1}" refY="{ARROW_PX / 2:.1f}" orient="auto">
      <path d="M 0 0 L {ARROW_PX} {ARROW_PX / 2:.1f} L 0 {ARROW_PX} z" fill="#242092"/>
    </marker>
    <style>
      .casing {{ fill: #fbfbfb; stroke: #1f2937; stroke-width: 2; }}
      .finned {{ fill: #eef2ff; stroke: #4b5563; stroke-width: 1.5; }}
      .header-pipe {{ fill: #e0e7ff; stroke: #1f2937; stroke-width: 1.5; }}
      .connection {{ fill: #ffffff; stroke: #4b5563; stroke-width: 1.5; }}
      .stub {{ stroke: #1f2937; stroke-width: 1.5; fill: none; }}
      .nozzle {{ stroke: #1f2937; stroke-width: 1.5; fill: none; }}
      .feeder {{ stroke: #4b5563; stroke-width: 1.1; fill: none; }}
      .dist-ext {{ stroke: #1f2937; stroke-width: 1.8; fill: none; }}
      .airflow {{ fill: #eef2ff; stroke: #242092; stroke-width: 1.2; }}
      .airflow-label {{ fill: #242092; font: 700 {FONT_PX}px Arial, sans-serif; }}
      .row {{ stroke: #c7cce8; stroke-width: 0.8; fill: none; }}
      .ext-line {{ stroke: #9aa0c4; stroke-width: 0.8; fill: none; }}
      .dim-arrows {{ stroke: #242092; stroke-width: 1.2; fill: none; marker-start: url(#schem-arrow); marker-end: url(#schem-arrow); }}
      .witness {{ stroke: #242092; stroke-width: 1.1; fill: none; }}
      .leader {{ stroke: #242092; stroke-width: 0.9; fill: none; }}
      .dim-label {{ fill: #0d0877; font: 700 {FONT_PX}px Arial, sans-serif; }}
      .callout {{ fill: #1f2937; font: 600 {FONT_PX}px Arial, sans-serif; }}
      .review {{ fill: #92400e; font: 700 {FONT_PX}px Arial, sans-serif; }}
      .omitted {{ fill: #92400e; font: 700 {FONT_PX}px Arial, sans-serif; }}
      .watermark {{ fill: #b91c1c; font: 800 16px Arial, sans-serif; }}
      .meta {{ fill: #475569; font: 11px Arial, sans-serif; }}
    </style>
  </defs>
  <g id="zone.{_esc(view.view)}_view">
    {''.join(geom)}
    {''.join(leader_parts)}
    {''.join(text_parts)}
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


def _dimension_parts(dim: Dimension, x_px, y_px):  # noqa: ANN001 - local px mappers
    """Return (fixed-geometry <g data-dim …>, collected text _Label, line-segment bboxes). The
    value text is NOT inside the group, so de-collision can move it (a leader is redrawn); the
    returned bboxes let the value (and every other label) be kept CLEAR of the dim lines. The
    value is seated a clear gap OFF its own line — never centered on it."""
    ax, ay = x_px(dim.ax), y_px(dim.ay)
    bx, by = x_px(dim.bx), y_px(dim.by)
    horizontal_edge = dim.edge in ("top", "bottom")
    tp = y_px(dim.tier_pos) if horizontal_edge else x_px(dim.tier_pos)

    # Overalls (CD/CH + spacing S/R) draw as tiered arrows like EZC-0007 — regardless of span,
    # so short spacings tier cleanly instead of piling up as leaders. Offsets (I/O/SL) stay
    # leader-style (their span is the offset itself).
    arrows = dim.kind == "overall"
    off = 0.25 * FONT_PX + LABEL_GAP + 4  # vertical clearance so the value clears its own line

    if horizontal_edge:
        lpar = (ax + bx) / 2.0
        # Value BEYOND the datum end (away from the measured point), off the line — like
        # EZC-0007, so it never sits where the dimension ext-lines run. ``dirn`` flips under the
        # x-mirror with ax/bx, and the end<->start anchor flips with it, so the placement stays
        # mirror-covariant (the y-only de-collision then matches LH/RH).
        dirn = -1.0 if ax <= bx else 1.0
        lx = ax + dirn * 4.0
        anchor = "end" if dirn < 0 else "start"
        ly = tp - off if dim.edge == "top" else tp + 0.8 * FONT_PX + LABEL_GAP + 4
    else:
        lpar = (ay + by) / 2.0
        if dim.edge == "left":
            lx, ly, anchor = tp - 8, lpar + 4, "end"  # value BESIDE the vertical line
        else:
            lx, ly, anchor = tp + 8, lpar + 4, "start"

    if arrows:
        if horizontal_edge:
            segs = [(ax, ay, ax, tp), (bx, by, bx, tp), (ax, tp, bx, tp)]
            lines = [
                f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{ax:.2f}" y2="{tp:.2f}" class="ext-line"/>',
                f'<line x1="{bx:.2f}" y1="{by:.2f}" x2="{bx:.2f}" y2="{tp:.2f}" class="ext-line"/>',
                f'<line x1="{ax:.2f}" y1="{tp:.2f}" x2="{bx:.2f}" y2="{tp:.2f}" class="dim-arrows"/>',
            ]
            connector = (lpar, tp)
        else:
            segs = [(ax, ay, tp, ay), (bx, by, tp, by), (tp, ay, tp, by)]
            lines = [
                f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{tp:.2f}" y2="{ay:.2f}" class="ext-line"/>',
                f'<line x1="{bx:.2f}" y1="{by:.2f}" x2="{tp:.2f}" y2="{by:.2f}" class="ext-line"/>',
                f'<line x1="{tp:.2f}" y1="{ay:.2f}" x2="{tp:.2f}" y2="{by:.2f}" class="dim-arrows"/>',
            ]
            connector = (tp, lpar)
        style, always = "arrows", False
    else:
        # leader style: the witness is the fixed geometry; the leader to the label is drawn
        # AFTER de-collision, from the witness midpoint to the label's final position.
        segs = [(ax, ay, bx, by)]
        lines = [f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" y2="{by:.2f}" class="witness"/>']
        connector = ((ax + bx) / 2.0, (ay + by) / 2.0)
        style, always = "leader", True

    text = f"{dim.value:.2f} {dim.label}" if dim.value is not None else dim.label
    group = f'<g data-dim="{_esc(dim.label)}" data-style="{style}">{"".join(lines)}</g>'
    label = _Label(lx, ly, anchor, "dim-label", text, connector=connector, always_leader=always)
    return group, label, [_seg_box(*s) for s in segs]
