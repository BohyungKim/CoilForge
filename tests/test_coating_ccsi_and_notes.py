"""A stated coil coating reaches CCSI, the Drawing Notes and the drawing (John 2026-09-30).

"드랍다운에 매칭되는 코팅이 있으면 선택하되, 없으면 coating을 선택해주고, note section에 꼭
coating 관련 노트를 추가, 도면에도 coating 노트를 꼭 추가."

* CCSI's Coil Coating dropdown is ``Plain`` / ``AA Coating`` (re-captured live 2026-09-30). A
  coating it names is selected by name; any other stated coating selects ``AA Coating``.
* The Drawing Notes (paste field + CCSI ``#DrawingNotes``) lead with the coating's name, since
  the dropdown cannot say ElectroFin / Finkote / Heresite.
* The drawing already stamps that same text on every template (``_inject_coating_note_label``);
  the gap was the intake never recognizing the cover's "AA coil coating adder".
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ccsi.coil_data_map import _coating_option, resolve_coil_data  # noqa: E402
from coilforge.submittal.pdf_intake import _package_coating, _TextPage, coating_family  # noqa: E402
from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    _clean_template_svg,
    _coating_drawing_note,
    _engine_drawing_notes,
)

OPTIONS = ["Plain", "AA Coating"]


# ------------------------------------------------------------------ intake: AA is a coating
def test_aa_is_recognized_only_when_a_coating_word_follows() -> None:
    assert coating_family("AA Coating") == "AA"
    assert coating_family("Miscellaneous AA coil coating adder") == "AA"
    assert coating_family("AA") is None                  # a bare AA is not a coating
    assert coating_family("AA filter rack") is None


def test_the_cover_adder_wrapped_over_two_lines_is_the_package_coating() -> None:
    cover = _TextPage(page_number=2, text="SE70ERU074-\n1 Miscellaneous AA coil\ncoating adder\nVersion 1.0.0.9")
    spec = _TextPage(page_number=1, text="Provide AA coil coating adder per spec")  # before the cover
    assert _package_coating([spec, cover], cover_page=2) == "AA"
    assert _package_coating([spec], cover_page=2) is None


def test_the_drawing_note_names_aa() -> None:
    assert _coating_drawing_note("AA") == "AA COATING REQUIRED"
    assert _coating_drawing_note("AA Coating") == "AA COATING REQUIRED"


# ------------------------------------------------------------------ CCSI dropdown
def _coating_entry(value):
    sources = {"coil_coating": {"value": value, "status": "review_required"}} if value is not None else {}
    return next(e for e in resolve_coil_data(sources, coil_type="DX") if e.ccsi_id == "CoilCoating")


def test_a_coating_the_dropdown_names_is_selected_by_name() -> None:
    entry = _coating_entry("AA")
    assert entry.value == "AA Coating" and entry.reason_code == "CCSI_OK" and entry.pushable


def test_a_coating_the_dropdown_lacks_selects_the_coating_option_and_says_so() -> None:
    for stated in ("ElectroFin", "Finkote2 Epoxy Coil Coating", "HERESITE UV"):
        entry = _coating_entry(stated)
        assert entry.value == "AA Coating", stated
        assert entry.pushable
        assert "Drawing Notes" in entry.reason                 # the reviewer sees why


def test_no_coating_is_plain() -> None:
    assert _coating_entry("NONE").value == "Plain"
    absent = _coating_entry(None)
    assert absent.value == "Plain" and absent.reason_code == "CCSI_DEFAULT_PROFILE"


def test_two_coating_options_would_be_ambiguous_and_are_never_guessed() -> None:
    picked, why = _coating_option("ElectroFin", ["Plain", "AA Coating", "Epoxy Coating"])
    assert picked is None and "2 coating options" in why
    assert _coating_option("Epoxy", ["Plain", "AA Coating", "Epoxy Coating"])[0] == "Epoxy Coating"


# ------------------------------------------------------------------ Drawing Notes + drawing
_CTX = {"product_type": "NOVA", "unit_size": "B20", "coil_category": "DX", "rows": 4, "feeds": 8, "circuits": 2}


def test_the_drawing_notes_lead_with_the_coating_name() -> None:
    coated = _engine_drawing_notes({**_CTX, "coating": "ElectroFin"})
    assert coated[0] == "ELECTROFIN COATING REQUIRED"
    assert "Do Not Coat Last 5-6 inches of Distributor Extensions." in coated   # R-080 still fires
    plain = _engine_drawing_notes(_CTX)
    assert plain and not any("COATING" in n.upper() for n in plain)


def test_an_aa_coated_hgrh_gets_the_note_and_r081() -> None:
    notes = _engine_drawing_notes({**_CTX, "coil_category": "HGRH", "coating": "AA"})
    assert notes[0] == "AA COATING REQUIRED"
    assert "Do Not Coat Last 5-6 inches of Supply Stubouts." in notes


def test_the_drawing_stamps_the_same_text() -> None:
    svg = '<svg viewBox="0 0 10 10" width="10" height="10"><text>x</text></svg>'
    assert "AA COATING REQUIRED" in _clean_template_svg(svg, "DX", tag="CDXC-1", coating="AA")
    assert "COATING REQUIRED" not in _clean_template_svg(svg, "DX", tag="CDXC-1", coating=None)
