"""The Drawing Parameters panel joins the Coil Checklist by SLOT, not by name.

John reviews the drawing-parameter panel constantly and was scrolling down to the
checklist comparison table to line the two up by eye. The panel now shows each
dimension's disagreement inline — which only works if both sides agree on which
dimension a row IS, and they do not agree by name: the panel's logical ``O2`` is the
sheet's ``O4``, while the sheet's own ``O2`` is the panel's ``O``. Joining by name would
put the red flag one row off, which is worse than showing nothing.

``DrawingParameter.slot`` is the shared identity. It is COMPUTED from ``key`` rather
than passed in, because the model is constructed at a dozen call sites across three
modules and a constructor argument would eventually be forgotten at one of them.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.checklist.mapping import _dim_slot
from coilforge.checklist.overrides import param_slot
from coilforge.drawing.parameters import DrawingParameter
from coilforge.services.drawing_param_resolver import (
    EXTRA_DRAWING_PARAMS,
    PARAM_TO_SLOT,
    slot_for_param_key,
)

_APP_JS = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(
    encoding="utf-8"
)


def _param(key: str) -> DrawingParameter:
    return DrawingParameter(
        key=key, label=key, mode="default", status="review_required", review_required=True
    )


# --- the join key -----------------------------------------------------------
def test_the_panel_key_and_the_sheet_label_disagree_about_which_dim_they_name():
    """The collision that makes a name join wrong — pinned so it can't be forgotten."""
    assert slot_for_param_key("O2") == "slot.O4"   # panel: header assembly 2
    assert _dim_slot("O2") == "slot.O2"            # sheet: parity id 2
    assert slot_for_param_key("O") == "slot.O2"    # ...which is the panel's bare O
    assert slot_for_param_key("S2") == "slot.S3"
    assert _dim_slot("S1") == "slot.S1" == slot_for_param_key("S")


def test_every_panel_key_resolves_to_a_slot_except_the_ones_with_none():
    for key in (*PARAM_TO_SLOT, *EXTRA_DRAWING_PARAMS):
        assert _param(key).slot == PARAM_TO_SLOT.get(key, _param(key).slot)
        assert _param(key).slot is not None, key
    for n in (2, 3, 4):
        for base in ("I", "S", "O", "R", "HD"):
            assert _param(f"{base}{n}").slot is not None, f"{base}{n}"
    for key in ("ZD", "ZD2", "ZD3"):
        assert _param(key).slot is None, key


def test_the_model_and_the_override_path_answer_identically():
    """One bridge, three consumers. A second implementation would mis-anchor flags."""
    keys = [
        *PARAM_TO_SLOT, *EXTRA_DRAWING_PARAMS, "ZD", "ZD2",
        *[f"{b}{n}" for b in ("I", "S", "O", "R", "HD") for n in (2, 3, 4)],
    ]
    for key in keys:
        assert param_slot(key) == slot_for_param_key(key) == _param(key).slot, key


def test_slot_is_serialized_so_the_browser_can_join_on_it():
    dumped = _param("S2").model_dump()
    assert dumped["slot"] == "slot.S3"


def test_slot_cannot_be_set_by_a_caller():
    """Computed, so no construction site can disagree with the bridge."""
    import pytest

    with pytest.raises(Exception):
        DrawingParameter(
            key="S", label="S", mode="default", status="review_required",
            review_required=True, slot="slot.WRONG",
        )


# --- frontend invariants (source-level, like tests/test_ccsi_field_map.py) ---
def test_the_panel_joins_on_slot_and_never_on_the_key():
    assert "function checklistEntryFor(parameter)" in _APP_JS
    assert "bySlot.get(parameter.slot)" in _APP_JS
    assert "state.checklistBySlot.get(activeCoilTag())" in _APP_JS


def test_verdicts_are_kept_per_coil_so_colours_cannot_bleed():
    """A flat store kept the previous coil's green/red after a coil switch."""
    assert "ccsiVerdictsByTag" in _APP_JS
    assert "state.ccsiVerdicts[" not in _APP_JS, "the flat per-session store is gone"
    assert "state.checklistBySlot = null" in _APP_JS, "a new analyze must drop old verdicts"


def test_a_checklist_match_earns_no_styling():
    """Two implementations agreeing is evidence, not approval — green stays CCSI's."""
    view = _APP_JS.split("function checklistRowView(")[1].split("\nfunction ")[0]
    assert 'verdict === "mismatch"' in view
    assert "dc-control--match" not in view


def test_only_an_unexplained_disagreement_is_painted_red():
    view = _APP_JS.split("function checklistRowView(")[1].split("\nfunction ")[0]
    for verdict in ("overridden", "missing_one"):
        block = view.split(f'entry.verdict === "{verdict}"')[1].split("if (")[0]
        assert "dc-control--divergence" not in block, verdict


def test_border_precedence_puts_the_blank_first_and_the_checklist_before_ccsi():
    """One border class wins; the order encodes which problem is bigger."""
    assert (
        "const borderClass = emptyControl || chkView.controlClass || compareClass;"
        in _APP_JS
    )


def test_staleness_is_an_explicit_signal_not_a_value_comparison():
    """The checklist resolves its OWN product line, so the two CoilForge numbers can
    differ permanently — a value-difference staleness rule would hide the badge forever
    on exactly the coils being investigated."""
    assert "state.checklistRefillPending" in _APP_JS
    assert "checklist re-running" in _APP_JS
