"""DX RH Header 1 = horizontal mirror of the LH seed; activated for rendering."""

from __future__ import annotations

import sys
import xml.dom.minidom
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.services.template_selection import link_drawing_template  # noqa: E402
from coilforge.template_population.catalog import get_template_entry  # noqa: E402
from coilforge.template_population.slot_population import (  # noqa: E402
    populate_template_slots,
)

REPO = Path(__file__).resolve().parents[1]
RH_SVG = REPO / "templates/drawing/coilmaster/dx/coilmaster_dx_rh_header1/template.svg"


def test_rh_template_is_active_and_mirrored() -> None:
    entry = get_template_entry("coilmaster_dx_rh_header1")
    assert entry is not None
    assert entry.coil_hand == "RH"
    assert entry.status == "active_review_aid"
    assert entry.generation_allowed is True
    assert entry.reference_status == "mirrored_from_seeded_pair_review_required"


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


def test_dx_rh_selection_links_and_renders() -> None:
    out = link_drawing_template(
        coil_type="DX",
        ez_json={"Geometry": {"NumCircuits": 1, "CoilHand": 0,
                              "Headers": [{"ID": 1, "IsSupply": True}]}},
    )
    assert out["template_id"] == "coilmaster_dx_rh_header1"
    assert out["generation_allowed"] is True

    result = populate_template_slots(
        "coilmaster_dx_rh_header1",
        {"slot.CD": 5.5, "slot.HDx1": 4.5, "slot.O2": 2, "slot.FH": 12},
    )
    assert result.svg and "5.5" in result.svg
    assert result.metadata["template_population_status"].startswith("generated")
