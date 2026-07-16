"""Coil internal-volume formula — re-exported from the canonical Coil Utilities home.

The formula is shared: the Ambient comparison workbook (C15/D15) and the Coil Utilities
workbook (R32/R410a C13) use the identical tube-geometry calc. It now lives once in
``coil_utilities.geometry``; this module re-exports it so ``ambient`` callers keep a
stable import.
"""
from __future__ import annotations

from coilforge.coil_utilities.geometry import DEFAULT_TUBE_OD_IN, coil_volume_cuin

__all__ = ["coil_volume_cuin", "DEFAULT_TUBE_OD_IN"]
