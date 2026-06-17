"""DX RH Header 1 was a horizontal mirror of the LH seed. Mirror generation is now
DISABLED (John, 2026-06-17): the flip moves cleaned dimension callouts off their
leader lines. Each hand must be seeded from its own PDF, so the RH bucket is
"template not registered" (needs_pair, generation_allowed=False) until then. The
mirror SVG artwork and the `mirror.py` helper are retained for future use but no
longer activate a template."""

from __future__ import annotations

import sys
import xml.dom.minidom
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.services.template_selection import link_drawing_template  # noqa: E402
from coilforge.template_population.catalog import get_template_entry  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RH_SVG = REPO / "templates/drawing/coilmaster/dx/coilmaster_dx_rh_header1/template.svg"


def test_rh_mirror_template_is_disabled_not_registered() -> None:
    # Mirror generation is forbidden: the RH bucket exists but is not active.
    entry = get_template_entry("coilmaster_dx_rh_header1")
    assert entry is not None
    assert entry.coil_hand == "RH"
    assert entry.status == "needs_pair"
    assert entry.generation_allowed is False
    assert entry.reference_status != "mirrored_from_seeded_pair_review_required"


def test_rh_svg_is_valid_and_has_flip_transform() -> None:
    import re

    xml.dom.minidom.parse(str(RH_SVG))  # raises if malformed
    svg = RH_SVG.read_text(encoding="utf-8")
    assert re.search(r"matrix\(-1 0 0 1 [\d.]+ 0\)", svg)  # horizontal mirror
    assert "coilmaster_dx_rh_header1" in svg
    assert "coilmaster_dx_lh_header1" not in svg  # identity fully rewritten


def test_mirror_helper_reusable_for_any_seed(tmp_path) -> None:
    # The helper regenerates the RH pair deterministically from the LH seed.
    from coilforge.template_population.mirror import create_rh_mirror, mirror_svg

    lh_svg = (REPO / "templates/drawing/coilmaster/dx/coilmaster_dx_lh_header1"
              / "template.svg").read_text(encoding="utf-8")
    mirrored = mirror_svg(lh_svg)
    assert mirrored != lh_svg
    xml.dom.minidom.parseString(mirrored.replace("{{", "0").replace("}}", ""))
    # idempotent id derivation
    assert create_rh_mirror("coilmaster_dx_lh_header1") == "coilmaster_dx_rh_header1"


def test_dx_rh_selection_links_but_is_not_generation_allowed() -> None:
    # Selection still classifies the coil to the RH bucket, but mirror generation
    # is forbidden, so generation_allowed is False (UI -> "template not registered").
    out = link_drawing_template(
        coil_type="DX",
        ez_json={"Geometry": {"NumCircuits": 1, "CoilHand": 0,
                              "Headers": [{"ID": 1, "IsSupply": True}]}},
    )
    assert out["template_id"] == "coilmaster_dx_rh_header1"
    assert out["generation_allowed"] is False
