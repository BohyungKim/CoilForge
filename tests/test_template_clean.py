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
    assert ">REVIEW REQUIRED</tspan>" in out  # value kept, label dropped
    assert "HD2</tspan>" not in out and " FH</tspan>" not in out and " OAL</tspan>" not in out


def test_clean_does_not_touch_non_callout_text() -> None:
    assert "TUBE MATERIAL" in _clean_template_svg(_SVG)  # panel text only clipped by the crop


def test_clean_crops_viewbox_and_size_to_drawing() -> None:
    out = _clean_template_svg(_SVG)
    assert 'viewBox="40 128 527 372"' in out
    assert 'width="527" height="372"' in out
    assert 'viewBox="0 0 792 612"' not in out


def test_clean_handles_empty() -> None:
    assert _clean_template_svg("") == ""
