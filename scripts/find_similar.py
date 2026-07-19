"""Case Retrieval (Stage 2): "have I seen this coil before?"

Finds the nearest past coils to a given ledger coil and prints John's own prior corrections
(before -> after -> reason) as EVIDENCE. Read-only; nothing is applied. Local tool, so it shows
the full detail the HTTP endpoint redacts (override reason, project number).

Usage:
    python scripts/find_similar.py <coil_uid>
    python scripts/find_similar.py <coil_uid> --k 8 --all-categories
    python scripts/find_similar.py <coil_uid> --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.capture.retrieve import similar_by_coil_uid  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Find similar past coils + their corrections.")
    parser.add_argument("coil_uid", help="the coil_uid to search from (see /api/capture/health)")
    parser.add_argument("--k", type=int, default=5, help="number of neighbors (default 5)")
    parser.add_argument("--all-categories", action="store_true",
                        help="do not restrict neighbors to the same coil category")
    parser.add_argument("--json", action="store_true", help="emit the raw JSON report")
    args = parser.parse_args()

    report = similar_by_coil_uid(
        args.coil_uid, k=args.k, same_category=not args.all_categories, redact=False
    )
    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    if not report.get("enabled", True):
        print("capture ledger disabled (COILFORGE_CAPTURE)")
        return 1
    if report.get("exists") is False:
        print("no capture ledger on this machine yet")
        return 1
    if report.get("error"):
        print(f"{args.coil_uid}: {report['error']}")
        return 1

    size = report.get("corpus_size", 0)
    gate = "" if report.get("corpus_ready") else f"  [insufficient corpus: {size}/50 — evidence not yet reliable]"
    query = report.get("query", {})
    print(f"query {query.get('tag') or args.coil_uid[:8]}  "
          f"({query.get('axes_present', 0)} axes)  corpus={size}{gate}")

    neighbors = report.get("neighbors", [])
    if not neighbors:
        print("  no comparable neighbors")
        return 0
    for n in neighbors:
        proj = f"  [{n['project_number']}]" if n.get("project_number") else ""
        print(f"  {n['tag']}{proj}  d={n['distance']}  ({n['shared_axes']} shared)")
        for c in n.get("corrections", []):
            reason = f"  ({c['reason']})" if c.get("reason") else ""
            print(f"      {c['field_key']} [{c['stage']}]: {c['before']} -> {c['after']}{reason}")
        if not n.get("corrections"):
            print("      (no corrections recorded for this coil)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
