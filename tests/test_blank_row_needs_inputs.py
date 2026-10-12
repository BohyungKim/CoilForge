"""A blank drawing row names the input that unblocks it (John 2026-10-02).

`DrawingParameter.needs_inputs` lists the fill keys whose absence blanked a row -- only an
input that is BOTH a verified dependency of that dimension AND missing on this coil. A
wrong entry would send the engineer to type a value that changes nothing, so the
dependency table is re-proved here by running the slot layer with and without each input.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from coilforge.services.drawing_param_resolver import (  # noqa: E402
    _NEEDS_BY_BASE,
    _NEEDS_BY_CATEGORY_BASE,
)
from coilforge.workflows.submittal_to_drawing import derive_coil_template_drawing  # noqa: E402

_APP_JS = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")

# A complete coil per category: every input the table names is present.
_FULL = {
    "DX": dict(coil_category="DX", coil_hand="LH", tag="CDXC-1", circuits=2, rows=4, feeds=6,
               finned_height=20.0, finned_length=40.0, suction_conn_size=1.125,
               product_type="NOVA", unit_size="B20"),
    "HGRH": dict(coil_category="HGRH", coil_hand="LH", tag="RHHGRC-1", circuits=2, rows=2,
                 feeds=4, finned_height=20.0, finned_length=40.0, return_conn_size=0.875,
                 product_type="NOVA", unit_size="B20"),
    # Water S/R come from inlet/outlet, falling back to a single connection size -- so the
    # proof coil carries ONLY the split, or removing the inlet would prove nothing.
    "HWC": dict(coil_category="HWC", coil_hand="LH", tag="HHWC-1", circuits=1, rows=1, feeds=2,
                finned_height=36.0, finned_length=33.0, product_type="NOVA", unit_size="C24",
                water_conn_extracted={"inlet": 1.5, "outlet": 1.25}),
}
_FULL["CWC"] = {**_FULL["HWC"], "coil_category": "CWC", "tag": "CCWC-1", "rows": 6}

_SLOT_FOR_BASE = {"CD": "slot.CD", "CH": "slot.CH", "S": "slot.S1", "R": "slot.R2"}


def _without(spec, input_key):
    spec = dict(spec)
    if input_key == "return_conn_size":
        spec.pop("suction_conn_size", None)
        spec.pop("return_conn_size", None)
    elif input_key in ("inlet_conn_size", "outlet_conn_size"):
        side = input_key.split("_")[0]
        spec["water_conn_extracted"] = {**spec["water_conn_extracted"], side: None}
    else:
        spec[input_key] = None
    return spec


def _rows(result):
    return result["drawing_parameter_set"]["parameters"]


def _table_cases():
    for (category, base), inputs in _NEEDS_BY_CATEGORY_BASE.items():
        for input_key in inputs:
            yield category, base, input_key
    for base, inputs in _NEEDS_BY_BASE.items():
        for category in _FULL:
            if (category, base) in _NEEDS_BY_CATEGORY_BASE:
                continue
            for input_key in inputs:
                yield category, base, input_key


@pytest.mark.parametrize("category,base,input_key", list(_table_cases()))
def test_dim_needs_table_matches_the_slot_layer(category, base, input_key):
    """Each table entry, executed: the slot exists with every input and disappears when
    that one input is removed -- and the blank row then names exactly that input."""
    slot = _SLOT_FOR_BASE[base]
    full = derive_coil_template_drawing(dict(_FULL[category]))
    assert full["slot_values"].get(slot) is not None, f"{category} {slot} precondition"
    missing = derive_coil_template_drawing(_without(_FULL[category], input_key))
    assert missing["slot_values"].get(slot) is None, f"{category} {slot} does not need {input_key}"
    row = _rows(missing)[base]
    assert row["mode"] == "blocked"
    assert input_key in row["needs_inputs"], (category, base, row["needs_inputs"])


def test_blank_ch_names_finned_height():
    row = _rows(derive_coil_template_drawing(_without(_FULL["DX"], "finned_height")))["CH"]
    assert row["needs_inputs"] == ["finned_height"]


def test_terra_water_o_names_finned_height():
    """Terra water artwork dimensions O from the opposite end (O = CH - I)."""
    terra = dict(_FULL["CWC"], product_type="TERRA H", unit_size="024", coil_hand="RH")
    assert derive_coil_template_drawing(dict(terra))["slot_values"].get("slot.O2") is not None
    row = _rows(derive_coil_template_drawing(_without(terra, "finned_height")))["O"]
    assert row["mode"] == "blocked" and row["needs_inputs"] == ["finned_height"]


def test_needs_inputs_never_names_a_present_input():
    """HGRH S depends on the connection size AND the casing depth (rows); with rows read,
    only the connection size may be named."""
    result = derive_coil_template_drawing(_without(_FULL["HGRH"], "return_conn_size"))
    for key in ("S", "S2", "R", "R2"):
        assert _rows(result)[key]["needs_inputs"] == ["return_conn_size"], key


def test_a_typed_input_is_never_named():
    typed = derive_coil_template_drawing(
        {**_without(_FULL["DX"], "finned_height"), "manual_inputs": {"finned_height": 20.0}}
    )
    assert all("finned_height" not in row["needs_inputs"] for row in _rows(typed).values())


def test_no_product_names_the_pickers():
    result = derive_coil_template_drawing({"coil_category": "DX", "tag": "CDXC-1", "circuits": 1})
    assert _rows(result)["CD"]["needs_inputs"] == ["product_type", "unit_size"]


def test_multi_header_s_inherits_the_hgrh_reason():
    result = derive_coil_template_drawing(_without(_FULL["HGRH"], "return_conn_size"))
    assert _rows(result)["S"]["blocked_reason"] == _rows(result)["S2"]["blocked_reason"]
    assert _rows(result)["S2"]["blocked_reason"].startswith("HGRH supply S is placed")


def test_dimensions_with_no_verified_dependency_name_nothing():
    """I / HD / HDx / SL have no entry: a blank there says nothing rather than guess."""
    for base in ("I", "HD", "HDx", "SL"):
        assert base not in _NEEDS_BY_BASE
        assert all(b != base for _c, b in _NEEDS_BY_CATEGORY_BASE)


def test_the_needs_chip_focuses_where_the_input_is_typed():
    row = _APP_JS.split("function renderParameterRow(")[1].split("\nfunction ")[0]
    assert "parameter.needs_inputs" in row and "data-needs-input=" in row
    assert "focusFillInput(needs.dataset.needsInput)" in _APP_JS
    focus = _APP_JS.split("function focusFillInput(")[1].split("\nfunction ")[0]
    assert '"#coil-product-line"' in focus and "[data-manual-fill=" in focus
