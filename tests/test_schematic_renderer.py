"""Phase 1 — parametric drawing engine v0 (DX front view, SVG).

These tests pin the three-layer contract:
  L1 CoilGeometry (inches only) -> L2 FrontViewLayout (inches only) -> L3 SVG (pixels).

The load-bearing properties verified here are:
  * uniform px_per_inch (a skinny coil renders skinny, a wide coil wide) — the
    anti-regression against renderer.py's x18/x16 aspect distortion;
  * proportionality (doubling an inch dimension doubles its pixels when the scale
    is clamp-pinned);
  * missing / "REVIEW REQUIRED" slots are omitted + annotated, never invented;
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
    MAX_PPI,
    SvgBackendResult,
    render_front_view_svg,
)
from coilforge.drawing.schematic_layout import FrontViewLayout, layout_dx_front_view
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


def geometry(sv: dict[str, object], *, category: str = "DX", hand: str = "LH") -> CoilGeometry:
    return CoilGeometry.from_slot_values(
        sv, coil_category=category, coil_hand=hand, header_type="Header 1", special_feature=None
    )


def backend(sv: dict[str, object], *, canvas: tuple[int, int] = (4000, 4000)) -> SvgBackendResult:
    layout = layout_dx_front_view(geometry(sv))
    return render_front_view_svg(layout, canvas_w=canvas[0], canvas_h=canvas[1])


def render(sv: dict[str, object], **kw: object) -> SchematicResult:
    params: dict[str, object] = dict(
        coil_category="DX", coil_hand="LH", header_type="Header 1"
    )
    params.update(kw)
    return render_scale_schematic(sv, **params)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# proportionality / uniform scale (the core point of the slice)
# --------------------------------------------------------------------------- #
def test_doubling_ch_doubles_casing_px_height_when_pinned() -> None:
    a = backend(slots())  # CH = 24
    b = backend(slots(**{"slot.CH": 48.0}))  # CH = 48
    # large canvas => both pinned at MAX_PPI => scale is constant => exact doubling.
    assert a.px_per_inch == pytest.approx(MAX_PPI)
    assert b.px_per_inch == pytest.approx(MAX_PPI)
    assert b.casing_px[3] == pytest.approx(2 * a.casing_px[3])


def test_fl_fh_ratio_preserved_in_finned_box() -> None:
    r = backend(slots(**{"slot.FL": 40.0, "slot.FH": 10.0}))
    assert r.finned_px is not None
    _, _, w, h = r.finned_px
    assert w / h == pytest.approx(40.0 / 10.0)


def test_uniform_scale_casing_aspect_matches_inches() -> None:
    # one px_per_inch for both axes => casing pixel aspect == inch aspect.
    # This is the anti-regression against renderer.py's x18 (width) / x16 (height).
    r = backend(slots(**{"slot.CL": 50.0, "slot.CH": 10.0}))
    _, _, w, h = r.casing_px
    assert w / h == pytest.approx(50.0 / 10.0)


def test_skinny_and_wide_have_visibly_different_aspect() -> None:
    tall = backend(slots(**{"slot.CL": 24.0, "slot.CH": 66.0}))
    wide = backend(slots(**{"slot.CL": 126.0, "slot.CH": 24.0}))
    tall_aspect = tall.casing_px[2] / tall.casing_px[3]
    wide_aspect = wide.casing_px[2] / wide.casing_px[3]
    assert tall_aspect < 1.0 < wide_aspect


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
    assert res.metadata["export_allowed"] is False
    assert res.metadata["john_review_required"] is True


# --------------------------------------------------------------------------- #
# layer separation — model & layout carry inches, not pixels
# --------------------------------------------------------------------------- #
def test_model_and_layout_carry_no_pixels() -> None:
    geom = geometry(slots())
    layout = layout_dx_front_view(geom)
    assert isinstance(layout, FrontViewLayout)
    for f in dataclasses.fields(geom):
        assert "px" not in f.name.lower() and "pixel" not in f.name.lower()
    for f in dataclasses.fields(layout):
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
