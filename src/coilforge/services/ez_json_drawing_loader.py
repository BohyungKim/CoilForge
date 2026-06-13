"""Apply the JSON -> drawing link registry to an EZ Coil export.

Turns the link-rule registry (json_drawing_link_rules.yaml) into working code:
given an EZ Coil selection JSON (either schema), produce the drawing slot values
it can legitimately source, following the STRONG rules and the confirmed
Headers[] pair pattern, and never sourcing from the forbidden top-level fields.

This is the JSON-sourced complement to the header rule engine: when an EZ JSON
exists, geometry/connection slots come from it; rule-driven header constants and
any JSON-absent values come from the prepopulation engine.
"""

from __future__ import annotations

import re
from typing import Any

from coilforge.services.json_drawing_link import load_link_registry

_TOKEN_RE = re.compile(r"([A-Za-z][A-Za-z0-9]*)\s*=\s*([0-9]+(?:\.[0-9]+)?|[A-Za-z]+)")

_NOTES_TOKENS = {"I1", "S1", "SL1", "O2", "R2", "HD2", "SL2", "SupConnAngle"}


def detect_schema(data: dict[str, Any]) -> str:
    """'geometry' | 'physicaldata' | 'unknown'."""
    if "Geometry" in data:
        return "geometry"
    if "PhysicalData" in data:
        return "physicaldata"
    return "unknown"


def slots_from_ez_json(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return (slot_values, provenance_notes) sourced per the link registry."""
    schema = detect_schema(data)
    if schema == "geometry":
        return _slots_geometry(data["Geometry"])
    if schema == "physicaldata":
        return _slots_physicaldata(data)
    return {}, ["unknown_schema: no Geometry or PhysicalData object"]


def _slots_geometry(geom: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    registry = load_link_registry()
    slots: dict[str, Any] = {}
    notes: list[str] = []

    # Direct fin/casing/flange links (registry-driven).
    for entry in registry["direct_links"]:
        key = str(entry["source"]).split(".", 1)[1]  # "Geometry.FH" -> "FH"
        value = geom.get(key)
        if value not in (None, "", 0.0, 0) or key in ("CD", "CL", "CH"):
            if value is not None:
                slots[entry["slot"]] = value

    # Header connection links: per-header from Geometry.Headers[] (NEVER the
    # forbidden top-level Geometry.I/O/S/R/SL). Odd id = supply/distributor,
    # even id = return; drawing label index == header ID.
    for header in geom.get("Headers") or []:
        if not header:
            continue
        hid = header.get("ID")
        io0 = (header.get("IO") or [None])[0]
        sl0 = (header.get("SL") or [None])[0]
        if header.get("IsSupply"):
            slots[f"slot.I{hid}"] = io0
            slots[f"slot.S{hid}"] = header.get("SR")
            slots[f"slot.HDx{hid}"] = header.get("HD")
            if header.get("IsASC"):
                notes.append(f"header {hid}: IsASC=true -> HGBP/ASC (review naming).")
        else:
            slots[f"slot.O{hid}"] = io0
            slots[f"slot.R{hid}"] = header.get("SR")
            slots[f"slot.SL{hid}"] = sl0
            slots[f"slot.HD{hid}"] = header.get("HD")

    # OAL is derived (not stored) -> review item, never auto-sourced.
    notes.append("slot.OAL: derived (Geometry.OAL not stored) -> review_required.")
    return {k: v for k, v in slots.items() if v is not None}, notes


def _slots_physicaldata(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    physical = data["PhysicalData"]
    construction = data.get("Construction") or {}
    notes_text = construction.get("notes") or ""
    slots: dict[str, Any] = {}
    provenance: list[str] = []

    if physical.get("finHeight") is not None:
        slots["slot.FH"] = _to_number(physical["finHeight"])
    if physical.get("finLength") is not None:
        slots["slot.FL"] = _to_number(physical["finLength"])

    # Header tokens only exist for single-feed coils.
    if "Add Headers & Stubouts" in notes_text:
        for key, value in _TOKEN_RE.findall(notes_text):
            if key in _NOTES_TOKENS:
                slots[f"slot.{key}"] = _to_number(value)
    else:
        provenance.append(
            "physicaldata multi-feed / no header tokens -> header geometry not "
            "in JSON; use prepopulation engine."
        )
    return slots, provenance


def _to_number(value: Any) -> Any:
    try:
        f = float(value)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return value
