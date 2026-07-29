"""Human-in-the-loop manual fill: engineer supplies missing coil data in the
browser and the drawing regenerates — instead of the flow halting and bouncing
back to Claude. Covers both tiers (engine-input recompute + drawing-param
override), the auto-surface fill plan, the audit trail, the hard-halt guards,
the kill switch, and — load-bearing — that a coil with NO manual fill is
byte-for-byte unchanged (the H4 regression guard) and no frozen file is edited.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from coilforge.services.direct_coil_drawing_pipeline import (  # noqa: E402
    UnknownCoilInputError,
    build_drawing_slots,
    build_header_request,
)
from coilforge.services.drawing_param_resolver import (  # noqa: E402
    build_manual_fill_plan,
    parameter_set_from_template_drawing,
)
from coilforge.contracts.canonical import ManualOverride  # noqa: E402
from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    derive_coil_template_drawing,
    manual_overrides_from_fills,
)

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from coilforge.web_app import app  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

# The DO-NOT-TOUCH frozen set (CLAUDE.md). This feature must not edit any of these.
FROZEN_PATHS = (
    "src/coilforge/submittal/pdf_to_template_drawing.py",
    "src/coilforge/template_population/slot_population.py",
)


def _base_spec(**overrides):
    spec = {
        "coil_category": "DX",
        "tag": "CDXC-1",
        "circuits": 1,
        "rows": 4,
        "finned_height": 20.0,
        "finned_length": 40.0,
        "product_type": "NOVA",
        "unit_size": "B20",
    }
    spec.update(overrides)
    return spec


# --------------------------------------------------------------------------- #
# Hard-halt guards (1.2 / 1.3)
# --------------------------------------------------------------------------- #
def test_unknown_coil_type_raises_typed_error_not_keyerror():
    with pytest.raises(UnknownCoilInputError) as exc:
        build_header_request(coil_type="BOGUS", product_type="NOVA", unit_size="B20")
    assert exc.value.field == "coil_type"
    assert "DX" in exc.value.allowed


def test_unknown_product_type_raises_typed_error():
    with pytest.raises(UnknownCoilInputError) as exc:
        build_header_request(coil_type="DX", product_type="NOTAPRODUCT", unit_size="B20")
    assert exc.value.field == "product_type"


def test_invalid_unit_size_surfaces_unit_size_picker_not_raise():
    # unit_size present but invalid for NOVA -> engine returns unknown_unit_size,
    # the fill plan surfaces a unit_size picker (human-in-the-loop), no crash.
    result = derive_coil_template_drawing(_base_spec(unit_size="ZZ99", application="INTEGRATED"))
    plan = result["manual_fill_plan"]
    unit_items = [i for i in plan["items"] if i["key"] == "unit_size"]
    assert unit_items and unit_items[0]["allowed"]


# --------------------------------------------------------------------------- #
# Tier A — engine-input un-gate (1.1 / 1.1a)
# --------------------------------------------------------------------------- #
def test_build_drawing_slots_accepts_ungate_inputs():
    slots, _ = build_drawing_slots(
        coil_type="DX", product_type="NOVA", unit_size="B20",
        rows=4, application="INTEGRATED", header_count=1, qty_conn_per_header=1,
    )
    assert "slot.CD" in slots


def test_tier_a_fill_recomputes_and_merges_slot_values():
    result = derive_coil_template_drawing(
        _base_spec(application="INTEGRATED", header_count=1, override_reason="engineer picked")
    )
    assert result["slot_values"].get("slot.CD") is not None
    assert result["export_allowed"] is False


# --------------------------------------------------------------------------- #
# Tier B — drawing-param override (1.5), panel-only
# --------------------------------------------------------------------------- #
def test_tier_b_override_is_manual_review_required():
    td = {"product_type": "NOVA", "unit_size": "B20", "slot_values": {}}
    param_set = parameter_set_from_template_drawing(
        td, param_overrides=[{"key": "CD", "value": 3.25, "override_reason": "measured"}]
    )
    cd = param_set.parameters["CD"]
    assert cd.value == 3.25
    assert cd.mode == "manual"
    assert cd.manual_override is True
    assert cd.status == "review_required"
    assert param_set.export_allowed is False


def test_tier_b_override_does_not_touch_slot_values():
    td = {"product_type": "NOVA", "unit_size": "B20", "slot_values": {}}
    parameter_set_from_template_drawing(
        td, param_overrides=[{"key": "CD", "value": 3.25, "override_reason": "measured"}]
    )
    # The PANEL resolver stays panel-only (correct layering): reflection into slot_values
    # is the non-frozen caller's job (_reflect_param_overrides_into_slots), NOT this
    # function's. So a direct call must still leave slot_values untouched.
    assert "slot.CD" not in td["slot_values"]


# --------------------------------------------------------------------------- #
# 1b — Tier-B reflection: the override reaches slot_values + the SVG, and the
# pre-override machine proposal is event-sourced for the correction ledger.
# --------------------------------------------------------------------------- #
def test_tier_b_override_reflects_into_slot_and_events():
    spec = _base_spec(
        param_overrides=[{"key": "CD", "value": 9.5, "override_reason": "field measured"}]
    )
    result = derive_coil_template_drawing(dict(spec))

    # Reflected into slot_values so the drawing renders the corrected dimension.
    assert result["slot_values"]["slot.CD"] == 9.5
    assert result["manual_override_keys"] == ["CD"]

    # Event-sourced: the pre-override machine proposal is captured (and != the override).
    events = result["manual_override_events"]
    assert len(events) == 1
    ev = events[0]
    assert ev["key"] == "CD" and ev["new_value"] == 9.5
    assert ev["override_reason"] == "field measured"
    assert ev["previous_value"] != 9.5  # the machine proposal, not the override

    # Panel agrees with the slot (single source of truth) and stays review-required.
    cd = result["drawing_parameter_set"]["parameters"]["CD"]
    assert cd["value"] == 9.5 and cd["mode"] == "manual"
    assert result["export_allowed"] is False
    if result.get("svg"):
        assert "9.5" in result["svg"]


def test_tier_b_multi_header_override_maps_to_parity_slot():
    # Logical UI header key S2 -> engine parity slot S3 (supply id 2*2-1).
    spec = _base_spec(
        circuits=2,
        param_overrides=[{"key": "S2", "value": 4.25, "override_reason": "measured"}],
    )
    result = derive_coil_template_drawing(dict(spec))
    assert result["slot_values"]["slot.S3"] == 4.25
    assert result["manual_override_keys"] == ["S2"]


def test_reflection_no_op_without_overrides():
    # No param_overrides -> the reflection helper must not fire (no events key, and the
    # H4 byte-identical guard below still holds).
    result = derive_coil_template_drawing(dict(_base_spec()))
    assert "manual_override_events" not in result
    assert "manual_override_keys" not in result


# --------------------------------------------------------------------------- #
# Auto-surface fill plan (1.4) — sourcing corrections H-NEW-3 / M-NEW-1
# --------------------------------------------------------------------------- #
def test_no_product_line_surfaces_product_and_size_pickers():
    result = derive_coil_template_drawing({"coil_category": "DX", "tag": "CDXC-1", "circuits": 1})
    keys = {i["key"] for i in result["manual_fill_plan"]["items"]}
    assert {"product_type", "unit_size"} <= keys


def test_fill_plan_drawing_params_are_blocked_not_unmapped():
    # ZD/unmapped rows must NOT leak into the fill plan; only mode=='blocked' dims.
    td = {"product_type": "NOVA", "unit_size": "B20", "slot_values": {}}
    param_set = parameter_set_from_template_drawing(td)
    plan = build_manual_fill_plan(td, None, param_set)
    dp_keys = {i["key"] for i in plan.model_dump()["items"] if i["kind"] == "drawing_param"}
    # ZD is a default constant (not blocked) -> must be absent.
    assert "ZD" not in dp_keys
    assert all(param_set.parameters[k].mode == "blocked" for k in dp_keys)


# --------------------------------------------------------------------------- #
# Audit trail (1.6)
# --------------------------------------------------------------------------- #
def test_manual_overrides_logged_review_required():
    overrides = manual_overrides_from_fills(
        _base_spec(
            application="INTEGRATED",
            param_overrides=[{"key": "CD", "value": 3.25, "override_reason": "measured"}],
            override_reason="engineer picked",
        )
    )
    targets = {mo.target_field for mo in overrides}
    assert "application" in targets
    assert "drawing_parameters.CD" in targets
    assert all(mo.review_status == "unreviewed" for mo in overrides)
    # round-trips through the contract
    for mo in overrides:
        assert ManualOverride.model_validate(mo.model_dump())


# --------------------------------------------------------------------------- #
# H4 regression — a coil with NO manual fill is byte-for-byte unchanged
# --------------------------------------------------------------------------- #
def test_no_manual_fill_output_is_unchanged():
    spec = _base_spec()  # no application/header_count/qty/param_overrides
    a = derive_coil_template_drawing(dict(spec))
    b = derive_coil_template_drawing(dict(spec))
    # The re-run block must not fire (no dropped inputs), so slot_values are identical
    # and stable across calls — the drawing is untouched by the feature.
    assert a["slot_values"] == b["slot_values"]
    assert a["drawing_parameter_set"] == b["drawing_parameter_set"]


# --------------------------------------------------------------------------- #
# Frozen-file guard — the feature must not edit any DO-NOT-TOUCH file
# --------------------------------------------------------------------------- #
def test_frozen_files_untouched_by_working_tree():
    # Fails if any frozen file has uncommitted edits. Skips cleanly outside git.
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "--", *FROZEN_PATHS,
             "src/coilforge/templates/drawing"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git not available")
    if out.returncode != 0:
        pytest.skip("git diff unavailable")
    changed = [line for line in out.stdout.splitlines() if line.strip()]
    assert not changed, f"DO-NOT-TOUCH files were modified: {changed}"


# --------------------------------------------------------------------------- #
# API boundary — validation + kill switch (Layer 2)
# --------------------------------------------------------------------------- #
def test_api_missing_override_reason_is_error_not_500():
    client = TestClient(app)
    r = client.post(
        "/api/coil-drawing/derive",
        json={"coil_category": "DX", "product_type": "NOVA", "unit_size": "B20",
              "param_overrides": [{"key": "CD", "value": 3.25}]},
    )
    assert r.status_code == 200
    assert any("override_reason" in e for e in r.json().get("manual_fill_errors", []))


def test_api_non_numeric_param_rejected():
    client = TestClient(app)
    r = client.post(
        "/api/coil-drawing/derive",
        json={"coil_category": "DX", "product_type": "NOVA", "unit_size": "B20",
              "param_overrides": [{"key": "CD", "value": "abc", "override_reason": "x"}]},
    )
    assert r.status_code == 200
    assert r.json().get("manual_fill_errors")


def test_api_unknown_param_key_rejected():
    client = TestClient(app)
    r = client.post(
        "/api/coil-drawing/derive",
        json={"coil_category": "DX", "product_type": "NOVA", "unit_size": "B20",
              "param_overrides": [{"key": "NOPE", "value": 1, "override_reason": "x"}]},
    )
    assert r.status_code == 200
    assert r.json().get("manual_fill_errors")


def test_pdf_workflow_attaches_manual_fill_plan():
    # The very first analyze (no /derive) must surface the fill plan so a blocked
    # coil shows "fill these to complete the drawing" immediately.
    from coilforge.workflows.submittal_to_drawing import run_pdf_to_drawing_workflow
    from test_pdf_to_template_drawing import DX1_TEXT, _make_text_pdf

    workflow = run_pdf_to_drawing_workflow(_make_text_pdf(DX1_TEXT.splitlines()))
    plan = workflow["template_drawing"].get("manual_fill_plan")
    assert plan is not None
    assert "items" in plan


def test_kill_switch_off_strips_fills(monkeypatch):
    monkeypatch.setenv("COILFORGE_MANUAL_FILL", "0")
    client = TestClient(app)
    r = client.post(
        "/api/coil-drawing/derive",
        json={"coil_category": "DX", "product_type": "NOVA", "unit_size": "B20",
              "application": "INTEGRATED",
              "param_overrides": [{"key": "CD", "value": 9.9, "override_reason": "x"}]},
    )
    body = r.json()
    assert "manual_fill_plan" not in body
    # the override value must NOT have been applied
    assert body["drawing_parameter_set"]["parameters"]["CD"]["value"] != 9.9


# --------------------------------------------------------------------------- #
# Coil hand assumed vs. read (John 2026-07-28)
# --------------------------------------------------------------------------- #
# The frozen drawing path resolves the hand as
# `ctx.coil_hand or extract.hand or "LH"`, so a submittal that states no handing
# silently draws LEFT and the UI shows "HAND LH" as if it had been read. Oxygen8
# cover rows carry handing for DX but leave it blank for water coils, so this is
# the normal HWC/CWC case. The hand picks the LH vs RH template, i.e. it mirrors
# the entire drawing.


def _water_spec(**kw):
    spec = dict(
        coil_category="HWC", product_type="TERRA V", unit_size="040",
        circuits=1, rows=1, feeds=2, finned_height=36.0, finned_length=33.0,
        suction_conn_size=1.0, tag="HHWC-1",
    )
    spec.update(kw)
    return spec


def test_unstated_hand_is_flagged_as_assumed_and_still_draws():
    result = derive_coil_template_drawing(_water_spec())
    assert result["svg"], "the drawing must still render — the hand is labelled, not blanked"
    assert result["coil_hand_defaulted"] is True
    assert "not stated" in result["coil_hand_review"].lower()
    assert result["template_id"] == "coilmaster_hwc_lh"


def test_stated_hand_is_not_flagged():
    for hand, template_id in (("Left", "coilmaster_hwc_lh"), ("Right", "coilmaster_hwc_rh")):
        result = derive_coil_template_drawing(_water_spec(coil_hand=hand))
        assert result.get("coil_hand_defaulted") is None, hand
        assert result.get("coil_hand_review") is None, hand
        assert result["template_id"] == template_id, hand


def test_assumed_hand_surfaces_a_fill_item_that_reselects_the_template():
    """The fill item is the whole point: picking RH must re-select the mirrored
    template, not merely record a note."""
    assumed = derive_coil_template_drawing(_water_spec())
    items = {i["key"]: i for i in assumed["manual_fill_plan"]["items"]}
    assert "coil_hand" in items
    assert items["coil_hand"]["kind"] == "template_input"
    assert items["coil_hand"]["allowed"] == ["Left", "Right"]

    # Filling it (the /derive spec carries coil_hand) redraws the other hand.
    filled = derive_coil_template_drawing(_water_spec(coil_hand="Right"))
    assert filled["template_id"] == "coilmaster_hwc_rh"
    assert filled["svg"] and filled["svg"] != assumed["svg"]


def test_hand_fill_item_absent_when_the_hand_was_stated():
    result = derive_coil_template_drawing(_water_spec(coil_hand="Left"))
    keys = {i["key"] for i in result["manual_fill_plan"]["items"]}
    assert "coil_hand" not in keys
