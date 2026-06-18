"""Phase 5a — UPSTREAM per-category topology slot sourcing (fail-closed, gated).

Proves the confidence gate is load-bearing and mutation-resistant:
  * conn_angle (R-047) / HGBP (R-083) HIGH  -> values (drawable);
  * vent_drain (R-066) MEDIUM               -> review (carried, flagged);
  * vent_drain (R-067, Terra V) LOW         -> blocked (value=None);
  * asc_orientation (R-084) CONFLICT        -> blocked (value=None) + omit/annotate;
  * the gate re-buckets by the field's OWN confidence, so a tampered placement cannot smuggle a
    LOW/CONFLICT value into ``values`` — and DISABLING the gate reds the LOW->blocked tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.schemas.header_prepopulate import (
    Confidence,
    CoilType,
    FieldResult,
    HeaderPrepopulateRequest,
    HeaderPrepopulateResponse,
    ProductFamily,
    TerraVariant,
)
from coilforge.services.header_prepopulate_engine import prepopulate
from coilforge.services import topology_slots
from coilforge.services.topology_slots import topology_drawing_slots


# --------------------------------------------------------------------------- #
# helpers — real engine responses per category
# --------------------------------------------------------------------------- #
def _resp(coil: CoilType, *, product=ProductFamily.NOVA, size="A16", **kw) -> HeaderPrepopulateResponse:
    return prepopulate(
        HeaderPrepopulateRequest(type_of_coil=coil, product_type=product, unit_size=size, **kw)
    )


def hgrh_resp() -> HeaderPrepopulateResponse:
    return _resp(CoilType.HGRH)


def cwc_resp() -> HeaderPrepopulateResponse:
    return _resp(CoilType.CWC)


def cwc_terra_v_resp() -> HeaderPrepopulateResponse:
    return _resp(CoilType.CWC, product=ProductFamily.TERRA, size="012", terra_variant=TerraVariant.TERRA_V)


def dx_hgbp_resp() -> HeaderPrepopulateResponse:
    return _resp(CoilType.DX, hot_gas_bypass=True)


# --------------------------------------------------------------------------- #
# HIGH -> values (drawable)
# --------------------------------------------------------------------------- #
def test_conn_angle_high_lands_in_values() -> None:
    r = topology_drawing_slots(engine_response=hgrh_resp(), category="HGRH")
    assert "slot.conn_angle" in r.values
    gs = r.values["slot.conn_angle"]
    assert gs.value == "LAS"
    assert gs.confidence is Confidence.HIGH
    assert "slot.conn_angle" not in r.review and "slot.conn_angle" not in r.blocked
    assert r.gated_slot_values() == {"slot.conn_angle": "LAS"}


def test_hgbp_high_lands_in_values_as_presence_flag() -> None:
    r = topology_drawing_slots(engine_response=dx_hgbp_resp(), category="DX", special="HGBP")
    assert r.values["slot.HGBP"].value is True
    assert r.values["slot.HGBP"].confidence is Confidence.HIGH


# --------------------------------------------------------------------------- #
# MEDIUM -> review (carried, flagged, never drawn as confirmed)
# --------------------------------------------------------------------------- #
def test_vent_drain_medium_lands_in_review_not_values() -> None:
    r = topology_drawing_slots(engine_response=cwc_resp(), category="CWC")
    assert "slot.vent_drain" in r.review
    assert r.review["slot.vent_drain"].value == "Connections"
    assert r.review["slot.vent_drain"].confidence is Confidence.MEDIUM
    # review-bucket items must NOT be drawable
    assert "slot.vent_drain" not in r.gated_slot_values()


# --------------------------------------------------------------------------- #
# LOW / CONFLICT -> blocked (value=None) — the fail-closed core
# --------------------------------------------------------------------------- #
def test_vent_drain_terra_v_low_actually_blocks() -> None:
    r = topology_drawing_slots(engine_response=cwc_terra_v_resp(), category="CWC")
    assert "slot.vent_drain" in r.blocked
    assert r.blocked["slot.vent_drain"].value is None
    assert r.blocked["slot.vent_drain"].confidence is Confidence.LOW
    # never carried as drawable or review
    assert "slot.vent_drain" not in r.gated_slot_values()
    assert "slot.vent_drain" not in r.review


def test_asc_orientation_conflict_blocks_and_annotates() -> None:
    r = topology_drawing_slots(engine_response=dx_hgbp_resp(), category="DX", special="HGBP")
    assert "asc_orientation" in r.blocked
    assert r.blocked["asc_orientation"].value is None
    assert r.blocked["asc_orientation"].confidence is Confidence.CONFLICT
    items = list(topology_slots.review_and_blocked_items(r))
    assert any("asc_orientation" in s and "blocked" in s for s in items)


# --------------------------------------------------------------------------- #
# The gate is BY CONFIDENCE, not by where the engine placed the field.
# A tampered response (LOW value parked in `values`) is still re-bucketed to blocked.
# --------------------------------------------------------------------------- #
def test_gate_rebuckets_by_confidence_even_if_misplaced() -> None:
    tampered = HeaderPrepopulateResponse(
        values={"vent_drain": FieldResult(value="HDR ENDS", confidence=Confidence.LOW)},
    )
    r = topology_drawing_slots(engine_response=tampered, category="CWC")
    assert "slot.vent_drain" in r.blocked and r.blocked["slot.vent_drain"].value is None
    assert "slot.vent_drain" not in r.gated_slot_values()


@pytest.mark.parametrize(
    "confidence,bucket_attr,expected_value",
    [
        (Confidence.HIGH, "values", "X"),
        (Confidence.MEDIUM, "review", "X"),
        (Confidence.LOW, "blocked", None),
        (Confidence.CONFLICT, "blocked", None),
    ],
)
def test_confidence_drives_bucket(confidence, bucket_attr, expected_value) -> None:
    resp = HeaderPrepopulateResponse(
        values={"conn_angle": FieldResult(value="X", confidence=confidence)}
        if confidence is Confidence.HIGH else {},
        suggestions={"conn_angle": FieldResult(value="X", confidence=confidence)}
        if confidence is Confidence.MEDIUM else {},
        blocked={"conn_angle": FieldResult(value="X", confidence=confidence)}
        if confidence in (Confidence.LOW, Confidence.CONFLICT) else {},
    )
    r = topology_drawing_slots(engine_response=resp, category="HGRH")
    bucket = getattr(r, bucket_attr)
    assert "slot.conn_angle" in bucket
    assert bucket["slot.conn_angle"].value == expected_value


def test_disabling_the_gate_would_leak_low_into_values(monkeypatch) -> None:
    """MUTATION-PROOF: if the confidence gate were disabled (every confidence -> "values"),
    a LOW vent_drain would WRONGLY become drawable. This pins the gate as the single control
    point — the real gate (above) keeps LOW in blocked; only a broken gate leaks it."""
    monkeypatch.setattr(topology_slots, "bucket_for_confidence", lambda _c: "values")
    r = topology_drawing_slots(engine_response=cwc_terra_v_resp(), category="CWC")
    # With the gate disabled the LOW value leaks into values — proving the gate is load-bearing.
    assert "slot.vent_drain" in r.values
    assert "slot.vent_drain" not in r.blocked


# --------------------------------------------------------------------------- #
# missing / not-applicable source -> omitted (review note), never invented
# --------------------------------------------------------------------------- #
def test_missing_source_is_omitted_not_invented() -> None:
    # DX+HGBP request WITHOUT hot_gas_bypass: the engine emits no asc / asc_orientation.
    r = topology_drawing_slots(engine_response=_resp(CoilType.DX), category="DX", special="HGBP")
    assert not r.values and not r.review and not r.blocked
    assert any("slot.HGBP" in n for n in r.notes)
    assert any("asc_orientation" in n for n in r.notes)


def test_category_selects_relevant_slots_only() -> None:
    # HGRH sources conn_angle only; no vent_drain / HGBP.
    r = topology_drawing_slots(engine_response=hgrh_resp(), category="HGRH")
    all_slots = set(r.values) | set(r.review) | set(r.blocked)
    assert all_slots == {"slot.conn_angle"}
