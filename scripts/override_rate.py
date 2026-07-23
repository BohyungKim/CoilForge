"""Review Triage measurement (Stage 3.0): "which fields does John actually override?"

Reads the capture ledger and prints, per field, the override rate — of the coil identities
flagged for that field (blocked / mismatch / fit FAIL / low-confidence / engine-blocked), the
fraction John actually corrected. This is the number the roadmap says Stage 1 must reveal
before a triage RANKING is promised. Read-only; nothing is applied. Local tool, so it shows the
full detail the HTTP endpoint redacts (correction reasons).

Until corrections accrue it prints ``insufficient`` — the honest 0, not a fabricated weight.

Usage:
    python scripts/override_rate.py
    python scripts/override_rate.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.capture.triage import measure_override_rate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure per-field override rate from the capture ledger."
    )
    parser.add_argument("--json", action="store_true", help="emit the raw JSON report")
    args = parser.parse_args()

    report = measure_override_rate(redact=False)
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
        print(f"error: {report['error']}")
        return 1

    corr_rows = report.get("correction_rows", 0)
    identities = report.get("identities_with_corrections", 0)
    if report.get("insufficient"):
        print(f"insufficient (identities_with_corrections={identities}, "
              f"correction_rows={corr_rows}) — {report.get('note', '')}")
        return 0

    flagged = report.get("flagged_identities", 0)
    print(f"override rate over {flagged} flagged identit(y/ies)  "
          f"({identities} with corrections, {corr_rows} correction rows)")
    for f in report.get("fields", []):
        print(f"  {f['field_key']:<16} rate={f['override_rate']:<6} "
              f"({f['corrected']}/{f['flagged']} flagged)  {f.get('by_reason', {})}")
        for ex in f.get("examples", []):
            reason = f"  ({ex['reason']})" if ex.get("reason") else ""
            print(f"      {ex['before']} -> {ex['after']}{reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
