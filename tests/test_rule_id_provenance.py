"""1c — engine provenance (`rule_id` on FieldResult).

Guards the two load-bearing properties: the new field is byte-identical in serialization
(so the drawing/engine payload is unchanged), and EVERY FieldResult(...) in the engine
passes rule_id= (an AST guard, not a fixed count — phase5's unmerged copy has a different
constructor count, so counting would be brittle).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.schemas.header_prepopulate import Confidence, FieldResult  # noqa: E402

_ENGINE = (
    Path(__file__).resolve().parents[1]
    / "src" / "coilforge" / "services" / "header_prepopulate_engine.py"
)


def test_rule_id_excluded_from_serialization():
    fr = FieldResult(value=8, confidence=Confidence.HIGH, rule_id="R-070")
    assert fr.rule_id == "R-070"  # available as an attribute for capture
    # exclude=True -> never in the serialized payload, so every dump is byte-identical.
    assert "rule_id" not in fr.model_dump()
    assert "rule_id" not in fr.model_dump_json()


def test_rule_id_default_none_keeps_equality():
    # default None keeps two rule_id-less results equal (existing engine tests compare via
    # .value scalars, but this documents the pydantic-__eq__-includes-excluded caveat).
    a = FieldResult(value=8, confidence=Confidence.HIGH)
    b = FieldResult(value=8, confidence=Confidence.HIGH)
    assert a == b
    assert a != FieldResult(value=8, confidence=Confidence.HIGH, rule_id="R-070")


def test_every_field_result_ctor_passes_rule_id():
    tree = ast.parse(_ENGINE.read_text(encoding="utf-8"))
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "FieldResult"
    ]
    assert calls, "AST walk found no FieldResult(...) — guard is not looking at the engine"
    missing = [c.lineno for c in calls if not any(kw.arg == "rule_id" for kw in c.keywords)]
    assert not missing, f"FieldResult(...) missing rule_id= at lines {missing}"
