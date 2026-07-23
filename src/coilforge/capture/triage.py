"""Review-triage measurement (Stage 3.0): read-only override-rate over the ledger.

Answers ONE question — "of the coils flagged for field X, what fraction did John actually
correct?" — the number the roadmap says Stage 1 must reveal before a triage RANKING can be
promised (``.claude/roadmap.md``: "실 override율은 1단계가 처음 알려줌 → 미리 약속 안 함").
It is the measurement half of Stage 3; the ranking that consumes it is deferred until this
number is meaningful. Nothing is invented: with no corrections yet the tool returns
``insufficient`` — the honest 0, not a fabricated weight.

Contract (mirrors ``observe.py`` / ``retrieve.py``):
- Read-only, never raises into a caller (a failure returns a flagged/empty result).
- Never materializes the DB on a machine that never captured (``capture_db_path().exists()``).
- Honors the ``COILFORGE_CAPTURE`` kill switch.
- Aggregate counts only — no per-customer data in the fields list; the HTTP surface
  (``redact=True``) additionally drops the free-text ``reason`` from each correction example.

Data-model note (the load-bearing fact — same one Stage 2 was built around):
    The "flag" and the "correction" live on DIFFERENT runs / different ``coil_uid``s. A coil is
    flagged into ``gate_verdict`` on a ``project_review`` run; a field John corrected lands in
    ``correction`` on a ``coil_manual_fill`` derive run; a re-analyzed coil gets a fresh
    ``coil_uid`` every run. So the rate MUST be computed at the ``(tag, project_number)``
    IDENTITY grain, reusing the ``retrieve._assemble`` join — never single-``coil_uid``.

Per-source identity resolution (MAJOR fix from plan review): the flag sources take TWO
distinct identity paths. ``gate_verdict`` / ``field_observation`` / ``rule_firing`` /
``engine_call`` all carry ``coil_uid`` -> ``coil c JOIN run r``. ``compare_observation`` has
NO ``coil_uid`` column (schema.py) -> it joins ``run`` on ``run_id`` and uses its own
``coil_tag``. ``ccsi`` compare rows are excluded: their ``coil_tag`` is NULL by design, so they
are unattributable at the identity grain (the ``run_dedup`` NULL-GROUP-BY trap).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from coilforge.capture import db
from coilforge.capture.retrieve import _correction_value

# A coil-level pseudo-field for signals that can't be attributed to one field (engine_call
# n_blocked is a per-coil count). Its "corrected" tracks whether the identity had ANY
# correction, so its rate is a coarse coil-grain signal, not a per-field one.
COIL_PSEUDO_KEY = "__coil__"

# gate_verdict.exceptions_json reason vocabulary (project_gate._classify_coil).
_GATE_REASONS = frozenset({"no_drawing", "blocked", "engine_vs_checklist"})

_EXAMPLE_LIMIT = 3

_INSUFFICIENT_NOTE = (
    "Insufficient corrections to measure an override rate yet — the ranking signal accrues "
    "as John corrects coils in the browser (Update drawing / Spec data)."
)
_MEASURED_NOTE = (
    "Measured from John's own corrections: of the identities flagged for each field, the "
    "fraction he actually overrode. Review aid; nothing auto-applied."
)


# --------------------------------------------------------------------------- #
# corrections (numerator) — identity grain, reuse the retrieve join
# --------------------------------------------------------------------------- #
def _identity_corrections(
    conn: sqlite3.Connection,
) -> tuple[dict[tuple[str, str], set[str]], dict[str, list[dict[str, Any]]], int]:
    """Per identity: the set of ``field_key``s John corrected; plus up to ``_EXAMPLE_LIMIT``
    before/after/reason examples per field; plus the total correction row count. Reuses the
    ``retrieve._assemble`` correction identity-join (``correction`` -> ``coil`` -> ``run``)."""
    by_identity: dict[tuple[str, str], set[str]] = {}
    examples: dict[str, list[dict[str, Any]]] = {}
    total_rows = 0
    for tag, project, field_key, pv_json, pv_num, nv_json, nv_num, reason in conn.execute(
        "SELECT c.tag, r.project_number, cor.field_key,"
        " cor.previous_value_json, cor.previous_value_num,"
        " cor.new_value_json, cor.new_value_num, cor.override_reason"
        " FROM correction cor JOIN coil c ON cor.coil_uid = c.coil_uid"
        " JOIN run r ON c.run_id = r.run_id"
        " WHERE c.tag IS NOT NULL AND r.project_number IS NOT NULL"
        " ORDER BY cor.correction_id"
    ).fetchall():
        total_rows += 1
        by_identity.setdefault((tag, project), set()).add(field_key)
        bucket = examples.setdefault(field_key, [])
        if len(bucket) < _EXAMPLE_LIMIT:
            bucket.append({
                "before": _correction_value(pv_json, pv_num),
                "after": _correction_value(nv_json, nv_num),
                "reason": reason,
            })
    return by_identity, examples, total_rows


# --------------------------------------------------------------------------- #
# flags (denominator) — the expanded review-signal set, two identity paths
# --------------------------------------------------------------------------- #
def _json_reasons(exceptions_json: str | None):
    """Yield ``(key, reason)`` from a ``gate_verdict.exceptions_json`` list. Guards malformed
    / NULL JSON by yielding nothing — never raises."""
    if not exceptions_json:
        return
    try:
        entries = json.loads(exceptions_json)
    except (TypeError, ValueError):
        return
    if not isinstance(entries, list):
        return
    for entry in entries:
        if isinstance(entry, dict):
            key = entry.get("key")
            reason = entry.get("reason")
            if key and reason in _GATE_REASONS:
                yield key, reason


def _identity_flags(
    conn: sqlite3.Connection,
) -> dict[tuple[str, str], dict[str, set[str]]]:
    """Per identity: ``{field_key: {reason_class, ...}}``. Unions the expanded signal set
    across its TWO identity paths (see module docstring). Set semantics collapse re-analyze
    multiplicity — a coil processed N times counts once per identity."""
    flags: dict[tuple[str, str], dict[str, set[str]]] = {}

    def add(tag: Any, project: Any, field_key: Any, reason: str) -> None:
        if tag is None or project is None or not field_key:
            return
        flags.setdefault((tag, project), {}).setdefault(field_key, set()).add(reason)

    # A. gate_verdict exceptions (coil_uid path) — no_drawing / blocked / engine_vs_checklist.
    for exc_json, tag, project in conn.execute(
        "SELECT g.exceptions_json, c.tag, r.project_number"
        " FROM gate_verdict g JOIN coil c ON g.coil_uid = c.coil_uid"
        " JOIN run r ON c.run_id = r.run_id"
        " WHERE c.tag IS NOT NULL AND r.project_number IS NOT NULL"
    ).fetchall():
        for key, reason in _json_reasons(exc_json):
            add(tag, project, key, reason)

    # B. mechanical_fit FAIL/CANNOT_EVALUATE (run + coil_tag path — NO coil_uid column).
    for key, tag, project in conn.execute(
        "SELECT co.key, co.coil_tag, r.project_number"
        " FROM compare_observation co JOIN run r ON co.run_id = r.run_id"
        " WHERE co.comparator = 'mechanical_fit'"
        " AND co.verdict IN ('FAIL', 'CANNOT_EVALUATE')"
        " AND co.coil_tag IS NOT NULL AND r.project_number IS NOT NULL"
    ).fetchall():
        add(tag, project, key, "fit")

    # C. field_observation with a blocked_reason (coil_uid path). Presence of the reason is the
    # robust signal — the exact status/mode string is not relied on.
    for field_key, tag, project in conn.execute(
        "SELECT fo.field_key, c.tag, r.project_number"
        " FROM field_observation fo JOIN coil c ON fo.coil_uid = c.coil_uid"
        " JOIN run r ON c.run_id = r.run_id"
        " WHERE fo.blocked_reason IS NOT NULL"
        " AND c.tag IS NOT NULL AND r.project_number IS NOT NULL"
    ).fetchall():
        add(tag, project, field_key, "blocked")

    # D. rule_firing LOW/MEDIUM confidence (coil_uid path). Captured only on Tier-A derive.
    for field_key, tag, project in conn.execute(
        "SELECT rf.field_key, c.tag, r.project_number"
        " FROM rule_firing rf JOIN coil c ON rf.coil_uid = c.coil_uid"
        " JOIN run r ON c.run_id = r.run_id"
        " WHERE rf.confidence IN ('LOW', 'MEDIUM')"
        " AND c.tag IS NOT NULL AND r.project_number IS NOT NULL"
    ).fetchall():
        add(tag, project, field_key, "confidence")

    # E. engine_call n_blocked > 0 (coil_uid path) -> coil-grain pseudo-field.
    for tag, project in conn.execute(
        "SELECT c.tag, r.project_number"
        " FROM engine_call ec JOIN coil c ON ec.coil_uid = c.coil_uid"
        " JOIN run r ON c.run_id = r.run_id"
        " WHERE ec.n_blocked > 0"
        " AND c.tag IS NOT NULL AND r.project_number IS NOT NULL"
    ).fetchall():
        add(tag, project, COIL_PSEUDO_KEY, "n_blocked")

    return flags


# --------------------------------------------------------------------------- #
# aggregation + public API
# --------------------------------------------------------------------------- #
def _empty(**extra: Any) -> dict[str, Any]:
    return {
        "enabled": db.capture_enabled(),
        "raw_private_data_returned": False,
        "insufficient": True,
        "fields": [],
        **extra,
    }


def _measure(conn: sqlite3.Connection, *, redact: bool) -> dict[str, Any]:
    corrected_by_identity, examples, correction_rows = _identity_corrections(conn)
    identities_with_corrections = len(corrected_by_identity)

    # Degrade on the IDENTITY count (matches health.corpus.coils_with_corrections), not the raw
    # row count — the two stay comparable as corrections accrue.
    if identities_with_corrections == 0:
        return {
            "correction_rows": correction_rows,
            "identities_with_corrections": 0,
            "insufficient": True,
            "flagged_identities": 0,
            "fields": [],
            "note": _INSUFFICIENT_NOTE,
        }

    flags = _identity_flags(conn)

    # Per field_key: how many identities flagged it, how many of those John also corrected,
    # and the per-reason-class identity counts.
    stats: dict[str, dict[str, Any]] = {}
    for identity, field_map in flags.items():
        corrected_fields = corrected_by_identity.get(identity, set())
        has_any_correction = identity in corrected_by_identity
        for field_key, reasons in field_map.items():
            st = stats.setdefault(field_key, {"flagged": 0, "corrected": 0, "by_reason": {}})
            st["flagged"] += 1
            for reason in reasons:
                st["by_reason"][reason] = st["by_reason"].get(reason, 0) + 1
            # __coil__ can't attribute a field, so it counts as corrected when the identity had
            # ANY correction; a real field must have been corrected by that same field_key.
            if field_key == COIL_PSEUDO_KEY:
                if has_any_correction:
                    st["corrected"] += 1
            elif field_key in corrected_fields:
                st["corrected"] += 1

    fields: list[dict[str, Any]] = []
    for field_key, st in stats.items():
        flagged = st["flagged"]
        corrected = st["corrected"]
        entry: dict[str, Any] = {
            "field_key": field_key,
            "flagged": flagged,
            "corrected": corrected,
            "override_rate": round(corrected / flagged, 4) if flagged else 0.0,
            "by_reason": dict(sorted(st["by_reason"].items())),
        }
        bucket = examples.get(field_key)
        if bucket:
            entry["examples"] = [
                {k: v for k, v in ex.items() if not (redact and k == "reason")}
                for ex in bucket
            ]
        fields.append(entry)

    # Highest override rate first (the ranking-relevant order), then most-flagged, then name.
    fields.sort(key=lambda f: (-f["override_rate"], -f["flagged"], f["field_key"]))

    return {
        "correction_rows": correction_rows,
        "identities_with_corrections": identities_with_corrections,
        "insufficient": False,
        "flagged_identities": len(flags),
        "fields": fields,
        "note": _MEASURED_NOTE,
    }


def measure_override_rate(*, redact: bool = False) -> dict[str, Any]:
    """Per-field override rate over the ledger, at the ``(tag, project_number)`` identity grain.

    Returns ``insufficient: True`` (with empty ``fields``) until any corrections exist. Never
    raises; honors the kill switch; never creates the DB. ``redact=True`` (the HTTP surface)
    drops the free-text ``reason`` from each correction example.
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
