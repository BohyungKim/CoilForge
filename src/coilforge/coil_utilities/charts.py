"""Raw per-kit source charts, transcribed from the Coil Utilities workbook.

Each chart is the **single-circuit** published limit set (QTY=1). Multiply every band
by the coil's ``circuits`` to get the live chart (see ``ranges.ranges_for_kit``).
Capacities are Daikin's published BTU/h; volumes are internal in^3.

- ``R32_CHART``  — Daikin R32 VRV (primary; the ``R32`` sheet source rows 18–24 + the
  ``50% Conn`` heating-nominal row 22).
- ``R410A_DX_HGRH_CHART`` / ``R410A_DX_CHART`` — legacy R410a (the ``R410a`` sheet's two
  controller sub-charts). Different kit index set and per-column constants.

Data-only; no logic. ``ranges.py`` turns these into lookups.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KitRow:
    """One EKEXVA kit's single-circuit published band (BTU/h capacities, in^3 volume)."""

    index: int  # capacity index; nominal tons = index / 12
    cooling_min: int
    cooling_max: int
    heating_min: int
    heating_max: int
    volume_min: float
    volume_max: float
    heating_nominal: int | None = None  # from the '50% Conn' sheet (R32 only)


# --- R32 (primary). Source: 'R32'!R18:R24 (single circuit) + '50% Conn'!R22 nominal. ---
_R32_INDEX = (12, 18, 24, 30, 36, 48, 60, 72, 96, 114, 132, 156, 174, 192)
_R32_COOL_MIN = (10000, 17000, 21500, 27000, 34000, 45000, 53000, 72000, 84500, 105500, 126000, 150500, 169000, 189500)
_R32_COOL_MAX = (16500, 21000, 26500, 33500, 44500, 52500, 71500, 84000, 105000, 125500, 150000, 168500, 189000, 210000)
_R32_HEAT_MIN = (11500, 19000, 22000, 30500, 38000, 50500, 59500, 81000, 95000, 118500, 142000, 164000, 184500, 213500)
_R32_HEAT_MAX = (18500, 21500, 30000, 37500, 50000, 59000, 80500, 94500, 118000, 141500, 163500, 184000, 213000, 236500)
_R32_VOL_MIN = (20, 32, 40, 51, 63, 79, 90, 126, 158, 188, 218, 253, 287, 315)
_R32_VOL_MAX = (53, 85, 108, 137, 170, 213, 244, 341, 427, 510, 590, 686, 778, 854)
_R32_HEAT_NOM = (13500, 20000, 27000, 34000, 40000, 54000, 66000, 81000, 106000, 126000, 146000, 172000, 192000, 213000)

R32_CHART: tuple[KitRow, ...] = tuple(
    KitRow(idx, cmin, cmax, hmin, hmax, vmin, vmax, hnom)
    for idx, cmin, cmax, hmin, hmax, vmin, vmax, hnom in zip(
        _R32_INDEX, _R32_COOL_MIN, _R32_COOL_MAX, _R32_HEAT_MIN, _R32_HEAT_MAX,
        _R32_VOL_MIN, _R32_VOL_MAX, _R32_HEAT_NOM,
    )
)

# --- R410a legacy (NOT YET TRANSCRIBED) ---
# The 'R410a' sheet has two controller sub-charts (DX+HGRH "D Ctrl", kits …400; and
# DX "W Ctrl", kits …500) with per-column constants that were NOT fully captured from
# the workbook. Shipping a partial/guessed table would invent engineering values, so
# both stay EMPTY until transcribed cell-by-cell from the real sheet. R32 is the current
# line (Daikin R32 VRV); R410a is legacy and can be filled when a project needs it.
# Verified single data point for the future transcription (do not extrapolate from it):
#   index 18 -> cooling 17000/21000, heating 19000/24000, volume 32/101 (D Ctrl).
R410A_DX_HGRH_CHART: tuple[KitRow, ...] = ()  # TODO: transcribe 'R410a'!R2:R11 in full.
R410A_DX_CHART: tuple[KitRow, ...] = ()        # TODO: transcribe 'R410a'!R13:R22 in full.
