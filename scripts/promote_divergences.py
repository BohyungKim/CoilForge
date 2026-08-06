"""Promote adjudicated divergences from the working file into the tracked registry.

    python scripts/promote_divergences.py --list
    python scripts/promote_divergences.py KD-006 KD-007
    python scripts/promote_divergences.py --all

Why this is a script and not a route: `outputs/divergence_staging.yaml` is gitignored and
the HTTP layer only ever appends there, so a ruling made in the browser cannot reach a
tracked file on its own. Promotion moves it into `src/coilforge/rules/known_divergences.yaml`
— and **John's commit is the approval step**. This script deliberately does not commit.

Idempotent: an id already present in the promoted file is reported and skipped, so a
partially-completed run can simply be re-run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import yaml  # noqa: E402

from coilforge.review.divergence import (  # noqa: E402
    _PROMOTED_PATH,
    _STAGING_PATH,
    load_registry,
)

_HEADER_LINES = 33  # keep the promoted file's explanatory preamble on rewrite


def _load(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "divergences": []}
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    doc.setdefault("version", 1)
    doc.setdefault("divergences", [])
    return doc


def _preamble(path: Path) -> str:
    """Keep the promoted file's comment header — yaml.safe_dump drops comments, and that
    header is where the "this is not a rule table" warning lives."""
    if not path.exists():
        return ""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            out.append(line)
        else:
            break
    return "\n".join(out).rstrip() + "\n\n" if out else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="*", help="divergence ids to promote (e.g. KD-006)")
    parser.add_argument("--all", action="store_true", help="promote every staged ruling")
    parser.add_argument("--list", action="store_true", help="show staged rulings and exit")
    parser.add_argument("--staging", type=Path, default=_STAGING_PATH)
    parser.add_argument("--promoted", type=Path, default=_PROMOTED_PATH)
    args = parser.parse_args(argv)

    staging_doc = _load(args.staging)
    staged = list(staging_doc["divergences"])
    if not staged:
        print(f"nothing staged in {args.staging}")
        return 0

    registry = load_registry(promoted_path=args.promoted, staging_path=args.staging)
    warnings = [w for w in registry.warnings]

    if args.list:
        print(f"{len(staged)} staged ruling(s) in {args.staging}:\n")
        for entry in staged:
            print(
                f"  {entry.get('id'):<8} {entry.get('verdict'):<18} "
                f"{entry.get('coil_category')}/{entry.get('terra_variant') or '-'}"
                f"/{entry.get('unit_size_scope')} {entry.get('slot')}"
            )
            print(f"           {str(entry.get('reason', '')).strip()[:100]}")
        for w in warnings:
            print(f"\n  ⚠ {w}")
        return 0

    if not args.ids and not args.all:
        parser.error("give ids to promote, or --all (or --list to look first)")

    wanted = {e.get("id") for e in staged} if args.all else set(args.ids)
    unknown = wanted - {e.get("id") for e in staged}
    if unknown:
        print(f"not staged: {sorted(unknown)}", file=sys.stderr)
        return 2

    promoted_doc = _load(args.promoted)
    already = {e.get("id") for e in promoted_doc["divergences"]}

    moved, skipped, remaining = [], [], []
    for entry in staged:
        if entry.get("id") not in wanted:
            remaining.append(entry)
            continue
        if entry.get("id") in already:
            skipped.append(entry.get("id"))
            remaining.append(entry)
            continue
        promoted = dict(entry)
        # `accepted` records that it now lives in the tracked file. It is NOT a claim of
        # engineering approval — that is John's commit, and the reason text still stands
        # on its own evidence.
        promoted["status"] = "accepted"
        promoted_doc["divergences"].append(promoted)
        moved.append(entry.get("id"))

    if not moved:
        print(f"nothing to move (already promoted: {sorted(skipped)})")
        return 0

    args.promoted.write_text(
        _preamble(args.promoted)
        + yaml.safe_dump(promoted_doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    staging_doc["divergences"] = remaining
    args.staging.write_text(
        yaml.safe_dump(staging_doc, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    print(f"promoted {len(moved)}: {', '.join(moved)}")
    if skipped:
        print(f"already present, left staged: {', '.join(skipped)}")
    for w in warnings:
        print(f"⚠ {w}")
    print(f"\n{args.promoted} was rewritten. Review the diff and commit it — the commit "
          "IS the approval step. Nothing was committed for you.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
