"""Capture-ledger observability (1d): read-side tools over the append-only ledger.

Three tools, no engine or frozen-path changes:
- ``health()``          — status + row counts for /api/capture/health.
- ``draw_audit_sample`` — a flag-INDEPENDENT random draw of coils into the audit queue
                          (the only way to break stage-4 sample bias, where only flagged
                          coils are ever reviewed).
- ``replay_run()``      — re-run the engine for a stored run and compare to the ledger.

Privacy: the ledger stores hashes, never raw customer text/bytes. These tools return
counts / verdicts / rule ids — never a raw extracted value that could be customer data.
``health`` deliberately does NOT echo full ``capture_error`` diagnostic text.
"""

from __future__ import annotations

import json
import random
from typing import Any

from coilforge.capture import db

# Slot sources that the rule engine (not a submittal/as-built overlay) produced. Only these
# are replayable — the overlays (submittal_input / review_default / as_built_fallback) come
# from scanned geometry the ledger never stored, so they are reported not_replayable, never
# mismatch. See submittal/pdf_to_template_drawing.py::_slot_source.
_ENGINE_SLOT_SOURCES = frozenset({"engine_rule", "recovered_formula", "engine_or_formula"})

_COUNT_TABLES = (
    "run", "coil", "field_observation", "correction", "rule_firing", "engine_call",
    "gate_verdict", "artifact", "run_input", "audit_sample", "capture_error", "migration",
)


def health() -> dict[str, Any]:
    """Read-only ledger status. Never raises. Does not create the DB on a machine that has
    never captured (a GET must not materialize an empty ledger)."""
    base: dict[str, Any] = {
        "enabled": db.capture_enabled(),
        "raw_private_data_returned": False,
    }
    if not db.capture_db_path().exists():
        return {**base, "exists": False}
    try:
        conn = db.connect()
        try:
            base["exists"] = True
            base["user_version"] = int(conn.execute("PRAGMA user_version").fetchone()[0])
            base["capture_schema_version"] = db.CAPTURE_SCHEMA_VERSION
            counts: dict[str, int] = {}
            for table in _COUNT_TABLES:
                try:
                    counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                except Exception:  # noqa: BLE001 — a missing table must not sink health
                    counts[table] = -1
            base["counts"] = counts
            # Recent errors: ts + phase + the exception TYPE only (the leading token of the
            # stored "Type: message" string) — never the full diagnostic, which could carry
            # an engineering value.
            base["recent_errors"] = [
                {"ts_utc": ts, "phase": phase, "error_type": str(err or "").split(":", 1)[0]}
                for ts, phase, err in conn.execute(
                    "SELECT ts_utc, phase, error FROM capture_error ORDER BY ts_utc DESC LIMIT 5"
                ).fetchall()
            ]
            # Redacted like recent_errors: the leading TYPE token only, never the full
            # fallback string (which embeds the original exception message -> could carry an
            # engineering value on this unauthenticated endpoint).
            last = db.last_error()
            base["last_error_type"] = last.split(":", 1)[0] if last else None
            return base
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — health never raises into a request
        return {**base, "exists": True, "error": f"{type(exc).__name__}"}


def draw_audit_sample(n: int, *, seed: int | None = None) -> list[dict[str, Any]]:
    """Draw ``n`` coils into the audit queue for ground-truth review, INDEPENDENT of whether
    they were flagged (never joins gate_verdict) — that independence is the whole point.

    De-duplicated so re-analyze multiplicity does not bias the draw: candidates are the
    LATEST coil per (tag, project_number), so a coil processed N times counts once. Already
    -sampled coils are excluded. Sampling is done in Python (SQLite RANDOM() is unseedable),
    so ``seed`` makes the draw reproducible for tests.

    Respects the ``COILFORGE_CAPTURE`` kill switch: with capture off the ledger is quiesced,
    so an audit draw (a ledger WRITE) is a no-op — an operator who disabled capture mid-
    incident should see zero writes, audit draws included."""
    if n <= 0 or not db.capture_enabled():
        return []
    conn = db.connect()
    try:
        # Candidates = the most-recent coil per (tag, project_number) IDENTITY, excluding any
        # identity that already has a sampled coil. Excluding by coil_uid alone is a bug: the
        # same logical coil re-analyzed gets a fresh coil_uid each run, so a different coil_uid
        # of an already-sampled identity would slip back in and re-draw the same coil. NOT
        # EXISTS on (tag, project_number) with NULL-safe `IS` excludes the whole identity.
        # SQLite bare-column-with-MAX(): the bare columns come from the row holding the max.
        candidates = conn.execute(
            "SELECT c.coil_uid, c.run_id, c.tag, MAX(r.ts_utc) AS ts"
            " FROM coil c JOIN run r ON c.run_id = r.run_id"
            " WHERE NOT EXISTS ("
            "   SELECT 1 FROM audit_sample a"
            "   JOIN coil ac ON a.coil_uid = ac.coil_uid"
            "   JOIN run ar ON ac.run_id = ar.run_id"
            "   WHERE ac.tag IS c.tag AND ar.project_number IS r.project_number"
            " )"
            " GROUP BY c.tag, r.project_number"
        ).fetchall()
        if not candidates:
            return []
        picked = random.Random(seed).sample(candidates, min(n, len(candidates)))
        drawn_ts = db.utc_now()
        rows = [(drawn_ts, uid, run_id, tag) for uid, run_id, tag, _ts in picked]
        with conn:
            conn.executemany(
                "INSERT INTO audit_sample (drawn_ts_utc, coil_uid, run_id, tag)"
                " VALUES (?, ?, ?, ?)",
                rows,
            )
        return [
            {"coil_uid": uid, "run_id": run_id, "tag": tag} for uid, run_id, tag, _ts in picked
        ]
    finally:
        conn.close()


def replay_run(run_id: str) -> dict[str, Any]:
    """Time Machine: re-run the rule engine for a stored run and compare to the ledger.

    ENGINE-ONLY and honest about its limits. Only slots the engine produced
    (``field_observation.source`` in the engine set) are comparable; submittal/as-built
    overlays and any slot whose input the ledger never stored (e.g. the scanned connection
    size) are reported ``not_replayable``, NEVER ``mismatch`` — a false mismatch would read
    as real drift. Comparison uses the tolerant checklist comparator (0.01)."""
    from coilforge.checklist.compare import _match
    from coilforge.services.direct_coil_drawing_pipeline import (
        UnknownCoilInputError,
        build_drawing_slots,
    )

    conn = db.connect()
    try:
        coils = conn.execute(
            "SELECT coil_uid, coil_seq, coil_category, product_line, terra_variant,"
            " unit_size, circuits, tag FROM coil WHERE run_id = ? ORDER BY coil_seq",
            (run_id,),
        ).fetchall()
        if not coils:
            return {"run_id": run_id, "error": "unknown run_id or no coils"}

        out: list[dict[str, Any]] = []
        for uid, seq, category, product, terra_variant, unit_size, circuits, tag in coils:
            entry: dict[str, Any] = {"coil_uid": uid, "tag": tag}
            if not (category and product and unit_size):
                entry["status"] = "insufficient_inputs"
                out.append(entry)
                continue
            inputs = {
                key: json.loads(value) if value is not None else None
                for key, value in conn.execute(
                    "SELECT key, value_json FROM run_input WHERE run_id = ? AND coil_seq = ?",
                    (run_id, seq),
                ).fetchall()
            }
            try:
                new_slots, _resp = build_drawing_slots(
                    coil_type=category,
                    product_type=product,
                    unit_size=unit_size,
                    rows=inputs.get("rows"),
                    feeds=inputs.get("feeds"),
                    circuits=circuits,
                    suction_conn_size=inputs.get("suction_conn_size"),
                    terra_variant=terra_variant,
                    tag=tag,
                )
            except (UnknownCoilInputError, ValueError) as exc:
                entry["status"] = "engine_error"
                entry["detail"] = type(exc).__name__
                out.append(entry)
                continue

            stored = conn.execute(
                "SELECT field_key, value_json, source FROM field_observation"
                " WHERE run_id = ? AND coil_uid = ? AND stage = 'slot'",
                (run_id, uid),
            ).fetchall()
            comparisons = []
            for field_key, value_json, source in stored:
                if source not in _ENGINE_SLOT_SOURCES:
                    comparisons.append(
                        {"slot": field_key, "verdict": "not_replayable", "reason": source or "overlay"}
                    )
                    continue
                replayed = new_slots.get(field_key)
                if replayed is None:
                    comparisons.append(
                        {"slot": field_key, "verdict": "not_replayable", "reason": "input_not_recovered"}
                    )
                    continue
                stored_val = json.loads(value_json) if value_json is not None else None
                comparisons.append(
                    {
                        "slot": field_key,
                        "verdict": _match(replayed, stored_val),
                        "stored": stored_val,
                        "replayed": replayed,
                    }
                )
            entry["status"] = "replayed"
            entry["comparisons"] = comparisons
            entry["mismatches"] = sum(1 for c in comparisons if c["verdict"] == "mismatch")
            out.append(entry)

        return {
            "run_id": run_id,
            "coils": out,
            "note": "Engine-only replay. not_replayable = a submittal/as-built overlay or an "
            "input the ledger never stored (e.g. scanned conn size); never a mismatch.",
        }
    finally:
        conn.close()
