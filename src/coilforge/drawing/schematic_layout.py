"""Layer 2 — layout / datum engine (real inches only, no pixels).

Turns a :class:`CoilGeometry` into a :class:`FrontViewLayout`: rectangles and
dimensions placed by datum/offset arithmetic in inches. There are no absolute hardcoded
coordinates and no presentation scale here — doubling any inch dimension moves every
dependent feature coherently because every position is derived from a datum. Pixels
appear only in the SVG backend (Layer 3).

Front-view datum model (origin at the casing top-left, y grows downward):

    casing  = (DIM_MARGIN, DIM_MARGIN, CL, CH)
    finned  = inset by the flange datums — HF from the left, TF from the top
              (RH/LH mirror is Phase 2; this fixes one hand).

Dimensioning is **tiered** to stay collision-free (Phase 1.5): each dimension is tagged
``overall`` or ``offset`` and assigned a tier on its edge. Offsets sit on the inner tier
(0), overall dims on the outer tier (1), so on any shared edge their perpendicular bands
are disjoint. ``tier_pos`` is reusable across future views — it is pure tier math derived
from the part, never pixels. The backend decides HOW each dimension is drawn (extension
lines, arrowheads vs leader by rendered length).

When an offset slot is missing/REVIEW REQUIRED the finned face is centered on that axis
and the offset dimension is omitted + annotated — never invented.
"""

from __future__ import annotations

from dataclasses import dataclass

from coilforge.drawing.schematic_model import CoilGeometry

# Tier step as a fraction of the part's larger side, so dimension tiers scale with the
# drawing under fit-to-canvas (a fixed inch step would crowd large coils / float small).
STEP_FRACTION = 0.06
# Margin around the casing, in tier steps — room for the outer (overall) tier + labels.
TIER_MARGIN_STEPS = 3


@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle in inches (x, y = top-left)."""

    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Dimension:
    """A single dimension in inches. WHERE it goes (the backend decides HOW to draw it).

    ``ax/ay`` .. ``bx/by`` are the two feature points the dimension spans. ``tier_pos`` is
    the perpendicular coordinate of the tier the dimension/label sit on (a ``y`` for
    top/bottom edges, an ``x`` for left/right). No pixels.
    """

    label: str
    kind: str  # "overall" | "offset"
    edge: str  # "top" | "bottom" | "left" | "right"
    tier: int  # 0 = inner (offsets), 1+ = outer (overalls)
    orient: str  # "h" | "v" — direction the measured span runs
    ax: float
    ay: float
    bx: float
    by: float
    tier_pos: float


@dataclass(frozen=True)
class FrontViewLayout:
    """Resolved front-view geometry in inches, ready for any backend."""

    extent_w: float  # bounding width incl. dimension margins (inches)
    extent_h: float
    casing: Rect | None
    finned: Rect | None
    dimensions: tuple[Dimension, ...]
    omitted_notes: tuple[str, ...]


def _omit(label: str) -> str:
    return f"{label}: REVIEW REQUIRED (omitted)"


def _step(part: Rect) -> float:
    return STEP_FRACTION * max(part.w, part.h)


def tier_pos(casing: Rect, edge: str, tier: int, step: float) -> float:
    """Perpendicular coordinate of a dimension tier, outward from a casing edge (inches).

    Reusable across views: tier 0 sits one step out, each further tier another step.
    """
    out = step * (tier + 1)
    if edge == "top":
        return casing.y - out
    if edge == "bottom":
        return casing.y + casing.h + out
    if edge == "left":
        return casing.x - out
    if edge == "right":
        return casing.x + casing.w + out
    raise ValueError(f"unknown edge: {edge}")


def _dx_front_dimensions(
    casing: Rect | None, finned: Rect | None, geom: CoilGeometry, step: float
) -> tuple[list[Dimension], list[str]]:
    dims: list[Dimension] = []
    notes: list[str] = []

    def overall(label: str, edge: str, ax: float, ay: float, bx: float, by: float, orient: str) -> None:
        dims.append(Dimension(label, "overall", edge, 1, orient, ax, ay, bx, by, tier_pos(casing, edge, 1, step)))

    def offset(label: str, edge: str, ax: float, ay: float, bx: float, by: float, orient: str) -> None:
        dims.append(Dimension(label, "offset", edge, 0, orient, ax, ay, bx, by, tier_pos(casing, edge, 0, step)))

    # --- overall dimensions (outer tier) ---------------------------------- #
    if finned is not None and casing is not None:
        overall("FL", "top", finned.x, finned.y, finned.x + finned.w, finned.y, "h")
        overall("FH", "right", finned.x + finned.w, finned.y, finned.x + finned.w, finned.y + finned.h, "v")
    if casing is not None:
        overall("CL", "bottom", casing.x, casing.y + casing.h, casing.x + casing.w, casing.y + casing.h, "h")
        overall("CH", "left", casing.x, casing.y, casing.x, casing.y + casing.h, "v")

    # --- flange offsets (inner tier; emitted only when present) ----------- #
    if casing is not None and finned is not None:
        mid_x = finned.x + finned.w / 2.0
        mid_y = finned.y + finned.h / 2.0
        cb, fb = casing.y + casing.h, finned.y + finned.h
        cr, fr = casing.x + casing.w, finned.x + finned.w
        if geom.top_flange is not None:
            offset("TF", "top", mid_x, casing.y, mid_x, finned.y, "v")
        else:
            notes.append(_omit("TF"))
        if geom.bottom_flange is not None:
            offset("BF", "bottom", mid_x, fb, mid_x, cb, "v")
        else:
            notes.append(_omit("BF"))
        if geom.header_flange is not None:
            offset("HF", "left", casing.x, mid_y, finned.x, mid_y, "h")
        else:
            notes.append(_omit("HF"))
        if geom.return_flange is not None:
            offset("RF", "right", fr, mid_y, cr, mid_y, "h")
        else:
            notes.append(_omit("RF"))

    return dims, notes


def layout_dx_front_view(geom: CoilGeometry) -> FrontViewLayout:
    notes: list[str] = []

    cl, ch = geom.casing_length, geom.casing_height
    fl, fh = geom.finned_length, geom.finned_height

    # --- tier step from the part size (casing, else finned, else unit) ----- #
    if cl is not None and ch is not None:
        step = STEP_FRACTION * max(cl, ch)
    elif fl is not None and fh is not None:
        step = STEP_FRACTION * max(fl, fh)
    else:
        step = STEP_FRACTION
    margin = TIER_MARGIN_STEPS * step

    # --- casing datum ----------------------------------------------------- #
    casing: Rect | None
    if cl is not None and ch is not None:
        casing = Rect(margin, margin, cl, ch)
        extent_w = cl + 2 * margin
        extent_h = ch + 2 * margin
    else:
        casing = None
        if cl is None:
            notes.append(_omit("CL"))
        if ch is None:
            notes.append(_omit("CH"))
        extent_w = (fl or 1.0) + 2 * margin
        extent_h = (fh or 1.0) + 2 * margin

    # --- finned face datum (inset into the casing) ------------------------ #
    finned: Rect | None = None
    if fl is not None and fh is not None and casing is not None:
        # horizontal: HF from the left, else RF from the right, else centered.
        if geom.header_flange is not None:
            fx = casing.x + geom.header_flange
        elif geom.return_flange is not None:
            fx = casing.x + casing.w - geom.return_flange - fl
        else:
            fx = casing.x + (casing.w - fl) / 2.0
        # vertical: TF from the top, else BF from the bottom, else centered.
        if geom.top_flange is not None:
            fy = casing.y + geom.top_flange
        elif geom.bottom_flange is not None:
            fy = casing.y + casing.h - geom.bottom_flange - fh
        else:
            fy = casing.y + (casing.h - fh) / 2.0
        finned = Rect(fx, fy, fl, fh)
    else:
        if fl is None:
            notes.append(_omit("FL"))
        if fh is None:
            notes.append(_omit("FH"))
        notes.append("finned face: REVIEW REQUIRED (omitted)")

    dims, dim_notes = _dx_front_dimensions(casing, finned, geom, step)
    notes.extend(dim_notes)

    return FrontViewLayout(
        extent_w=extent_w,
        extent_h=extent_h,
        casing=casing,
        finned=finned,
        dimensions=tuple(dims),
        omitted_notes=tuple(dict.fromkeys(notes)),  # stable, de-duplicated
    )
