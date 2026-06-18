from __future__ import annotations

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.adapters import load_sanitized_ez_json
from coilforge.compatibility import (
    build_compatibility_diff_review_packet,
    compare_submittal_and_ez,
)
from coilforge.submittal import load_submittal_candidate_fixture


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "examples" / "sanitized"
SUBMITTAL_FIXTURE = FIXTURE_DIR / "submittal_candidate_dx_header1_default.json"
EZ_FIXTURE = FIXTURE_DIR / "dx_header1_ezc0001_default.json"


def test_review_packet_contains_required_phase_sections() -> None:
    report = compare_submittal_and_ez(
        load_submittal_candidate_fixture(SUBMITTAL_FIXTURE),
        load_sanitized_ez_json(EZ_FIXTURE),
    )

    packet = build_compatibility_diff_review_packet(report)

    assert packet.startswith("# Phase 2C.3 Compatibility Diff Review Packet")
    assert "## Review status" in packet
    assert "## Source path summaries" in packet
    assert "## Compatibility counts" in packet
    assert "## Mismatches requiring review" in packet
    assert "## Source-only values requiring review" in packet
    assert "## John/Engineering decisions needed" in packet


def test_review_packet_reports_no_current_mismatches_and_ez_only_values() -> None:
    report = compare_submittal_and_ez(
        load_submittal_candidate_fixture(SUBMITTAL_FIXTURE),
        load_sanitized_ez_json(EZ_FIXTURE),
    )

    packet = build_compatibility_diff_review_packet(report)

    assert "- Mismatches: `0`" in packet
    assert "`CD` (drawing_parameters.CD)" in packet
    assert "`BF` (drawing_parameters.BF)" in packet
    assert "Export allowed: `False`" in packet
    assert "Production drawing approval: `not_requested_not_granted`" in packet


def test_review_packet_surfaces_mismatches_for_engineering_review() -> None:
    candidate = load_submittal_candidate_fixture(SUBMITTAL_FIXTURE)
    ez_payload = load_sanitized_ez_json(EZ_FIXTURE)
    ez_payload["fin_height"] = 12.5
    report = compare_submittal_and_ez(candidate, ez_payload)

    packet = build_compatibility_diff_review_packet(report)

    assert "- Mismatches: `1`" in packet
    assert "`finned_height` (geometry.finned_height)" in packet
    assert "engineering review required" in packet
