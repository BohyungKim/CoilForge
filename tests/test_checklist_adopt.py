"""Adopt from Coil Checklist (John 2026-09-22).

When intake could not read a coil, the checklist may still have computed its dimensions.
The browser can copy them in — INPUTS first (the engine recomputes), the sheet's formula
RESULTS only onto rows still blank. An adopted value is a copy of the sheet, so the
compare must report it as ``adopted``: never ``match`` (that would claim two independent
implementations agreed) and never ``mismatch`` / ``overridden``.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.checklist import template_map as T  # noqa: E402
from coilforge.checklist.compare import build_review  # noqa: E402
from coilforge.checklist.mapping import _to_size  # noqa: E402
from coilforge.checklist.model import (  # noqa: E402
    ChecklistFill,
    DimCompare,
    OverrideNote,
    SheetFill,
)
from coilforge.checklist.overrides import (  # noqa: E402
    ADOPTED_REASON_PREFIX,
    is_adopted_reason,
    normalize_coil_overrides,
)
from coilforge.workflows.submittal_to_drawing import derive_coil_template_drawing  # noqa: E402

_APP_JS = (ROOT / "web" / "app.js").read_text(encoding="utf-8")


def _water(**kw):
    spec = dict(
        coil_category="HWC", tag="HHWC-1", circuits=1, rows=1, finned_height=30.0,
        finned_length=60.0, product_type="NOVA", unit_size="C24", suction_conn_size=1.5,
    )
    spec.update(kw)
    return spec


def _adopted(key="CD", value=6.0):
    return {
        "key": key, "value": value, "unit": "in", "source": "checklist",
        "override_reason": f"{ADOPTED_REASON_PREFIX} HHWC-1 {key} (sheet formula result)",
    }


# --- provenance on the wire ---------------------------------------------------------
def test_adopted_override_source_rides_on_the_wire_and_in_the_events():
    result = derive_coil_template_drawing(_water(param_overrides=[_adopted()]))
    cd = result["drawing_parameter_set"]["parameters"]["CD"]
    assert cd["value"] == 6.0 and cd["mode"] == "manual" and cd["source"] == "checklist"
    assert cd["review_required"] is True  # never promoted
    assert result["manual_override_events"][0]["source"] == "checklist"
    assert result["export_allowed"] is False
    three_way = {row["field"]: row for row in result["three_way"]["fields"]}
    assert three_way["CD"]["engineer_source"] == "checklist"


def test_adoption_reason_prefix_is_ledgered():
    result = derive_coil_template_drawing(_water(param_overrides=[_adopted()]))
    reasons = [m["override_reason"] for m in result["manual_overrides"]]
    assert reasons and all(is_adopted_reason(r) for r in reasons)
    assert is_adopted_reason(result["manual_override_events"][0]["override_reason"])


def test_an_engineer_typed_override_is_not_mistaken_for_an_adoption():
    typed = {"key": "CD", "value": 6.0, "unit": "in", "override_reason": "measured on site"}
    result = derive_coil_template_drawing(_water(param_overrides=[typed]))
    assert result["drawing_parameter_set"]["parameters"]["CD"]["source"] == "engineer"


def test_sanitizer_whitelists_the_source():
    from coilforge.web_app import _sanitize_derive_spec

    clean, errors = _sanitize_derive_spec(
        {"param_overrides": [{**_adopted(), "source": "robot"}, _adopted("CH", 30.0)]}
    )
    assert [o["key"] for o in clean["param_overrides"]] == ["CH"]
    assert any("source" in e for e in errors)


# --- compare verdict ----------------------------------------------------------------
def _review(reason):
    fill = ChecklistFill(sheets=(SheetFill(
        category="HWC", source_sheet="HWC", sheet_tag="HHWC-1",
        compare_dims=(DimCompare(
            label="CD", slot="slot.CD", coilforge_value=6.0,
            override=OverrideNote(key="CD", previous_value=None, reason=reason),
        ),),
    ),))
    return build_review(fill, {"sheets": [{"tag": "HHWC-1", "computed_dims": {"CD": 6.0}}]})


def test_compare_reports_adopted_not_overridden_when_the_note_is_an_adoption():
    review = _review(f"{ADOPTED_REASON_PREFIX} HHWC-1 CD (sheet formula result)")
    row = review["sheets"][0]["comparisons"][0]
    assert row["verdict"] == "adopted"
    assert review["mismatch_total"] == 0
    assert review["override_total"] == 0
    assert review["adopted_total"] == 1
    assert review["sheets"][0]["adopted_count"] == 1


def test_a_typed_override_still_reports_overridden():
    row = _review("measured on site")["sheets"][0]["comparisons"][0]
    assert row["verdict"] == "overridden"


def test_the_adopted_reason_reaches_the_checklist_note():
    notes = normalize_coil_overrides([{"tag": "HHWC-1", "param_overrides": [_adopted()]}])
    assert is_adopted_reason(notes["HHWC-1"].reason_for("CD"))


def test_a_known_divergence_ruling_does_not_annotate_an_adopted_row(tmp_path):
    yaml = pytest.importorskip("yaml")
    from coilforge.review.divergence import ANY_SIZE, annotate_known_divergences, load_registry

    path = tmp_path / "p.yaml"
    path.write_text(yaml.safe_dump({"version": 1, "divergences": [{
        "id": "KD-900", "coil_category": "HWC", "product_family": "NOVA",
        "terra_variant": None, "unit_size_scope": ANY_SIZE, "slot": "slot.CD",
        "verdict": "checklist_wrong", "reason": "test", "evidence_refs": ["x"],
        "adjudicated_by": "John",
    }]}), encoding="utf-8")
    registry = load_registry(promoted_path=path, staging_path=tmp_path / "absent.yaml")
    review = {"sheets": [{"tag": "HHWC-1", "category": "HWC", "comparisons": [
        {"label": "CD", "slot": "slot.CD", "coilforge": 6.0, "checklist": 6.0,
         "verdict": "adopted"},
    ]}]}
    coils = [{"tag": "HHWC-1", "coil_type": "HWC", "product_label": "NOVA", "unit_size": "C24"}]
    import copy

    control = copy.deepcopy(review)
    control["sheets"][0]["comparisons"][0].update(coilforge=5.0, verdict="mismatch")
    annotated = annotate_known_divergences(control, coils, registry=registry)
    assert "divergence" in annotated["sheets"][0]["comparisons"][0], "control: the ruling matches"
    out = annotate_known_divergences(review, coils, registry=registry)
    assert "divergence" not in out["sheets"][0]["comparisons"][0]


# --- frontend mapping pinned against the Python side --------------------------------
def test_the_js_prefix_equals_the_python_prefix():
    assert f'const ADOPTED_REASON_PREFIX = "{ADOPTED_REASON_PREFIX}";' in _APP_JS


def _js_size_token(unit: str, size) -> str:
    """Python mirror of app.js::checklistSizeToPickerToken (the JS text is pinned below)."""
    if size in (None, ""):
        return ""
    if unit in ("TERRA H", "TERRA V"):
        return f"{int(size):03d}" if isinstance(size, int) and size > 0 else ""
    return str(size)


def test_size_token_inverse_matches_mapping_to_size():
    """Every SIZE the sheet can hold maps back to the picker token that produced it."""
    js = _APP_JS.split("function checklistSizeToPickerToken(")[1].split("\nfunction ")[0]
    assert 'String(n).padStart(3, "0")' in js
    for unit, options in T.SIZE_OPTIONS.items():
        for size in options:
            token = _js_size_token(unit, size)
            assert _to_size(unit, token) == size, (unit, size, token)


def test_unit_inverse_covers_every_sheet_unit():
    js = _APP_JS.split("const CHECKLIST_UNIT_TO_PRODUCT = {")[1].split("};")[0]
    from coilforge.submittal.coilmaster_drawing_extract import product_size_options

    pickers = set(product_size_options())
    for unit in set(T.UNIT_BY_PRODUCT.values()):
        line = next((ln for ln in js.splitlines() if f'"{unit}"' in ln or f"{unit}:" in ln), None)
        assert line, unit
        product = line.split(":")[1].strip().strip('",')
        assert product in pickers, (unit, product)
        assert T.UNIT_BY_PRODUCT[product] == unit


def test_adoption_is_offered_only_on_blank_rows_and_never_while_refilling():
    fn = _APP_JS.split("function checklistAdoptHtml(")[1].split("\nfunction ")[0]
    assert "if (hasValue || !chk || state.checklistRefillPending) return \"\";" in fn
    # The adopted number is the sheet's value in the DRAWING's datum (water O, 2026-09-23).
    assert "checklistValueAsDrawn(chk)" in fn
    assert "isAdoptableChecklistValue(sheetValue)" in fn


def test_inputs_are_adopted_before_sheet_results():
    fn = _APP_JS.split("async function adoptAllFromChecklist(")[1].split("\nfunction ")[0]
    assert fn.index("plan.inputs.length") < fn.index("stillBlank")
    assert 'source: "checklist"' in _APP_JS.split("async function adoptChecklistDims(")[1]


def test_water_connection_sizes_are_not_adopted_pending_j1b():
    """Adopting IN/OUT CONN SZ would switch R-071 on per coil — John's open decision J-1b."""
    plan = _APP_JS.split("function checklistAdoptionPlan(")[1].split("\nasync function ")[0]
    assert "CONN SZ" not in plan
    assert "inlet_conn_size" not in plan and "outlet_conn_size" not in plan


def test_the_checklist_table_marks_an_adopted_row():
    """Found in the TR-13 eyeball: the '=' column was blank for `adopted`."""
    icon = _APP_JS.split("function _verdictIcon(")[1].split("\nfunction ")[0]
    assert 'adopted: "↙"' in icon
