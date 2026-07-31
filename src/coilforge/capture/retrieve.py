"""Case retrieval (Stage 2.0): read-only nearest-neighbor over the capture ledger.

Answers "have I seen this coil before?" — for a query coil it finds the most similar
past coils in the ledger and surfaces John's own prior ``correction`` rows (before ->
after -> reason) as EVIDENCE. It never invents a value and never auto-applies one; the
confidence gate and the never-invent invariant are untouched. This is a review aid.

Contract (mirrors ``observe.py``):
- Read-only, never raises into a caller (a failure returns an empty/flagged result).
- Never materializes the DB on a machine that never captured (``capture_db_path().exists()``).
- Honors the ``COILFORGE_CAPTURE`` kill switch.
- Returns counts / structured signals — the HTTP surface (``redact=True``) drops the free-text
  ``override_reason`` and the raw ``project_number`` (health() redacts capture_error text for the
  same reason); the local CLI keeps them.
- numpy is imported LAZILY inside the metric functions only, so the capture package still
  loads (and ``corpus_status`` / ``health`` still work) on a numpy-less machine.

Data-model note (the load-bearing fact a single-coil_uid design gets wrong):
    A logical coil re-analyzed gets a FRESH ``coil_uid`` every run (record.py), and the two
    halves of a case live on DIFFERENT runs — the numeric feature vector is written only on
    the PDF-analyze run (``run_input``), while ``correction`` rows are written only on the
    ``coil_manual_fill`` run. So a case is assembled at the ``(tag, project_number)`` IDENTITY
    grain: features come from the identity's run that carries ``run_input``; corrections are
    aggregated across ALL of the identity's coil_uids.
"""

from __future__ import annotations

import json
import sqlite3
import warnings
from typing import Any

from coilforge.capture import db

# Roadmap start-condition gate (.claude/roadmap.md): retrieval output is not meaningful
# below this many distinct coils. Below it we still compute neighbors but flag the result.
CORPUS_MIN = 50

# A single-axis coincidence must never rank as "I've seen this coil"; require at least this
# many axes present in BOTH query and candidate before a neighbor is eligible.
MIN_SHARED_AXES = 4

# Categorical axes = exact match / mismatch (Gower d in {0, 1}). unit_size and
# suction_conn_size are strings with no invented ordering (John 2026-07-17), so both are
# categorical. All but suction_conn_size come from the ``coil`` table; suction_conn_size
# lives only in ``run_input``.
_CATEGORICAL_AXES = (
    "coil_category", "product_line", "terra_variant", "unit_size", "hand",
    "header_type", "special_feature", "template_id", "suction_conn_size",
)
# Numeric axes = normalized L1 (|delta| / range). ``circuits`` is read from ``coil`` (always
# present there); the rest come from ``run_input``. suction_conn_size is NOT here — it is a
# fractional-inch string ("2-5/8"), so it is categorical above.
_NUMERIC_AXES = ("rows", "feeds", "circuits", "finned_height", "finned_length")

# run_input keys we read: the four run_input numerics + suction_conn_size (categorical).
_RUN_INPUT_NUMERIC = ("rows", "feeds", "finned_height", "finned_length")
_RUN_INPUT_KEYS = _RUN_INPUT_NUMERIC + ("suction_conn_size",)

_CAT_ABSENT = -1   # axis absent (masked out of the Gower mean)
_CAT_UNSEEN = -2   # present in the query but a value the corpus never saw -> matches nothing


# --------------------------------------------------------------------------- #
# value coercion
# --------------------------------------------------------------------------- #
def _as_float(value_json: str | None) -> float | None:
    """Numeric shadow of a run_input JSON cell; None for absent / non-numeric / bool."""
    if value_json is None:
        return None
    try:
        value = json.loads(value_json)
    except (TypeError, ValueError):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _as_str(value_json: str | None) -> str | None:
    """Categorical value of a run_input JSON cell; None for absent/null."""
    if value_json is None:
        return None
    try:
        value = json.loads(value_json)
    except (TypeError, ValueError):
        return None
    return None if value is None else str(value)


def _correction_value(value_json: str | None, value_num: float | None) -> Any:
    """Prefer the JSON value; fall back to the numeric shadow."""
    if value_json is not None:
        try:
            return json.loads(value_json)
        except (TypeError, ValueError):
            return value_json
    return value_num


# --------------------------------------------------------------------------- #
# corpus assembly (identity grain)
# --------------------------------------------------------------------------- #
def _assemble(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """One case per ``(tag, project_number)`` identity. NULL-identity rows are excluded (the
    ``run_dedup`` NULL-GROUP-BY trap); features come from the identity's representative run
    (one carrying run_input, else the latest), corrections from ALL of its coil_uids."""
    coil_rows = conn.execute(
        "SELECT c.coil_uid, c.run_id, c.tag, r.project_number, r.ts_utc,"
        " c.coil_category, c.product_line, c.terra_variant, c.unit_size, c.hand,"
        " c.header_type, c.special_feature, c.template_id, c.circuits, c.coil_seq"
        " FROM coil c JOIN run r ON c.run_id = r.run_id"
        " WHERE c.tag IS NOT NULL AND r.project_number IS NOT NULL"
    ).fetchall()
    if not coil_rows:
        return []

    # run_input, keyed by (run_id, coil_seq): numerics coerced, suction_conn_size kept as str.
    placeholders = ",".join("?" * len(_RUN_INPUT_KEYS))
    run_inputs: dict[tuple[str, int], dict[str, Any]] = {}
    for run_id, coil_seq, key, value_json in conn.execute(
        f"SELECT run_id, coil_seq, key, value_json FROM run_input WHERE key IN ({placeholders})",
        _RUN_INPUT_KEYS,
    ).fetchall():
        cell = run_inputs.setdefault((run_id, coil_seq), {})
        cell[key] = _as_str(value_json) if key == "suction_conn_size" else _as_float(value_json)

    # corrections aggregated per identity, latest-per-(field_key, stage). ORDER BY correction_id
    # ASC means a later override overwrites an earlier one in the dict.
    corrections: dict[tuple[str, str], dict[tuple[str, str], dict[str, Any]]] = {}
    for tag, project, field_key, stage, pv_json, pv_num, nv_json, nv_num, reason, _cid in conn.execute(
        "SELECT c.tag, r.project_number, cor.field_key, cor.stage,"
        " cor.previous_value_json, cor.previous_value_num,"
        " cor.new_value_json, cor.new_value_num, cor.override_reason, cor.correction_id"
        " FROM correction cor JOIN coil c ON cor.coil_uid = c.coil_uid"
        " JOIN run r ON c.run_id = r.run_id"
        " WHERE c.tag IS NOT NULL AND r.project_number IS NOT NULL"
        " ORDER BY cor.correction_id"
    ).fetchall():
        corrections.setdefault((tag, project), {})[(field_key, stage)] = {
            "field_key": field_key,
            "stage": stage,
            "before": _correction_value(pv_json, pv_num),
            "after": _correction_value(nv_json, nv_num),
            "reason": reason,
        }

    # group coil rows by identity, choose the representative run for features
    by_identity: dict[tuple[str, str], list[Any]] = {}
    for row in coil_rows:
        by_identity.setdefault((row[2], row[3]), []).append(row)

    cases: list[dict[str, Any]] = []
    for (tag, project), rows in by_identity.items():
        # representative: prefer a run that carries run_input (the analyze run — the only run
        # with the numeric axes), tie-break on latest ts_utc.
        rep = max(rows, key=lambda r: ((r[1], r[14]) in run_inputs, r[4] or ""))
        cell = run_inputs.get((rep[1], rep[14]), {})
        features = {
            "coil_category": rep[5],
            "product_line": rep[6],
            "terra_variant": rep[7],
            "unit_size": rep[8],
            "hand": rep[9],
            "header_type": rep[10],
            "special_feature": rep[11],
            "template_id": rep[12],
            "suction_conn_size": cell.get("suction_conn_size"),
            "circuits": float(rep[13]) if rep[13] is not None else None,
            "rows": cell.get("rows"),
            "feeds": cell.get("feeds"),
            "finned_height": cell.get("finned_height"),
            "finned_length": cell.get("finned_length"),
        }
        cases.append({
            "coil_uid": rep[0],
            "tag": tag,
            "project_number": project,
            "features": features,
            "corrections": list(corrections.get((tag, project), {}).values()),
        })
    return cases


# --------------------------------------------------------------------------- #
# encoding + distance (numpy — lazy-imported by callers)
# --------------------------------------------------------------------------- #
def _encode(cases: list[dict[str, Any]], np):
    """Corpus matrices: CAT int codes (absent = _CAT_ABSENT), NUM floats (absent = nan),
    per-axis numeric ranges, and the categorical codebooks (for encoding an external query)."""
    n = len(cases)
    cat = np.full((n, len(_CATEGORICAL_AXES)), _CAT_ABSENT, dtype=np.int64)
    num = np.full((n, len(_NUMERIC_AXES)), np.nan, dtype=np.float64)
    codebooks: list[dict[Any, int]] = [{} for _ in _CATEGORICAL_AXES]
    for i, case in enumerate(cases):
        feats = case["features"]
        for j, axis in enumerate(_CATEGORICAL_AXES):
            value = feats.get(axis)
            if value is not None and value != "":
                cat[i, j] = codebooks[j].setdefault(value, len(codebooks[j]))
        for j, axis in enumerate(_NUMERIC_AXES):
            value = feats.get(axis)
            if value is not None:
                try:
                    num[i, j] = float(value)
                except (TypeError, ValueError):
                    pass
    # An all-absent numeric column makes nanmax warn "All-NaN slice"; the range is 0 there
    # anyway (nan_to_num), so the warning is noise — silence it locally.
    if n:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            ranges = np.nan_to_num(np.nanmax(num, axis=0) - np.nanmin(num, axis=0),
                                   nan=0.0, posinf=0.0, neginf=0.0)
    else:
        ranges = np.zeros(len(_NUMERIC_AXES))
    return cat, num, ranges, codebooks


def _encode_query(features: dict[str, Any], codebooks, np):
    """Encode an external query against the corpus codebooks. A categorical value the corpus
    never saw -> _CAT_UNSEEN (present, but distance 1 to every candidate)."""
    qcat = np.full(len(_CATEGORICAL_AXES), _CAT_ABSENT, dtype=np.int64)
    qnum = np.full(len(_NUMERIC_AXES), np.nan, dtype=np.float64)
    for j, axis in enumerate(_CATEGORICAL_AXES):
        value = features.get(axis)
        if value is not None and value != "":
            qcat[j] = codebooks[j].get(value, _CAT_UNSEEN)
    for j, axis in enumerate(_NUMERIC_AXES):
        value = features.get(axis)
        if value is not None:
            try:
                qnum[j] = float(value)
            except (TypeError, ValueError):
                pass
    return qcat, qnum


def _distances(cat, num, qcat, qnum, ranges, wc, wn, np):
    """Masked Gower. Absent axes (either side) drop out of numerator AND denominator; a
    candidate sharing no axis with the query gets inf (never a neighbor)."""
    cat_present = (cat != _CAT_ABSENT) & (qcat != _CAT_ABSENT)
    cat_d = (cat != qcat).astype(np.float64)
    num_present = (~np.isnan(num)) & (~np.isnan(qnum))
    safe_range = np.where(ranges == 0, 1.0, ranges)
    num_d = np.clip(np.nan_to_num(np.abs(num - qnum) / safe_range), 0.0, 1.0)
    numer = (wc * cat_present * cat_d).sum(1) + (wn * num_present * num_d).sum(1)
    denom = (wc * cat_present).sum(1) + (wn * num_present).sum(1)
    shared = cat_present.sum(1) + num_present.sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        dist = np.where(denom > 0, numer / denom, np.inf)
    return dist, shared


def _weight_vectors(weights: dict[str, float] | None, np):
    wc = np.ones(len(_CATEGORICAL_AXES), dtype=np.float64)
    wn = np.ones(len(_NUMERIC_AXES), dtype=np.float64)
    if weights:
        for j, axis in enumerate(_CATEGORICAL_AXES):
            if axis in weights:
                wc[j] = float(weights[axis])
        for j, axis in enumerate(_NUMERIC_AXES):
            if axis in weights:
                wn[j] = float(weights[axis])
    return wc, wn


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def _empty(**extra: Any) -> dict[str, Any]:
    return {"enabled": db.capture_enabled(), "raw_private_data_returned": False,
            "neighbors": [], **extra}


def _neighbor(case: dict[str, Any], distance: float, shared: int, *, redact: bool) -> dict[str, Any]:
    feats = case.get("features") or {}
    out: dict[str, Any] = {
        "coil_uid": case["coil_uid"],
        "tag": case["tag"],
        "distance": round(float(distance), 4),
        "shared_axes": int(shared),
        # Compact axis summary for the UI "which past coil" chips. All engineering attributes
        # (no customer identity), so shown under redaction too.
        "features": {k: feats.get(k) for k in
                     ("coil_category", "product_line", "unit_size", "hand", "header_type")},
        "corrections": [
            {k: v for k, v in c.items() if not (redact and k == "reason")}
            for c in case["corrections"]
        ],
    }
    if not redact:
        out["project_number"] = case["project_number"]
    return out


def _search(cases, query_idx, query_features, *, k, same_category, weights,
            exclude_coil_uid, redact, min_shared_axes=None) -> dict[str, Any]:
    """Shared kernel. Exactly one of query_idx / query_features is used.

    ``min_shared_axes`` overrides the module-constant floor for a single call (the offline
    tuning harness sweeps it); None means use ``MIN_SHARED_AXES`` (the live default)."""
    try:
        import numpy as np
    except ImportError:
        return _empty(status="numpy_unavailable")

    corpus_size = len(cases)
    # optional hard pre-filter: a DX query never surfaces an HWC neighbor.
    query_category = (
        cases[query_idx]["features"]["coil_category"] if query_idx is not None
        else (query_features or {}).get("coil_category")
    )
    kept = list(range(corpus_size))
    if same_category and query_category is not None:
        kept = [i for i in kept if cases[i]["features"]["coil_category"] == query_category]
    # never return the query itself, nor an explicitly excluded coil.
    kept = [
        i for i in kept
        if i != query_idx and cases[i]["coil_uid"] != exclude_coil_uid
    ]

    base = {
        "enabled": True,
        # We never return raw customer bytes / extracted document text (db.py posture); the
        # HTTP surface additionally redacts free-text reason + project_number (redact=True).
        "raw_private_data_returned": False,
        "corpus_size": corpus_size,
        "corpus_min": CORPUS_MIN,
        "corpus_ready": corpus_size >= CORPUS_MIN,
        "insufficient_corpus": corpus_size < CORPUS_MIN,
    }
    if not kept:
        return {**base, "neighbors": [], "note": "no comparable coils in the corpus yet."}

    cat, num, ranges, codebooks = _encode(cases, np)
    if query_idx is not None:
        qcat, qnum = cat[query_idx], num[query_idx]
        query_desc = {"coil_uid": cases[query_idx]["coil_uid"],
                      "tag": cases[query_idx]["tag"]}
    else:
        qcat, qnum = _encode_query(query_features or {}, codebooks, np)
        query_desc = {"features": query_features or {}}
    wc, wn = _weight_vectors(weights, np)

    idx = np.array(kept, dtype=np.int64)
    dist, shared = _distances(cat[idx], num[idx], qcat, qnum, ranges, wc, wn, np)
    floor = MIN_SHARED_AXES if min_shared_axes is None else min_shared_axes
    eligible = (shared >= floor) & np.isfinite(dist)
    order = np.argsort(dist)
    neighbors = []
    for pos in order:
        if not eligible[pos]:
            continue
        if len(neighbors) >= k:  # checked before append so k<=0 yields zero neighbors
            break
        neighbors.append(_neighbor(cases[idx[pos]], dist[pos], shared[pos], redact=redact))

    query_desc["axes_present"] = int(
        (qcat != _CAT_ABSENT).sum() + int((~np.isnan(qnum)).sum())
    )
    return {**base, "query": query_desc, "neighbors": neighbors,
            "note": "Evidence only — John's own prior corrections on similar coils; nothing "
            "auto-applied."}


def similar_by_coil_uid(coil_uid: str, *, k: int = 5, same_category: bool = True,
                        weights: dict[str, float] | None = None,
                        redact: bool = False,
                        min_shared_axes: int | None = None) -> dict[str, Any]:
    """Neighbors of a coil already in the ledger (by its representative coil_uid)."""
    if not db.capture_enabled():
        return _empty(enabled=False)
    if not db.capture_db_path().exists():
        return _empty(exists=False)
    try:
        conn = db.connect()
        try:
            cases = _assemble(conn)
        finally:
            conn.close()
        query_idx = next((i for i, c in enumerate(cases) if c["coil_uid"] == coil_uid), None)
        if query_idx is None:
            return _empty(exists=True, error="unknown_coil_uid", corpus_size=len(cases))
        return _search(cases, query_idx, None, k=k, same_category=same_category,
                       weights=weights, exclude_coil_uid=None, redact=redact,
                       min_shared_axes=min_shared_axes)
    except Exception as exc:  # noqa: BLE001 — retrieval never raises into a caller
        return _empty(error=type(exc).__name__)


def features_from_result(result: dict[str, Any]) -> dict[str, Any]:
    """Extract the case-retrieval axes from a derive/analyze RESULT dict (a what-if query).

    Mirrors ``capture.record._coil_row`` source-expression for source-expression so a query
    lands in the SAME categorical codebook the ledger WRITE path stored — otherwise a coil
    would read as "unseen" against its own past. ``record.py`` stays untouched: its ``_coil_row``
    returns a SQL tuple (not a dict) and also pulls gate flags, so duplicating the ~14 mappings
    here is the drift-proof cost of not reaching into that path. KEEP IN SYNC with ``_coil_row``.

    Numeric-source equivalence (MINOR-1): corpus numerics come from the analyze run's
    ``run_input`` (``record._input_rows`` / ``fit_inputs``); the query numerics come from
    ``result["extracted"]``. Both echo the same physical values — extracted ``rows/feeds/
    finned_height/finned_length`` are ``extract.get(..) or ctx.get(..)``
    (``pdf_to_template_drawing.py:458-461``), the same ``ctx`` the engine input vector is built
    from — so a coil compares equal to itself across the analyze/derive boundary.
    """
    from coilforge.submittal.coilmaster_drawing_extract import resolve_product_line

    td = result or {}
    extracted = td.get("extracted") or {}
    # product_line = the picker label ("TERRA H"/"NOVA"/...), NOT the cover-row family (record.py).
    product_line = td.get("product_type") or None
    _family, terra_variant = resolve_product_line(product_line)
    return {
        # --- categorical (mirror record._coil_row) ---
        "coil_category": extracted.get("coil_category"),
        "product_line": product_line,
        "terra_variant": terra_variant,
        "unit_size": td.get("unit_size"),
        "hand": extracted.get("hand"),
        "header_type": extracted.get("header_type"),
        "special_feature": extracted.get("special_feature"),
        "template_id": td.get("template_id"),
        # the suction_conn_size axis is the derive-time "return_conn_size" (see _RUN_INPUT_KEYS)
        "suction_conn_size": extracted.get("return_conn_size"),
        # --- numeric (extracted echoes; circuits included so all 5 _NUMERIC_AXES are sourced) ---
        "circuits": extracted.get("circuits"),
        "rows": extracted.get("rows"),
        "feeds": extracted.get("feeds"),
        "finned_height": extracted.get("finned_height"),
        "finned_length": extracted.get("finned_length"),
    }


def similar_by_features(features: dict[str, Any], *, k: int = 5, same_category: bool = True,
                        weights: dict[str, float] | None = None,
                        exclude_coil_uid: str | None = None,
                        redact: bool = False,
                        min_shared_axes: int | None = None) -> dict[str, Any]:
    """Neighbors of an arbitrary feature dict (a live/what-if coil not yet in the ledger)."""
    if not db.capture_enabled():
        return _empty(enabled=False)
    if not db.capture_db_path().exists():
        return _empty(exists=False)
    try:
        conn = db.connect()
        try:
            cases = _assemble(conn)
        finally:
            conn.close()
        query = features if isinstance(features, dict) else {}
        return _search(cases, None, query, k=k, same_category=same_category,
                       weights=weights, exclude_coil_uid=exclude_coil_uid, redact=redact,
                       min_shared_axes=min_shared_axes)
    except Exception as exc:  # noqa: BLE001 — retrieval never raises into a caller
        return _empty(error=type(exc).__name__)


# --------------------------------------------------------------------------- #
# corpus-readiness meter (no numpy; safe for the health path)
# --------------------------------------------------------------------------- #
def _corpus_counts(conn: sqlite3.Connection) -> dict[str, Any]:
    """Distinct-identity corpus size + how many identities carry a correction. Runs on an
    ALREADY-OPEN connection so health() can embed it without a second connect(). NULL-identity
    rows are excluded (COUNT(*) FROM coil would over-count re-analyze multiplicity)."""
    distinct = int(conn.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM coil c JOIN run r ON c.run_id = r.run_id"
        " WHERE c.tag IS NOT NULL AND r.project_number IS NOT NULL"
        " GROUP BY c.tag, r.project_number)"
    ).fetchone()[0])
    with_corr = int(conn.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM correction cor"
        " JOIN coil c ON cor.coil_uid = c.coil_uid JOIN run r ON c.run_id = r.run_id"
        " WHERE c.tag IS NOT NULL AND r.project_number IS NOT NULL"
        " GROUP BY c.tag, r.project_number)"
    ).fetchone()[0])
    return {
        "distinct_coils": distinct,
        "coils_with_corrections": with_corr,
        "threshold": CORPUS_MIN,
        "ready": distinct >= CORPUS_MIN,
        "remaining": max(0, CORPUS_MIN - distinct),
        "pct": round(min(1.0, distinct / CORPUS_MIN), 4) if CORPUS_MIN else 1.0,
    }


def corpus_status() -> dict[str, Any]:
    """Standalone readiness meter. Guards like observe.health(): never creates the DB."""
    if not db.capture_db_path().exists():
        return {"exists": False, "distinct_coils": 0, "threshold": CORPUS_MIN,
                "ready": False, "remaining": CORPUS_MIN}
    try:
        conn = db.connect()
        try:
            return {"exists": True, **_corpus_counts(conn)}
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return {"exists": True, "error": type(exc).__name__}
