"""Replay the capture ledger through the CCSI coil-data mapping contract.

For every coil of a category in the latest draft-bearing run of each project, resolve
the CCSI coil-data fields (``coilforge.ccsi.coil_data_map``) from the draft values the
ledger already recorded, and tally the reason codes per CCSI field. The output is the
submittal-side half of mapping validation: which fields CoilForge can fill, and which
source values fall off the CCSI vocabulary (the list of decisions for John).

Read-only: the ledger is opened ``mode=ro``. The report names projects, so it is
written under the gitignored ``outputs/ccsi_coil_data/``.

    python scripts/ccsi_coil_data_readiness.py            # DX
    python scripts/ccsi_coil_data_readiness.py --category HGRH
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

from coilforge.capture.db import capture_db_path  # noqa: E402
from coilforge.ccsi.coil_data_map import TUBE_SURFACE_SOURCE, load_coil_data_map, resolve_coil_data  # noqa: E402

OUT_DIR = ROOT / "outputs" / "ccsi_coil_data"

_LATEST_DRAFT_RUNS = """
select r.run_id, coalesce(r.project_number, r.project_name, r.source_filename) as project, r.input_hash
from run r
where r.ok = 1
  and exists (select 1 from field_observation f where f.run_id = r.run_id and f.stage = 'draft')
  and r.ts_utc = (
      select max(r2.ts_utc) from run r2
      where coalesce(r2.project_name, '') = coalesce(r.project_name, '') and r2.ok = 1
        and exists (select 1 from field_observation f where f.run_id = r2.run_id and f.stage = 'draft'))
"""


def load_coils(conn: sqlite3.Connection, category: str) -> list[dict]:
    coils = []
    for run_id, project, input_hash in conn.execute(_LATEST_DRAFT_RUNS).fetchall():
        rows = conn.execute(
            """select c.coil_uid, c.tag, c.circuits, f.stage, f.field_key, f.value_json, f.unit, f.status,
                      f.blocked_reason
               from field_observation f join coil c on c.coil_uid = f.coil_uid
               where f.run_id = ? and c.coil_category = ?
                 and (f.stage = 'draft' or (f.stage = 'slot' and f.field_key = 'slot.TUBE_MATERIAL_2'))""",
            (run_id, category),
        ).fetchall()
        per: dict[str, dict] = {}
        tube_surface: dict[str, object] = {}
        for uid, tag, circuits, stage, key, value_json, unit, status, blocked in rows:
            value = json.loads(value_json) if value_json is not None else None
            if stage == "slot":  # the drawing slot is the ledger's only record of the stated tube surface
                tube_surface[uid] = value
                continue
            # input_hash = sha1 of the PDF this draft was read from (pairs canonical values with it)
            coil = per.setdefault(uid, {"project": project, "tag": tag, "input_hash": input_hash,
                                        "sources": {"tag": tag}})
            if circuits is not None:  # the run's extracted circuit count (coil table), not a draft field
                coil["sources"].setdefault("geometry.circuits", {"value": circuits, "status": "review_required"})
            # ``unit`` carries the material of tube/fin ("0.016" + "Copper") — D1
            coil["sources"][key] = {"value": value, "unit": unit, "status": status, "blocked_reason": blocked}
        for uid, coil in per.items():
            if tube_surface.get(uid) not in (None, ""):
                coil["sources"].setdefault(TUBE_SURFACE_SOURCE, {"value": tube_surface[uid], "status": "review_required"})
        coils.extend(per.values())
    return coils


def build_report(coils: list[dict], coil_type: str) -> dict:
    fields = load_coil_data_map(coil_type).fields
    codes: dict[str, collections.Counter] = {k: collections.Counter() for k in fields}
    unmapped: dict[str, collections.Counter] = {k: collections.Counter() for k in fields}
    for coil in coils:
        for e in resolve_coil_data(coil["sources"], coil_type=coil_type):
            codes[e.ccsi_id][e.reason_code] += 1
            if e.reason_code in ("CCSI_OPTION_UNMAPPED", "CCSI_VALUE_UNPARSEABLE"):
                unmapped[e.ccsi_id][repr(e.source_value)] += 1
    return {
        "coil_type": coil_type,
        "coils": len(coils),
        "projects": len({c["project"] for c in coils}),
        "fields": {
            k: {
                "role": fields[k].role,
                "section": fields[k].section,
                "reason_counts": dict(codes[k]),
                "off_vocabulary": dict(unmapped[k].most_common()),
            }
            for k in fields
        },
    }


def render_markdown(report: dict) -> str:
    n = report["coils"]
    lines = [
        f"# CCSI coil-data readiness — {report['coil_type']}",
        "",
        f"{n} coils across {report['projects']} projects (latest draft-bearing run per project).",
        "`resolved` = CoilForge produced a value on the CCSI vocabulary (pushable once validated).",
        "",
        "| CCSI field | role | resolved | missing/blocked | off-vocabulary | no source | off-vocabulary values |",
        "|---|---|---|---|---|---|---|",
    ]
    for ccsi_id, f in report["fields"].items():
        c = f["reason_counts"]
        resolved = c.get("CCSI_NOT_VALIDATED", 0) + c.get("CCSI_OK", 0) + c.get("CCSI_READ_BACK_ONLY", 0)
        missing = c.get("CCSI_SOURCE_MISSING", 0) + c.get("CCSI_SOURCE_BLOCKED", 0)
        off = c.get("CCSI_OPTION_UNMAPPED", 0) + c.get("CCSI_VALUE_UNPARSEABLE", 0)
        values = ", ".join(f"{v}×{k}" for v, k in list(f["off_vocabulary"].items())[:6])
        lines.append(
            f"| `{ccsi_id}` | {f['role']} | {resolved}/{n} | {missing} | {off} | {c.get('CCSI_NO_SOURCE', 0)} | {values} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--category", default="DX", help="coil category in the ledger (DX, HGRH, CWC, HWC)")
    parser.add_argument("--coil-type", default=None, help="coil-data map to use (default: same as category)")
    args = parser.parse_args()
    coil_type = args.coil_type or args.category

    db = capture_db_path()
    if not db.exists():
        print(f"ledger not found: {db}")
        return 1
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        report = build_report(load_coils(conn, args.category), coil_type)
    finally:
        conn.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"readiness_{args.category.lower()}"
    (OUT_DIR / f"{stem}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = render_markdown(report)
    (OUT_DIR / f"{stem}.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
