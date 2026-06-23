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


def test_no_count_is_never_guessed() -> None:
    # A bare "Intertwined"/"Interlaced" with no number must NOT be assumed to be 2.
    assert _circuits_from_coil_style("Intertwined") is None
    assert _circuits_from_coil_style("Interlaced") is None
    assert _circuits_from_coil_style("Standard") is None
    # A circuit-word without the word "circuit" present is not a false positive.
    assert _circuits_from_coil_style("Single Row") is None
    assert _circuits_from_coil_style("") is None
    assert _circuits_from_coil_style(None) is None


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
