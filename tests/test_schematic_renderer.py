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
    layout_dx_front_view,
    layout_header_side_view,
    mirror_view_x,
)
from coilforge.drawing.schematic_model import CoilGeometry, HeaderSpec
from coilforge.drawing.schematic_renderer import SchematicResult, render_scale_schematic


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def slots(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        # front
        "slot.FL": 18.0, "slot.FH": 18.0, "slot.CL": 24.0, "slot.CH": 24.0,
        "slot.TF": 3.0, "slot.BF": 3.0, "slot.HF": 3.0, "slot.RF": 3.0,
        # side / header
        "slot.CD": 12.0, "slot.ROWS": 4, "slot.HDx1": 4.5, "slot.HD2": 3.5,
        "slot.I1": 6.0, "slot.O2": 4.0, "slot.SL2": 3.0, "slot.RETURN_CONN_SIZE": 0.625,
    }
    base.update(over)
    return base


def sanitized_slots() -> dict[str, object]:
    # A real, small DX coil (sanitized example values).
    return {
        "slot.FH": 12.0, "slot.FL": 15.0, "slot.CH": 13.25, "slot.CL": 18.0,
        "slot.TF": 0.63, "slot.BF": 0.63, "slot.HF": 1.5, "slot.RF": 1.5,
        "slot.CD": 5.5, "slot.ROWS": 4, "slot.HDx1": 4.5, "slot.HD2": 3.5,
        "slot.I1": 3.0, "slot.O2": 2.0, "slot.SL2": 8.0, "slot.RETURN_CONN_SIZE": 0.625,
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
    _assert_no_tier_collision(layout)  # CH overall vs I1/O2 offsets disjoint; CD vs SL2 disjoint
    res = render(slots())
    # header offsets are offsets -> leader style (never crammed arrowheads).
    assert 'data-dim="O2" data-style="leader"' in res.side_svg
    assert 'data-dim="CD" data-style="arrows"' in res.side_svg


def _side_casing(layout: ViewLayout) -> Rect:
    return next(lr.rect for lr in layout.rects if lr.feature == "casing")


def _connections(layout: ViewLayout) -> list[Circle]:
    return [c for c in layout.circles if c.feature.startswith("connection")]


def test_side_offset_dims_colocated_with_connections() -> None:
    # Phase 2.5 fix: I1/O2 witness to the SAME (left) side as the connections, not the
    # opposite edge.
    layout = layout_header_side_view(geometry(slots()))
    casing = _side_casing(layout)
    for label in ("I1", "O2"):
        dim = dim_by_label(layout, label)
        assert dim.edge == "left"
        assert dim.ax == pytest.approx(casing.x)  # attaches at the header face
    conns = _connections(layout)
    assert conns and all(c.cx <= casing.x + 1e-9 for c in conns)  # on the left of the face


def test_connections_sit_at_face_not_buried_in_casing() -> None:
    layout = layout_header_side_view(geometry(sanitized_slots()))
    casing = _side_casing(layout)
    conns = _connections(layout)
    assert conns
    for c in conns:
        assert c.cx + c.r <= casing.x + 0.1  # tangent/at the face, not inside the casing


def test_header_diameter_is_a_label_not_a_manifold_circle() -> None:
    res = render(sanitized_slots())
    assert 'data-label="hd_supply"' in res.side_svg and "HDx1" in res.side_svg
    assert 'data-label="hd_return"' in res.side_svg and "HD2" in res.side_svg
    # the only circles are connections — no full-diameter manifold circles.
    assert "header_supply" not in res.side_svg and "header_return" not in res.side_svg


def test_distinct_connections_do_not_overlap() -> None:
    conns = _connections(layout_header_side_view(geometry(sanitized_slots())))
    for a, b in itertools.combinations(conns, 2):
        dist = ((a.cx - b.cx) ** 2 + (a.cy - b.cy) ** 2) ** 0.5
        assert dist >= a.r + b.r - 0.05  # physically plausible: no overlap


def test_side_labels_match_ez_convention() -> None:
    # EZ: geometry callouts are "{value} {CODE}" (value-first, no Ø/unit); the return
    # connection follows EZ's panel style "RETURN {value}". data-dim stays the bare CODE.
    svg = render(sanitized_slots()).side_svg
    assert "4.50 HDx1" in svg  # supply header diameter callout
    assert "3.50 HD2" in svg  # return header diameter callout
    assert "2.00 O2" in svg and 'data-dim="O2"' in svg  # value-first dim text, bare-code id
    assert 'data-label="conn_return"' in svg and "RETURN" in svg  # return connection label


def test_supply_distributor_is_labels_only_no_circle() -> None:
    # The distributor has no sweat connection (EZ ConnectionSize=0): labels only, no circle.
    res = render(sanitized_slots())
    assert 'data-feature="connection_supply"' not in res.side_svg
    assert 'data-feature="connection_return"' in res.side_svg
    assert 'data-label="hd_supply"' in res.side_svg  # HDx1 callout still shown
    assert 'data-dim="I1"' in res.side_svg  # and the I1 offset
    # The overlap guard remains in code for Phase 3 multi-circuit, but a single-circuit DX
    # draws exactly one connection, so it cannot overlap here.
    assert res.side_svg.count('data-feature="connection_') == 1


def test_small_offset_renders_as_leader_not_arrowheads() -> None:
    res = render(sanitized_slots())
    assert 'data-dim="TF" data-style="leader"' in res.svg
    assert 'data-dim="CL" data-style="arrows"' in res.svg


# --------------------------------------------------------------------------- #
# Phase 2.7 — ONE unified collision pass over ALL labels (dim + callout + note)
# --------------------------------------------------------------------------- #
_LABEL_CLASSES = ("dim-label", "callout", "omitted")


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


def test_i1_dim_and_return_callout_no_longer_overlap() -> None:
    # The previously-colliding pair on the side view.
    boxes = _svg_label_boxes(render(sanitized_slots()).side_svg)
    i1 = next(b for t, b in boxes if t.endswith(" I1"))
    ret = next(b for t, b in boxes if t.startswith("RETURN"))
    assert not boxes_overlap(i1, ret)


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
    for code in ("3.00 I1", "2.00 O2"):
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
# non-DX category renders generic boxes + a Phase 3 deferral note
# --------------------------------------------------------------------------- #
def test_non_dx_category_renders_box_with_phase3_note() -> None:
    res = render_scale_schematic(
        slots(), coil_category="HGRH", coil_hand="LH", header_type="Header 3"
    )
    assert "<svg" in res.svg and "<svg" in res.side_svg
    assert res.metadata.get("phase3_deferred") is True
    assert any("phase 3" in note.lower() or "phase3" in note.lower() for note in res.omitted_features)
