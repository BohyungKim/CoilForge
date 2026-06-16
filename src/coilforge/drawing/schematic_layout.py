"""Layer 2 — layout / datum engine (real inches only, no pixels).

Turns a :class:`CoilGeometry` into a :class:`FrontViewLayout`: rectangles and
dimension lines placed by datum/offset arithmetic in inches. There are no absolute
hardcoded coordinates and no presentation scale here — doubling any inch dimension
moves every dependent feature coherently because every position is derived from a
datum. Pixels appear only in the SVG backend (Layer 3).

Front-view datum model (origin at the casing top-left, y grows downward):

    casing  = (DIM_MARGIN, DIM_MARGIN, CL, CH)
    finned  = inset by the flange datums — HF from the left, TF from the top
              (RH/LH mirror is Phase 2; this fixes one hand).

When an offset slot is missing/REVIEW REQUIRED the finned face is centered on that
axis and the offset dimension is omitted + annotated — never invented.
"""

from __future__ import annotations

from dataclasses import dataclass

from coilforge.drawing.schematic_model import CoilGeometry

# Model-space margin (inches) around the casing, reserving room for witness lines.
DIM_MARGIN = 12.0
# How far (inches) a witness line sits outside the feature it dimensions.
DIM_OFFSET = 4.0


@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle in inches (x, y = top-left)."""

    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class DimLine:
    """A dimension/witness line in inches with a fixed-text label anchor."""

    x1: float
    y1: float
    x2: float
    y2: float
    label: str
    lx: float  # label anchor (inches)
    ly: float
    orient: str  # "h" | "v"


@dataclass(frozen=True)
class FrontViewLayout:
    """Resolved front-view geometry in inches, ready for any backend."""

    extent_w: float  # bounding width incl. dimension margins (inches)
    extent_h: float
    casing: Rect | None
    finned: Rect | None
    dim_lines: tuple[DimLine, ...]
    omitted_notes: tuple[str, ...]


def _omit(label: str) -> str:
    return f"{label}: REVIEW REQUIRED (omitted)"


def layout_dx_front_view(geom: CoilGeometry) -> FrontViewLayout:
    dim_lines: list[DimLine] = []
    notes: list[str] = []

    cl, ch = geom.casing_length, geom.casing_height
    fl, fh = geom.finned_length, geom.finned_height

    # --- casing datum ----------------------------------------------------- #
    casing: Rect | None
    if cl is not None and ch is not None:
        casing = Rect(DIM_MARGIN, DIM_MARGIN, cl, ch)
        extent_w = cl + 2 * DIM_MARGIN
        extent_h = ch + 2 * DIM_MARGIN
    else:
        casing = None
        if cl is None:
            notes.append(_omit("CL"))
        if ch is None:
            notes.append(_omit("CH"))
        # Fall back to the finned face (or a unit box) so the view still scales.
        extent_w = (fl or 1.0) + 2 * DIM_MARGIN
        extent_h = (fh or 1.0) + 2 * DIM_MARGIN

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

    # --- dimension lines (each emitted only when its value is real) ------- #
    if finned is not None:
        # FL across the finned top.
        wy = finned.y - DIM_OFFSET
        dim_lines.append(
            DimLine(finned.x, wy, finned.x + finned.w, wy, "FL", finned.x + finned.w / 2.0, wy, "h")
        )
        # FH up the finned right edge.
        wx = finned.x + finned.w + DIM_OFFSET
        dim_lines.append(
            DimLine(wx, finned.y, wx, finned.y + finned.h, "FH", wx, finned.y + finned.h / 2.0, "v")
        )

    if casing is not None:
        # CL across the casing bottom.
        wy = casing.y + casing.h + DIM_OFFSET
        dim_lines.append(
            DimLine(casing.x, wy, casing.x + casing.w, wy, "CL", casing.x + casing.w / 2.0, wy, "h")
        )
        # CH up the casing left edge.
        wx = casing.x - DIM_OFFSET
        dim_lines.append(
            DimLine(wx, casing.y, wx, casing.y + casing.h, "CH", wx, casing.y + casing.h / 2.0, "v")
        )

    # --- offset dimensions / omissions ------------------------------------ #
    if casing is not None and finned is not None:
        mid_x = finned.x + finned.w / 2.0
        # TF: casing top -> finned top.
        if geom.top_flange is not None:
            dim_lines.append(DimLine(mid_x, casing.y, mid_x, finned.y, "TF", mid_x, (casing.y + finned.y) / 2.0, "v"))
        else:
            notes.append(_omit("TF"))
        # BF: finned bottom -> casing bottom.
        if geom.bottom_flange is not None:
            cb, fb = casing.y + casing.h, finned.y + finned.h
            dim_lines.append(DimLine(mid_x, fb, mid_x, cb, "BF", mid_x, (fb + cb) / 2.0, "v"))
        else:
            notes.append(_omit("BF"))
        mid_y = finned.y + finned.h / 2.0
        # HF: casing left -> finned left.
        if geom.header_flange is not None:
            dim_lines.append(DimLine(casing.x, mid_y, finned.x, mid_y, "HF", (casing.x + finned.x) / 2.0, mid_y, "h"))
        else:
            notes.append(_omit("HF"))
        # RF: finned right -> casing right.
        if geom.return_flange is not None:
            cr, fr = casing.x + casing.w, finned.x + finned.w
            dim_lines.append(DimLine(fr, mid_y, cr, mid_y, "RF", (fr + cr) / 2.0, mid_y, "h"))
        else:
            notes.append(_omit("RF"))

    return FrontViewLayout(
        extent_w=extent_w,
        extent_h=extent_h,
        casing=casing,
        finned=finned,
        dim_lines=tuple(dim_lines),
        omitted_notes=tuple(dict.fromkeys(notes)),  # stable, de-duplicated
    )
