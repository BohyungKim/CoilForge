"""Draw a flag-INDEPENDENT random audit sample (1d): pick N coils for ground-truth review,
regardless of whether they were flagged — the only way to break the stage-4 sample bias
where only flagged coils are ever seen. De-duplicated over re-analyze multiplicity.
See capture/observe.py::draw_audit_sample.

Usage:
    python scripts/draw_audit_sample.py --n 5
    python scripts/draw_audit_sample.py --n 5 --seed 42
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.capture.observe import draw_audit_sample  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Draw a random audit sample of coils.")
    parser.add_argument("--n", type=int, default=5, help="how many coils to draw")
    parser.add_argument("--seed", type=int, default=None, help="reproducible draw")
    args = parser.parse_args()

    drawn = draw_audit_sample(args.n, seed=args.seed)
    if not drawn:
        print("no new coils to sample (all candidates already sampled, or ledger empty)")
        return 0
    print(f"drew {len(drawn)} coil(s) into the audit queue:")
    for row in drawn:
        print(f"  {row.get('tag') or '(no tag)'}  coil_uid={row['coil_uid']}  run={row['run_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
