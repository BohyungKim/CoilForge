"""Phase 4 — Ambient comparator tolerance + the shared _match regression guard."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ambient.compare import field_verdict
from coilforge.checklist.compare import _match


def test_match_no_kwargs_is_unchanged():
    # The checklist/ccsi callers pass no kwargs — behavior must be byte-identical.
    assert _match(1.0, 1.005) == "match"      # within 0.01
    assert _match(1.0, 1.05) == "mismatch"    # beyond 0.01
    assert _match(None, None) == "both_missing"
    assert _match(1.0, None) == "missing_one"
    assert _match("L", "L") == "match"
    assert _match("L", "K") == "mismatch"


def test_capacity_relative_tolerance():
    # Capacity ±2%: 171.5 vs 173 (<2%) matches; 171.5 vs 190 (>2%) mismatches.
    assert field_verdict(171.5, 173.0, "capacity") == "match"
    assert field_verdict(171.5, 190.0, "capacity") == "mismatch"


def test_count_fields_are_exact():
    assert field_verdict(5, 5, "count") == "match"
    assert field_verdict(5, 6, "count") == "mismatch"


def test_missing_side_flags():
    assert field_verdict(None, 5, "count") == "missing_one"
    assert field_verdict(None, None, "capacity") == "both_missing"
