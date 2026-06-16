"""Layer 1 — geometry model for the parametric drawing engine (real inches only).

This is the first of the three never-collapsed layers:

    [L1 model] CoilGeometry  ->  [L2 layout] ViewLayout  ->  [L3 backend] SVG

``CoilGeometry`` carries true dimensions in inches and nothing else: no pixels, no
SVG/DXF knowledge, no presentation scale. It is built from gated ``slot_values`` that
were already resolved and confidence-gated upstream — the model never invents a value.
A slot that is missing, ``None``, ``""`` or ``"REVIEW REQUIRED"`` resolves to ``None``
and its label is recorded in ``omitted`` so downstream layers can drop + annotate the
feature instead of guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Drawing-label -> slot key. The model exposes the front-view dimensions the DX
# layout needs; per-header / circuiting slots are out of scope for the front view.
_SLOT_KEYS: dict[str, str] = {
    "CL": "slot.CL",
    "CH": "slot.CH",
    "FL": "slot.FL",
    "FH": "slot.FH",
    "TF": "slot.TF",
    "BF": "slot.BF",
    "HF": "slot.HF",
    "RF": "slot.RF",
}

# Header/side-view slots (verified against slot_map.json + ez_json_drawing_loader.py).
# Header id 1 = supply/distributor (odd), id 2 = return/suction (even).
_SUPPLY_SLOTS = {
    "diameter": "slot.HDx1",
    "offset": "slot.I1",
    "connection_diameter": "slot.SUPPLY_CONN_SIZE",
}
_RETURN_SLOTS = {
    "diameter": "slot.HD2",
    "offset": "slot.O2",
    "stub_length": "slot.SL2",
    "connection_diameter": "slot.RETURN_CONN_SIZE",
}

_REVIEW_REQUIRED = "REVIEW REQUIRED"


def _slot_inches(slot_values: dict[str, Any], key: str) -> float | None:
    """Leading numeric inches for a slot, or ``None`` when it is not a real value.

    Gate enforcement lives here: ``None`` / ``""`` / ``"REVIEW REQUIRED"`` /
    unparseable -> ``None``. Never invents a value. (We intentionally do not import
    ``_conn_float`` from the frozen ``pdf_to_template_drawing`` module.)
    """
    value = slot_values.get(key)
    if value is None:
        return None
    if isinstance(value, bool):  # guard: bool is an int subclass
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.upper() == _REVIEW_REQUIRED:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def _slot_int(slot_values: dict[str, Any], key: str) -> int | None:
    value = _slot_inches(slot_values, key)
    return int(value) if value is not None else None


@dataclass(frozen=True)
class HeaderSpec:
    """One header/connection at the coil's header end, in inches. No pixels.

    A field is ``None`` when its slot was missing / REVIEW REQUIRED — the side view
    drops + annotates that feature rather than inventing it.
    """

    role: str  # "supply" | "return"
    diameter: float | None  # HDx1 (supply) / HD2 (return)
    offset: float | None  # I1 (supply) / O2 (return) — vertical position, review-aid datum
    stub_length: float | None  # SL2 (return)
    connection_diameter: float | None  # RETURN_CONN_SIZE (return)


@dataclass(frozen=True)
class CoilGeometry:
    """A coil's real-world dimensions in inches. No pixels, no renderer types."""

    # outer casing
    casing_length: float | None  # CL
    casing_height: float | None  # CH
    # inset finned face
    finned_length: float | None  # FL
    finned_height: float | None  # FH
    # face offsets (flange datums)
    top_flange: float | None  # TF
    bottom_flange: float | None  # BF
    header_flange: float | None  # HF
    return_flange: float | None  # RF
    # header / end-view geometry
    casing_depth: float | None  # CD
    rows: int | None  # ROWS
    headers: tuple[HeaderSpec, ...]  # supply (id 1), return (id 2) for DX
    # long-axis overalls (return-bend end)
    return_bend: float | None  # RB — bend allowance beyond the casing at the return end
    overall_length: float | None  # OAL — casing length + return bend
    # context (carried through for downstream layers / metadata)
    coil_category: str
    coil_hand: str
    header_type: str
    special_feature: str | None
    # drawing labels whose slot was missing / REVIEW REQUIRED (dropped, not invented)
    omitted: tuple[str, ...]

    @classmethod
    def from_slot_values(
        cls,
        slot_values: dict[str, Any],
        *,
        coil_category: str,
        coil_hand: str,
        header_type: str,
        special_feature: str | None,
    ) -> CoilGeometry:
        resolved = {label: _slot_inches(slot_values, key) for label, key in _SLOT_KEYS.items()}
        omitted = tuple(label for label, value in resolved.items() if value is None)
        supply = HeaderSpec(
            role="supply",
            diameter=_slot_inches(slot_values, _SUPPLY_SLOTS["diameter"]),
            offset=_slot_inches(slot_values, _SUPPLY_SLOTS["offset"]),
            stub_length=None,  # supply distributor has no stubout (per EZ data)
            connection_diameter=_slot_inches(slot_values, _SUPPLY_SLOTS["connection_diameter"]),
        )
        return_header = HeaderSpec(
            role="return",
            diameter=_slot_inches(slot_values, _RETURN_SLOTS["diameter"]),
            offset=_slot_inches(slot_values, _RETURN_SLOTS["offset"]),
            stub_length=_slot_inches(slot_values, _RETURN_SLOTS["stub_length"]),
            connection_diameter=_slot_inches(slot_values, _RETURN_SLOTS["connection_diameter"]),
        )
        return cls(
            casing_length=resolved["CL"],
            casing_height=resolved["CH"],
            finned_length=resolved["FL"],
            finned_height=resolved["FH"],
            top_flange=resolved["TF"],
            bottom_flange=resolved["BF"],
            header_flange=resolved["HF"],
            return_flange=resolved["RF"],
            casing_depth=_slot_inches(slot_values, "slot.CD"),
            rows=_slot_int(slot_values, "slot.ROWS"),
            headers=(supply, return_header),
            return_bend=_slot_inches(slot_values, "slot.RB"),
            overall_length=_slot_inches(slot_values, "slot.OAL"),
            coil_category=coil_category,
            coil_hand=coil_hand,
            header_type=header_type,
            special_feature=special_feature,
            omitted=omitted,
        )
