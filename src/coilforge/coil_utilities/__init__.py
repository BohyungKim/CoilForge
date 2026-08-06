"""Coil Utilities — Oxygen8's internal coil data charts, ported to a reusable table.

Source: ``Coil Utilities - HWC DX.xlsx`` (the workbook an engineer uses to derive a
coil's acceptable **capacity / coil-volume / refrigerant-charge ranges** from its
geometry and Daikin EKEXVA valve kit = tonnage). This package is the single, reusable
home for that logic so it is available across CoilForge (the Ambient quote comparison
consumes it as an acceptance-range provider, but it is deliberately supplier-agnostic).

Layers (pure, no I/O):
- ``geometry`` — coil geometry engine: internal Volume (in^3), passes, drop tubes,
  % drop, face area, and the Extras heating-capacity calc.
- ``charts`` — the raw per-kit source charts (R32, R410a) as structured data.
- ``ranges`` — kit lookup (index<->tonnage), per-kit min/max bands scaled by circuits,
  and the qualitative "Allowable Ranges" acceptance criteria.

Everything is a **review aid**: the ranges are engineering references for a human to
judge against; nothing here approves or exports.
"""
from __future__ import annotations

from coilforge.coil_utilities.charts import R32_CHART, R410A_DX_HGRH_CHART, R410A_DX_CHART
from coilforge.coil_utilities.geometry import (
    coil_volume_cuin,
    drop_tubes,
    face_area_sqft,
    heating_capacity_mbh,
    passes,
    pct_drop_tubes,
)
from coilforge.coil_utilities.ranges import (
    ALLOWABLE_RANGES,
    KitRanges,
    kit_for_cooling_btuh,
    ranges_for_kit,
    tons_for_kit,
)

__all__ = [
    "R32_CHART",
    "R410A_DX_HGRH_CHART",
    "R410A_DX_CHART",
    "coil_volume_cuin",
    "passes",
    "drop_tubes",
    "pct_drop_tubes",
    "face_area_sqft",
    "heating_capacity_mbh",
    "KitRanges",
    "ranges_for_kit",
    "kit_for_cooling_btuh",
    "tons_for_kit",
    "ALLOWABLE_RANGES",
]
