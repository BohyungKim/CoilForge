"""Circuit count derived from the 'Coil Style' prose.

Real submittals state the circuit count only inside the Coil Style description, e.g.
"Coil Style: Interlaced 2 Circuits" — there is no discrete "Circuits: 2" cell. Without
parsing it, multi-circuit coils silently default to circuits=1 and never surface their
second/Nth header in the Drawing Parameters panel. These tests cover the parser and the
intake derivation (inferred -> review-required; explicit label still wins).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.submittal.extract import SanitizedSubmittalLine  # noqa: E402
from coilforge.submittal.pdf_intake import (  # noqa: E402
    _candidate_from_cover_row,
    _circuits_from_coil_style,
    _CoverRow,
)


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def test_numeric_circuit_phrasings() -> None:
    assert _circuits_from_coil_style("Interlaced 2 Circuits") == 2
    assert _circuits_from_coil_style("2-Circuit") == 2
    assert _circuits_from_coil_style("3 Circuit") == 3
    assert _circuits_from_coil_style("Intertwined 4 Circuits") == 4


def test_word_circuit_phrasings() -> None:
    assert _circuits_from_coil_style("Dual Circuit") == 2
    assert _circuits_from_coil_style("Single Circuit") == 1
    assert _circuits_from_coil_style("Triple Circuit") == 3
    assert _circuits_from_coil_style("Quad Circuit") == 4


def test_word_count_on_any_circuiting_descriptor() -> None:
    """The count word attaches to whichever descriptor the document uses.

    Project 3095 writes "Dual Face Split" (HGRH) and "Dual Interlaced" (DX) with the
    count as a word and no literal "Circuit" on the line. Gating the word map on the
    substring "circuit" read those as no-count, so they fell to circuits=1 and drew as
    Header 1 — RHHGRC-1's whole second header column went missing. R-086 names both
    spellings itself: DX "Interlaced N Circuits", HGRH "Face Split N Circuits".
    """
    assert _circuits_from_coil_style("Dual Face Split") == 2
    assert _circuits_from_coil_style("Dual Interlaced") == 2
    assert _circuits_from_coil_style("Single Face Split") == 1
    assert _circuits_from_coil_style("Triple Intertwined") == 3


def test_no_count_is_never_guessed() -> None:
    # A bare "Intertwined"/"Interlaced" with no number must NOT be assumed to be 2.
    assert _circuits_from_coil_style("Intertwined") is None
    assert _circuits_from_coil_style("Interlaced") is None
    assert _circuits_from_coil_style("Standard") is None
    # Widening the descriptor set must not widen the never-guess rule: "Face Split"
    # alone still states no count.
    assert _circuits_from_coil_style("Face Split") is None
    # A circuit-word without the word "circuit" present is not a false positive.
    assert _circuits_from_coil_style("Single Row") is None
    assert _circuits_from_coil_style("") is None
    assert _circuits_from_coil_style(None) is None


def test_the_count_word_must_sit_against_the_descriptor() -> None:
    """Adjacency is what keeps the widened vocabulary from over-reading.

    "Single Row Interlaced" carries both a count word and a descriptor, but the Single
    counts ROWS. Matching them across the string would turn a row count into a circuit
    count — i.e. into a header count — which is the exact failure mode being fixed,
    only inverted.
    """
    assert _circuits_from_coil_style("Single Row Interlaced") is None
    assert _circuits_from_coil_style("Dual Row, Standard") is None


# --------------------------------------------------------------------------- #
# Intake derivation (cover-row candidate)
# --------------------------------------------------------------------------- #
def _cover_row() -> _CoverRow:
    return _CoverRow(
        page_number=1, row_number=1, qty=1, tag="CDXC-1",
        item="DXC Cooling", model="", handing="LH",
    )


def _detail(source_key: str, source_value: str) -> SanitizedSubmittalLine:
    return SanitizedSubmittalLine(
        source_key=source_key, source_value=source_value, line_number=1, source_page=12,
    )


def test_intake_derives_circuits_from_coil_style_review_required() -> None:
    candidate = _candidate_from_cover_row(
        _cover_row(), source_id="TEST", index=1,
        detail_lines=(_detail("COIL_STYLE", "Interlaced 2 Circuits"),),
    )
    fv = candidate.geometry["circuits"]
    assert fv.value == 2  # int-coerced by intake normalization
    assert fv.confidence == "inferred"
    assert fv.review_required is True


def test_face_split_reheat_coil_reaches_the_two_header_template() -> None:
    """RHHGRC-1 (project 3095), end to end: prose -> circuits -> the Header 2 bucket.

    `circuits` IS the header count on the drawing path — `pdf_to_template_drawing` mints
    `header_type = f"Header {circuits}"` and `catalog._header_matches` compares that
    string exactly — so a misread style prose silently selects a one-header template and
    the drawing loses a whole header column. Asserted through to the template id because
    that is the thing that was visibly wrong.
    """
    from coilforge.template_population.catalog import (
        TemplateSelectionRequest,
        select_drawing_template,
    )
    from coilforge.workflows.submittal_to_drawing import (
        _template_header_context_from_candidate,
    )

    candidate = _candidate_from_cover_row(
        _CoverRow(
            page_number=1, row_number=1, qty=1, tag="RHHGRC-1",
            item="HGRC Reheat", model="TV_B_012", handing="RH",
        ),
        source_id="TEST", index=1,
        detail_lines=(_detail("COIL_STYLE", "Dual Face Split"),),
    )
    ctx = _template_header_context_from_candidate(candidate)
    assert ctx["circuits"] == 2

    selection = select_drawing_template(
        TemplateSelectionRequest(
            supplier="coilmaster",
            coil_category=ctx["coil_category"],
            coil_hand=ctx["coil_hand"],
            header_type=f"Header {ctx['circuits']}",
            special_feature=None,
        )
    )
    assert selection.template_id == "coilmaster_hgrh_rh_header2"


def test_intake_no_circuit_count_leaves_circuits_unset() -> None:
    candidate = _candidate_from_cover_row(
        _cover_row(), source_id="TEST", index=1,
        detail_lines=(_detail("COIL_STYLE", "Standard"),),
    )
    assert "circuits" not in candidate.geometry  # never guessed


def test_explicit_circuits_cell_wins_over_coil_style() -> None:
    # When the PDF DOES carry an explicit Circuits cell, it is authoritative and the
    # coil-style derivation is skipped (confirmed value, not the inferred override).
    candidate = _candidate_from_cover_row(
        _cover_row(), source_id="TEST", index=1,
        detail_lines=(
            _detail("CIRCUITS", "1"),
            _detail("COIL_STYLE", "Interlaced 2 Circuits"),
        ),
    )
    fv = candidate.geometry["circuits"]
    assert fv.value == 1
    assert fv.confidence != "inferred"  # explicit label stays confirmed


# --------------------------------------------------------------------------- #
# End-to-end: circuits=2 lights up the second-header panel column
# --------------------------------------------------------------------------- #
def test_derived_circuits_surface_second_header_in_panel() -> None:
    from coilforge.services.direct_coil_drawing_pipeline import build_drawing_slots
    from coilforge.services.drawing_param_resolver import parameter_set_from_template_drawing

    candidate = _candidate_from_cover_row(
        _cover_row(), source_id="TEST", index=1,
        detail_lines=(_detail("COIL_STYLE", "Interlaced 2 Circuits"),),
    )
    circuits = candidate.geometry["circuits"].value
    assert circuits == 2

    slots, _ = build_drawing_slots(
        coil_type="DX", product_type="NOVA", unit_size="B20",
        rows=4, feeds=2, circuits=circuits, suction_conn_size=0.625,
        finned_height=12.0, finned_length=15.0,
    )
    params = parameter_set_from_template_drawing({"slot_values": slots}, circuits=circuits).parameters
    for key in ("I2", "S2", "O2", "R2", "HD2", "ZD2"):
        assert key in params, key
