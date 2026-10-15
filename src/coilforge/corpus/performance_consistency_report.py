"""Run the performance self-consistency checks over the ordered-coil corpus (read-only).

Two inputs, both produced by the CCSI report cross-check runner and both only ever read:

* ``crosscheck.json`` — per coil, the CoilForge value next to the ordered CCSI report's value.
  Its ``coilforge`` column is the value AFTER the CCSI map's transforms, so the adapter undoes
  the two that matter here: ``FluidFlowRate`` is x quantity ("All Coils") and the fluid is
  stated as a glycol share (plain water = 0).
* the runner's ``cache/`` folder — the push-time ``sources`` mapping of each coil, fed to the
  checks untransformed. It is the only place a DX coil's sensible capacity appears.

The report names project numbers and coil tags, so it is written outside the repo. Review
aid only: it measures the checks, it does not rule on a coil.
"""
from __future__ import annotations

import collections
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from coilforge.coil_utilities import performance_consistency as pc

HEATING_TYPES = ("HGRH", "HWC")
SWEEP_FACTORS = (1.08, 1.084, 1.085)
SWEEP_TOLERANCES = (0.01, 0.015, 0.02, 0.03)

# crosscheck row (ccsi_id) -> the source key the checks read. All are per-coil values.
_ROW_TO_SOURCE = {
    "AirFlowPerCoil": "total_air_flow_cfm",
    "EnteringDryBulb": "entering_dry_bulb_f",
    "LeavingDryBulb": "leaving_dry_bulb_f",
    "EnteringWetBulb": "entering_wet_bulb_f",
    "Altitude": "altitude_ft",
    "FaceVelocity": "face_velocity_fpm",
    "FinnedHeight": "finned_height",
    "FinnedLength": "finned_length",
    "Capacity": "total_capacity_mbh",
    "EnteringFluidTemp": "airside_conditions.fluid_entering_temp_f",
    "LeavingFluidTemp": "airside_conditions.fluid_leaving_temp_f",
}
_REQUIRED_SOMEWHERE = ("AirFlowPerCoil", "Capacity")


class ReportInputError(ValueError):
    """An input file is truncated, unreadable or not the structure this report was built for."""


def read_json(path: Path) -> Any:
    """Parse one input. The runner writes these non-atomically, so a read during a batch can
    see a truncated file: that is reported, never half-used."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportInputError(f"cannot read {path.name}: {exc}") from exc


def validate_crosscheck_document(doc: Any) -> list[str]:
    """Structural problems that would make the adapter misread the file (empty = usable)."""
    if not isinstance(doc, Mapping) or not isinstance(doc.get("projects"), list):
        return ["root is not an object with a 'projects' list"]
    problems: list[str] = []
    seen: set[str] = set()
    for p_index, project in enumerate(doc["projects"]):
        if not isinstance(project, Mapping) or "project" not in project or not isinstance(project.get("coils"), list):
            problems.append(f"projects[{p_index}] lacks 'project' / 'coils'")
            continue
        for c_index, coil in enumerate(project["coils"]):
            where = f"projects[{p_index}].coils[{c_index}]"
            if not isinstance(coil, Mapping) or not all(k in coil for k in ("tag", "coil_type")) \
                    or not isinstance(coil.get("rows"), list):
                problems.append(f"{where} lacks 'tag' / 'coil_type' / 'rows'")
                continue
            for row in coil["rows"]:
                if not isinstance(row, Mapping) or not all(k in row for k in ("ccsi_id", "coilforge", "ccsi", "verdict")):
                    problems.append(f"{where} has a row without ccsi_id / coilforge / ccsi / verdict")
                    break
                seen.add(row["ccsi_id"])
    for ccsi_id in _REQUIRED_SOMEWHERE:
        if not problems and ccsi_id not in seen:
            problems.append(f"no coil carries a {ccsi_id!r} row")
    return problems[:20]


def _rows(coil: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    # Keyed by ccsi_id: source_key repeats (TotalAirFlow and AirFlowPerCoil share one).
    return {row["ccsi_id"]: row for row in coil["rows"]}


def inputs_from_crosscheck_coil(coil: Mapping[str, Any]) -> dict[str, Any]:
    """The per-coil submittal values of one crosscheck coil, in the shape the checks read."""
    rows = _rows(coil)
    sources: dict[str, Any] = {}
    for ccsi_id, key in _ROW_TO_SOURCE.items():
        value = rows.get(ccsi_id, {}).get("coilforge")
        if value is not None:
            sources[key] = value
    flow = pc.parse_number(rows.get("FluidFlowRate", {}).get("coilforge"))
    quantity = pc.parse_number(rows.get("CoilQuantity", {}).get("coilforge"))
    if flow is not None and quantity is not None and quantity > 0:
        sources["airside_conditions.fluid_flow_rate_gpm"] = flow / quantity
    fluid = rows.get("FluidType", {}).get("coilforge")
    glycol = pc.parse_number(rows.get("GlycolRatio", {}).get("coilforge"))
    if isinstance(fluid, str) and glycol is not None:
        water = fluid.strip().lower() == "water"
        # Plain water reads 0 where the map's glycol_ratio transform ran and 100 where the column
        # is still the submittal's own percent; both mean water. Any other share contradicts the
        # fluid name and is left out rather than interpreted.
        if not water or glycol in (0, 100):
            sources["airside_conditions.fluid_type"] = fluid
            sources["airside_conditions.fluid_percent"] = 100.0 if water else glycol
    return sources


def select_cache_files(cache_dir: Path, code_version: str) -> list[Path]:
    """Cache files of ``code_version`` only, the most recent per PDF sha.

    Names are ``<sha>_<code_version>_<hash>.json``. Older code versions stay on disk; mixing
    them in would report extractions the current push path no longer produces.
    """
    latest: dict[str, Path] = {}
    marker = f"_{code_version}_"
    for path in sorted(cache_dir.glob("*.json")):
        if marker not in path.name:
            continue
        sha = path.name.split("_", 1)[0]
        if sha not in latest or path.stat().st_mtime > latest[sha].stat().st_mtime:
            latest[sha] = path
    return [latest[sha] for sha in sorted(latest)]


def load_cache_coils(cache_dir: Path, code_version: str) -> list[dict[str, Any]]:
    coils: list[dict[str, Any]] = []
    for path in select_cache_files(cache_dir, code_version):
        doc = read_json(path)
        if not isinstance(doc, Mapping) or not isinstance(doc.get("coils") or [], list):
            raise ReportInputError(f"{path.name} is not a runner cache file")
        for coil in doc.get("coils") or []:
            if not isinstance(coil, Mapping) or not isinstance(coil.get("sources"), Mapping):
                raise ReportInputError(f"{path.name} has a coil without 'sources'")
            coils.append({"pdf": path.name.split("_", 1)[0][:8], "tag": coil.get("tag"),
                          "coil_type": coil.get("coil_type"), "sources": coil["sources"]})
    return coils


def _finding(sources: Mapping[str, Any], coil_type: Any, check: str) -> pc.ConsistencyFinding:
    report = pc.check_performance_consistency(sources, coil_type=coil_type)
    return next(f for f in report.findings if f.check == check)


def _reclassify(finding: pc.ConsistencyFinding, factor: float, tolerance: float) -> str | None:
    """The air-basis verdict a different (factor, tolerance) would give — for the sweep only.

    Reuses the module's density model: Actual = factor x (the module's actual / standard ratio).
    """
    if finding.observed is None or "actual" not in finding.expected:
        return None
    actual = factor * finding.expected["actual"] / finding.expected["standard"]
    standard_ok = abs(finding.observed - factor) <= tolerance + 1e-9
    actual_ok = abs(finding.observed - actual) <= tolerance + 1e-9
    if standard_ok and actual_ok:
        return "indeterminate"
    return "standard" if standard_ok else "actual" if actual_ok else "inconsistent"


def _sweep(findings: Iterable[pc.ConsistencyFinding]) -> list[dict[str, Any]]:
    findings = list(findings)
    out = []
    for factor in SWEEP_FACTORS:
        for tolerance in SWEEP_TOLERANCES:
            verdicts = collections.Counter(_reclassify(f, factor, tolerance) for f in findings)
            verdicts.pop(None, None)
            out.append({"factor": factor, "tolerance": tolerance, "evaluable": sum(verdicts.values()),
                        "inconsistent": verdicts["inconsistent"], "indeterminate": verdicts["indeterminate"]})
    return out


def _label(finding: pc.ConsistencyFinding) -> str:
    return finding.air_basis or finding.verdict


def build_report(doc: Mapping[str, Any], cache_coils: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Every table of the corpus report as plain data (see ``render_markdown``)."""
    heating: list[dict[str, Any]] = []
    water: list[dict[str, Any]] = []
    face = collections.Counter()
    for project in doc["projects"]:
        for coil in project["coils"]:
            rows = _rows(coil)
            sources = inputs_from_crosscheck_coil(coil)
            coil_type = coil["coil_type"]
            ident = {"project": str(project["project"]), "tag": coil["tag"], "coil_type": coil_type}
            face[_finding(sources, coil_type, "face_velocity").verdict] += 1
            if coil_type in HEATING_TYPES:
                heating.append({**ident, "finding": _finding(sources, coil_type, "air_sensible_balance"),
                                "capacity_verdict": rows.get("Capacity", {}).get("verdict"),
                                "report_acfm": rows.get("ACFM", {}).get("ccsi")})
            if coil_type in ("CWC", "HWC"):
                water.append({**ident, "finding": _finding(sources, coil_type, "fluid_heat_balance"),
                              "fluid": sources.get("airside_conditions.fluid_type"),
                              "percent": sources.get("airside_conditions.fluid_percent")})

    evaluable = [h for h in heating if h["finding"].verdict != "cannot_evaluate"]
    by_capacity = collections.Counter((_label(h["finding"]), h["capacity_verdict"]) for h in evaluable)
    basis_vs_acfm = collections.Counter(
        (_label(h["finding"]), h["report_acfm"]) for h in evaluable if h["capacity_verdict"] == "match")
    k_bins = collections.Counter(round(h["finding"].observed, 2) for h in evaluable)

    fluid_groups: dict[tuple[Any, Any], list[dict[str, Any]]] = collections.defaultdict(list)
    for w in water:
        if w["finding"].observed is not None:
            fluid_groups[(w["fluid"], w["percent"])].append(w)
    fluids = []
    for (fluid, percent), members in sorted(fluid_groups.items(), key=str):
        factors = [m["finding"].observed for m in members]
        expected = members[0]["finding"].expected
        outside = [m for m in members if expected and not
                   (expected["band_low"] <= m["finding"].observed <= expected["band_high"])]
        fluids.append({"fluid": fluid, "percent": percent, "coils": len(members),
                       "min": min(factors), "max": max(factors),
                       "band": [expected["band_low"], expected["band_high"]] if expected else None,
                       "outside_unmargined_band": [f"{m['project']} {m['tag']}" for m in outside],
                       "verdicts": dict(collections.Counter(m["finding"].verdict for m in members))})

    report: dict[str, Any] = {
        "code_version": doc.get("code_version"),
        "defaults": {"sensible_factor": pc.SENSIBLE_FACTOR, "k_tolerance": pc.K_TOLERANCE,
                     "face_velocity_tolerance": pc.FACE_VELOCITY_REL_TOLERANCE,
                     "fluid_band_margin": pc.FLUID_BAND_MARGIN},
        "heating": {
            "coils": len(heating), "evaluable": len(evaluable),
            "verdicts": dict(collections.Counter(_label(h["finding"]) for h in evaluable)),
            "by_capacity_verdict": [{"basis": b, "capacity": c, "coils": n} for (b, c), n in sorted(by_capacity.items(), key=str)],
            "basis_vs_report_acfm": [{"basis": b, "report_acfm": a, "coils": n} for (b, a), n in sorted(basis_vs_acfm.items(), key=str)],
            "k_histogram": [{"k": k, "coils": n} for k, n in sorted(k_bins.items())],
            "inconsistent": [{"project": h["project"], "tag": h["tag"], "k": round(h["finding"].observed, 3),
                              "expected": {n: round(v, 3) for n, v in h["finding"].expected.items()}}
                             for h in evaluable if h["finding"].verdict == "inconsistent"],
            "sweep": _sweep(h["finding"] for h in heating),
        },
        "fluid": {"coils": len(water), "groups": fluids,
                  # How many coils the self-check actually covered: 0 outside of 0 checked proves nothing.
                  "band_self_check_coils": sum(g["coils"] for g in fluids if g["band"]),
                  "band_self_check_outside": sum(len(g["outside_unmargined_band"]) for g in fluids)},
        "face_velocity": dict(face),
        "review_aid_only": True,
        "export_allowed": False,
    }
    if cache_coils is not None:
        dx = [c for c in cache_coils if c["coil_type"] == "DX"]
        dx_findings = [(c, _finding(c["sources"], "DX", "air_sensible_balance")) for c in dx]
        dx_evaluable = [(c, f) for c, f in dx_findings if f.verdict != "cannot_evaluate"]
        all_checks = collections.Counter()
        for coil in cache_coils:
            for finding in pc.check_performance_consistency(coil["sources"], coil_type=coil["coil_type"]).findings:
                all_checks[(finding.check, finding.verdict, finding.reason_code)] += 1
        report["push_time_sources"] = {
            "coils": len(cache_coils),
            "dx_sensible": {
                "coils": len(dx), "evaluable": len(dx_evaluable),
                "verdicts": dict(collections.Counter(_label(f) for _, f in dx_evaluable)),
                "inconsistent": [{"pdf": c["pdf"], "tag": c["tag"], "k": round(f.observed, 3)}
                                 for c, f in dx_evaluable if f.verdict == "inconsistent"],
                "sweep": _sweep(f for _, f in dx_findings),
            },
            "all_checks": [{"check": c, "verdict": v, "reason_code": r, "coils": n}
                           for (c, v, r), n in sorted(all_checks.items())],
        }
    return report


def _table(header: list[str], rows: Iterable[Iterable[Any]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return lines + [""]


def render_markdown(report: Mapping[str, Any]) -> str:
    d = report["defaults"]
    stamp = f"F {d['sensible_factor']}, tol ±{d['k_tolerance']}"
    h = report["heating"]
    out = ["# Performance self-consistency — corpus report", "",
           f"crosscheck code_version: `{report['code_version']}`. Review aid only.", "",
           f"## Heating coils — air sensible balance ({stamp})", "",
           f"{h['evaluable']} of {h['coils']} evaluable: " + ", ".join(f"{k} {v}" for k, v in sorted(h["verdicts"].items())), ""]
    out += _table(["basis / verdict", "Capacity vs order", "coils"],
                  ([r["basis"], r["capacity"], r["coils"]] for r in h["by_capacity_verdict"]))
    out += [f"### Inferred basis vs the report's ACFM — capacity-matched coils only ({stamp})", ""]
    out += _table(["inferred", "report ACFM", "coils"],
                  ([r["basis"], r["report_acfm"], r["coils"]] for r in h["basis_vs_report_acfm"]))
    out += ["### Inconsistent heating coils", ""]
    out += _table(["project", "tag", "k", "expected"],
                  ([r["project"], r["tag"], r["k"], r["expected"]] for r in h["inconsistent"]))
    out += ["### k distribution (rounded to 0.01)", ""]
    out += _table(["k", "coils"], ([r["k"], r["coils"]] for r in h["k_histogram"]))

    push = report.get("push_time_sources")
    out += ["## Sweep — one (F, tol) pair moves both families", ""]
    dx_sweep = {(r["factor"], r["tolerance"]): r for r in (push["dx_sensible"]["sweep"] if push else [])}
    out += _table(["F", "tol", "heating inconsistent", "heating indeterminate", "DX sensible inconsistent"],
                  ([r["factor"], r["tolerance"], r["inconsistent"], r["indeterminate"],
                    dx_sweep.get((r["factor"], r["tolerance"]), {}).get("inconsistent", "n/a")] for r in h["sweep"]))

    f = report["fluid"]
    out += [f"## Fluid side — captured bands (margin ±{d['fluid_band_margin']:.0%})", "",
            f"Band self-check — coils outside their unmargined band: **{f['band_self_check_outside']}** "
            f"of {f['band_self_check_coils']} checked (must be 0; 0 checked means the fluid inputs were not read).", ""]
    out += _table(["fluid", "%", "coils", "min", "max", "band", "outside band", "verdicts"],
                  ([g["fluid"], g["percent"], g["coils"], f"{g['min']:.2f}", f"{g['max']:.2f}", g["band"],
                    ", ".join(g["outside_unmargined_band"]) or "—", g["verdicts"]] for g in f["groups"]))
    out += [f"## Face velocity (tol {d['face_velocity_tolerance']:.0%})", "",
            ", ".join(f"{k} {v}" for k, v in sorted(report["face_velocity"].items())), ""]
    if push:
        s = push["dx_sensible"]
        out += [f"## Push-time sources — DX sensible balance ({stamp})", "",
                f"{s['evaluable']} of {s['coils']} DX coils evaluable: "
                + ", ".join(f"{k} {v}" for k, v in sorted(s["verdicts"].items())), ""]
        out += _table(["pdf", "tag", "k"], ([r["pdf"], r["tag"], r["k"]] for r in s["inconsistent"]))
        out += [f"### Every check on the push-time path ({push['coils']} coils)", ""]
        out += _table(["check", "verdict", "reason", "coils"],
                      ([r["check"], r["verdict"], r["reason_code"], r["coils"]] for r in push["all_checks"]))
    return "\n".join(out)
