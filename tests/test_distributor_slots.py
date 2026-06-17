"""Phase 4a — distributor sourcing + the FAIL-CLOSED DistExtension gate.

Proves the GATE, not just emission: a callout that disagrees with the engine MUST block
(never silently HIGH); DistModel/DistOD are review (value carried, not drawn); missing data is
omitted + annotated, never invented; the drawing engine sees only HIGH slots.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.schemas.header_prepopulate import (  # noqa: E402
    Confidence,
    HeaderPrepopulateResponse,
)
from coilforge.services.direct_coil_drawing_pipeline import (  # noqa: E402
    build_header_request,
    map_engine_to_slots,
)
from coilforge.services.distributor_slots import distributor_drawing_slots  # noqa: E402
from coilforge.services.header_prepopulate_engine import prepopulate  # noqa: E402

_EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "sanitized"


def dx_engine() -> HeaderPrepopulateResponse:
    """Real engine output for a DX coil -> dist_extension HIGH = 6 (R-033)."""
    return prepopulate(
        build_header_request(
            coil_type="DX", product_type="NOVA", unit_size="B20",
            rows=4, feeds=2, circuits=1, suction_conn_size=0.625, handing="LH",
        )
    )


def _fixture(name: str) -> dict:
    return json.loads((_EXAMPLES / name).read_text(encoding="utf-8"))


SINGLE = _fixture("dx_header1_ezc0001_default.json")
MULTI = _fixture("dx_header3_ezc0007_default.json")


def _display(fx: dict) -> dict:
    return {k: fx.get(k) for k in ("drawing_callouts", "distributors_display", "airflow_direction")}


# --------------------------------------------------------------------------- #
# Engine baseline
# --------------------------------------------------------------------------- #
def test_engine_dist_extension_is_high_6() -> None:
    r = dx_engine()
    assert "dist_extension" in r.values
    assert r.values["dist_extension"].value == 6


# --------------------------------------------------------------------------- #
# slot.AIRFLOW
# --------------------------------------------------------------------------- #
def test_airflow_high_from_direction() -> None:
    res = distributor_drawing_slots(engine_response=dx_engine(), supply_ids=[1], display=_display(SINGLE))
    assert res.values["slot.AIRFLOW"].value == "left_to_right"
    assert res.values["slot.AIRFLOW"].confidence == Confidence.HIGH
    assert res.values["slot.AIRFLOW"].source == "airflow_direction"


def test_airflow_missing_omitted_not_invented() -> None:
    res = distributor_drawing_slots(
        engine_response=dx_engine(), supply_ids=[1],
        display={"distributors_display": SINGLE["distributors_display"]},
    )
    assert "slot.AIRFLOW" not in res.values
    assert any("AIRFLOW" in n for n in res.notes)


# --------------------------------------------------------------------------- #
# slot.DistExtension — the fail-closed gate (a)/(b)/(c) + JSON override
# --------------------------------------------------------------------------- #
def test_dist_extension_callout_matches_engine_high() -> None:
    # SINGLE callout: "DISTRIBUTOR 1 HAS 6\" EXTENSION"; engine = 6 -> agree -> HIGH.
    res = distributor_drawing_slots(engine_response=dx_engine(), supply_ids=[1], display=_display(SINGLE))
    gs = res.values["slot.DistExtension1"]
    assert gs.value == 6 and gs.confidence == Confidence.HIGH
    assert "slot.DistExtension1" not in res.blocked


def test_dist_extension_callout_missing_engine_high() -> None:
    display = {"airflow_direction": "left_to_right", "drawing_callouts": ["COLLARED HOLES REQUIRED"]}
    res = distributor_drawing_slots(engine_response=dx_engine(), supply_ids=[1], display=display)
    assert res.values["slot.DistExtension1"].value == 6
    assert "slot.DistExtension1" not in res.blocked


def test_dist_extension_callout_mismatch_blocks_fail_closed() -> None:
    # Engine = 6, callout = 8 -> MUST block. This test fails if the mismatch is not blocked.
    display = dict(_display(SINGLE))
    display["drawing_callouts"] = ['DISTRIBUTOR 1 HAS 8" EXTENSION']
    res = distributor_drawing_slots(engine_response=dx_engine(), supply_ids=[1], display=display)
    assert "slot.DistExtension1" in res.blocked
    assert res.blocked["slot.DistExtension1"].value is None
    assert res.blocked["slot.DistExtension1"].confidence == Confidence.CONFLICT
    assert res.blocked["slot.DistExtension1"].reason
    assert "slot.DistExtension1" not in res.values  # never silently HIGH


def test_dist_extension_json_override_value_used() -> None:
    ez = [dict(SINGLE["header_assemblies"][0], DistExtension=8.0), SINGLE["header_assemblies"][1]]
    display = {"drawing_callouts": ['DISTRIBUTOR 1 HAS 8" EXTENSION'], "airflow_direction": "left_to_right"}
    res = distributor_drawing_slots(engine_response=dx_engine(), supply_ids=[1], ez_headers=ez, display=display)
    gs = res.values["slot.DistExtension1"]
    assert gs.value == 8 and gs.source == "ez_json"
    assert any("overrides engine" in n for n in res.notes)


# --------------------------------------------------------------------------- #
# slot.DistModel / slot.DistOD — review (value carried, NOT drawn)
# --------------------------------------------------------------------------- #
def test_dist_model_and_od_are_review_with_value() -> None:
    res = distributor_drawing_slots(engine_response=dx_engine(), supply_ids=[1], display=_display(SINGLE))
    model = res.review["slot.DistModel1"]
    assert isinstance(model.value, str) and model.value.startswith("501-2-3/16")  # label-only string
    assert model.confidence == Confidence.MEDIUM
    assert "slot.DistModel1" not in res.values  # never auto-drawn
    od = res.review["slot.DistOD1"]
    assert od.value == 0.625  # OD:5/8 parsed, NOT from the model string
    assert "slot.DistOD1" not in res.values


def test_missing_model_and_od_omitted_not_invented() -> None:
    res = distributor_drawing_slots(
        engine_response=dx_engine(), supply_ids=[1], display={"airflow_direction": "left_to_right"}
    )
    assert "slot.DistModel1" not in res.review and "slot.DistModel1" not in res.values
    assert any("DistModel1" in n for n in res.notes)
    assert any("DistOD1" in n for n in res.notes)


# --------------------------------------------------------------------------- #
# "Engine consumes gated slots only" — HIGH-only flat dict
# --------------------------------------------------------------------------- #
def test_gated_slot_values_high_only() -> None:
    res = distributor_drawing_slots(engine_response=dx_engine(), supply_ids=[1], display=_display(SINGLE))
    flat = res.gated_slot_values()
    assert "slot.AIRFLOW" in flat and "slot.DistExtension1" in flat
    assert "slot.DistModel1" not in flat  # review -> not drawable
    assert "slot.DistOD1" not in flat


def test_blocked_dist_extension_absent_from_gated_values() -> None:
    display = dict(_display(SINGLE))
    display["drawing_callouts"] = ['DISTRIBUTOR 1 HAS 8" EXTENSION']
    res = distributor_drawing_slots(engine_response=dx_engine(), supply_ids=[1], display=display)
    assert "slot.DistExtension1" not in res.gated_slot_values()


# --------------------------------------------------------------------------- #
# Per-id (3-circuit fixture)
# --------------------------------------------------------------------------- #
def test_multi_circuit_per_id_slots() -> None:
    res = distributor_drawing_slots(
        engine_response=dx_engine(), supply_ids=[1, 3, 5],
        ez_headers=MULTI["header_assemblies"], display=_display(MULTI),
    )
    for sid in (1, 3, 5):
        assert res.values[f"slot.DistExtension{sid}"].value == 6  # callouts all 6, engine 6
        assert res.review[f"slot.DistModel{sid}"].value.startswith("502-3-1/4-5")
        assert res.review[f"slot.DistOD{sid}"].value == 0.625


# --------------------------------------------------------------------------- #
# Engine bridge wiring (map_engine_to_slots)
# --------------------------------------------------------------------------- #
def test_map_engine_to_slots_merges_high_distributor_slots() -> None:
    slots, review = map_engine_to_slots(dx_engine(), display=_display(SINGLE), supply_ids=[1])
    assert slots["slot.AIRFLOW"] == "left_to_right"
    assert slots["slot.DistExtension1"] == 6
    assert "slot.DistModel1" not in slots  # review, not merged into drawable slots
    assert any("slot.DistModel1" in item for item in review)


def test_map_engine_to_slots_blocked_not_merged() -> None:
    display = dict(_display(SINGLE))
    display["drawing_callouts"] = ['DISTRIBUTOR 1 HAS 8" EXTENSION']
    slots, review = map_engine_to_slots(dx_engine(), display=display, supply_ids=[1])
    assert "slot.DistExtension1" not in slots
    assert any("blocked:slot.DistExtension1" in item for item in review)


def test_map_engine_to_slots_derives_supply_ids_from_headers() -> None:
    slots, _ = map_engine_to_slots(
        dx_engine(), display=_display(MULTI), ez_headers=MULTI["header_assemblies"]
    )
    for sid in (1, 3, 5):
        assert slots[f"slot.DistExtension{sid}"] == 6


def test_map_engine_to_slots_unchanged_without_distributor_inputs() -> None:
    # Back-compat: no display/ez_headers/supply_ids -> no distributor slots, legacy behaviour.
    slots, _ = map_engine_to_slots(dx_engine())
    assert not any(k.startswith("slot.Dist") or k == "slot.AIRFLOW" for k in slots)
