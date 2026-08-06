"""Phase 4a — UPSTREAM sourcing of the V3 distributor drawing slots (no drawing).

Emits four new gated drawing slots so the parametric engine can consume them GATED in
Phase 4b (`docs/design/ez-drawing-model.md §6`):

- ``slot.AIRFLOW``          — from the explicit ``airflow_direction`` (HIGH; never derived).
- ``slot.DistExtension{id}``— rule-engine ``dist_extension`` PRIMARY (R-033), EZ-JSON
  ``Headers[supply].DistExtension`` overrides when present, the drawing callout
  ``"DISTRIBUTOR N HAS X\" EXTENSION"`` is a CROSS-CHECK. **Fail-closed:** a callout that
  disagrees with the chosen value blocks (CONFLICT) — never silently HIGH.
- ``slot.DistModel{id}``    — distributor model string (``distributors_display`` / EZ JSON);
  review_required, **label-only** (no geometry parsed from the string).
- ``slot.DistOD{id}``       — feeder OD from ``distributors_display`` (e.g. ``OD:5/8``);
  review_required until John signs the display-string mapping off.

This module is a pure function: inputs -> result object, no I/O, no drawing/layout/backend
code, no ``eval``. Gating semantics mirror the header engine
(`HeaderPrepopulateResponse.values/suggestions/blocked` + `bucket_for_confidence`): HIGH ->
``values`` (the engine may consume these gated), MEDIUM -> ``review`` (value carried, surfaced),
LOW/CONFLICT -> ``blocked`` (``value=None`` + reason). Only ``values`` reach the flat
``slot_values`` the drawing engine reads.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from coilforge.schemas.header_prepopulate import Confidence, HeaderPrepopulateResponse

_TOL = 0.01  # inches; matches json_drawing_link_rules tolerance_in


@dataclass(frozen=True)
class GatedSlot:
    """One emitted distributor slot, fully traced back to its source."""

    slot: str
    value: Any  # number / string / enum; None when blocked
    confidence: Confidence
    source: str | None  # "engine" | "ez_json" | "distributors_display" | "callout" | "airflow_direction"
    reason: str | None = None  # blocked_reason / review note


@dataclass(frozen=True)
class DistributorSlotResult:
    """Tri-bucket sourcing outcome (mirrors HeaderPrepopulateResponse)."""

    values: dict[str, GatedSlot] = field(default_factory=dict)   # HIGH
    review: dict[str, GatedSlot] = field(default_factory=dict)   # review_required (value carried)
    blocked: dict[str, GatedSlot] = field(default_factory=dict)  # CONFLICT/LOW (value=None)
    notes: list[str] = field(default_factory=list)

    def gated_slot_values(self) -> dict[str, Any]:
        """HIGH-only flat slot dict — the only distributor slots the drawing engine may draw."""
        return {gs.slot: gs.value for gs in self.values.values()}


# --------------------------------------------------------------------------- #
# Pure parse helpers (never eval)
# --------------------------------------------------------------------------- #
def _num(value: Any) -> float | None:
    """Leading numeric inches for a scalar/string; None when not a real value."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def _fraction_to_float(text: Any) -> float | None:
    """Parse ``5/8`` -> 0.625, ``1-1/2`` -> 1.5, ``0.625`` -> 0.625, ``6"`` -> 6.0."""
    s = str(text).strip().strip('"').strip()
    if not s:
        return None
    mixed = re.fullmatch(r"(\d+)[ \-](\d+)/(\d+)", s)
    if mixed:
        whole, num, den = (int(g) for g in mixed.groups())
        return whole + num / den if den else None
    frac = re.fullmatch(r"(\d+)/(\d+)", s)
    if frac:
        num, den = int(frac.group(1)), int(frac.group(2))
        return num / den if den else None
    lead = re.search(r"\d+(?:\.\d+)?", s)
    return float(lead.group(0)) if lead else None


def _parse_extension_callout(callouts: Sequence[Any], dist_id: int) -> float | None:
    """Inches from ``DISTRIBUTOR <dist_id> HAS <X>" EXTENSION`` if that callout is present."""
    for callout in callouts:
        match = re.search(
            r"DISTRIBUTOR\s+(\d+)\s+HAS\s+(.+?)\s*EXTENSION", str(callout), re.IGNORECASE
        )
        if match and int(match.group(1)) == dist_id:
            return _fraction_to_float(match.group(2))
    return None


def _clean_model(rest: str) -> str:
    """First model token (up to a space or ``(``), e.g. ``501-2-3/16-1.5(0 ASC)`` -> ``501-2-3/16-1.5``."""
    return re.split(r"[ (]", rest.strip(), maxsplit=1)[0].strip()


def _parse_distributors_display(display: Sequence[Any]) -> list[tuple[int, str, float | None]]:
    """``["(1)501-2-3/16-1.5(0 ASC)", "OD:5/8"]`` -> ``[(1, "501-2-3/16-1.5", 0.625)]``.

    Each ``(N)model`` entry yields (quantity, model, OD); a bare ``OD:x`` line supplies a
    shared OD when a model line carries none. Returned in source order.
    """
    models: list[tuple[int, str, float | None]] = []
    global_od: float | None = None
    for entry in display:
        s = str(entry)
        od_here: float | None = None
        od_match = re.search(r"OD\s*:\s*([0-9./\- ]+)", s, re.IGNORECASE)
        if od_match:
            od_here = _fraction_to_float(od_match.group(1))
            if global_od is None:
                global_od = od_here
        model_match = re.match(r"\s*\((\d+)\)\s*(.+)", s)
        if model_match:
            qty = int(model_match.group(1))
            rest = re.sub(r"OD\s*:.*$", "", model_match.group(2), flags=re.IGNORECASE)
            models.append((qty, _clean_model(rest), od_here))
    return [(q, m, od if od is not None else global_od) for q, m, od in models]


def _display_by_supply_id(
    parsed: list[tuple[int, str, float | None]], supply_ids: Sequence[int]
) -> tuple[dict[int, tuple[str, float | None]], bool]:
    """Expand ``(qty, model, od)`` entries across the present supply ids, in order.

    Returns (mapping id -> (model, od), ambiguous) where ``ambiguous`` is True when the
    listed quantities do not total the number of supply ids (best-effort + review note).
    """
    expanded: list[tuple[str, float | None]] = []
    for qty, model, od in parsed:
        expanded.extend([(model, od)] * max(1, qty))
    mapping: dict[int, tuple[str, float | None]] = {}
    for i, sid in enumerate(supply_ids):
        if i < len(expanded):
            mapping[sid] = expanded[i]
        elif expanded:
            mapping[sid] = expanded[-1]
    ambiguous = bool(expanded) and len(expanded) != len(supply_ids)
    return mapping, ambiguous


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= _TOL


# --------------------------------------------------------------------------- #
# The sourcing function
# --------------------------------------------------------------------------- #
def distributor_drawing_slots(
    *,
    engine_response: HeaderPrepopulateResponse,
    supply_ids: Sequence[int],
    ez_headers: Sequence[Mapping[str, Any]] | None = None,
    display: Mapping[str, Any] | None = None,
) -> DistributorSlotResult:
    """Source the four V3 distributor slots from UPSTREAM data, gated and fail-closed.

    ``supply_ids`` are the odd EZ header ids present (e.g. ``[1]`` or ``[1, 3, 5]``).
    ``ez_headers`` is the raw ``Geometry.Headers[]`` array when an EZ JSON exists (often
    absent for real DX). ``display`` carries ``drawing_callouts`` / ``distributors_display``
    / ``airflow_direction`` from the canonical/state object. The drawing engine never reads
    any of these directly — only the gated result.
    """
    display = display or {}
    callouts = display.get("drawing_callouts") or []
    dist_display = display.get("distributors_display") or []
    airflow = display.get("airflow_direction")
    ez_by_id: dict[int, Mapping[str, Any]] = {
        int(h["ID"]): h for h in (ez_headers or []) if isinstance(h, Mapping) and "ID" in h
    }

    result = DistributorSlotResult()

    # --- slot.AIRFLOW: explicit direction only, never derived from hand/category ---
    if airflow is not None and str(airflow).strip():
        result.values["slot.AIRFLOW"] = GatedSlot(
            "slot.AIRFLOW", str(airflow).strip(), Confidence.HIGH, "airflow_direction"
        )
    else:
        result.notes.append("slot.AIRFLOW: airflow_direction missing -> omitted (review).")

    # --- engine dist_extension (PRIMARY base, shared across distributors) ---
    engine_fr = engine_response.values.get("dist_extension")
    engine_ext = _num(engine_fr.value) if engine_fr is not None else None

    parsed_display = _parse_distributors_display(dist_display)
    display_by_id, ambiguous = _display_by_supply_id(parsed_display, supply_ids)
    if ambiguous:
        result.notes.append(
            "distributors_display quantities do not total the supply ids -> "
            "per-id model/OD mapping is best-effort (review)."
        )

    for sid in supply_ids:
        _source_dist_extension(result, sid, engine_ext, ez_by_id.get(sid), callouts)
        _source_dist_model_od(result, sid, display_by_id.get(sid), ez_by_id.get(sid))

    return result


def _source_dist_extension(
    result: DistributorSlotResult,
    sid: int,
    engine_ext: float | None,
    ez_header: Mapping[str, Any] | None,
    callouts: Sequence[Any],
) -> None:
    slot = f"slot.DistExtension{sid}"
    ez_ext = _num(ez_header.get("DistExtension")) if ez_header else None
    chosen = ez_ext if ez_ext is not None else engine_ext
    source = "ez_json" if ez_ext is not None else ("engine" if engine_ext is not None else None)
    callout_ext = _parse_extension_callout(callouts, sid)

    if chosen is None:
        result.notes.append(f"{slot}: no engine/JSON DistExtension -> omitted (review).")
        return
    if callout_ext is not None and not _close(callout_ext, chosen):
        result.blocked[slot] = GatedSlot(
            slot, None, Confidence.CONFLICT, "callout",
            f"DistExtension{sid} CONFLICT: {source}={chosen:g} vs callout={callout_ext:g}",
        )
        return
    result.values[slot] = GatedSlot(slot, chosen, Confidence.HIGH, source)
    if ez_ext is not None and engine_ext is not None and not _close(ez_ext, engine_ext):
        result.notes.append(
            f"{slot}: EZ-JSON {ez_ext:g} overrides engine {engine_ext:g} (review)."
        )


def _source_dist_model_od(
    result: DistributorSlotResult,
    sid: int,
    display_entry: tuple[str, float | None] | None,
    ez_header: Mapping[str, Any] | None,
) -> None:
    model = display_entry[0] if display_entry else None
    od = display_entry[1] if display_entry else None
    if not model and ez_header:
        raw = ez_header.get("DistributorModelNumber")
        model = str(raw) if raw else None

    if model:
        result.review[f"slot.DistModel{sid}"] = GatedSlot(
            f"slot.DistModel{sid}", model, Confidence.MEDIUM, "distributors_display",
            "review: display-string model mapping unconfirmed (label-only).",
        )
    else:
        result.notes.append(f"slot.DistModel{sid}: no distributor model -> omitted.")

    if od is not None:
        result.review[f"slot.DistOD{sid}"] = GatedSlot(
            f"slot.DistOD{sid}", od, Confidence.MEDIUM, "distributors_display",
            "review: display-string OD mapping unconfirmed.",
        )
    else:
        result.notes.append(f"slot.DistOD{sid}: no feeder OD -> omitted.")
