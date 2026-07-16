"""Build a structured performance-target summary to send Ambient for a quote (Feature 1).

Given the baseline submittal candidates, emit a compact per-coil spec of the performance
TARGETS Ambient must meet (geometry envelope + duty point), plus the Coil-Utilities
acceptable capacity/volume band for context. Pure data — a review aid the engineer copies
into the RFQ; no email is sent, nothing is exported.
"""
from __future__ import annotations

from typing import Any

from coilforge.coil_utilities.ranges import kit_for_btuh, ranges_for_kit, tons_for_kit
from coilforge.submittal.candidate import SubmittalCoilCandidate
from coilforge.submittal.pdf_intake import coil_category_of_tag

_TARGET_FIELDS: tuple[tuple[str, str, str, str | None], ...] = (
    # (label, group, key, unit)
    ("rows", "geometry", "rows", None),
    ("fins_per_inch", "geometry", "fins_per_inch", "fpi"),
    ("fin_height_in", "geometry", "finned_height_in", "in"),
    ("fin_length_in", "geometry", "finned_length_in", "in"),
    ("fin_surface", "materials_construction", "fin_surface", None),
    ("total_air_flow_cfm", "airside_conditions", "total_air_flow_cfm", "cfm"),
    ("entering_dry_bulb_f", "airside_conditions", "entering_dry_bulb_f", "degF"),
    ("entering_wet_bulb_f", "airside_conditions", "entering_wet_bulb_f", "degF"),
    ("leaving_dry_bulb_f", "airside_conditions", "leaving_dry_bulb_f", "degF"),
    ("capacity_mbh", "performance", "nominal_cooling_capacity_mbh", "MBH"),
)


def _val(cand: SubmittalCoilCandidate, group: str, key: str) -> Any:
    fv = getattr(cand, group, {}).get(key)
    return fv.value if fv is not None else None


def _band(cand: SubmittalCoilCandidate, category: str | None) -> dict[str, Any] | None:
    cap = _val(cand, "performance", "nominal_cooling_capacity_mbh")
    if cap is None:
        return None
    band = "heating" if category == "HGRH COIL" else "cooling"
    kit = kit_for_btuh(cap * 1000.0, 1, band=band)
    if kit is None:
        return None
    r = ranges_for_kit(kit, 1)
    if r is None:
        return None
    lo, hi = (r.heating_min_mbh, r.heating_max_mbh) if band == "heating" else (r.cooling_min_mbh, r.cooling_max_mbh)
    return {
        "ekexva_kit": f"EKEXVA{kit}U",
        "nominal_tons": tons_for_kit(kit),
        "capacity_band_mbh": [round(lo, 1), round(hi, 1)],
        "coil_volume_band_cuin": [r.volume_min_cuin, r.volume_max_cuin],
        "band_basis": band,
    }


def build_ambient_rfq(baseline: list[SubmittalCoilCandidate]) -> dict[str, Any]:
    """Per-coil performance targets + acceptance band for the Ambient RFQ (review aid)."""
    coils: list[dict[str, Any]] = []
    for cand in baseline:
        tag = cand.tag.value if cand.tag is not None else None
        if not tag:
            continue
        category = coil_category_of_tag(tag)
        targets = {}
        for label, group, key, unit in _TARGET_FIELDS:
            v = _val(cand, group, key)
            if v is not None:
                targets[label] = {"value": v, "unit": unit}
        coils.append({
            "tag": tag,
            "category": category,
            "targets": targets,
            "acceptance_band": _band(cand, category),
        })
    return {
        "coils": coils,
        "note": "Performance targets for an Ambient Dynamics RFQ. Review aid — verify before sending.",
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
        "review_required": True,
    }
