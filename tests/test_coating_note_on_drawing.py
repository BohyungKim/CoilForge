"""The coil's ACTUAL coating is printed on the drawing (John 2026-08-05).

Three seeded templates were built from coated reference drawings, so the reference's own
coating name was baked into the artwork and printed on every coil in those buckets:

    coilmaster_dx_rh_header2    -> "ELECTROFIN COATING REQUIRED"
    coilmaster_hgrh_rh_header1  -> "ELECTROFIN COATING REQUIRED"
    coilmaster_hgrh_rh_header3  -> "FINKOTE 2 COATING REQUIRED"

An uncoated coil got a coating instruction it must not have, and a HERESITE coil was told
to use ElectroFin. The text is now `slot.COATING_NOTE`, filled per coil.

Covers John's three scenarios: a coated project, a non-coated project, and a manual
coating update reaching the drawing.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    _apply_coating_note_to_drawing,
    _coating_drawing_note,
    derive_coil_template_drawing,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPO_ROOT / "templates" / "drawing" / "coilmaster"

SLOTTED_TEMPLATES = (
    "dx/coilmaster_dx_rh_header2",
    "hgrh/coilmaster_hgrh_rh_header1",
    "hgrh/coilmaster_hgrh_rh_header3",
)

NOTE_RE = re.compile(
    r'<tspan\b[^>]*id="coilforge-coating-note"[^>]*>(.*?)</tspan>', re.DOTALL
)


def _coating_note_in(svg: str) -> str | None:
    match = NOTE_RE.search(svg or "")
    return None if match is None else match.group(1).strip()


# --------------------------------------------------------------------------- #
# The templates themselves no longer hardcode a coating name
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("template", SLOTTED_TEMPLATES)
def test_template_no_longer_hardcodes_a_coating_name(template):
    svg = (TEMPLATE_ROOT / template / "template.svg").read_text(encoding="utf-8")
    assert "ELECTROFIN COATING REQUIRED" not in svg
    assert "FINKOTE 2 COATING REQUIRED" not in svg
    assert "{{slot.COATING_NOTE}}" in svg


@pytest.mark.parametrize("template", SLOTTED_TEMPLATES)
def test_slot_is_registered_in_the_slot_map(template):
    """`populate_template_slots` substitutes ONLY slot_ids listed in slot_map.json, so an
    unregistered slot renders the literal `{{slot.COATING_NOTE}}` on the drawing."""
    slot_map = json.loads(
        (TEMPLATE_ROOT / template / "slot_map.json").read_text(encoding="utf-8")
    )
    ids = {slot["slot_id"] for slot in slot_map["slots"]}
    assert "slot.COATING_NOTE" in ids
    entry = next(s for s in slot_map["slots"] if s["slot_id"] == "slot.COATING_NOTE")
    # An uncoated coil legitimately has no note; a required slot would block its preview.
    assert entry["required_for_preview"] is False


# --------------------------------------------------------------------------- #
# The note text itself
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "coating,expected",
    [
        ("HERESITE", "HERESITE COATING REQUIRED"),
        ("Electrofin", "ELECTROFIN COATING REQUIRED"),
        ("FINKOTE 2", "FINKOTE 2 COATING REQUIRED"),
        # Normalized to the family it names: the submittal's own phrasing and the
        # `Coil Coating: <value>` label pattern both drag extra words along, and a
        # manufacturing instruction must not carry them.
        ("Finkote2 Epoxy Coil Coating", "FINKOTE2 COATING REQUIRED"),
        ("ElectroFin Evap Temp 45", "ELECTROFIN COATING REQUIRED"),
        ("Heresite UV", "HERESITE UV COATING REQUIRED"),
        # No known family -> keep the stated text rather than drop a real coating.
        ("Some Unknown Brand", "SOME UNKNOWN BRAND COATING REQUIRED"),
        (None, None),
        ("", None),
        ("NONE", None),
        ("Plain", None),
    ],
)
def test_coating_note_text(coating, expected):
    assert _coating_drawing_note(coating) == expected


# --------------------------------------------------------------------------- #
# Scenario 1 -- a COATED coil prints its own coating
# --------------------------------------------------------------------------- #
def test_coated_coil_prints_its_own_coating_not_the_templates():
    svg = (TEMPLATE_ROOT / "dx/coilmaster_dx_rh_header2/template.svg").read_text(
        encoding="utf-8"
    )
    result = {"svg": svg.replace("{{slot.COATING_NOTE}}", "REVIEW REQUIRED"),
              "slot_values": {}}
    _apply_coating_note_to_drawing(result, "HERESITE")
    assert _coating_note_in(result["svg"]) == "HERESITE COATING REQUIRED"
    assert result["slot_values"]["slot.COATING_NOTE"] == "HERESITE COATING REQUIRED"
    # The template's seeded coating must be gone, not merely joined by the new one.
    assert "ELECTROFIN" not in result["svg"]


# --------------------------------------------------------------------------- #
# Scenario 2 -- a NON-COATED coil prints nothing
# --------------------------------------------------------------------------- #
def test_uncoated_coil_prints_nothing_not_review_required():
    """"No coating" is a known state, not a pending decision -- so the line must be blank
    rather than the `REVIEW REQUIRED` sentinel a blank slot would otherwise render."""
    svg = (TEMPLATE_ROOT / "dx/coilmaster_dx_rh_header2/template.svg").read_text(
        encoding="utf-8"
    )
    result = {"svg": svg.replace("{{slot.COATING_NOTE}}", "REVIEW REQUIRED"),
              "slot_values": {}}
    _apply_coating_note_to_drawing(result, None)
    assert _coating_note_in(result["svg"]) == ""
    assert "COATING REQUIRED" not in result["svg"]
    assert "REVIEW REQUIRED" not in _coating_note_in(result["svg"])
    assert result["slot_values"]["slot.COATING_NOTE"] is None


def test_templates_without_a_coating_line_are_untouched():
    """19 of the 22 buckets carry no coating line at all; the helper must no-op there
    rather than inventing one."""
    svg = (TEMPLATE_ROOT / "dx/coilmaster_dx_lh_header1/template.svg").read_text(
        encoding="utf-8"
    )
    result = {"svg": svg, "slot_values": {}}
    _apply_coating_note_to_drawing(result, "HERESITE")
    assert result["svg"] == svg


# --------------------------------------------------------------------------- #
# Scenario 3 -- a MANUAL coating update reaches the drawing
# --------------------------------------------------------------------------- #
def _derive_spec(**overrides):
    spec = {
        "coil_category": "DX",
        "coil_hand": "RH",
        "tag": "CDXC-1",
        "circuits": 2,
        "rows": 4,
        "feeds": 8,
        "finned_height": 24.0,
        "finned_length": 48.0,
        "suction_conn_size": 1.375,
        "product_type": "NOVA",
        "unit_size": "B20",
        "header_type": "Header 2",
        "panel": {},
    }
    spec.update(overrides)
    return spec


@pytest.mark.parametrize(
    "hand,category,circuits",
    [("RH", "DX", 2), ("LH", "DX", 1), ("RH", "HGRH", 1), ("LH", "CWC", 1)],
)
def test_manual_coating_edit_reaches_the_rendered_drawing(hand, category, circuits):
    """The engineer edits Coating in the browser -> /derive -> the DISPLAYED drawing must
    print it. Checked on the rendered SVG, not the raw template: the template's own
    fabrication-notes block is stripped by `_strip_intruding_chrome` and clipped by the
    viewBox crop, so slotting that line alone would have printed nothing anywhere the
    engineer actually looks. Every hand/category, because the note is stamped into the
    cropped region rather than borrowed from a particular template's artwork.

    Wired into BOTH the analyze and the derive path -- an analyze-only post-process is
    exactly the TR-9 / 228d731 defect this repo has now hit twice.
    """
    plain = derive_coil_template_drawing(
        _derive_spec(coil_hand=hand, coil_category=category, circuits=circuits)
    )
    coated = derive_coil_template_drawing(
        _derive_spec(
            coil_hand=hand, coil_category=category, circuits=circuits, coating="HERESITE"
        )
    )
    assert plain.get("svg"), "no drawing rendered for this bucket"

    # Scenario 2: a non-coated coil says nothing about coating, anywhere.
    assert "COATING REQUIRED" not in plain["svg"]
    # Scenario 1 + 3: the coated coil prints its OWN coating, inside the visible region.
    assert "HERESITE COATING REQUIRED" in coated["svg"]
    assert "ELECTROFIN" not in coated["svg"], "the template's seeded coating leaked"
    assert coated["slot_values"]["slot.COATING_NOTE"] == "HERESITE COATING REQUIRED"


def test_coating_note_is_larger_than_the_tag_label():
    """It is a manufacturing instruction, so it must not read as metadata (John: 적당히
    크게). Pinned so a later style tweak cannot quietly shrink it back."""
    coated = derive_coil_template_drawing(_derive_spec(coating="HERESITE"))
    note = re.search(
        r'<text[^>]*font-size="(?P<size>[\d.]+)"[^>]*>[^<]*COATING REQUIRED</text>',
        coated["svg"],
    )
    tag = re.search(
        r'<text[^>]*font-size="(?P<size>[\d.]+)"[^>]*>Tag: [^<]*</text>', coated["svg"]
    )
    assert note and tag
    assert float(note.group("size")) > float(tag.group("size"))


def test_changing_the_coating_replaces_the_previous_note():
    """A second edit must overwrite, never append -- two coating instructions on one
    drawing is worse than the original bug."""
    svg = (TEMPLATE_ROOT / "hgrh/coilmaster_hgrh_rh_header3/template.svg").read_text(
        encoding="utf-8"
    )
    result = {"svg": svg.replace("{{slot.COATING_NOTE}}", "REVIEW REQUIRED"),
              "slot_values": {}}
    _apply_coating_note_to_drawing(result, "HERESITE")
    _apply_coating_note_to_drawing(result, "ELECTROFIN")
    assert _coating_note_in(result["svg"]) == "ELECTROFIN COATING REQUIRED"
    assert result["svg"].count("COATING REQUIRED") == 1
