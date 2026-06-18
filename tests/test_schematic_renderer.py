"""Phase 1 / 1.5 / 2 — parametric drawing engine (DX front + header/side, SVG).

Three-layer contract: L1 CoilGeometry (inches) -> L2 ViewLayout (inches) -> L3 SVG (px).

Load-bearing properties:
  * uniform, SCALE-INDEPENDENT px_per_inch — box pixel aspect == inch aspect (front & side);
  * per-drawing fit-to-canvas;
  * tiered, collision-free dimensioning + leader-for-small (shared by both views);
  * LH<->RH is ONE x-mirror applied to both views; the front HF/RF side flips with hand;
  * missing / "REVIEW REQUIRED" slots omitted + annotated, never invented;
  * safety flags (export_allowed False, watermark, not-to-scale) on both views;
  * model and layout carry no pixels.
"""

from __future__ import annotations

import dataclasses
import itertools
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.drawing.backends.svg import (
    FONT_PX,
    PAD_PX,
    TARGET_FILL,
    SvgBackendResult,
    boxes_overlap,
    render_view_svg,
    text_bbox,
)
from coilforge.drawing.schematic_layout import (
    Circle,
    Dimension,
    LabeledRect,
    Rect,
    Segment,
    ViewLayout,
    build_dx_views,
    build_views,
    layout_dx_front_view,
    layout_header_side_view,
    mirror_view_x,
)
from coilforge.drawing.schematic_model import CoilGeometry, HeaderSpec
from coilforge.drawing.schematic_renderer import SchematicResult, render_scale_schematic
from coilforge.drawing.svg_regression import normalize_svg_for_regression
from coilforge.drawing.topology import UnknownTopologyError, resolve_topology


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def slots(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        # front
        "slot.FL": 18.0, "slot.FH": 18.0, "slot.CL": 24.0, "slot.CH": 24.0,
        "slot.TF": 3.0, "slot.BF": 3.0, "slot.HF": 3.0, "slot.RF": 3.0,
        # side / header (single-circuit DX): supply id1 + return id2, with spacing S/R
        "slot.CD": 12.0, "slot.ROWS": 4, "slot.HDx1": 4.5, "slot.HD2": 3.5,
        "slot.I1": 6.0, "slot.O2": 4.0, "slot.S1": 3.0, "slot.R2": 2.0,
        "slot.SL2": 3.0, "slot.RETURN_CONN_SIZE": 0.625,
    }
    base.update(over)
    return base


def sanitized_slots() -> dict[str, object]:
    # A real, small single-circuit DX coil (sanitized EZC-0001 values: I/O offset, S/R spacing).
    return {
        "slot.FH": 12.0, "slot.FL": 15.0, "slot.CH": 13.25, "slot.CL": 18.0,
        "slot.TF": 0.63, "slot.BF": 0.63, "slot.HF": 1.5, "slot.RF": 1.5,
        "slot.CD": 5.5, "slot.ROWS": 4, "slot.HDx1": 4.5, "slot.HD2": 3.5,
        "slot.I1": 3.0, "slot.O2": 2.0, "slot.S1": 2.75, "slot.R2": 0.63,
        "slot.SL2": 8.0, "slot.RETURN_CONN_SIZE": 0.625,
    }


def multi_circuit_slots() -> dict[str, object]:
    # A SANITIZED 3-circuit DX, modelled on EZC-0007's STRUCTURE (constant I/O, increasing
    # S/R per circuit) — values altered so no raw customer numbers are committed.
    return {
        "slot.FH": 22.0, "slot.FL": 26.0, "slot.CH": 24.0, "slot.CL": 28.0,
        "slot.TF": 1.0, "slot.BF": 1.0, "slot.HF": 1.5, "slot.RF": 1.5,
        "slot.CD": 8.0, "slot.ROWS": 5,
        # circuit 1: supply id1 / return id2
        "slot.HDx1": 4.5, "slot.I1": 3.0, "slot.S1": 1.5,
        "slot.HD2": 3.5, "slot.O2": 2.0, "slot.R2": 1.0, "slot.SL2": 6.0,
        # circuit 2: supply id3 / return id4
        "slot.HDx3": 4.5, "slot.I3": 3.0, "slot.S3": 4.0,
        "slot.HD4": 3.5, "slot.O4": 2.0, "slot.R4": 3.5, "slot.SL4": 6.0,
        # circuit 3: supply id5 / return id6
        "slot.HDx5": 4.5, "slot.I5": 3.0, "slot.S5": 6.5,
        "slot.HD6": 3.5, "slot.O6": 2.0, "slot.R6": 6.0, "slot.SL6": 6.0,
        "slot.RETURN_CONN_SIZE": 1.0,
    }


def geometry(sv: dict[str, object], *, category: str = "DX", hand: str = "LH") -> CoilGeometry:
    return CoilGeometry.from_slot_values(
        sv, coil_category=category, coil_hand=hand, header_type="Header 1", special_feature=None
    )


def backend(sv: dict[str, object], *, canvas: tuple[int, int] = (1000, 780)) -> SvgBackendResult:
    return render_view_svg(layout_dx_front_view(geometry(sv)), canvas_w=canvas[0], canvas_h=canvas[1])


def side_backend(sv: dict[str, object], *, canvas: tuple[int, int] = (1000, 780)) -> SvgBackendResult:
    return render_view_svg(layout_header_side_view(geometry(sv)), canvas_w=canvas[0], canvas_h=canvas[1])


def render(sv: dict[str, object], **kw: object) -> SchematicResult:
    params: dict[str, object] = dict(coil_category="DX", coil_hand="LH", header_type="Header 1")
    params.update(kw)
    return render_scale_schematic(sv, **params)  # type: ignore[arg-type]


def dim_by_label(view: ViewLayout, label: str) -> Dimension:
    return next(d for d in view.dimensions if d.label == label)


def assert_views_close(a: ViewLayout, b: ViewLayout) -> None:
    """Numeric view equality up to float tolerance (mirror is not bit-exact involutive)."""
    assert a.view == b.view
    assert (a.extent_w, a.extent_h) == pytest.approx((b.extent_w, b.extent_h))
    assert len(a.dimensions) == len(b.dimensions)
    for da, db in zip(a.dimensions, b.dimensions):
        assert (da.label, da.kind, da.edge, da.tier, da.orient) == (db.label, db.kind, db.edge, db.tier, db.orient)
        assert (da.ax, da.ay, da.bx, da.by, da.tier_pos) == pytest.approx((db.ax, db.ay, db.bx, db.by, db.tier_pos))
    assert len(a.circles) == len(b.circles)
    for ca, cb in zip(a.circles, b.circles):
        assert ca.feature == cb.feature
        assert (ca.cx, ca.cy, ca.r) == pytest.approx((cb.cx, cb.cy, cb.r))
    assert len(a.rects) == len(b.rects)
    for ra, rb in zip(a.rects, b.rects):
        assert ra.feature == rb.feature
        assert (ra.rect.x, ra.rect.y, ra.rect.w, ra.rect.h) == pytest.approx((rb.rect.x, rb.rect.y, rb.rect.w, rb.rect.h))


# --------------------------------------------------------------------------- #
# proportionality / uniform scale — SCALE-INDEPENDENT (front)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("canvas", [(1000, 780), (1400, 900), (640, 480)])
def test_casing_aspect_matches_inches_at_any_scale(canvas: tuple[int, int]) -> None:
    r = backend(slots(**{"slot.CL": 50.0, "slot.CH": 10.0}), canvas=canvas)
    _, _, w, h = r.casing_px
    assert w / h == pytest.approx(50.0 / 10.0)


def test_finned_aspect_matches_inches() -> None:
    r = backend(slots(**{"slot.FL": 40.0, "slot.FH": 10.0}))
    assert r.finned_px is not None
    _, _, w, h = r.finned_px
    assert w / h == pytest.approx(40.0 / 10.0)


def test_skinny_and_wide_have_visibly_different_aspect() -> None:
    tall = backend(slots(**{"slot.CL": 24.0, "slot.CH": 66.0}))
    wide = backend(slots(**{"slot.CL": 126.0, "slot.CH": 24.0}))
    assert (tall.casing_px[2] / tall.casing_px[3]) < 1.0 < (wide.casing_px[2] / wide.casing_px[3])


def test_fit_to_canvas_fills_target_and_scale_differs() -> None:
    canvas = (1000, 780)
    avail_w, avail_h = canvas[0] - 2 * PAD_PX, canvas[1] - 2 * PAD_PX

    def fill_fraction(sv: dict[str, object]) -> tuple[float, float]:
        layout = layout_dx_front_view(geometry(sv))
        r = render_view_svg(layout, canvas_w=canvas[0], canvas_h=canvas[1])
        drawn_w, drawn_h = layout.extent_w * r.px_per_inch, layout.extent_h * r.px_per_inch
        return max(drawn_w / avail_w, drawn_h / avail_h), r.px_per_inch

    small_fill, small_ppi = fill_fraction(sanitized_slots())
    large_fill, large_ppi = fill_fraction(slots(**{"slot.CL": 240.0, "slot.CH": 120.0}))
    assert small_fill == pytest.approx(TARGET_FILL, abs=1e-3)
    assert large_fill == pytest.approx(TARGET_FILL, abs=1e-3)
    assert small_ppi > large_ppi


# --------------------------------------------------------------------------- #
# side-view proportionality (scale-independent)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("canvas", [(1000, 780), (1400, 900)])
def test_side_casing_aspect_matches_cd_ch(canvas: tuple[int, int]) -> None:
    r = side_backend(slots(**{"slot.CD": 40.0, "slot.CH": 10.0}), canvas=canvas)
    _, _, w, h = r.casing_px
    assert w / h == pytest.approx(40.0 / 10.0)


# --------------------------------------------------------------------------- #
# tiered dimensioning — no overall/offset band collisions (both views)
# --------------------------------------------------------------------------- #
def _assert_no_tier_collision(view: ViewLayout) -> None:
    by_edge: dict[str, dict[str, set[int]]] = {}
    for dim in view.dimensions:
        kinds = by_edge.setdefault(dim.edge, {"overall": set(), "offset": set()})
        kinds[dim.kind].add(dim.tier)
    assert by_edge
    for edge, kinds in by_edge.items():
        assert kinds["overall"].isdisjoint(kinds["offset"]), f"tier collision on {edge}"


def test_front_no_label_band_collision() -> None:
    _assert_no_tier_collision(layout_dx_front_view(geometry(slots())))


def test_side_dimensioning_reuses_helper_no_collision_and_leader() -> None:
    layout = layout_header_side_view(geometry(slots()))
    _assert_no_tier_collision(layout)  # CH overall vs I/O offsets disjoint; CD vs SL2 disjoint
    res = render(slots())
    # header offsets are offsets -> leader style (never crammed arrowheads).
    assert 'data-dim="O" data-style="leader"' in res.side_svg
    assert 'data-dim="CD" data-style="arrows"' in res.side_svg


def _side_casing(layout: ViewLayout) -> Rect:
    return next(lr.rect for lr in layout.rects if lr.feature == "casing")


def _connections(layout: ViewLayout) -> list[Circle]:
    return [c for c in layout.circles if c.feature.startswith("connection")]


def test_side_offset_dims_on_side_edges() -> None:
    # Phase 3c (EZC-0007): the offsets are vertical dims on the SIDE edges — supply I on the
    # LEFT, return O on the RIGHT, value beside — out of the nozzle/return columns (where the
    # diameter leaders run). The witness spans the offset depth at the box edge.
    layout = layout_header_side_view(geometry(slots()))
    casing = _side_casing(layout)
    i, o = dim_by_label(layout, "I"), dim_by_label(layout, "O")  # bare codes (one per row)
    assert i.edge == "left" and o.edge == "right"
    assert i.ax == pytest.approx(casing.x)  # I witness at the left edge
    assert o.ax == pytest.approx(casing.x + casing.w)  # O witness at the right edge
    assert abs(i.by - i.ay) == pytest.approx(i.value)  # spans the I offset depth
    assert abs(o.ay - o.by) == pytest.approx(o.value)  # spans the O offset depth


def test_connections_sit_below_bottom_edge_within_depth() -> None:
    # V2: return connections hang at the end of their SL stub, below the bottom edge, at a
    # spread-x within the casing depth (not buried in the casing).
    layout = layout_header_side_view(geometry(sanitized_slots()))
    casing = _side_casing(layout)
    conns = _connections(layout)
    assert conns
    for c in conns:
        assert casing.x - 1e-9 <= c.cx <= casing.x + casing.w + 1e-9  # within the depth span
        assert c.cy >= casing.y + casing.h - 1e-9  # at / below the bottom edge (stub end)


def test_header_diameters_deferred_no_manifold_circle() -> None:
    # Phase 3c (EZC-0007 faithful): header diameters HDx/HD are NOT drawn in the narrow
    # spread/end view — they belong in the wider header strip (Phase 4). The only circles
    # here are sweat connections, never full-diameter manifold circles, and no Ø callouts.
    res = render(sanitized_slots())
    assert 'data-label="hd_supply_1"' not in res.side_svg and "HDx1" not in res.side_svg
    assert 'data-label="hd_return_2"' not in res.side_svg
    assert "header_supply" not in res.side_svg and "header_return" not in res.side_svg


def test_distinct_connections_do_not_overlap() -> None:
    conns = _connections(layout_header_side_view(geometry(sanitized_slots())))
    for a, b in itertools.combinations(conns, 2):
        dist = ((a.cx - b.cx) ** 2 + (a.cy - b.cy) ** 2) ** 0.5
        assert dist >= a.r + b.r - 0.05  # physically plausible: no overlap


def test_side_labels_match_ez_convention() -> None:
    # EZ spread view: geometry callouts are "{value} {CODE}" (value-first, no Ø/unit); each
    # circuit carries an offset (I/O) + spacing (S/R) dim. Header diameters (HDx/HD) and the
    # RETURN connection size are data-strip items, deferred to Phase 4 — not in this view.
    svg = render(sanitized_slots()).side_svg
    assert "2.00 O" in svg and 'data-dim="O"' in svg  # return offset (bare code, one per row)
    assert "0.63 R2" in svg and 'data-dim="R2"' in svg  # return spacing (one per circuit)
    assert "2.75 S1" in svg and 'data-dim="S1"' in svg  # supply spacing (one per circuit)
    assert "HDx" not in svg and "RETURN" not in svg  # diameters + conn-size deferred


def test_supply_distributor_is_labels_only_no_circle() -> None:
    # The distributor has no sweat connection (EZ ConnectionSize=0): nozzle glyph + labels,
    # but no connection circle of its own.
    res = render(sanitized_slots())
    assert 'data-feature="connection_supply"' not in res.side_svg
    assert 'data-feature="connection_return"' in res.side_svg
    assert 'data-dim="I"' in res.side_svg  # the bare I offset (one per row)
    assert 'data-feature="distributor_supply"' in res.side_svg  # nozzle glyph drawn
    # exactly one connection circle (the single return) — the supply contributes none.
    assert res.side_svg.count('data-feature="connection_') == 1


def test_small_offset_renders_as_leader_not_arrowheads() -> None:
    res = render(sanitized_slots())
    assert 'data-dim="TF" data-style="leader"' in res.svg
    assert 'data-dim="CL" data-style="arrows"' in res.svg


# --------------------------------------------------------------------------- #
# Phase 3 — N indexed connections on the DX topology (EZ spread view)
# --------------------------------------------------------------------------- #
def multi_render(sv: dict[str, object] | None = None, **kw: object) -> SchematicResult:
    return render(sv if sv is not None else multi_circuit_slots(), header_type="Header 3", **kw)


def test_multi_circuit_all_indexed_labels_present() -> None:
    # Spacing S/R appear once per circuit (they position each circuit along the depth).
    # Offsets collapse to one bare I / O per row. Diameters HDx/HD are deferred (Phase 4).
    svg = multi_render().side_svg
    for code in ("S1", "S3", "S5", "R2", "R4", "R6"):
        assert code in svg, f"missing indexed label {code}"
    assert "HDx" not in svg and "RETURN" not in svg  # diameters + conn-size deferred
    assert 'data-dim="I"' in svg and 'data-dim="O"' in svg  # offsets collapsed to one bare I/O per row


def test_multi_circuit_offset_deduped_to_one_per_row() -> None:
    # Phase 3b: constant per-circuit offset collapses to ONE bare "I" / "O" dim per row
    # (was once-per-circuit, illegibly stacked). Spacing S/R stay per-circuit.
    svg = multi_render().side_svg
    assert svg.count('data-dim="I"') == 1  # constant supply offset -> a single I dim
    assert svg.count('data-dim="O"') == 1  # constant return offset -> a single O dim
    for code in ('data-dim="I3"', 'data-dim="I5"', 'data-dim="O4"', 'data-dim="O6"'):
        assert code not in svg  # no per-circuit offset dims


def test_offset_dedupe_is_value_aware_not_hardcoded_once() -> None:
    # When supply offsets genuinely DIFFER, each distinct value gets its own bare "I" dim
    # at its own height (the dedupe is value-keyed, not hardcoded "once").
    sv = multi_circuit_slots()
    sv["slot.I1"], sv["slot.I3"], sv["slot.I5"] = 2.0, 10.0, 18.0
    layout = layout_header_side_view(geometry(sv))
    i_dims = [d for d in layout.dimensions if d.label == "I"]
    assert len(i_dims) == 3  # three distinct values -> three I dims
    assert len({round(d.tier_pos, 3) for d in i_dims}) == 3  # at distinct heights


def test_multi_circuit_return_connsize_deferred() -> None:
    # RETURN_CONN_SIZE is a data-strip item (Phase 4) -> no "RETURN {value}" callout in the
    # spread view, though the return sweat circles themselves are still drawn (one per circuit).
    svg = multi_render().side_svg
    assert svg.count('data-label="conn_return"') == 0
    assert "RETURN " not in svg
    assert svg.count('data-feature="connection_return"') == 3


def test_multi_circuit_diameters_deferred_from_spread_view() -> None:
    # Header diameters (HDx / HD) are NOT drawn in the narrow spread/end view — they belong
    # in the wider header strip (Phase 4). The spread view shows no Ø callouts at all.
    res = multi_render()
    dia = [(t, b) for t, b in _svg_label_boxes(res.side_svg) if "HD" in t]
    assert len(dia) == 0


def test_multi_circuit_spacing_stays_one_per_circuit() -> None:
    svg = multi_render().side_svg
    for code in ("S1", "S3", "S5", "R2", "R4", "R6"):
        assert svg.count(f'data-dim="{code}"') == 1  # spacing positions each circuit


def test_multi_circuit_n_return_circles_distinct_and_supply_has_none() -> None:
    layout = layout_header_side_view(geometry(multi_circuit_slots()))
    conns = _connections(layout)
    assert len(conns) == 3  # one sweat connection per return circuit
    assert len({round(c.cx, 3) for c in conns}) == 3  # distinct spread-x (constant I/O does NOT collapse them)
    svg = multi_render().side_svg
    assert 'data-feature="connection_supply"' not in svg  # supply distributors have no circle
    assert svg.count('data-feature="connection_') == 3


def test_multi_circuit_spread_follows_spacing_not_offset() -> None:
    # The whole point of the re-plan: circuits are positioned by R{even} spacing even though
    # the O offset is constant — so the return circles' x-order follows R2 < R4 < R6.
    layout = layout_header_side_view(geometry(multi_circuit_slots()))
    by_x = sorted(_connections(layout), key=lambda c: c.cx)
    assert [round(c.cx - by_x[0].cx, 3) for c in by_x] == sorted(round(c.cx - by_x[0].cx, 3) for c in by_x)
    # and they are NOT all at the same x (which a constant-offset stack would produce)
    assert by_x[0].cx < by_x[-1].cx


def test_multi_circuit_dropped_slot_omits_only_that_header() -> None:
    sv = multi_circuit_slots()
    del sv["slot.S3"]  # circuit-2 supply spacing missing
    res = multi_render(sv)
    assert 'data-dim="S3"' not in res.side_svg  # that circuit's spacing dim omitted
    assert any("S3" in note for note in res.omitted_features)  # and annotated
    assert 'data-dim="S1"' in res.side_svg  # other circuits intact
    assert 'data-dim="S5"' in res.side_svg


@pytest.mark.parametrize("hand", ["LH", "RH"])
def test_multi_circuit_no_label_overlaps(hand: str) -> None:
    svg = multi_render(coil_hand=hand).side_svg
    boxes = _svg_label_boxes(svg)
    # S1/S3/S5 + R2/R4/R6 spacing + bare I/O + CD/CH = 10 dim values in the spread view
    # (diameters + RETURN deferred to Phase 4).
    assert len(boxes) >= 10
    for (ta, a), (tb, b) in itertools.combinations(boxes, 2):
        assert not boxes_overlap(a, b), f"{hand}: {ta!r} overlaps {tb!r}"


@pytest.mark.parametrize("hand", ["LH", "RH"])
def test_multi_circuit_every_leader_reached(hand: str) -> None:
    svg = multi_render(coil_hand=hand).side_svg
    ends, labels = _leader_endpoints(svg), _bearing_labels(svg)
    assert labels and ends
    for text, box in labels:
        assert _reach_px(box, ends) <= REACH_TOL, f"{hand}: {text!r} connector detached"


def test_multi_circuit_mirror_equivariant() -> None:
    def key(svg: str) -> list[tuple[str, float]]:
        return sorted((t, round((b[1] + b[3]) / 2.0, 1)) for t, b in _svg_label_boxes(svg))

    assert key(multi_render(coil_hand="LH").side_svg) == key(multi_render(coil_hand="RH").side_svg)


# --------------------------------------------------------------------------- #
# Phase 3c — obstacle-complete legibility: no LINE through a label, no GLYPH on a label
# (general properties — these FAIL on the 3b output that only checked label<->label)
# --------------------------------------------------------------------------- #
def _seg_hits_box(x1, y1, x2, y2, box) -> bool:
    """Liang-Barsky: does the segment cross the (already-shrunk) box interior?"""
    bx0, by0, bx1, by1 = box
    if bx0 >= bx1 or by0 >= by1:
        return False
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - bx0), (dx, bx1 - x1), (-dy, y1 - by0), (dy, by1 - y1)):
        if abs(p) < 1e-9:
            if q < 0:
                return False
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return False
                t0 = max(t0, r)
            else:
                if r < t0:
                    return False
                t1 = min(t1, r)
    return t0 <= t1


def _annotation_segments(svg: str) -> list[tuple[float, float, float, float]]:
    """Every dimension / witness / leader line segment (incl. dogleg-path leaders)."""
    segs = []
    for m in re.finditer(
        r'<line x1="(-?[\d.]+)" y1="(-?[\d.]+)" x2="(-?[\d.]+)" y2="(-?[\d.]+)" '
        r'class="(?:ext-line|dim-arrows|witness|leader)"',
        svg,
    ):
        segs.append(tuple(float(m.group(i)) for i in range(1, 5)))
    for m in re.finditer(
        r'<path d="M (-?[\d.]+) (-?[\d.]+) L (-?[\d.]+) (-?[\d.]+) L (-?[\d.]+) (-?[\d.]+)" class="leader"',
        svg,
    ):
        v = [float(m.group(i)) for i in range(1, 7)]
        segs.append((v[0], v[1], v[2], v[3]))
        segs.append((v[2], v[3], v[4], v[5]))
    return segs


def _glyph_boxes(svg: str) -> list[tuple[float, float, float, float]]:
    """Connection glyph bboxes: return circles + nozzle/stub segments."""
    boxes = []
    for m in re.finditer(
        r'<circle data-feature="connection_return" cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"', svg
    ):
        cx, cy, r = (float(m.group(i)) for i in (1, 2, 3))
        boxes.append((cx - r, cy - r, cx + r, cy + r))
    for m in re.finditer(
        r'<line data-feature="(?:distributor_supply|stub|nozzle_body|feeder_fan|dist_extension|stub_cap)" '
        r'x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"',
        svg,
    ):
        xs, ys = (float(m.group(1)), float(m.group(3))), (float(m.group(2)), float(m.group(4)))
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    return boxes


@pytest.mark.parametrize("sv", [sanitized_slots(), multi_circuit_slots()], ids=["single", "multi"])
@pytest.mark.parametrize("hand", ["LH", "RH"])
def test_no_annotation_line_passes_through_a_label(sv: dict, hand: str) -> None:
    # A label box, shrunk 2.5px so a leader that lands ON its edge midpoint (2.7b) doesn't
    # count — only a line crossing the value's interior (strikethrough / weave) fails.
    svg = render(sv, header_type="Header 3", coil_hand=hand).side_svg
    boxes = _svg_label_boxes(svg)
    segs = _annotation_segments(svg)
    assert boxes and segs
    for x1, y1, x2, y2 in segs:
        for t, b in boxes:
            shrunk = (b[0] + 2.5, b[1] + 2.5, b[2] - 2.5, b[3] - 2.5)
            assert not _seg_hits_box(x1, y1, x2, y2, shrunk), f"{hand}: line crosses {t!r}"


@pytest.mark.parametrize("sv", [sanitized_slots(), multi_circuit_slots()], ids=["single", "multi"])
@pytest.mark.parametrize("hand", ["LH", "RH"])
def test_no_connection_glyph_overlaps_a_label(sv: dict, hand: str) -> None:
    svg = render(sv, header_type="Header 3", coil_hand=hand).side_svg
    gboxes = _glyph_boxes(svg)
    assert gboxes
    for t, b in _svg_label_boxes(svg):
        for g in gboxes:
            assert not boxes_overlap(b, g, tol=0.5), f"{hand}: glyph sits on {t!r}"


# --------------------------------------------------------------------------- #
# Phase 2.7 — ONE unified collision pass over ALL labels (dim + callout + note)
# --------------------------------------------------------------------------- #
_LABEL_CLASSES = ("dim-label", "callout", "omitted", "review")


def _svg_label_boxes(svg: str) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Every rendered text label as (text, bbox), using the SAME estimator the backend's
    de-collision uses — so this test and the engine agree."""
    out = []
    for m in re.finditer(r"<text([^>]*)>([^<]*)</text>", svg):
        attrs, text = m.group(1), m.group(2)
        cm = re.search(r'class="([^"]+)"', attrs)
        if not cm or cm.group(1) not in _LABEL_CLASSES:
            continue
        x = float(re.search(r'\bx="(-?[\d.]+)"', attrs).group(1))
        y = float(re.search(r'\by="(-?[\d.]+)"', attrs).group(1))
        am = re.search(r'text-anchor="(\w+)"', attrs)
        out.append((text, text_bbox(x, y, am.group(1) if am else "start", text, FONT_PX)))
    return out


@pytest.mark.parametrize("hand", ["LH", "RH"])
def test_no_label_overlaps_anywhere(hand: str) -> None:
    res = render(sanitized_slots(), coil_hand=hand)
    for svg in (res.svg, res.side_svg):
        boxes = _svg_label_boxes(svg)
        assert len(boxes) >= 5
        for (ta, a), (tb, b) in itertools.combinations(boxes, 2):
            assert not boxes_overlap(a, b), f"{hand}: {ta!r} overlaps {tb!r}"


def test_side_offsets_on_opposite_edges_do_not_overlap() -> None:
    # Phase 3c: the I/O offsets sit on opposite side edges (I left, O right), so the pair
    # that previously collided in the return column is clear by construction.
    boxes = _svg_label_boxes(render(sanitized_slots()).side_svg)
    i_off = next(b for t, b in boxes if t.endswith(" I"))
    o_off = next(b for t, b in boxes if t.endswith(" O"))
    assert i_off[2] < o_off[0]  # I's right edge is left of O's left edge
    assert not boxes_overlap(i_off, o_off)


def test_side_label_y_is_mirror_equivariant() -> None:
    # y is unaffected by the x-mirror and the de-collision nudges only in y, so the
    # (text, label-centre-y) multiset must be identical between LH and RH.
    def key(svg: str) -> list[tuple[str, float]]:
        return sorted((t, round((b[1] + b[3]) / 2.0, 1)) for t, b in _svg_label_boxes(svg))

    lh = render(sanitized_slots(), coil_hand="LH").side_svg
    rh = render(sanitized_slots(), coil_hand="RH").side_svg
    assert key(lh) == key(rh)


# --------------------------------------------------------------------------- #
# Phase 2.7b — every leader-bearing label is REACHED by its connector (geometric,
# not a leader-count proxy): the leader endpoint lands on the label's edge midpoint.
# --------------------------------------------------------------------------- #
REACH_TOL = 4.0


def _leader_endpoints(svg: str) -> list[tuple[float, float]]:
    pts = []
    for m in re.finditer(r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)" class="leader"', svg):
        pts.append((float(m.group(3)), float(m.group(4))))
        pts.append((float(m.group(1)), float(m.group(2))))
    for m in re.finditer(r'<path d="M [\d. ]+L [\d. ]+L ([\d.]+) ([\d.]+)" class="leader"', svg):
        pts.append((float(m.group(1)), float(m.group(2))))
    return pts


def _edge_mids(b: tuple[float, float, float, float]) -> tuple[tuple[float, float], ...]:
    x0, y0, x1, y1 = b
    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    return ((mx, y0), (mx, y1), (x0, my), (x1, my))


def _bearing_labels(svg: str) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Labels that rely on a leader: callouts + leader-style ('offset') dim labels."""
    codes = {m.group(1) for m in re.finditer(r'<g data-dim="(\w+)" data-style="leader"', svg)}
    out = []
    for m in re.finditer(r"<text([^>]*)>([^<]*)</text>", svg):
        attrs, text = m.group(1), m.group(2)
        cm = re.search(r'class="([^"]+)"', attrs)
        cls = cm.group(1) if cm else ""
        code = text.split()[-1] if text.split() else ""
        if not (cls == "callout" or (cls == "dim-label" and code in codes)):
            continue
        x = float(re.search(r'\bx="(-?[\d.]+)"', attrs).group(1))
        y = float(re.search(r'\by="(-?[\d.]+)"', attrs).group(1))
        am = re.search(r'text-anchor="(\w+)"', attrs)
        out.append((text, text_bbox(x, y, am.group(1) if am else "start", text, FONT_PX)))
    return out


def _reach_px(box: tuple[float, float, float, float], ends: list[tuple[float, float]]) -> float:
    mids = _edge_mids(box)
    return min(min(((e[0] - md[0]) ** 2 + (e[1] - md[1]) ** 2) ** 0.5 for md in mids) for e in ends)


@pytest.mark.parametrize("hand", ["LH", "RH"])
def test_every_leader_bearing_label_is_reached_by_its_connector(hand: str) -> None:
    res = render(sanitized_slots(), coil_hand=hand)
    for svg in (res.svg, res.side_svg):
        ends = _leader_endpoints(svg)
        labels = _bearing_labels(svg)
        assert labels and ends
        for text, box in labels:
            d = _reach_px(box, ends)
            assert d <= REACH_TOL, f"{hand}: {text!r} connector lands {d:.1f}px off (corner/detached)"


def test_i1_o2_connectors_reach_after_nudge() -> None:
    svg = render(sanitized_slots()).side_svg
    ends = _leader_endpoints(svg)
    boxes = {t: b for t, b in _bearing_labels(svg)}
    for code in ("3.00 I", "2.00 O"):
        assert _reach_px(boxes[code], ends) <= REACH_TOL


# --------------------------------------------------------------------------- #
# LH <-> RH mirror — single transform, both views
# --------------------------------------------------------------------------- #
def test_mirror_symmetry_both_views() -> None:
    vlh = build_dx_views(geometry(slots(), hand="LH"))
    vrh = build_dx_views(geometry(slots(), hand="RH"))
    for name in ("front", "side"):
        assert vrh[name] == mirror_view_x(vlh[name])  # RH == mirror(LH), bit-exact
        assert_views_close(mirror_view_x(mirror_view_x(vlh[name])), vlh[name])  # involution (float-tol)


def test_front_header_flange_side_flips_with_hand() -> None:
    lh = build_dx_views(geometry(slots(), hand="LH"))["front"]
    rh = build_dx_views(geometry(slots(), hand="RH"))["front"]
    assert dim_by_label(lh, "HF").edge == "left"
    assert dim_by_label(rh, "HF").edge == "right"


# --------------------------------------------------------------------------- #
# omission — never invent a value
# --------------------------------------------------------------------------- #
def test_missing_tf_slot_is_omitted_and_annotated() -> None:
    sv = slots()
    del sv["slot.TF"]
    assert geometry(sv).top_flange is None
    res = render(sv)
    assert any("TF" in note for note in res.omitted_features)
    assert 'data-dim="TF"' not in res.svg


def test_review_required_fh_omits_finned_face() -> None:
    sv = slots(**{"slot.FH": "REVIEW REQUIRED"})
    assert geometry(sv).finned_height is None
    res = render(sv)
    assert 'data-feature="finned"' not in res.svg
    assert any(("FH" in note or "finned" in note.lower()) for note in res.omitted_features)


def test_missing_return_connection_omits_circle_in_side_view() -> None:
    sv = slots()
    del sv["slot.RETURN_CONN_SIZE"]  # no return connection size
    rh = geometry(sv).headers[1]
    assert rh.role == "return" and rh.connection_diameter is None  # not invented
    res = render(sv)
    assert 'data-feature="connection_return"' not in res.side_svg
    assert any("connection size" in note for note in res.omitted_features)


# --------------------------------------------------------------------------- #
# safety flags — both views
# --------------------------------------------------------------------------- #
def test_safety_flags_and_watermark_on_both_views() -> None:
    res = render(slots())
    assert res.export_allowed is False
    assert res.metadata["export_allowed"] is False
    assert res.metadata["john_review_required"] is True
    for svg in (res.svg, res.side_svg):
        assert res.watermark in svg
        assert "NOT TO STANDARD SCALE" in svg


# --------------------------------------------------------------------------- #
# layer separation — model & layout carry inches, not pixels
# --------------------------------------------------------------------------- #
def test_model_and_layout_carry_no_pixels() -> None:
    geom = geometry(slots())
    layout = layout_dx_front_view(geom)
    assert isinstance(layout, ViewLayout)
    for cls in (CoilGeometry, HeaderSpec, ViewLayout, Dimension, Rect, LabeledRect, Circle, Segment):
        for f in dataclasses.fields(cls):
            assert "px" not in f.name.lower() and "pixel" not in f.name.lower()
    casing = next(lr.rect for lr in layout.rects if lr.feature == "casing")
    assert geom.casing_length == 24.0
    assert casing.w == 24.0


# --------------------------------------------------------------------------- #
# Phase 5a — a non-DX category now COMPOSES via the topology table (no longer a
# generic-box + "phase 3" deferral). HGRH resolves to a plain_header supply; its
# styled per-category glyphs are still deferred to 5b (phase3_deferred stays True).
# --------------------------------------------------------------------------- #
def test_non_dx_category_composes_via_topology_table() -> None:
    res = render_scale_schematic(
        slots(), coil_category="HGRH", coil_hand="LH", header_type="Header 3"
    )
    assert "<svg" in res.svg and "<svg" in res.side_svg and "<svg" in res.plan_svg
    assert res.metadata.get("topology_resolved") is True
    assert res.metadata.get("topology_id") == "T-HGRH"
    assert res.metadata.get("supply_kind") == "plain_header"
    # New-glyph rendering (supply_header_port / conn_angle_glyph) is Phase 5b.
    assert res.metadata.get("phase3_deferred") is True


# --------------------------------------------------------------------------- #
# Phase 4b — V3 distributor plan/top view (the new third view). HIGH slots drawn;
# review-bucket DistModel/DistOD drawn FLAGGED (label-only); blocked/None omitted+annotated.
# V1 front + V2 spread stay byte-unchanged. Obstacle-complete + mirror-equivariant.
# --------------------------------------------------------------------------- #
def dist_slots(sv: dict[str, object], ids: tuple[int, ...]) -> dict[str, object]:
    """Augment a slot dict with the Phase-4a HIGH distributor slots (AIRFLOW + DistExtension)."""
    out = dict(sv)
    out["slot.AIRFLOW"] = "left_to_right"
    for sid in ids:
        out[f"slot.DistExtension{sid}"] = 6.0
    return out


def dist_review(ids: tuple[int, ...], *, model: str = "501-2-3/16", od: float = 0.625) -> dict[str, object]:
    """The Phase-4a review-bucket values (DistModel opaque string + DistOD inches), per supply id."""
    rev: dict[str, object] = {}
    for sid in ids:
        rev[f"slot.DistModel{sid}"] = model
        rev[f"slot.DistOD{sid}"] = od
    return rev


def plan_render(circuits: int = 1, *, hand: str = "LH", blocked=None, review=None, sv=None):
    if circuits == 1:
        ids, ht = (1,), "Header 1"
        base = sv if sv is not None else sanitized_slots()
    else:
        ids, ht = (1, 3, 5), "Header 3"
        base = sv if sv is not None else multi_circuit_slots()
    rev = review if review is not None else dist_review(ids)
    return render_scale_schematic(
        dist_slots(base, ids), coil_category="DX", coil_hand=hand, header_type=ht,
        dist_review=rev, dist_blocked=blocked,
    ), ids


def _plan_features(svg: str) -> set[str]:
    return set(re.findall(r'data-feature="([a-z_]+)"', svg))


@pytest.mark.parametrize("circuits", [1, 3])
def test_plan_view_renders_all_v3_elements(circuits: int) -> None:
    res, ids = plan_render(circuits)
    svg = res.plan_svg
    feats = _plan_features(svg)
    # every V3 element kind is present
    for kind in ("nozzle_body", "feeder_fan", "dist_extension", "stub", "stub_cap",
                 "tube_run", "connection_return", "airflow_arrow", "casing"):
        assert kind in feats, f"missing plan feature {kind}"
    # one feeder line + one extension stem + one return ring per circuit
    assert svg.count('data-feature="feeder_fan"') == len(ids)
    assert svg.count('data-feature="dist_extension"') == len(ids)
    assert svg.count('data-feature="connection_return"') == len(ids)
    # AIRFLOW carries an explicit direction
    assert 'data-direction="left_to_right"' in svg
    assert res.metadata["views"] == ("front", "side", "plan")


@pytest.mark.parametrize("circuits", [1, 3])
def test_plan_reintroduces_deferred_labels(circuits: int) -> None:
    res, ids = plan_render(circuits)
    svg = res.plan_svg
    assert "RETURN" in svg and "DISTRIBUTORS" in svg and "OD:0.625" in svg
    for sid in ids:
        assert f"HDx{sid}" in svg  # supply distributor Ø
        assert f"HD{sid + 1}" in svg  # return header Ø (even id)
        assert f"SL{sid + 1}" in svg  # return stub length


def test_plan_review_bucket_drawn_flagged() -> None:
    # DistModel/DistOD ride the review bucket -> value carried AND flagged (review class + marker).
    res, _ = plan_render(1)
    svg = res.plan_svg
    assert 'class="review"' in svg
    flagged = next(t for t, _ in _svg_label_boxes(svg) if "DISTRIBUTORS" in t)
    assert "501-2-3/16" in flagged and "OD:0.625" in flagged  # value carried
    assert "REVIEW" in flagged  # and visibly un-confirmed


def test_plan_model_string_is_label_only_no_geometry_derived() -> None:
    # The DistModel is an opaque string: changing it (numbers and all) must change ONLY the
    # label text, never any geometry (segments / circles / dimensions). OD still sizes the ring.
    a, _ = plan_render(1, review=dist_review((1,), model="501-2-3/16", od=0.625))
    b, _ = plan_render(1, review=dist_review((1,), model="999-9-9/99", od=0.625))

    def geom_only(svg: str) -> str:
        # strip all <text> nodes; keep rects/lines/circles/paths (the drawn geometry)
        return re.sub(r"<text[^>]*>[^<]*</text>", "", svg)

    assert geom_only(a.plan_svg) == geom_only(b.plan_svg)  # geometry identical -> label-only
    assert "999-9-9/99" in b.plan_svg  # but the new string IS shown (flagged)


def test_plan_blocked_distextension_omitted_and_annotated() -> None:
    res, _ = plan_render(1, blocked=["DistExtension1"])
    assert 'data-feature="dist_extension"' not in res.plan_svg  # conflicted -> not drawn
    assert any("DistExtension1" in n for n in res.omitted_features)  # annotated


def test_plan_missing_distod_falls_back_to_return_conn_ring() -> None:
    # DistOD absent (review carries only the model) -> the port ring falls back to the gated
    # RETURN_CONN_SIZE; the value is never invented from the model string.
    res, _ = plan_render(1, review={"slot.DistModel1": "501-2-3/16"})
    assert res.plan_svg.count('data-feature="connection_return"') == 1


def test_plan_missing_return_conn_omits_ring_and_annotates() -> None:
    sv = sanitized_slots()
    del sv["slot.RETURN_CONN_SIZE"]
    res, _ = plan_render(1, sv=sv, review={"slot.DistModel1": "501-2-3/16"})  # no OD, no conn size
    assert 'data-feature="connection_return"' not in res.plan_svg
    assert any("connection size" in n for n in res.omitted_features)


def test_plan_missing_airflow_omits_arrow_and_annotates() -> None:
    sv = sanitized_slots()
    res = render_scale_schematic(  # note: no slot.AIRFLOW
        {**sv, "slot.DistExtension1": 6.0}, coil_category="DX", coil_hand="LH",
        header_type="Header 1", dist_review=dist_review((1,)),
    )
    assert 'data-feature="airflow_arrow"' not in res.plan_svg
    assert any("AIRFLOW" in n for n in res.omitted_features)


@pytest.mark.parametrize("circuits", [1, 3])
@pytest.mark.parametrize("hand", ["LH", "RH"])
def test_plan_no_annotation_line_through_a_label(circuits: int, hand: str) -> None:
    svg = plan_render(circuits, hand=hand)[0].plan_svg
    boxes = _svg_label_boxes(svg)
    segs = _annotation_segments(svg)
    assert boxes and segs
    for x1, y1, x2, y2 in segs:
        for t, b in boxes:
            shrunk = (b[0] + 2.5, b[1] + 2.5, b[2] - 2.5, b[3] - 2.5)
            assert not _seg_hits_box(x1, y1, x2, y2, shrunk), f"{hand}: line crosses {t!r}"


@pytest.mark.parametrize("circuits", [1, 3])
@pytest.mark.parametrize("hand", ["LH", "RH"])
def test_plan_no_glyph_overlaps_a_label(circuits: int, hand: str) -> None:
    svg = plan_render(circuits, hand=hand)[0].plan_svg
    gboxes = _glyph_boxes(svg)
    assert gboxes
    for t, b in _svg_label_boxes(svg):
        for g in gboxes:
            assert not boxes_overlap(b, g, tol=0.5), f"{hand}: glyph sits on {t!r}"


@pytest.mark.parametrize("circuits", [1, 3])
def test_plan_no_label_overlaps(circuits: int) -> None:
    for hand in ("LH", "RH"):
        boxes = _svg_label_boxes(plan_render(circuits, hand=hand)[0].plan_svg)
        assert len(boxes) >= 6
        for (ta, a), (tb, b) in itertools.combinations(boxes, 2):
            assert not boxes_overlap(a, b), f"{hand}: {ta!r} overlaps {tb!r}"


@pytest.mark.parametrize("circuits", [1, 3])
def test_plan_mirror_equivariant_including_airflow_direction(circuits: int) -> None:
    lh = plan_render(circuits, hand="LH")[0].plan_svg
    rh = plan_render(circuits, hand="RH")[0].plan_svg

    def key(svg: str) -> list[tuple[str, float]]:
        return sorted((t, round((b[1] + b[3]) / 2.0, 1)) for t, b in _svg_label_boxes(svg))

    assert key(lh) == key(rh)  # label (text, centre-y) multiset identical under the x-mirror
    direction = lambda s: re.search(r'data-direction="([a-z_]+)"', s).group(1)
    assert direction(lh) == direction(rh)  # AIRFLOW direction is mirror-INVARIANT (not flipped)


def test_plan_view_is_additive_front_and_side_unchanged() -> None:
    # Adding the plan view + distributor params must not change the front or side outputs.
    sv = sanitized_slots()
    base = render_scale_schematic(sv, coil_category="DX", coil_hand="LH", header_type="Header 1")
    withv3 = render_scale_schematic(
        dist_slots(sv, (1,)), coil_category="DX", coil_hand="LH", header_type="Header 1",
        dist_review=dist_review((1,)), dist_blocked=["DistExtension1"],
    )
    assert withv3.svg == base.svg
    assert withv3.side_svg == base.side_svg


def test_plan_safety_flags_and_watermark() -> None:
    res, _ = plan_render(1)
    assert res.metadata["export_allowed"] is False
    assert res.watermark in res.plan_svg
    assert "NOT TO STANDARD SCALE" in res.plan_svg
    assert "plan" in res.plan_svg  # the view is labelled


# =========================================================================== #
# Phase 5a — table-driven topology: composition + supply-kind toggle + the DX
# byte-identical regression guard. (Sourcing/gating proofs live in
# tests/test_topology_slots.py.)
# =========================================================================== #
def _features(view: ViewLayout) -> set[str]:
    return {s.feature for s in view.segments} | {c.feature for c in view.circles}


def _views_for(category: str, *, header_type: str, special=None, hand: str = "LH",
               sv: dict | None = None) -> dict[str, ViewLayout]:
    sv = slots() if sv is None else sv
    geom = CoilGeometry.from_slot_values(
        sv, coil_category=category, coil_hand=hand, header_type=header_type, special_feature=special
    )
    return build_views(geom, resolve_topology(category, header_type, special))


# --- E1: per-category feature SET (right views + supply/return kind) -------- #
def test_dx_feature_set_has_distributor_supply_and_three_views() -> None:
    views = _views_for("DX", header_type="Header 1")
    assert set(views) == {"front", "side", "plan"}
    plan = _features(views["plan"])
    assert {"nozzle_body", "feeder_fan"} <= plan        # distributor supply glyphs present
    assert "connection_supply" not in plan              # not a plain header port


@pytest.mark.parametrize(
    "category,header_type,special",
    [("HGRH", "Header 1", None), ("CWC", "Header 1", None),
     ("HWC", "Header 1", None), ("DX", None, "HGBP")],
)
def test_each_category_renders_correct_views(category, header_type, special) -> None:
    views = _views_for(category, header_type=header_type, special=special)
    topo = resolve_topology(category, header_type, special)
    assert set(views) == set(topo.views) == {"front", "side", "plan"}


# --- E2: supply-kind toggle (distributor vs plain header port) -------------- #
@pytest.mark.parametrize("category,header_type", [("HGRH", "Header 1"), ("CWC", "Header 1"), ("HWC", "Header 1")])
def test_plain_header_supply_uses_existing_circle_no_distributor_glyph(category, header_type) -> None:
    views = _views_for(category, header_type=header_type)
    for name in ("side", "plan"):
        feats = _features(views[name])
        # plain supply header port = the EXISTING connection circle primitive…
        assert "connection_supply" in feats, f"{category} {name} missing plain supply port"
        # …and NONE of the distributor-only glyphs (deferred styled glyph is 5b).
        assert not ({"distributor_supply", "nozzle_body", "feeder_fan", "dist_extension"} & feats), (
            f"{category} {name} drew a distributor glyph"
        )


def test_dx_vs_plain_header_toggle_is_the_only_supply_difference() -> None:
    dx_plan = _features(_views_for("DX", header_type="Header 1")["plan"])
    hgrh_plan = _features(_views_for("HGRH", header_type="Header 1")["plan"])
    assert "nozzle_body" in dx_plan and "nozzle_body" not in hgrh_plan
    assert "connection_supply" in hgrh_plan and "connection_supply" not in dx_plan
    # the return path is unchanged across the toggle
    assert "connection_return" in dx_plan and "connection_return" in hgrh_plan


# --- E4: the engine consumes gated slots only; blocked -> omit + annotate --- #
def test_blocked_topo_slot_is_annotated_not_drawn() -> None:
    res = render_scale_schematic(
        slots(), coil_category="DX", coil_hand="LH", header_type="Header 1",
        special_feature="HGBP", topo_blocked=["asc_orientation"],
    )
    assert any("asc_orientation" in n and "blocked" in n.lower() for n in res.omitted_features)
    # no new glyph renders it in 5a (deferred to 5b)
    assert "asc_orientation" not in res.plan_svg


def test_review_bucket_vent_drain_is_carried_not_drawn_as_confirmed() -> None:
    geom = CoilGeometry.from_slot_values(
        slots(), coil_category="CWC", coil_hand="LH", header_type="Header 1",
        special_feature=None, topo_review={"slot.vent_drain": "Connections"},
    )
    assert geom.vent_drain == "Connections"           # carried for 5b
    assert "vent_drain" in geom.topo_review_labels     # flagged as review-sourced


# --- E5: topology fail-closed (no DX fallback) ------------------------------ #
def test_resolve_topology_raises_on_unknown() -> None:
    with pytest.raises(UnknownTopologyError):
        resolve_topology("NOT_A_CATEGORY", "Header 1", None)


def test_render_is_fail_closed_on_unknown_topology() -> None:
    res = render_scale_schematic(
        slots(), coil_category="NOPE", coil_hand="LH", header_type="Header 1"
    )
    assert res.metadata.get("topology_resolved") is False
    assert res.svg == "" and res.side_svg == "" and res.plan_svg == ""  # no DX fallback geometry
    assert res.export_allowed is False
    assert any("no topology" in n.lower() for n in res.omitted_features)


# --- E6: DX REGRESSION GUARD — byte-identical vs the Phase-4 baseline ------- #
_GOLDEN = Path(__file__).resolve().parents[1] / "tests" / "golden" / "phase5_dx_baseline"


def _dx_high(ids: tuple[int, ...]) -> dict[str, object]:
    sv: dict[str, object] = {"slot.AIRFLOW": "left_to_right"}
    for i in ids:
        sv[f"slot.DistExtension{i}"] = 6.0
    return sv


@pytest.mark.parametrize(
    "name,sv_factory,hand,ids,review",
    [
        ("single_lh", sanitized_slots, "LH", (1,), {"slot.DistModel1": "501-2", "slot.DistOD1": 0.625}),
        ("single_rh", sanitized_slots, "RH", (1,), {"slot.DistModel1": "501-2", "slot.DistOD1": 0.625}),
        ("multi_lh", multi_circuit_slots, "LH", (1, 3, 5), {}),
        ("multi_rh", multi_circuit_slots, "RH", (1, 3, 5), {}),
    ],
)
def test_dx_output_byte_identical_to_phase4_baseline(name, sv_factory, hand, ids, review) -> None:
    """The table-driven refactor must not change ANY DX byte. Baseline captured from the
    pre-refactor engine for DX single (EZC-0001) + multi (EZC-0007) x LH/RH x V1/V2/V3."""
    sv = dict(sv_factory(), **_dx_high(ids))
    res = render_scale_schematic(
        sv, coil_category="DX", coil_hand=hand, header_type="Header 1", dist_review=review,
    )
    for view, svg in (("front", res.svg), ("side", res.side_svg), ("plan", res.plan_svg)):
        want = (_GOLDEN / f"{name}_{view}.svg").read_text(encoding="utf-8")
        assert normalize_svg_for_regression(svg) == want, f"DX {name} {view} drifted from baseline"


# --- Task D: the per-category sanitized fixtures are well-formed ------------ #
@pytest.mark.parametrize(
    "filename,category,special",
    [
        ("hgrh_header1_ezc0002_default.json", "HGRH", None),
        ("cwc_header1_ezc0014_default.json", "CWC", None),
        ("hwc_header1_ezc0005_default.json", "HWC", None),
        ("dx_hgbp_ezc0013_default.json", "DX", "HGBP"),
        ("cwc_header1_terra_v_default.json", "CWC", None),
    ],
)
def test_sanitized_fixture_resolves_a_topology(filename, category, special) -> None:
    import json

    path = Path(__file__).resolve().parents[1] / "examples" / "sanitized" / filename
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["coil_category"] == category
    assert data["fixture_status"] == "sanitized_example"
    # every fixture must map to a real topology row (no DX fallback).
    topo = resolve_topology(data["coil_category"], data.get("header_type"), data.get("special_feature"))
    assert topo.id.startswith("T-")
