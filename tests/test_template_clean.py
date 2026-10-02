"""`_clean_template_svg` — cleanup of the populated CoilMaster template to the direct-coil
view: value+label dim callouts (John 2026-06-25 "valuemap" style) + viewBox cropped to the
drawing region (clips the panel / dim table / title block / notes chrome)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.workflows.submittal_to_drawing import (
    _clean_template_svg,
    _coil_tag_for_drawing,
    _stamp_missing_drawing_tag,
)


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


def test_clean_keeps_value_and_label_on_callouts() -> None:
    out = _clean_template_svg(_SVG)
    # value + label kept together (existing drawing style)
    assert ">3.5 HD2</tspan>" in out and ">12 FH</tspan>" in out
    # blank-slot placeholder: the "REVIEW REQUIRED" sentinel never reaches the drawing,
    # the label is kept so the dim stays identified, AND the withholding is visible.
    # The bare label used to stand alone, which reads as a rendering slip rather than a
    # deliberate refusal -- on a real Terra V HGRH header-2 the SOP-withheld I3 (R-046
    # covers Supply 1 only) drew as nothing but "I3". John 2026-08-30.
    assert "REVIEW REQUIRED" not in out
    assert ">— OAL</tspan>" in out
    assert ">OAL</tspan>" not in out


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
    # geometry dimension value+label kept; DIST LIST heading + distributor entries removed
    assert ">12 FH</tspan>" in out
    assert "DIST LIST" not in out
    assert "501-" not in out and "OD:5/8" not in out


def test_clean_handles_empty() -> None:
    assert _clean_template_svg("") == ""


# Literal EZ-baked callouts (no {{slot}}): a hardcoded EZ value + EZ/bare label, as found in
# the CWC/HWC/HGRH templates. The Direct Coil label authority (John 2026-06-26) normalizes
# the LABEL only — bare I/S/O/R -> parity-indexed I1/S1/O2/R2, EZ HD1/SL1 -> HD2/SL2 — and
# keeps the EZ value (cleared only when those templates are re-seeded).
_SVG_EZ_RESIDUE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="792" height="612" viewBox="0 0 792 612">'
    '<text fill="#1c0a80" transform="matrix(1 0 -0 1 0 612)"><tspan x="1" y="-2">2.31 I</tspan></text>'
    '<text fill="#1c0a80" transform="matrix(1 0 -0 1 0 612)"><tspan x="1" y="-2">1.63 S</tspan></text>'
    '<text fill="#1c0a80" transform="matrix(1 0 -0 1 0 612)"><tspan x="1" y="-2">2.31 O</tspan></text>'
    '<text fill="#1c0a80" transform="matrix(1 0 -0 1 0 612)"><tspan x="1" y="-2">1.63 R</tspan></text>'
    '<text fill="#1c0a80" transform="matrix(1 0 -0 1 0 612)"><tspan x="1" y="-2">3.50 HD1</tspan></text>'
    '<text fill="#1c0a80" transform="matrix(1 0 -0 1 0 612)"><tspan x="1" y="-2">8.00 SL1</tspan></text>'
    '<text fill="#1c0a80" transform="matrix(1 0 -0 1 0 612)"><tspan x="1" y="-2">0.63 BF</tspan></text>'
    "</svg>"
)


def test_clean_normalizes_ez_residue_labels_keeps_values() -> None:
    out = _clean_template_svg(_SVG_EZ_RESIDUE)
    # bare EZ connection labels -> Direct Coil parity-indexed; EZ value preserved.
    assert ">2.31 I1</tspan>" in out
    assert ">1.63 S1</tspan>" in out
    assert ">2.31 O2</tspan>" in out
    assert ">1.63 R2</tspan>" in out
    # EZ header-1 forms -> Direct Coil return-header index.
    assert ">3.50 HD2</tspan>" in out
    assert ">8.00 SL2</tspan>" in out
    # already-canonical label is unchanged.
    assert ">0.63 BF</tspan>" in out
    # the bare/EZ originals are gone.
    for stale in (">2.31 I<", ">1.63 S<", ">2.31 O<", ">1.63 R<", ">3.50 HD1<", ">8.00 SL1<"):
        assert stale not in out


def _sl_svg(*callouts: str) -> str:
    body = "".join(
        f'<text fill="#1c0a80" transform="matrix(1 0 -0 1 0 612)">'
        f'<tspan x="1" y="-2">{c}</tspan></text>'
        for c in callouts
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="792" height="612" '
        f'viewBox="0 0 792 612">{body}</svg>'
    )


def test_clean_keeps_hgrh_supply_sl1_but_normalizes_cwc_sl1() -> None:
    """John 2026-07-03: the redacted HGRH supply SL1 callout must stay SL1 (its own reheat
    stub), so the two HGRH SL callouts render distinctly — 5 SL1 (supply) and 12 SL2 (return).
    CWC's lone SL1 residue still normalizes to the return SL2 (unchanged)."""
    hgrh = _clean_template_svg(_sl_svg("5 SL1", "12 SL2"), "HGRH")
    assert ">5 SL1</tspan>" in hgrh and ">12 SL2</tspan>" in hgrh
    # CWC keeps the residue->return normalization; default (no category) too.
    assert ">8.00 SL2</tspan>" in _clean_template_svg(_sl_svg("8.00 SL1"), "CWC")
    assert ">8.00 SL2</tspan>" in _clean_template_svg(_sl_svg("8.00 SL1"))


def test_clean_stamps_coil_tag_inside_crop() -> None:
    """The coil tag is cropped out of the bottom title block, so it is re-drawn top-left
    INSIDE the retained viewBox (110 19 542 473)."""
    out = _clean_template_svg(_SVG, tag="CDXC-1")
    assert ">Tag: CDXC-1</text>" in out
    # placed inside the crop's top-left corner
    assert 'x="116" y="34"' in out


def test_clean_no_tag_stamps_nothing() -> None:
    # default (no tag) and explicit None/blank -> no injected label, existing output intact.
    assert "Tag:" not in _clean_template_svg(_SVG)
    assert "Tag:" not in _clean_template_svg(_SVG, tag=None)
    assert "Tag:" not in _clean_template_svg(_SVG, tag="   ")


def test_clean_escapes_tag() -> None:
    out = _clean_template_svg(_SVG, tag="A&B<1")
    assert "Tag: A&amp;B&lt;1" in out


def test_coil_tag_for_drawing_prefers_slot_then_extract() -> None:
    assert _coil_tag_for_drawing({"slot_values": {"slot.TAG": "CDXC-1"}}) == "CDXC-1"
    # falls back to the as-built extract when the slot is absent
    assert _coil_tag_for_drawing({"extracted": {"tag": "RHHGRH-2"}}) == "RHHGRH-2"
    # nothing real -> None (so no blank 'Tag:' is drawn)
    assert _coil_tag_for_drawing({"slot_values": {}, "extracted": {}}) is None


# A minimal cropped drawing (has </svg>; no coil tag of its own).
_UNTAGGED_DRAWING_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="542" height="473" '
    'viewBox="110 19 542 473"><text><tspan>5.5 CD</tspan></text></svg>'
)


def test_stamp_missing_drawing_tag_uses_page_tag_when_drawing_untagged() -> None:
    # page.tag resolved from the cover row ("CDXC-2") while the candidate carried none, so the
    # drawing has no tag -> stamp the page tag as a visible top-left label (John's blank-tag bug).
    wf = {"template_drawing": {"svg": _UNTAGGED_DRAWING_SVG, "slot_values": {}, "extracted": {}}}
    _stamp_missing_drawing_tag(wf, "CDXC-2")
    assert ">Tag: CDXC-2</text>" in wf["template_drawing"]["svg"]


def test_stamp_missing_drawing_tag_noop_when_already_tagged() -> None:
    # the drawing already carries its tag (candidate/as-built) -> never double-stamp / override.
    wf = {
        "template_drawing": {
            "svg": _UNTAGGED_DRAWING_SVG,
            "slot_values": {"slot.TAG": "CDXC-1"},
            "extracted": {},
        }
    }
    _stamp_missing_drawing_tag(wf, "CDXC-2")
    assert "CDXC-2" not in wf["template_drawing"]["svg"]


def test_stamp_missing_drawing_tag_skips_positional_placeholder() -> None:
    # "Coil N" is the positional placeholder when no real tag exists anywhere -> never stamp it.
    wf = {"template_drawing": {"svg": _UNTAGGED_DRAWING_SVG, "slot_values": {}, "extracted": {}}}
    _stamp_missing_drawing_tag(wf, "Coil 3")
    assert "Tag:" not in wf["template_drawing"]["svg"]
