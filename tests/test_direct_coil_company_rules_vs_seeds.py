"""The Direct Coil company-rule table in web/app.js vs John's own hand-filled seeds.

Context: until 2026-07-28 the construction rules (Header Material, Connection Type, Casing
Style, ...) were gated to DX only, so an RHHGRC/HGRH coil rendered a wall of "unmapped".
They were widened to condensing on the strength of four coils John transcribed by hand into
`examples/mapping_lab/`. THIS test is what keeps that claim honest: if a rule is ever edited
away from what John actually fills, or the shared/DX-only split drifts, it fails here.

There is no JS test runner in this repo, so the rule table is regex-extracted from the source
(precedent: tests/test_phase2c_ui_compatibility_panel.py, tests/test_phase2e_pdf_coil_intake.py).
Be clear about what that buys: this pins the RULE TABLE against real engineering data, which
is the valuable half. It does NOT prove the rendered mirror is correct — only the browser
eyeball gate does that.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_APP_JS = (_ROOT / "web" / "app.js").read_text(encoding="utf-8")
_LAB = _ROOT / "examples" / "mapping_lab"

_DX_SEEDS = [
    ("case_004_dx_image_seed", 0),
    ("case_006_v60_dx_hgrh_combined_image_seed", 0),
]
_HGRH_SEEDS = [
    ("case_005_hgrh_condensing_image_seed", 0),
    ("case_006_v60_dx_hgrh_combined_image_seed", 1),
]

# John transcribes the casing material without the gauge; he confirmed 2026-07-28 that the
# real CCSI dropdown option carries it, so app.js is right and the seeds are shorthand.
# Recorded here rather than silently skipped, so the divergence stays visible.
_SEED_SHORTHAND = {"casingmaterial": {"Galvanized Steel": "Galvanized Steel 16 gauge"}}


def _function_body(name: str) -> str:
    """Slice one JS function's body by brace matching, so tests can assert what is INSIDE it."""
    start = _APP_JS.index(f"function {name}(")
    brace = _APP_JS.index("{", start)
    depth = 0
    for index in range(brace, len(_APP_JS)):
        if _APP_JS[index] == "{":
            depth += 1
        elif _APP_JS[index] == "}":
            depth -= 1
            if depth == 0:
                return _APP_JS[brace : index + 1]
    raise AssertionError(f"unbalanced braces in {name}")


def _extract_rules(function_name: str, array_name: str) -> dict[str, str]:
    body = _function_body(function_name)
    array_start = body.index(f"const {array_name} = [")
    array_text = body[array_start : body.index("];", array_start)]
    pairs = re.findall(r'\[\s*"([^"]+)"\s*,\s*"([^"]*)"', array_text)
    assert pairs, f"no rules parsed out of {function_name}/{array_name}"
    return {_normalize(label): value for label, value in pairs}


def _normalize(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", label.lower())


def _seed_fields(case: str, coil_index: int) -> dict[str, str]:
    data = json.loads((_LAB / case / "output" / "direct_coil_filled.json").read_text(encoding="utf-8"))
    coil = (data.get("coils") or [data])[coil_index]
    fields = coil.get("fields") or coil
    out = {}
    for key, entry in fields.items():
        value = entry.get("value") if isinstance(entry, dict) else entry
        if value is not None:
            out[_normalize(key)] = value
    return out


def _assert_rules_match_seed(rules: dict[str, str], case: str, coil_index: int) -> None:
    seed = _seed_fields(case, coil_index)
    checked = 0
    for key, rule_value in rules.items():
        if key not in seed:
            continue  # the seed didn't state this field; absence is not a contradiction
        expected = _SEED_SHORTHAND.get(key, {}).get(str(seed[key]), str(seed[key]))
        assert str(rule_value) == expected, (
            f"{case}[{coil_index}] {key}: app.js says {rule_value!r}, John filled {seed[key]!r}"
        )
        checked += 1
    assert checked >= 5, f"{case}[{coil_index}] compared only {checked} rules — extraction drifted"


@pytest.mark.parametrize("case,index", _DX_SEEDS)
def test_shared_rules_match_every_dx_image_seed(case: str, index: int) -> None:
    _assert_rules_match_seed(
        _extract_rules("addSharedConstructionFallbackFields", "optionRules"), case, index
    )


@pytest.mark.parametrize("case,index", _HGRH_SEEDS)
def test_shared_rules_match_every_hgrh_condensing_image_seed(case: str, index: int) -> None:
    # The whole justification for widening the rules to condensing lives in this assertion.
    _assert_rules_match_seed(
        _extract_rules("addSharedConstructionFallbackFields", "optionRules"), case, index
    )


def test_drain_pan_stays_dx_only() -> None:
    # Drain pan is absent from BOTH HGRH seeds and the condensing mirror has no such rows.
    shared = _function_body("addSharedConstructionFallbackFields")
    dx_only = _function_body("addDxOnlyOptionsFallbackFields")
    assert "Drain Pan" not in shared, "drain pan leaked into the shared (DX+HGRH) rule set"
    assert "Drain Pan Type" in dx_only and "Drain Pan Material" in dx_only


def test_system_type_stays_dx_only() -> None:
    # case_006's RHHGRC-1 is "Dual-Circuit Face Split", which the connections-per-header
    # derivation cannot produce — so it must never be applied to a condensing coil.
    assert "directCoilSystemTypeField" not in _function_body("addSharedConstructionFallbackFields")
    assert "directCoilSystemTypeField" in _function_body("addDxOnlyOptionsFallbackFields")


def test_dx_distributor_stays_dx_only() -> None:
    assert "DXDistCapillarySize" in _function_body("addDxOnlyRefrigerantFallbackFields")
    assert "DXDistCapillarySize" not in _function_body("addSharedFoulingFallbackFields")


def test_hgrh_review_defaults_match_both_hgrh_seeds() -> None:
    """The 7 values John approved as HGRH company defaults must equal what he actually fills."""
    body = _function_body("addCondensingDefaultFallbackFields")
    array_text = body[body.index("const defaults = [") : body.index("];")]
    # Each entry is [[label, ...], key, value] — the label LIST matters: a row whose
    # declared sourceLabel differs from its display label resolves through the alias, so a
    # default registered under one label only would silently never reach the mirror.
    rules = {
        _normalize(key): value.strip().strip('"')
        for _labels, key, value in re.findall(
            r'\[\s*\[([^\]]+)\]\s*,\s*"([^"]+)"\s*,\s*("[^"]*"|[^,\]\s]+)\s*,?\s*\]',
            array_text,
        )
    }
    assert len(rules) == 7, f"expected 7 HGRH defaults, parsed {len(rules)}"
    assert '"Evaporating Temperature(°F)"' in array_text, (
        "saturated suction must also register under the Evaporating alias the mirror row "
        "declares as its sourceLabel, or it renders unmapped"
    )
    for case, index in _HGRH_SEEDS:
        seed = _seed_fields(case, index)
        compared = 0
        for key, actual in rules.items():
            if key not in seed:
                continue
            expected = str(seed[key])
            assert actual == expected or float_eq(actual, expected), (
                f"{case}[{index}] {key}: default {actual!r} != seed {expected!r}"
            )
            compared += 1
        assert compared >= 5, f"{case}[{index}] compared only {compared} defaults"


def float_eq(a: str, b: str) -> bool:
    try:
        return float(a) == float(b)
    except ValueError:
        return False
