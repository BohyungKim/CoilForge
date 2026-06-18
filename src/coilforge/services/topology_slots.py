"""Phase 5a — UPSTREAM sourcing of the per-category topology drawing slots (no drawing).

Emits the new gated drawing slots the parametric engine needs to extend beyond DX
(docs/design/ez-drawing-model.md §7.4). Like :mod:`distributor_slots`, this is a pure
function: an already-gated :class:`HeaderPrepopulateResponse` in, a tri-bucket result out, no
I/O, no drawing/layout/backend code, no ``eval``.

The 4 NEW visual glyphs that RENDER these data are Phase 5b. 5a sources + gates + tests the
data only; the engine consumes the gated result (HIGH -> drawable; review -> flagged; blocked
-> omit + annotate).

Slots, by coil type:

- ``slot.conn_angle`` (HGRH)        <- engine ``conn_angle`` (R-047 ``"LAS"``, HIGH).
- ``slot.vent_drain`` (CWC/HWC)     <- engine ``vent_drain`` (R-066 MEDIUM -> review; R-067
  Terra V LOW -> blocked).
- ``slot.HGBP`` (DX + special HGBP) <- engine ``asc`` (R-083 ``"selected"``, HIGH when
  ``hot_gas_bypass``).
- ``asc_orientation`` (DX HGBP)     <- engine ``asc_orientation`` (R-084 CONFLICT) -> stays
  blocked / deferred -> orientation omitted + annotated.

**The confidence gate is enforced HERE, not assumed from where the engine placed a field.**
Each datum is looked up wherever it sits in the response and RE-BUCKETED by its own
``confidence`` via :func:`bucket_for_confidence` — so a LOW/CONFLICT value can never reach the
drawable ``values`` bucket, even if a caller hands us a tampered response. Only ``values``
(HIGH) reach the flat ``slot_values`` the drawing engine reads.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from coilforge.schemas.header_prepopulate import (
    Confidence,
    FieldResult,
    HeaderPrepopulateResponse,
)
from coilforge.services.header_prepopulate_engine import bucket_for_confidence


@dataclass(frozen=True)
class GatedSlot:
    """One emitted topology slot, traced back to its engine field + confidence."""

    slot: str
    value: Any  # string / bool / enum; None when blocked
    confidence: Confidence
    source: str | None  # the engine field name, or None
    reason: str | None = None  # blocked_reason / review note


@dataclass(frozen=True)
class TopologySlotResult:
    """Tri-bucket sourcing outcome (mirrors HeaderPrepopulateResponse / DistributorSlotResult)."""

    values: dict[str, GatedSlot] = field(default_factory=dict)   # HIGH (drawable)
    review: dict[str, GatedSlot] = field(default_factory=dict)   # MEDIUM (value carried, flagged)
    blocked: dict[str, GatedSlot] = field(default_factory=dict)  # LOW/CONFLICT (value=None)
    notes: list[str] = field(default_factory=list)

    def gated_slot_values(self) -> dict[str, Any]:
        """HIGH-only flat slot dict — the only topology slots the drawing engine may draw."""
        return {gs.slot: gs.value for gs in self.values.values()}


# --------------------------------------------------------------------------- #
# Engine lookup — find a field wherever it sits, MOST-CONSERVATIVE first.
# --------------------------------------------------------------------------- #
def _find_field(response: HeaderPrepopulateResponse, name: str) -> FieldResult | None:
    """Return the FieldResult for ``name``, searching blocked -> suggestions -> values.

    Blocked-first is deliberate: a field that the engine emits in BOTH buckets (e.g. Terra V
    ``vent_drain`` — R-066 MEDIUM *and* R-067 LOW) resolves to the most conservative outcome.
    """
    for bucket in (response.blocked, response.suggestions, response.values):
        if name in bucket:
            return bucket[name]
    return None


def _emit(
    result: TopologySlotResult,
    slot: str,
    engine_field: str,
    response: HeaderPrepopulateResponse,
    *,
    transform: Any = None,
) -> None:
    """Source one slot from ``engine_field`` and route it by the confidence gate.

    The gate (``bucket_for_confidence``) is applied to the field's OWN confidence — never to
    the bucket the engine happened to place it in — so this stays fail-closed under a tampered
    response. ``transform`` optionally maps the raw engine value (e.g. ``"selected" -> True``)
    for the drawable (HIGH/MEDIUM) case; blocked always carries ``value=None``.
    """
    fr = _find_field(response, engine_field)
    if fr is None:
        result.notes.append(f"{slot}: engine emitted no {engine_field!r} -> omitted (review).")
        return
    bucket = bucket_for_confidence(fr.confidence)
    if bucket == "values":
        value = transform(fr.value) if transform else fr.value
        result.values[slot] = GatedSlot(slot, value, fr.confidence, engine_field)
    elif bucket == "suggestions":
        value = transform(fr.value) if transform else fr.value
        reason = fr.review_required_reason or "review_required (value carried, label-only)."
        result.review[slot] = GatedSlot(slot, value, fr.confidence, engine_field, reason)
    else:  # blocked (LOW | CONFLICT) -> value=None, omit + annotate
        result.blocked[slot] = GatedSlot(
            slot, None, fr.confidence, engine_field,
            fr.blocked_reason or f"{engine_field} blocked ({fr.confidence.value}).",
        )


def _selected_true(value: Any) -> bool:
    """R-083 emits ``asc = "selected"``; the drawing slot is a boolean presence flag."""
    return str(value).strip().lower() == "selected"


# --------------------------------------------------------------------------- #
# The sourcing function
# --------------------------------------------------------------------------- #
def topology_drawing_slots(
    *,
    engine_response: HeaderPrepopulateResponse,
    category: str,
    special: str | None = None,
) -> TopologySlotResult:
    """Source the per-category topology slots from the UPSTREAM (already-gated) engine response,
    re-gated fail-closed. ``category`` / ``special`` select which slots are relevant; the engine
    only emits a field when its rule applies, so an absent field is simply omitted (review note).
    """
    cat = str(category).strip().upper()
    sp = (str(special).strip().upper() or None) if special is not None else None
    result = TopologySlotResult()

    if cat == "HGRH":
        # conn_angle = "LAS" (R-047 HIGH).
        _emit(result, "slot.conn_angle", "conn_angle", engine_response)

    if cat in ("CWC", "HWC"):
        # vent_drain — R-066 MEDIUM (review) for all; R-067 LOW (blocked) on Terra V.
        _emit(result, "slot.vent_drain", "vent_drain", engine_response)

    if cat == "DX" and sp == "HGBP":
        # ASC selected (R-083 HIGH when hot_gas_bypass) -> drawable presence flag.
        _emit(result, "slot.HGBP", "asc", engine_response, transform=_selected_true)
        # ASC orientation (R-084 CONFLICT) -> stays blocked / deferred -> omit + annotate.
        _emit(result, "asc_orientation", "asc_orientation", engine_response)

    return result


def review_and_blocked_items(result: TopologySlotResult) -> Iterable[str]:
    """Human-readable review items for the pipeline's ``review_items`` list (mirrors the
    distributor wiring): each review/blocked slot + any notes, never the HIGH (drawable) ones."""
    for gs in result.review.values():
        yield f"review:{gs.slot}={gs.value} ({gs.reason})"
    for gs in result.blocked.values():
        yield f"blocked:{gs.slot} ({gs.reason})"
    yield from result.notes
