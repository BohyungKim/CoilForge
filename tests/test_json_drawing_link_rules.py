"""Validation tests for the JSON -> drawing link-rule registry.

Schema/consistency checks, plus a cross-check that the engine->slot bridge
names real fields the header-prepopulation engine actually produces.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.schemas.header_prepopulate import (  # noqa: E402
    CoilType,
    HeaderPrepopulateRequest,
    ProductFamily,
)
from coilforge.services import json_drawing_link as link  # noqa: E402
from coilforge.services.header_prepopulate_engine import prepopulate  # noqa: E402


def test_registry_loads_with_core_sections() -> None:
    reg = link.load_link_registry()
    assert reg["schema_version"]
    for section in (
        "schema_families",
        "category_decode",
        "direct_links",
        "physicaldata_links",
        "header_connection_links",
        "notes_token_links",
        "derived_links",
        "forbidden_sources",
        "engine_slot_bridge",
    ):
        assert section in reg, section


def test_link_ids_unique() -> None:
    ids = [entry["link_id"] for entry in link.iter_links()]
    assert ids, "no link entries found"
    assert len(ids) == len(set(ids)), "duplicate link_id"


def test_confidence_tiers_valid() -> None:
    for entry in link.iter_links():
        conf = entry.get("confidence")
        if conf is not None:
            assert conf in link.CONFIDENCE_TIERS, entry["link_id"]


def test_review_gate_consistent_with_confidence() -> None:
    """STRONG auto-populates (review False); everything weaker requires review."""
    for entry in link.iter_links():
        conf = entry.get("confidence")
        if conf is None or "review_required" not in entry:
            continue
        if conf == "STRONG":
            assert entry["review_required"] is False, entry["link_id"]
        else:  # DERIVED | UNCERTAIN | DEFERRED
            assert entry["review_required"] is True, entry["link_id"]


def test_forbidden_sources_have_reasons() -> None:
    rows = link.load_link_registry()["forbidden_sources"]["entries"]
    assert rows
    for entry in rows:
        assert entry.get("source") and entry.get("reason"), entry["link_id"]


def test_engine_slot_bridge_fields_are_produced_by_engine() -> None:
    """Every engine_field in the bridge must be a real prepopulation output."""
    # DX/NOVA/B20 with rows + application exercises flanges, CD, dist/suction HD,
    # dist_i, suction_sl, dist_extension, notes, and casing width/height.
    resp = prepopulate(
        HeaderPrepopulateRequest(
            type_of_coil=CoilType.DX,
            product_type=ProductFamily.NOVA,
            unit_size="B20",
            rows=4,
            application="DECOUPLED",
        )
    )
    produced = set(resp.values) | set(resp.suggestions) | set(resp.blocked)
    for pair in link.engine_slot_bridge():
        assert pair["engine_field"] in produced, pair
