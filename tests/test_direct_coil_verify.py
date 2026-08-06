"""Direct Coil entry verifier: diff entered web values against the canonical record.

Asserts the central design: severity is the confidence gate reused (mismatch vs a
'confirmed' value is high, vs 'inferred' is medium), normalization prevents
false alarms (5/8 == 0.625, '47 in' == 47), a blocked CoilForge field is reported
un-verifiable rather than silently passed, and a near-empty parse raises the
low-coverage warning so it can never masquerade as a clean verification.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.contracts.canonical import CanonicalCoilRecord  # noqa: E402
from coilforge.contracts.evidence import SourceEvidence  # noqa: E402
from coilforge.contracts.field_value import FieldValue  # noqa: E402
from coilforge.direct_coil.verify import verify_entered_values  # noqa: E402


def _ev() -> SourceEvidence:
    return SourceEvidence(
        evidence_id="E1", source_type="test", source_id="S1", source_location="fixture"
    )


def _fv(value, *, confidence="confirmed", status="ready", **kwargs) -> FieldValue:
    return FieldValue(
        value=value,
        confidence=confidence,
        status=status,
        review_required=False,
        source_evidence=[_ev()],
        **kwargs,
    )


def _record(**groups) -> CanonicalCoilRecord:
    return CanonicalCoilRecord(record_id="TEST-1", **groups)


def _row_for(report, field_key):
    return next((r for r in report["discrepancies"] if r["field_key"] == field_key), None)


def test_mismatch_against_confirmed_value_is_high_severity() -> None:
    record = _record(geometry={"finned_height": _fv(47.0, confidence="confirmed")})
    report = verify_entered_values({"finned_height_in": "50"}, record)
    row = _row_for(report, "finned_height")
    assert row is not None
    assert row["severity"] == "high"
    assert row["match"] is False
    assert report["mismatch_count"] == 1
    assert report["match_count"] == 0


def test_mismatch_against_inferred_value_is_medium_severity() -> None:
    record = _record(geometry={"finned_height": _fv(47.0, confidence="inferred")})
    report = verify_entered_values({"finned_height_in": "50"}, record)
    assert _row_for(report, "finned_height")["severity"] == "medium"


def test_fraction_and_decimal_match_without_false_alarm() -> None:
    # CoilForge holds 0.625; the human typed 5/8. These are the same size.
    record = _record(connections={"return_connection_size": _fv(0.625, confidence="confirmed")})
    report = verify_entered_values({"return_connection_size": "5/8"}, record)
    assert report["mismatch_count"] == 0
    assert report["match_count"] == 1
    assert _row_for(report, "return_connection_size") is None


def test_unit_suffix_is_stripped_before_compare() -> None:
    record = _record(geometry={"finned_height": _fv(47.0)})
    report = verify_entered_values({"finned_height_in": "47 in"}, record)
    assert report["match_count"] == 1
    assert report["mismatch_count"] == 0


def test_string_field_matches_case_insensitively() -> None:
    record = _record(connections={"coil_hand": _fv("Left")})
    report = verify_entered_values({"coil_hand": "left"}, record)
    assert report["match_count"] == 1
    assert report["mismatch_count"] == 0


def test_blocked_field_is_unverifiable_not_a_pass() -> None:
    record = _record(
        connections={
            "return_connection_size": _fv(
                0.5, confidence="ambiguous", status="blocked", blocked_reason="conflict"
            )
        }
    )
    report = verify_entered_values({"return_connection_size": "0.625"}, record)
    row = _row_for(report, "return_connection_size")
    assert row is not None
    assert row["severity"] == "info"
    assert report["unverifiable_count"] == 1
    assert report["mismatch_count"] == 0
    assert report["match_count"] == 0


def test_all_matching_entry_yields_no_discrepancies() -> None:
    record = _record(
        geometry={"finned_height": _fv(47.0), "rows_deep": _fv(4)},
        connections={"coil_hand": _fv("Left")},
    )
    report = verify_entered_values(
        {"finned_height_in": "47", "rows_deep": "4", "coil_hand": "Left"}, record
    )
    assert report["discrepancies"] == []
    assert report["mismatch_count"] == 0
    assert report["match_count"] == 3


def test_low_coverage_warning_blocks_false_reassurance() -> None:
    # CoilForge has many confirmed values but only one field was read off the page.
    record = _record(
        geometry={"finned_height": _fv(47.0), "rows_deep": _fv(4), "fins_per_inch": _fv(10)},
        connections={"coil_hand": _fv("Left")},
    )
    report = verify_entered_values({"coil_hand": "Left"}, record)
    assert report["fields_read"] == 1
    assert report["fields_expected"] > 4
    assert report["low_coverage_warning"] is True


def test_full_entry_does_not_warn_low_coverage() -> None:
    record = _record(geometry={"finned_height": _fv(47.0)})
    # Enter a value for every comparable field so coverage is high.
    from coilforge.direct_coil.verify import _PASTE_BY_CANONICAL_KEY

    entered = {spec.normalized_key: "x" for spec in _PASTE_BY_CANONICAL_KEY.values()}
    entered["finned_height_in"] = "47"
    report = verify_entered_values(entered, record)
    assert report["low_coverage_warning"] is False


def test_safety_flags_never_relaxed() -> None:
    record = _record(geometry={"finned_height": _fv(47.0)})
    report = verify_entered_values({"finned_height_in": "47"}, record)
    assert report["export_allowed"] is False
    assert report["raw_private_data_returned"] is False
    assert report["production_drawing_approval_claimed"] is False
