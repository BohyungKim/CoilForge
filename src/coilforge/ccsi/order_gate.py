"""Order cross-check gate — John's decision tables over the CCSI report cross-check.

``scripts/ccsi_report_crosscheck.py`` compares the CCSI selection report filed with each order
against CoilForge's current submittal extraction (``crosscheck_coil`` rows). This module turns
those rows into what John rules on (plan Rev 3.1, 2026-09-30): which coil-data mappings the
ordered projects support, contradict, or cannot test. Four rules carry it:

* **Evidence tiers.** ``calibration`` = a coil with a live CCSI form harvest — those coils wrote
  the maps, so they check the report adapter and never count as corpus evidence. ``order`` =
  a report at REV>=1 (the ordered state). ``quote_only`` = only a REV0 exists; shown, never
  counted (John 2026-09-30).
* **Only a ``mismatch`` row gets a cause**, and each cause says whether the push would have been
  wrong (``counts_as_defect``). An order-time re-selection that CoilForge's REV0 agrees with, a
  D7-withheld field, or a report the parser could not read is explained; a wrong D2 default, a
  per-coil vs all-coils airflow/GPM, and anything else are defects.
* **Proposals only.** Demotion = a pushable field with a defect on an order project. Promotion =
  an input with a source, matched on >=3 order projects with >=2 distinct stated values, no
  defect, and a calibrated adapter. Nothing here edits a map.
* **Adapter calibration.** The report -> CCSI-id adapter is itself a mapping; it is checked
  field by field against the harvests before its verdicts carry weight.

Pure: dicts in, dicts out.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from coilforge.ccsi.coil_data_map import GEOMETRY_RESELECT_IDS, PUSHABLE_STATUSES, load_coil_data_map
from coilforge.ccsi.selection_report import LABEL_TABLE, option_key
from coilforge.checklist.compare import _match

# cause -> counts_as_defect
CAUSES: dict[str, bool] = {
    "report_unparsed": False,          # the report side could not be read for this field
    "map_options_incomplete": False,   # the report value is not in the map's captured options
    "reselect_predicted": False,       # D7 withheld the field: never pushed
    "changed_at_order": False,         # REV0 == CoilForge, the order changed it
    "notation": False,                 # computed field, per-coil vs all-coils
    "rounding": False,                 # printed precision only (77.9 vs 77.89, 1050 vs 1048)
    "default_counterexample": True,    # a D2 default the order contradicts
    "quantity_semantics": True,        # pushed airflow / GPM off by the coil quantity
    "changed_at_order_cf_differs": True,  # changed at order, and CoilForge matched neither side
    "unexplained": True,
}
_REPORT_UNPARSED_PREFIXES = ("unparsed_number:", "unparsed_composite:", "ambiguous_duplicate:")
_MODEL_CHECKED_IDS = ("RowsDeep", "FinnedHeight", "FinsPerInch", "FinnedLength")
# Assumption (plan review M3): CCSI can solve one of these from the others, so pushing all of them
# may over-constrain the rating — John decides which to push rather than a promotion rule.
_SOLVED_TOGETHER: frozenset[tuple[str, str]] = frozenset({
    ("HWC", "LeavingDryBulb"), ("HWC", "EnteringFluidTemp"), ("HWC", "LeavingFluidTemp"),
    ("CWC", "EnteringFluidTemp"), ("CWC", "LeavingFluidTemp"),
})
# The form's LeavingDryBulb is a locked input / design target (55 / 66.8 / 72 / 90 on the
# harvests) while the report prints the rating — the two never measure the adapter.
_NOT_COMPARABLE_ON_FORM: frozenset[str] = frozenset({"LeavingDryBulb"})
_FORM_PLACEHOLDERS: frozenset[str] = frozenset({"calculate", "optimise"})
PERFORMANCE_IDS: tuple[str, ...] = ("LeavingDryBulb", "Capacity", "FaceVelocity", "AirFlowPerCoil")
_FLUID_IDS: dict[str, str] = {"EnteringFluidTemp": "EWT", "LeavingFluidTemp": "LWT", "FluidFlowRate": "GPM"}
# The report states these only when they differ from CCSI's usual (a Coating line on the quote —
# report_extras), so a match with the default is unobservable: every order that shows the field
# disagrees with a default-filled push. Read their demotion as "the default is wrong on these
# coils", and their value table as the rule to find (John 2026-09-30, decision A).
POSITIVE_ONLY_IDS: frozenset[str] = frozenset({"CoilCoating"})
# reason_code -> how CoilForge filled the field when a rule is what decides it (decision A)
_RULE_SOURCES: dict[str, str] = {
    "CCSI_DEFAULT_PROFILE": "default_profile",
    "CCSI_SOURCE_MISSING": "submittal_silent",
    "CCSI_NO_SOURCE": "no_source",
}
PROMOTE_MIN_PROJECTS = 3
ROUNDING_REL = 0.002
PROMOTE_MIN_VALUES = 2


@dataclass(frozen=True)
class FieldInfo:
    role: str
    mapping_status: str
    transform: str
    has_source: bool


FieldInfoLookup = Callable[[str, str], "FieldInfo | None"]


def map_field_info(coil_type: str, ccsi_id: str) -> FieldInfo | None:
    """The live map's view of one field (the default lookup)."""
    try:
        entry = load_coil_data_map(coil_type).fields.get(ccsi_id)
    except FileNotFoundError:
        return None
    if entry is None:
        return None
    return FieldInfo(entry.role, entry.mapping_status, entry.transform,
                     bool(entry.draft_key or entry.canonical_path or entry.default is not None))


# ------------------------------------------------------------------ small helpers
def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def same_value(a: Any, b: Any, *, rel_tol: float | None = None, refrigerant: bool = False) -> bool:
    """Numbers through the shared comparator, text through the report parser's option key."""
    x, y = _number(a), _number(b)
    if x is not None and y is not None:
        return _match(x, y, rel_tol=rel_tol) == "match"
    return option_key(a, refrigerant=refrigerant) == option_key(b, refrigerant=refrigerant)


def field_flags(report_flags: Iterable[str], coil_type: str) -> dict[str, list[str]]:
    """Report parse flags keyed by the CCSI id they concern (a flag never masks another field)."""
    table = LABEL_TABLE.get(coil_type, {})
    out: dict[str, list[str]] = defaultdict(list)
    for flag in report_flags:
        kind, _, subject = flag.partition(":")
        ids: list[str] = []
        if kind in ("unparsed_number", "unmatched_option"):
            ids = [subject]
        elif kind == "unparsed_composite":
            spec = table.get(subject)
            if spec:
                ids = [spec[0]] + {"connection": ["ConnectionMaterial"], "header": ["HeaderWallSchedule"]}.get(spec[1], [])
        elif kind == "ambiguous_duplicate" and subject == "Fouling Factor":
            ids = ["AirSideFoulingFactor", "TubeSideFoulingFactor"]
        elif kind == "parse_inconsistent":
            ids = list(_MODEL_CHECKED_IDS)
        for ccsi_id in ids:
            out[ccsi_id].append(flag)
    return dict(out)


def _coil_quantity(coil: Mapping[str, Any]) -> float | None:
    for row in coil.get("rows", []):
        if row.get("ccsi_id") == "CoilQuantity":
            return _number(row.get("ccsi"))
    return None


def _ratio_is(a: Any, b: Any, qty: float | None) -> bool:
    x, y = _number(a), _number(b)
    if not qty or qty <= 1 or not x or not y:
        return False
    return any(abs(r - qty) <= 0.01 * qty for r in (x / y, y / x))


def _within_rounding(a: Any, b: Any) -> bool:
    """Two numbers that differ only at printed precision: <= 0.015 apart or within 0.2 %."""
    x, y = _number(a), _number(b)
    if x is None or y is None or x == y:
        return False
    return abs(x - y) <= max(0.015, ROUNDING_REL * max(abs(x), abs(y)))


# ------------------------------------------------------------------ causes
def mismatch_cause(row: Mapping[str, Any], coil: Mapping[str, Any], info: FieldInfo | None) -> str:
    """Why a ``mismatch`` row disagrees (first rule that applies)."""
    ccsi_id = row["ccsi_id"]
    flags = field_flags(coil.get("report_flags") or [], coil.get("coil_type") or "").get(ccsi_id, [])
    if any(f.startswith(_REPORT_UNPARSED_PREFIXES) or f == "parse_inconsistent" for f in flags):
        return "report_unparsed"
    if any(f.startswith("unmatched_option:") for f in flags):
        return "map_options_incomplete"
    code = row.get("reason_code")
    if code == "CCSI_GEOMETRY_RESELECT":
        return "reselect_predicted"
    if code == "CCSI_DEFAULT_PROFILE":
        return "default_counterexample"
    if row.get("changed_at_order"):
        return "changed_at_order" if same_value(row.get("coilforge"), row.get("rev0")) else "changed_at_order_cf_differs"
    if _within_rounding(row.get("coilforge"), row.get("ccsi")):
        return "rounding"
    if _ratio_is(row.get("coilforge"), row.get("ccsi"), _coil_quantity(coil)):
        if (info and info.role) == "computed" or row.get("role") == "computed":
            return "notation"
        return "quantity_semantics"
    return "unexplained"


def coil_tier(project: Mapping[str, Any], tag: str, calibration_keys: frozenset[tuple[str, str]]) -> str:
    if (str(project.get("project")), str(tag).upper()) in calibration_keys:
        return "calibration"
    return "order" if project.get("report_kind") == "order" else "quote_only"


def annotate(results: Iterable[Mapping[str, Any]], calibration_keys: frozenset[tuple[str, str]], *,
             field_info: FieldInfoLookup = map_field_info) -> list[dict[str, Any]]:
    """One flat row per compared field with tier, cause and defect flag (Tag excluded)."""
    out: list[dict[str, Any]] = []
    for project in results:
        for coil in project.get("coils", []):
            tier = coil_tier(project, coil.get("tag") or "", calibration_keys)
            reselect = any(r.get("reason_code") == "CCSI_GEOMETRY_RESELECT" for r in coil.get("rows", []))
            for row in coil.get("rows", []):
                if row.get("ccsi_id") == "Tag":
                    continue  # the pairing key; single_of_type pairing makes a mismatch expected
                info = field_info(coil["coil_type"], row["ccsi_id"])
                cause = mismatch_cause(row, coil, info) if row.get("verdict") == "mismatch" else None
                out.append({
                    "project": str(project.get("project")), "tag": coil.get("tag"), "coil_type": coil["coil_type"],
                    "tier": tier, "coil_reselect": reselect, "ccsi_id": row["ccsi_id"], "role": row.get("role"),
                    "verdict": row.get("verdict"), "reason_code": row.get("reason_code"),
                    "cause": cause, "counts_as_defect": bool(cause and CAUSES[cause]),
                    "coilforge": row.get("coilforge"), "ccsi": row.get("ccsi"), "rev0": row.get("rev0"),
                    "truth_file": project.get("truth_file"),
                })
    return out


# ------------------------------------------------------------------ calibration
def calibrate(pairs: Iterable[Mapping[str, Any]], *, field_info: FieldInfoLookup = map_field_info) -> dict[str, Any]:
    """Report record vs live harvest, field by field.

    ``pairs``: ``{project, tag, coil_type, report_fields | None, harvest_fields, missing_reason?}``.
    A harvest value that is blank, ``Calculate`` / ``Optimise``, a computed 0, or a form field that
    is not the rating (LeavingDryBulb) is no evidence either way. Pairing is always assumed: a
    harvest carries no revision, only the project and tag.
    """
    fields: dict[str, dict[str, Any]] = defaultdict(lambda: {"agree": [], "disagree": [], "no_evidence": 0})
    coils = []
    for pair in pairs:
        key = f"{pair['project']}/{pair['tag']}"
        report = pair.get("report_fields")
        if report is None:
            coils.append({"coil": key, "status": pair.get("missing_reason") or "no_report"})
            continue
        coils.append({"coil": key, "status": "paired", "pairing": "assumed"})
        harvest = pair.get("harvest_fields") or {}
        for ccsi_id, got in report.items():
            if ccsi_id == "Tag":
                continue
            slot = fields[f"{pair['coil_type']}:{ccsi_id}"]
            want = (harvest.get(ccsi_id) or {}).get("value")
            info = field_info(pair["coil_type"], ccsi_id)
            computed = bool(info and info.role == "computed")
            if (_blank(want) or str(want).strip().casefold() in _FORM_PLACEHOLDERS
                    or ccsi_id in _NOT_COMPARABLE_ON_FORM or (computed and _number(want) == 0)):
                slot["no_evidence"] += 1
                continue
            value = got.get("value")
            if same_value(want, value, rel_tol=0.01 if computed else None, refrigerant=ccsi_id == "Refrigerant"):
                slot["agree"].append(key)
            else:
                slot["disagree"].append({"coil": key, "harvest": want, "report": value, "raw": got.get("raw")})
    for slot in fields.values():
        slot["status"] = ("adapter_mismatch" if slot["disagree"] else
                          "calibrated" if slot["agree"] else "adapter_uncalibrated")
    complete = bool(coils) and all(c["status"] == "paired" for c in coils)
    mismatched = sorted(k for k, v in fields.items() if v["status"] == "adapter_mismatch")
    return {"coils": coils, "fields": dict(fields), "complete": complete, "adapter_mismatch": mismatched,
            "status": "PASS" if complete and not mismatched else ("FAIL" if mismatched else "INCOMPLETE")}


# ------------------------------------------------------------------ proposals
def proposals(rows: Iterable[Mapping[str, Any]], calibration: Mapping[str, Any], *,
              field_info: FieldInfoLookup = map_field_info) -> dict[str, dict[str, Any]]:
    """Per ``TYPE:ccsi_id``: counts by tier, defects, and one proposal (order tier only counts)."""
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[f"{row['coil_type']}:{row['ccsi_id']}"].append(row)
    cal_fields = calibration.get("fields") or {}
    out: dict[str, dict[str, Any]] = {}
    for key, group in sorted(grouped.items()):
        coil_type, ccsi_id = key.split(":", 1)
        info = field_info(coil_type, ccsi_id)
        if info is None:
            continue
        by_tier: dict[str, Counter] = defaultdict(Counter)
        for r in group:
            by_tier[r["tier"]][r["cause"] or r["verdict"]] += 1
        order = [r for r in group if r["tier"] == "order"]
        defects = [r for r in order if r["counts_as_defect"]]
        matched = [r for r in order if r["verdict"] == "match" and r["reason_code"] != "CCSI_DEFAULT_PROFILE"]
        match_projects = {r["project"] for r in matched}
        match_values = {option_key(r["ccsi"]) for r in matched}
        # Printed at all is judged over every tier: no order evidence yet is not "never printed".
        printed = any(r["verdict"] != "absent_on_form" for r in group)
        adapter = (cal_fields.get(key) or {}).get("status", "adapter_uncalibrated")
        if calibration.get("status") != "PASS" and adapter == "calibrated":
            adapter = "calibration_incomplete"
        pushable = info.mapping_status in PUSHABLE_STATUSES
        if pushable:
            if not printed:
                proposal = "untestable_from_report"
            elif defects:
                proposal = "demote_candidate" if adapter == "calibrated" else "held_adapter"
            elif match_projects:
                proposal = "supported"
            else:
                proposal = "insufficient"
        elif info.role != "input":
            proposal = "read_back_only"
        elif not info.has_source:
            proposal = "no_source"
        elif (coil_type, ccsi_id) in _SOLVED_TOGETHER:
            proposal = "needs_decision"
        elif defects:
            proposal = "blocked_by_defects"
        elif len(match_projects) >= PROMOTE_MIN_PROJECTS and len(match_values) >= PROMOTE_MIN_VALUES:
            proposal = "promote_candidate" if adapter == "calibrated" else "held_adapter"
        else:
            proposal = "insufficient"
        out[key] = {
            "coil_type": coil_type, "ccsi_id": ccsi_id, "role": info.role, "mapping_status": info.mapping_status,
            "adapter": adapter, "proposal": proposal, "positive_only": ccsi_id in POSITIVE_ONLY_IDS,
            "order_match_projects": len(match_projects),
            "distinct_values": len(match_values), "defects": defects,
            "by_tier": {tier: dict(counts) for tier, counts in sorted(by_tier.items())},
        }
    return out


# ------------------------------------------------------------------ decision tables
def decision_tables(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Order-tier evidence for D1 (material + gauge), D2 (defaults), D6 (System Type),
    D7 (re-selection gate) and D4 (report LDB / Capacity — the rating, not a push)."""
    order = [r for r in rows if r["tier"] == "order"]

    def tally(selected: Iterable[Mapping[str, Any]]) -> dict[str, int]:
        return dict(Counter(r["cause"] or r["verdict"] for r in selected))

    tables: dict[str, Any] = {"D1": {}, "D2": {}, "D6": {}, "D7": {}, "D4": {}, "fluid": {}, "rule_candidates": {}}
    # Decision A (John 2026-09-30): what the submittal never states is set by a rule learned from
    # orders. For every field CoilForge fills from the default profile — or cannot fill at all
    # because the submittal is silent (HGRH Vapor Temperature, the ACFM basis) — which values the
    # ordered reports printed, and on how many coils the report was silent (silence is not the
    # default for POSITIVE_ONLY_IDS).
    for r in order:
        source = _RULE_SOURCES.get(r["reason_code"] or "")
        if source is None or r["role"] not in (None, "input"):
            continue
        slot = tables["rule_candidates"].setdefault(r["coil_type"], {}).setdefault(
            r["ccsi_id"], {"source": source, "default": r["coilforge"] if source == "default_profile" else None,
                           "report_values": Counter(), "not_printed": 0})
        if r["verdict"] == "absent_on_form":
            slot["not_printed"] += 1
        else:
            slot["report_values"][str(r["ccsi"])] += 1
    for per_type in tables["rule_candidates"].values():
        for slot in per_type.values():
            slot["report_values"] = dict(slot["report_values"])
    # Which of EWT / LWT / GPM an ordered water selection kept from the submittal (John 2026-09-30:
    # decide what to push from past orders): "EWT match, LWT match, GPM mismatch" on most coils
    # means CCSI solved the flow from the temperatures.
    water: dict[tuple[str, str, str], dict[str, str]] = defaultdict(dict)
    for r in order:
        if r["coil_type"] in ("CWC", "HWC") and r["ccsi_id"] in _FLUID_IDS:
            water[(r["coil_type"], r["project"], str(r["tag"]))][_FLUID_IDS[r["ccsi_id"]]] = r["cause"] or r["verdict"]
    for (coil_type, *_coil), seen in water.items():
        pattern = ", ".join(f"{name} {seen.get(name, 'absent')}" for name in _FLUID_IDS.values())
        tables["fluid"].setdefault(coil_type, Counter())[pattern] += 1
    tables["fluid"] = {t: dict(c) for t, c in tables["fluid"].items()}
    for coil_type in sorted({r["coil_type"] for r in order}):
        mine = [r for r in order if r["coil_type"] == coil_type]
        tables["D1"][coil_type] = {i: tally(r for r in mine if r["ccsi_id"] == i and not r["coil_reselect"])
                                   for i in ("TubeMaterial", "FinMaterial")}
        defaults = [r for r in mine if r["reason_code"] == "CCSI_DEFAULT_PROFILE" and r["verdict"] in ("match", "mismatch")]
        tables["D2"][coil_type] = {i: tally(r for r in defaults if r["ccsi_id"] == i)
                                   for i in sorted({r["ccsi_id"] for r in defaults})}
        tables["D6"][coil_type] = tally(r for r in mine if r["ccsi_id"] == "RefrigerationSystemType")
        tables["D7"][coil_type] = {i: tally(r for r in mine if r["ccsi_id"] == i and r["coil_reselect"])
                                   for i in sorted(GEOMETRY_RESELECT_IDS)}
        tables["D4"][coil_type] = {i: tally(r for r in mine if r["ccsi_id"] == i) for i in PERFORMANCE_IDS}
    return tables
