"""Case-retrieval weight tuning harness (Stage 2, Part A5).

Two load-bearing tests mirror the plan's A5.4:
  * NORMAL signal — a discriminating axis with co-occurring same-field corrections along it: the
    single-pass grid must FIND the improvement (flag None, tuned > baseline). The corpus is
    built tie-free so the baseline miss is deterministic.
  * DEGENERATE signal — every corrected field appears on exactly one coil (no cross-coil
    co-occurrence): search_weights must return uniform + "signal_too_weak" and NEVER invent a
    tuned vector.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from coilforge.capture.retrieve import _CATEGORICAL_AXES, _NUMERIC_AXES  # noqa: E402
from coilforge.capture.tuning import (  # noqa: E402
    corrections_available,
    hit_at_k,
    objective_health,
    search_weights,
)

pytest.importorskip("numpy")

_AXES = _CATEGORICAL_AXES + _NUMERIC_AXES


def _case(uid, tag, *, hand=None, header=None, rows=None, field=None, category="DX"):
    feats = {a: None for a in _AXES}
    feats.update(coil_category=category, hand=hand, header_type=header, rows=rows)
    corrections = []
    if field is not None:
        corrections = [{"field_key": field, "stage": "drawing_param",
                        "before": 1, "after": 2, "reason": "r"}]
    return {"coil_uid": uid, "tag": tag, "project_number": "P",
            "features": feats, "corrections": corrections}


def _signal_corpus():
    """Discriminating axis = hand; field 'CD' co-occurs among the LH coils. Built so that under
    UNIFORM weights the k=1 nearest of L1 is the RH coil R1 (a hair closer via a tiny rows nudge
    on L2, range stretched to 100 by A0) -> baseline miss; up-weighting hand flips it -> hit.
    R1's field 'SL' is unshareable (only R1), so it never hits either way (a real corpus trait)."""
    return [
        _case("l1", "L1", hand="LH", header="X", rows=0.0, field="CD"),
        _case("r1", "R1", hand="RH", header="X", rows=0.0, field="SL"),
        _case("l2", "L2", hand="LH", header="Y", rows=1.0, field="CD"),
        _case("a0", "A0", hand="LH", header="Y", rows=100.0, field="CD"),
    ]


def test_corrections_available_counts_corrected_identities():
    cases = _signal_corpus()
    assert corrections_available(cases) == 4
    assert corrections_available([_case("x", "X")]) == 0  # no field -> not corrected


def test_hit_at_k_responds_to_weights_when_signal_exists():
    # The corpus HAS signal: an explicit hand-heavy vector beats uniform at k=1.
    cases = _signal_corpus()
    base = hit_at_k(cases, k=1)
    heavy = hit_at_k(cases, weights={"hand": 2.0}, k=1)
    assert heavy > base


def test_objective_health_reports_headroom_and_cooccurrence():
    health = objective_health(_signal_corpus(), k=1)
    assert health["n_queries"] == 4
    assert health["shareable_fields"] == 1          # only 'CD' is shared (>=2 coils)
    assert health["achievable_hit"] > health["baseline_hit"]  # real headroom


def test_search_weights_recovers_axis_on_real_signal():
    # The single-pass grid must find the improvement the discriminating axis affords.
    result = search_weights(_signal_corpus(), k=1)
    assert result["flag"] is None
    assert result["weights"] is not None
    assert result["tuned_hit"] > result["baseline_hit"]
    assert result["weights"]["hand"] == 2.0          # up-weighted the discriminating axis
    assert "coil_category" not in result["weights"]  # never swept (structurally inert)
    # minimal intervention: only the axis that strictly helps moves; the rest stay uniform.
    assert all(w == 1.0 for a, w in result["weights"].items() if a != "hand")


def test_search_weights_refuses_to_invent_on_degenerate_signal():
    # Every corrected field appears on exactly one coil -> no co-occurrence -> flat objective.
    cases = [
        _case("c1", "C1", hand="LH", header="X", rows=0.0, field="A"),
        _case("c2", "C2", hand="RH", header="Y", rows=1.0, field="B"),
        _case("c3", "C3", hand="LH", header="Z", rows=2.0, field="C"),
    ]
    result = search_weights(cases, k=1)
    assert result["flag"] == "signal_too_weak"
    assert result["weights"] is None                 # uniform kept; nothing invented
    assert result["shareable_fields"] == 0


def test_search_weights_refuses_below_two_queries():
    cases = [_case("c1", "C1", hand="LH", field="A"), _case("x", "X", hand="RH")]
    result = search_weights(cases, k=1)
    assert result["flag"] == "signal_too_weak"
