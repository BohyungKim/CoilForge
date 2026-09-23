"""CCSI "Drain and Vent Location" for water coils (John 2026-09-23).

Every CWC / HWC, on every product line, takes ``Hdr Side In Airflow Dir.`` in the CCSI
Direct Coil form. The value lives in three copies — the app (mirror default + autofill
payload), the userscript (DOM-scraped bridge path) and the Claude-in-Chrome skill's
inline payload builder — which drifted once before (the skill pushed no notes), so all
three are pinned equal here.

It is deliberately NOT tied to the engine's R-066 ``vent_drain = ConnEnd``: that is the
EZ Coil / Coil Checklist vocabulary for a different field, and John keeps them separate.

The CCSI select's id and option values have not been captured live, so the target is
found by label and chosen by OPTION TEXT, and the entry is ``selector_verified: false``
until a capture pins it. The same edit makes the userscript honour the ``{strategy:
"css"}`` selector form, which the live-captured ``#DrawingNotes`` has used since
2026-08-05 without ever resolving.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_APP_JS = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
_USERSCRIPT = (ROOT / "web" / "ccsi" / "ccsi_autofill.user.js").read_text(encoding="utf-8")
_SKILL = (ROOT / ".claude" / "commands" / "ccsi-fill.md").read_text(encoding="utf-8")
_MAP = json.loads((ROOT / "web" / "ccsi" / "ccsi_dx_field_map.json").read_text(encoding="utf-8"))

VALUE = "Hdr Side In Airflow Dir."


def _fn(source: str, name: str) -> str:
    return source.split(f"function {name}(")[1].split("\n  function ")[0].split("\nfunction ")[0]


# --- one value, three copies ----------------------------------------------------------
def test_the_value_is_exactly_the_ccsi_option_text_in_all_three_copies():
    assert f'const CCSI_WATER_DRAIN_VENT_LOCATION = "{VALUE}";' in _APP_JS
    assert f'const WATER_DRAIN_VENT_LOCATION = "{VALUE}";' in _USERSCRIPT
    assert f"value:'{VALUE}'" in _SKILL


def test_the_water_mirror_defaults_to_it_for_every_product_line():
    mirror = _fn(_APP_JS, "renderWaterCoilScreenMirror")
    assert '["Drain and Vent Location", "select", null, CCSI_WATER_DRAIN_VENT_LOCATION]' in mirror
    assert "Stub/Connection" not in _APP_JS
    # no product-line branch on this row: the one mirror serves CWC + every hot-water format
    row = next(line for line in mirror.splitlines() if "Drain and Vent Location" in line)
    assert "isHotWater" not in row and "product" not in row.lower()


# --- the autofill payload -------------------------------------------------------------
def test_payload_carries_it_as_a_top_level_key_for_water_coils_only():
    builder = _fn(_APP_JS, "buildCcsiAutofillPayload")
    assert "drain_vent_location: ccsiDrainVentLocation(" in builder
    entry = _fn(_APP_JS, "ccsiDrainVentLocation")
    assert 'if (!CCSI_WATER_CATEGORIES.has(String(coilCategory || "").toUpperCase())) return null;' in entry
    assert 'const CCSI_WATER_CATEGORIES = new Set(["CWC", "HWC"]);' in _APP_JS
    for fragment in ('match: "option_text"', "selector_verified: false", 'type: "select"'):
        assert fragment in entry, fragment


def test_the_dimension_field_map_is_untouched():
    """`fields` stays dimension-only (the existing contract test enforces the key set)."""
    assert not any("drain" in key.lower() or "vent" in key.lower() for key in _MAP["fields"])


def test_the_dom_bridge_and_the_skill_read_the_stamped_coil_category():
    assert "elements.drawingParameters.dataset.coilCategory =" in _APP_JS
    assert "drain_vent_location: drainVentLocationEntry(" in _USERSCRIPT
    assert 'dataset.coilCategory' in _USERSCRIPT
    assert "dataset.coilCategory" in _SKILL and "drain_vent_location, fields" in _SKILL


# --- the filler -----------------------------------------------------------------------
def test_resolve_understands_the_css_selector_object():
    resolve = _fn(_USERSCRIPT, "resolve")
    assert 'sel.strategy === "css" && sel.selector' in resolve
    assert "document.querySelector(sel.selector)" in resolve


def test_the_entry_becomes_a_panel_row():
    entries = _fn(_USERSCRIPT, "entriesOf")
    assert "payload.drain_vent_location" in entries
    assert 'key: "DVL"' in entries


def test_a_select_is_filled_by_option_text_and_never_guessed():
    fill = _fn(_USERSCRIPT, "fillOne")
    block = fill.split('field.match === "option_text"')[1].split("setNativeValue(target, forTarget")[0]
    assert "optionByText(target, field.value)" in block
    # no matching option -> the function returns BEFORE any write
    miss = block.split("if (!option) {")[1].split("setNativeValue(target, option.value)")[0]
    assert "return;" in miss and "setNativeValue" not in miss
    assert "setNativeValue(target, option.value)" in block


def test_option_matching_is_loose_only_on_whitespace_case_and_a_trailing_period():
    norm = _fn(_USERSCRIPT, "normOptionText")
    assert re.search(r'replace\(/\\s\+/g, " "\)', norm)
    assert ".replace(/\\.$/, \"\")" in norm
    assert ".toLowerCase()" in norm
    verify = _fn(_USERSCRIPT, "verify")
    assert "normOptionText(selected.textContent) === normOptionText(field.value)" in verify


def test_the_userscript_version_was_bumped_in_both_places():
    header = re.search(r"// @version\s+(\S+)", _USERSCRIPT).group(1)
    runtime = re.search(r'const SCRIPT_VERSION = "([^"]+)";', _USERSCRIPT).group(1)
    assert header == runtime
    assert tuple(int(p) for p in header.split(".")) >= (2, 2, 3)
