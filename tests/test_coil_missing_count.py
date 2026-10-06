"""Each coil in the coil list says how many critical inputs it is still missing
(John 2026-10-02), so an incomplete submittal is visible without opening every coil.

The count is the backend plan's `critical_missing`: critical AND unresolved inputs. The
hand and the water connection sizes are offered on every coil as correction levers, so
counting them whenever they are offered would put a red number on complete coils.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.workflows.submittal_to_drawing import derive_coil_template_drawing  # noqa: E402

_APP_JS = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")


def _missing(spec):
    return set(derive_coil_template_drawing(spec)["manual_fill_plan"]["critical_missing"])


def _hwc(**kw):
    spec = dict(coil_category="HWC", coil_hand="LH", tag="HHWC-1", circuits=1, rows=1, feeds=2,
                finned_height=36.0, finned_length=33.0, product_type="NOVA", unit_size="C24",
                water_conn_extracted={"inlet": 1.5, "outlet": 1.5})
    spec.update(kw)
    return spec


def test_summary_counts_only_unresolved_critical_inputs():
    assert _missing(_hwc()) == set(), "a complete coil shows no count"
    assert _missing(_hwc(coil_hand=None, water_conn_extracted=None, rows=None)) == {
        "coil_hand", "inlet_conn_size", "outlet_conn_size", "rows",
    }


def test_a_typed_input_leaves_the_count():
    assert "rows" in _missing(_hwc(rows=None))
    assert "rows" not in _missing({**_hwc(rows=None), "manual_inputs": {"rows": 1}})


def test_count_includes_rows_and_conn_when_no_product_is_chosen():
    missing = _missing({"coil_category": "DX", "tag": "CDXC-1", "circuits": 1})
    assert {"product_type", "unit_size", "rows", "feeds", "finned_height", "finned_length",
            "return_conn_size"} <= missing


def test_blank_dimension_rows_are_not_counted_as_inputs():
    """The count is of INPUTS to supply; a blank dimension is their consequence."""
    result = derive_coil_template_drawing(_hwc(finned_height=None))
    plan = result["manual_fill_plan"]
    dims = {i["key"] for i in plan["items"] if i["kind"] == "drawing_param"}
    assert dims and not dims & set(plan["critical_missing"])


def test_the_coil_list_shows_the_count():
    tree = _APP_JS.split("function renderProjectTree(")[1].split("\nfunction ")[0]
    assert "manual_fill_plan?.critical_missing" in tree and 'class="tree-missing"' in tree


def test_the_coil_list_refreshes_after_a_fill():
    derive = _APP_JS.split("async function deriveCoilDrawing(")[1].split("\nasync function ")[0]
    persisted = derive.index("persistDerivedToPage(targetPage, updated);")
    assert derive.index("renderProjectTree(state.ui)", persisted) > persisted
