"""Draft a rule-change proposal from an adjudicated divergence. Never applies one.

The whole point of this module is that it writes to `outputs/rule_proposals/` and nowhere
else. `coil_header_rules.yaml` is opened **read-only**; `tests/test_rule_proposal.py` pins
its sha256 across a proposal build, because a generator that could edit the rule table
would be an automatic-rule-application path wearing a review-aid's coat.

Only THREE changes may be proposed
----------------------------------
1. ``demote_confidence``  — an existing rule's confidence lowered.
2. ``narrow_applies_to``  — an existing rule scoped to fewer coils.
3. ``new_medium_scope``   — a NEW rule entering at ``confidence: MEDIUM``.

All three are safe in the same way: they can only ever *reduce* what gets drawn. A new
rule entering at MEDIUM lands in ``suggestions``, which the existing confidence gate
already refuses to draw automatically — so the gate does the enforcing and this module
does not have to be trusted. **A HIGH value inferred from observations is never
proposable**; that is the never-invent line, and observing a number N times is not
evidence of the engineering behind it.

Two traps the proposal must state rather than paper over
--------------------------------------------------------
* **`_SPECIAL_IDS` rules ignore the YAML confidence.** Their Python helper hardcodes
  ``Confidence.MEDIUM``, so a YAML flip on R-048 / R-074 / R-046 … is INERT. A proposal
  targeting one says so in bold, or John applies it and nothing happens.
* **`target_rules` may legitimately be empty.** "No rule governs this field" is a real,
  useful conclusion (the I3 case: the divergence was the slot layer broadcasting a value
  no rule ever authorised). An empty list is a finding, not a failed lookup.

Identifiers
-----------
Proposals are meant to be pasteable into a ticket, so the payload is whitelisted:
``run_id``, ``rules_hash``, ``code_version``, ``slot``, rule ids, and numbers. Project
numbers, file names and customer identifiers are rejected — ``_assert_no_identifiers``
raises rather than redacting, because a silent redaction would let the caller believe it
had recorded provenance it did not.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROPOSAL_DIR = _REPO_ROOT / "outputs" / "rule_proposals"

PROPOSAL_KINDS = ("demote_confidence", "narrow_applies_to", "new_medium_scope")

#: Patterns that must never reach a proposal file. Oxygen8 project numbers are 4 digits,
#: submittal filenames end in .pdf/.xlsx.
_FORBIDDEN = (
    (re.compile(r"\b\d{4}\s+[A-Z][A-Za-z]"), "what looks like a project number + name"),
    (re.compile(r"\.(pdf|xlsx|xls|docx)\b", re.I), "a source file name"),
)


@dataclass(frozen=True)
class RuleProposal:
    proposal_id: str
    kind: str
    field: str
    slot: str
    divergence_id: str
    target_rules: tuple[str, ...]
    rationale: str
    proposed: dict[str, Any]
    current: dict[str, Any]
    inert_rule_ids: tuple[str, ...]
    conflicting_rules: tuple[str, ...]
    diff: str
    replay_plan: str
    evidence_refs: tuple[str, ...] = ()


def _rules() -> list[dict[str, Any]]:
    from coilforge.services.header_prepopulate_engine import load_rule_table

    return load_rule_table()


def _special_ids() -> frozenset[str]:
    from coilforge.services.header_prepopulate_engine import _SPECIAL_IDS

    return frozenset(_SPECIAL_IDS)


def _assert_no_identifiers(text: str) -> None:
    for pattern, what in _FORBIDDEN:
        if pattern.search(text):
            raise ValueError(
                f"proposal text contains {what}; proposals carry rule ids, slots and "
                "numbers only"
            )


def find_target_rules(*, field: str, coil_category: str, product_family: str,
                      terra_variant: str | None, unit_size: str | None) -> list[str]:
    """Rules that could govern ``field`` for this coil, by the engine's OWN scope test.

    Reuses ``_applies`` rather than re-reading ``applies_to`` here: a second
    interpretation of scoping would eventually disagree with the engine, and the proposal
    would name the wrong rule. An empty result is a valid conclusion (see module docstring).
    """
    from coilforge.services.header_prepopulate_engine import _applies
    from coilforge.services.direct_coil_drawing_pipeline import build_header_request

    try:
        request = build_header_request(
            coil_type=coil_category,
            product_type=product_family,
            unit_size=unit_size or "",
            terra_variant=terra_variant,
        )
    except Exception:  # noqa: BLE001 -- an unresolvable coil yields no target, not a crash
        return []
    out = []
    for rule in _rules():
        if rule.get("field") != field:
            continue
        try:
            if _applies(rule, request):
                out.append(rule["rule_id"])
        except Exception:  # noqa: BLE001 -- a rule we cannot evaluate is not a target
            continue
    return out


def conflicting_rules(field: str, target_ids: tuple[str, ...]) -> list[str]:
    """Other rules writing the same ``field``.

    The engine applies rules in YAML order and the generic emitter's ``place()`` overwrites
    per field, so last-writer-wins is real: narrowing rule A can hand the field to rule B
    further down the file rather than blanking it. Reviewing a proposal without this list
    means reviewing half the change.
    """
    return [
        r["rule_id"] for r in _rules()
        if r.get("field") == field and r["rule_id"] not in target_ids
    ]


def _current_block(rule_ids: tuple[str, ...]) -> dict[str, Any]:
    index = {r["rule_id"]: r for r in _rules()}
    return {rid: index[rid] for rid in rule_ids if rid in index}


def _unified_diff(current: dict[str, Any], proposed: dict[str, Any]) -> str:
    before = yaml.safe_dump(current, sort_keys=False, allow_unicode=True).splitlines()
    after = yaml.safe_dump(proposed, sort_keys=False, allow_unicode=True).splitlines()
    return "\n".join(
        difflib.unified_diff(
            before, after, fromfile="coil_header_rules.yaml (current)",
            tofile="coil_header_rules.yaml (proposed)", lineterm="",
        )
    )


def build_rule_proposal(
    *,
    proposal_id: str,
    kind: str,
    field: str,
    slot: str,
    divergence_id: str,
    rationale: str,
    proposed: dict[str, Any],
    coil_category: str,
    product_family: str,
    terra_variant: str | None = None,
    unit_size: str | None = None,
    evidence_refs: tuple[str, ...] = (),
    run_id: str | None = None,
) -> RuleProposal:
    """Assemble a proposal. Pure — reads the rule table, writes nothing."""
    if kind not in PROPOSAL_KINDS:
        raise ValueError(
            f"kind must be one of {PROPOSAL_KINDS} — a proposal that raises a confidence "
            "or asserts a new HIGH value is not expressible on purpose"
        )
    if not rationale.strip():
        raise ValueError("a proposal without a rationale is not reviewable")
    _assert_no_identifiers(f"{rationale} {yaml.safe_dump(proposed, allow_unicode=True)}")

    # A new-scope proposal must enter at MEDIUM: that is the entire safety argument.
    if kind == "new_medium_scope":
        confidences = {
            str(v.get("confidence", "")).upper()
            for v in proposed.values() if isinstance(v, dict)
        } or {str(proposed.get("confidence", "")).upper()}
        if confidences != {"MEDIUM"}:
            raise ValueError(
                "new_medium_scope must propose confidence: MEDIUM — the existing gate is "
                f"what keeps it from being drawn, got {sorted(confidences)}"
            )

    targets = tuple(find_target_rules(
        field=field, coil_category=coil_category, product_family=product_family,
        terra_variant=terra_variant, unit_size=unit_size,
    ))
    current = _current_block(targets)
    inert = tuple(rid for rid in targets if rid in _special_ids())

    replay = (
        "Apply the diff by hand, then re-run the affected coils through "
        "`capture.observe.replay_run(run_id)` and confirm only the intended slots move. "
        "Slots the ledger never stored report `not_replayable` rather than `mismatch` — "
        "read those as 'not covered by this check', not as agreement."
    )
    if run_id:
        replay += f" Reference run: {run_id}."

    return RuleProposal(
        proposal_id=proposal_id,
        kind=kind,
        field=field,
        slot=slot,
        divergence_id=divergence_id,
        target_rules=targets,
        rationale=rationale.strip(),
        proposed=proposed,
        current=current,
        inert_rule_ids=inert,
        conflicting_rules=tuple(conflicting_rules(field, targets)),
        diff=_unified_diff(current, proposed),
        replay_plan=replay,
        evidence_refs=tuple(evidence_refs),
    )


def render_markdown(proposal: RuleProposal) -> str:
    """The human-facing half. Written so a reviewer can act without opening the YAML."""
    lines = [
        f"# {proposal.proposal_id} — {proposal.kind}",
        "",
        f"**Field:** `{proposal.field}`  ·  **Slot:** `{proposal.slot}`  ·  "
        f"**From divergence:** {proposal.divergence_id}",
        "",
        "> **This is a proposal, not a change.** Nothing has been applied. "
        "`coil_header_rules.yaml` is untouched — apply the diff by hand after review.",
        "",
        "## Rationale",
        proposal.rationale,
        "",
        "## Target rules",
    ]
    if proposal.target_rules:
        lines += [f"- `{rid}`" for rid in proposal.target_rules]
    else:
        lines += [
            "- **None.** No rule in the table governs this field for this coil. That is a "
            "finding, not a lookup failure: the value is being produced somewhere other "
            "than the rule engine (typically the slot layer), so a YAML change cannot fix "
            "it and the correct target is that code path.",
        ]
    if proposal.inert_rule_ids:
        lines += [
            "",
            "## ⚠ This proposal is INERT as written",
            "",
            "These targets are handled by `_SPECIAL_IDS` helpers that hardcode their "
            "confidence in Python, so editing the YAML changes nothing:",
            *[f"- `{rid}`" for rid in proposal.inert_rule_ids],
            "",
            "Edit the helper in `services/header_prepopulate_engine.py` instead.",
        ]
    if proposal.conflicting_rules:
        lines += [
            "",
            "## Last-writer-wins neighbours",
            "",
            "Other rules write the same field. Rules apply in YAML order and `place()` "
            "overwrites, so narrowing a target may hand the field to one of these rather "
            "than blanking it:",
            *[f"- `{rid}`" for rid in proposal.conflicting_rules],
        ]
    lines += [
        "",
        "## Proposed change",
        "",
        "```diff",
        proposal.diff or "(no textual diff — new scope item)",
        "```",
        "",
        "## Verification",
        "",
        proposal.replay_plan,
        "",
        "Golden tests naming this field or rule id should be re-run. That list is "
        "grep-derived and therefore **over-reports** — a test mentioning the id may not "
        "assert on it.",
    ]
    if proposal.evidence_refs:
        lines += ["", "## Evidence", *[f"- `{r}`" for r in proposal.evidence_refs]]
    return "\n".join(lines) + "\n"


def write_proposal(proposal: RuleProposal, *, directory: Path | None = None) -> dict[str, str]:
    """Write ``RP-*.yaml`` + ``RP-*.md``. The only write in this module, and it lands in a
    gitignored directory that no code imports."""
    out = directory or _PROPOSAL_DIR
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "proposal_id": proposal.proposal_id,
        "kind": proposal.kind,
        "field": proposal.field,
        "slot": proposal.slot,
        "divergence_id": proposal.divergence_id,
        "target_rules": list(proposal.target_rules),
        "inert_rule_ids": list(proposal.inert_rule_ids),
        "conflicting_rules": list(proposal.conflicting_rules),
        "rationale": proposal.rationale,
        "current": proposal.current,
        "proposed": proposal.proposed,
        "evidence_refs": list(proposal.evidence_refs),
        "replay_plan": proposal.replay_plan,
        "applied": False,
        "export_allowed": False,
    }
    yaml_path = out / f"{proposal.proposal_id}.yaml"
    md_path = out / f"{proposal.proposal_id}.md"
    yaml_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    md_path.write_text(render_markdown(proposal), encoding="utf-8")
    return {"yaml": str(yaml_path), "markdown": str(md_path)}
