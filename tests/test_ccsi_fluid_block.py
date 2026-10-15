"""Water-coil fluid block on the CCSI form (bug fix 2026-09-30).

The submittal prints ``Fluid Type: Water`` + ``Fluid Percent (%): 100`` or ``Fluid Type:
Propylene`` + ``Fluid Percent (%): 40`` — the percent is the share of the NAMED fluid. CCSI's
``Fluid Ratio(%)`` is the glycol share, so 100 % water is 0, and CCSI calls the glycol
``Propylene Glycol``. Reading the percent straight across pushed "100 % glycol" for plain water
(3154 HHWC-1/2, 2954 CCWC-1/2: CoilForge 100 vs CCSI 0).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ccsi.coil_data_map import resolve_coil_data  # noqa: E402


def _fluid(fluid_type, percent, coil_type="HWC"):
    sources = {}
    if fluid_type is not None:
        sources["airside_conditions.fluid_type"] = {"value": fluid_type, "status": "review_required"}
    if percent is not None:
        sources["airside_conditions.fluid_percent"] = {"value": percent, "status": "review_required"}
    by = {e.ccsi_id: e for e in resolve_coil_data(sources, coil_type=coil_type)}
    return by["FluidType"], by["GlycolRatio"]


@pytest.mark.parametrize("coil_type", ["CWC", "HWC"])
def test_water_at_100_percent_is_zero_glycol(coil_type) -> None:
    fluid, ratio = _fluid("Water", 100, coil_type)
    assert fluid.value == "Water"
    assert ratio.value == "0"


@pytest.mark.parametrize(("stated", "ccsi"), [("Propylene", "Propylene Glycol"), ("Ethylene", "Ethylene Glycol"),
                                              ("Propylene Glycol", "Propylene Glycol")])
def test_a_glycol_keeps_its_percent_and_gets_ccsis_name(stated, ccsi) -> None:
    fluid, ratio = _fluid(stated, 40)
    assert fluid.value == ccsi
    assert ratio.value == "40"


def test_water_below_100_percent_is_contradictory_not_guessed() -> None:
    _fluid_entry, ratio = _fluid("Water", 40)
    assert ratio.value is None and ratio.reason_code == "CCSI_VALUE_UNPARSEABLE"


def test_a_percent_without_a_fluid_type_is_never_read_as_glycol() -> None:
    _fluid_entry, ratio = _fluid(None, 40)
    assert ratio.value is None and ratio.reason_code == "CCSI_SOURCE_MISSING"


def test_an_unknown_fluid_stays_unmapped() -> None:
    fluid, ratio = _fluid("Brine", 20)
    assert fluid.value is None and fluid.reason_code == "CCSI_OPTION_UNMAPPED"
    assert ratio.value is None and ratio.reason_code == "CCSI_OPTION_UNMAPPED"
