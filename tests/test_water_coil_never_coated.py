"""A water coil is never coated (John 2026-08-05).

Coating reaches a coil three ways in the detail-block reader — the structured table seed,
the free asterisk annotation (`*Finkote2 Epoxy Coil Coating*`) and the "Coil Coating:
<value>" label pattern — and the blocks genuinely bleed into each other, so a CWC/HWC/PHWC
coil could pick up its neighbour's coating. Per John that value is physically impossible,
so it is suppressed rather than shown.

Closes the roadmap's open "물코일 coating 노트" question: R-080 (DX) / R-081 (HGRH) stay
water-free BY DESIGN, not as an unclosed gap.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from coilforge.submittal.pdf_intake import (  # noqa: E402
    _WATER_COIL_FORMATS,
    _drop_coating_from_water_coil,
    normalize_source_key,
)
from coilforge.workflows.submittal_to_drawing import _engine_drawing_notes  # noqa: E402

COATING_KEY = normalize_source_key("COIL_COATING")
WEIGHT_KEY = normalize_source_key("COIL_WEIGHT")


def _block():
    return {COATING_KEY: "Finkote2 Epoxy Coil Coating", WEIGHT_KEY: 32.94}


@pytest.mark.parametrize("coil_format", sorted(_WATER_COIL_FORMATS))
def test_water_coil_block_never_keeps_a_coating(coil_format):
    extracted = _block()
    _drop_coating_from_water_coil(extracted, coil_format)
    assert COATING_KEY not in extracted
    # Only the coating goes -- the block's other readings are untouched.
    assert extracted[WEIGHT_KEY] == 32.94


@pytest.mark.parametrize("coil_format", ["dx", "condensing"])
def test_coatable_coils_are_unaffected(coil_format):
    extracted = _block()
    _drop_coating_from_water_coil(extracted, coil_format)
    assert extracted[COATING_KEY] == "Finkote2 Epoxy Coil Coating"


def test_unidentified_block_is_left_alone():
    """Only suppress where the coil is KNOWN to be a water coil; an unresolved block keeps
    its reading rather than losing data on a guess."""
    extracted = _block()
    _drop_coating_from_water_coil(extracted, None)
    assert extracted[COATING_KEY] == "Finkote2 Epoxy Coil Coating"


def test_a_manual_coating_on_a_water_coil_is_deliberately_still_allowed():
    """DELIBERATE ASYMMETRY (John 2026-08-05) -- do not "fix" this.

    Automatic EXTRACTION never gives a water coil a coating: a reading that lands there
    came from a neighbouring block, and the coil cannot be coated. But an engineer typing
    a coating into the Coating field is an explicit human decision, and CoilForge does not
    override those -- the manual-fill contract everywhere else is that the human wins and
    the value stays review-required.

    So the drawing note still renders for a hand-entered coating. John was asked and chose
    to leave it: refusing an engineer's explicit entry is a different class of behaviour
    from declining to infer one.
    """
    from coilforge.workflows.submittal_to_drawing import _coating_drawing_note

    assert _coating_drawing_note("HERESITE") == "HERESITE COATING REQUIRED"


@pytest.mark.parametrize("coil_category", ["CWC", "HWC"])
def test_water_coil_gets_no_coating_note_even_if_a_coating_is_forced(coil_category):
    """Belt and braces: even if a coating value somehow reaches the engine for a water
    coil, R-080/R-081 are DX/HGRH-scoped so no "Do Not Coat..." note is assembled. The
    absence is the confirmed rule now, not an unclosed gap."""
    ctx = {
        "coil_category": coil_category,
        "product_type": "NOVA",
        "unit_size": "B20",
        "rows": 4,
        "circuits": 1,
        "coating": "HERESITE",
    }
    notes = _engine_drawing_notes(ctx)
    assert not [note for note in notes if "Do Not Coat" in note]
