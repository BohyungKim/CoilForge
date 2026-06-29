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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.interfaces.direct_coil.fields import (  # noqa: E402
    DRAWING_PARAMETER_FIELD_KEYS,
)

_MAP_PATH = (
    Path(__file__).resolve().parents[1] / "web" / "ccsi" / "ccsi_dx_field_map.json"
)


def _load_map() -> dict:
    return json.loads(_MAP_PATH.read_text(encoding="utf-8"))


def test_field_map_covers_exactly_the_13_drawing_params() -> None:
    fields = _load_map()["fields"]
    assert set(fields) == set(DRAWING_PARAMETER_FIELD_KEYS)
    assert len(DRAWING_PARAMETER_FIELD_KEYS) == 13


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
