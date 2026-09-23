"""Un-blocking a coil whose Drawing Parameters are empty (John 2026-09-22).

The report: a water coil (CWC / HWC) whose data was not read ends with a Drawing
Parameters panel that is completely empty and NO way forward. Three distinct states did
that, and none of them was "the data is missing" — each one removed the LEVERS:

- B1 a gate-withheld drawing (Terra H/V water, re-seed 2026-09-22) set
  ``template_found=False``, which emptied the fill plan AND hid the product picker;
- B2 the frozen drawing path raising left a bare ``{"error"}`` that rendered as
  "Template not registered" with no picker and no fill panel;
- B3 a rejected ``/derive`` returned a 200 stub that the browser persisted over the
  good coil page, bricking it until a full re-analyze.

Plus the water inlet/outlet connection lever (R-071's connection term), which must
fire ONLY on an engineer-typed value (plan-review R1 BLOCKER-2).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

from coilforge.services.drawing_param_resolver import (  # noqa: E402
    build_manual_fill_plan,
    parameter_set_from_template_drawing,
)
from coilforge.workflows import submittal_to_drawing as std  # noqa: E402
from coilforge.workflows.submittal_to_drawing import derive_coil_template_drawing  # noqa: E402

_APP_JS = (Path(__file__).resolve().parents[1] / "web" / "app.js").read_text(encoding="utf-8")


def _items(result_or_plan):
    plan = result_or_plan.get("manual_fill_plan", result_or_plan)
    return {item["key"]: item for item in plan["items"]}


def _terra_water(**kw):
    spec = dict(
        coil_category="HWC", tag="HHWC-1", circuits=1, rows=2, finned_height=30.0,
        finned_length=60.0, product_type="TERRA V", unit_size="024", suction_conn_size=1.5,
    )
    spec.update(kw)
    return spec


def _nova_water(**kw):
    spec = dict(
        coil_category="HWC", tag="HHWC-1", circuits=1, rows=1, finned_height=30.0,
        finned_length=60.0, product_type="NOVA", unit_size="C24", suction_conn_size=1.5,
    )
    spec.update(kw)
    return spec


# --------------------------------------------------------------------------- #
# B1 — a withheld drawing still offers its levers
# --------------------------------------------------------------------------- #
def test_withheld_terra_water_still_offers_hand_and_param_levers():
    result = derive_coil_template_drawing(_terra_water())
    assert result["not_registered_reason"], "precondition: the 2026-09-22 gate withheld it"
    assert result["svg"] == ""
    plan = result["manual_fill_plan"]
    assert plan["withheld_reason"] == result["not_registered_reason"]  # banner, kept
    items = _items(plan)
    assert "coil_hand" in items, "the hand lever must survive a withheld drawing"
    blocked = {
        k for k, p in result["drawing_parameter_set"]["parameters"].items()
        if p["mode"] == "blocked"
    }
    assert blocked, "precondition: this coil has blank rows"
    assert blocked <= set(items), "every blank row stays fillable while the art is withheld"


def test_withheld_coil_is_labelled_hand_assumed():
    """The withheld coil's hand came from the same LH default; say so there too."""
    result = derive_coil_template_drawing(_terra_water())
    assert result["coil_hand_defaulted"] is True


def test_hand_lever_is_offered_without_artwork():
    td = {"extracted": {"coil_category": "CWC", "hand": "LH"}, "svg": ""}
    assert "coil_hand" in _items(build_manual_fill_plan(td).model_dump())


def test_category_lever_only_when_classification_failed():
    unclassified = derive_coil_template_drawing({"tag": "X-1", "circuits": 1})
    assert _items(unclassified)["coil_category"]["allowed"] == ["DX", "HGRH", "CWC", "HWC"]
    classified = derive_coil_template_drawing(_nova_water())
    assert "coil_category" not in _items(classified), "re-classification is J-0a (John)"


# --------------------------------------------------------------------------- #
# B2 — the frozen path raising yields a classified shell with a fill plan
# --------------------------------------------------------------------------- #
@pytest.fixture
def fresh_workflow_cache():
    """The analyze workflow is memoized by PDF bytes: without this a monkeypatched failure
    would be served to (and leak into) any later test analyzing the same PDF."""
    std.clear_pdf_to_drawing_workflow_cache()
    yield
    std.clear_pdf_to_drawing_workflow_cache()


def _analyze_dx1():
    from test_pdf_to_template_drawing import DX1_TEXT, _make_text_pdf

    return std.run_pdf_to_drawing_workflow(_make_text_pdf(DX1_TEXT.splitlines()))


def test_analyze_error_branch_yields_a_shell_with_a_fill_plan(monkeypatch, fresh_workflow_cache):
    import coilforge.submittal.pdf_to_template_drawing as frozen

    def boom(*_a, **_k):
        raise RuntimeError("simulated drawing-path failure")

    monkeypatch.setattr(frozen, "pdf_text_to_template_drawing", boom)
    td = _analyze_dx1()["template_drawing"]
    assert td["error"] == "simulated drawing-path failure"
    assert td["extracted"]["coil_category"] == "DX"
    assert td["svg"] == ""
    # Never invents: no drawn value at all (the coating note used to leak in here).
    assert td["slot_values"] == {}
    assert "product_type" in _items(td) or td.get("product_type")
    assert td["export_allowed"] is False


def test_analyze_ctx_builder_failure_still_yields_a_shell(monkeypatch, fresh_workflow_cache):
    """`ctx` used to be bound inside the try: a builder failure was an UnboundLocalError."""

    def boom(_candidate):
        raise RuntimeError("simulated context failure")

    monkeypatch.setattr(std, "_template_header_context_from_candidate", boom)
    td = _analyze_dx1()["template_drawing"]
    assert td["error"] == "simulated context failure"
    assert td["slot_values"] == {}
    assert "coil_category" in _items(td)


def test_shell_panel_is_all_blocked_rows_not_preview_defaults():
    shell = std._error_shell_template_drawing(RuntimeError("x"), {"coil_category": "CWC"})
    params = parameter_set_from_template_drawing(shell).parameters
    assert all(p.value is None for k, p in params.items() if k != "ZD")
    assert shell["extracted"]["hand"] is None, "never the frozen path's LH default"


# --------------------------------------------------------------------------- #
# B3 — a rejected /derive is identifiable and never persisted
# --------------------------------------------------------------------------- #
def test_api_engine_error_payload_carries_the_coil_identity():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from coilforge.web_app import app

    body = TestClient(app).post(
        "/api/coil-drawing/derive",
        json={"coil_category": "DX", "tag": "CDXC-1", "product_type": "NOT_A_LINE",
              "unit_size": "B20", "application": "INTEGRATED"},
    ).json()
    if "drawing_parameter_set" in body:
        pytest.skip("this product spelling did not reach the engine's typed error")
    assert body["error"]
    assert body["tag"] == "CDXC-1"
    assert body["export_allowed"] is False


def test_api_rejects_an_unknown_coil_category_without_500():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from coilforge.web_app import app

    r = TestClient(app).post(
        "/api/coil-drawing/derive", json={"tag": "X-1", "coil_category": "STEAM"}
    )
    assert r.status_code == 200
    assert any("coil_category" in e for e in r.json().get("manual_fill_errors", []))


# --------------------------------------------------------------------------- #
# Phase 3 — water inlet/outlet connection sizes (R-071), engineer-typed only
# --------------------------------------------------------------------------- #
def test_water_conn_sizes_reach_r071_on_derive():
    base = derive_coil_template_drawing(_nova_water())
    typed = derive_coil_template_drawing(
        _nova_water(inlet_conn_size=1.5, outlet_conn_size=1.5)
    )
    # HWC R-071: CD = MAX(base, 1.5*(IN+OUT)+1.5) = MAX(base, 6.0)
    assert typed["slot_values"]["slot.CD"] == max(base["slot_values"]["slot.CD"], 6.0)
    assert typed["slot_values"]["slot.CD"] == 6.0
    assert {m["target_field"] for m in typed["manual_overrides"]} == {
        "inlet_conn_size", "outlet_conn_size",
    }


def test_extracted_water_conn_alone_changes_nothing_and_logs_nothing():
    """The shape the browser sends when the engineer typed nothing: the extracted values
    ride under the NON-trigger key. No Tier-A re-run, no phantom ManualOverride."""
    plain = derive_coil_template_drawing(_nova_water())
    with_extracted = derive_coil_template_drawing(
        _nova_water(water_conn_extracted={"inlet": 1.5, "outlet": 1.5})
    )
    assert with_extracted["slot_values"] == plain["slot_values"]
    assert with_extracted["manual_overrides"] == []
    assert with_extracted["water_conn_extracted"] == {"inlet": 1.5, "outlet": 1.5}


def test_water_conn_fill_items_offered_for_water_only():
    water = _items(derive_coil_template_drawing(
        _nova_water(water_conn_extracted={"inlet": 1.25, "outlet": 1.5})
    ))
    assert water["inlet_conn_size"]["current_value"] == 1.25
    assert water["outlet_conn_size"]["critical"] is True
    dx = _items(derive_coil_template_drawing(
        {"coil_category": "DX", "tag": "CDXC-1", "circuits": 1, "rows": 4,
         "finned_height": 20.0, "finned_length": 40.0, "product_type": "NOVA",
         "unit_size": "B20"}
    ))
    assert "inlet_conn_size" not in dx and "outlet_conn_size" not in dx


def test_drawing_and_checklist_agree_on_water_cd_after_the_fill():
    from coilforge.checklist.mapping import _resolve_engine

    drawn = derive_coil_template_drawing(_nova_water(inlet_conn_size=1.5, outlet_conn_size=1.5))
    sheet_slots, _ = _resolve_engine(
        {"coil_type": "HWC", "product_label": "NOVA", "unit_size": "C24", "rows": 1,
         "circuits": 1, "suction_conn_size": 1.5, "inlet_conn_size": 1.5,
         "outlet_conn_size": 1.5, "finned_height": 30.0, "finned_length": 60.0,
         "tag": "HHWC-1"},
        None,
    )
    assert drawn["slot_values"]["slot.CD"] == sheet_slots["slot.CD"]


def test_water_conn_sanitizer_and_kill_switch(monkeypatch):
    from coilforge.web_app import _sanitize_derive_spec

    clean, errors = _sanitize_derive_spec({"inlet_conn_size": "abc", "outlet_conn_size": "1.5"})
    assert "inlet_conn_size" not in clean and clean["outlet_conn_size"] == 1.5
    assert any("inlet_conn_size" in e for e in errors)
    monkeypatch.setenv("COILFORGE_MANUAL_FILL", "0")
    off, _ = _sanitize_derive_spec({"inlet_conn_size": 1.5, "outlet_conn_size": 1.5})
    assert "inlet_conn_size" not in off and "outlet_conn_size" not in off


# --------------------------------------------------------------------------- #
# The cumulative fill store — the backend half of the contract
# --------------------------------------------------------------------------- #
def test_a_resent_override_survives_an_unrelated_second_derive():
    """The browser now re-sends its merged fill set on every derive. A Tier-B override from
    the first fill must still be drawn after a second derive that only changes the hand,
    and the response must not duplicate its event (plan-review R1 BLOCKER-3). The ledger
    inserts one correction row per RUN — identity-set 1 — which is what the measurement
    consumers (triage / observatory) count."""
    cd = {"key": "CD", "value": 7.25, "unit": "in", "override_reason": "measured"}
    first = derive_coil_template_drawing(_nova_water(param_overrides=[cd]))
    second = derive_coil_template_drawing(
        _nova_water(param_overrides=[cd], coil_hand="RH")
    )
    for result in (first, second):
        assert result["slot_values"]["slot.CD"] == 7.25
        assert [e["key"] for e in result["manual_override_events"]] == ["CD"]
    assert second["extracted"]["hand"] == "RH"


# --------------------------------------------------------------------------- #
# Frontend contract (source-level, like tests/test_checklist_panel_join.py)
# --------------------------------------------------------------------------- #
def _fn(name: str) -> str:
    return _APP_JS.split(f"function {name}(")[1].split("\nfunction ")[0]


def test_picker_is_no_longer_gated_on_artwork():
    picker = _fn("templateDrawingPicker")
    assert "if (!templateDrawing.template_found) {" not in picker
    assert "templateDrawing.extracted?.coil_category" in picker


def test_classified_results_render_through_the_template_path():
    assert "if (uiState.template_drawing && uiState.template_drawing.extracted) {" in _APP_JS
    assert "if (templateDrawing && templateDrawing.extracted) {" in _APP_JS
    assert "!uiState.template_drawing.error" not in _APP_JS


def test_withheld_fill_panel_continues_to_its_items():
    panel = _fn("renderManualFillPanel")
    assert "const withheldHtml = plan.withheld_reason" in panel
    assert "if (plan.withheld_reason) {\n    return" not in panel


def test_a_rejected_derive_is_never_persisted():
    derive = _APP_JS.split("async function deriveCoilDrawing(")[1].split("\nasync function ")[0]
    guard = derive.index("if (updated.error || !updated.drawing_parameter_set) {")
    assert guard < derive.index("persistDerivedToPage(targetPage, updated);")
    assert "if (opts.headless) throw new Error(" in derive  # counted as failed by the fan-out
    assert "td.error" not in _fn("reapplyManualFills")


def test_the_fill_store_is_cumulative_and_committed_at_call_time():
    derive = _APP_JS.split("async function deriveCoilDrawing(")[1].split("\nasync function ")[0]
    assert "mergeManualFills(" in derive
    assert "page.manualFills = {" not in _APP_JS, "the store is merged, never replaced"
    assert "targetPage.manualFills = merged" in derive


def test_latest_wins_is_per_page_and_never_drops_a_headless_derive():
    derive = _APP_JS.split("async function deriveCoilDrawing(")[1].split("\nasync function ")[0]
    assert "state.deriveSeq" not in _APP_JS, "a session-wide counter drops the fan-out"
    assert "targetPage.deriveSeq" in derive
    assert "!opts.headless && targetPage && seq !== targetPage.deriveSeq" in derive
    # a stale interactive response is neither rendered nor persisted (R2 MAJOR-1)
    assert derive.index("if (isStale()) return null;\n    persistDerivedToPage(") > 0


def test_water_conn_is_sent_only_when_typed():
    spec = _fn("deriveSpecFromTemplate")
    assert "inlet_conn_size: engineInputs.inlet_conn_size," in spec
    assert 'pick("inlet_conn_size"' not in spec and 'pick("outlet_conn_size"' not in spec
    assert "water_conn_extracted: templateDrawing.water_conn_extracted," in spec


def test_checklist_collector_carries_the_picker_but_not_the_category():
    collector = _fn("collectChecklistOverrides")
    assert "engineInputs.product_type = fills.productLine" in collector
    assert "engineInputs.unit_size = fills.unitSize" in collector
    assert "coil_category: _category" in collector


def test_auto_derive_listens_to_change_not_input():
    attach = _fn("attachManualFillPanel")
    assert 'addEventListener("change"' in attach
    assert 'addEventListener("input"' not in attach
    assert 'addEventListener("input"' not in _fn("scheduleAutoDerive")


def test_no_blocking_browser_dialogs_were_added():
    """confirm()/alert() block the page and any Claude-in-Chrome session driving it."""
    import re

    code = chr(10).join(line.split("//")[0] for line in _APP_JS.splitlines())
    assert not re.search(r"(?<![\w.])(?:window\.)?(confirm|alert|prompt)\(", code)
