"""Mirror generation is retired; Ventum Plus draws via the shared templates.

- Mirroring never activates a template (it smeared dimension callouts). Each hand is
  seeded from its own real provided PDF. As of 2026-06-21 the eight previously
  mirror-derived hands were seeded from real per-hand drawings, so no active template
  is mirror-derived and every bucket is an active review aid.
- Ventum Plus (DX/HGRH/CWC/HWC) draws through the existing product-agnostic CoilMaster
  templates, like Nova/Terra/Ventum H (confirmed 2026-07-03: its reference selection
  PDFs are CoilMaster EZ-Coil drawings in the same format the templates were seeded
  from; the unit only sets casing dims, which the engine computes). Review aid only.
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


def test_ventum_plus_renders_across_categories() -> None:
    # Ventum Plus draws through the shared product-agnostic CoilMaster templates
    # (confirmed 2026-07-03). It is no longer forced to "not registered"; it renders
    # exactly like Nova/Terra with its own engine-computed dimensions. Review aid only.
    for category, template_id in (
        ("DX", "coilmaster_dx_lh_header1"),
        ("HGRH", "coilmaster_hgrh_lh_header1"),
        ("CWC", "coilmaster_cwc_lh"),
        ("HWC", "coilmaster_hwc_lh"),
    ):
        out = derive_coil_template_drawing(
            dict(coil_category=category, coil_hand="Left", circuits=1,
                 product_type="VENTUM_PLUS", unit_size="V20", rows=4,
                 finned_height=12, finned_length=15, suction_conn_size=0.625)
        )
        assert out["template_id"] == template_id, category
        assert out["template_found"] is True, category
        assert out["generation_allowed"] is True, category
        assert out["svg"], category
        assert out.get("unregistered_product_line") is None, category
        # Still a review aid only — export stays off.
        assert out["export_allowed"] is False, category


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


def test_terra_v_water_coils_are_omitted() -> None:
    # Terra V CWC/HWC drawings are deliberately omitted — no seeded Terra V water
    # reference, so the shared (Terra-H-shaped) water template is not borrowed.
    for category in ("CWC", "HWC"):
        out = derive_coil_template_drawing(
            dict(coil_category=category, coil_hand="Left", circuits=1,
                 product_type="TERRA V", unit_size="024", rows=4,
                 finned_height=12, finned_length=15, suction_conn_size=0.625)
        )
        assert out["template_found"] is False, category
        assert out["generation_allowed"] is False, category
        assert not out["svg"], category
        assert "Terra V" in out["not_registered_reason"], category
        # Terra V is a registered line; only its water coils are withheld.
        assert out.get("unregistered_product_line") is None, category


def test_terra_v_dx_and_hgrh_still_generate() -> None:
    # Only Terra V WATER is omitted — Terra V DX/HGRH draw normally.
    for category in ("DX", "HGRH"):
        out = derive_coil_template_drawing(
            dict(coil_category=category, coil_hand="Left", circuits=1,
                 product_type="TERRA V", unit_size="024", rows=4,
                 finned_height=12, finned_length=15, suction_conn_size=0.625)
        )
        assert out["generation_allowed"] is True, category
        assert out["svg"], category


def test_terra_h_water_still_generates() -> None:
    # The omission is variant-specific: Terra H (resolved H C) water still draws.
    out = derive_coil_template_drawing(
        dict(coil_category="CWC", coil_hand="Left", circuits=1,
             product_type="TERRA H", unit_size="024", rows=4,
             finned_height=12, finned_length=15, suction_conn_size=0.625)
    )
    assert out["generation_allowed"] is True
    assert out["svg"]
