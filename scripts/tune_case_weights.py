"""Case Retrieval weight-tuning harness (Stage 2, Part A5).

Proposes per-axis Gower weights that make nearest-neighbor retrieval surface the RIGHT past
corrections, and prints a before/after neighbor sample for John's EYEBALL (the final adoption
gate). Read-only, offline — it never touches the live retrieval path. Adoption is a separate
John-gated one-line wire-in (plan A5.3).

It degrades honestly:
  * corrections < --min-corrections            -> "insufficient (N/M)" (Part A pattern)
  * no cross-coil field co-occurrence / flat   -> "signal too weak — keep uniform"
Only when a real, supported improvement exists does it print a proposed weight vector.

Usage:
    python scripts/tune_case_weights.py
    python scripts/tune_case_weights.py --k 5 --min-corrections 20 --min-shared-axes 4
    python scripts/tune_case_weights.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.capture import db, tuning  # noqa: E402
from coilforge.capture.retrieve import _assemble, _search  # noqa: E402


def _load_cases():
    if not db.capture_enabled():
        return None, "disabled"
    if not db.capture_db_path().exists():
        return None, "no_db"
    conn = db.connect()
    try:
        return _assemble(conn), None
    finally:
        conn.close()


def _coverage(cases, *, k, min_shared_axes):
    """Fraction of corrected queries that get >= 1 eligible neighbor (uniform weights)."""
    qs = [i for i, c in enumerate(cases) if tuning._query_field_keys(c)]
    if not qs:
        return 0.0
    hit = 0
    for i in qs:
        res = _search(cases, i, None, k=k, same_category=True, weights=None,
                      exclude_coil_uid=None, redact=False, min_shared_axes=min_shared_axes)
        if res.get("neighbors"):
            hit += 1
    return hit / len(qs)


def _neighbor_sample(cases, *, k, min_shared_axes, weights, limit=5):
    """For John's eyeball: per corrected query, the top-k neighbor tags + which of the query's
    corrected fields they cover."""
    out = []
    qs = [i for i, c in enumerate(cases) if tuning._query_field_keys(c)][:limit]
    for i in qs:
        qfields = tuning._query_field_keys(cases[i])
        res = _search(cases, i, None, k=k, same_category=True, weights=weights,
                      exclude_coil_uid=None, redact=False, min_shared_axes=min_shared_axes)
        nbrs = []
        for nb in res.get("neighbors") or []:
            nb_fields = {c["field_key"] for c in (nb.get("corrections") or []) if c.get("field_key")}
            nbrs.append({"tag": nb.get("tag"), "distance": nb.get("distance"),
                         "covers": sorted(qfields & nb_fields)})
        out.append({"query_tag": cases[i].get("tag"), "corrected_fields": sorted(qfields),
                    "neighbors": nbrs})
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Tune case-retrieval axis weights (offline, read-only).")
    p.add_argument("--k", type=int, default=5, help="neighbors per query (default 5)")
    p.add_argument("--min-corrections", type=int, default=20,
                   help="min corrected identities before tuning is attempted (default 20)")
    p.add_argument("--min-shared-axes", type=int, default=None,
                   help="override the shared-axes floor (default = module MIN_SHARED_AXES)")
    p.add_argument("--json", action="store_true", help="emit the raw JSON report")
    args = p.parse_args()

    cases, err = _load_cases()
    if err == "disabled":
        print("capture ledger disabled (COILFORGE_CAPTURE)")
        return 1
    if err == "no_db":
        print("no capture ledger on this machine yet")
        return 1

    navail = tuning.corrections_available(cases)

    # Degrade 1: not enough corrected coils yet (the expected state today).
    if navail < args.min_corrections:
        msg = f"insufficient ({navail}/{args.min_corrections}) - not enough corrected coils to tune yet"
        if args.json:
            print(json.dumps({"status": "insufficient", "corrections_available": navail,
                              "min_corrections": args.min_corrections}, indent=2))
        else:
            print(msg)
        return 0

    result = tuning.search_weights(cases, k=args.k, min_shared_axes=args.min_shared_axes)
    sensitivity = {
        msa: {"baseline_hit": round(tuning.hit_at_k(cases, k=args.k, min_shared_axes=msa), 4),
              "coverage": round(_coverage(cases, k=args.k, min_shared_axes=msa), 4)}
        for msa in (3, 4, 5)
    }

    if args.json:
        print(json.dumps({"status": result["flag"] or "proposed", "result": result,
                          "min_shared_axes_sensitivity": sensitivity,
                          "sample": _neighbor_sample(cases, k=args.k,
                                                     min_shared_axes=args.min_shared_axes,
                                                     weights=result.get("weights"))},
                         indent=2, default=str))
        return 0

    print(f"corrected identities: {result['n_queries']}  "
          f"shareable fields (>=2 coils): {result['shareable_fields']}")
    print(f"baseline hit@{args.k} (uniform): {result['baseline_hit']:.4f}   "
          f"achievable ceiling: {result['achievable_hit']:.4f}")
    print("min_shared_axes sensitivity (baseline hit / coverage):")
    for msa, v in sensitivity.items():
        print(f"    {msa}: hit={v['baseline_hit']:.4f}  coverage={v['coverage']:.4f}")

    # Degrade 2: the objective can't support a tuned vector — keep uniform, invent nothing.
    if result["flag"] == "signal_too_weak":
        print("\nsignal too weak - keep uniform weights (no field co-occurrence / no headroom).")
        print("Corrections don't yet predict each other across coils; re-run as more accrue.")
        return 0

    print(f"\ntuned hit@{args.k}: {result['tuned_hit']:.4f}  "
          f"(+{result['tuned_hit'] - result['baseline_hit']:.4f} over uniform)")
    print("proposed per-axis weights (non-1.0 only; coil_category is not swept):")
    for axis, w in sorted(result["weights"].items()):
        if abs(w - 1.0) > 1e-9:
            print(f"    {axis}: {w}")
    print("\nbefore/after neighbor sample for eyeball review "
          "(uniform vs proposed) - adopt ONLY if the proposed neighbors read better:")
    uni = _neighbor_sample(cases, k=args.k, min_shared_axes=args.min_shared_axes, weights=None)
    tun = _neighbor_sample(cases, k=args.k, min_shared_axes=args.min_shared_axes,
                           weights=result["weights"])
    def _fmt(nbrs):
        return ", ".join(f"{n['tag']}(d={n['distance']},covers={n['covers']})" for n in nbrs) or "-"

    for u, t in zip(uni, tun):
        print(f"  query {u['query_tag']}  corrected={u['corrected_fields']}")
        print(f"    uniform : {_fmt(u['neighbors'])}")
        print(f"    proposed: {_fmt(t['neighbors'])}")
    print("\n(review aid only - no weights were written to the live path.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
