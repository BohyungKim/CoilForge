"""`_clean_template_svg` — short-term cleanup of the populated CoilMaster template to the
direct-coil ordering view (image #7): numbers-only dim callouts + viewBox cropped to the
drawing region (clips the panel / dim table / title block / notes chrome)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.workflows.submittal_to_drawing import _clean_template_svg


_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="792" height="612" viewBox="0 0 792 612">'
    # blue dimension callouts (value + label code)
    '<text font-size="11" fill="#1c0a80" transform="matrix(-1 0 0 1 0 0)"><tspan x="1" y="2">3.5 HD2</tspan></text>'
    '<text font-size="11" fill="#1c0a80" transform="matrix(-1 0 0 1 0 0)"><tspan x="1" y="2">12 FH</tspan></text>'
    '<text font-size="11" fill="#1c0a80" transform="matrix(-1 0 0 1 0 0)"><tspan x="1" y="2">REVIEW REQUIRED OAL</tspan></text>'
    # chrome (different colour) must not be touched by the label strip
    '<text fill="#000000"><tspan x="1" y="2">TUBE MATERIAL</tspan></text>'
    "</svg>"
)


def test_clean_strips_dim_labels_to_numbers_only() -> None:
    out = _clean_template_svg(_SVG)
    assert ">3.5</tspan>" in out and ">12</tspan>" in out
    assert "REVIEW REQUIRED" not in out  # blank-slot placeholder dropped entirely
    assert "HD2</tspan>" not in out and " FH</tspan>" not in out and " OAL</tspan>" not in out


def test_clean_does_not_touch_non_callout_text() -> None:
    assert "TUBE MATERIAL" in _clean_template_svg(_SVG)  # panel text only clipped by the crop


def test_clean_crops_viewbox_and_size_to_drawing() -> None:
    out = _clean_template_svg(_SVG)
    assert 'viewBox="110 19 542 473"' in out
    assert 'width="542" height="473"' in out
    assert 'viewBox="0 0 792 612"' not in out


_SVG_WITH_INTRUDING_CHROME = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="792" height="612" viewBox="0 0 792 612">'
    # top-left fabrication-notes block: bold, anchored far-left in the top band
    '<text font-family="Arial,Bold" font-weight="bold">'
    '<tspan y="-562.5" x="47.99 54.78 62.09">COLLARED HOLES REQUIRED</tspan>'
    '<tspan y="-535.5" x="47.99 54.78">DISTRIBUTOR 1 HAS 6&quot; EXTENSION</tspan></text>'
    # bottom metadata line whose glyph tops poke into the crop
    '<text font-family="Arial"><tspan y="-113.5" x="578.3 50.9">'
    'Coil ID = 543681Casing Style: FlangedStacking Flanges: False</tspan></text>'
    # a real blue dimension callout that must survive
    '<text fill="#1c0a80" transform="matrix(-1 0 0 1 0 0)"><tspan x="300" y="200">12 FH</tspan></text>'
    # DIST LIST heading + its distributor-part entries: sheet metadata, removed
    '<text font-family="Arial"><tspan y="-552.6" x="561.9 567.4">DIST LIST</tspan></text>'
    '<text font-family="Arial"><tspan y="-539.1" x="527.0 529.5">(1)501-4-3/16-4 OD:5/8</tspan></text>'
    "</svg>"
)


def test_clean_strips_intruding_chrome_keeps_geometry() -> None:
    out = _clean_template_svg(_SVG_WITH_INTRUDING_CHROME)
    # top-left fabrication notes + bottom metadata line removed
    assert "COLLARED HOLES REQUIRED" not in out
    assert "DISTRIBUTOR 1 HAS" not in out
    assert "Coil ID" not in out and "Casing Style" not in out
    # geometry dimension value kept; DIST LIST heading + distributor entries removed
    assert ">12</tspan>" in out
    assert "DIST LIST" not in out
    assert "501-" not in out and "OD:5/8" not in out


def test_clean_handles_empty() -> None:
    assert _clean_template_svg("") == ""
