"""Tests for applying the JSON->drawing link registry to EZ Coil exports.

Uses synthetic JSON (Case/ data is git-ignored) mirroring the real schemas.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.services.ez_json_drawing_loader import (  # noqa: E402
    detect_schema,
    slots_from_ez_json,
)

# Single-circuit DX (2 headers) with deliberate forbidden top-level traps.
GEOM_1 = {
    "Geometry": {
        "FH": 12.0, "FL": 15.0, "CH": 13.25, "CL": 18.0, "CD": 5.5,
        "TSP": 0.625, "BSP": 0.625, "RB": 1.75, "LEP": 1.5, "REP": 1.5,
        "I": 0.0, "O": 2.06, "S": 1.2, "R": 1.2, "SL": 4.0,  # traps
        "Headers": [
            {"ID": 1, "IsSupply": True, "IsDistributor": True, "HD": 4.5,
             "IO": [3.0, 0, 0], "SR": 2.75, "SL": [0, 0, 0]},
            {"ID": 2, "IsSupply": False, "HD": 3.5,
             "IO": [2.0, 0, 0], "SR": 0.625, "SL": [8.0, 0, 0]},
        ],
    }
}

# Multi-circuit DX (4 headers).
GEOM_2 = {
    "Geometry": {
        "FH": 26.0, "FL": 34.0, "CD": 5.5,
        "Headers": [
            {"ID": 1, "IsSupply": True, "HD": 4.5, "IO": [3.0], "SR": 1.875, "SL": [0]},
            {"ID": 2, "IsSupply": False, "HD": 3.5, "IO": [2.0], "SR": 1.125, "SL": [8.0]},
            {"ID": 3, "IsSupply": True, "HD": 4.5, "IO": [3.0], "SR": 3.625, "SL": [0]},
            {"ID": 4, "IsSupply": False, "HD": 3.5, "IO": [2.0], "SR": 3.75, "SL": [8.0]},
        ],
    }
}

PD_SINGLE_FEED = {
    "PhysicalData": {"finHeight": "12", "finLength": "15"},
    "Construction": {
        "notes": " Copper Straps Required. Add Headers & Stubouts. I1=2. "
                 "S1=1.875. SL1=6. O2=2. R2=0.625. HD2=3.5. SL2=8. SupConnAngle=LAS"
    },
}

PD_MULTI_FEED = {
    "PhysicalData": {"finHeight": "34", "finLength": "52"},
    "Construction": {"notes": " Copper Straps Required."},
}


def test_detect_schema() -> None:
    assert detect_schema(GEOM_1) == "geometry"
    assert detect_schema(PD_SINGLE_FEED) == "physicaldata"
    assert detect_schema({"foo": 1}) == "unknown"


def test_geometry_single_pair_slots() -> None:
    slots, _ = slots_from_ez_json(GEOM_1)
    assert slots["slot.FH"] == 12.0
    assert slots["slot.CD"] == 5.5
    assert slots["slot.TF"] == 0.625  # from TSP
    assert slots["slot.BF"] == 0.625  # from BSP
    assert slots["slot.RB"] == 1.75
    assert slots["slot.I1"] == 3.0      # Headers[0].IO[0]
    assert slots["slot.S1"] == 2.75     # Headers[0].SR
    assert slots["slot.HDx1"] == 4.5    # distributor HD
    assert slots["slot.O2"] == 2.0      # Headers[1].IO[0]
    assert slots["slot.R2"] == 0.625    # Headers[1].SR
    assert slots["slot.SL2"] == 8.0
    assert slots["slot.HD2"] == 3.5     # return/suction HD


def test_forbidden_top_level_fields_not_sourced() -> None:
    """slot.I1 must come from Headers[], never top-level Geometry.I (=0)."""
    slots, _ = slots_from_ez_json(GEOM_1)
    assert slots["slot.I1"] == 3.0
    # No slot is sourced from the forbidden top-level I/O/S/R/SL traps.
    assert "slot.I" not in slots
    assert slots.get("slot.SL2") == 8.0  # not the top-level Geometry.SL=4


def test_geometry_multi_header_pairs() -> None:
    slots, _ = slots_from_ez_json(GEOM_2)
    # Two supply (odd) + two return (even) -> I1/I3, O2/O4 etc.
    assert slots["slot.I1"] == 3.0 and slots["slot.I3"] == 3.0
    assert slots["slot.O2"] == 2.0 and slots["slot.O4"] == 2.0
    assert slots["slot.S3"] == 3.625 and slots["slot.R4"] == 3.75


def test_physicaldata_single_feed_tokens() -> None:
    slots, _ = slots_from_ez_json(PD_SINGLE_FEED)
    assert slots["slot.FH"] == 12 and slots["slot.FL"] == 15
    assert slots["slot.I1"] == 2 and slots["slot.SL1"] == 6
    assert slots["slot.O2"] == 2 and slots["slot.HD2"] == 3.5
    assert slots["slot.SL2"] == 8
    assert slots["slot.SupConnAngle"] == "LAS"


def test_physicaldata_multi_feed_has_no_header_tokens() -> None:
    slots, provenance = slots_from_ez_json(PD_MULTI_FEED)
    assert slots["slot.FH"] == 34 and slots["slot.FL"] == 52
    assert not any(k.startswith("slot.I") for k in slots)
    assert any("multi-feed" in p for p in provenance)
