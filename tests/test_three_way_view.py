"""Phase 2b — three-way review view (submittal / CoilForge / engineer).

The load-bearing guard (plan MAJOR-1): once a drawing-param override is reflected, the live
resolved value equals the engineer value, so the CoilForge-logic column MUST read the
event-sourced machine proposal instead — otherwise the machine's original proposal is
invisible for exactly the fields the engineer corrected.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.services.three_way_view import build_three_way_view  # noqa: E402


def _field(view, name):
    return next(f for f in view["fields"] if f["field"] == name)


def test_overridden_drawing_param_logic_reads_machine_proposal_not_override():
    # CD was overridden 3.75 -> 9.5; the panel now shows 9.5 (reflected), and the event
    # snapshot carries the machine proposal 3.75.
    result = {
        "extracted": {},
        "drawing_parameter_set": {"parameters": {
            "CD": {"key": "CD", "value": 9.5, "mode": "manual"},
        }},
        "manual_override_events": [
            {"key": "CD", "previous_value": 3.75, "new_value": 9.5, "override_reason": "measured"},
        ],
    }
    view = build_three_way_view(result)
    cd = _field(view, "CD")
    assert cd["coilforge"] == 3.75, "logic column must be the machine proposal, not the override"
    assert cd["engineer"] == 9.5
    assert cd["submittal"] is None  # computed dim has no raw
    assert cd["coilforge_vs_engineer"] == "mismatch"  # the correction is visible


def test_unoverridden_drawing_param_logic_is_resolved_value():
    result = {
        "extracted": {},
        "drawing_parameter_set": {"parameters": {
            "CD": {"key": "CD", "value": 5.5, "mode": "default"},
        }},
    }
    cd = _field(build_three_way_view(result), "CD")
    assert cd["coilforge"] == 5.5
    assert cd["engineer"] is None
    assert cd["coilforge_vs_engineer"] is None  # no override -> no engineer verdict


def test_spec_override_three_columns():
    result = {
        "extracted": {"rows": 4},
        "drawing_parameter_set": {"parameters": {}},
        "spec_overrides": [
            {"field_key": "rows", "previous_value": 4, "new_value": 6, "override_reason": "BOM"},
        ],
    }
    rows = _field(build_three_way_view(result), "rows")
    assert rows["submittal"] == 4        # raw extracted
    assert rows["coilforge"] == 4        # machine value (pre-edit)
    assert rows["engineer"] == 6         # engineer correction
    assert rows["coilforge_vs_engineer"] == "mismatch"


def test_all_empty_fields_are_skipped():
    result = {"extracted": {}, "drawing_parameter_set": {"parameters": {}}}
    view = build_three_way_view(result)
    assert view["fields"] == []


def test_error_result_returns_empty():
    assert build_three_way_view({"error": "gated"})["fields"] == []


def test_drawing_param_rule_id_from_engine_provenance():
    # 1c seam-A: the CD param's engine field is casing_depth; its firing carries the rule.
    result = {
        "extracted": {},
        "drawing_parameter_set": {"parameters": {
            "CD": {"key": "CD", "value": 5.5, "mode": "default"},
        }},
        "engine_provenance": {"firings": [
            {"field_key": "casing_depth", "rule_id": "R-070", "confidence": "HIGH"},
        ]},
    }
    cd = _field(build_three_way_view(result), "CD")
    assert cd["rule_id"] == "R-070"  # bridged CD -> casing_depth -> firing


def test_rule_id_is_none_without_provenance():
    # no engine_provenance (engine didn't run on this derive) -> never fabricated.
    result = {
        "extracted": {},
        "drawing_parameter_set": {"parameters": {
            "CD": {"key": "CD", "value": 5.5, "mode": "default"},
        }},
    }
    assert _field(build_three_way_view(result), "CD")["rule_id"] is None
