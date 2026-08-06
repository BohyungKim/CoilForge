"""Contract guard for the CCSI Direct Coil autofill field map.

The browser-side autofill (web/app.js::buildCcsiAutofillPayload + the CCSI
userscript) only fills the 13 drawing-parameter fields, and resolves each one's
DOM target from web/ccsi/ccsi_dx_field_map.json. This test pins the map to the
canonical 13 keys so the map, the JS scope, and fields.py can't silently drift
apart. It does NOT validate live CCSI selectors (those are Phase 0, captured off
the real form); it validates the contract shape only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.interfaces.direct_coil.fields import (  # noqa: E402
    DRAWING_PARAMETER_FIELD_KEYS,
)

# A multi-header drawing key is a base geometry stem (I/S/O/R/HD/ZD) suffixed with
# the header index, n >= 2 (I2, S2, HD3, ZD3, ...). Base header-1 keys carry no digit.
_MULTI_HEADER_RE = re.compile(r"^(?:I|S|O|R|HD|ZD)(\d+)$")

_MAP_PATH = (
    Path(__file__).resolve().parents[1] / "web" / "ccsi" / "ccsi_dx_field_map.json"
)


def _load_map() -> dict:
    return json.loads(_MAP_PATH.read_text(encoding="utf-8"))


def test_field_map_covers_the_13_base_params_and_only_multiheader_extras() -> None:
    fields = _load_map()["fields"]
    # All 13 canonical base keys must be present — no silent drop / drift.
    assert set(DRAWING_PARAMETER_FIELD_KEYS) <= set(fields)
    assert len(DRAWING_PARAMETER_FIELD_KEYS) == 13
    # Any key beyond the 13 base must be a multi-header key (I2/S2/.../HD3/ZD3), n >= 2 —
    # the map must not accrete unrelated fields.
    for key in set(fields) - set(DRAWING_PARAMETER_FIELD_KEYS):
        match = _MULTI_HEADER_RE.match(key)
        assert match and int(match.group(1)) >= 2, (
            f"{key} is neither a base drawing param nor a multi-header (I2/S2/...) key"
        )


def test_every_field_resolves_to_a_distinct_real_ccsi_id() -> None:
    # The first selector is the real CCSI #id; every field's real id must be unique so a
    # header-2 value can never overwrite a header-1 (or base) input during autofill.
    fields = _load_map()["fields"]
    real_ids = [entry["selectors"][0] for entry in fields.values()]
    assert len(real_ids) == len(set(real_ids)), "duplicate CCSI #id across the field map"


def test_each_field_entry_has_selectors_type_and_unit() -> None:
    fields = _load_map()["fields"]
    for key, entry in fields.items():
        assert isinstance(entry.get("selectors"), list) and entry["selectors"], (
            f"{key} must list at least one selector"
        )
        assert entry.get("type"), f"{key} must declare an input type"
        assert entry.get("unit"), f"{key} must declare a unit"


def test_map_declares_form_and_version() -> None:
    data = _load_map()
    assert data.get("form")
    assert data.get("version")


# --- Drawing Notes ride the payload WITHOUT entering the field map (2026-07-28) ------------
#
# The engine-assembled drawing notes travel to CCSI so John stops re-typing them, but they are
# a separate top-level payload key, never a 14th entry in `fields`. These guards pin that
# separation from both sides — the map above must stay dimension-only, and the userscript must
# read the notes through its adapter rather than by mutating `fields`.

_APP_JS = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")
_USERSCRIPT = (
    Path(__file__).resolve().parents[1] / "web" / "ccsi" / "ccsi_autofill.user.js"
).read_text(encoding="utf-8")


def test_drawing_notes_never_enter_the_field_map() -> None:
    fields = _load_map()["fields"]
    for key in fields:
        assert "NOTE" not in key.upper(), f"{key} looks like a notes key; the map is dimension-only"


def test_payload_emits_drawing_notes_as_a_top_level_key() -> None:
    assert "drawing_notes: ccsiDrawingNotes(uiState)" in _APP_JS
    # The paste-surface key is direct_coil_label, not label — `label` is undefined forever and
    # would emit null, which reads as "this coil has no notes" rather than as a bug.
    assert 'entry.direct_coil_label === "Drawing Notes"' in _APP_JS


def test_notes_selector_is_the_live_captured_id() -> None:
    """Captured 2026-08-05 off coil.ccsi.ie/Coils/Edit: `#DrawingNotes`.

    This replaces the guard that required the selector to stay unverified — that guard did
    its job, and the capture is what retires it. The capture also explained why the fallback
    never worked: CCSI labels the field `<label for="Drawing_Notes">`, an id that does not
    exist (the input is `DrawingNotes`), so `label.control` is null and labelText resolved
    to nothing. The notes push was silently a no-op.
    """
    assert '{ strategy: "css", selector: "#DrawingNotes" }' in _APP_JS
    assert "selector_verified: true" in _APP_JS
    # The labelText entry stays as a SECOND choice — harmless today, useful if CCSI ever
    # repairs the `for` attribute.
    assert 'strategy: "labelText"' in _APP_JS


def test_the_userscript_still_handles_an_unverified_selector() -> None:
    """The unverified branch must survive the Notes capture. It is not Notes-specific — it
    is what warns John about ANY future field added before its id is captured."""
    assert "selector_verified === false" in _USERSCRIPT


def test_a_single_line_target_gets_newlines_collapsed_on_both_sides() -> None:
    """CCSI's Drawing Notes is an <input>, not a textarea, and CoilForge assembles notes one
    per line. An <input> drops newlines, so writing raw and comparing raw reports a mismatch
    on every successful fill. Both the write and the verify must use the same collapse."""
    assert "function forTarget(target, value)" in _USERSCRIPT
    assert "setNativeValue(target, forTarget(target, field.value));" in _USERSCRIPT
    assert "forTarget(target, field.value).trim()" in _USERSCRIPT
    # A textarea keeps its newlines.
    assert "if (target instanceof HTMLTextAreaElement) return text;" in _USERSCRIPT


def test_userscript_fills_through_the_entries_adapter_not_raw_fields() -> None:
    assert "function entriesOf(payload)" in _USERSCRIPT
    # Fill-all and the row builder must both go through the adapter, or the notes never fill.
    assert "entriesOf(payload).forEach((f) => { if (isFillable(f)) fillOne(f); });" in _USERSCRIPT
    assert "entriesOf(payload).forEach((field) => {" in _USERSCRIPT
    assert "payload.fields.forEach(" not in _USERSCRIPT
