"""The Direct Coil (submittal-data) screen paints a missing CRITICAL input red
(John 2026-10-02), driven by the backend fill plan's `mirror_field` -- not by a second
hand-kept list of critical fields, and not by row emptiness (that screen keeps showing
analyze-time values, so an emptiness test would stay red after the value was typed).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.interfaces.direct_coil import DIRECT_COIL_FIELD_REGISTRY  # noqa: E402
from coilforge.services.drawing_param_resolver import _MIRROR_FIELD_BY_INPUT  # noqa: E402
from coilforge.workflows.submittal_to_drawing import derive_coil_template_drawing  # noqa: E402

_APP_JS = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")


def _fn(name):
    return _APP_JS.split(f"function {name}(")[1].split("\nfunction ")[0]


def _aliases(field):
    block = _fn("directCoilLabelsForDraftKey")
    match = re.search(rf"\b{field}: \[([^\]]*)\]", block)
    return re.findall(r'"([^"]+)"', match.group(1)) if match else []


def test_mirror_fields_are_registry_keys():
    for fill_key, field in _MIRROR_FIELD_BY_INPUT.items():
        assert field in DIRECT_COIL_FIELD_REGISTRY, (fill_key, field)


def test_every_mirror_field_has_a_row_in_each_mirror_variant_it_applies_to():
    """An alias with no row on the screen would make the highlight silently do nothing."""
    variants = {
        "dx": _APP_JS.split("const DC_SECTIONS = {")[1].split("\n};")[0],
        "condensing": _fn("renderCondensingCoilScreenMirror"),
        "water": _fn("renderWaterCoilScreenMirror"),
    }
    applies = {
        "finned_height": ("dx", "condensing", "water"),
        "finned_length": ("dx", "condensing", "water"),
        "rows_deep": ("dx", "condensing", "water"),
        "number_of_feeds": ("dx", "condensing", "water"),
        "return_connection_size": ("dx", "condensing", "water"),
        "coil_hand": ("dx", "condensing", "water"),
    }
    assert set(applies) == set(_MIRROR_FIELD_BY_INPUT.values())
    for field, names in applies.items():
        labels = _aliases(field)
        assert labels, field
        for name in names:
            assert any(f'"{label}"' in variants[name] for label in labels), (field, name)


def test_the_plan_names_the_mirror_field_of_each_missing_input():
    result = derive_coil_template_drawing(
        {"coil_category": "HWC", "tag": "HHWC-1", "circuits": 1, "product_type": "NOVA",
         "unit_size": "C24"}
    )
    items = {i["key"]: i for i in result["manual_fill_plan"]["items"]}
    assert items["finned_height"]["mirror_field"] == "finned_height"
    assert items["inlet_conn_size"]["mirror_field"] == "return_connection_size"
    assert items["coil_hand"]["mirror_field"] == "coil_hand"


def test_mirror_red_comes_from_the_plan_and_the_screen_stays_readonly():
    labels = _fn("dcMissingCriticalLabels")
    assert "it.critical && it.unresolved !== false && it.mirror_field" in labels
    row = _fn("renderDcInputRow")
    assert "dcMissingCriticalLabels().has(normalizeDcLabel(label))" in row
    assert row.count("readonly") >= 2 and "disabled" in row


def test_the_mirror_refreshes_after_a_fill():
    derive = _APP_JS.split("async function deriveCoilDrawing(")[1].split("\nasync function ")[0]
    persisted = derive.index("persistDerivedToPage(targetPage, updated);")
    assert derive.index("renderDirectCoilScreenMirror(state.ui)", persisted) > persisted
