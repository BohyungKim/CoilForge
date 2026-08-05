"""Phase E: the drain-pan option reaching the check, the Terra V guard, the size guard.

The three failures these pin all look identical in the UI — a width appears and a verdict
is rendered — so none of them would be caught by looking at the screen.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

pytest.importorskip("yaml")

from coilforge.checklist.mapping import _FAMILY_FROM_UNIT, _install_widths  # noqa: E402
from coilforge.compatibility.mechanical_fit import (  # noqa: E402
    _drain_pan_row,
    build_mechanical_fit_report,
    evaluate_drain_pan_fit,
)


def _coil(tag, coil_type, *, size="012", family="TERRA H", cd=3.75, option=None):
    return {
        "tag": tag, "coil_type": coil_type, "product_type": family, "unit_size": size,
        "finned_height": 20.0, "finned_length": 30.0, "rows": 4, "circuits": 1,
        "suction_conn_size": 0.875, "conn_size": 0.875, "drain_pan_option": option,
    }


# --------------------------------------------------------------------------- #
# E1 -> E2: the option now reaches the lookup
# --------------------------------------------------------------------------- #
def test_a_terra_h_option_resolves_a_width_that_used_to_be_unreachable():
    assert _drain_pan_row("TERRA_H", "012", None) is None, "no option -> still blocked"
    row = _drain_pan_row("TERRA_H", "012", "D1")
    assert row, "with the option read from the model code, R-077 resolves"
    assert any(isinstance(v, (int, float)) for v in row.values())


def test_the_option_changes_the_width_rather_than_being_decorative():
    widths = {
        opt: _drain_pan_row("TERRA_H", "012", opt) for opt in ("D1", "D2", "D3")
    }
    distinct = {tuple(sorted(w.items())) for w in widths.values() if w}
    assert len(distinct) > 1, (
        "if every D-option gave the same width, reading it off the model code would be "
        "pointless and a mis-parse would be invisible"
    )


# --------------------------------------------------------------------------- #
# E3: the Terra V guard, at BOTH callers
# --------------------------------------------------------------------------- #
def test_terra_v_never_borrows_the_terra_h_width_in_the_lookup():
    assert _drain_pan_row("TERRA_V", "072", "D1") is None
    assert _drain_pan_row("TERRA_V", "072", None) is None


def test_terra_v_never_borrows_the_terra_h_width_in_the_checklist_path():
    """The dangerous caller: this number is written into the .xlsx filed with the order."""
    assert _FAMILY_FROM_UNIT["TERRA V"] == "TERRA_V", (
        "folding TERRA V onto coarse TERRA is the route around the guard"
    )
    assert _install_widths("TERRA V", "072", "D1") == (None, None)
    # Terra H with the same option DOES resolve -- proving the guard is Terra-V-specific
    # and did not simply break the feature for everyone.
    assert _install_widths("TERRA H", "012", "D1") != (None, None)


def test_terra_v_gets_a_reason_it_can_act_on_rather_than_an_impossible_instruction():
    result = evaluate_drain_pan_fit(
        product_family="TERRA_V", unit_size="072", this_cd=3.75, partner_cd=3.75,
        partner_tag="RHHGRC-1", installed_on_drain_pan=True, drain_pan_option="D1",
    )
    assert result.verdict == "CANNOT_EVALUATE"
    assert "keyed by unit size" in result.detail
    assert "provide the drain-pan option" not in result.detail, (
        "Terra V's pan is size-keyed, so telling the engineer to supply an option is "
        "advice that can never be followed"
    )


def test_terra_h_still_gets_the_option_message_when_the_code_was_unreadable():
    result = evaluate_drain_pan_fit(
        product_family="TERRA_H", unit_size="012", this_cd=3.75, partner_cd=3.75,
        partner_tag="RHHGRC-1", installed_on_drain_pan=True, drain_pan_option=None,
    )
    assert result.verdict == "CANNOT_EVALUATE"
    assert "D1/D2/D3" in result.detail


def test_terra_h_pair_now_produces_an_actual_verdict():
    report = build_mechanical_fit_report(
        [_coil("CDXC-1", "DX", option="D1"), _coil("RHHGRC-1", "HGRH", option="D1")],
        installed_on_drain_pan=True,
    )
    verdicts = {c.tag: c.drain_pan.verdict for c in report.coils}
    assert set(verdicts.values()) <= {"PASS", "FAIL"}, (
        f"Terra INSTALL FIT should now evaluate, got {verdicts}"
    )


# --------------------------------------------------------------------------- #
# E4: partner size mismatch degrades EVERYTHING keyed by size
# --------------------------------------------------------------------------- #
def test_a_pair_detected_at_different_sizes_withholds_every_size_keyed_verdict():
    report = build_mechanical_fit_report(
        [
            _coil("CDXC-1", "DX", size="012", option="D1"),
            _coil("RHHGRC-1", "HGRH", size="024", option="D1"),
        ],
        installed_on_drain_pan=True,
    )
    for coil in report.coils:
        assert coil.width.verdict == "CANNOT_EVALUATE", coil.tag
        assert coil.height.verdict == "CANNOT_EVALUATE", coil.tag
        # The original plan degraded width/height only. drain_pan reads the same
        # unit_size through the same lookup, so a live PASS here would be standing on
        # exactly the value we just declared untrustworthy.
        assert coil.drain_pan.verdict == "CANNOT_EVALUATE", coil.tag


def test_the_size_conflict_note_states_both_sizes_and_picks_neither():
    report = build_mechanical_fit_report(
        [
            _coil("CDXC-1", "DX", size="012"),
            _coil("RHHGRC-1", "HGRH", size="024"),
        ],
        installed_on_drain_pan=True,
    )
    note = report.coils[0].note or ""
    assert "012" in note and "024" in note, (
        "the system cannot know which detection failed; quietly choosing one would be "
        "the guess this guard exists to prevent"
    )
    assert "model code" in note


def test_a_matching_pair_is_untouched_by_the_guard():
    report = build_mechanical_fit_report(
        [_coil("CDXC-1", "DX", size="012"), _coil("RHHGRC-1", "HGRH", size="012")],
        installed_on_drain_pan=True,
    )
    assert all(c.note is None for c in report.coils)
    assert all(c.width.verdict != "CANNOT_EVALUATE" for c in report.coils)


def test_an_unpaired_coil_is_not_flagged_for_a_size_conflict():
    report = build_mechanical_fit_report(
        [_coil("CDXC-1", "DX", size="012")], installed_on_drain_pan=True
    )
    assert report.coils[0].note is None
    assert report.coils[0].width.verdict != "CANNOT_EVALUATE"
