"""Golden + invariant tests for the header prepopulation engine.

Written before the engine (TDD) from the 20 golden cases (T01-T20) in section 6
of docs/rules/coil_header_rule_extraction.md, plus the four required invariant
tests (confidence gate, CD-table reproduction, YAML schema validation,
never-raises).

T09's ``supply_sl=6`` for HGRH/VENTUM+ was confirmed by John (2026-06-11) and is
now backed by rule R-044c (MEDIUM suggestion), so it matches the golden case.

T13 labels feeds-absent ``io``/``hd`` as ``Confidence=High``, contradicting T12
which makes the identical feeds-absent fields MEDIUM suggestions. John confirmed
(2026-06-11) that they stay MEDIUM suggestions, so the engine follows T12.

T17's coating note is HIGH, not the doc's blocked CONFLICT (John 2026-06-11 resolved
the SOP-vs-CHK wording in favour of SOP Rev H). It now fires ONLY for a stated,
non-NONE coating (John 2026-07-15), superseding that same day's "no coating trigger
field, so always append" — so the uncoated golden cases (T01/T03/T05/T08) carry no
coating note.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.schemas.header_prepopulate import (  # noqa: E402
    Confidence,
    CoilType,
    HeaderPrepopulateRequest,
    HeaderPrepopulateResponse,
    ProductFamily,
    TerraVariant,
)
from coilforge.services import header_prepopulate_engine as engine  # noqa: E402
from coilforge.services.header_prepopulate_engine import (  # noqa: E402
    cd_cwc_hwc,
    cd_dx_hgrh,
    load_rule_table,
    prepopulate,
    roundup_eighth,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _req(coil: CoilType, product: ProductFamily, size: str, **kw):
    return HeaderPrepopulateRequest(
        type_of_coil=coil, product_type=product, unit_size=size, **kw
    )


def _bucket_and_result(resp: HeaderPrepopulateResponse, field: str):
    for bucket_name in ("values", "suggestions", "blocked"):
        bucket = getattr(resp, bucket_name)
        if field in bucket:
            return bucket_name, bucket[field]
    return None, None


def _in_values(resp, field):
    return field in resp.values


# A valid unit size per product family (R-076 enumerations).
VALID_SIZE = {
    ProductFamily.NOVA: "B20",
    ProductFamily.TERRA: "024",
    ProductFamily.TERRA_H: "024",
    ProductFamily.TERRA_V: "060",
    ProductFamily.VENTUM_H: "H15",
    ProductFamily.VENTUM_PLUS: "V40",
}

# Coating notes (SOP Rev H wording, John 2026-06-11) fire ONLY when a custom coating
# is required -- `only_when: coating_set` (John 2026-07-15). DX/HGRH only.
DX_COATING_NOTE = "Do Not Coat Last 5-6 inches of Distributor Extensions."
HGRH_COATING_NOTE = "Do Not Coat Last 5-6 inches of Supply Stubouts."
# Distributor extension note (R-035a/b): Ventum+ DX mounts ConnectionUP, every other
# DX line mounts down. Appended after the coating note.
DX_DIST_NOTE_DOWN = 'Distributor 6" Extension Downwards'
DX_DIST_NOTE_UP = 'Distributor 6" Extension Upwards'
# R-035c: hot gas bypass restates the distributor note in one combined line and
# DISPLACES the plain Down note (Nova / Ventum H only -- John 2026-07-15).
DX_DIST_NOTE_HGBP = 'Distributor Down w/ ASC & 6" Extension'


def test_r022_return_spacing_terra_h_generic_terra_v_sop_formula() -> None:
    """R-022 (generic) fires for Terra H; Terra V uses its own SOP formula R-023
    (John 2026-06-28, SOP-confirmed). Both HIGH, different formulas."""
    common = dict(circuits=2, suction_conn_size=1.125)
    resp_h = prepopulate(
        _req(CoilType.DX, ProductFamily.TERRA, "024", terra_variant=TerraVariant.TERRA_H, **common)
    )
    assert _in_values(resp_h, "return_spacing")
    assert resp_h.values["return_spacing"].value == [1.125, 3.75]  # Rn = n*D + (n-1)*1.5
    assert resp_h.values["return_spacing"].confidence == Confidence.HIGH

    # Terra V: R-023 SOP formula Rn = (n-0.5)*D + (n-1)*1.5 + 0.75 (HIGH, drawn).
    resp_v = prepopulate(
        _req(CoilType.DX, ProductFamily.TERRA, "024", terra_variant=TerraVariant.TERRA_V, **common)
    )
    assert _in_values(resp_v, "return_spacing")
    assert resp_v.values["return_spacing"].value == [1.3125, 3.9375]
    assert resp_v.values["return_spacing"].confidence == Confidence.HIGH

    # Non-Terra families are unaffected (NOVA still fires the generic R-022).
    resp_nova = prepopulate(_req(CoilType.DX, ProductFamily.NOVA, "B20", **common))
    assert _in_values(resp_nova, "return_spacing")


def test_r052_hgrh_return_spacing_is_review_required_and_product_branched() -> None:
    """R-052: HGRH return spacing R, keyed on conn_size (the "Suction Size"), count
    gated by qty_conn_per_header. MEDIUM -> suggestions (never auto-drawn HIGH).
    TERRA/NOVA/VENTUM_H use the running-edge formula; VENTUM+ uses scalar conn_size.
    """
    # TERRA H, 2 connections per header: Rn = n*D + (n-1)*1.5 => [0.625, 2.75].
    resp = prepopulate(
        _req(
            CoilType.HGRH, ProductFamily.TERRA, "024",
            terra_variant=TerraVariant.TERRA_H, rows=2,
            conn_size=0.625, qty_conn_per_header=2,
        )
    )
    bucket, result = _bucket_and_result(resp, "return_spacing")
    assert bucket == "suggestions"  # MEDIUM never lands in `values`
    assert result.review_required is True
    assert result.confidence == Confidence.MEDIUM
    assert result.value == [0.625, 2.75]

    # qty_conn_per_header gates how many R positions emit (single connection -> R2 only).
    resp1 = prepopulate(
        _req(
            CoilType.HGRH, ProductFamily.TERRA, "024",
            terra_variant=TerraVariant.TERRA_H, rows=2,
            conn_size=0.625, qty_conn_per_header=1,
        )
    )
    assert resp1.suggestions["return_spacing"].value == [0.625]

    # Missing conn_size -> reported as a missing input, not invented.
    resp_missing = prepopulate(
        _req(
            CoilType.HGRH, ProductFamily.TERRA, "024",
            terra_variant=TerraVariant.TERRA_H, rows=2, qty_conn_per_header=2,
        )
    )
    assert "conn_size" in resp_missing.missing_inputs
    assert "return_spacing" not in resp_missing.suggestions


# --------------------------------------------------------------------------- #
# Golden cases T01-T20
# --------------------------------------------------------------------------- #
def test_t01_dx_nova_b20_happy_path_1in() -> None:
    r = prepopulate(_req(CoilType.DX, ProductFamily.NOVA, "B20"))
    assert r.values["return_bend"].value == 1.5
    assert r.values["top_flange"].value == 0.625
    assert r.values["bottom_flange"].value == 0.625
    assert r.values["suction_hd"].value == 3.5
    assert r.values["suction_sl"].value == 8
    assert r.values["dist_i"].value == 3
    assert r.values["dist_orientation"].value == "DOWN"
    assert r.values["dist_extension"].value == 6
    assert r.values["suction_io"].value == 2
    assert r.values["collared_holes"].value is True
    assert r.values["stacking_flanges"].value is False
    # No coating input -> no coating note (R-080 is gated on coating_set,
    # John 2026-07-15). See test_t17_* for the coated case.
    assert r.values["notes"].value == [
        "Copper Straps Required.",
        DX_DIST_NOTE_DOWN,
    ]
    assert r.values["size_class"].value == "NOVA_1IN"
    # Distributor HD = 4.5 (R-030); 3.5 is the suction/return HD (suction_hd).
    assert r.values["dist_hd"].value == 4.5
    assert r.values["suction_hd"].value == 3.5
    assert "dist_hd" not in r.blocked
    # listed value fields are not review_required at the field level
    assert r.values["return_bend"].review_required is False
    # every value field carries evidence
    for fr in r.values.values():
        assert fr.evidence_refs


def test_t02_dx_nova_a18_2in() -> None:
    r = prepopulate(_req(CoilType.DX, ProductFamily.NOVA, "A18"))
    assert r.values["size_class"].value == "NOVA_2IN"
    assert r.values["return_bend"].value == 1.5
    assert r.values["dist_hd"].value == 4.5


def test_t03_dx_ventum_plus_v40() -> None:
    r = prepopulate(_req(CoilType.DX, ProductFamily.VENTUM_PLUS, "V40"))
    assert r.values["top_flange"].value == 1
    assert r.values["bottom_flange"].value == 1
    assert r.values["suction_sl"].value == 10
    assert r.values["dist_i"].value == 12
    assert r.values["dist_orientation"].value == "UP"
    # Ventum+ DX distributor mounts up (R-035a), so the note reads "Upwards".
    assert r.values["notes"].value == [
        "Copper Straps Required.",
        DX_DIST_NOTE_UP,  # no coating input -> no coating note (R-080 coating_set)
    ]
    assert r.values["return_bend"].value == 1.5
    assert r.values["suction_hd"].value == 3.5
    assert r.values["dist_extension"].value == 6
    assert r.values["suction_io"].value == 2
    # Both docs agree dist_hd=4.5 for Ventum+ -> HIGH, not blocked (R-030b).
    assert r.values["dist_hd"].value == 4.5
    assert r.values["dist_hd"].review_required is False
    assert "dist_hd" not in r.blocked


def test_t04_dx_ventum_h_h15() -> None:
    r = prepopulate(_req(CoilType.DX, ProductFamily.VENTUM_H, "H15"))
    assert r.values["top_flange"].value == 0.625
    assert r.values["bottom_flange"].value == 0.625
    assert r.values["suction_sl"].value == 8
    assert r.values["dist_i"].value == 3
    assert r.values["dist_orientation"].value == "DOWN"
    assert r.values["suction_io"].value == 2
    # Distributor HD = 4.5 (R-030); 3.5 is the suction/return HD (suction_hd).
    assert r.values["dist_hd"].value == 4.5
    assert "dist_hd" not in r.blocked


def test_r025b_dx_ventum_h_h05_h10_sl_is_17() -> None:
    """John 2026-06-26: DX Ventum H H05/H10 even-slot SL clearance = 17 (R-025b overrides
    R-025's 8 via the now-active size_pattern match). H15+ keep 8 (test_t04)."""
    for size in ("H05", "H10"):
        r = prepopulate(_req(CoilType.DX, ProductFamily.VENTUM_H, size))
        assert r.values["suction_sl"].value == 17, size
        assert r.values["suction_sl"].confidence == Confidence.HIGH
        assert r.values["suction_sl"].review_required is False


def test_r044d_hgrh_ventum_h_h05_h10_return_sl_is_17() -> None:
    for size in ("H05", "H10"):
        r = prepopulate(_req(CoilType.HGRH, ProductFamily.VENTUM_H, size))
        assert r.values["return_sl"].value == 17, size
        assert r.values["return_sl"].confidence == Confidence.HIGH
        assert r.values["return_sl"].review_required is False


def test_sl_17_override_is_size_scoped() -> None:
    """The override is H05/H10-only: other Ventum H sizes and NOVA keep the default 8 —
    proves the size_pattern gate is precise and backward-compatible."""
    assert prepopulate(_req(CoilType.DX, ProductFamily.VENTUM_H, "H15")).values["suction_sl"].value == 8
    assert prepopulate(_req(CoilType.DX, ProductFamily.VENTUM_H, "H20")).values["suction_sl"].value == 8
    assert prepopulate(_req(CoilType.DX, ProductFamily.NOVA, "B20")).values["suction_sl"].value == 8
    assert prepopulate(_req(CoilType.HGRH, ProductFamily.VENTUM_H, "H15")).values["return_sl"].value == 8


def test_t05_dx_terra_24_gate() -> None:
    r = prepopulate(_req(CoilType.DX, ProductFamily.TERRA, "024"))
    # Terra-invariant constants still populate HIGH.
    assert r.values["header_flange"].value == 1.5
    assert r.values["return_flange"].value == 1.5
    assert r.values["return_bend"].value == 1.5
    assert r.values["suction_hd"].value == 3.5
    assert r.values["dist_i"].value == 3
    assert r.values["dist_orientation"].value == "DOWN"
    assert r.values["dist_extension"].value == 6
    # No coating input -> no coating note (R-080 is gated on coating_set,
    # John 2026-07-15). See test_t17_* for the coated case.
    assert r.values["notes"].value == [
        "Copper Straps Required.",
        DX_DIST_NOTE_DOWN,
    ]
    # Terra = Terra H C, checklist values reliable (John 2026-06-11): resolved HIGH.
    assert r.values["suction_io"].value == 3.25  # R-021
    assert r.values["suction_sl"].value == 10  # R-027
    assert r.values["dist_hd"].value == 4.5  # R-030c (Terra checklist)
    assert r.values["top_flange"].value == 1.625  # R-012
    assert r.values["bottom_flange"].value == 0.5  # R-012 (Terra H C default; John 2026-06-25)
    # No longer gated on terra_variant.
    assert r.blocked_reason is None


def test_terra_v_unit_size_set_diverges_from_terra_h() -> None:
    """Terra V has 4 sizes Terra H lacks (060/072/084/100): the size gate accepts
    them for Terra V and hard-blocks them for Terra H / Terra H C (John 2026-06-29)."""
    for size in ("060", "072", "084", "100"):
        rv = prepopulate(
            _req(CoilType.DX, ProductFamily.TERRA, size,
                 terra_variant=TerraVariant.TERRA_V)
        )
        assert rv.blocked_reason is None
        # The Terra V variant constants still resolve HIGH for the new sizes.
        assert rv.values["bottom_flange"].value == 0.625  # R-012v
        assert rv.values["top_flange"].value == 0.625  # R-012v
        assert rv.values["suction_io"].value == 2.75  # R-021v
        assert rv.values["suction_sl"].value == 12  # R-027v
        # Terra H / Terra H C top out at 048 -> 060+ is an unknown size.
        rh = prepopulate(
            _req(CoilType.DX, ProductFamily.TERRA, size,
                 terra_variant=TerraVariant.TERRA_H)
        )
        assert rh.blocked_reason == "unknown_unit_size"


def test_terra_v_has_own_casing_dims_independent_of_terra_h() -> None:
    """Terra V (vertical) has its OWN R-074 casing table (TERRA_V|INTEGRATED|<size>),
    distinct from Terra H, for all 13 sizes incl. the V-only 060/072/084/100. Values
    transcribed from the Terra Vertical Overall Dimensions sheet (John 2026-06-30):
    Unit Width -> casing_width, Unit Height -> casing_height (review-required, MEDIUM)."""
    expect = {  # representative sizes across the 5 sheet groups (incl. V-only 060/100)
        "006": (30, 51), "024": (44, 62), "048": (48, 78),
        "060": (69, 78), "100": (77, 80),
    }
    for size, (w, h) in expect.items():
        r = prepopulate(_req(CoilType.DX, ProductFamily.TERRA, size,
                             terra_variant=TerraVariant.TERRA_V, application="INTEGRATED"))
        assert r.blocked_reason is None, size
        assert r.suggestions["casing_width"].value == w, size
        assert r.suggestions["casing_height"].value == h, size
        assert r.suggestions["casing_width"].review_required is True, size
    # Terra V must NOT borrow Terra H's casing: shared size 024 differs, and Terra H
    # itself is unchanged (V=44x62 vs H=62x21).
    h024 = prepopulate(_req(CoilType.DX, ProductFamily.TERRA, "024",
                            terra_variant=TerraVariant.TERRA_H, application="INTEGRATED"))
    assert h024.suggestions["casing_width"].value == 62
    assert h024.suggestions["casing_height"].value == 21


def test_t06_dx_nova_cd_single_circuit() -> None:
    r = prepopulate(
        _req(CoilType.DX, ProductFamily.NOVA, "B20", rows=4, circuits=1,
             suction_conn_size=0.875)
    )
    assert r.values["casing_depth"].value == 5.5
    assert r.values["casing_depth"].confidence == Confidence.HIGH


def test_t07_dx_nova_cd_multi_circuit_and_spacing() -> None:
    r = prepopulate(
        _req(CoilType.DX, ProductFamily.NOVA, "B20", rows=4, circuits=3,
             suction_conn_size=1.625)
    )
    assert r.values["casing_depth"].value == 9.5
    assert r.values["return_spacing"].value == [1.625, 4.75, 7.875]


def test_distributor_s_checklist_even_spacing() -> None:
    # R-034 resolved to checklist even-spacing: ROUND(k*CD/(circuits+1)).
    # rows=12 -> CD=12.5 (base); circuits=3 -> [3, 6, 9].
    r = prepopulate(_req(CoilType.DX, ProductFamily.NOVA, "B20", rows=12, circuits=3))
    assert r.values["dist_s"].value == [3, 6, 9]


def test_t08_hgrh_nova_c20() -> None:
    r = prepopulate(_req(CoilType.HGRH, ProductFamily.NOVA, "C20"))
    assert r.values["supply_io"].value == 2
    assert r.values["return_io"].value == 2
    assert r.values["hd"].value == 3.5
    assert r.values["return_sl"].value == 8
    assert r.values["conn_angle"].value == "LAS"
    assert r.values["top_flange"].value == 0.625
    assert r.values["return_bend"].value == 1.5
    # No coating input -> no coating note (R-081 coating_set, John 2026-07-15).
    assert r.values["notes"].value == ["Copper Straps Required."]
    # supply_sl is MEDIUM (R-044a) -> suggestion only.
    assert r.suggestions["supply_sl"].value == 6
    assert "supply_sl" not in r.values


def test_t09_hgrh_ventum_plus_v20() -> None:
    r = prepopulate(_req(CoilType.HGRH, ProductFamily.VENTUM_PLUS, "V20"))
    assert r.values["top_flange"].value == 1
    assert r.values["bottom_flange"].value == 1
    assert r.values["return_sl"].value == 10
    assert r.values["hd"].value == 3.5
    assert r.values["supply_io"].value == 2
    # supply_sl=6 confirmed by John for Ventum+ (R-044c), promoted MEDIUM->HIGH
    # 2026-07-06 (auto-drawn). Nova/Ventum H rule R-044a stays MEDIUM (see t08).
    assert r.values["supply_sl"].value == 6
    assert r.values["supply_sl"].confidence == Confidence.HIGH
    assert "supply_sl" not in r.suggestions


def test_r048_hgrh_positions_multi_circuit() -> None:
    """R-048 conditional emission: HGRH with circuits+conn_size+rows present emits
    return_position at HIGH (auto-drawn) and supply_position at MEDIUM (review-
    required). John 2026-07-15: the supply≠return defect is corrected — supply uses
    the documented Supply = CD - [(Xmax+2)*D + (Xmax-1)*1.5], NOT the return list —
    but stays review-required (never HIGH) because that SOP formula is unverified and
    can yield out-of-range values (here CD=3.75 < the 4.0 connection run -> -0.25);
    formula verification is open in docs/wiki/open-questions.md."""
    r = prepopulate(
        _req(CoilType.HGRH, ProductFamily.NOVA, "B20", circuits=2, conn_size=0.625, rows=2)
    )
    # return: x=1 -> 0.625 ; x=2 -> 2*0.625 + 1.5 = 2.75 (HIGH, verified)
    assert r.values["return_position"].value == [0.625, 2.75]
    assert r.values["return_position"].confidence == Confidence.HIGH
    # supply is a distinct value from the OPPOSITE edge: CD - [(2+2)*0.625 + (2-1)*1.5]
    cd = r.values["casing_depth"].value
    assert r.suggestions["supply_position"].value == round(cd - (4 * 0.625 + 1.5), 4)
    assert r.suggestions["supply_position"].value != r.values["return_position"].value
    assert r.suggestions["supply_position"].confidence == Confidence.MEDIUM
    assert "supply_position" not in r.values  # never auto-drawn as confirmed


def test_r048_hgrh_positions_missing_inputs_when_no_circuits() -> None:
    """R-048 skips (not blocked) when its trigger inputs are absent: the fields
    appear in neither values nor suggestions, and the missing inputs are surfaced."""
    r = prepopulate(_req(CoilType.HGRH, ProductFamily.NOVA, "B20"))
    assert "supply_position" not in r.values and "supply_position" not in r.suggestions
    assert "return_position" not in r.values and "return_position" not in r.suggestions
    for inp in ("circuits", "conn_size", "rows"):
        assert inp in r.missing_inputs


def test_r085_back_to_back_mounting_high_when_flagged() -> None:
    """R-085 conditional emission: back_to_back=True fires the only_when gate and
    emits the mounting-hole note at HIGH (auto-drawn)."""
    r = prepopulate(_req(CoilType.DX, ProductFamily.NOVA, "B20", back_to_back=True))
    assert (
        r.values["back_to_back_mounting"].value
        == 'Mounting Holes, Bolts, 0.3125", 12" spacing'
    )
    assert r.values["back_to_back_mounting"].confidence == Confidence.HIGH


def test_r085_absent_when_not_flagged() -> None:
    """R-085 only_when gate: without back_to_back the field is not emitted at all
    (neither values nor suggestions). Reachable only via direct construction — the
    production build_header_request path does not wire back_to_back (see
    docs/wiki/open-questions.md)."""
    r = prepopulate(_req(CoilType.DX, ProductFamily.NOVA, "B20"))
    assert "back_to_back_mounting" not in r.values
    assert "back_to_back_mounting" not in r.suggestions


def test_t10_hgrh_terra_12_gate() -> None:
    r = prepopulate(_req(CoilType.HGRH, ProductFamily.TERRA, "012"))
    assert r.values["hd"].value == 3.5
    assert r.values["conn_angle"].value == "LAS"
    assert r.values["return_bend"].value == 1.5
    # Terra = Terra H C, checklist values reliable (John 2026-06-11): resolved HIGH.
    assert r.values["return_io"].value == 3.25  # R-042
    assert r.values["return_sl"].value == 10  # R-045b
    assert r.values["top_flange"].value == 1.625  # R-012
    assert r.values["bottom_flange"].value == 0.5  # R-012 (Terra H C default; John 2026-06-25)
    assert r.blocked_reason is None


def test_hgrh_terra_h_supply_io_resolves() -> None:
    """R-040b: TERRA H / Terra H C HGRH supply I/O = 2 (HIGH). Terra V uses its own
    SOP value (R-046, supply I/O = 2.75), John 2026-06-28 SOP-confirmed."""
    for variant in (TerraVariant.TERRA_H, TerraVariant.TERRA_H_C):
        r = prepopulate(_req(CoilType.HGRH, ProductFamily.TERRA, "024", terra_variant=variant))
        assert r.values["supply_io"].value == 2  # R-040b HIGH
        assert r.values["supply_io"].review_required is False
    # Terra V: R-046 SOP values now HIGH (supply I/O=2.75, supply SL=5, return SL=12).
    rv = prepopulate(_req(CoilType.HGRH, ProductFamily.TERRA, "024", terra_variant=TerraVariant.TERRA_V))
    assert rv.values["supply_io"].value == 2.75
    assert rv.values["supply_sl"].value == 5
    assert rv.values["return_sl"].value == 12


def test_t11_hgrh_nova_single_feed() -> None:
    r = prepopulate(_req(CoilType.HGRH, ProductFamily.NOVA, "C20", feeds=1))
    # R-049 single-feed note is intentionally suppressed (John 2026-06-15): a
    # single-feed HGRH is treated as a standard one-header HGRH, no note emitted.
    assert "single_feed_note" not in r.suggestions
    assert "single_feed_note" not in r.values
    assert "single_feed_note" not in r.blocked
    # R-050 single-feed extension is unaffected (separate dimension, not a note).
    assert r.suggestions["single_feed_ext"].value == 3
    assert r.suggestions["single_feed_ext"].confidence == Confidence.MEDIUM


def test_t12_cwc_nova_a16_feeds_absent() -> None:
    r = prepopulate(_req(CoilType.CWC, ProductFamily.NOVA, "A16"))
    assert r.values["return_bend"].value == 1.875  # R-006 rule-of-thumb (John 2026-06-29; was 2.25)
    assert r.values["header_flange"].value == 1.5
    assert r.values["return_flange"].value == 1.5
    assert r.values["sl"].value == 8
    assert r.values["size_class"].value == "NOVA_1IN"
    assert r.values["notes"].value[0].startswith("Vent & Drain installed")
    # feeds absent -> io/hd are suggestions reporting missing feeds.
    assert r.suggestions["io"].value == 2.3125
    assert "feeds" in r.suggestions["io"].missing_inputs
    assert r.suggestions["hd"].value == 4
    assert "feeds" in r.suggestions["hd"].missing_inputs
    # TF/BF resolved to checklist value 0.625 (R-013, John 2026-06-11).
    assert r.values["top_flange"].value == 0.625
    assert r.values["bottom_flange"].value == 0.625


def test_t13_cwc_ventum_plus_v30() -> None:
    r = prepopulate(_req(CoilType.CWC, ProductFamily.VENTUM_PLUS, "V30"))
    assert r.values["top_flange"].value == 1
    assert r.values["bottom_flange"].value == 1
    assert r.values["return_bend"].value == 1.875  # R-006 rule-of-thumb (John 2026-06-29; was 2.25)
    assert r.values["sl"].value == 10
    # Per John (2026-06-11): feeds absent -> io/hd are MEDIUM suggestions,
    # consistent with T12 (not T13's literal "Confidence=High").
    assert r.suggestions["io"].value == 2.3125
    assert r.suggestions["hd"].value == 4


def test_t14_hwc_ventum_plus_single_feed() -> None:
    r = prepopulate(_req(CoilType.HWC, ProductFamily.VENTUM_PLUS, "V60", feeds=1))
    assert r.values["sl"].value == 14
    assert r.suggestions["io"].value == "TBD"
    assert r.suggestions["io"].review_required is True
    assert r.suggestions["hd"].value == "N/A"
    assert r.suggestions["hd"].review_required is True


def test_t15_hwc_nova_multi_feed_cd() -> None:
    r = prepopulate(
        _req(CoilType.HWC, ProductFamily.NOVA, "C30", feeds=2, rows=2)
    )
    assert r.values["sl"].value == 8
    assert r.values["io"].value == 2.3125
    assert r.values["hd"].value == 4
    assert r.values["casing_depth"].value == 4.625


def test_t16_cwc_terra_18_gate() -> None:
    r = prepopulate(_req(CoilType.CWC, ProductFamily.TERRA, "018"))
    assert r.values["return_bend"].value == 1.875  # R-006 rule-of-thumb (John 2026-06-29; was 2.25)
    assert r.values["header_flange"].value == 1.5
    assert r.values["notes"].value[0].startswith("Vent & Drain installed")
    # CWC/HWC have no coating process -> no coating note appended.
    assert r.values["notes"].value == [r.values["notes"].value[0]]
    # Terra = Terra H C, checklist values reliable (John 2026-06-11): resolved HIGH.
    assert r.values["io"].value == 3.25  # R-061
    assert r.values["sl"].value == 10  # R-065
    assert r.values["top_flange"].value == 1.625  # R-014
    assert r.values["bottom_flange"].value == 0.5  # R-014 (Terra H C default; John 2026-06-25)
    assert r.blocked_reason is None


def test_terra_flanges_h_c_asymmetric_v_symmetric_all_coil_types() -> None:
    """Terra H C flanges are asymmetric TF=1.625/BF=0.5 (John 2026-06-25); Terra V
    flanges are symmetric TF=BF=0.625 (John 2026-06-30, corrected from 1.625/0.375).
    R-012/R-014 set the Terra-H-C default; R-012v/R-014v override Terra V (both flanges)."""
    sizes = {CoilType.DX: "024", CoilType.HGRH: "012", CoilType.CWC: "018", CoilType.HWC: "018"}
    for coil, size in sizes.items():
        h_c = prepopulate(
            _req(coil, ProductFamily.TERRA, size, terra_variant=TerraVariant.TERRA_H_C)
        )
        assert h_c.values["bottom_flange"].value == 0.5, coil
        assert h_c.values["top_flange"].value == 1.625, coil

        terra_v = prepopulate(
            _req(coil, ProductFamily.TERRA, size, terra_variant=TerraVariant.TERRA_V)
        )
        assert terra_v.values["bottom_flange"].value == 0.625, coil  # R-012v / R-014v
        assert terra_v.values["top_flange"].value == 0.625, coil  # R-012v / R-014v


def test_t17_dx_coating_note_only_when_a_custom_coating_is_required() -> None:
    """T17's golden case IS a coated coil (DX/NOVA/B20, coating=HERESITE).

    Per John (2026-07-15) the coating note fires only when a custom coating is
    actually required — "do not coat the last 5-6 inches" says nothing about a coil
    nobody is coating. This SUPERSEDES John 2026-06-11 ("no coating trigger field, so
    always append"); the trigger now flows from the submittal's coil_coating. The note
    itself is still HIGH (SOP Rev H wording), never held back as a conflict.
    """
    with_coating = prepopulate(
        _req(CoilType.DX, ProductFamily.NOVA, "B20", coating="HERESITE")
    )
    assert with_coating.values["notes"].value == [
        "Copper Straps Required.",
        DX_COATING_NOTE,
        DX_DIST_NOTE_DOWN,
    ]
    assert "coating_note" not in with_coating.blocked

    # Uncoated, and coating simply not stated, both drop the note. Oxygen8 submittals
    # do not mention coating when there is none, so absent must read as "no coating".
    for coating in (None, "NONE", "none", " None "):
        notes = prepopulate(
            _req(CoilType.DX, ProductFamily.NOVA, "B20", coating=coating)
        ).values["notes"].value
        assert notes == ["Copper Straps Required.", DX_DIST_NOTE_DOWN], coating


def test_t17b_hgrh_coating_note_only_when_a_custom_coating_is_required() -> None:
    # R-081 is the HGRH twin of R-080 and is gated identically.
    with_coating = prepopulate(
        _req(CoilType.HGRH, ProductFamily.NOVA, "B20", coating="ELECTROFIN")
    )
    assert HGRH_COATING_NOTE in with_coating.values["notes"].value
    without = prepopulate(_req(CoilType.HGRH, ProductFamily.NOVA, "B20"))
    assert HGRH_COATING_NOTE not in without.values["notes"].value


def test_every_non_none_coating_option_triggers_the_note() -> None:
    """"Custom coating" == any stated non-NONE value: every option in the checklist
    vocabulary other than NONE is a custom coating process, so `coating_set` and
    "custom coating required" coincide. Pins that, so adding a *standard* coating to
    the vocabulary later fails here instead of silently mis-noting every coil."""
    from coilforge.checklist.template_map import COATING_DEFAULT, COATING_OPTIONS

    assert COATING_DEFAULT == "NONE"
    for option in COATING_OPTIONS:
        notes = prepopulate(
            _req(CoilType.DX, ProductFamily.NOVA, "B20", coating=option)
        ).values["notes"].value
        assert (DX_COATING_NOTE in notes) is (option != "NONE"), option


def test_distributor_extension_note_up_for_ventum_plus_dx_else_down() -> None:
    # R-035a/b: the distributor extension note branches on product line exactly like
    # the distributor orientation (R-031 DOWN / R-032 UP). Ventum+ DX -> "Upwards";
    # every other DX line -> "Downwards"; never both, never on HGRH/CWC/HWC.
    up = prepopulate(_req(CoilType.DX, ProductFamily.VENTUM_PLUS, "V40"))
    assert up.values["notes"].value[-1] == DX_DIST_NOTE_UP
    assert DX_DIST_NOTE_DOWN not in up.values["notes"].value

    for pf, size in (
        (ProductFamily.NOVA, "B20"),
        (ProductFamily.VENTUM_H, "H10"),
        (ProductFamily.TERRA, "024"),
    ):
        down = prepopulate(_req(CoilType.DX, pf, size))
        assert down.values["notes"].value[-1] == DX_DIST_NOTE_DOWN, pf
        assert DX_DIST_NOTE_UP not in down.values["notes"].value, pf

    # Terra V DX (variant of TERRA) still resolves the Down note.
    terra_v = prepopulate(
        _req(CoilType.DX, ProductFamily.TERRA, "060", terra_variant=TerraVariant.TERRA_V)
    )
    assert terra_v.values["notes"].value[-1] == DX_DIST_NOTE_DOWN

    # No distributor note on HGRH or water coils (DX-only rule).
    hgrh = prepopulate(_req(CoilType.HGRH, ProductFamily.NOVA, "B20"))
    assert not any("Distributor" in n for n in hgrh.values["notes"].value)
    for coil in (CoilType.CWC, CoilType.HWC):
        water = prepopulate(_req(coil, ProductFamily.NOVA, "C30", feeds=2, rows=2))
        assert not any("Distributor" in n for n in water.values["notes"].value)


def test_hot_gas_bypass_distributor_note_replaces_the_plain_down_note() -> None:
    # R-035c displaces R-035b (gated not_hot_gas_bypass) rather than adding to it, so
    # the "exactly one distributor note per DX" invariant holds. Nova / Ventum H are the
    # only lines that can select hot gas bypass (John 2026-07-15).
    for pf, size in ((ProductFamily.NOVA, "B20"), (ProductFamily.VENTUM_H, "H10")):
        notes = prepopulate(_req(CoilType.DX, pf, size, hot_gas_bypass=True)).values[
            "notes"
        ].value
        assert notes[-1] == DX_DIST_NOTE_HGBP, pf
        assert DX_DIST_NOTE_DOWN not in notes, pf  # displaced, not duplicated
        assert len([n for n in notes if "Distributor 6" in n or "ASC" in n]) == 1, pf


def test_non_hgbp_dx_keeps_the_plain_down_note() -> None:
    # Regression guard for the R-035b `not_hot_gas_bypass` gate: an ordinary DX coil
    # (hot_gas_bypass False or simply absent) is unchanged.
    for hgbp in (False, None):
        notes = prepopulate(
            _req(CoilType.DX, ProductFamily.NOVA, "B20", hot_gas_bypass=hgbp)
        ).values["notes"].value
        assert notes[-1] == DX_DIST_NOTE_DOWN, hgbp
        assert DX_DIST_NOTE_HGBP not in notes, hgbp


def test_ventum_plus_hgbp_keeps_the_up_note() -> None:
    # R-035c is Nova/Ventum-H-only, so it never displaces the Ventum+ Up note (R-035a).
    notes = prepopulate(
        _req(CoilType.DX, ProductFamily.VENTUM_PLUS, "V40", hot_gas_bypass=True)
    ).values["notes"].value
    assert notes[-1] == DX_DIST_NOTE_UP
    assert DX_DIST_NOTE_HGBP not in notes


def test_terra_hgbp_yields_no_distributor_note() -> None:
    # Terra cannot select hot gas bypass, so DX+Terra+HGBP is an impossible combo (its
    # drawing is omitted at the submittal gate). It yields NO distributor note --
    # fail-closed beats emitting a wrong one.
    notes = prepopulate(
        _req(CoilType.DX, ProductFamily.TERRA, "024", hot_gas_bypass=True)
    ).values["notes"].value
    assert not any("Distributor 6" in n or "ASC" in n for n in notes)


def test_terra_split_phase1_new_families_normalize_to_terra_variant() -> None:
    # Terra split (phased): TERRA_H / TERRA_V are first-class product families that
    # normalize onto TERRA + terra_variant at the engine entry, so results are identical
    # to the old (TERRA, terra_variant) form. Exercises the DX note/spacing path AND the
    # CWC direct-check path (product == ProductFamily.TERRA branches).
    def vals(r):
        return {k: r.values[k].value for k in r.values}

    # Terra V DX
    assert vals(prepopulate(_req(CoilType.DX, ProductFamily.TERRA_V, "060"))) == vals(
        prepopulate(
            _req(CoilType.DX, ProductFamily.TERRA, "060", terra_variant=TerraVariant.TERRA_V)
        )
    )
    # Terra H DX (H is the default variant)
    assert vals(prepopulate(_req(CoilType.DX, ProductFamily.TERRA_H, "024"))) == vals(
        prepopulate(_req(CoilType.DX, ProductFamily.TERRA, "024"))
    )
    # Terra V CWC — hits the product == ProductFamily.TERRA direct checks (R-061v/R-065v)
    assert vals(prepopulate(_req(CoilType.CWC, ProductFamily.TERRA_V, "060", feeds=2, rows=2))) == vals(
        prepopulate(
            _req(
                CoilType.CWC, ProductFamily.TERRA, "060",
                terra_variant=TerraVariant.TERRA_V, feeds=2, rows=2,
            )
        )
    )
    # An explicit TERRA_H_C sub-variant is preserved (never overridden by normalization).
    hc = prepopulate(
        _req(CoilType.DX, ProductFamily.TERRA_H, "024", terra_variant=TerraVariant.TERRA_H_C)
    )
    assert hc.values["notes"].value[-1] == DX_DIST_NOTE_DOWN


def test_t18_dx_nova_hot_gas_bypass() -> None:
    r = prepopulate(
        _req(CoilType.DX, ProductFamily.NOVA, "B20", hot_gas_bypass=True,
             handing="LH")
    )
    assert r.values["asc"].value == "selected"
    assert "asc_orientation" in r.blocked  # R-084 CONFLICT
    assert r.blocked["asc_orientation"].value is None


def test_t19_dx_ventum_h_invalid_size() -> None:
    r = prepopulate(_req(CoilType.DX, ProductFamily.VENTUM_H, "H99"))
    assert r.blocked_reason == "unknown_unit_size"
    assert not r.values
    assert not r.suggestions
    assert not r.blocked


def test_t20_cwc_nova_casing_lookup() -> None:
    r = prepopulate(
        _req(CoilType.CWC, ProductFamily.NOVA, "A16", application="DECOUPLED")
    )
    assert r.suggestions["casing_width"].value == 34
    assert r.suggestions["casing_height"].value == 20
    assert r.suggestions["casing_width"].review_required is True


@pytest.mark.parametrize(
    "coil,product,size,application,width,height",
    [
        # DX/CWC/HGRH share the "DX/CWC" application columns.
        (CoilType.CWC, ProductFamily.NOVA, "A16", "DECOUPLED", 34, 20),
        (CoilType.DX, ProductFamily.NOVA, "C70", "DECOUPLED", 76, 46),
        (CoilType.DX, ProductFamily.TERRA, "024", "INTEGRATED", 62, 21),
        (CoilType.HGRH, ProductFamily.VENTUM_H, "H15", "CPLD EXT", 37, 21),
        (CoilType.DX, ProductFamily.VENTUM_PLUS, "V150", "INTEGRATED", 115.75, 106),
        # HWC uses its own application columns.
        (CoilType.HWC, ProductFamily.NOVA, "A16", "CPLD/DCPLD VERT", 16, 20.625),
        (CoilType.HWC, ProductFamily.VENTUM_H, "H20", "CPLD/DCPLD STD", 39.375, 21),
    ],
)
def test_casing_dims_lookup_from_units_sheet(
    coil, product, size, application, width, height
) -> None:
    r = prepopulate(_req(coil, product, size, application=application))
    assert r.suggestions["casing_width"].value == width
    assert r.suggestions["casing_height"].value == height


def test_casing_dims_missing_without_application() -> None:
    r = prepopulate(_req(CoilType.CWC, ProductFamily.NOVA, "A16"))
    assert "casing_width" not in r.suggestions
    assert "application" in r.missing_inputs


# --------------------------------------------------------------------------- #
# Invariant: confidence gate (constraint #3)
# --------------------------------------------------------------------------- #
def test_confidence_gate_routing_table() -> None:
    """No MEDIUM/LOW/CONFLICT rule may ever route into `values`."""
    rules = load_rule_table()
    for rule in rules:
        conf = rule["confidence"]
        bucket = engine.bucket_for_confidence(Confidence(conf))
        if conf == "HIGH":
            assert bucket == "values", rule["rule_id"]
        else:
            assert bucket != "values", rule["rule_id"]


def test_confidence_gate_holds_across_requests() -> None:
    """Across a broad input sweep, each bucket only holds its confidence tier."""
    coils = list(CoilType)
    products = list(ProductFamily)
    extras = [
        {},
        {"feeds": 1},
        {"feeds": 2},
        {"rows": 4, "circuits": 3, "suction_conn_size": 1.625},
        {"coating": "HERESITE"},
        {"hot_gas_bypass": True, "handing": "LH"},
        {"application": "DECOUPLED"},
    ]
    for coil in coils:
        for product in products:
            for extra in extras:
                r = prepopulate(_req(coil, product, VALID_SIZE[product], **extra))
                for fr in r.values.values():
                    assert fr.confidence == Confidence.HIGH
                for fr in r.suggestions.values():
                    assert fr.confidence == Confidence.MEDIUM
                    assert fr.review_required is True
                for fr in r.blocked.values():
                    assert fr.confidence in (Confidence.LOW, Confidence.CONFLICT)
                    assert fr.value is None
                    assert fr.blocked_reason


# --------------------------------------------------------------------------- #
# Invariant: CD table reproduction (24 values)
# --------------------------------------------------------------------------- #
DX_HGRH_CD = [2.875, 3.75, 4.625, 5.5, 6.375, 7.25, 8.125, 9.0, 9.875, 10.75,
              11.625, 12.5]
CWC_HWC_CD = [3.375, 4.625, 6.0, 7.25, 8.5, 9.875, 11.125, 12.5, 13.75, 15.0,
              16.375, 17.625]


@pytest.mark.parametrize("rows,expected", list(zip(range(1, 13), DX_HGRH_CD)))
def test_cd_table_dx_hgrh(rows: int, expected: float) -> None:
    assert cd_dx_hgrh(rows) == expected


@pytest.mark.parametrize("rows,expected", list(zip(range(1, 13), CWC_HWC_CD)))
def test_cd_table_cwc_hwc(rows: int, expected: float) -> None:
    assert cd_cwc_hwc(rows) == expected


def test_roundup_eighth() -> None:
    assert roundup_eighth(0.866) == 0.875
    assert roundup_eighth(1.0) == 1.0
    assert roundup_eighth(1.001) == 1.125


# --------------------------------------------------------------------------- #
# Invariant: YAML schema validation
# --------------------------------------------------------------------------- #
def test_yaml_schema_validation() -> None:
    rules = load_rule_table()
    seen = set()
    for rule in rules:
        assert rule.get("rule_id"), rule
        assert rule["rule_id"] not in seen, f"duplicate {rule['rule_id']}"
        seen.add(rule["rule_id"])
        assert rule.get("evidence_refs"), rule["rule_id"]
        assert rule["confidence"] in {"HIGH", "MEDIUM", "LOW", "CONFLICT"}


# --------------------------------------------------------------------------- #
# Invariant: prepopulate never raises on valid enum inputs / all-None optionals
# --------------------------------------------------------------------------- #
def test_prepopulate_never_raises() -> None:
    for coil in CoilType:
        for product in ProductFamily:
            # valid size
            prepopulate(_req(coil, product, VALID_SIZE[product]))
            # invalid size (must return unknown_unit_size, not raise)
            prepopulate(_req(coil, product, "ZZZ999"))
