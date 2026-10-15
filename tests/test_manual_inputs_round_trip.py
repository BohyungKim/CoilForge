"""Typed submittal inputs: they reach the drawing, travel apart from what the submittal
said, and can be taken back (John 2026-10-02).

Connection size, FH / FL, rows and feeds are the submittal's own geometry. When the PDF
omits or misreads one, the engineer types it. Each then travels as TWO values --
``input_baseline`` (what the submittal said) and ``manual_inputs`` (what was typed) -- for
the reason the round-trip tests below exist: the frozen path echoes whatever it was sent
into ``extracted``, the browser builds the next request from that echo, and a typed value
folded into the plain keys could never be cleared.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

from coilforge.services.drawing_param_resolver import (  # noqa: E402
    _ENGINE_INPUT_META,
    build_manual_fill_plan,
)
from coilforge.workflows import submittal_to_drawing as std  # noqa: E402
from coilforge.workflows.submittal_to_drawing import derive_coil_template_drawing  # noqa: E402
from derive_roundtrip import spec_from_template_drawing  # noqa: E402

_APP_JS = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")


def _js_function(name):
    return _APP_JS.split(f"function {name}(")[1].split("\nfunction ")[0]


def _dx(**kw):
    spec = dict(
        coil_category="DX", coil_hand="LH", tag="CDXC-1", circuits=2, rows=4, feeds=6,
        finned_height=20.0, finned_length=40.0, product_type="NOVA", unit_size="B20",
    )
    spec.update(kw)
    return spec


def _nova_hgrh(**kw):
    spec = dict(
        coil_category="HGRH", coil_hand="LH", tag="RHHGRC-1", circuits=2, rows=2, feeds=4,
        finned_height=20.0, finned_length=40.0, return_conn_size=0.875,
        product_type="NOVA", unit_size="B20",
    )
    spec.update(kw)
    return spec


def _hgrh_no_conn():
    return _nova_hgrh(return_conn_size=None, panel={"feeds": 4})


def _hwc(**kw):
    spec = dict(
        coil_category="HWC", coil_hand="LH", tag="HHWC-1", circuits=1, rows=1, feeds=2,
        finned_height=36.0, finned_length=33.0, suction_conn_size=1.0,
        product_type="NOVA", unit_size="C24",
    )
    spec.update(kw)
    return spec


def _slots(result):
    return result.get("slot_values") or {}


def _items(result):
    return {item["key"]: item for item in result["manual_fill_plan"]["items"]}


# --------------------------------------------------------------------------- #
# The lever is offered under the key the drawing reads
# --------------------------------------------------------------------------- #
def test_missing_conn_item_uses_return_conn_size():
    """The engine asks for `suction_conn_size` (DX) / `conn_size` (HGRH); offered under
    those names, the typed value reached the checklist but never the drawing."""
    for spec in (_dx(), _nova_hgrh(return_conn_size=None)):
        items = _items(derive_coil_template_drawing(spec))
        assert "return_conn_size" in items, spec["coil_category"]
        assert items["return_conn_size"]["critical"] and items["return_conn_size"]["unresolved"]
        assert not {"suction_conn_size", "conn_size"} & set(items), spec["coil_category"]


def test_return_conn_lever_is_not_offered_on_water_coils():
    """A water coil's connections are its inlet and outlet; a third lever for the same two
    physical values would inflate the missing count."""
    items = _items(derive_coil_template_drawing(_hwc(suction_conn_size=None)))
    assert "return_conn_size" not in items
    assert items["inlet_conn_size"]["unresolved"] and items["outlet_conn_size"]["unresolved"]


def test_missing_critical_inputs_are_offered_before_the_engine_runs():
    """With no product line the engine never runs, so it lists nothing as missing -- and
    the coil's missing geometry went unasked until a product was picked."""
    items = _items(derive_coil_template_drawing({"coil_category": "DX", "tag": "CDXC-1", "circuits": 1}))
    for key in ("finned_height", "finned_length", "rows", "feeds", "return_conn_size"):
        assert items[key]["critical"] and items[key]["unresolved"], key


def test_every_offered_engine_input_is_read_by_the_spec_builder():
    """The defect class itself: a fill item whose key the browser never sends."""
    spec_builder = _js_function("deriveSpecFromTemplate")
    manual_keys = set(
        re.findall(r'"(\w+)"', _APP_JS.split("const MANUAL_INPUT_KEYS = [")[1].split("];")[0])
    )
    for key in _ENGINE_INPUT_META:
        read = (
            key in manual_keys
            or f"engineInputs.{key}" in spec_builder
            or f'pick("{key}"' in spec_builder
        )
        assert read, f"fill item {key!r} is offered but never sent to /derive"


# --------------------------------------------------------------------------- #
# A typed value draws exactly what the same value draws when intake read it
# --------------------------------------------------------------------------- #
def test_typed_conn_draws_like_an_extracted_one():
    read_dx = derive_coil_template_drawing(
        _dx(suction_conn_size=1.125, panel={"conn_size": 1.125, "feeds": 6})
    )
    typed_dx = derive_coil_template_drawing(
        _dx(panel={"feeds": 6}, manual_inputs={"return_conn_size": 1.125})
    )
    assert _slots(typed_dx) == _slots(read_dx)
    assert typed_dx["svg"] == read_dx["svg"]

    read_hgrh = derive_coil_template_drawing(_nova_hgrh(panel={"conn_size": 0.875, "feeds": 4}))
    typed_hgrh = derive_coil_template_drawing(
        _nova_hgrh(return_conn_size=None, panel={"feeds": 4},
                   manual_inputs={"return_conn_size": 0.875})
    )
    assert _slots(typed_hgrh) == _slots(read_hgrh)
    assert typed_hgrh["svg"] == read_hgrh["svg"]


def test_corrected_conn_and_feeds_replace_the_title_block_text():
    """The title block's connection size and "N Feed" text come from `panel`, not from the
    geometry the dimensions use; correcting only the geometry printed new dimensions next
    to the old connection size."""
    misread = _nova_hgrh(return_conn_size=0.625, feeds=4, panel={"conn_size": 0.625, "feeds": 4})
    before = derive_coil_template_drawing(misread)
    after = derive_coil_template_drawing(
        {**misread, "manual_inputs": {"return_conn_size": 0.875, "feeds": 6}}
    )
    assert _slots(before)["slot.SUPPLY_CONN_SIZE"] == '0.625"'
    assert _slots(after)["slot.SUPPLY_CONN_SIZE"] == '0.875"'
    assert _slots(after)["slot.CIRCUITING"].startswith("6 Feed")
    # The SVG escapes the inch mark.
    assert "0.875&quot;" in after["svg"] and "0.625&quot;" not in after["svg"]
    assert "6 Feed" in after["svg"] and "4 Feed" not in after["svg"]


def test_water_typed_inlet_outlet_fills_the_title_block_conn_text():
    no_conn = _hwc(suction_conn_size=None)
    blank = derive_coil_template_drawing(no_conn)
    typed = derive_coil_template_drawing({**no_conn, "inlet_conn_size": 2.0, "outlet_conn_size": 2.0})
    assert _slots(blank).get("slot.SUPPLY_CONN_SIZE") in (None, "")
    assert _slots(typed)["slot.SUPPLY_CONN_SIZE"] == '2.0"'
    assert typed["panel"] == {}, "the round-trip carrier keeps what the submittal said"


def test_typed_fh_draws_ch():
    read = derive_coil_template_drawing(_dx(suction_conn_size=1.125))
    missing = derive_coil_template_drawing(_dx(suction_conn_size=1.125, finned_height=None))
    typed = derive_coil_template_drawing(
        _dx(suction_conn_size=1.125, finned_height=None, manual_inputs={"finned_height": 20.0})
    )
    assert _slots(missing).get("slot.CH") is None
    assert _slots(typed)["slot.CH"] == _slots(read)["slot.CH"]
    assert typed["svg"] == read["svg"]


def test_typed_fl_draws_fl_cl_oal():
    read = derive_coil_template_drawing(_dx(suction_conn_size=1.125))
    typed = derive_coil_template_drawing(
        _dx(suction_conn_size=1.125, finned_length=None, manual_inputs={"finned_length": 40.0})
    )
    for slot in ("slot.FL", "slot.CL", "slot.OAL"):
        assert _slots(typed)[slot] == _slots(read)[slot], slot
    assert typed["svg"] == read["svg"]


# --------------------------------------------------------------------------- #
# Taking a value back -- built the way the browser builds it
# --------------------------------------------------------------------------- #
def test_clearing_a_typed_input_reverts_the_drawing_and_the_lever():
    """Each request is built from the previous RESPONSE. A hand-written second request is
    clean exactly where the real round trip is dirty (`extracted` and `panel` echo
    whatever the previous derive was sent), so it would pass while the page kept the value.
    The Tier-A variant matters: that re-run reads the plain connection key itself."""
    for tier_a in ({}, {"application": "INTEGRATED"}):
        first = derive_coil_template_drawing(_hgrh_no_conn())
        typed = derive_coil_template_drawing(
            spec_from_template_drawing(first, {"return_conn_size": 0.875, "feeds": 6, **tier_a})
        )
        assert _slots(typed)["slot.R2"] == 0.875 and "6 Feed" in typed["svg"]
        cleared = derive_coil_template_drawing(spec_from_template_drawing(typed, dict(tier_a)))
        reference = derive_coil_template_drawing(spec_from_template_drawing(first, dict(tier_a)))
        assert cleared["svg"] == reference["svg"], tier_a
        assert _slots(cleared) == _slots(reference), tier_a
        assert _items(cleared)["return_conn_size"]["unresolved"] is True


def test_clearing_the_only_fill_empties_the_page_store():
    derive = _APP_JS.split("async function deriveCoilDrawing(")[1].split("\nasync function ")[0]
    assert "if (targetPage && (committed || prevStore)) targetPage.manualFills = nextStore;" in derive
    assert "JSON.stringify(nextStore)" in derive  # so a cleared store schedules a refill


def test_clearing_an_input_drops_its_spec_override_row():
    merge = _js_function("mergeManualFills")
    assert "delete engineInputs[key];" in merge and "specs.delete(key);" in merge


def test_mechanical_fit_reads_the_drawn_geometry_not_the_request():
    derive = _APP_JS.split("async function deriveCoilDrawing(")[1].split("\nasync function ")[0]
    assert "const drawn = updated.extracted || {};" in derive
    assert "finned_height: drawn.finned_height," in derive


def test_second_derive_keeps_the_baseline_as_previous_value():
    first = derive_coil_template_drawing(_dx(suction_conn_size=1.125))
    once = derive_coil_template_drawing(spec_from_template_drawing(first, {"rows": 6}))
    twice = derive_coil_template_drawing(spec_from_template_drawing(once, {"rows": 6}))
    for result in (once, twice):
        (row,) = [ov for ov in result["spec_overrides"] if ov["field_key"] == "rows"]
        assert (row["previous_value"], row["new_value"]) == (4, 6)
        (audit,) = [mo for mo in result["manual_overrides"] if mo["target_field"] == "rows"]
        assert (audit["previous_value"], audit["override_value"]) == (4, 6)


def test_water_coil_with_unstated_feeds_is_flagged():
    """With neither feeds nor circuits stated, analyze still fills a water coil's feeds
    (header type, else 1). The drawing may use that; the fill panel must not present it as
    read."""
    td = {"extracted": {"coil_category": "HWC", "hand": "LH", "feeds": 2, "rows": 1,
                        "finned_height": 30.0, "finned_length": 60.0},
          "product_type": "NOVA", "unit_size": "C24"}
    td["input_baseline"] = std._input_baseline(td, SimpleNamespace(geometry={}))
    assert td["input_baseline"]["feeds"] == {"value": 2, "stated": False}
    feeds = {i.key: i for i in build_manual_fill_plan(td).items}["feeds"]
    assert feeds.critical and feeds.unresolved and feeds.current_value == 2
    assert "assumes 2" in feeds.reason


def test_water_feeds_taken_from_stated_circuits_count_as_read():
    """John 2026-10-06 (A): a water submittal states "Circuits", and feeds come from that
    count -- the source he approved for the CCSI push. Flagging it would put "1 missing" on
    every water coil and bury the real gaps."""
    td = {"extracted": {"coil_category": "HWC", "hand": "LH", "feeds": 4, "rows": 1,
                        "finned_height": 30.0, "finned_length": 60.0},
          "product_type": "NOVA", "unit_size": "C24",
          "water_conn_extracted": {"inlet": 1.5, "outlet": 1.5}}
    candidate = SimpleNamespace(geometry={"circuits": SimpleNamespace(value=4)})
    td["input_baseline"] = std._input_baseline(td, candidate)
    assert td["input_baseline"]["feeds"] == {"value": 4, "stated": True}
    plan = build_manual_fill_plan(td)
    assert "feeds" not in {i.key for i in plan.items}
    assert "feeds" not in plan.critical_missing


def test_analyze_stamps_the_baseline_the_browser_round_trips():
    from test_pdf_to_template_drawing import DX1_TEXT, _make_text_pdf

    std.clear_pdf_to_drawing_workflow_cache()
    try:
        td = std.run_pdf_to_drawing_workflow(_make_text_pdf(DX1_TEXT.splitlines()))["template_drawing"]
    finally:
        std.clear_pdf_to_drawing_workflow_cache()
    baseline = td["input_baseline"]
    assert set(baseline) == set(std._MANUAL_INPUT_KEYS)
    for key, entry in baseline.items():
        assert entry["value"] == td["extracted"].get(key), key


# --------------------------------------------------------------------------- #
# The API boundary and the audit trail
# --------------------------------------------------------------------------- #
def test_manual_inputs_sanitizer_and_kill_switch(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from coilforge.web_app import app

    client = TestClient(app)
    base = _nova_hgrh(panel={"conn_size": 0.875, "feeds": 4})
    good = client.post("/api/coil-drawing/derive", json={**base, "manual_inputs": {"feeds": "6"}}).json()
    assert "6 Feed" in good["svg"] and "6.0 Feed" not in good["svg"]
    bad = client.post(
        "/api/coil-drawing/derive",
        json={**base, "manual_inputs": {"rows": 4.5, "finned_height": "abc", "nope": 1}},
    ).json()
    errors = " | ".join(bad["manual_fill_errors"])
    assert "rows: must be a whole number" in errors
    assert "finned_height: must be a positive number" in errors
    assert "unknown manual input" in errors
    assert _slots(bad)["slot.ROWS"] == 2  # nothing bad was applied

    monkeypatch.setenv("COILFORGE_MANUAL_FILL", "0")
    off = client.post("/api/coil-drawing/derive", json={**base, "manual_inputs": {"feeds": 6}}).json()
    plain = client.post("/api/coil-drawing/derive", json=base).json()
    assert _slots(off) == _slots(plain) and off["svg"] == plain["svg"]


def test_manual_input_writes_audit_and_spec_field_row():
    result = derive_coil_template_drawing(_dx(manual_inputs={"return_conn_size": 1.125}))
    (row,) = result["spec_overrides"]
    assert row == {"field_key": "return_conn_size", "previous_value": None, "new_value": 1.125,
                   "override_reason": "manual fill (human-in-the-loop)"}
    (audit,) = [m for m in result["manual_overrides"] if m["target_field"] == "return_conn_size"]
    assert audit["review_status"] == "unreviewed"
    assert result["export_allowed"] is False


def test_extracted_value_writes_no_audit_row():
    result = derive_coil_template_drawing(_dx(suction_conn_size=1.125))
    assert not result.get("spec_overrides")
    assert not result["manual_overrides"]


def test_explicit_spec_edit_reason_wins():
    explicit = {"field_key": "rows", "previous_value": 4, "new_value": 6,
                "override_reason": "submittal page 3 says 6 rows"}
    result = derive_coil_template_drawing(
        _dx(suction_conn_size=1.125, manual_inputs={"rows": 6}, spec_overrides=[explicit])
    )
    assert result["spec_overrides"] == [explicit]


def test_spec_field_lists_agree():
    from coilforge.services.three_way_view import _SPEC_FIELDS
    from coilforge.web_app import _KNOWN_SPEC_FIELD_KEYS

    block = _APP_JS.split("const SPEC_EDIT_FIELDS = [")[1].split("];")[0]
    js = set(re.findall(r'\{ key: "(\w+)", label:', block))
    assert js == set(_KNOWN_SPEC_FIELD_KEYS) == set(_SPEC_FIELDS)


# --------------------------------------------------------------------------- #
# HGRH with no connection size (John 2026-10-02)
# --------------------------------------------------------------------------- #
def test_hgrh_without_conn_leaves_every_supply_s_blank_with_a_reason():
    result = derive_coil_template_drawing(_hgrh_no_conn())
    slots = _slots(result)
    assert "slot.S1" not in slots and "slot.S3" not in slots
    assert slots.get("slot.CD") is not None, "precondition: the casing depth resolved"
    rows = result["drawing_parameter_set"]["parameters"]
    for key in ("S", "S2"):
        assert rows[key]["value"] is None and rows[key]["mode"] == "blocked", key
        assert rows[key]["blocked_reason"].startswith("HGRH supply S is placed"), key
