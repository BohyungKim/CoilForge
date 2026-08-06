"""Kit lookup + acceptance ranges scaled by circuits, and the Allowable Ranges criteria.

The acceptance band for a coil = its EKEXVA kit's published min/max, multiplied by the
coil's circuit count (QTY). ``kit_for_cooling_btuh`` picks the kit whose cooling band
covers a design capacity; ``ranges_for_kit`` returns the scaled bands. Capacities are
BTU/h (Daikin's units) with MBH convenience properties; volumes are in^3.
"""
from __future__ import annotations

from dataclasses import dataclass

from coilforge.coil_utilities.charts import KitRow, R32_CHART

_CHARTS: dict[str, tuple[KitRow, ...]] = {"R32": R32_CHART}


def tons_for_kit(index: int) -> float:
    """Nominal tons = capacity index / 12."""
    return index / 12.0


@dataclass(frozen=True)
class KitRanges:
    """A kit's acceptance bands for a given circuit count (BTU/h + in^3)."""

    index: int
    circuits: int
    tons: float
    cooling_min_btuh: float
    cooling_max_btuh: float
    heating_min_btuh: float
    heating_max_btuh: float
    volume_min_cuin: float
    volume_max_cuin: float
    heating_nominal_btuh: float | None

    @property
    def cooling_min_mbh(self) -> float:
        return self.cooling_min_btuh / 1000.0

    @property
    def cooling_max_mbh(self) -> float:
        return self.cooling_max_btuh / 1000.0

    @property
    def heating_min_mbh(self) -> float:
        return self.heating_min_btuh / 1000.0

    @property
    def heating_max_mbh(self) -> float:
        return self.heating_max_btuh / 1000.0


def _chart(refrigerant: str) -> tuple[KitRow, ...]:
    return _CHARTS.get(refrigerant.upper(), ())


def ranges_for_kit(index: int, circuits: int = 1, *, refrigerant: str = "R32") -> KitRanges | None:
    """The kit's bands scaled by ``circuits``; ``None`` if the kit/refrigerant is unknown."""
    if circuits < 1:
        return None
    for row in _chart(refrigerant):
        if row.index == index:
            return KitRanges(
                index=index,
                circuits=circuits,
                tons=tons_for_kit(index),
                cooling_min_btuh=row.cooling_min * circuits,
                cooling_max_btuh=row.cooling_max * circuits,
                heating_min_btuh=row.heating_min * circuits,
                heating_max_btuh=row.heating_max * circuits,
                volume_min_cuin=row.volume_min * circuits,
                volume_max_cuin=row.volume_max * circuits,
                heating_nominal_btuh=(row.heating_nominal * circuits if row.heating_nominal is not None else None),
            )
    return None


def kit_for_btuh(value_btuh: float, circuits: int = 1, *, band: str = "cooling", refrigerant: str = "R32") -> int | None:
    """Pick the kit whose circuit-scaled ``band`` (cooling|heating) covers ``value_btuh``.

    If the value falls in a gap (or above/below the chart), return the smallest kit whose
    scaled max covers it (next size up), else the largest kit. ``None`` only if the chart
    is empty, circuits<1, or ``band`` is unknown.
    """
    chart = _chart(refrigerant)
    if not chart or circuits < 1 or band not in ("cooling", "heating"):
        return None
    lo_attr, hi_attr = f"{band}_min", f"{band}_max"
    for row in chart:
        lo = getattr(row, lo_attr) * circuits
        hi = getattr(row, hi_attr) * circuits
        if lo <= value_btuh <= hi:
            return row.index
    covering = [row for row in chart if getattr(row, hi_attr) * circuits >= value_btuh]
    if covering:
        return min(covering, key=lambda r: getattr(r, hi_attr)).index
    return chart[-1].index


def kit_for_cooling_btuh(cooling_btuh: float, circuits: int = 1, *, refrigerant: str = "R32") -> int | None:
    """Convenience: ``kit_for_btuh(..., band="cooling")``."""
    return kit_for_btuh(cooling_btuh, circuits, band="cooling", refrigerant=refrigerant)


@dataclass(frozen=True)
class AllowableRanges:
    """Qualitative acceptance criteria (the 'Allowable Ranges' sheet). Review references,
    not automated gates — a human judges against them."""

    tube_od_in: float = 0.375  # "Must be 3/8" 1"x0.866"
    fins_per_inch_max: int = 14
    fins_per_inch_ideal_max: int = 12
    fin_texture_allowed: tuple[str, ...] = ("Sine", "Flat")
    fin_texture_default: str = "Flat"
    face_velocity_min_fpm: float = 350.0
    face_velocity_max_fpm: float = 500.0
    face_velocity_ideal_fpm: tuple[float, float] = (400.0, 450.0)
    drop_tubes_max_pct: float = 0.10  # "Less than 10%"
    ref_pressure_drop_max: float = 10.0  # "Less than 10"
    ref_pressure_drop_ideal: tuple[float, float] = (6.0, 9.0)
    # Sheet defaults (E8/E9). NOTE: the sheet shows fin-thickness default 0.075, but real
    # coils (and Ambient PDFs) use 0.0075 — treat 0.075 as a likely sheet typo; kept here
    # as the raw sheet value, not used as a computed default.
    fin_thickness_default_sheet: float = 0.075
    tube_thickness_default: float = 0.016


ALLOWABLE_RANGES = AllowableRanges()


def classify_face_velocity(fpm: float | None) -> str:
    """'ideal' | 'acceptable' | 'out_of_range' | 'unknown' vs the Allowable Ranges band."""
    if fpm is None:
        return "unknown"
    a = ALLOWABLE_RANGES
    if a.face_velocity_ideal_fpm[0] <= fpm <= a.face_velocity_ideal_fpm[1]:
        return "ideal"
    if a.face_velocity_min_fpm <= fpm <= a.face_velocity_max_fpm:
        return "acceptable"
    return "out_of_range"
