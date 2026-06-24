"""Copper-strap price adder: $25/strap over the R-090 strap count.

DX = 1 strap/header -> $25/header; HGRH = 2 straps/header -> $50/header.
CWC/HWC keep R-090's blocked status (no fabricated price); unknown header count
routes to review-required. Mirrors the confidence gate end to end.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.package.copper_strap_pricing import (  # noqa: E402
    COPPER_STRAP_UNIT_PRICE,
    copper_strap_price,
)
from coilforge.schemas.header_prepopulate import CoilType  # noqa: E402


def test_dx_one_header_is_25() -> None:
    price = copper_strap_price(CoilType.DX, 1)
    assert price["status"] == "required"
    assert price["strap_count"] == 1
    assert price["total"] == 25.0
    assert "DX" in price["note"] and "CAD$25.00" in price["note"]


def test_hgrh_one_header_is_50() -> None:
    price = copper_strap_price(CoilType.HGRH, 1)
    assert price["status"] == "required"
    assert price["strap_count"] == 2  # 2 straps/header
    assert price["total"] == 50.0
    assert "CAD$50.00" in price["note"]


def test_price_scales_with_header_count() -> None:
    assert copper_strap_price(CoilType.DX, 2)["total"] == 50.0  # 2 straps x $25
    assert copper_strap_price(CoilType.HGRH, 2)["total"] == 100.0  # 4 straps x $25


def test_water_coils_never_priced() -> None:
    for coil in (CoilType.CWC, CoilType.HWC):
        price = copper_strap_price(coil, 1)
        assert price["status"] == "blocked"
        assert price["total"] is None
        assert price["strap_count"] is None


def test_unknown_header_count_is_review_required() -> None:
    price = copper_strap_price(CoilType.DX, None)
    assert price["status"] == "review_required"
    assert price["total"] is None


def test_unit_price_constant() -> None:
    assert COPPER_STRAP_UNIT_PRICE == 25.00
    assert copper_strap_price(CoilType.DX, 1)["currency"] == "CAD"
