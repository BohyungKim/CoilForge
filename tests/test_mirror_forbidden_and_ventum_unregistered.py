"""Mirror generation is retired and Ventum Plus is tracked separately.

- Mirroring never activates a template (it smeared dimension callouts). Each hand is
  seeded from its own real provided PDF. As of 2026-06-21 the eight previously
  mirror-derived hands were seeded from real per-hand drawings, so no active template
  is mirror-derived and every bucket is an active review aid.
- Ventum Plus (DX/HGRH/CWC/HWC) still has no seeded template; the workflow forces its
  template result to "not registered" rather than borrowing another line's artwork,
  even though the drawing-parameter rule engine covers Ventum Plus dimensions.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.template_population.catalog import (  # noqa: E402
    ACTIVE_TEMPLATES,
    load_drawing_template_catalog,
)
from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    derive_coil_template_drawing,
)


# The eight hand/header combos that were previously mirror-derived and are now
# seeded from their own real per-hand PDFs (2026-06-21).
_FORMER_MIRROR_BUCKETS = (
    "coilmaster_dx_rh_header1",
    "coilmaster_dx_lh_header2",
    "coilmaster_dx_rh_header3",
    "coilmaster_hgrh_rh_header2",
    "coilmaster_hgrh_lh_header3",
    "coilmaster_dx_rh_hgbp",
    "coilmaster_cwc_rh",
    "coilmaster_hwc_rh",
)


def test_no_mirror_entries_remain_active() -> None:
    # No active template is mirror-derived; all 22 buckets are seeded singles.
    for _id, (_cat, _src, ref_status) in ACTIVE_TEMPLATES.items():
        assert ref_status != "mirrored_from_seeded_pair_review_required"
    assert len(ACTIVE_TEMPLATES) == 22


def test_former_mirror_buckets_now_seeded_from_real_pdfs() -> None:
    entries = load_drawing_template_catalog().by_template_id()
    assert len(entries) == 22
    for bucket in _FORMER_MIRROR_BUCKETS:
        assert entries[bucket].generation_allowed is True
        assert entries[bucket].status == "active_review_aid"


def test_seeded_hand_still_renders() -> None:
    out = derive_coil_template_drawing(
        dict(coil_category="DX", coil_hand="Left", circuits=1, product_type="NOVA",
             unit_size="B20", rows=4, finned_height=12, finned_length=15,
             suction_conn_size=0.625)
    )
    assert out["template_id"] == "coilmaster_dx_lh_header1"
    assert out["generation_allowed"] is True
    assert out["svg"]


def test_former_mirror_hand_now_renders() -> None:
    out = derive_coil_template_drawing(
        dict(coil_category="DX", coil_hand="Right", circuits=1, product_type="NOVA",
             unit_size="B20", rows=4, finned_height=12, finned_length=15,
             suction_conn_size=0.625)
    )
    # DX RH Header 1 is now seeded from its own real PDF (no longer a disabled mirror).
    assert out["template_id"] == "coilmaster_dx_rh_header1"
    assert out["generation_allowed"] is True
    assert out["svg"]
    # Still a review aid only — export stays off.
    assert out["export_allowed"] is False


def test_ventum_plus_is_unregistered_across_categories() -> None:
    for category in ("DX", "HGRH", "CWC", "HWC"):
        out = derive_coil_template_drawing(
            dict(coil_category=category, coil_hand="Left", circuits=1,
                 product_type="VENTUM_PLUS", unit_size="V20", rows=4,
                 finned_height=12, finned_length=15, suction_conn_size=0.625)
        )
        assert out["template_found"] is False, category
        assert out["generation_allowed"] is False, category
        assert not out["svg"], category
        assert out["unregistered_product_line"] == "VENTUM_PLUS", category
        assert "Ventum Plus" in out["not_registered_reason"], category


def test_non_ventum_line_is_not_gated() -> None:
    # A seeded line on a seeded hand renders normally (gate is a no-op).
    out = derive_coil_template_drawing(
        dict(coil_category="HGRH", coil_hand="Right", circuits=1,
             product_type="NOVA", unit_size="B20", rows=4, finned_height=12,
             finned_length=15, suction_conn_size=0.625)
    )
    assert out["generation_allowed"] is True
    assert out.get("unregistered_product_line") is None
    assert out["svg"]
