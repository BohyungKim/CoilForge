"""Cross-check harvested CCSI selections against the capture ledger's submittal extraction.

Reads every ``outputs/ccsi_harvest/<project>/<tag>.json`` (written by the read-only
``/ccsi-harvest`` skill), finds the same ``(project, tag)`` coil in the ledger's latest
draft-bearing run, and writes a per-category field matrix to the gitignored
``outputs/ccsi_crosscheck/``: agreement per CCSI field, and every non-match with both
raw values — the list John and Claude validate together.

    python scripts/ccsi_crosscheck.py
    python scripts/ccsi_crosscheck.py --submittal "3232=C:/.../3232 - Oxygen8 Submittal.pdf"

``--submittal`` re-reads a project's submittal PDF (read-only) and adds its canonical values
(``group.key``) next to the ledger's draft values. The ledger only records the Direct Coil draft,
so the HGRH refrigerant block and the water fluid block are comparable only this way.
"""
from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ccsi_coil_data_readiness import load_coils  # noqa: E402  # pyright: ignore[reportMissingImports]

from coilforge.capture.db import capture_db_path  # noqa: E402
from coilforge.ccsi.coil_data_map import canonical_sources  # noqa: E402
from coilforge.ccsi.crosscheck import crosscheck_coil  # noqa: E402

HARVEST_DIR = ROOT / "outputs" / "ccsi_harvest"
OUT_DIR = ROOT / "outputs" / "ccsi_crosscheck"
CATEGORIES = ("DX", "HGRH", "CWC", "HWC")


def dimension_ids() -> frozenset[str]:
    """CCSI ids owned by the drawing-dimension map (plus notes) — not coil data."""
    dim = json.loads((ROOT / "web" / "ccsi" / "ccsi_dx_field_map.json").read_text(encoding="utf-8"))
    ids = {e["selectors"][0].lstrip("#") for e in dim["fields"].values()}
    return frozenset(ids | {f"{i}_isActive" for i in ids} | {"DrawingNotes"})


def load_harvests(harvest_dir: Path = HARVEST_DIR) -> list[dict]:
    out = []
    for path in sorted(harvest_dir.glob("*/*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        record.setdefault("project", path.parent.name)
        out.append(record)
    return out


def submittal_canonical_by_tag(pdf_path: Path) -> dict[str, dict]:
    """``{tag: {"group.key": FieldValue}}`` for every coil the intake finds in one submittal."""
    from coilforge.submittal.pdf_intake import coil_tag_aliases, extract_coil_candidate_from_pdf_bytes

    result = extract_coil_candidate_from_pdf_bytes(pdf_path.read_bytes(), source_filename=pdf_path.name)
    out: dict[str, dict] = {}
    for cand in [result.candidate, *result.cover_candidates]:
        tag = cand.tag.value if cand.tag is not None else None
        if not tag:
            continue
        for alias in coil_tag_aliases(str(tag)):
            out.setdefault(alias, canonical_sources(cand))
    return out


def merge_submittal(ledger_coils: dict[str, list[dict]], project: str, by_tag: dict[str, dict]) -> int:
    """Add canonical keys to that project's ledger coils; draft keys are never overwritten."""
    merged = 0
    for coils in ledger_coils.values():
        for coil in coils:
            extra = by_tag.get(coil["tag"]) if str(coil["project"]) == project else None
            if extra:
                for key, field in extra.items():
                    coil["sources"].setdefault(key, field)
                merged += 1
    return merged


def build(harvests: list[dict], ledger_coils: dict[str, list[dict]]) -> dict[str, dict]:
    """Per category: coil results + field aggregates. ``ledger_coils`` is keyed by category."""
    ignore = dimension_ids()
    report: dict[str, dict] = {}
    for category in CATEGORIES:
        index = {(str(c["project"]), c["tag"]): c for c in ledger_coils.get(category, [])}
        coils, agg = [], collections.defaultdict(collections.Counter)
        for h in harvests:
            coil = index.get((str(h["project"]), h.get("tag")))
            if coil is None:
                continue
            rows = crosscheck_coil(h, coil["sources"], coil_type=category, ignore_ids=ignore)
            coils.append({"project": h["project"], "tag": h.get("tag"), "rows": rows})
            for r in rows:
                agg[r["ccsi_id"]][r["verdict"]] += 1
        report[category] = {"coils": coils, "fields": {k: dict(v) for k, v in agg.items()}}
    matched = {(str(c["project"]), c["tag"]) for cat in report.values() for c in cat["coils"]}
    report["_unmatched_harvests"] = {"coils": [], "fields": {}, "unmatched": [
        f"{h['project']}/{h.get('tag')}" for h in harvests if (str(h["project"]), h.get("tag")) not in matched]}
    return report


def render_markdown(category: str, data: dict) -> str:
    lines = [f"# CCSI cross-check — {category}", "", f"{len(data['coils'])} harvested coils matched to the ledger.", "",
             "| CCSI field | verdicts |", "|---|---|"]
    for ccsi_id, counts in sorted(data["fields"].items()):
        lines.append(f"| `{ccsi_id}` | " + ", ".join(f"{v} {n}" for v, n in sorted(counts.items())) + " |")
    lines += ["", "## Non-matching values", "", "| coil | CCSI field | verdict | CoilForge | CCSI | reason |", "|---|---|---|---|---|---|"]
    for coil in data["coils"]:
        for r in coil["rows"]:
            if r["verdict"] in ("match", "both_missing"):
                continue
            lines.append(f"| {coil['project']}/{coil['tag']} | `{r['ccsi_id']}` {r['label'] or ''} | {r['verdict']} | "
                         f"{r['coilforge']!r} | {r['ccsi']!r} | {r['reason']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--submittal", action="append", default=[], metavar="PROJECT=PDF",
                        help="re-read this project's submittal PDF for canonical-only values (repeatable)")
    args = parser.parse_args()
    harvests = load_harvests()
    if not harvests:
        print(f"no harvests under {HARVEST_DIR}")
        return 1
    conn = sqlite3.connect(f"file:{capture_db_path()}?mode=ro", uri=True)
    try:
        ledger = {cat: load_coils(conn, cat) for cat in CATEGORIES}
    finally:
        conn.close()
    for spec in args.submittal:
        project, _, pdf = spec.partition("=")
        n = merge_submittal(ledger, project.strip(), submittal_canonical_by_tag(Path(pdf.strip())))
        print(f"submittal {project}: canonical values merged into {n} ledger coils")
    report = build(harvests, ledger)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "crosscheck.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    for category in CATEGORIES:
        if report[category]["coils"]:
            md = render_markdown(category, report[category])
            (OUT_DIR / f"{category.lower()}.md").write_text(md, encoding="utf-8")
            print(md)
    if report["_unmatched_harvests"]["unmatched"]:
        print("harvests with no ledger coil:", ", ".join(report["_unmatched_harvests"]["unmatched"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
