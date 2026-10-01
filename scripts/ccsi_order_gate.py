"""The past-order gate for the CCSI coil-data mappings: John's decision tables.

Reads the report cross-check that ``scripts/ccsi_report_crosscheck.py`` wrote (the CCSI selection
report filed with each order vs CoilForge's current extraction) and the live CCSI form harvests,
then writes what John rules on (``coilforge.ccsi.order_gate``): evidence tiers, the report
adapter's calibration against the harvests, demotion / promotion candidates, and the D1 / D2 / D6
/ D7 / D4 tables. Proposals only — no map is edited.

    python scripts/ccsi_order_gate.py                  # after ccsi_report_crosscheck.py
    python scripts/ccsi_order_gate.py --no-calibration # skip re-reading the harvested projects' reports

Calibration re-reads the reports of the harvested projects through the cross-check's own
cloud-guarded ``scan_reports`` (local files only; a cloud-only report leaves that coil unpaired).
Outputs name customer projects, so they go to the gitignored ``outputs/ccsi_order_gate/``.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.ccsi import order_gate as og  # noqa: E402
from coilforge.submittal.pdf_intake import coil_tag_aliases  # noqa: E402

CROSSCHECK = ROOT / "outputs" / "ccsi_report_crosscheck" / "crosscheck.json"
HARVEST_DIR = ROOT / "outputs" / "ccsi_harvest"
OUT_DIR = ROOT / "outputs" / "ccsi_order_gate"
RUNNER = ROOT / "scripts" / "ccsi_report_crosscheck.py"
# A cross-check older than any of these was computed by different mapping / comparison code.
STALENESS_SOURCES = (
    RUNNER, ROOT / "src/coilforge/ccsi/selection_report.py", ROOT / "src/coilforge/ccsi/crosscheck.py",
    ROOT / "src/coilforge/ccsi/coil_data_map.py", *sorted((ROOT / "web/ccsi").glob("ccsi_coil_data_map.*.json")),
)
_TYPE_BY_COMPONENT = {"DXCoil": "DX", "CondenserCoil": "HGRH", "ColdWaterCoil": "CWC", "HotWaterCoil": "HWC"}
_PROPOSAL_ORDER = ("demote_candidate", "held_adapter", "promote_candidate", "needs_decision", "blocked_by_defects",
                   "untestable_from_report", "supported", "insufficient", "no_source", "read_back_only")


def load_runner() -> Any:
    """The report cross-check script as a module (its read-only ``scan_reports`` / ``aggregate``)."""
    spec = importlib.util.spec_from_file_location("ccsi_report_crosscheck", RUNNER)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def load_harvests(root: Path = HARVEST_DIR) -> list[dict[str, Any]]:
    out = []
    for path in sorted(root.glob("*/*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        record.setdefault("project", path.parent.name)
        out.append(record)
    return out


def stale_sources(crosscheck: Path) -> list[str]:
    made = crosscheck.stat().st_mtime
    return [p.relative_to(ROOT).as_posix() for p in STALENESS_SOURCES if p.exists() and p.stat().st_mtime > made]


def _aliases(tag: str | None) -> set[str]:
    return {a.upper() for a in coil_tag_aliases(tag)} if tag else set()


def project_dir(po_root: Path, number: str) -> Path | str:
    hits = [Path(e.path) for e in os.scandir(po_root) if e.is_dir() and re.match(rf"^{re.escape(number)}(?!\d)", e.name)]
    return hits[0] if len(hits) == 1 else ("no_project_folder" if not hits else "ambiguous_project_folder")


def calibration_pairs(harvests: list[dict[str, Any]], runner: Any, po_root: Path) -> list[dict[str, Any]]:
    pairs, scans = [], {}
    for h in harvests:
        project, tag = str(h["project"]), str(h.get("tag") or "")
        pair = {"project": project, "tag": tag, "coil_type": _TYPE_BY_COMPONENT.get(str(h.get("component_type") or "")),
                "report_fields": None, "harvest_fields": h.get("fields") or {}}
        if project not in scans:
            folder = project_dir(po_root, project)
            scans[project] = folder if isinstance(folder, str) else runner.scan_reports(folder)
        scan = scans[project]
        if isinstance(scan, str) or scan.get("skip"):
            pair["missing_reason"] = scan if isinstance(scan, str) else f"report:{scan['skip']}"
        else:
            hits = [r for r in scan["truth"] if _aliases(r.get("base_tag")) & _aliases(tag)]
            if len(hits) == 1:
                pair["report_fields"] = hits[0]["fields"]
                pair["truth_file"] = scan["truth_file"]
            else:
                pair["missing_reason"] = "no_report_coil" if not hits else "ambiguous_report_coil"
        pairs.append(pair)
    return pairs


# ------------------------------------------------------------------ rendering
# The rating inputs John rules on first (2026-09-30): HGRH refrigerant, water fluid, GPM, airflow basis.
FOCUS_FIELDS = (
    "HGRH:VaporTemperature", "HGRH:CondensingTemperature", "HGRH:Subcooling",
    "CWC:FluidType", "CWC:GlycolRatio", "CWC:EnteringFluidTemp", "CWC:LeavingFluidTemp", "CWC:FluidFlowRate",
    "HWC:FluidType", "HWC:GlycolRatio", "HWC:EnteringFluidTemp", "HWC:LeavingFluidTemp", "HWC:FluidFlowRate",
    "DX:ACFM", "HGRH:ACFM", "CWC:ACFM", "HWC:ACFM",
)


def _cell(value: Any) -> str:
    return "" if value is None else str(value).replace("|", "/")


def _focus_section(gate: dict[str, Any]) -> list[str]:
    """One table for the fields that decide whether CCSI rates like the order."""
    rules = gate["decision_tables"].get("rule_candidates", {})
    lines = ["", "## Decide first — rating inputs (order tier)", "",
             "| field | status | proposal | order verdicts | report values when the submittal is silent | defect examples |",
             "|---|---|---|---|---|---|"]
    for key in FOCUS_FIELDS:
        coil_type, ccsi_id = key.split(":")
        p = gate["proposals"].get(key)
        rule = (rules.get(coil_type) or {}).get(ccsi_id)
        if p is None and rule is None:
            continue
        verdicts = ", ".join(f"{k} {n}" for k, n in sorted(((p or {}).get("by_tier") or {}).get("order", {}).items()))
        silent = ", ".join(f"{v} ×{n}" for v, n in sorted((rule or {}).get("report_values", {}).items(),
                                                          key=lambda kv: -kv[1]))
        examples = "; ".join(f"{d['project']} {d['tag']}: {d['coilforge']}→{d['ccsi']}" for d in (p or {}).get("defects", [])[:4])
        lines.append(f"| {coil_type} `{ccsi_id}` | {(p or {}).get('mapping_status', '')} | {(p or {}).get('proposal', '')} | "
                     f"{verdicts} | {silent} | {_cell(examples)} |")
    fluid = gate["decision_tables"].get("fluid") or {}
    if fluid:
        lines += ["", "Water fluid pattern per ordered coil (which inputs the order kept from the submittal):"]
        for coil_type, patterns in fluid.items():
            for pattern, n in sorted(patterns.items(), key=lambda kv: -kv[1]):
                lines.append(f"- {coil_type}: {pattern} — {n}")
    return lines


def render(gate: dict[str, Any]) -> str:
    cal = gate["calibration"]
    lines = ["# CCSI coil-data mappings vs past orders — decision tables", "",
             f"Input: `{gate['input']}` (code {gate['code_version']}). Review aid; proposals only.", ""]
    if gate["stale_sources"]:
        lines += [f"> ⚠ **Stale cross-check** — changed since it ran: {', '.join(gate['stale_sources'])}. "
                  "Re-run `scripts/ccsi_report_crosscheck.py` before trusting these tables.", ""]
    lines += ["## Adapter calibration", "", f"**{cal['status']}** — report fields vs the live harvests "
              "(pairing assumed: a harvest records no revision)."]
    if cal["status"] != "PASS":
        lines.append("Until it passes, demotion / promotion proposals are held (`held_adapter`).")
    lines += ["", "| harvested coil | status |", "|---|---|"] + [f"| {c['coil']} | {c['status']} |" for c in cal["coils"]]
    for key in cal["adapter_mismatch"]:
        for d in cal["fields"][key]["disagree"]:
            lines.append(f"- `{key}` {d['coil']}: harvest {d['harvest']!r} vs report {d['report']!r} (raw {d['raw']!r})")
    lines += _focus_section(gate)
    tiers = gate["tiers"]
    lines += ["", "## Evidence", "", "| tier | projects | coils |", "|---|---|---|"]
    lines += [f"| {t} | {v['projects']} | {v['coils']} |" for t, v in sorted(tiers.items())]
    lines += ["", f"Runner skips: {gate['runner_skips'] or 'none'}",
              f"Cloud-only (not read — a later approved download would unlock): {len(gate['cloud_only'])} projects", ""]
    lines += ["## Proposals (order tier counts; John decides)", "",
              "| proposal | field | status | role | adapter | order projects matched | distinct values | defects | by tier |",
              "|---|---|---|---|---|---|---|---|---|"]
    props = sorted(gate["proposals"].values(), key=lambda p: (_PROPOSAL_ORDER.index(p["proposal"]), p["coil_type"], p["ccsi_id"]))
    for p in props:
        tier_text = "; ".join(f"{t}: " + ", ".join(f"{k} {n}" for k, n in sorted(c.items())) for t, c in p["by_tier"].items())
        mark = " (positive-only)" if p.get("positive_only") else ""
        lines.append(f"| {p['proposal']} | {p['coil_type']} `{p['ccsi_id']}`{mark} | {p['mapping_status']} | {p['role']} | "
                     f"{p['adapter']} | {p['order_match_projects']} | {p['distinct_values']} | {len(p['defects'])} | {tier_text} |")
    lines += ["", "## Defect rows (order tier)", "",
              "| project | coil | field | cause | CoilForge | report | REV0 | report file |", "|---|---|---|---|---|---|---|---|"]
    for p in props:
        for r in p["defects"]:
            lines.append(f"| {r['project']} | {r['tag']} | `{r['ccsi_id']}` | {r['cause']} | {_cell(r['coilforge'])} | "
                         f"{_cell(r['ccsi'])} | {_cell(r['rev0'])} | {_cell(r['truth_file'])} |")
    lines += ["", "## Decision tables (order tier; counts = coils by verdict or cause)", ""]
    for name, per_type in gate["decision_tables"].items():
        lines.append(f"**{name}**")
        for coil_type, table in per_type.items():
            lines.append(f"- {coil_type}: {json.dumps(table, sort_keys=True)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--crosscheck", type=Path, default=CROSSCHECK)
    parser.add_argument("--no-calibration", action="store_true", help="do not re-read the harvested projects' reports")
    args = parser.parse_args()
    if not args.crosscheck.exists():
        print(f"missing {args.crosscheck} — run scripts/ccsi_report_crosscheck.py first", file=sys.stderr)
        return 2
    data = json.loads(args.crosscheck.read_text(encoding="utf-8"))
    harvests = load_harvests()
    calibration_keys = frozenset((str(h["project"]), str(h.get("tag") or "").upper()) for h in harvests)

    runner = load_runner()
    if args.no_calibration:
        calibration = og.calibrate([])
        calibration["status"] = "SKIPPED"
    else:
        po_root = Path(os.environ.get("COILFORGE_PO_ROOT") or runner.DEFAULT_PO_ROOT)
        calibration = og.calibrate(calibration_pairs(harvests, runner, po_root))

    results = data.get("projects", [])
    rows = og.annotate(results, calibration_keys)
    tiers: dict[str, dict[str, Any]] = {}
    for tier in ("order", "quote_only", "calibration"):
        mine = [r for r in rows if r["tier"] == tier]
        tiers[tier] = {"projects": len({r["project"] for r in mine}), "coils": len({(r["project"], r["tag"]) for r in mine})}
    per_tier_results = {
        tier: [{**p, "coils": [c for c in p.get("coils", []) if og.coil_tier(p, c.get("tag") or "", calibration_keys) == tier]}
               for p in results]
        for tier in tiers
    }
    gate = {
        "input": args.crosscheck.relative_to(ROOT).as_posix() if args.crosscheck.is_relative_to(ROOT) else str(args.crosscheck),
        "code_version": data.get("code_version"), "stale_sources": stale_sources(args.crosscheck),
        "calibration": calibration, "tiers": tiers, "runner_skips": data.get("skips") or {},
        "cloud_only": data.get("cloud_only") or {},
        "degraded_pages_outside_coils": {p["project"]: p["degraded_pages_outside_coils"]
                                         for p in results if p.get("degraded_pages_outside_coils")},
        "proposals": og.proposals(rows, calibration), "decision_tables": og.decision_tables(rows),
        "field_counts_by_tier": {tier: runner.aggregate(res) for tier, res in per_tier_results.items()},
        "review_aid_only": True,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "gate.json").write_text(json.dumps(gate, indent=2, default=str), encoding="utf-8")
    (OUT_DIR / "summary.md").write_text(render(gate), encoding="utf-8")
    counts = Counter(p["proposal"] for p in gate["proposals"].values())
    print(f"calibration {calibration['status']} · tiers {tiers} · proposals {dict(counts)}")
    if gate["stale_sources"]:
        print(f"WARNING stale cross-check: {gate['stale_sources']}")
    print(f"wrote {OUT_DIR / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
