"""Case-retrieval weight tuning harness (Stage 2, Part A5).

OFFLINE, READ-ONLY analysis over an already-assembled corpus (a ``cases`` list from
``retrieve._assemble``). It proposes per-axis Gower weights that make the nearest-neighbor
retrieval surface the RIGHT past corrections, and it refuses to propose anything the data
can't support. It NEVER touches the live retrieval path — adoption is a separate, John-gated
one-line wire-in (see the plan's A5.3). numpy is used only indirectly, inside ``_search``.

The objective (a leave-one-out retrieval-relevance proxy): for each ledger identity that
carries a correction, do its nearest neighbors (found with a candidate weight vector) include
coils John corrected on the SAME field? Good weights rank "coils whose past correction predicts
this coil's correction" higher. The final adoption gate is John's eyeball (this is the *first
pass* filter, not the decision) — see ``scripts/tune_case_weights.py``.

Three review-hardened invariants live here:
  * LOO via the private ``_search(cases, i, None, ...)`` kernel (it excludes the query itself);
    ``same_category=True`` mirrors the live seam, and ``coil_category`` is dropped from the sweep
    because under that pre-filter every surviving candidate matches it (cat_d=0) → it only
    dilutes the Gower denominator, never discriminates (would show a spurious hit@k delta).
  * The achievable-hit ceiling respects the SAME ``shared >= min_shared_axes`` eligibility the
    search enforces — two coils can share a corrected field yet never be eligible neighbors.
  * hit@k is per-query normalized (field-coverage fraction), so a coil corrected on many fields
    doesn't dominate one corrected on a single field.

If the objective is flat / has no ceiling headroom / lacks cross-coil field co-occurrence,
``search_weights`` returns ``weights=None`` with ``flag="signal_too_weak"`` — a tuned vector
with no statistical support would be inventing a signal (never-invent).
"""

from __future__ import annotations

from typing import Any

# Fixed finite grid, swept in ONE deterministic greedy pass (no convergence loop / solver).
_SWEEP_GRID = (0.5, 1.0, 2.0)


def _query_field_keys(case: dict[str, Any]) -> set[str]:
    """The set of field_keys John corrected on this identity (empty if none)."""
    return {
        c["field_key"]
        for c in (case.get("corrections") or [])
        if c.get("field_key")
    }


def _sweep_axes() -> tuple[str, ...]:
    """Axes ``search_weights`` sweeps: every axis EXCEPT ``coil_category`` (structurally inert
    under ``same_category=True`` — see module docstring)."""
    from coilforge.capture.retrieve import _CATEGORICAL_AXES, _NUMERIC_AXES

    return tuple(a for a in _CATEGORICAL_AXES if a != "coil_category") + tuple(_NUMERIC_AXES)


def corrections_available(cases: list[dict[str, Any]]) -> int:
    """How many identities carry at least one correction (the necessary-not-sufficient trigger)."""
    return sum(1 for c in cases if _query_field_keys(c))


def hit_at_k(cases: list[dict[str, Any]], *, weights: dict[str, float] | None = None,
             k: int = 5, min_shared_axes: int | None = None) -> float:
    """Per-query-normalized leave-one-out field-coverage hit rate.

    For each corrected query i: the fraction of its corrected field_keys that at least one of
    its top-k neighbors ALSO corrected; averaged over corrected queries. Neighbors come from the
    private ``_search`` kernel (self-excluded LOO), ``same_category=True`` to mirror the live seam.
    Returns 0.0 when there are no corrected queries.
    """
    from coilforge.capture.retrieve import _search

    queries = [i for i, c in enumerate(cases) if _query_field_keys(c)]
    if not queries:
        return 0.0
    total = 0.0
    for i in queries:
        qfields = _query_field_keys(cases[i])
        res = _search(cases, i, None, k=k, same_category=True, weights=weights,
                      exclude_coil_uid=None, redact=False, min_shared_axes=min_shared_axes)
        neighbor_fields: set[str] = set()
        for nb in res.get("neighbors") or []:
            neighbor_fields |= {
                c["field_key"] for c in (nb.get("corrections") or []) if c.get("field_key")
            }
        total += len(qfields & neighbor_fields) / len(qfields)
    return total / len(queries)


def objective_health(cases: list[dict[str, Any]], *, k: int = 5,
                     min_shared_axes: int | None = None) -> dict[str, Any]:
    """Diagnostics that decide whether the objective can be tuned at all (never-invent gate).

    - ``field_counts`` / ``shareable_fields``: how many distinct corrected identities share each
      field_key; a hit is only possible for fields shared by >= 2 coils.
    - ``achievable_hit``: the ceiling — same field-coverage metric with UNIFORM weights and
      ``k = len(cases)`` (all eligible neighbors), so it measures "does an ELIGIBLE neighbor
      sharing the field exist at all", using the SAME ``shared >= min_shared_axes`` eligibility
      the real search enforces.
    - ``baseline_hit``: hit@k under uniform weights.
    - ``headroom``: achievable - baseline (how much a weight change could possibly buy).
    """
    queries = [i for i, c in enumerate(cases) if _query_field_keys(c)]
    field_counts: dict[str, int] = {}
    for i in queries:
        for f in _query_field_keys(cases[i]):
            field_counts[f] = field_counts.get(f, 0) + 1
    shareable = sum(1 for v in field_counts.values() if v >= 2)
    baseline = hit_at_k(cases, weights=None, k=k, min_shared_axes=min_shared_axes)
    achievable = hit_at_k(cases, weights=None, k=len(cases), min_shared_axes=min_shared_axes)
    return {
        "n_queries": len(queries),
        "field_counts": field_counts,
        "shareable_fields": shareable,
        "baseline_hit": baseline,
        "achievable_hit": achievable,
        "headroom": achievable - baseline,
    }


def search_weights(cases: list[dict[str, Any]], *, k: int = 5,
                   min_shared_axes: int | None = None,
                   noise_margin: float = 0.0) -> dict[str, Any]:
    """Propose per-axis weights via a SINGLE deterministic greedy pass over ``_SWEEP_GRID``.

    Returns ``{"weights": <dict or None>, "flag": None | "signal_too_weak", "baseline_hit",
    "tuned_hit", "achievable_hit", "n_queries", "shareable_fields"}``.

    Refuses to propose (``weights=None, flag="signal_too_weak"``) when the objective can't support
    tuning — < 2 corrected queries, no cross-coil field co-occurrence, no ceiling headroom, or a
    tuned gain within ``noise_margin``. A tuned vector without that support would invent a signal.
    """
    health = objective_health(cases, k=k, min_shared_axes=min_shared_axes)
    baseline = health["baseline_hit"]
    weak = {
        "weights": None, "flag": "signal_too_weak", "baseline_hit": baseline,
        "tuned_hit": baseline, "achievable_hit": health["achievable_hit"],
        "n_queries": health["n_queries"], "shareable_fields": health["shareable_fields"],
    }
    if (health["n_queries"] < 2 or health["shareable_fields"] == 0
            or health["headroom"] <= noise_margin):
        return weak

    weights = {a: 1.0 for a in _sweep_axes()}
    for axis in _sweep_axes():  # one pass, each axis visited once (no convergence loop)
        # Incumbent = 1.0; move an axis ONLY on a STRICT improvement, so inert / signal-free axes
        # stay 1.0 (a proposed vector that down-weights masked axes would just be noise to John).
        best_w = 1.0
        best_hit = hit_at_k(cases, weights=weights, k=k, min_shared_axes=min_shared_axes)
        for w in _SWEEP_GRID:
            if w == best_w:
                continue
            weights[axis] = w
            h = hit_at_k(cases, weights=weights, k=k, min_shared_axes=min_shared_axes)
            if h > best_hit:
                best_hit, best_w = h, w
        weights[axis] = best_w
    tuned = hit_at_k(cases, weights=weights, k=k, min_shared_axes=min_shared_axes)
    if tuned - baseline <= noise_margin:
        return weak
    return {
        "weights": weights, "flag": None, "baseline_hit": baseline, "tuned_hit": tuned,
        "achievable_hit": health["achievable_hit"], "n_queries": health["n_queries"],
        "shareable_fields": health["shareable_fields"],
    }
