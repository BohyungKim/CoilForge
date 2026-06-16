"""Phase 1 / 1.5 — parametric drawing engine (DX front view, SVG).

These tests pin the three-layer contract:
  L1 CoilGeometry (inches only) -> L2 FrontViewLayout (inches only) -> L3 SVG (pixels).

Load-bearing properties:
  * uniform, SCALE-INDEPENDENT px_per_inch — casing/finned pixel aspect equals the inch
    aspect at any canvas size (anti-regression against renderer.py's x18/x16 distortion);
  * per-drawing fit-to-canvas — small and large coils both fill the canvas to a target
    fraction with aspect preserved (Phase 1.5: no more floating at the MAX clamp);
  * tiered, collision-free dimensioning — overall dims and flange offsets never share a
    perpendicular band (Phase 1.5);
  * small offsets drawn with a leader, not crammed double arrowheads (Phase 1.5);
  * missing / "REVIEW REQUIRED" slots omitted + annotated, never invented;
  * safety flags (export_allowed False, watermark present);
  * model and layout carry no pixels.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.drawing.backends.svg import (
    PAD_PX,
    TARGET_FILL,
    SvgBackendResult,
    render_front_view_svg,
)
from coilforge.drawing.schematic_layout import (
    Dimension,
    FrontViewLayout,
    layout_dx_front_view,
)
from coilforge.drawing.schematic_model import CoilGeometry
from coilforge.drawing.schematic_renderer import SchematicResult, render_scale_schematic


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def slots(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "slot.FL": 18.0,
        "slot.FH": 18.0,
        "slot.CL": 24.0,
        "slot.CH": 24.0,
        "slot.TF": 3.0,
        "slot.BF": 3.0,
        "slot.HF": 3.0,
        "slot.RF": 3.0,
    }
    base.update(over)
    return base


# A real, small DX coil (sanitized example values) — the case that must read cleanly,
# with sub-1" flanges that must render as leaders, not arrowhead clusters.
def sanitized_slots() -> dict[str, object]:
    return {
        "slot.FH": 12.0,
        "slot.FL": 15.0,
        "slot.CH": 13.25,
        "slot.CL": 18.0,
        "slot.TF": 0.63,
        "slot.BF": 0.63,
        "slot.HF": 1.5,
        "slot.RF": 1.5,
    }


def geometry(sv: dict[str, object], *, category: str = "DX", hand: str = "LH") -> CoilGeometry:
    return CoilGeometry.from_slot_values(
        sv, coil_category=category, coil_hand=hand, header_type="Header 1", special_feature=None
    )


def backend(sv: dict[str, object], *, canvas: tuple[int, int] = (1000, 780)) -> SvgBackendResult:
    layout = layout_dx_front_view(geometry(sv))
    return render_front_view_svg(layout, canvas_w=canvas[0], canvas_h=canvas[1])


def render(sv: dict[str, object], **kw: object) -> SchematicResult:
    params: dict[str, object] = dict(coil_category="DX", coil_hand="LH", header_type="Header 1")
    params.update(kw)
    return render_scale_schematic(sv, **params)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# proportionality / uniform scale — now SCALE-INDEPENDENT
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("canvas", [(1000, 780), (1400, 900), (640, 480)])
def test_casing_aspect_matches_inches_at_any_scale(canvas: tuple[int, int]) -> None:
    # one px_per_inch for both axes => casing pixel aspect == inch aspect, regardless of
    # canvas/scale. Anti-regression against renderer.py's x18 (width) / x16 (height).
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
    tall_aspect = tall.casing_px[2] / tall.casing_px[3]
    wide_aspect = wide.casing_px[2] / wide.casing_px[3]
    assert tall_aspect < 1.0 < wide_aspect


# --------------------------------------------------------------------------- #
# fit-to-canvas — small and large coils both fill the canvas (Phase 1.5)
# --------------------------------------------------------------------------- #
def test_fit_to_canvas_fills_target_and_scale_differs() -> None:
    canvas = (1000, 780)
    avail_w, avail_h = canvas[0] - 2 * PAD_PX, canvas[1] - 2 * PAD_PX

    def fill_fraction(sv: dict[str, object]) -> tuple[float, float]:
        layout = layout_dx_front_view(geometry(sv))
        r = render_front_view_svg(layout, canvas_w=canvas[0], canvas_h=canvas[1])
        drawn_w, drawn_h = layout.extent_w * r.px_per_inch, layout.extent_h * r.px_per_inch
        return max(drawn_w / avail_w, drawn_h / avail_h), r.px_per_inch

    small_fill, small_ppi = fill_fraction(sanitized_slots())  # ~18" coil
    large_fill, large_ppi = fill_fraction(slots(**{"slot.CL": 240.0, "slot.CH": 120.0}))

    assert small_fill == pytest.approx(TARGET_FILL, abs=1e-3)
    assert large_fill == pytest.approx(TARGET_FILL, abs=1e-3)
    # same fill fraction, very different real sizes => different scale.
    assert small_ppi > large_ppi


# --------------------------------------------------------------------------- #
# tiered dimensioning — no overall/offset band collisions (Phase 1.5)
# --------------------------------------------------------------------------- #
def test_no_label_band_collision() -> None:
    layout = layout_dx_front_view(geometry(slots()))
    by_edge: dict[str, dict[str, set[int]]] = {}
    for dim in layout.dimensions:
        kinds = by_edge.setdefault(dim.edge, {"overall": set(), "offset": set()})
        kinds[dim.kind].add(dim.tier)
    # every edge carries both an overall and an offset here, on disjoint tiers.
    assert by_edge  # something was placed
    for edge, kinds in by_edge.items():
        assert kinds["overall"].isdisjoint(kinds["offset"]), f"tier collision on {edge}"


def test_small_offset_renders_as_leader_not_arrowheads() -> None:
    # sanitized TF = 0.63" is far below the leader threshold at fill scale.
    res = render(sanitized_slots())
    assert 'data-dim="TF" data-style="leader"' in res.svg
    # a large overall dimension keeps arrowheads.
    assert 'data-dim="CL" data-style="arrows"' in res.svg


# --------------------------------------------------------------------------- #
# omission — never invent a value
# --------------------------------------------------------------------------- #
def test_missing_tf_slot_is_omitted_and_annotated() -> None:
    sv = slots()
    del sv["slot.TF"]
    assert geometry(sv).top_flange is None  # not invented
    res = render(sv)
    assert any("TF" in note for note in res.omitted_features)
    assert 'data-dim="TF"' not in res.svg  # no TF dimension drawn


def test_review_required_fh_omits_finned_face() -> None:
    sv = slots(**{"slot.FH": "REVIEW REQUIRED"})
    assert geometry(sv).finned_height is None  # gate enforced at the model
    res = render(sv)
    assert 'data-feature="finned"' not in res.svg
    assert any(("FH" in note or "finned" in note.lower()) for note in res.omitted_features)


# --------------------------------------------------------------------------- #
# safety flags
# --------------------------------------------------------------------------- #
def test_safety_flags_and_watermark() -> None:
    res = render(slots())
    assert res.export_allowed is False
    assert res.watermark
    assert res.watermark in res.svg
    assert "NOT TO STANDARD SCALE" in res.svg
    assert res.metadata["export_allowed"] is False
    assert res.metadata["john_review_required"] is True


# --------------------------------------------------------------------------- #
# layer separation — model & layout carry inches, not pixels
# --------------------------------------------------------------------------- #
def test_model_and_layout_carry_no_pixels() -> None:
    geom = geometry(slots())
    layout = layout_dx_front_view(geom)
    assert isinstance(layout, FrontViewLayout)
    for cls in (geom, layout):
        for f in dataclasses.fields(cls):
            assert "px" not in f.name.lower() and "pixel" not in f.name.lower()
    for f in dataclasses.fields(Dimension):
        assert "px" not in f.name.lower() and "pixel" not in f.name.lower()
    # inch values pass through untouched.
    assert geom.casing_length == 24.0
    assert layout.casing.w == 24.0


# --------------------------------------------------------------------------- #
# non-DX category renders a generic front box + a Phase 3 deferral note
# --------------------------------------------------------------------------- #
def test_non_dx_category_renders_front_box_with_phase3_note() -> None:
    res = render_scale_schematic(
        slots(), coil_category="HGRH", coil_hand="LH", header_type="Header 3"
    )
    assert "<svg" in res.svg
    assert res.metadata.get("phase3_deferred") is True
    assert any("phase 3" in note.lower() or "phase3" in note.lower() for note in res.omitted_features)
