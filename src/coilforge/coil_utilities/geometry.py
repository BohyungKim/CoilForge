"""Coil geometry engine — the left-block calculators shared across the workbook.

Ports the identical formulas the ``R32`` / ``R410a`` sheets use (cols C9–C14) plus the
``Extras`` heating-capacity calc. Pure and deterministic; every function returns
``None`` when a required input is missing (never invents). Tube OD is 3/8" (the
workbook + Allowable Ranges hard rule "Tube Geometry must be 3/8" 1"x0.866").
"""
from __future__ import annotations

import math

DEFAULT_TUBE_OD_IN = 0.375


def passes(*, fin_height: float | None, rows: float | None, feeds: float | None) -> int | None:
    """Even number of tube passes: ROUNDDOWN(Rows*FinHeight/Feeds/2,0)*2."""
    if fin_height is None or rows is None or feeds in (None, 0):
        return None
    return math.floor(rows * fin_height / feeds / 2) * 2


def _total_tubes(fin_height: float, rows: float) -> float:
    # C11 = FLOOR.MATH(FinHeight) * Rows
    return math.floor(fin_height) * rows


def drop_tubes(*, fin_height: float | None, rows: float | None, feeds: float | None) -> float | None:
    """Leftover tubes not fed: FinHeight*Rows - Feeds*Passes (C10)."""
    p = passes(fin_height=fin_height, rows=rows, feeds=feeds)
    if p is None:
        return None
    return fin_height * rows - feeds * p


def pct_drop_tubes(*, fin_height: float | None, rows: float | None, feeds: float | None) -> float | None:
    """Drop tubes as a fraction of total tubes (C12) — compare vs Allowable <10%."""
    d = drop_tubes(fin_height=fin_height, rows=rows, feeds=feeds)
    if d is None:
        return None
    total = _total_tubes(fin_height, rows)
    if total == 0:
        return None
    return d / total


def coil_volume_cuin(
    *,
    feeds: float | int | None,
    fin_height: float | int | None,
    rows: float | int | None,
    fin_length: float | int | None,
    tube_thickness_in: float | int | None,
    tube_od_in: float = DEFAULT_TUBE_OD_IN,
) -> float | None:
    """Internal tube volume [in^3] — the workbook's C13 formula (with the ×1.1 factor).

    ``volume = (Feeds*Passes*π*bore²*FinLength/4 + Feeds*(Passes-1)*π*(bore/2)²*(1.5+π/2)) * 1.1``
    where ``bore = OD - 2*thk`` and ``Passes = floor(Rows*FinHeight/Feeds/2)*2``.
    Returns ``None`` on any missing input.
    """
    if None in (feeds, fin_height, rows, fin_length, tube_thickness_in) or feeds == 0:
        return None
    p = math.floor(rows * fin_height / feeds / 2) * 2  # Passes
    bore = tube_od_in - 2 * tube_thickness_in
    straight = feeds * p * math.pi * bore**2 * fin_length / 4
    bends = feeds * (p - 1) * math.pi * (bore / 2) ** 2 * (1.5 + math.pi / 2)
    return (straight + bends) * 1.1


def face_area_sqft(*, fin_height: float | None, fin_length: float | None) -> float | None:
    """Coil face area: FinHeight*FinLength/144 (C14 / Extras)."""
    if fin_height is None or fin_length is None:
        return None
    return fin_height * fin_length / 144.0


# Extras heating-capacity: kW = 1.085*(LAT-EAT)*CFM*0.000293071 ; MBH = kW*3.41214.
_HEATING_KW_COEFF = 1.085 * 0.000293071
_KW_TO_MBH = 3.41214


def heating_capacity_mbh(*, eat_f: float | None, lat_f: float | None, cfm: float | None) -> float | None:
    """Sensible heating capacity [MBH] from air conditions (Extras B11 calc)."""
    if eat_f is None or lat_f is None or cfm is None:
        return None
    kw = _HEATING_KW_COEFF * (lat_f - eat_f) * cfm
    return kw * _KW_TO_MBH
