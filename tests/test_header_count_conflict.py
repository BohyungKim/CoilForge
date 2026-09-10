"""Header count contradicted by the stated connections per header.

`circuits` IS the header count on the drawing path (`header_type = f"Header {circuits}"`
in pdf_to_template_drawing, matched as an exact string by catalog._header_matches), and
when nothing states it it falls to `or 1` with no flag of any kind. Project 3095 is that
failure: every coil block states `Qty Conn. / Header 2` while `Coil Style: Dual Face
Split` went unparsed, so the reheat coils drew as Header 1 and lost a header column.

Connections-per-header is a DIFFERENT quantity from header count, so it is read only to
raise the question — never to answer it. These tests pin that: the flag labels, and
nothing else about the drawing moves.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.submittal.extract import SanitizedSubmittalLine  # noqa: E402
from coilforge.submittal.pdf_intake import (  # noqa: E402
    _candidate_from_cover_row,
    _CoverRow,
)
from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    _flag_header_count_conflict,
    _template_header_context_from_candidate,
)


def _result(circuits, category="HGRH", **over):
    result = {
        "svg": "<svg/>",
        "template_id": "coilmaster_hgrh_rh_header1",
        "slot_values": {"slot.CD": 3.75, "slot.S1": 3.25},
        "extracted": {"coil_category": category, "circuits": circuits, "tag": "RHHGRC-1"},
    }
    result.update(over)
    return result


# --- the 3095 case -----------------------------------------------------------
def test_stated_connections_exceeding_the_read_circuits_is_flagged():
    result = _flag_header_count_conflict(_result(1), {"qty_conn_per_header": 2})
    assert result["header_count_conflict"] is True
    review = result["header_count_review"]
    assert "2 connections per header" in review
    assert "Header 1" in review, review


def test_the_flag_changes_no_value_and_no_template():
    """It labels. A guard that quietly repaired the count would be inventing a header."""
    before = _result(1)
    after = _flag_header_count_conflict(_result(1), {"qty_conn_per_header": 2})
    assert after["slot_values"] == before["slot_values"]
    assert after["template_id"] == before["template_id"]
    assert after["extracted"]["circuits"] == 1


def test_agreement_is_silent():
    result = _flag_header_count_conflict(_result(2), {"qty_conn_per_header": 2})
    assert "header_count_conflict" not in result
    # ...but the stated value is still stamped, so /derive can round-trip it.
    assert result["qty_conn_per_header_stated"] == 2


def test_more_circuits_than_connections_is_not_this_defect():
    """Only the understated direction is suspect — the other way round is ordinary
    geometry (a Terra V HGRH whose circuit count exceeds its connections per header is
    already handled by the R-052 blanking rules)."""
    result = _flag_header_count_conflict(_result(6), {"qty_conn_per_header": 2})
    assert "header_count_conflict" not in result


def test_nothing_stated_flags_nothing():
    for ctx in ({}, {"qty_conn_per_header": None}, {"qty_conn_per_header": ""}, None):
        result = _flag_header_count_conflict(_result(1), ctx)
        assert "header_count_conflict" not in result
        assert "qty_conn_per_header_stated" not in result


# --- water coils are excluded by construction --------------------------------
def test_water_coils_are_not_a_contradiction():
    """A water coil's circuits=1 is not a reading at all: the water branch in
    `_template_header_context_from_candidate` forces it per the 1HD-only MVP taxonomy.
    Flagging it would fire on every CWC/HWC with two connections and train the banner
    to be ignored."""
    for category in ("CWC", "HWC"):
        result = _flag_header_count_conflict(
            _result(1, category=category), {"qty_conn_per_header": 2}
        )
        assert "header_count_conflict" not in result, category


def test_a_blocked_coil_with_no_drawing_is_left_alone():
    result = _flag_header_count_conflict(
        _result(1, svg=None), {"qty_conn_per_header": 2}
    )
    assert "header_count_conflict" not in result


# --- the value reaches the flag from a real candidate ------------------------
def test_the_submittal_stated_connections_reach_the_context():
    """`Qty Conn. / Header` was extracted all along (pdf_intake QUANTITY_CONNECTIONS_
    PER_HEADER) but the drawing path never looked at it. This pins the new wire."""
    candidate = _candidate_from_cover_row(
        _CoverRow(
            page_number=1, row_number=1, qty=1, tag="RHHGRC-1",
            item="HGRC Reheat", model="TV_B_012", handing="RH",
        ),
        source_id="TEST", index=1,
        detail_lines=(
            SanitizedSubmittalLine(
                source_key="QUANTITY_CONNECTIONS_PER_HEADER", source_value="2",
                line_number=1, source_page=5,
            ),
        ),
    )
    ctx = _template_header_context_from_candidate(candidate)
    assert str(ctx["qty_conn_per_header"]) in ("2", "2.0")
    # No Coil Style stated at all -> circuits falls to 1 -> the conflict is real.
    assert ctx["circuits"] == 1
    result = _flag_header_count_conflict(_result(ctx["circuits"]), ctx)
    assert result["header_count_conflict"] is True
