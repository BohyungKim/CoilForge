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
