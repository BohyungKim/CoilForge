"""Rule Observatory (Stage 4.0): read-only, per-RULE measurement over the ledger.

Stage 3.0 answers "which FIELD does John keep overriding". This answers the question one
level up — "which RULE keeps producing a value somebody disagreed with" — which is the
only grain a YAML change can actually be made at. It became answerable when 1c' started
recording ``rule_firing`` for ordinary analyses; before that the table was empty and the
field -> rule edge did not exist.

WHAT THIS DELIBERATELY DOES NOT REPORT
    There is no ``accuracy`` field, and there never should be. The roadmap names sample
    bias as this stage's largest risk — "John은 flag된 코일만 보므로 안 보이는 곳의 틀린
    규칙은 영원히 완벽해 보인다" — and a correctness percentage is precisely the shape that
    turns "nobody has ever checked this rule" into "this rule is 100% correct". So:

    - the denominator of every rate is ``second_opinion``, never ``fired``. Dividing by
      ``fired`` silently scores every uninspected coil as agreement.
    - a rule with ``coverage == 0`` reports ``disagreement_rate: None`` and a flag. There
      is no number for it to be misread as.
    - ``blind_spots`` is returned ALONGSIDE ``rules``, ordered by how many firings nobody
      ever looked at, so "checked and wrong" and "never checked at all" are equally
      visible. The CLI prints the blind spots first for the same reason.
    - ``audit_coverage`` separates the one statistically usable second opinion (the
      flag-independent ``audit_sample`` draw) from the review-conditional ones. A rule
      whose only evidence came from coils John was already looking at is marked
      ``review_conditional``.

Contract (mirrors ``triage.py`` / ``observe.py``):
- Read-only, never raises into a caller, never materializes the DB, honors the kill switch.
- ``redact=True`` (the HTTP surface) drops coil tags, project numbers and every free-text
  reason. A per-rule aggregate needs no entity identifiers at all.

Identity grain — the same trap Stage 2 and Stage 3 were built around. A firing lands on a
``coil_uid``; the checklist observation that disagrees with it lands on a DIFFERENT run
with only a ``coil_tag`` (``compare_observation`` has no ``coil_uid`` column); a
re-analysed coil mints a fresh ``coil_uid`` every time. Everything is therefore joined at
``(coil.tag, run.project_number)``, reusing ``triage``'s joins rather than inventing new
ones. ``ccsi`` rows stay excluded: their ``coil_tag`` is NULL by design.

Vocabulary bridge — five key vocabularies meet here and none of them match:
``rule_firing.field_key`` is an ENGINE field (``suction_io``), ``compare_observation.key``
is a PANEL key (``O2``), its ``slot`` and ``divergence_adjudication.slot`` are SHEET slots
(``slot.O4``), and ``correction.field_key`` is a panel key again. The bridge is composed
from the maps that already exist — ``_SLOT_ENGINE_FIELD``, ``_PER_HEADER_ENGINE_FIELDS``
and ``param_key_for_slot`` — never hand-written here, or it forks the day one of them
changes.
"""

from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from typing import Any

from coilforge.capture import db

#: A rule needs this many independent observations before a rate means anything.
MIN_SECOND_OPINION = 5
#: ... and the corpus needs this many observed identities before ANY rate is reported.
MIN_IDENTITIES = 10

#: Checklist verdicts that count as a disagreement. ``overridden`` is excluded on purpose
#: (it records a decision John already made, not one awaiting him) and so is ``both_missing``
#: (neither side produced a value, so neither is wrong).
_DISAGREE_VERDICTS = frozenset({"mismatch", "missing_one"})

#: Panel-key stems that carry a header index. Used to fold ``O2``/``O3`` back onto ``O`` --
#: one engine field feeds every header column, so the columns are N observations of ONE
#: firing, not N firings.
_HEADER_STEMS = ("HDx", "HD", "ZD", "I", "S", "O", "R", "SL")
_TRAILING_DIGITS = re.compile(r"^(?P<stem>.*?)(?P<index>\d+)$")

_INSUFFICIENT_NOTE = (
    "Not enough independently observed coils to measure any rule yet. A firing only becomes "
    "measurable once something else saw the same dimension — the Coil Checklist's own "
    "formulas, a correction, or an audit-sample draw."
)
_MEASURED_NOTE = (
    "Per-rule disagreement, measured only where a second opinion exists. There is no "
    "accuracy figure: a rule nobody has checked is reported as uncovered, never as correct. "
    "Review aid; no rule is changed by this."
)
_FRESH_FILL_NOTE = (
    "Checklist observations are recorded on a FRESH fill only (a cache hit re-reports "
    "numbers already counted), so coverage understates how often a dimension was seen."
)


# --------------------------------------------------------------------------- #
# vocabulary bridge
# --------------------------------------------------------------------------- #
def base_panel_key(key: Any) -> str | None:
    """Panel key -> its header-independent base. ``O2`` -> ``O``, ``HDx1`` -> ``HDx``.

    Only strips a trailing index when what remains is a known multi-header stem, so ``CD``
    and ``OAL`` survive intact and a stem is never invented by regex accident.
    """
    text = str(key or "").strip()
    if not text:
        return None
    match = _TRAILING_DIGITS.match(text)
    if match:
        stem = match.group("stem")
        if stem in _HEADER_STEMS:
            return stem
    return text


@lru_cache(maxsize=1)
def _engine_field_to_panel_keys() -> dict[str, frozenset[str]]:
    """``engine field -> {base panel key}``, composed from the drawing path's own maps.

    Two sources, because the engine names this geometry differently per coil category:
    ``_SLOT_ENGINE_FIELD`` covers the single-header slots, ``_PER_HEADER_ENGINE_FIELDS``
    covers the per-header roles (``suction_io`` feeds ``O`` on DX, ``io`` feeds it on
    CWC/HWC). A field that appears in neither has no drawing dimension to be judged by --
    that is a real answer, not a lookup failure, and is reported as ``fired_not_drawn``.
    """
    from coilforge.checklist.mapping import _DIM_BASE
    from coilforge.services.direct_coil_drawing_pipeline import (
        _PER_HEADER_ENGINE_FIELDS,
        _SLOT_ENGINE_FIELD,
    )
    from coilforge.services.drawing_param_resolver import param_key_for_slot

    # The header-1 slot each per-header role writes; its panel key is the role's base.
    role_slot = {
        "i": "slot.I1", "o": "slot.O2", "hd": "slot.HD2",
        "sl": "slot.SL2", "hdx": "slot.HDx1",
    }
    # `record._compare_rows` files a checklist row under `param_key_for_slot(slot) or label`,
    # so the bridge has to reproduce BOTH halves or it silently loses whatever falls to the
    # label. `slot.DIST_EXT` is exactly that case: it has no panel key, so its rows are filed
    # as "DIST EXTENTION" — and R-033's constant 6 vs the sheet's IF(SIZE in {H05,H10},17,6)
    # is a live open divergence, i.e. precisely the row this tool exists to attribute.
    slot_label = {slot: label for label, slot in _DIM_BASE.items()}

    # One engine field reaches a drawing dimension without passing through either map
    # above: `build_drawing_slots` consumes `return_spacing` BY NAME and writes the
    # per-circuit R directly (`direct_coil_drawing_pipeline.py`:
    # `slots[f"slot.R{return_id}"] = round(return_spacing[k - 1], 4)`), because R is a
    # per-circuit list rather than one of the i/o/hd/sl/hdx roles. Leaving it out would
    # systematically under-measure the DX return-spacing rules on a dimension the sheet
    # checks constantly. Transcribed from that line, not inferred — anything else the
    # engine emits that the slot layer does not name (dist_s, supply_position, notes,
    # collared_holes, ...) genuinely has no drawing dimension and stays unbridged.
    direct_slot_fields = {"return_spacing": "slot.R2"}

    bridge: dict[str, set[str]] = {}

    def link(slot: str, field: str) -> None:
        key = base_panel_key(param_key_for_slot(slot) or slot_label.get(slot))
        if key:
            bridge.setdefault(field, set()).add(key)

    for slot, field in _SLOT_ENGINE_FIELD.items():
        link(slot, field)
    for roles in _PER_HEADER_ENGINE_FIELDS.values():
        for role, field in roles.items():
            slot = role_slot.get(role)
            if slot:
                link(slot, field)
    for field, slot in direct_slot_fields.items():
        link(slot, field)

    return {field: frozenset(keys) for field, keys in bridge.items()}


@lru_cache(maxsize=1)
def _panel_keys_with_a_rule() -> frozenset[str]:
    """Every base panel key some engine field feeds. Its complement is what makes a
    checklist disagreement UNATTRIBUTABLE — ``S`` comes from the slot layer's recovered
    formula, ``CH``/``OAL`` are sums, ``FH``/``FL``/``ROWS`` come straight off the
    submittal. Those disagreements are real CoilForge error with no rule to hang it on,
    so they are reported separately rather than dropped."""
    keys: set[str] = set()
    for panel_keys in _engine_field_to_panel_keys().values():
        keys |= set(panel_keys)
    return frozenset(keys)


# --------------------------------------------------------------------------- #
# ledger reads — every one at the (tag, project_number) identity grain
# --------------------------------------------------------------------------- #
def _firings(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """One row per captured rule firing, carrying the coil axes an adjudication needs."""
    rows = conn.execute(
        "SELECT rf.rule_id, rf.field_key, COALESCE(rf.source, 'live') AS source,"
        " rf.fidelity, rf.confidence, rf.run_id,"
        " c.tag, r.project_number, c.coil_category, c.product_line, c.terra_variant,"
        " c.unit_size"
        " FROM rule_firing rf JOIN coil c ON rf.coil_uid = c.coil_uid"
        " JOIN run r ON c.run_id = r.run_id"
        " WHERE rf.rule_id IS NOT NULL"
        " AND c.tag IS NOT NULL AND r.project_number IS NOT NULL"
    ).fetchall()
    return [
        {
            "rule_id": row[0], "field_key": row[1], "source": row[2], "fidelity": row[3],
            "confidence": row[4], "run_id": row[5],
            "identity": (row[6], row[7]), "tag": row[6],
            "coil_category": row[8], "product_family": row[9],
            "terra_variant": row[10], "unit_size": row[11],
        }
        for row in rows
    ]


def _checklist_observations(
    conn: sqlite3.Connection,
) -> tuple[dict[tuple, set[str]], set[tuple[str, Any, str]]]:
    """``{(identity, base panel key): {verdict}}`` plus the ``(run_id, tag, key)`` triples,
    which is what lets same-run joins be counted separately from identity-only ones."""
    seen: dict[tuple, set[str]] = {}
    same_run: set[tuple[str, Any, str]] = set()
    for key, verdict, tag, project, run_id in conn.execute(
        "SELECT co.key, co.verdict, co.coil_tag, r.project_number, co.run_id"
        " FROM compare_observation co JOIN run r ON co.run_id = r.run_id"
        " WHERE co.comparator = 'checklist'"
        " AND co.coil_tag IS NOT NULL AND r.project_number IS NOT NULL"
    ).fetchall():
        base = base_panel_key(key)
        if not base:
            continue
        seen.setdefault(((tag, project), base), set()).add(verdict)
        same_run.add((run_id, tag, base))
    return seen, same_run


def _corrections(conn: sqlite3.Connection) -> set[tuple]:
    """``{(identity, base panel key)}`` John actually changed."""
    out: set[tuple] = set()
    for field_key, tag, project in conn.execute(
        "SELECT cor.field_key, c.tag, r.project_number"
        " FROM correction cor JOIN coil c ON cor.coil_uid = c.coil_uid"
        " JOIN run r ON c.run_id = r.run_id"
        " WHERE c.tag IS NOT NULL AND r.project_number IS NOT NULL"
    ).fetchall():
        base = base_panel_key(field_key)
        if base:
            out.add(((tag, project), base))
    return out


def _audited_identities(conn: sqlite3.Connection) -> set[tuple]:
    """Identities drawn by the flag-INDEPENDENT audit sample and actually reviewed. The
    only second opinion that is not conditioned on John already suspecting the coil, hence
    the only one a statistical claim could rest on."""
    out: set[tuple] = set()
    for tag, project in conn.execute(
        "SELECT c.tag, r.project_number"
        " FROM audit_sample a JOIN coil c ON a.coil_uid = c.coil_uid"
        " JOIN run r ON c.run_id = r.run_id"
        " WHERE a.reviewed = 1"
        " AND c.tag IS NOT NULL AND r.project_number IS NOT NULL"
    ).fetchall():
        out.add((tag, project))
    return out


def _adjudications(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Human rulings, reduced to (axes, base panel key, verdict).

    The scope rules (``ANY_SIZE``, the split ``TERRA_H``/``TERRA_V`` variant token) are NOT
    re-implemented as SQL — matching happens in Python against ``review.divergence``'s own
    normalisation, because a second copy of a suppression rule is a second copy that drifts.
    """
    from coilforge.review.divergence import ANY_SIZE, _norm

    from coilforge.services.drawing_param_resolver import param_key_for_slot

    out: list[dict[str, Any]] = []
    for category, family, variant, scope, slot, verdict in conn.execute(
        "SELECT coil_category, product_family, terra_variant, unit_size_scope, slot, verdict"
        " FROM divergence_adjudication"
    ).fetchall():
        base = base_panel_key(param_key_for_slot(slot))
        if not base:
            continue
        out.append({
            "coil_category": _norm(category),
            "product_family": _norm(family),
            "terra_variant": _norm(variant),
            "unit_size_scope": ANY_SIZE if scope == ANY_SIZE else _norm(scope),
            "panel_key": base,
            "verdict": verdict,
        })
    return out


def _adjudication_verdicts(
    adjudications: list[dict[str, Any]], firing: dict[str, Any], panel_keys: set[str]
) -> set[str]:
    """Verdicts recorded against this coil's axes for any dimension this rule feeds."""
    from coilforge.review.divergence import ANY_SIZE, _norm

    category = _norm(firing["coil_category"])
    family = _norm(firing["product_family"])
    variant = _norm(firing["terra_variant"])
    size = _norm(firing["unit_size"])
    verdicts: set[str] = set()
    for entry in adjudications:
        if entry["panel_key"] not in panel_keys:
            continue
        if entry["coil_category"] != category or entry["product_family"] != family:
            continue
        if entry["terra_variant"] != variant:
            continue
        scope = entry["unit_size_scope"]
        if scope != ANY_SIZE and scope != size:
            continue
        verdicts.add(entry["verdict"])
    return verdicts


# --------------------------------------------------------------------------- #
# aggregation
# --------------------------------------------------------------------------- #
def _empty(**extra: Any) -> dict[str, Any]:
    return {
        "enabled": db.capture_enabled(),
        "raw_private_data_returned": False,
        "insufficient": True,
        "rules": [],
        "blind_spots": [],
        "unattributed_divergences": [],
        **extra,
    }


def _measure(conn: sqlite3.Connection, *, redact: bool) -> dict[str, Any]:
    firings = _firings(conn)
    checklist, checklist_same_run = _checklist_observations(conn)
    corrections = _corrections(conn)
    audited = _audited_identities(conn)
    adjudications = _adjudications(conn)
    bridge = _engine_field_to_panel_keys()

    # --- per (rule, identity) roll-up ------------------------------------- #
    # A rule may fire on several fields of one coil; they are ONE observation of that rule
    # on that coil, so the panel keys are unioned before anything is counted.
    per_rule: dict[str, dict[tuple, dict[str, Any]]] = {}
    provenance_mix = {"live": 0, "recomputed": 0, "drifted": 0}
    same_run_hits = 0

    for firing in firings:
        rule_id = firing["rule_id"]
        identity = firing["identity"]
        entry = per_rule.setdefault(rule_id, {}).setdefault(
            identity,
            {"panel_keys": set(), "sources": set(), "drifted": False, "firing": firing},
        )
        entry["panel_keys"] |= set(bridge.get(firing["field_key"], ()))
        entry["sources"].add(firing["source"])
        if firing["fidelity"] == "drifted":
            entry["drifted"] = True
        provenance_mix[firing["source"]] = provenance_mix.get(firing["source"], 0) + 1
        if firing["fidelity"] == "drifted":
            provenance_mix["drifted"] += 1
        for key in bridge.get(firing["field_key"], ()):
            if (firing["run_id"], firing["tag"], key) in checklist_same_run:
                same_run_hits += 1

    observed_identities: set[tuple] = set()
    rules: list[dict[str, Any]] = []

    for rule_id, by_identity in per_rule.items():
        counts = {
            "fired": 0, "fired_live": 0, "fired_recomputed": 0, "fired_drifted": 0,
            "fired_not_drawn": 0, "second_opinion": 0, "by_checklist": 0,
            "by_correction": 0, "by_audit": 0, "disagreed": 0, "corrected": 0,
        }
        adjudicated: dict[str, int] = {}

        for identity, entry in by_identity.items():
            counts["fired"] += 1
            if "live" in entry["sources"]:
                counts["fired_live"] += 1
            if "recomputed" in entry["sources"]:
                counts["fired_recomputed"] += 1
            panel_keys: set[str] = entry["panel_keys"]
            if not panel_keys:
                # Fired, but feeds no drawing dimension (notes, collared_holes, and the
                # distributor S the slot layer recomputes for itself). Counted, but never
                # admitted to a denominator -- a value the drawing never used cannot earn
                # this rule agreement credit.
                counts["fired_not_drawn"] += 1
                continue
            if entry["drifted"]:
                # The reconstruction disagreed with the drawing, so this firing is not
                # trustworthy evidence about the rule. Counted, excluded from the rates.
                counts["fired_drifted"] += 1
                continue

            verdicts: set[str] = set()
            for key in panel_keys:
                verdicts |= checklist.get((identity, key), set())
            corrected = any((identity, key) in corrections for key in panel_keys)
            audit = identity in audited

            if verdicts or corrected or audit:
                counts["second_opinion"] += 1
                observed_identities.add(identity)
                if verdicts:
                    counts["by_checklist"] += 1
                if corrected:
                    counts["by_correction"] += 1
                if audit:
                    counts["by_audit"] += 1
                if verdicts & _DISAGREE_VERDICTS:
                    counts["disagreed"] += 1
                if corrected:
                    counts["corrected"] += 1

            for verdict in _adjudication_verdicts(adjudications, entry["firing"], panel_keys):
                adjudicated[verdict] = adjudicated.get(verdict, 0) + 1

        rules.append({"rule_id": rule_id, "adjudicated": dict(sorted(adjudicated.items())), **counts})

    # --- global degrade ---------------------------------------------------- #
    if len(observed_identities) < MIN_IDENTITIES:
        return {
            "insufficient": True,
            "rules": [],
            "blind_spots": [],
            "unattributed_divergences": [],
            "observed_identities": len(observed_identities),
            "min_identities": MIN_IDENTITIES,
            "firing_rows": len(firings),
            "provenance_mix": provenance_mix,
            "note": _INSUFFICIENT_NOTE,
        }

    # --- rates, with the no-coverage cases kept unquantified ---------------- #
    for entry in rules:
        fired = entry["fired"]
        second = entry["second_opinion"]
        entry["coverage"] = round(second / fired, 4) if fired else 0.0
        entry["blind_spot"] = fired - second
        entry["audit_coverage"] = round(entry["by_audit"] / second, 4) if second else 0.0
        entry["review_conditional"] = entry["by_audit"] == 0
        if second == 0:
            entry["disagreement_rate"] = None
            entry["flag"] = "no_second_opinion"
        elif second < MIN_SECOND_OPINION:
            entry["disagreement_rate"] = None
            entry["flag"] = "signal_too_weak"
        else:
            entry["disagreement_rate"] = round(entry["disagreed"] / second, 4)
            entry["flag"] = None

    ranked = sorted(
        rules,
        key=lambda e: (
            -(e["disagreement_rate"] or 0.0), -e["disagreed"], -e["fired"], e["rule_id"]
        ),
    )
    blind = sorted(
        ({"rule_id": e["rule_id"], "fired": e["fired"], "blind_spot": e["blind_spot"],
          "coverage": e["coverage"], "flag": e["flag"]}
         for e in rules if e["blind_spot"] > 0),
        key=lambda e: (-e["blind_spot"], e["rule_id"]),
    )

    # --- disagreements no rule can be blamed for ---------------------------- #
    attributable = _panel_keys_with_a_rule()
    unattributed: dict[str, int] = {}
    for (_identity, key), verdicts in checklist.items():
        if key in attributable or not (verdicts & _DISAGREE_VERDICTS):
            continue
        unattributed[key] = unattributed.get(key, 0) + 1

    return {
        "insufficient": False,
        "observed_identities": len(observed_identities),
        "min_identities": MIN_IDENTITIES,
        "min_second_opinion": MIN_SECOND_OPINION,
        "firing_rows": len(firings),
        "provenance_mix": provenance_mix,
        "join_quality": {
            "same_run": same_run_hits,
            "identity_only": max(0, len(checklist) - same_run_hits),
        },
        "rules": ranked,
        "blind_spots": blind,
        "unattributed_divergences": [
            {"panel_key": key, "disagreed_identities": count,
             "detail": "no engine field feeds this dimension — it is computed in the slot "
                       "layer or read straight off the submittal, so the disagreement is "
                       "real but not attributable to a rule"}
            for key, count in sorted(unattributed.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "note": _MEASURED_NOTE if not redact else f"{_MEASURED_NOTE} {_FRESH_FILL_NOTE}",
        "coverage_note": _FRESH_FILL_NOTE,
    }


def measure_rule_observatory(*, redact: bool = False) -> dict[str, Any]:
    """Per-rule disagreement over the ledger, at the ``(tag, project_number)`` grain.

    Returns ``insufficient: True`` until enough coils have been independently observed.
    Never raises; honors the kill switch; never creates the DB. Reports no accuracy figure
    by construction — see the module docstring.
    """
    if not db.capture_enabled():
        return _empty(enabled=False)
    if not db.capture_db_path().exists():
        return _empty(exists=False)
    try:
        conn = db.connect()
        try:
            return {
                "enabled": True,
                "raw_private_data_returned": False,
                "exists": True,
                **_measure(conn, redact=redact),
            }
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — measurement never raises into a caller
        return _empty(exists=True, error=type(exc).__name__)
