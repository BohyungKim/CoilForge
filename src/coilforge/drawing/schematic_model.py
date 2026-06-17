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

# Header/side-view slots (verified against slot_map.json + ez_json_drawing_loader.py and the
# real DX references EZC-0001 / EZC-0007). Headers are indexed by EZ id: ODD = supply/
# distributor, EVEN = return/suction. Each circuit k -> supply id 2k-1, return id 2k.
#   supply id : HDx{id} (header Ø), I{id} (offset from edge), S{id} (spacing along the depth)
#   return id : HD{id}, O{id}, R{id}, SL{id} (stub) + the shared RETURN_CONN_SIZE (sweat Ø)
# A DX distributor has no single sweat connection (EZ: Headers[supply].ConnectionSize=[0,0,0]),
# so the supply carries no connection_diameter — it is represented by labels (HDx + I + S).
_HEADER_SLOT_RE = re.compile(r"^slot\.(HDx|HD|SL|S|R|I|O)(\d+)$")
_RETURN_CONN_SLOT = "slot.RETURN_CONN_SIZE"

_REVIEW_REQUIRED = "REVIEW REQUIRED"


def _header_ids(slot_values: dict[str, Any]) -> list[int]:
    """Sorted unique EZ header ids present in the indexed side-view slots (e.g. ``[1, 2]``
    single-circuit, ``[1, 2, 3, 4, 5, 6]`` for a 3-circuit DX). ``RETURN_CONN_SIZE`` is a
    shared (un-indexed) slot and is intentionally not matched here."""
    ids: set[int] = set()
    for key in slot_values:
        match = _HEADER_SLOT_RE.match(str(key))
        if match:
            ids.add(int(match.group(2)))
    return sorted(ids)


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

    Indexed by EZ id (``index``): odd = supply/distributor, even = return. The real DX
    references (EZC-0001 / EZC-0007) show ``offset`` (I/O) is a per-row CONSTANT while
    ``spacing`` (S/R) is what positions each circuit along the depth — so both are carried.

    A field is ``None`` when its slot was missing / REVIEW REQUIRED — the side view
    drops + annotates that feature rather than inventing it.
    """

    role: str  # "supply" | "return"
    index: int  # EZ header id (odd = supply, even = return)
    diameter: float | None  # HDx{id} (supply) / HD{id} (return)
    offset: float | None  # I{id} (supply) / O{id} (return) — constant offset from the edge
    spacing: float | None  # S{id} (supply) / R{id} (return) — position along the depth
    stub_length: float | None  # SL{id} (return)
    connection_diameter: float | None  # RETURN_CONN_SIZE (return; shared sweat Ø)


def _make_header(slot_values: dict[str, Any], hid: int) -> HeaderSpec:
    """Build one indexed header from its gated slots. Odd id = supply/distributor
    (HDx/I/S, no stub or sweat connection per the EZ DX distributor rule); even id =
    return (HD/O/R/SL + the shared RETURN_CONN_SIZE sweat Ø)."""
    if hid % 2 == 1:  # supply / distributor
        return HeaderSpec(
            role="supply",
            index=hid,
            diameter=_slot_inches(slot_values, f"slot.HDx{hid}"),
            offset=_slot_inches(slot_values, f"slot.I{hid}"),
            spacing=_slot_inches(slot_values, f"slot.S{hid}"),
            stub_length=None,  # supply distributor has no stubout (per EZ data)
            connection_diameter=None,  # a distributor has no single sweat connection
        )
    return HeaderSpec(
        role="return",
        index=hid,
        diameter=_slot_inches(slot_values, f"slot.HD{hid}"),
        offset=_slot_inches(slot_values, f"slot.O{hid}"),
        spacing=_slot_inches(slot_values, f"slot.R{hid}"),
        stub_length=_slot_inches(slot_values, f"slot.SL{hid}"),
        connection_diameter=_slot_inches(slot_values, _RETURN_CONN_SLOT),
    )


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
        # One HeaderSpec per EZ id present (odd = supply, even = return). Default to the
        # single-circuit pair [1, 2] when no indexed header slots are present (back-compat).
        ids = _header_ids(slot_values) or [1, 2]
        headers = tuple(_make_header(slot_values, hid) for hid in ids)
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
            headers=headers,
            coil_category=coil_category,
            coil_hand=coil_hand,
            header_type=header_type,
            special_feature=special_feature,
            omitted=omitted,
        )
