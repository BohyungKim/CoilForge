"""Critical-field tiering (John 2026-09-22).

The rows a drawing cannot be trusted without get a stronger highlight than an ordinary
blank and are editable in place: dimensions CD / CH / HD / HDx / S / I (every header
index), and the input levers product line / unit size / hand / connection sizes /
coil type. O and R stay standard (John chose the base set, not base + O/R).

``criticality`` is a COMPUTED field, like ``slot``: the model is built at twelve call
sites, and a forgotten constructor argument would silently demote a row.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.drawing.parameters import DrawingParameter  # noqa: E402
from coilforge.services.drawing_param_resolver import (  # noqa: E402
    CRITICAL_FILL_KEYS,
    build_manual_fill_plan,
    criticality_for_param_key,
)

_APP_JS = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
_CSS = (ROOT / "web" / "style.css").read_text(encoding="utf-8")


def _param(key: str) -> DrawingParameter:
    return DrawingParameter(
        key=key, label=key, mode="blocked", status="review_required", review_required=True
    )


def test_criticality_is_computed_serialized_and_not_settable():
    assert _param("CD").model_dump()["criticality"] == "critical"
    with pytest.raises(Exception):
        DrawingParameter(
            key="CD", label="CD", mode="default", status="review_required",
            review_required=True, criticality="standard",
        )


def test_critical_set_is_exactly_the_owner_list():
    critical = ["CD", "CH", "HD", "HDx1", "S", "I", "S2", "I3", "HD4"]
    standard = ["O", "R", "O2", "R3", "BF", "TF", "HF", "RF", "SL", "ZD", "ZD2"]
    for key in critical:
        assert criticality_for_param_key(key) == "critical", key
    for key in standard:
        assert criticality_for_param_key(key) == "standard", key


def test_fill_items_carry_the_critical_flag():
    td = {
        "extracted": {"coil_category": "HWC", "hand": "LH"},
        "svg": "",
        "review_items": ["missing_input:application", "missing_input:rows"],
    }
    items = {i.key: i for i in build_manual_fill_plan(td).items}
    for key in ("product_type", "unit_size", "coil_hand", "inlet_conn_size", "outlet_conn_size"):
        assert items[key].critical is True, key
    assert items["application"].critical is False
    assert items["rows"].critical is False
    assert {"coil_hand", "product_type", "unit_size"} <= CRITICAL_FILL_KEYS


def test_the_registry_preview_gate_is_untouched():
    """`required` is the PREVIEW gate ({CD, BF, TF, CH}) — criticality is a separate axis."""
    from coilforge.drawing.parameters import REQUIRED_PREVIEW_PARAMETER_KEYS

    assert set(REQUIRED_PREVIEW_PARAMETER_KEYS) == {"CD", "BF", "TF", "CH"}


# --- frontend -------------------------------------------------------------------
def _fn(name: str) -> str:
    return _APP_JS.split(f"function {name}(")[1].split("\nfunction ")[0]


def test_blank_critical_rows_outrank_blank_rows_and_are_editable_in_place():
    row = _fn("renderParameterRow")
    assert '!hasValue && parameter.criticality === "critical" ? " dc-control--critical-empty"' in row
    assert 'state.manualDrawingMode || criticalEmpty ? "" : "readonly"' in row
    assert "data-inline-reason-for=" in row


def test_inline_edit_needs_a_reason_before_it_derives():
    """The value commit only OPENS the reason field; the reason commit derives."""
    delegation = _APP_JS.split("(function initDrawingParamDelegation()")[1].split("})();")[0]
    value_step = delegation.split('target.matches("input[data-critical-inline]")')[1].split(
        'target.matches(".dc-inline-reason")'
    )[0]
    assert "deriveCoilDrawing(" not in value_step
    reason_step = delegation.split('target.matches(".dc-inline-reason")')[1]
    assert "if (!reasonText || value === null || !td) return;" in reason_step
    assert "override_reason: reasonText" in reason_step


def _token_block(selector: str) -> set[str]:
    block = _CSS.split(selector, 1)[1].split("}", 1)[0]
    return set(re.findall(r"var\((--[a-z0-9-]+)", block))


def _defined_in(block_selector: str) -> set[str]:
    block = _CSS.split(block_selector, 1)[1].split("}", 1)[0]
    return set(re.findall(r"(--[a-z0-9-]+)\s*:", block))


def test_critical_styles_use_only_tokens_defined_in_both_themes():
    """Dark theme is token-driven; an undefined token silently falls back to white."""
    light = _defined_in(":root {")
    dark = _defined_in('[data-theme="dark"] {')
    for selector in (
        ".dc-control.dc-control--critical-empty {",
        ".dc-dimension-row .dc-dimension-critical {",
        ".manual-fill-row.is-critical .manual-fill-key {",
        ".coil-drawing-picker.is-critical {",
        ".checklist-adopt-bar {",
    ):
        used = _token_block(selector)
        assert used, selector
        assert used <= light and used <= dark, (selector, used - (light & dark))
