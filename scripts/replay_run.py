"""Time Machine (1d): re-run the rule engine for a stored capture run and compare to the
ledger. Engine-only and honest about its limits — see capture/observe.py::replay_run.

Usage:
    python scripts/replay_run.py <run_id>
    python scripts/replay_run.py <run_id> --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.capture.observe import replay_run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay a capture run through the engine.")
    parser.add_argument("run_id", help="the run_id to replay")
    parser.add_argument("--json", action="store_true", help="emit the raw JSON report")
    args = parser.parse_args()

    report = replay_run(args.run_id)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    if report.get("error"):
        print(f"run {args.run_id}: {report['error']}")
        return 1
    print(f"run {args.run_id} — {len(report['coils'])} coil(s)")
    for coil in report["coils"]:
        status = coil.get("status")
        head = f"  {coil.get('tag') or coil['coil_uid'][:8]}: {status}"
        if status != "replayed":
            print(head + (f" ({coil.get('detail')})" if coil.get("detail") else ""))
            continue
        comps = coil["comparisons"]
        tally: dict[str, int] = {}
        for c in comps:
            tally[c["verdict"]] = tally.get(c["verdict"], 0) + 1
        print(head + " — " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
        for c in comps:
            if c["verdict"] == "mismatch":
                print(f"      MISMATCH {c['slot']}: ledger={c['stored']} replay={c['replayed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
