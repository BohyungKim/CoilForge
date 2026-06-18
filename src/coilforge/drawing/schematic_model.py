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
from collections.abc import Mapping, Sequence
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
    # V3 distributor extras (supply/odd id only; HIGH from slot_values, review from dist_review).
    extension_in: float | None = None  # DistExtension{id} — distributor stem stub (HIGH)
    nozzle_spec: str | None = None  # DistModel{id} — distributor model string (review, label-only)
    feeder_od_in: float | None = None  # DistOD{id} — feeder/tube OD (review; sizes the circle)


def _review_num(dist_review: Mapping[str, Any], key: str) -> float | None:
    """Leading numeric inches for a review-bucket slot (e.g. ``slot.DistOD1``), gated like
    ``_slot_inches`` — None when missing / "REVIEW REQUIRED" / unparseable. The review bucket
    carries the value; it is drawn FLAGGED, never as a confirmed dimension."""
    value = dist_review.get(key)
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.upper() == _REVIEW_REQUIRED:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def _make_header(
    slot_values: dict[str, Any], hid: int, dist_review: Mapping[str, Any]
) -> HeaderSpec:
    """Build one indexed header from its gated slots. Odd id = supply/distributor
    (HDx/I/S, no stub or sweat connection per the EZ DX distributor rule); even id =
    return (HD/O/R/SL + the shared RETURN_CONN_SIZE sweat Ø).

    The supply/distributor also carries the V3 extras: ``extension_in`` (DistExtension, HIGH,
    from the flat gated ``slot_values``) and the review-bucket ``nozzle_spec`` (DistModel,
    opaque string) / ``feeder_od_in`` (DistOD) from ``dist_review`` — drawn FLAGGED downstream."""
    if hid % 2 == 1:  # supply / distributor
        model = dist_review.get(f"slot.DistModel{hid}")
        return HeaderSpec(
            role="supply",
            index=hid,
            diameter=_slot_inches(slot_values, f"slot.HDx{hid}"),
            offset=_slot_inches(slot_values, f"slot.I{hid}"),
            spacing=_slot_inches(slot_values, f"slot.S{hid}"),
            stub_length=None,  # supply distributor has no stubout (per EZ data)
            connection_diameter=None,  # a distributor has no single sweat connection
            extension_in=_slot_inches(slot_values, f"slot.DistExtension{hid}"),  # HIGH (gated)
            nozzle_spec=str(model).strip() if model not in (None, "") else None,  # review
            feeder_od_in=_review_num(dist_review, f"slot.DistOD{hid}"),  # review
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
    # V3 distributor plan-view extras (additive; default keeps front/side identical).
    airflow: str | None = None  # slot.AIRFLOW enum (raw, NOT inches) — drives the AIRFLOW arrow
    dist_review_labels: tuple[str, ...] = ()  # dist features sourced from the review bucket (flagged)
    dist_blocked: tuple[str, ...] = ()  # blocked dist slots (e.g. conflicted DistExtension) — annotate
    # Phase-5a per-category topology data (gated upstream; CARRIED for the 5b glyphs, not drawn in
    # 5a). HIGH (conn_angle/hgbp_selected) ride in slot_values; vent_drain is review-bucket; blocked
    # slots (asc_orientation CONFLICT, Terra V vent_drain LOW) are listed for omit + annotate.
    conn_angle: str | None = None  # slot.conn_angle (HGRH, R-047 HIGH "LAS")
    vent_drain: str | None = None  # slot.vent_drain (CWC/HWC, R-066 MEDIUM/review — flagged)
    hgbp_selected: bool | None = None  # slot.HGBP (DX HGBP, R-083 HIGH)
    topo_review_labels: tuple[str, ...] = ()  # topology features sourced from the review bucket
    topo_blocked: tuple[str, ...] = ()  # blocked topology slots — omit + annotate

    @classmethod
    def from_slot_values(
        cls,
        slot_values: dict[str, Any],
        *,
        coil_category: str,
        coil_hand: str,
        header_type: str,
        special_feature: str | None,
        dist_review: Mapping[str, Any] | None = None,
        dist_blocked: Sequence[str] | None = None,
        topo_review: Mapping[str, Any] | None = None,
        topo_blocked: Sequence[str] | None = None,
    ) -> CoilGeometry:
        """Build the inches model from gated slots. ``dist_review`` carries the review-bucket
        distributor values (``slot.DistModel{id}`` / ``slot.DistOD{id}``) — drawn FLAGGED, never
        as confirmed dimensions; ``dist_blocked`` lists blocked dist slots to omit + annotate. HIGH
        distributor slots (``slot.AIRFLOW``, ``slot.DistExtension{id}``) ride in ``slot_values``.

        ``topo_review`` / ``topo_blocked`` carry the Phase-5a per-category topology data (gated
        upstream): HIGH ``slot.conn_angle`` / ``slot.HGBP`` ride in ``slot_values``; review
        ``slot.vent_drain`` rides in ``topo_review``; blocked slots (``asc_orientation``, Terra V
        ``slot.vent_drain``) are listed in ``topo_blocked``. These are CARRIED for the 5b glyphs —
        5a does not render them (no new glyph)."""
        dist_review = dist_review or {}
        topo_review = topo_review or {}
        resolved = {label: _slot_inches(slot_values, key) for label, key in _SLOT_KEYS.items()}
        omitted = tuple(label for label, value in resolved.items() if value is None)
        # One HeaderSpec per EZ id present (odd = supply, even = return). Default to the
        # single-circuit pair [1, 2] when no indexed header slots are present (back-compat).
        ids = _header_ids(slot_values) or [1, 2]
        headers = tuple(_make_header(slot_values, hid, dist_review) for hid in ids)
        # AIRFLOW is an explicit enum string, NOT inches — read raw (the gate would null it).
        airflow_raw = slot_values.get("slot.AIRFLOW")
        airflow = str(airflow_raw).strip() if airflow_raw not in (None, "") else None
        review_labels = tuple(
            key.replace("slot.", "") for key in dist_review if str(key).startswith("slot.")
        )
        # Phase-5a topology data — HIGH ride in slot_values (raw, like airflow; the inch gate
        # would null these non-numeric values), review rides in topo_review. Carried for 5b.
        conn_angle_raw = slot_values.get("slot.conn_angle")
        conn_angle = str(conn_angle_raw).strip() if conn_angle_raw not in (None, "") else None
        hgbp_raw = slot_values.get("slot.HGBP")
        hgbp_selected = bool(hgbp_raw) if hgbp_raw is not None else None
        vent_drain_raw = topo_review.get("slot.vent_drain")
        vent_drain = str(vent_drain_raw).strip() if vent_drain_raw not in (None, "") else None
        topo_review_labels = tuple(
            key.replace("slot.", "") for key in topo_review if str(key).startswith("slot.")
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
            headers=headers,
            coil_category=coil_category,
            coil_hand=coil_hand,
            header_type=header_type,
            special_feature=special_feature,
            omitted=omitted,
            airflow=airflow,
            dist_review_labels=review_labels,
            dist_blocked=tuple(dist_blocked or ()),
            conn_angle=conn_angle,
            vent_drain=vent_drain,
            hgbp_selected=hgbp_selected,
            topo_review_labels=topo_review_labels,
            topo_blocked=tuple(topo_blocked or ()),
        )
