"""Rule Observatory (Stage 4.0): "which RULE keeps producing a value somebody disagreed with?"

One level up from override_rate.py — that one names the FIELD, this one names the rule, which
is the grain a YAML change is actually made at. Read-only; nothing is applied. Local tool, so
it shows the full detail the HTTP endpoint redacts.

It prints BLIND SPOTS FIRST, on purpose. The failure this stage is most exposed to is not a
wrong number, it is an unexamined rule reading as a perfect one — John only reviews coils that
were already flagged, so a rule nobody ever checked would otherwise scroll past looking clean.
For the same reason there is no accuracy column anywhere in this output: rates divide by
`second_opinion`, never by `fired`, and a rule with no second opinion prints `-`.

Usage:
    python scripts/rule_observatory.py
    python scripts/rule_observatory.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.capture.observatory import measure_rule_observatory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure per-rule disagreement from the capture ledger."
    )
    parser.add_argument("--json", action="store_true", help="emit the raw JSON report")
    args = parser.parse_args()

    report = measure_rule_observatory(redact=False)
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

    mix = report.get("provenance_mix", {})
    print(
        f"rule firings: {report.get('firing_rows', 0)} rows "
        f"(live={mix.get('live', 0)} recomputed={mix.get('recomputed', 0)} "
        f"drifted={mix.get('drifted', 0)})"
    )
    if report.get("insufficient"):
        print(
            f"insufficient (observed_identities={report.get('observed_identities', 0)}"
            f"/{report.get('min_identities')}) — {report.get('note', '')}"
        )
        return 0

    join = report.get("join_quality", {})
    print(
        f"observed identities: {report.get('observed_identities', 0)}  "
        f"(join same_run={join.get('same_run', 0)} identity_only={join.get('identity_only', 0)})"
    )

    # Blind spots FIRST — see the module docstring.
    blind = report.get("blind_spots", [])
    print(f"\nBLIND SPOTS — fired, never independently checked ({len(blind)} rules)")
    if not blind:
        print("  (none)")
    for entry in blind[:25]:
        print(
            f"  {entry['rule_id']:<10} unchecked={entry['blind_spot']:<6} "
            f"fired={entry['fired']:<6} coverage={entry['coverage']}"
        )

    print("\nDISAGREEMENT — measured only where a second opinion exists")
    for entry in report.get("rules", []):
        rate = entry["disagreement_rate"]
        shown = "-" if rate is None else f"{rate}"
        flag = f"  [{entry['flag']}]" if entry.get("flag") else ""
        conditional = "  review-conditional" if entry.get("review_conditional") else ""
        print(
            f"  {entry['rule_id']:<10} rate={shown:<8} "
            f"({entry['disagreed']}/{entry['second_opinion']} observed of "
            f"{entry['fired']} fired)  corrected={entry['corrected']}{flag}{conditional}"
        )
        if entry.get("adjudicated"):
            print(f"      adjudicated: {entry['adjudicated']}")
        if entry.get("fired_not_drawn"):
            print(f"      fired but feeds no drawing dimension: {entry['fired_not_drawn']}")
        if entry.get("fired_drifted"):
            print(f"      excluded, provenance drifted: {entry['fired_drifted']}")

    unattributed = report.get("unattributed_divergences", [])
    if unattributed:
        print("\nUNATTRIBUTABLE — real disagreement, no rule to blame")
        for entry in unattributed:
            print(f"  {entry['panel_key']:<10} {entry['disagreed_identities']} identit(y/ies)")

    if report.get("coverage_note"):
        print(f"\nnote: {report['coverage_note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
