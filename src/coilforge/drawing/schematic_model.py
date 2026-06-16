"""Layer 1 — geometry model for the parametric drawing engine (real inches only).

This is the first of the three never-collapsed layers:

    [L1 model] CoilGeometry  ->  [L2 layout] FrontViewLayout  ->  [L3 backend] SVG

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
        return cls(
            casing_length=resolved["CL"],
            casing_height=resolved["CH"],
            finned_length=resolved["FL"],
            finned_height=resolved["FH"],
            top_flange=resolved["TF"],
            bottom_flange=resolved["BF"],
            header_flange=resolved["HF"],
            return_flange=resolved["RF"],
            coil_category=coil_category,
            coil_hand=coil_hand,
            header_type=header_type,
            special_feature=special_feature,
            omitted=omitted,
        )
