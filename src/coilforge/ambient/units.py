"""Unit normalization for Ambient performance data.

Ambient Dynamics reports coil capacity in **Btu/hr**; the Coilmaster/submittal
baseline CoilForge already parses is in **MBH** (thousand Btu/hr). To compare
apples-to-apples, the Ambient parser normalizes capacity to MBH — but ONLY when the
report actually states Btu/hr (see ``ambient.pdf_intake``), never unconditionally,
so an MBH-labeled value is not silently divided by 1000.
"""
from __future__ import annotations


def btuh_to_mbh(value: float) -> float:
    """Btu/hr -> MBH (thousand Btu/hr)."""
    return value / 1000.0


def mbh_to_btuh(value: float) -> float:
    """MBH -> Btu/hr (for display / write-back back into Ambient's own units)."""
    return value * 1000.0
