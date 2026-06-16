"""Layer 2 — layout / datum engine (real inches only, no pixels).

Turns a :class:`CoilGeometry` into one or more :class:`ViewLayout`s — rectangles,
circles, segments and dimensions placed by datum/offset arithmetic in inches. There are
no absolute hardcoded coordinates and no presentation scale here. Pixels appear only in
the SVG backend (Layer 3).

Two views are produced for a DX coil:

* **front** — casing CL×CH with the inset finned face FL×FH and the TF/BF/HF/RF flanges
  (canonical hand = HF on the left).
* **side** (header/end view) — casing depth CD × casing height CH, with the supply and
  return headers as circles on the header-face (canonical = left) edge, the return's stub
  (SL2) + connection, and optional ROWS tube lines.

Both views share one **tiered dimensioning** placement (Phase 1.5): each dimension is
tagged ``overall`` or ``offset`` and stacked per edge — offsets on the inner tiers,
overalls outside them — so labels never collide (the backend additionally draws small
spans with a leader). ``tier_pos`` is reusable, pure tier math derived from the part.

LH↔RH is a single deterministic x-mirror (:func:`mirror_view_x`) applied once to a built
view — never a hand-coded second layout. :func:`build_dx_views` is the one call site that
mirrors (both views) when the coil hand is right.

``None``/"REVIEW REQUIRED" slots → the feature is omitted + annotated, never invented.
"""

from __future__ import annotations

from dataclasses import dataclass

from coilforge.drawing.schematic_model import CoilGeometry

# Tier step as a fraction of the part's larger side, so dimension tiers scale with the
# drawing under fit-to-canvas.
STEP_FRACTION = 0.06
_EDGES = ("top", "bottom", "left", "right")
_EDGE_SWAP = {"left": "right", "right": "left", "top": "top", "bottom": "bottom"}


@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle in inches (x, y = top-left)."""

    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class LabeledRect:
    feature: str
    rect: Rect


@dataclass(frozen=True)
class Circle:
    feature: str
    cx: float
    cy: float
    r: float


@dataclass(frozen=True)
class Segment:
    feature: str
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class Label:
    """A fixed-size text callout anchored at an inch position (e.g. a header Ø note)."""

    feature: str
    x: float
    y: float
    text: str


@dataclass(frozen=True)
class Dimension:
    """A single dimension in inches. WHERE it goes (the backend decides HOW to draw it)."""

    label: str
    kind: str  # "overall" | "offset"
    edge: str  # "top" | "bottom" | "left" | "right"
    tier: int  # stacked per edge: offsets inner (0..), overalls outside
    orient: str  # "h" | "v" — direction the measured span runs
    ax: float
    ay: float
    bx: float
    by: float
    tier_pos: float  # perpendicular tier coordinate (y for top/bottom, x for left/right)
    value: float | None = None  # measured value in inches (the number the backend prints)


@dataclass(frozen=True)
class ViewLayout:
    """Resolved geometry for one view, in inches — ready for any backend."""

    view: str  # "front" | "side"
    extent_w: float
    extent_h: float
    rects: tuple[LabeledRect, ...]
    circles: tuple[Circle, ...]
    segments: tuple[Segment, ...]
    labels: tuple[Label, ...]
    dimensions: tuple[Dimension, ...]
    omitted_notes: tuple[str, ...]


@dataclass(frozen=True)
class _DimReq:
    """A requested dimension before its tier (and tier_pos) are assigned."""

    label: str
    kind: str
    edge: str
    orient: str
    ax: float
    ay: float
    bx: float
    by: float
    # Explicit measured value (inches). When None, place_dimensions derives it from the
    # endpoint span along `orient` (true for every datum-span dim). Set it for callouts
    # whose number is a property, not a span (e.g. a header diameter HDx1/HD2).
    value: float | None = None


def _omit(label: str) -> str:
    return f"{label}: REVIEW REQUIRED (omitted)"


def tier_pos(casing: Rect, edge: str, tier: int, step: float, base: float = 0.0) -> float:
    """Perpendicular coordinate of a dimension tier, outward from a casing edge (inches).

    ``base`` pushes the whole tier stack further out (e.g. to clear features that
    protrude past the edge, like the header stub on the left).
    """
    out = base + step * (tier + 1)
    if edge == "top":
        return casing.y - out
    if edge == "bottom":
        return casing.y + casing.h + out
    if edge == "left":
        return casing.x - out
    if edge == "right":
        return casing.x + casing.w + out
    raise ValueError(f"unknown edge: {edge}")


def place_dimensions(
    reqs: list[_DimReq], casing: Rect, step: float, edge_base: dict[str, float] | None = None
) -> list[Dimension]:
    """Stack dimensions per edge — offsets on inner tiers, overalls outside them.

    Reusable across views: any number of offsets/overalls on one edge gets distinct,
    collision-free tiers (offset tiers are always disjoint from overall tiers). ``edge_base``
    pushes a given edge's whole stack further out (to clear protruding features).
    """
    edge_base = edge_base or {}
    placed: list[Dimension] = []
    for edge in _EDGES:
        group = [r for r in reqs if r.edge == edge]
        group.sort(key=lambda r: 0 if r.kind == "offset" else 1)  # offsets inner first
        for tier, r in enumerate(group):
            value = r.value if r.value is not None else (
                abs(r.bx - r.ax) if r.orient == "h" else abs(r.by - r.ay)
            )
            placed.append(
                Dimension(
                    r.label, r.kind, edge, tier, r.orient, r.ax, r.ay, r.bx, r.by,
                    tier_pos(casing, edge, tier, step, edge_base.get(edge, 0.0)),
                    value,
                )
            )
    return placed


# --------------------------------------------------------------------------- #
# Front view
# --------------------------------------------------------------------------- #
def layout_dx_front_view(geom: CoilGeometry) -> ViewLayout:
    notes: list[str] = []
    cl, ch = geom.casing_length, geom.casing_height
    fl, fh = geom.finned_length, geom.finned_height

    if cl is not None and ch is not None:
        step = STEP_FRACTION * max(cl, ch)
    elif fl is not None and fh is not None:
        step = STEP_FRACTION * max(fl, fh)
    else:
        step = STEP_FRACTION
    margin = 3 * step  # room for one offset tier + one overall tier + labels

    rects: list[LabeledRect] = []
    reqs: list[_DimReq] = []
    segments: list[Segment] = []

    casing: Rect | None
    if cl is not None and ch is not None:
        casing = Rect(margin, margin, cl, ch)
        extent_w, extent_h = cl + 2 * margin, ch + 2 * margin
        rects.append(LabeledRect("casing", casing))
    else:
        casing = None
        if cl is None:
            notes.append(_omit("CL"))
        if ch is None:
            notes.append(_omit("CH"))
        extent_w, extent_h = (fl or 1.0) + 2 * margin, (fh or 1.0) + 2 * margin

    finned: Rect | None = None
    if fl is not None and fh is not None and casing is not None:
        if geom.header_flange is not None:
            fx = casing.x + geom.header_flange
        elif geom.return_flange is not None:
            fx = casing.x + casing.w - geom.return_flange - fl
        else:
            fx = casing.x + (casing.w - fl) / 2.0
        if geom.top_flange is not None:
            fy = casing.y + geom.top_flange
        elif geom.bottom_flange is not None:
            fy = casing.y + casing.h - geom.bottom_flange - fh
        else:
            fy = casing.y + (casing.h - fh) / 2.0
        finned = Rect(fx, fy, fl, fh)
        rects.append(LabeledRect("finned", finned))
    else:
        if fl is None:
            notes.append(_omit("FL"))
        if fh is None:
            notes.append(_omit("FH"))
        notes.append("finned face: REVIEW REQUIRED (omitted)")

    if finned is not None and casing is not None:
        reqs.append(_DimReq("FL", "overall", "top", "h", finned.x, finned.y, finned.x + finned.w, finned.y))
        reqs.append(_DimReq("FH", "overall", "right", "v", finned.x + finned.w, finned.y, finned.x + finned.w, finned.y + finned.h))
    if casing is not None:
        reqs.append(_DimReq("CL", "overall", "bottom", "h", casing.x, casing.y + casing.h, casing.x + casing.w, casing.y + casing.h))
        reqs.append(_DimReq("CH", "overall", "left", "v", casing.x, casing.y, casing.x, casing.y + casing.h))
    if casing is not None and finned is not None:
        mid_x = finned.x + finned.w / 2.0
        mid_y = finned.y + finned.h / 2.0
        cb, fb = casing.y + casing.h, finned.y + finned.h
        cr, fr = casing.x + casing.w, finned.x + finned.w
        if geom.top_flange is not None:
            reqs.append(_DimReq("TF", "offset", "top", "v", mid_x, casing.y, mid_x, finned.y))
        else:
            notes.append(_omit("TF"))
        if geom.bottom_flange is not None:
            reqs.append(_DimReq("BF", "offset", "bottom", "v", mid_x, fb, mid_x, cb))
        else:
            notes.append(_omit("BF"))
        if geom.header_flange is not None:
            reqs.append(_DimReq("HF", "offset", "left", "h", casing.x, mid_y, finned.x, mid_y))
        else:
            notes.append(_omit("HF"))
        if geom.return_flange is not None:
            reqs.append(_DimReq("RF", "offset", "right", "h", fr, mid_y, cr, mid_y))
        else:
            notes.append(_omit("RF"))

    # Return-bend end: OAL = CL + RB protrudes past the casing on the return side
    # (canonical right). Draw a light bend-extreme line and dimension OAL (overall) +
    # RB (offset) on the bottom edge; they stack collision-free with CL via the tiers.
    if casing is not None:
        oal, rb = geom.overall_length, geom.return_bend
        cb = casing.y + casing.h
        if oal is not None and oal > casing.w:
            bend_x = casing.x + oal
            extent_w = max(extent_w, bend_x + margin)
            segments.append(Segment("return_bend", bend_x, casing.y, bend_x, cb))
            reqs.append(_DimReq("OAL", "overall", "bottom", "h", casing.x, cb, bend_x, cb, value=oal))
            if rb is not None:
                reqs.append(_DimReq("RB", "offset", "bottom", "h", casing.x + casing.w, cb, bend_x, cb, value=rb))
            else:
                notes.append(_omit("RB"))
        else:
            if oal is None:
                notes.append(_omit("OAL"))
            if rb is None:
                notes.append(_omit("RB"))

    dims = place_dimensions(reqs, casing, step) if casing is not None else []
    return ViewLayout(
        "front", extent_w, extent_h, tuple(rects), (), tuple(segments), (), tuple(dims),
        tuple(dict.fromkeys(notes)),
    )


# --------------------------------------------------------------------------- #
# Header / side (end) view
# --------------------------------------------------------------------------- #
def layout_header_side_view(geom: CoilGeometry) -> ViewLayout:
    """End view (CD x CH). Headers are drawn as their small CONNECTIONS (to scale) at the
    header-face (canonical = left) edge; the manifold diameter HD is a label, not a circle.
    Connection heights come from I1/O2 (from the casing bottom); the return carries the SL2
    stub; the supply distributor has no stubout (per EZ data)."""
    notes: list[str] = []
    cd, ch = geom.casing_depth, geom.casing_height

    if cd is not None and ch is not None:
        step = STEP_FRACTION * max(cd, ch)
    elif ch is not None:
        step = STEP_FRACTION * ch
    else:
        step = STEP_FRACTION
    base_margin = 4 * step

    # How far connections/stubs reach left of the header face (the manifold HD is NOT drawn).
    def _reach(h: HeaderSpec) -> float:
        r = (h.connection_diameter / 2.0) if h.connection_diameter is not None else 0.0
        if h.role == "return":
            return (h.stub_length or 0.0) + r
        if h.extension is not None:
            return h.extension + r  # supply distributor extension stub
        return 2.0 * r  # a circle tangent just outside the face reaches 2r
    protrusion = max((_reach(h) for h in geom.headers), default=0.0)
    left_margin = max(base_margin, protrusion + 3 * step)  # protrusion + 2 dim tiers + label

    rects: list[LabeledRect] = []
    circles: list[Circle] = []
    segments: list[Segment] = []
    labels: list[Label] = []
    reqs: list[_DimReq] = []

    casing: Rect | None
    if cd is not None and ch is not None:
        casing = Rect(left_margin, base_margin, cd, ch)
        extent_w = left_margin + cd + base_margin
        extent_h = 2 * base_margin + ch
        rects.append(LabeledRect("casing", casing))
    else:
        casing = None
        if cd is None:
            notes.append(_omit("CD"))
        if ch is None:
            notes.append(_omit("CH"))
        extent_w = left_margin + (cd or 1.0) + base_margin
        extent_h = 2 * base_margin + (ch or 1.0)

    if casing is not None:
        bottom = casing.y + casing.h
        if geom.rows and geom.rows > 1:
            for i in range(1, geom.rows):
                x = casing.x + i * casing.w / geom.rows
                segments.append(Segment("row", x, casing.y, x, bottom))

        kept: list[tuple[float, float, float]] = []  # (cx, cy, r) of placed connections
        for h in geom.headers:
            dia_label = "HDx1" if h.role == "supply" else "HD2"
            off_label = "I1" if h.role == "supply" else "O2"
            cy = bottom - h.offset if h.offset is not None else casing.y + casing.h / 2.0
            if h.offset is not None:
                # offset dim on the LEFT (connection) side, from the bottom to the connection.
                reqs.append(_DimReq(off_label, "offset", "left", "v", casing.x, bottom, casing.x, cy))
            else:
                notes.append(_omit(off_label))

            # S1 (supply) / R2 (return): the header's depth position along CD, measured
            # from the front (left) edge — a top-edge horizontal dim (hand-mirrored with
            # the view). S1 = CD/2 reads as a centered distributor.
            sp_label = "S1" if h.role == "supply" else "R2"
            if h.spacing is not None:
                reqs.append(_DimReq(sp_label, "offset", "top", "h", casing.x, casing.y, casing.x + h.spacing, casing.y, value=h.spacing))
            else:
                notes.append(_omit(sp_label))

            r = (h.connection_diameter / 2.0) if h.connection_diameter is not None else None
            if h.role == "return":
                if h.stub_length is not None:
                    sx = casing.x - h.stub_length
                    segments.append(Segment("stub", casing.x, cy, sx, cy))
                    reqs.append(_DimReq("SL2", "offset", "bottom", "h", sx, cy, casing.x, cy))
                    conn_cx = sx
                else:
                    notes.append(_omit("SL2"))
                    conn_cx = casing.x
            else:  # supply distributor — extension stub (DIST_EXT), mirror of the return SL2
                if h.extension is not None:
                    sx = casing.x - h.extension
                    segments.append(Segment("stub", casing.x, cy, sx, cy))
                    reqs.append(_DimReq("DIST_EXT", "offset", "bottom", "h", sx, cy, casing.x, cy, value=h.extension))
                    conn_cx = sx
                else:
                    conn_cx = casing.x - (r or 0.0)  # tangent just outside the face

            if r is not None:
                # overlap guard: never draw physically-impossible overlapping connections.
                if any((conn_cx - px) ** 2 + (cy - py) ** 2 < (r + pr - 0.05) ** 2 for px, py, pr in kept):
                    notes.append(f"{dia_label} connection overlaps another — review required (omitted)")
                else:
                    kept.append((conn_cx, cy, r))
                    circles.append(Circle(f"connection_{h.role}", conn_cx, cy, r))
            else:
                notes.append(_omit(f"{dia_label} connection size"))

            if h.diameter is not None:
                # Numbers-only callout (the diameter), placed at the header. The label
                # code (HDx1/HD2) is dropped per direct-coil ordering; it stays on the
                # SVG `data-label` attribute for identification.
                labels.append(Label(f"hd_{h.role}", conn_cx, cy - (r or 0.0) - 0.4 * step, f"{h.diameter:g}"))
            else:
                notes.append(_omit(dia_label))

        reqs.append(_DimReq("CD", "overall", "bottom", "h", casing.x, bottom, casing.x + casing.w, bottom))
        reqs.append(_DimReq("CH", "overall", "right", "v", casing.x + casing.w, casing.y, casing.x + casing.w, bottom))

    edge_base = {"left": protrusion} if casing is not None else {}
    dims = place_dimensions(reqs, casing, step, edge_base) if casing is not None else []
    return ViewLayout(
        "side", extent_w, extent_h, tuple(rects), tuple(circles), tuple(segments),
        tuple(labels), tuple(dims), tuple(dict.fromkeys(notes)),
    )


# --------------------------------------------------------------------------- #
# LH <-> RH mirror — single source of truth, applied to a built view
# --------------------------------------------------------------------------- #
def _mirror_dim(d: Dimension, extent_w: float) -> Dimension:
    edge = _EDGE_SWAP[d.edge]
    # tier_pos is an x for left/right edges (reflect), a y for top/bottom (unchanged).
    tp = extent_w - d.tier_pos if d.edge in ("left", "right") else d.tier_pos
    return Dimension(
        d.label, d.kind, edge, d.tier, d.orient,
        extent_w - d.ax, d.ay, extent_w - d.bx, d.by, tp, d.value,
    )


def mirror_view_x(view: ViewLayout) -> ViewLayout:
    """Reflect a view about its vertical centerline (x = extent_w/2). Involutive."""
    w = view.extent_w
    rects = tuple(
        LabeledRect(lr.feature, Rect(w - (lr.rect.x + lr.rect.w), lr.rect.y, lr.rect.w, lr.rect.h))
        for lr in view.rects
    )
    circles = tuple(Circle(c.feature, w - c.cx, c.cy, c.r) for c in view.circles)
    segments = tuple(Segment(s.feature, w - s.x1, s.y1, w - s.x2, s.y2) for s in view.segments)
    labels = tuple(Label(lb.feature, w - lb.x, lb.y, lb.text) for lb in view.labels)
    dims = tuple(_mirror_dim(d, w) for d in view.dimensions)
    return ViewLayout(view.view, view.extent_w, view.extent_h, rects, circles, segments, labels, dims, view.omitted_notes)


def build_dx_views(geom: CoilGeometry) -> dict[str, ViewLayout]:
    """Both views, hand-correct. The mirror is applied here, once, for a right hand."""
    views = {"front": layout_dx_front_view(geom), "side": layout_header_side_view(geom)}
    if str(geom.coil_hand).strip().upper().startswith("R"):
        views = {name: mirror_view_x(v) for name, v in views.items()}
    return views
