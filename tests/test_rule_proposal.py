"""Rule proposals: the three allowed kinds, the YAML stays untouched, honest empties."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

pytest.importorskip("yaml")

from coilforge.review.rule_proposal import (  # noqa: E402
    PROPOSAL_KINDS,
    build_rule_proposal,
    conflicting_rules,
    find_target_rules,
    render_markdown,
    write_proposal,
)

_RULES_YAML = ROOT / "src" / "coilforge" / "rules" / "coil_header_rules.yaml"


def _sha() -> str:
    return hashlib.sha256(_RULES_YAML.read_bytes()).hexdigest()


def _build(**over):
    kwargs = {
        "proposal_id": "RP-TEST",
        "kind": "demote_confidence",
        "field": "casing_depth",
        "slot": "slot.CD",
        "divergence_id": "KD-001",
        "rationale": "the sheet has no TERRA V branch, so its value is not a comparand",
        "proposed": {"R-070": {"confidence": "MEDIUM"}},
        "coil_category": "HGRH",
        "product_family": "TERRA_V",
        "terra_variant": "TERRA_V",
        "unit_size": "072",
    }
    kwargs.update(over)
    return build_rule_proposal(**kwargs)


# --------------------------------------------------------------------------- #
# the invariant: a proposal never becomes a change
# --------------------------------------------------------------------------- #
def test_building_and_writing_a_proposal_leaves_the_rule_table_byte_identical(tmp_path):
    before = _sha()
    write_proposal(_build(), directory=tmp_path)
    assert _sha() == before, (
        "a generator that can edit coil_header_rules.yaml is an automatic-rule-application "
        "path wearing a review aid's coat"
    )


def test_the_written_payload_declares_it_was_not_applied(tmp_path):
    import yaml

    paths = write_proposal(_build(), directory=tmp_path)
    payload = yaml.safe_load(Path(paths["yaml"]).read_text(encoding="utf-8"))
    assert payload["applied"] is False and payload["export_allowed"] is False
    assert "not a change" in Path(paths["markdown"]).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# only three kinds, all of them safety-reducing
# --------------------------------------------------------------------------- #
def test_only_the_three_safe_kinds_exist():
    assert PROPOSAL_KINDS == ("demote_confidence", "narrow_applies_to", "new_medium_scope")


def test_an_unlisted_kind_is_refused():
    with pytest.raises(ValueError, match="kind must be one of"):
        _build(kind="promote_confidence")


def test_a_new_scope_item_must_enter_at_medium():
    # This is the whole safety argument: MEDIUM lands in `suggestions`, which the existing
    # confidence gate already refuses to draw. The gate enforces it, not this module.
    with pytest.raises(ValueError, match="must propose confidence: MEDIUM"):
        _build(kind="new_medium_scope", proposed={"R-999": {"confidence": "HIGH"}})
    ok = _build(kind="new_medium_scope", proposed={"R-999": {"confidence": "MEDIUM"}})
    assert ok.kind == "new_medium_scope"


def test_a_proposal_without_a_rationale_is_refused():
    with pytest.raises(ValueError, match="rationale"):
        _build(rationale="  ")


# --------------------------------------------------------------------------- #
# identifiers
# --------------------------------------------------------------------------- #
def test_a_project_identifier_in_the_rationale_is_refused():
    with pytest.raises(ValueError, match="project number"):
        _build(rationale="seen on 2968 HTS Houston")


def test_a_source_filename_in_the_rationale_is_refused():
    with pytest.raises(ValueError, match="file name"):
        _build(rationale="see Submittal.pdf page 4")


# --------------------------------------------------------------------------- #
# target resolution
# --------------------------------------------------------------------------- #
def test_target_rules_come_from_the_engines_own_scope_test():
    targets = find_target_rules(
        field="casing_depth", coil_category="HGRH", product_family="TERRA_V",
        terra_variant="TERRA_V", unit_size="072",
    )
    assert targets, "casing_depth should have at least one governing rule"
    assert all(t.startswith("R-") for t in targets)


def test_no_governing_rule_is_a_valid_conclusion_not_a_failure():
    # The I3 case: the value was produced by the slot layer, which no YAML rule authorises.
    proposal = _build(field="a_field_no_rule_writes", proposed={})
    assert proposal.target_rules == ()
    md = render_markdown(proposal)
    assert "No rule in the table governs this field" in md
    assert "slot layer" in md, "the reader needs to be told where to look instead"


def test_a_special_ids_target_is_flagged_inert():
    # R-074 hardcodes Confidence.MEDIUM in its Python helper, so a YAML flip does nothing.
    proposal = _build(field="casing_dims", proposed={"R-074": {"confidence": "MEDIUM"}})
    if proposal.target_rules:
        assert proposal.inert_rule_ids, "a _SPECIAL_IDS target must be called out"
        assert "INERT" in render_markdown(proposal)


def test_last_writer_wins_neighbours_are_listed():
    targets = tuple(find_target_rules(
        field="casing_depth", coil_category="HGRH", product_family="TERRA_V",
        terra_variant="TERRA_V", unit_size="072",
    ))
    others = conflicting_rules("casing_depth", targets)
    assert set(others).isdisjoint(targets)


def test_the_replay_plan_warns_that_not_replayable_is_not_agreement():
    assert "not_replayable" in _build().replay_plan
