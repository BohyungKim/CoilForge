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

from coilforge.drawing.schematic_model import CoilGeometry, HeaderSpec
from coilforge.drawing.topology import Topology, resolve_topology

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
    """A fixed-size text callout anchored at an inch position (e.g. a header Ø note).

    ``connector`` is the feature point the label belongs to (inches); the backend draws a
    leader to it after de-collision so the label never detaches from its feature.
    """

    feature: str
    x: float
    y: float
    text: str
    connector: tuple[float, float] | None = None
    anchor: str = "middle"  # "start" | "middle" | "end"; flips start<->end under the x-mirror


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
    value: float | None = None  # measured inches, for the EZ "{value} {CODE}" label


@dataclass(frozen=True)
class ViewLayout:
    """Resolved geometry for one view, in inches — ready for any backend."""

    view: str  # "front" | "side" | "plan"
    extent_w: float
    extent_h: float
    rects: tuple[LabeledRect, ...]
    circles: tuple[Circle, ...]
    segments: tuple[Segment, ...]
    labels: tuple[Label, ...]
    dimensions: tuple[Dimension, ...]
    omitted_notes: tuple[str, ...]
    # V3 plan view extras (additive; front/side leave these defaulted so their output is identical).
    airflow: str | None = None  # AIRFLOW arrow direction enum; DIRECTION is mirror-INVARIANT
    airflow_anchor: tuple[float, float] | None = None  # arrow anchor point in inches (x reflects)
    review_labels: tuple[str, ...] = ()  # callout features drawn FLAGGED for review


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
            placed.append(
                Dimension(
                    r.label, r.kind, edge, tier, r.orient, r.ax, r.ay, r.bx, r.by,
                    tier_pos(casing, edge, tier, step, edge_base.get(edge, 0.0)), r.value,
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

    dims = place_dimensions(reqs, casing, step) if casing is not None else []
    return ViewLayout(
        "front", extent_w, extent_h, tuple(rects), (), (), (), tuple(dims),
        tuple(dict.fromkeys(notes)),
    )


# --------------------------------------------------------------------------- #
# Header / side (end) view
# --------------------------------------------------------------------------- #
def _spread_x(casing: Rect, h: HeaderSpec) -> float | None:
    """Depth position of a header along the spread axis (CD), from its spacing S/R.
    ``None`` when the spacing slot was missing — the caller omits + annotates."""
    if h.spacing is None:
        return None
    return casing.x + min(max(h.spacing, 0.0), casing.w)


def layout_header_side_view(geom: CoilGeometry, *, supply_kind: str = "distributor") -> ViewLayout:
    """End / spread view (CH high x CD wide) — faithful to the EZ DX convention
    (EZC-0001 / EZC-0007). Circuits are positioned ALONG the depth (CD) by their spacing
    (``S{odd}`` / ``R{even}``); supply distributors sit near the TOP edge (offset ``I`` down),
    return connections near the BOTTOM edge (offset ``O`` up). ``I``/``O`` is a per-row
    CONSTANT and ``S``/``R`` is what positions each circuit, so every connection is
    dual-dimensioned (offset I/O + spacing S/R). The supply is a nozzle glyph (no sweat
    circle, per EZ); the return is a connection circle + ``SL`` stub. ``None`` /
    "REVIEW REQUIRED" → the feature is omitted + annotated. LH<->RH is the single x-mirror."""
    notes: list[str] = []
    cd, ch = geom.casing_depth, geom.casing_height

    if cd is not None and ch is not None:
        step = STEP_FRACTION * max(cd, ch)
    elif ch is not None:
        step = STEP_FRACTION * ch
    else:
        step = STEP_FRACTION

    supplies = [h for h in geom.headers if h.role == "supply"]
    returns = [h for h in geom.headers if h.role == "return"]
    circuits = max(len(supplies), len(returns), 1)

    # A return's stub reaches below the bottom edge by SL beyond its O offset.
    def _below(h: HeaderSpec) -> float:
        if h.stub_length is None:
            return 0.0
        return max(0.0, h.stub_length - (h.offset or 0.0))
    protrusion = max((_below(h) for h in returns), default=0.0)

    # Margins fit the dim band: top carries S spacing (circuits) + CD; bottom carries R
    # spacing (circuits) + SL, cleared past the stub protrusion. (Header diameters HDx/HD are
    # NOT drawn here — EZ shows them in the wider header strip; deferred to Phase 4.)
    top_margin = max(4.0, circuits + 3) * step
    bottom_margin = max(top_margin, protrusion + (circuits + 3) * step)
    left_margin = right_margin = 4 * step

    rects: list[LabeledRect] = []
    circles: list[Circle] = []
    segments: list[Segment] = []
    labels: list[Label] = []
    reqs: list[_DimReq] = []

    casing: Rect | None
    if cd is not None and ch is not None:
        casing = Rect(left_margin, top_margin, cd, ch)
        extent_w = left_margin + cd + right_margin
        extent_h = top_margin + ch + bottom_margin
        rects.append(LabeledRect("casing", casing))
    else:
        casing = None
        if cd is None:
            notes.append(_omit("CD"))
        if ch is None:
            notes.append(_omit("CH"))
        extent_w = left_margin + (cd or 1.0) + right_margin
        extent_h = top_margin + (ch or 1.0) + bottom_margin

    if casing is not None:
        top = casing.y
        bottom = casing.y + casing.h
        datum_x = casing.x  # spacing measured rightward from the header-face datum

        # ROWS as faint lines across the depth (CD) — the spread axis.
        if geom.rows and geom.rows > 1:
            for i in range(1, geom.rows):
                x = casing.x + i * casing.w / geom.rows
                segments.append(Segment("row", x, top, x, bottom))

        # --- supply distributors: top row, offset I down, spaced by S ---
        # Offset I is a per-row constant in EZ -> dimension it ONCE per distinct value (bare
        # "I"); spacing S stays one per circuit (it positions them). Diameter HDx goes OUTSIDE
        # the casing (above the top edge) on a leader.
        supply_offsets: set[float] = set()
        kept_supply: list[tuple[float, float, float]] = []  # plain-header supply ports (overlap guard)
        for h in supplies:
            sp_lab = f"S{h.index}"
            cx = _spread_x(casing, h)
            if cx is None:
                cx = casing.x + casing.w / 2.0
                notes.append(_omit(sp_lab))
            else:
                reqs.append(_DimReq(sp_lab, "overall", "top", "h", datum_x, top, cx, top, h.spacing))
            cy = top + h.offset if h.offset is not None else top + step
            if h.offset is not None:
                key = round(h.offset, 3)
                if key not in supply_offsets:  # one bare "I" dim per distinct value, not per circuit
                    supply_offsets.add(key)
                    # EZ draws the supply offset on the LEFT (value beside), out of the nozzle column
                    reqs.append(_DimReq("I", "offset", "left", "v", casing.x, top, casing.x, cy, h.offset))
            else:
                notes.append(_omit(f"I{h.index}"))
            if supply_kind == "plain_header":
                # plain supply header port (HGRH/CWC/HWC): reuse the EXISTING connection circle
                # primitive at the supply I/S position — NO distributor glyph (the styled
                # supply_header_port glyph is Phase 5b). Sized by the supply header Ø (HDx).
                r = h.diameter / 2.0 if h.diameter is not None else None
                if r is None:
                    notes.append(_omit(f"HDx{h.index} supply port size"))
                elif any((cx - px) ** 2 + (cy - py) ** 2 < (r + pr - 0.05) ** 2 for px, py, pr in kept_supply):
                    notes.append(f"supply {h.index} port overlaps another — review required (omitted)")
                else:
                    kept_supply.append((cx, cy, r))
                    circles.append(Circle("connection_supply", cx, cy, r))
            else:
                # nozzle glyph (downward triangle) — NO sweat circle (per EZ distributor rule). The
                # header diameter HDx is NOT labelled here (shown in the header strip — Phase 4).
                fw, fd = 0.16 * casing.w, 0.5 * step
                segments.append(Segment("distributor_supply", cx - fw, cy, cx + fw, cy))
                segments.append(Segment("distributor_supply", cx - fw, cy, cx, cy + fd))
                segments.append(Segment("distributor_supply", cx + fw, cy, cx, cy + fd))

        # --- return connections: bottom row, offset O up, spaced by R, + SL stub ---
        # Offset O dimensioned ONCE per distinct value (bare "O"); spacing R one per circuit.
        # Diameter HD goes OUTSIDE (below the bottom edge); the shared RETURN conn-size is
        # labelled ONCE. Geometry (circle at the stub end, stub, glyphs) is unchanged.
        kept: list[tuple[float, float, float]] = []  # (cx, cy, r) placed connections
        return_offsets: set[float] = set()
        for h in returns:
            dia_lab, sp_lab = f"HD{h.index}", f"R{h.index}"  # dia_lab only used in the conn notes
            cx = _spread_x(casing, h)
            if cx is None:
                cx = casing.x + casing.w / 2.0
                notes.append(_omit(sp_lab))
            else:
                reqs.append(_DimReq(sp_lab, "overall", "bottom", "h", datum_x, bottom, cx, bottom, h.spacing))
            cy = bottom - h.offset if h.offset is not None else bottom - step
            if h.offset is not None:
                key = round(h.offset, 3)
                if key not in return_offsets:  # one bare "O" dim per distinct value, not per circuit
                    return_offsets.add(key)
                    # EZ draws the return offset on the RIGHT (value beside), out of the return column
                    right = casing.x + casing.w
                    reqs.append(_DimReq("O", "offset", "right", "v", right, cy, right, bottom, h.offset))
            else:
                notes.append(_omit(f"O{h.index}"))
            # The header diameter HD is NOT labelled here (shown in the header strip — Phase 4).
            # stub down + sweat connection circle at its end (GEOMETRY UNCHANGED)
            conn_cy = cy
            if h.stub_length is not None:
                conn_cy = cy + h.stub_length
                segments.append(Segment("stub", cx, cy, cx, conn_cy))  # SL dimensioned in the header strip (Phase 4)
            if h.connection_diameter is not None:
                r = h.connection_diameter / 2.0
                # overlap guard: never draw physically-impossible overlapping connections.
                if any((cx - px) ** 2 + (conn_cy - py) ** 2 < (r + pr - 0.05) ** 2 for px, py, pr in kept):
                    notes.append(f"{dia_lab} connection overlaps another — review required (omitted)")
                else:
                    kept.append((cx, conn_cy, r))
                    circles.append(Circle("connection_return", cx, conn_cy, r))
                    # The RETURN connection size is a data-table / header-strip item (Phase 4),
                    # not a spread-view callout — EZC-0007 keeps it out of the narrow end view.
            else:
                notes.append(_omit(f"{dia_lab} connection size"))

        # --- tube runs: supply id 2k-1 -> return id 2k (light, ties each circuit) ---
        ret_by_id = {h.index: h for h in returns}
        for s in supplies:
            r = ret_by_id.get(s.index + 1)
            if r is None:
                continue
            sx, rx = _spread_x(casing, s), _spread_x(casing, r)
            if sx is None or rx is None:
                continue
            sy = top + (s.offset if s.offset is not None else step)
            ry = bottom - (r.offset if r.offset is not None else step)
            segments.append(Segment("tube_run", sx, sy, rx, ry))

        if supplies:
            if supply_kind == "plain_header":
                notes.append("supply: plain header ports (no distributor)")
            else:
                notes.append("supply distributors: nozzle glyphs, no sweat connection (per EZ data)")
        reqs.append(_DimReq("CD", "overall", "top", "h", casing.x, top, casing.x + casing.w, top, cd))
        reqs.append(_DimReq("CH", "overall", "right", "v", casing.x + casing.w, top, casing.x + casing.w, bottom, ch))

    edge_base = {"bottom": protrusion} if casing is not None else {}
    dims = place_dimensions(reqs, casing, step, edge_base) if casing is not None else []
    return ViewLayout(
        "side", extent_w, extent_h, tuple(rects), tuple(circles), tuple(segments),
        tuple(labels), tuple(dims), tuple(dict.fromkeys(notes)),
    )


# --------------------------------------------------------------------------- #
# Plan / top view (V3 distributor strip)
# --------------------------------------------------------------------------- #
def _fmt_in(value: float) -> str:
    """EZ value text: 2-decimals, trailing zeros trimmed to a tidy callout (3.50 / 0.625)."""
    return f"{value:.3f}".rstrip("0").rstrip(".")


def layout_plan_top_view(geom: CoilGeometry, *, supply_kind: str = "distributor") -> ViewLayout:
    """V3 plan/top view — the distributor strip, looking down (``CD`` wide x ``FL`` deep).

    Orientation reproduces the real CDXC drawings (EZC-0001/-0007): the **header end is the TOP
    edge**, circuits spread across the depth ``CD`` (horizontal) by their ``S``/``R`` spacing
    exactly like V2 (so the proven, legible tiered top/bottom dimensioning is reused), the supply
    tubes run the length ``FL`` (downward). The ``I``/``O`` offsets stay the per-row inset from the
    header/return edge. LH<->RH is the single x-mirror (reverses the S/R order — the hand
    difference). ADDS the distributor detail — a simplified-symbol nozzle funnel glyph, a feeder
    fan (one apex -> N supply circuits), the DistExtension stem, stub pipes + end-caps — the
    AIRFLOW arrow, and the Phase-3c-deferred labels (``HDx``/``HD`` Ø, ``SL``, ``RETURN`` conn,
    ``DISTRIBUTORS`` model OD) as a clean right-margin DATA STRIP (no leaders to rake the detail).

    Gated consumption: HIGH inches (S/R/I/O/SL/HDx/HD/DistExtension/feeder OD) are drawn;
    review-bucket ``DistModel``/``DistOD`` are drawn FLAGGED for review (label-only — the OD sizes
    the port circle, the model is an opaque string); blocked / ``None`` -> feature omitted +
    annotated, never invented. Distributor fidelity = simplified symbol (EZ-faithful)."""
    notes: list[str] = []
    fl, cd = geom.finned_length, geom.casing_depth

    if fl is not None and cd is not None:
        step = STEP_FRACTION * max(fl, cd)
    elif fl is not None:
        step = STEP_FRACTION * fl
    elif cd is not None:
        step = STEP_FRACTION * cd
    else:
        step = STEP_FRACTION

    supplies = [h for h in geom.headers if h.role == "supply"]
    returns = [h for h in geom.headers if h.role == "return"]
    circuits = max(len(supplies), len(returns), 1)

    ext_out = max((h.extension_in or 0.0 for h in supplies), default=0.0)  # distributor stem (up)

    # A return's stub reaches below the bottom edge by SL beyond its O offset (like V2).
    def _below(h: HeaderSpec) -> float:
        if h.stub_length is None:
            return 0.0
        return max(0.0, h.stub_length - (h.offset or 0.0))
    protrusion = max((_below(h) for h in returns), default=0.0)

    # Margins mirror V2: top carries S spacing (circuits) + CD + the fan/stem/AIRFLOW; bottom
    # carries R spacing (circuits) + SL past the stub protrusion. The right margin holds the O
    # offset + the distributor DATA STRIP (the tall FL gives it room to stack cleanly).
    top_margin = max(4.0, circuits + 3) * step + ext_out
    bottom_margin = max(top_margin, protrusion + (circuits + 3) * step)
    left_margin = 4 * step
    right_margin = 6 * step

    rects: list[LabeledRect] = []
    circles: list[Circle] = []
    segments: list[Segment] = []
    labels: list[Label] = []
    reqs: list[_DimReq] = []
    review_labels: list[str] = []
    airflow_anchor: tuple[float, float] | None = None

    casing: Rect | None
    if cd is not None and fl is not None:
        casing = Rect(left_margin, top_margin, cd, fl)
        extent_w = left_margin + cd + right_margin
        extent_h = top_margin + fl + bottom_margin
        rects.append(LabeledRect("casing", casing))
    else:
        casing = None
        if cd is None:
            notes.append(_omit("CD"))
        if fl is None:
            notes.append(_omit("FL"))
        extent_w = left_margin + (cd or 1.0) + right_margin
        extent_h = top_margin + (fl or 1.0) + bottom_margin

    if casing is not None:
        top, bottom = casing.y, casing.y + casing.h  # FL runs top->bottom
        datum_x = casing.x  # spacing measured rightward from the header-face datum (left), like V2
        data_x = casing.x + casing.w + 2.0 * step  # the right-margin data-strip column
        fw = 0.45 * step
        fan_apex = (casing.x + casing.w / 2.0, top - (circuits + 1) * step)  # one convergence point

        # --- supply distributors: top row, offset I down, spaced by S; funnel + fan + stem + tube ---
        supply_offsets: set[float] = set()
        kept_supply: list[tuple[float, float, float]] = []  # plain-header supply ports (overlap guard)
        for h in supplies:
            cx = _spread_x(casing, h)
            if cx is None:
                cx = casing.x + casing.w / 2.0
                notes.append(_omit(f"S{h.index}"))
            else:
                reqs.append(_DimReq(f"S{h.index}", "overall", "top", "h", datum_x, top, cx, top, h.spacing))
            ny = top + (h.offset if h.offset is not None else step)  # nozzle inset DOWN by I
            # I offset: per-row constant -> ONE bare "I" dim on the LEFT (value beside), like V2
            if h.offset is not None:
                key = round(h.offset, 3)
                if key not in supply_offsets:
                    supply_offsets.add(key)
                    reqs.append(_DimReq("I", "offset", "left", "v", casing.x, top, casing.x, ny, h.offset))
            else:
                notes.append(_omit(f"I{h.index}"))
            if supply_kind == "plain_header":
                # plain supply header port (HGRH/CWC/HWC): reuse the EXISTING connection circle
                # primitive at the supply I/S position — NO distributor funnel/fan/stem (the styled
                # supply_header_port glyph is Phase 5b). Sized by the supply header Ø (HDx).
                r = h.diameter / 2.0 if h.diameter is not None else None
                if r is None:
                    notes.append(_omit(f"HDx{h.index} supply port size"))
                elif any((cx - px) ** 2 + (ny - py) ** 2 < (r + pr - 0.05) ** 2 for px, py, pr in kept_supply):
                    notes.append(f"supply {h.index} port overlaps another — review required (omitted)")
                else:
                    kept_supply.append((cx, ny, r))
                    circles.append(Circle("connection_supply", cx, ny, r))
            else:
                # funnel glyph (simplified symbol): face bar + two tapers converging DOWN into the coil
                segments.append(Segment("nozzle_body", cx - fw, ny, cx + fw, ny))
                segments.append(Segment("nozzle_body", cx - fw, ny, cx, ny + fw))
                segments.append(Segment("nozzle_body", cx + fw, ny, cx, ny + fw))
                segments.append(Segment("feeder_fan", fan_apex[0], fan_apex[1], cx, ny))  # apex -> nozzle
                # DistExtension stem (HIGH) — short stem UP toward the header; blocked/None omit+annotate
                if f"DistExtension{h.index}" in geom.dist_blocked:
                    notes.append(f"DistExtension{h.index}: CONFLICT (blocked) — omitted")
                elif h.extension_in is not None:
                    segments.append(Segment("dist_extension", cx, ny, cx, ny - h.extension_in))
                else:
                    notes.append(_omit(f"DistExtension{h.index}"))
            segments.append(Segment("tube_run", cx, ny + fw, cx, bottom))  # supply tube runs the FL
            # deferred HDx Ø — right-margin DATA STRIP line (no leader, left-aligned into the margin)
            if h.diameter is not None:
                labels.append(Label(f"hdx_{h.index}", data_x, ny,
                                    f"{_fmt_in(h.diameter)} HDx{h.index}", anchor="start"))
            # deferred DISTRIBUTORS model / OD — review-bucket -> FLAGGED (label-only, data strip).
            # Distributor-only (DX); a plain-header supply has no distributor data line.
            if supply_kind != "plain_header":
                parts: list[str] = []
                if h.nozzle_spec:
                    parts.append(h.nozzle_spec)  # opaque string; NO geometry parsed from it
                if h.feeder_od_in is not None:
                    parts.append(f"OD:{_fmt_in(h.feeder_od_in)}")
                if parts:
                    feat = f"dist_data_{h.index}"
                    labels.append(Label(feat, data_x, ny + 0.5 * step, "DISTRIBUTORS " + " ".join(parts),
                                        anchor="start"))
                    review_labels.append(feat)

        # --- return connections: bottom row, offset O up, spaced by R, + port circle + SL stub ---
        return_offsets: set[float] = set()
        kept: list[tuple[float, float, float]] = []
        shared_conn: float | None = None
        for h in returns:
            cx = _spread_x(casing, h)
            if cx is None:
                cx = casing.x + casing.w / 2.0
                notes.append(_omit(f"R{h.index}"))
            else:
                reqs.append(_DimReq(f"R{h.index}", "overall", "bottom", "h", datum_x, bottom, cx, bottom, h.spacing))
            ry = bottom - (h.offset if h.offset is not None else step)  # port inset UP by O
            if h.offset is not None:
                key = round(h.offset, 3)
                if key not in return_offsets:
                    return_offsets.add(key)
                    right = casing.x + casing.w
                    reqs.append(_DimReq("O", "offset", "right", "v", right, ry, right, bottom, h.offset))
            else:
                notes.append(_omit(f"O{h.index}"))
            # port circle sized by the feeder OD (review) or the shared return sweat Ø
            r = (h.feeder_od_in / 2.0) if h.feeder_od_in is not None else (
                h.connection_diameter / 2.0 if h.connection_diameter is not None else None)
            if r is not None:
                if any((cx - px) ** 2 + (ry - py) ** 2 < (r + pr - 0.05) ** 2 for px, py, pr in kept):
                    notes.append(f"return {h.index} port overlaps another — review required (omitted)")
                else:
                    kept.append((cx, ry, r))
                    circles.append(Circle("connection_return", cx, ry, r))
            else:
                notes.append(_omit(f"return {h.index} connection size"))
            # stub pipe + end cap, extending outward (DOWN) past the bottom edge by SL
            if h.stub_length is not None:
                sy = ry + h.stub_length
                cap = 0.4 * step
                segments.append(Segment("stub", cx, ry, cx, sy))
                segments.append(Segment("stub_cap", cx - cap, sy, cx + cap, sy))
                labels.append(Label(f"sl_{h.index}", data_x, ry + 0.5 * step,
                                    f"{_fmt_in(h.stub_length)} SL{h.index}", anchor="start"))  # data strip
            else:
                notes.append(_omit(f"SL{h.index}"))
            # deferred HD Ø — data-strip line (no leader)
            if h.diameter is not None:
                labels.append(Label(f"hd_{h.index}", data_x, ry,
                                    f"{_fmt_in(h.diameter)} HD{h.index}", anchor="start"))
            if shared_conn is None and h.connection_diameter is not None:
                shared_conn = h.connection_diameter

        # RETURN connection size — a shared header-strip DATA line (no leader; data-strip item).
        if shared_conn is not None:
            labels.append(Label("return_conn", data_x, bottom, f"RETURN {_fmt_in(shared_conn)}",
                                anchor="start"))

        # AIRFLOW arrow (direction from the explicit enum; never derived from hand/category)
        if geom.airflow:
            airflow_anchor = (casing.x + casing.w / 2.0, fan_apex[1] - 1.6 * step)
        else:
            notes.append("AIRFLOW: direction missing -> omitted (review)")

        reqs.append(_DimReq("CD", "overall", "top", "h", casing.x, top, casing.x + casing.w, top, cd))
        reqs.append(_DimReq("FL", "overall", "left", "v", casing.x, top, casing.x, bottom, fl))

    edge_base = {"bottom": protrusion} if casing is not None else {}
    dims = place_dimensions(reqs, casing, step, edge_base) if casing is not None else []
    return ViewLayout(
        "plan", extent_w, extent_h, tuple(rects), tuple(circles), tuple(segments),
        tuple(labels), tuple(dims), tuple(dict.fromkeys(notes)),
        airflow=geom.airflow, airflow_anchor=airflow_anchor, review_labels=tuple(review_labels),
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
    _flip = {"start": "end", "end": "start", "middle": "middle"}
    labels = tuple(
        Label(
            lb.feature, w - lb.x, lb.y, lb.text,
            (w - lb.connector[0], lb.connector[1]) if lb.connector is not None else None,
            _flip[lb.anchor],
        )
        for lb in view.labels
    )
    dims = tuple(_mirror_dim(d, w) for d in view.dimensions)
    # AIRFLOW direction is mirror-INVARIANT (LH and RH are distinct coils, each with its own
    # upstream airflow_direction); only the arrow ANCHOR x reflects. Everything else mirrors.
    anchor = (w - view.airflow_anchor[0], view.airflow_anchor[1]) if view.airflow_anchor else None
    return ViewLayout(
        view.view, view.extent_w, view.extent_h, rects, circles, segments, labels, dims,
        view.omitted_notes, airflow=view.airflow, airflow_anchor=anchor,
        review_labels=view.review_labels,
    )


def build_views(geom: CoilGeometry, topology: Topology) -> dict[str, ViewLayout]:
    """Table-driven composition (Phase 5a): build the views the ``topology`` lists, selecting the
    supply kind from it. The mirror is applied here, once, for a right hand.

    The only structural geometry toggle is ``topology.supply``: ``distributor`` (DX — the existing
    nozzle/fan/extension path, byte-identical) vs ``plain_header`` (HGRH/CWC/HWC — a plain supply
    port reusing the existing connection circle primitive; no new glyph in 5a). The front view is
    category-agnostic; only side/plan consume the supply kind.
    """
    sk = topology.supply
    builders = {
        "front": lambda: layout_dx_front_view(geom),
        "side": lambda: layout_header_side_view(geom, supply_kind=sk),
        "plan": lambda: layout_plan_top_view(geom, supply_kind=sk),
    }
    views = {name: builders[name]() for name in topology.views if name in builders}
    if str(geom.coil_hand).strip().upper().startswith("R"):
        views = {name: mirror_view_x(v) for name, v in views.items()}
    return views


def build_dx_views(geom: CoilGeometry) -> dict[str, ViewLayout]:
    """Back-compat DX entry: resolve the DX topology and compose. Identical output to the
    pre-Phase-5 hardcoded path (distributor supply, front/side/plan)."""
    return build_views(geom, resolve_topology(geom.coil_category, geom.header_type, geom.special_feature))
