"""Coil-Utilities-backed acceptance-range provider for the Ambient comparison.

Bridges ``coil_utilities`` (the ported data charts) into the ``mapping.RangeProvider``
contract: given a coil's design intent (baseline), pick its EKEXVA kit and return the
acceptable capacity / coil-volume band the Ambient value must fall inside.

Kit selection uses the BASELINE capacity (design intent). DX coils use the cooling band;
HGRH/condensing coils use the heating band. Circuits scale every band. When the design
capacity or a chart entry is missing, returns ``None`` -> the row degrades to
``cannot_evaluate`` (never a fabricated band). Review aid only; John confirms the kit.
"""
from __future__ import annotations

from coilforge.coil_utilities.ranges import kit_for_btuh, ranges_for_kit
from coilforge.submittal.candidate import SubmittalCoilCandidate
from coilforge.submittal.pdf_intake import coil_category_of_tag

_HGRH_CATEGORIES = frozenset({"HGRH COIL"})


def _val(cand: SubmittalCoilCandidate, group: str, key: str):
    fv = getattr(cand, group, {}).get(key)
    return fv.value if fv is not None else None


def _circuits(baseline: SubmittalCoilCandidate, ambient: SubmittalCoilCandidate) -> int:
    for cand in (baseline, ambient):
        c = _val(cand, "geometry", "circuits")
        if c:
            try:
                return max(1, int(c))
            except (TypeError, ValueError):
                pass
    return 1


def coil_utilities_range_provider(
    kind: str, baseline: SubmittalCoilCandidate, ambient: SubmittalCoilCandidate
) -> tuple[float, float] | None:
    """(kind, baseline, ambient) -> acceptable band, or None if not derivable.

    The kit (tonnage) is design intent — taken from the baseline capacity when the
    submittal carries it. Oxygen8 submittals often don't state per-coil capacity, so we
    fall back to the Ambient-returned capacity to select the kit; the coil-volume band
    check (does Ambient's volume match the kit's expected volume?) stays meaningful, which
    is the workbook's primary use. Never invents a capacity — if neither side has one,
    returns None -> cannot_evaluate."""
    design_cap_mbh = _val(baseline, "performance", "nominal_cooling_capacity_mbh")
    if design_cap_mbh is None:
        design_cap_mbh = _val(ambient, "performance", "nominal_cooling_capacity_mbh")
    if design_cap_mbh is None:
        return None
    circuits = _circuits(baseline, ambient)

    tag = baseline.tag.value if baseline.tag is not None else None
    category = coil_category_of_tag(tag) if tag else None
    band = "heating" if category in _HGRH_CATEGORIES else "cooling"

    kit = kit_for_btuh(design_cap_mbh * 1000.0, circuits, band=band)
    if kit is None:
        return None
    ranges = ranges_for_kit(kit, circuits)
    if ranges is None:
        return None

    if kind == "capacity":
        if band == "heating":
            return (ranges.heating_min_mbh, ranges.heating_max_mbh)
        return (ranges.cooling_min_mbh, ranges.cooling_max_mbh)
    if kind == "coil_volume":
        return (ranges.volume_min_cuin, ranges.volume_max_cuin)
    return None
