"""Stage — Ambient submittal->package builder (transcription + acceptance band).

Guards the load-bearing invariants: transcription reads the REAL submittal candidate keys
(not the Ambient parser's ``*_in`` vocabulary — a wrong key would read present data as
missing), no calculation / no selection engine, never-invent (absent essentials flagged),
tagless kept-not-dropped, and the review-aid safety contract.

All cases drive a SUBMITTAL-parsed candidate (the sanitized DX fixture), never the Ambient
report parser — the fixture's key names are exactly what production produces.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ambient.package import (
    _PERFORMANCE_FIELDS,
    build_ambient_package,
)
from coilforge.coil_utilities.ranges import kit_for_btuh, ranges_for_kit
from coilforge.contracts import FieldValue
from coilforge.submittal.candidate import load_submittal_candidate_fixture

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "sanitized"
    / "submittal_candidate_dx_header1_default.json"
)


def _dx_candidate():
    return load_submittal_candidate_fixture(_FIXTURE)


def test_transcription_uses_real_submittal_keys_verbatim():
    # BLOCKER-1 guard: the fixture stores geometry.rows_deep / finned_height /
    # finned_length and performance.total_capacity_mbh — the builder must read THOSE,
    # copying value + unit verbatim (no MBH re-conversion, no recompute).
    cand = _dx_candidate()
    pkg = build_ambient_package([cand]).as_dict()
    lines = {(l["group"], l["key"]): l for l in pkg["coils"][0]["performance_lines"]}

    assert ("geometry", "rows_deep") in lines
    assert lines[("geometry", "rows_deep")]["value"] == cand.geometry["rows_deep"].value
    assert ("geometry", "finned_height") in lines
    assert lines[("geometry", "finned_height")]["value"] == cand.geometry["finned_height"].value
    cap = lines[("performance", "total_capacity_mbh")]
    assert cap["value"] == cand.performance["total_capacity_mbh"].value  # not divided/recomputed
    assert cap["unit"] == "MBH"
    # every transcribed line stays a review-required target, never an approved value.
    assert all(l["review_required"] is True for l in pkg["coils"][0]["performance_lines"])


def test_no_identity_or_drawing_param_field_becomes_a_line():
    # Allowlist guard (Round-2 MINOR): product_type / coil_hand / airflow_direction /
    # drawing dims must never render as performance lines.
    cand = _dx_candidate()
    pkg = build_ambient_package([cand]).as_dict()
    banned_groups = {"connections", "manufacturing_options", "drawing_parameters"}
    banned_keys = {"airflow_direction", "product_type", "coil_type", "header_type", "coil_hand"}
    for line in pkg["coils"][0]["performance_lines"]:
        assert line["group"] not in banned_groups
        assert line["key"] not in banned_keys
    # and the derived spec table itself excludes them
    assert ("geometry", "airflow_direction") not in {(g, k) for g, k, _ in _PERFORMANCE_FIELDS}


def test_acceptance_band_equals_ranges_primitive():
    cand = _dx_candidate()
    band = build_ambient_package([cand]).as_dict()["coils"][0]["acceptance_band"]
    assert band is not None
    cap = float(cand.performance["total_capacity_mbh"].value)
    kit = kit_for_btuh(cap * 1000.0, 1, band="cooling")
    ranges = ranges_for_kit(kit, 1)
    assert band["ekexva_kit"] == f"EKEXVA{kit}U"
    assert band["capacity_band_mbh"] == [round(ranges.cooling_min_mbh, 1), round(ranges.cooling_max_mbh, 1)]


def test_band_flags_assumed_circuits_and_scales_when_stated():
    # never-invent: a missing circuit count is surfaced (circuits_assumed) rather than
    # silently scaling the band that gets handed to Ambient.
    cand = _dx_candidate()
    geom = dict(cand.geometry)
    geom.pop("circuits", None)
    no_circ = build_ambient_package([cand.model_copy(update={"geometry": geom})]).as_dict()
    band = no_circ["coils"][0]["acceptance_band"]
    assert band["circuits"] == 1 and band["circuits_assumed"] is True

    geom2 = dict(cand.geometry)
    geom2["circuits"] = FieldValue(value=2, manual_override=True)
    with_circ = build_ambient_package([cand.model_copy(update={"geometry": geom2})]).as_dict()
    band2 = with_circ["coils"][0]["acceptance_band"]
    assert band2["circuits"] == 2 and band2["circuits_assumed"] is False
    # the circuit count feeds kit selection, so the band actually responds to it
    # (different kit / band than the 1-circuit assumption).
    assert band2["ekexva_kit"] != band["ekexva_kit"]


def test_capacity_read_under_either_label():
    # Some submittals label capacity nominal_cooling_capacity_mbh instead of
    # total_capacity_mbh; the band must still compute (dual-key read, never-invent).
    cand = _dx_candidate()
    cap_value = cand.performance["total_capacity_mbh"].value
    perf = dict(cand.performance)
    del perf["total_capacity_mbh"]
    perf["nominal_cooling_capacity_mbh"] = FieldValue(
        value=cap_value, unit="MBH", manual_override=True
    )
    swapped = cand.model_copy(update={"performance": perf})
    band = build_ambient_package([swapped]).as_dict()["coils"][0]["acceptance_band"]
    assert band is not None and band["capacity_band_mbh"]


def test_missing_essential_flagged_and_never_fabricated():
    cand = _dx_candidate()
    geom = dict(cand.geometry)
    del geom["finned_height"]
    stripped = cand.model_copy(update={"geometry": geom})
    coil = build_ambient_package([stripped]).as_dict()["coils"][0]
    assert "geometry.finned_height" in coil["missing_fields"]
    # never invented: it must not appear as a line either
    assert ("geometry", "finned_height") not in {
        (l["group"], l["key"]) for l in coil["performance_lines"]
    }


def test_tagless_coil_kept_with_warning_and_no_band():
    cand = _dx_candidate()
    tagless = cand.model_copy(update={"tag": None})
    pkg = build_ambient_package([tagless]).as_dict()
    assert len(pkg["coils"]) == 1  # kept, not dropped
    coil = pkg["coils"][0]
    assert coil["tag"] is None
    assert coil["performance_lines"]  # lines still transcribed
    assert coil["targets"] == {}
    assert coil["acceptance_band"] is None
    assert any("no tag" in w for w in pkg["warnings"])


def test_real_submittal_package_has_nonempty_geometry_and_air_lines():
    # MAJOR-2: prove the transcription surface actually fills from a real submittal.
    cand = _dx_candidate()
    coil = build_ambient_package([cand]).as_dict()["coils"][0]
    groups = {l["group"] for l in coil["performance_lines"]}
    assert "geometry" in groups
    assert "airside_conditions" in groups
    assert len(coil["performance_lines"]) >= 5


def test_safety_flags_are_locked():
    pkg = build_ambient_package([_dx_candidate()]).as_dict()
    assert pkg["export_allowed"] is False
    assert pkg["production_drawing_approval_claimed"] is False
    assert pkg["review_required"] is True


def test_empty_baseline_yields_empty_package():
    pkg = build_ambient_package([]).as_dict()
    assert pkg["coils"] == []
    assert pkg["export_allowed"] is False
