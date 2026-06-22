"""DX RH Header 1 is seeded from its own real EZ drawing PDF (2026-06-21).

It was previously a horizontal mirror of the LH seed, but mirroring moved cleaned
dimension callouts off their leader lines, so every hand is now seeded from its own
PDF. The `mirror.py` helper is retained as a pure utility but no longer activates a
template -- and must never be run against a live seeded bucket, since create_mirror
writes into the bucket dir and would overwrite the real seed.
"""

from __future__ import annotations

import sys
import xml.dom.minidom
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.services.template_selection import link_drawing_template  # noqa: E402
from coilforge.template_population.catalog import get_template_entry  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RH_SVG = REPO / "templates/drawing/coilmaster/dx/coilmaster_dx_rh_header1/template.svg"


def test_rh_header1_is_seeded_active() -> None:
    # The RH bucket is now a real seed (not a disabled mirror).
    entry = get_template_entry("coilmaster_dx_rh_header1")
    assert entry is not None
    assert entry.coil_hand == "RH"
    assert entry.status == "active_review_aid"
    assert entry.generation_allowed is True
    assert entry.reference_status != "mirrored_from_seeded_pair_review_required"


def test_rh_svg_is_valid_review_aid() -> None:
    xml.dom.minidom.parse(str(RH_SVG))  # raises if malformed
    svg = RH_SVG.read_text(encoding="utf-8")
    assert "coilmaster_dx_rh_header1" in svg
    assert "coilmaster_dx_lh_header1" not in svg  # identity fully rewritten
    assert "REVIEW AID - NOT FOR MANUFACTURING" in svg


def test_mirror_helper_is_pure_and_non_destructive() -> None:
    # The mirror helper is retained as a pure utility. mirror_svg returns a new
    # string (no disk writes); id derivation is deterministic. We deliberately do
    # NOT call create_rh_mirror here -- it writes into the live RH bucket dir and
    # would clobber the real seed.
    from coilforge.template_population.mirror import _opposite_hand_id, mirror_svg

    lh_svg = (REPO / "templates/drawing/coilmaster/dx/coilmaster_dx_lh_header1"
              / "template.svg").read_text(encoding="utf-8")
    mirrored = mirror_svg(lh_svg)
    assert mirrored != lh_svg
    xml.dom.minidom.parseString(mirrored.replace("{{", "0").replace("}}", ""))
    assert _opposite_hand_id("coilmaster_dx_lh_header1") == "coilmaster_dx_rh_header1"
    assert _opposite_hand_id("coilmaster_cwc_rh") == "coilmaster_cwc_lh"


def test_dx_rh_selection_links_and_is_generation_allowed() -> None:
    # Selection classifies the coil to the RH bucket, which is now seeded and active.
    out = link_drawing_template(
        coil_type="DX",
        ez_json={"Geometry": {"NumCircuits": 1, "CoilHand": 0,
                              "Headers": [{"ID": 1, "IsSupply": True}]}},
    )
    assert out["template_id"] == "coilmaster_dx_rh_header1"
    assert out["generation_allowed"] is True
