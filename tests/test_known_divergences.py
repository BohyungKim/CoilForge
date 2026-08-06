"""The shipped registry file itself: schema, key whitelist, unique ids, no identifiers.

These are content tests on `rules/known_divergences.yaml`, separate from the matching
logic in `test_divergence_registry.py`. A malformed entry here would silently vanish (the
loader skips bad rows with a warning rather than raising, so a review never 500s), and a
suppression that vanished would look exactly like a suppression that never applied.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

yaml = pytest.importorskip("yaml")

from coilforge.review.divergence import (  # noqa: E402
    _ALLOWED_ENTRY_KEYS,
    _PROMOTED_PATH,
    REGISTERABLE,
    load_registry,
)

_DOC = yaml.safe_load(_PROMOTED_PATH.read_text(encoding="utf-8"))
_ENTRIES = _DOC.get("divergences") or []


def test_registry_file_parses_and_is_non_empty():
    assert _DOC.get("version") == 1
    assert _ENTRIES, "the promoted registry should carry the D4 Terra V rulings"


def test_every_entry_uses_only_whitelisted_keys():
    for entry in _ENTRIES:
        unknown = set(entry) - _ALLOWED_ENTRY_KEYS
        assert not unknown, f"{entry.get('id')} has unknown keys {sorted(unknown)}"


def test_ids_are_unique():
    ids = [e["id"] for e in _ENTRIES]
    assert len(ids) == len(set(ids)), "duplicate ids make ledger registry_id ambiguous"


def test_every_entry_carries_a_reason_and_evidence():
    # The registry's only claim to not being a machine-accumulated suppression list is
    # that a human stated why, with a citation.
    for entry in _ENTRIES:
        assert str(entry.get("reason", "")).strip(), f"{entry['id']} has no reason"
        assert entry.get("evidence_refs"), f"{entry['id']} cites nothing"
        assert entry.get("adjudicated_by"), f"{entry['id']} has no attribution"


def test_verdicts_are_registerable():
    for entry in _ENTRIES:
        assert entry["verdict"] in REGISTERABLE, (
            f"{entry['id']}: 'unresolved' must never be registered — it would suppress a "
            "row nobody actually decided"
        )


def test_no_customer_identifiers_in_the_registry():
    text = _PROMOTED_PATH.read_text(encoding="utf-8")
    assert not re.search(r"\.(pdf|xlsx|xls)\b", text, re.I), "a source filename leaked in"
    # Oxygen8 project numbers appear as "2968 HTS Houston" — 4 digits then a capitalised
    # word. Rule ids (R-074) and SOP numbers (2024018) do not match this shape.
    assert not re.search(r"\b\d{4}\s+[A-Z][a-z]+\s+[A-Z]", text), "a project name leaked in"


def test_loader_marks_the_shipped_file_as_promoted():
    registry = load_registry(staging_path=Path("does-not-exist.yaml"))
    assert registry.entries
    assert all(e.promoted for e in registry.entries)
    assert not registry.warnings


def test_terra_v_rulings_are_scoped_to_terra_v_only():
    # The load-bearing property of the whole registry: a Terra V ruling must not silence
    # Terra H. Both used to fold to product_family TERRA, so without the variant axis
    # these keys would collide.
    for entry in _ENTRIES:
        if entry.get("terra_variant") == "TERRA_V":
            assert entry.get("product_family") == "TERRA_V"


def test_every_referenced_rule_proposal_resolves():
    # A dangling reference is worse than none: the badge tells John a proposal exists and
    # he goes looking for a file nobody wrote.
    proposals = ROOT / "docs" / "rule_proposals"
    for entry in _ENTRIES:
        ref = entry.get("rule_proposal")
        if not ref:
            continue
        assert list(proposals.glob(f"{ref}-*.md")), f"{entry['id']} cites missing {ref}"


def test_the_repaired_i3_defect_is_not_registered():
    # I3 was CoilForge's own bug and was FIXED (9abe5a7). Registering it would suppress
    # the regression if it ever came back — a repaired defect is not a known gap.
    slots = {e["slot"] for e in _ENTRIES}
    assert "slot.I3" not in slots
