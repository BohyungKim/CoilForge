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
    assert len(entries) >= 22  # 22 shared + any dedicated per-family (seeded Ventum+)
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
    # Ventum Plus renders across categories. These LH 1-header combos now have DEDICATED
    # Ventum+ templates seeded from real Ventum+ selection drawings (2026-07-06), so they
    # route to the `coilmaster_vplus_*` bucket instead of the shared one. Review aid only.
    for category, template_id in (
        ("DX", "coilmaster_vplus_dx_lh_header1"),
        ("HGRH", "coilmaster_vplus_hgrh_lh_header1"),
        ("CWC", "coilmaster_vplus_cwc_lh"),
        ("HWC", "coilmaster_vplus_hwc_lh"),
    ):
        out = derive_coil_template_drawing(
            dict(coil_category=category, coil_hand="Left", circuits=1,
                 product_type="VENTUM_PLUS", unit_size="V20", rows=4,
                 finned_height=12, finned_length=15, suction_conn_size=0.625)
        )
        assert out["template_id"] == template_id, category
        assert out.get("dedicated_family_template") == "VENTUM_PLUS", category
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


def test_ventum_plus_dx_unseeded_is_not_registered() -> None:
    # DX-only not-registered gate (John 2026-07-14): a Ventum+ DX combo with NO dedicated
    # UP template (DX RH 3-header — the shared bucket exists but no vplus one is seeded)
    # must NOT fall back to the shared ConnectionDown template. Ventum+ DX mounts the
    # distributor ConnectionUP (R-032), so a DOWN drawing would be wrong — it is blocked
    # as "not registered" instead of drawn-with-a-caveat.
    out = derive_coil_template_drawing(
        dict(coil_category="DX", coil_hand="Right", circuits=3,
             product_type="VENTUM_PLUS", unit_size="V20", rows=4,
             finned_height=12, finned_length=15, suction_conn_size=0.625)
    )
    assert not out["svg"]  # blocked — no wrong-orientation shared drawing leaks through
    assert out["template_found"] is False
    assert out["generation_allowed"] is False
    assert out.get("unregistered_ventum_plus_dx") is True
    reason = out.get("not_registered_reason") or ""
    assert "R-032" in reason and "ConnectionUP" in reason
    # No shared drawing was produced, so no orientation caveat rides alongside.
    assert out.get("distributor_orientation_warning") is None


def test_ventum_plus_non_dx_has_no_orientation_warning() -> None:
    # R-031/R-032 are DX-only (the distributor exists on DX). Ventum+ HGRH/CWC/HWC have
    # no distributor, so no orientation warning is attached.
    for category in ("HGRH", "CWC", "HWC"):
        out = derive_coil_template_drawing(
            dict(coil_category=category, coil_hand="Left", circuits=1,
                 product_type="VENTUM_PLUS", unit_size="V20", rows=4,
                 finned_height=12, finned_length=15, suction_conn_size=0.625)
        )
        assert out.get("distributor_orientation_warning") is None, category


def test_nova_dx_has_no_orientation_warning() -> None:
    # Nova/Terra/Ventum H distributors mount ConnectionDown (R-031) — the seeded
    # template already draws them correctly, so no warning is attached.
    out = derive_coil_template_drawing(
        dict(coil_category="DX", coil_hand="Left", circuits=1, product_type="NOVA",
             unit_size="B20", rows=4, finned_height=12, finned_length=15,
             suction_conn_size=0.625)
    )
    assert out["svg"]
    assert out.get("distributor_orientation_warning") is None


def test_ventum_plus_dx_rh_routes_to_dedicated_template() -> None:
    # A dedicated Ventum+ DX RH 1-header template is seeded (from a real UP reference),
    # so a Ventum+ DX RH coil draws from it — not the shared ConnectionDown bucket — and
    # the orientation caveat is dropped (the dedicated template already draws UP).
    out = derive_coil_template_drawing(
        dict(coil_category="DX", coil_hand="Right", circuits=1,
             product_type="VENTUM_PLUS", unit_size="V20", rows=4,
             finned_height=12, finned_length=15, suction_conn_size=0.625)
    )
    assert out["template_id"] == "coilmaster_vplus_dx_rh_header1"
    assert out.get("dedicated_family_template") == "VENTUM_PLUS"
    assert out["svg"]
    assert out.get("distributor_orientation_warning") is None  # dedicated UP -> no caveat
    assert out["export_allowed"] is False  # still review aid only


def test_ventum_plus_non_dx_unseeded_still_draws_via_shared() -> None:
    # The not-registered gate is DX-ONLY (the distributor is a DX concept). An un-seeded
    # Ventum+ NON-DX combo (HGRH LH 2-header — no dedicated bucket) still falls back to
    # the shared template and draws; it is never blocked and carries no orientation caveat.
    out = derive_coil_template_drawing(
        dict(coil_category="HGRH", coil_hand="Left", circuits=2,
             product_type="VENTUM_PLUS", unit_size="V20", rows=4,
             finned_height=12, finned_length=15, suction_conn_size=0.625)
    )
    assert out["svg"]  # non-DX un-seeded still draws via the shared bucket
    assert out.get("dedicated_family_template") is None  # shared fallback, not dedicated
    assert out.get("not_registered_reason") is None
    assert out.get("unregistered_ventum_plus_dx") is None
    assert out.get("distributor_orientation_warning") is None  # non-DX -> no caveat


def test_non_ventum_line_never_gets_dedicated_ventum_template() -> None:
    # A Nova DX RH coil must keep the shared bucket even though a dedicated Ventum+ RH
    # bucket exists for the same category/hand/header (the family axis gates it).
    out = derive_coil_template_drawing(
        dict(coil_category="DX", coil_hand="Right", circuits=1, product_type="NOVA",
             unit_size="B20", rows=4, finned_height=12, finned_length=15,
             suction_conn_size=0.625)
    )
    assert out["template_id"] == "coilmaster_dx_rh_header1"  # shared, NOT the vplus one
    assert out.get("dedicated_family_template") is None


# --------------------------------------------------------------------------- #
# Hot gas bypass (HGBP / ASC) is selectable on Nova and Ventum H ONLY (John,
# 2026-07-15). The two seeded HGBP templates are Nova/Ventum-H-class references,
# so an HGBP coil resolving to another line is a misclassification, not an exotic
# coil — its drawing is omitted rather than borrowing another line's geometry.
# --------------------------------------------------------------------------- #
def _hgbp_spec(product_type: str | None, hand: str = "Left") -> dict:
    return dict(coil_category="DX", coil_hand=hand, circuits=1,
                special_feature="HGBP", product_type=product_type, unit_size="B20",
                rows=4, finned_height=12, finned_length=15, suction_conn_size=0.625)


def test_hgbp_draws_for_nova_and_ventum_h() -> None:
    # The two lines that may select the option draw from the seeded HGBP bucket,
    # with no unverified-line caveat (their product line resolved).
    for product_type in ("NOVA", "VENTUM_H"):
        out = derive_coil_template_drawing(_hgbp_spec(product_type))
        assert out["template_id"] == "coilmaster_dx_lh_hgbp", product_type
        assert out["generation_allowed"] is True, product_type
        assert out["svg"], product_type
        assert out.get("unsupported_hgbp_product_line") is None, product_type
        assert out.get("hgbp_product_line_warning") is None, product_type
        assert out["export_allowed"] is False, product_type  # review aid only


def test_hgbp_rh_draws_for_nova() -> None:
    out = derive_coil_template_drawing(_hgbp_spec("NOVA", hand="Right"))
    assert out["template_id"] == "coilmaster_dx_rh_hgbp"
    assert out["svg"]


def test_hgbp_omitted_for_lines_that_cannot_select_the_option() -> None:
    for product_type, family in (("TERRA H", "TERRA_H"), ("TERRA V", "TERRA_V")):
        out = derive_coil_template_drawing(_hgbp_spec(product_type))
        assert not out["svg"], product_type
        assert out["template_found"] is False, product_type
        assert out["generation_allowed"] is False, product_type
        assert out.get("unsupported_hgbp_product_line") == family, product_type
        reason = out.get("not_registered_reason") or ""
        assert "Nova and Ventum H only" in reason, product_type


def test_hgbp_unknown_product_line_draws_with_a_warning() -> None:
    """An unresolved product line means the Nova/Ventum-H premise is unverified.
    Blanking on that absence would kill legitimate Nova HGBP coils whose model code
    merely failed to parse, so the drawing stands and the premise is surfaced instead.
    Flipping this to strict must be a conscious test-breaking act.

    Note the line resolves from EITHER product_type OR unit_size (a Nova size like
    "B20" implies Nova), so neither may be present for the line to be unknown.
    """
    out = derive_coil_template_drawing(
        dict(coil_category="DX", coil_hand="Left", circuits=1, special_feature="HGBP",
             rows=4, finned_height=12, finned_length=15, suction_conn_size=0.625)
    )
    assert out["svg"]
    assert out["template_id"] == "coilmaster_dx_lh_hgbp"
    assert out.get("unsupported_hgbp_product_line") is None
    assert "UNVERIFIED" in (out.get("hgbp_product_line_warning") or "")


def test_hgbp_product_line_inferred_from_unit_size_is_not_warned() -> None:
    # A Nova unit size implies the Nova line even with no product_type, so the premise
    # is verified and no caveat rides along.
    out = derive_coil_template_drawing(_hgbp_spec(None))
    assert out["svg"]
    assert out.get("hgbp_product_line_warning") is None


def test_ventum_plus_hgbp_reads_as_nonexistent_not_as_an_unseeded_bucket() -> None:
    """Ventum+ DX HGBP does not exist (John 2026-07-15) — hot gas bypass is a Nova /
    Ventum H option. It would also trip _gate_unseeded_ventum_plus_dx, whose reason
    ("no seeded Ventum+ DX reference matches ... must be seeded first") reads as a
    coverage gap someone could close by finding a reference PDF. There is no such
    reference, so the HGBP gate runs FIRST and owns the message — pins the ordering."""
    out = derive_coil_template_drawing(_hgbp_spec("VENTUM_PLUS"))
    assert not out["svg"]
    assert out["template_found"] is False
    assert out["generation_allowed"] is False
    assert out.get("unsupported_hgbp_product_line") == "VENTUM_PLUS"
    reason = out.get("not_registered_reason") or ""
    assert "Nova and Ventum H only" in reason
    # Must NOT invite anyone to go seed a Ventum+ DX HGBP reference (the vplus gate's
    # wording) — no such reference can be produced.
    assert "must be seeded first" not in reason
    assert "R-032" not in reason
    assert out.get("unregistered_ventum_plus_dx") is None


def test_ventum_plus_dx_without_hgbp_still_reports_the_r032_reason() -> None:
    """The reordering must not steal the R-032 message from a genuinely unseeded
    Ventum+ DX hand/header — that one IS a real, closeable coverage gap."""
    out = derive_coil_template_drawing(
        dict(coil_category="DX", coil_hand="Right", circuits=3,
             product_type="VENTUM_PLUS", unit_size="V20", rows=4,
             finned_height=12, finned_length=15, suction_conn_size=0.625)
    )
    assert not out["svg"]
    assert out.get("unregistered_ventum_plus_dx") is True
    reason = out.get("not_registered_reason") or ""
    assert "R-032" in reason and "ConnectionUP" in reason
    assert out.get("unsupported_hgbp_product_line") is None


def test_non_hgbp_dx_is_untouched_by_the_hgbp_gates() -> None:
    # Regression guard: a plain Terra DX Header 1 coil (no HGBP) is unaffected.
    out = derive_coil_template_drawing(
        dict(coil_category="DX", coil_hand="Left", circuits=1, product_type="TERRA H",
             unit_size="024", rows=4, finned_height=12, finned_length=15,
             suction_conn_size=0.625)
    )
    assert out["template_id"] == "coilmaster_dx_lh_header1"
    assert out["svg"]
    assert out.get("unsupported_hgbp_product_line") is None
    assert out.get("hgbp_product_line_warning") is None


def test_hgbp_drawing_notes_carry_the_asc_distributor_note() -> None:
    """R-035c end-to-end: the SAME special_feature that selects the HGBP template also
    picks the distributor note, so the note and the drawing can never disagree about
    whether this coil is HGBP. Guards the _engine_drawing_notes -> build_header_request
    hot_gas_bypass thread (without it R-035c never fires)."""
    from coilforge.workflows.submittal_to_drawing import _engine_drawing_notes

    ctx = dict(product_type="NOVA", unit_size="B20", coil_category="DX",
               rows=4, feeds=2, circuits=1)
    hgbp_notes = _engine_drawing_notes({**ctx, "special_feature": "HGBP"})
    assert 'Distributor Down w/ ASC & 6" Extension' in hgbp_notes
    assert 'Distributor 6" Extension Downwards' not in hgbp_notes

    plain_notes = _engine_drawing_notes({**ctx, "special_feature": None})
    assert 'Distributor 6" Extension Downwards' in plain_notes
    assert not any("ASC" in note for note in plain_notes)
