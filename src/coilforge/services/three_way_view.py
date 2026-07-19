"""Three-way review view (Phase 2b): for one coil, put the three sources of a field's
value side by side so a wrong mapping surfaces —

    submittal (raw extracted)  vs  CoilForge (engine-resolved)  vs  engineer (manual override)

This is a REVIEW AID only. It never changes a value, never approves a mapping, and never
invents: a cell with no value is ``None`` and rendered as a gap, not a guess. The
accumulation that actually trains the system lives in the append-only ``correction`` ledger
(written elsewhere); this is the per-coil surfacing of the same triple.

Sourcing (the load-bearing rule — MAJOR-1 from the plan review):
- Phase-1 reflection writes a drawing-param override into ``slot_values`` and stamps the
  panel ``mode='manual'`` with the override value. So the *live* resolved value for a
  corrected field EQUALS the engineer value — reading it as the "CoilForge logic" column
  would make (logic vs engineer) a trivial match and hide the machine's original proposal.
  Therefore, when an override exists, the CoilForge-logic column is read from the
  event-sourced **machine proposal** (``manual_override_events[].previous_value`` /
  ``spec_overrides[].previous_value``), falling back to the live resolved value only when no
  override exists for that field.

``rule_id`` is filled from the seam-A engine provenance (``result['engine_provenance']``,
roadmap 1c) via ``PARAM_TO_ENGINE_FIELD``: a drawing-param row's engine field (e.g. CD ->
casing_depth) is looked up in the recorded firings. It stays ``None`` when the engine did not
run on this derive (no Tier-A fill -> no provenance) or when no rule produced that field
(e.g. a pure input like circuits, which the engine consumes rather than emits).
"""

from __future__ import annotations

from typing import Any

from coilforge.checklist.compare import _match

# The engine-relevant spec fields the engineer can edit (mirrors web_app._KNOWN_SPEC_FIELD_KEYS).
_SPEC_FIELDS: tuple[str, ...] = ("circuits", "rows", "feeds", "return_conn_size", "coating")


def _verdict(left: Any, right: Any) -> str:
    """Reuse the single canonical comparator (tol 0.01, string-safe)."""
    return _match(left, right)


def build_three_way_view(result: dict[str, Any]) -> dict[str, Any]:
    """Assemble the per-field three-way rows from a derive result. Pure; returns
    ``{"fields": [...], "note": ...}``. Empty ``fields`` when nothing is comparable."""
    if not isinstance(result, dict) or "error" in result:
        return {"fields": [], "note": None}

    extracted = result.get("extracted") or {}
    params = ((result.get("drawing_parameter_set") or {}).get("parameters")) or {}

    # Engineer overrides + their event-sourced machine proposal (the "before").
    param_events = {
        ev.get("key"): ev
        for ev in (result.get("manual_override_events") or [])
        if isinstance(ev, dict) and ev.get("key")
    }
    spec_overrides = {
        ov.get("field_key"): ov
        for ov in (result.get("spec_overrides") or [])
        if isinstance(ov, dict) and ov.get("field_key")
    }

    # rule_id per engine field, from the seam-A provenance (1c). Empty when the engine did
    # not run on this derive -> every rule_id stays None (honest, never fabricated).
    firing_rule = {
        f.get("field_key"): f.get("rule_id")
        for f in ((result.get("engine_provenance") or {}).get("firings") or [])
        if isinstance(f, dict) and f.get("field_key")
    }
    # Bridge a drawing-param key (CD) to its engine field (casing_depth). Lazy import avoids
    # any import-cycle with the resolver, which pulls in the engine + pipeline.
    from coilforge.services.drawing_param_resolver import PARAM_TO_ENGINE_FIELD

    fields: list[dict[str, Any]] = []

    # --- Spec fields: submittal(raw extracted) / coilforge(logic) / engineer -----------
    for key in _SPEC_FIELDS:
        ov = spec_overrides.get(key)
        submittal = extracted.get(key)
        # coilforge-logic = the machine value: the pre-edit value when overridden, else the
        # extracted value (spec fields carry no separate normalized value today).
        coilforge = ov.get("previous_value") if ov else submittal
        engineer = ov.get("new_value") if ov else None
        if submittal is None and coilforge is None and engineer is None:
            continue  # nothing to compare — never surface an all-empty row
        # spec fields are engine INPUTS (circuits/rows/feeds…), which the engine consumes
        # rather than emits, so a firing rarely exists — rule_id is None unless one matches.
        fields.append(_row(key, "spec_field", submittal, coilforge, engineer,
                           rule_id=firing_rule.get(key)))

    # --- Drawing params: no submittal-raw (engine-computed); coilforge(proposal)/engineer -
    for key, param in params.items():
        if not isinstance(param, dict):
            continue
        ev = param_events.get(key)
        overridden = param.get("mode") == "manual"
        engineer = param.get("value") if overridden else None
        # coilforge-logic = machine proposal: the event-sourced before when overridden
        # (NOT the live value, which now equals the override), else the resolved value.
        if ev is not None:
            coilforge = ev.get("previous_value")
        elif overridden:
            coilforge = None  # override with no event snapshot -> proposal unknown, don't fake it
        else:
            coilforge = param.get("value")
        if coilforge is None and engineer is None:
            continue
        # bridge the param key to its engine field (CD -> casing_depth) to find the rule.
        rule_id = firing_rule.get(PARAM_TO_ENGINE_FIELD.get(key, key))
        fields.append(_row(key, "drawing_param", None, coilforge, engineer, rule_id=rule_id))

    note = (
        "Review aid — submittal (raw) vs CoilForge (engine) vs engineer (manual). "
        "Not an approval; corrections accumulate for continuous mapping improvement."
    )
    return {"fields": fields, "note": note}


def _row(
    field: str, kind: str, submittal: Any, coilforge: Any, engineer: Any,
    *, rule_id: str | None = None,
) -> dict[str, Any]:
    return {
        "field": field,
        "kind": kind,
        "submittal": submittal,
        "coilforge": coilforge,
        "engineer": engineer,
        # verdicts drive the green/red cells; engineer verdict only when an override exists
        "submittal_vs_coilforge": _verdict(submittal, coilforge),
        "coilforge_vs_engineer": _verdict(coilforge, engineer) if engineer is not None else None,
        "rule_id": rule_id,  # engine field's firing (1c); None when the engine didn't emit it
    }
