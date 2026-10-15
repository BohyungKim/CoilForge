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
* **Estimate confirmation** (John 2026-10-12) is a separate question from promotion: is a value
  CoilForge fills by assumption (a D2 default, a substitution, a style mapping) what the orders
  actually used? There a matching default IS evidence — but only from orders exported before
  CoilForge began pushing (``PUSH_START``), confirmed only on >=5 order projects with every
  counterexample explained, and labelled ``in_sample`` when the value was itself read off orders.

Pure: dicts in, dicts out.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
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
    "air_basis": False,                # order rated on Standard air; CoilForge pushes Actual (John 2026-10-01)
    "ruled_order_change": False,       # John ruled this exact disagreement an order-side change (RULED_ORDER_CHANGES)
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
# (project, TAG, ccsi_id) -> (CoilForge value, order value) John ruled an order-side change: CoilForge
# matches the submittal, the order differs (John 2026-10-12, "셋 다 A"). The ruling covers that exact
# disagreement only — if either value moves, the row is judged afresh, never silently kept explained.
RULED_ORDER_CHANGES: dict[tuple[str, str, str], tuple[str, str]] = {
    # Q1 DX EnteringDryBulb: submittal p33/p42 `DB (F): 74.0`; the REV1 order was re-selected
    ("3239", "CDXC-3", "EnteringDryBulb"): ("74", "75.59"),
    ("3239", "CDXC-4", "EnteringDryBulb"): ("74", "75.59"),
    # Q2 HGRH RowsDeep: every submittal prints `Rows: 2`; the order (2897 from REV0) says 1
    ("2447", "RHHGRC-1", "RowsDeep"): ("2", "1"),
    ("2541", "RHHGRC-1", "RowsDeep"): ("2", "1"),
    ("2897", "RHHGRC-1", "RowsDeep"): ("2", "1"),
    # Q3 water TubeMaterial: the 0.018 default stays; these orders chose 0.020
    ("2298", "PHWC-2", "TubeMaterial"): ("Copper 0.018 Plain", "Copper 0.020 Plain"),
    ("2811", "HHWC-1", "TubeMaterial"): ("Copper 0.018 Plain", "Copper 0.020 Plain"),
    ("2678", "CCWC-1", "TubeMaterial"): ("Copper 0.018 Plain", "Copper 0.020 Plain"),
    ("2811", "CCWC-1", "TubeMaterial"): ("Copper 0.018 Plain", "Copper 0.020 Plain"),
    # John 2026-10-13 (estimate decisions v2 "모두 A"). E1: 3/16 capillary was the order practice before
    # 2026-06-05 (every 3/16 order is a 6/3-6/4 export, every 1/4 order 6/10 or later); the 1/4 default stays.
    ("2862", "CDXC-1", "DXDistCapillarySize"): ("1/4 x 0.025", "3/16 x 0.025"),
    ("2862", "CDXC-2", "DXDistCapillarySize"): ("1/4 x 0.025", "3/16 x 0.025"),
    ("2914", "CDXC-1", "DXDistCapillarySize"): ("1/4 x 0.025", "3/16 x 0.025"),
    ("2914", "CDXC-2", "DXDistCapillarySize"): ("1/4 x 0.025", "3/16 x 0.025"),
    ("2978", "CDXC-1", "DXDistCapillarySize"): ("1/4 x 0.025", "3/16 x 0.025"),
    # E2: 2814 chose Copper water connections from REV0 (26/29 water orders are Steel); the Steel default stays
    ("2814", "CCWC-1", "ConnectionMaterial"): ("Steel", "Copper"),
    ("2814", "PHWC-1", "ConnectionMaterial"): ("Steel", "Copper"),
    ("2814", "HHWC-1", "ConnectionMaterial"): ("Steel", "Copper"),
    # E3: a coil-specific turbulator choice (low-flow laminar coil; 28/29 water orders are No)
    ("3031", "CCWC-2", "TubeTurbulators"): ("No", "Yes"),
    # E4: 2915 re-selected (FPI 12 -> 11); Sine -> Corrugated stays (16/17 Sine orders are Corrugated)
    ("2915", "CDXC-2", "FinSurface"): ("Corrugated", "Flat"),
    # C1: values read correctly off the submittal (22 rows checked against the page, 0 extraction errors);
    # CCSI's selection differed. 2843 is a whole-project re-selection (model -12 -> -16), 3002/3006/2972 differ
    # from REV0, 3095's submittal prints Smooth, 2811/3032 are CCSI-side altitude entries, 2600 re-selected.
    ("2843", "CDXC-1", "FinMaterial"): ("Aluminum 0.010", "Aluminum 0.008"),
    ("2843", "CDXC-2", "FinMaterial"): ("Aluminum 0.010", "Aluminum 0.008"),
    ("2843", "CDXC-3", "FinMaterial"): ("Aluminum 0.010", "Aluminum 0.008"),
    ("3002", "CDXC-1", "TubeMaterial"): ("Copper 0.016 Plain", "Copper 0.014 Plain"),
    ("3006", "CDXC-1", "TubeMaterial"): ("Copper 0.016 Plain", "Copper 0.014 Plain"),
    ("3095", "CDXC-1", "TubeMaterial"): ("Copper 0.016 Plain", "Copper 0.016 Rifled"),
    ("3095", "CDXC-2", "TubeMaterial"): ("Copper 0.016 Plain", "Copper 0.016 Rifled"),
    ("3095", "CDXC-3", "TubeMaterial"): ("Copper 0.016 Plain", "Copper 0.016 Rifled"),
    ("2972", "RHHGRC-1", "FinMaterial"): ("Aluminum 0.008", "Aluminum 0.010"),
    ("3084", "RHHGRC-1", "FinMaterial"): ("Aluminum 0.008", "Aluminum 0.006"),
    ("3117", "RHHGRC-1", "FinMaterial"): ("Aluminum 0.008", "Aluminum 0.006"),
    ("3155", "RHHGRC-1", "FinMaterial"): ("Aluminum 0.008", "Aluminum 0.006"),
    ("2811", "HHWC-1", "Altitude"): ("823", "832"),
    ("3032", "PHWC-1", "Altitude"): ("1056", "1061"),
    ("2600", "PHWC-1", "NumberOfFeeds"): ("3", "2"),
    # John 2026-10-14 (estimate follow-up ③ A): the rest of 2843's whole-project re-selection (C1). The submittal
    # prints Flat and 12 / 18 feeds; the REV3 order carries Corrugated and 16 / 24.
    ("2843", "CDXC-1", "FinSurface"): ("Flat", "Corrugated"),
    ("2843", "CDXC-2", "FinSurface"): ("Flat", "Corrugated"),
    ("2843", "CDXC-3", "FinSurface"): ("Flat", "Corrugated"),
    ("2843", "CDXC-1", "NumberOfFeeds"): ("12", "16"),
    ("2843", "CDXC-2", "NumberOfFeeds"): ("12", "16"),
    ("2843", "CDXC-3", "NumberOfFeeds"): ("12", "16"),
    ("2843", "CDXC-4", "NumberOfFeeds"): ("18", "24"),
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


def _order_air_basis(coil: Mapping[str, Any]) -> str | None:
    """The basis the ordered selection was rated on (report airflow unit -> CCSI ACFM option)."""
    for row in coil.get("rows", []):
        if row.get("ccsi_id") == "ACFM" and not _blank(row.get("ccsi")):
            return str(row["ccsi"]).strip().lower()
    return None


# Fields a Standard-air selection moves away from an Actual-basis push (John 2026-10-01: Direct Coil
# selections were calculated in ACFM, so CoilForge pushes Actual): the basis itself, Altitude (CCSI locks
# it to 0 under Standard) and the rating (an Actual-basis submittal re-rated on Standard air).
_AIR_BASIS_IDS: frozenset[str] = frozenset({"ACFM", "Altitude", "Capacity", "LeavingDryBulb"})


def _is_air_basis(row: Mapping[str, Any], coil: Mapping[str, Any]) -> bool:
    ccsi_id = row["ccsi_id"]
    if ccsi_id not in _AIR_BASIS_IDS or _order_air_basis(coil) != "standard":
        return False
    if ccsi_id == "Altitude":
        return _number(row.get("ccsi")) == 0  # the lock, not a different site altitude
    return True


def _within_rounding(a: Any, b: Any) -> bool:
    """Two numbers that differ only at printed precision: <= 0.015 apart or within 0.2 %."""
    x, y = _number(a), _number(b)
    if x is None or y is None or x == y:
        return False
    return abs(x - y) <= max(0.015, ROUNDING_REL * max(abs(x), abs(y)))


# ------------------------------------------------------------------ causes
def _is_ruled(row: Mapping[str, Any], coil: Mapping[str, Any], project: str) -> bool:
    ruled = RULED_ORDER_CHANGES.get((project, str(coil.get("tag") or "").upper(), row["ccsi_id"]))
    return bool(ruled) and same_value(row.get("coilforge"), ruled[0]) and same_value(row.get("ccsi"), ruled[1])


def mismatch_cause(row: Mapping[str, Any], coil: Mapping[str, Any], info: FieldInfo | None, *,
                   project: str = "") -> str:
    """Why a ``mismatch`` row disagrees (first rule that applies)."""
    ccsi_id = row["ccsi_id"]
    if _is_ruled(row, coil, project):
        return "ruled_order_change"
    flags = field_flags(coil.get("report_flags") or [], coil.get("coil_type") or "").get(ccsi_id, [])
    if any(f.startswith(_REPORT_UNPARSED_PREFIXES) or f == "parse_inconsistent" for f in flags):
        return "report_unparsed"
    if any(f.startswith("unmatched_option:") for f in flags):
        return "map_options_incomplete"
    code = row.get("reason_code")
    if code == "CCSI_GEOMETRY_RESELECT":
        return "reselect_predicted"
    # Before the default check: ACFM is now a default (Actual), and a Standard-air order is a known basis
    # difference, not a counterexample to that default.
    if _is_air_basis(row, coil):
        return "air_basis"
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


# The first coil-data push into CCSI (c44ca77, Step E). An order exported on or after it may echo
# what CoilForge pushed, so it is not independent evidence for anything CoilForge fills.
PUSH_START = date(2026, 9, 30)
# CCSI's export stamp in the report file name: `..._REV1_6_28_2026,11_24_38_PM.pdf` / `..._REV0_2026-06-05_...`
_STAMP_MDY = re.compile(r"_(\d{1,2})_(\d{1,2})_(\d{4}),")
_STAMP_ISO = re.compile(r"_(\d{4})-(\d{2})-(\d{2})")


def report_date(truth_file: Any) -> date | None:
    """The CCSI export date stamped in a report's file name (None = no readable stamp)."""
    name = str(truth_file or "")
    try:
        if m := _STAMP_MDY.search(name):
            return date(int(m[3]), int(m[1]), int(m[2]))
        if m := _STAMP_ISO.search(name):
            return date(int(m[1]), int(m[2]), int(m[3]))
    except ValueError:
        return None
    return None


def coil_tier(project: Mapping[str, Any], tag: str, calibration_keys: frozenset[tuple[str, str]]) -> str:
    if (str(project.get("project")), str(tag).upper()) in calibration_keys:
        return "calibration"
    if project.get("report_kind") != "order":
        return "quote_only"
    # Fail closed: an order with no readable export date may postdate the push.
    when = report_date(project.get("truth_file"))
    return "order" if when is not None and when < PUSH_START else "order_after_push"


def annotate(results: Iterable[Mapping[str, Any]], calibration_keys: frozenset[tuple[str, str]], *,
             field_info: FieldInfoLookup = map_field_info) -> list[dict[str, Any]]:
    """One flat row per compared field with tier, cause and defect flag (Tag excluded)."""
    out: list[dict[str, Any]] = []
    for project in results:
        when = report_date(project.get("truth_file"))
        for coil in project.get("coils", []):
            tier = coil_tier(project, coil.get("tag") or "", calibration_keys)
            reselect = any(r.get("reason_code") == "CCSI_GEOMETRY_RESELECT" for r in coil.get("rows", []))
            for row in coil.get("rows", []):
                if row.get("ccsi_id") == "Tag":
                    continue  # the pairing key; single_of_type pairing makes a mismatch expected
                info = field_info(coil["coil_type"], row["ccsi_id"])
                cause = (mismatch_cause(row, coil, info, project=str(project.get("project")))
                         if row.get("verdict") == "mismatch" else None)
                out.append({
                    "project": str(project.get("project")), "tag": coil.get("tag"), "coil_type": coil["coil_type"],
                    "tier": tier, "coil_reselect": reselect, "ccsi_id": row["ccsi_id"], "role": row.get("role"),
                    "verdict": row.get("verdict"), "reason_code": row.get("reason_code"),
                    "cause": cause, "counts_as_defect": bool(cause and CAUSES[cause]),
                    "coilforge": row.get("coilforge"), "ccsi": row.get("ccsi"), "rev0": row.get("rev0"),
                    "truth_file": project.get("truth_file"),
                    "source_key": row.get("source_key"), "reason": row.get("reason"),
                    "report_date": when.isoformat() if when else None,
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


# ------------------------------------------------------------------ estimate confirmation
# John 2026-10-12: an estimate is confirmed only when >=5 order projects match it and every
# counterexample is explained; a counterexample group that one push-time attribute separates cleanly
# (>=3 projects each side) becomes a conditional proposal for John, anything else is not confirmed.
CONFIRM_MIN_PROJECTS = 5
SPLIT_MIN_PROJECTS = 3
# coil_data_map.resolve_coil_data's reason on a substituted value; a test pins the coupling.
SUBSTITUTED_MARK = "sent in its place"
# Push-time attributes a condition may use (CoilForge's column — the order's is unknown at push time).
# Capacity, temperatures and GPM are left out on purpose: with only a handful of counterexamples a
# continuous rating value separates almost anything, which a prototype run showed.
SPLIT_CATEGORY_IDS: tuple[str, ...] = (
    "RowsDeep", "FinsPerInch", "NumberOfFeeds", "CoilQuantity", "CoilHand", "Refrigerant",
    "RefrigerationSystemType", "FinMaterial", "FinSurface", "TubeMaterial", "FluidType",
)
SPLIT_THRESHOLD_IDS: tuple[str, ...] = ("FinnedHeight", "FinnedLength", "TotalAirFlow")
_NO_EVIDENCE_CAUSES = frozenset({"report_unparsed", "reselect_predicted"})
# John's class-level rulings: a Standard-air order (2026-10-01) and an exact (project, tag, values) ruling.
_EXPLAINING_CAUSES = frozenset({"ruled_order_change", "air_basis"})


@dataclass(frozen=True)
class Estimate:
    """One value CoilForge fills by assumption, and which cross-check rows carry it."""

    key: str
    coil_type: str
    ccsi_id: str
    kind: str            # default | substitution | style_map | extra
    value: str           # what is assumed (the comparison target only for kind "extra")
    derived_from: str    # harvest | order+quote — how the value was chosen in the first place
    decided: str | None  # the date John approved it, when there is one
    select: Callable[[Mapping[str, Any]], bool]

    @property
    def evidence_basis(self) -> str:
        # Re-counting the orders a value was read off is a stricter re-count, not a new test.
        return "independent" if self.derived_from == "harvest" else "in_sample"


def _decided(evidence: str | None) -> str | None:
    found = re.search(r"\d{4}-\d{2}-\d{2}", evidence or "")
    return found.group(0) if found else None


def _option(row: Mapping[str, Any], text: str) -> bool:
    return isinstance(row.get("coilforge"), str) and option_key(row["coilforge"]) == option_key(text)


# Not in the maps: the 2026-10-02 decision table's Q5 (style text with no style_map entry) and Q9
# (a water submittal silent on fin surface). Both were read off orders, so both are in-sample.
EXTRA_ESTIMATES: tuple[Estimate, ...] = (
    Estimate("DX:RefrigerationSystemType=Intertwined (x2)", "DX", "RefrigerationSystemType", "extra",
             "Dual-Circuit Intertwined", "order+quote", None,
             lambda r: r.get("reason_code") == "CCSI_OPTION_UNMAPPED" and _option(r, "Intertwined (x2)")),
    Estimate("HGRH:RefrigerationSystemType=Face Split", "HGRH", "RefrigerationSystemType", "extra",
             "Dual-Circuit Face-Split", "order+quote", None,
             lambda r: r.get("reason_code") == "CCSI_OPTION_UNMAPPED" and _option(r, "Face Split")),
    *(Estimate(f"{t}:FinSurface=silent", t, "FinSurface", "extra", "Flat", "order+quote", None,
               lambda r: r.get("reason_code") == "CCSI_SOURCE_MISSING") for t in ("CWC", "HWC")),
)


def estimate_register(*, load: Callable[[str], Any] = load_coil_data_map) -> list[Estimate]:
    """Every assumed value in the four maps (defaults, substitutions, style maps) plus EXTRA_ESTIMATES.

    ACFM is left out: Actual is John's 2026-10-01 policy, and the only explanation a Standard order
    could get is ``air_basis`` — confirming the policy through its own exemption would be circular.
    """
    out: list[Estimate] = []
    for coil_type in ("DX", "HGRH", "CWC", "HWC"):
        for ccsi_id, entry in load(coil_type).fields.items():
            if ccsi_id == "ACFM":
                continue
            decided = _decided(entry.evidence)
            base = f"{coil_type}:{ccsi_id}"
            if entry.default is not None:
                harvest = (entry.evidence or "").startswith("D2 default profile")
                out.append(Estimate(f"{base}=default", coil_type, ccsi_id, "default", entry.default,
                                    "harvest" if harvest else "order+quote", decided,
                                    lambda r: r.get("reason_code") == "CCSI_DEFAULT_PROFILE"))
            if entry.substitutions:
                text = ", ".join(f"{k} -> {v}" for k, v in entry.substitutions.items())
                out.append(Estimate(f"{base}=substitution", coil_type, ccsi_id, "substitution", text,
                                    "order+quote", decided, lambda r: SUBSTITUTED_MARK in str(r.get("reason") or "")))
            if entry.style_map:
                text = ", ".join(f"{k} -> {v}" for k, v in entry.style_map.items())
                out.append(Estimate(f"{base}=style_map", coil_type, ccsi_id, "style_map", text, "order+quote", decided,
                                    lambda r, path=entry.style_path: (r.get("source_key") == path
                                                                      and r.get("reason_code") == "CCSI_OK")))
    return out + list(EXTRA_ESTIMATES)


def _attr_value(value: Any) -> Any:
    number = _number(value)
    if number is not None:
        return number
    return None if _blank(value) else option_key(value)


def coil_attributes(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Push-time attributes per (project, tag): CoilForge's column, the tag prefix, the export date."""
    out: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    for r in rows:
        attrs = out[(r["project"], str(r["tag"]))]
        if r["ccsi_id"] in SPLIT_CATEGORY_IDS or r["ccsi_id"] in SPLIT_THRESHOLD_IDS:
            attrs[r["ccsi_id"]] = _attr_value(r["coilforge"])
        prefix = re.match(r"[A-Za-z]+", str(r["tag"] or ""))
        attrs["tag_prefix"] = prefix.group(0).upper() if prefix else None
        attrs["coil_reselect"] = bool(r.get("coil_reselect"))
        when = r.get("report_date")
        attrs["report_date"] = date.fromisoformat(when).toordinal() if when else None
    return dict(out)


def _bound(op: str, value: Any, name: str) -> str:
    return f"{op} {date.fromordinal(int(value)).isoformat() if name == 'report_date' else value}"


def pure_splits(bad: Iterable[tuple[str, str]], good: Iterable[tuple[str, str]],
                attrs: Mapping[tuple[str, str], Mapping[str, Any]], *, skip: str = "") -> list[dict[str, Any]]:
    """Single push-time attributes that separate the counterexample coils from the matching ones."""
    bad, good = list(bad), list(good)
    out: list[dict[str, Any]] = []
    for name in (*SPLIT_CATEGORY_IDS, "tag_prefix", "coil_reselect", *SPLIT_THRESHOLD_IDS, "report_date"):
        if name == skip:
            continue
        bad_vals = [attrs.get(c, {}).get(name) for c in bad]
        if any(v is None for v in bad_vals):
            continue  # a counterexample with the attribute unknown rules the attribute out
        known_good = [c for c in good if attrs.get(c, {}).get(name) is not None]
        if len({p for p, _ in bad}) < SPLIT_MIN_PROJECTS or len({p for p, _ in known_good}) < SPLIT_MIN_PROJECTS:
            continue
        good_vals = [attrs[c][name] for c in known_good]
        if name in SPLIT_THRESHOLD_IDS or name == "report_date":
            lows = [v for v in bad_vals if isinstance(v, (int, float))]
            highs = [v for v in good_vals if isinstance(v, (int, float))]
            if len(lows) != len(bad_vals) or len(highs) != len(good_vals):
                continue  # a value that is not a number cannot sit on either side of a threshold
            if max(lows) < min(highs):
                out.append({"attribute": name, "kind": "threshold",
                            "bad": _bound("<=", max(lows), name), "good": _bound(">=", min(highs), name)})
            elif min(lows) > max(highs):
                out.append({"attribute": name, "kind": "threshold",
                            "bad": _bound(">=", min(lows), name), "good": _bound("<=", max(highs), name)})
        elif not set(map(str, bad_vals)) & set(map(str, good_vals)):
            out.append({"attribute": name, "kind": "category",
                        "bad": sorted(set(map(str, bad_vals))), "good": sorted(set(map(str, good_vals)))})
    for split in out:
        split["ambiguous"] = len(out) > 1
    return out


def _near_zero(value: Any) -> bool:
    number = _number(value)
    return number is not None and abs(number) < 0.015


def _same(a: Any, b: Any) -> bool:
    """same_value, except around zero: its 0.01 absolute tolerance would call a 0.001 fouling factor 0."""
    if _near_zero(a) or _near_zero(b):
        return _number(a) == _number(b)
    return same_value(a, b)


def _explanation(row: Mapping[str, Any], target: Any) -> str | None:
    """Why an order disagreeing with the estimate is not a counterexample to it (None = it is)."""
    if row.get("cause") in _EXPLAINING_CAUSES:
        return row["cause"]
    if not _blank(row.get("rev0")) and _same(row["rev0"], target):
        return "changed_at_order"  # the quote used the estimate; the order changed it
    # mismatch_cause returns default_counterexample before its rounding check, so recompute here — but
    # never around zero, where "0.015 apart" would wave through a real fouling factor.
    if not (_near_zero(target) or _near_zero(row.get("ccsi"))) and _within_rounding(target, row.get("ccsi")):
        return "rounding"
    return None


def _group_key(value: Any) -> str:
    number = _number(value)
    return str(number) if number is not None else option_key(value)


def evaluate_estimates(rows: Iterable[Mapping[str, Any]], register: Iterable[Estimate], *,
                       field_info: FieldInfoLookup = map_field_info) -> dict[str, dict[str, Any]]:
    """Per estimate: strict confirmation against orders exported before PUSH_START (proposals only)."""
    rows = list(rows)
    attrs = coil_attributes(rows)
    by_field: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for r in rows:
        by_field[(r["coil_type"], r["ccsi_id"])].append(r)
    out: dict[str, dict[str, Any]] = {}
    for est in register:
        mine = [r for r in by_field.get((est.coil_type, est.ccsi_id), []) if est.select(r)]
        printed = [r for r in mine if r["verdict"] != "absent_on_form" and not _blank(r["ccsi"])]

        def target(r: Mapping[str, Any], est: Estimate = est) -> Any:
            # The value actually pushed ("Aluminum 0.008", not the map's "0.008"); an extra estimate
            # was never pushed, so its own value is the claim under test.
            return est.value if est.kind == "extra" else r["coilforge"]

        matches: list[Mapping[str, Any]] = []
        unexplained: list[Mapping[str, Any]] = []
        explained: Counter = Counter()
        excluded: Counter = Counter()
        for r in printed:
            if r["tier"] != "order":
                continue
            if r.get("cause") in _NO_EVIDENCE_CAUSES:
                excluded[r["cause"]] += 1
            elif _same(r["ccsi"], target(r)):
                matches.append(r)
            elif r.get("cause") == "map_options_incomplete":
                unexplained.append(r)  # an order value the map cannot even express blocks, never hides
            elif why := _explanation(r, target(r)):
                explained[why] += 1
            else:
                unexplained.append(r)
        excluded["order_after_push"] = sum(r["tier"] == "order_after_push" for r in mine)
        excluded["not_printed"] = len(mine) - len(printed)
        match_projects = {r["project"] for r in matches}

        groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for r in unexplained:
            groups[_group_key(r["ccsi"])].append(r)
        good = sorted({(r["project"], str(r["tag"])) for r in matches})
        splits = {value: pure_splits({(r["project"], str(r["tag"])) for r in group}, good, attrs, skip=est.ccsi_id)
                  for value, group in groups.items()}
        if not printed:
            verdict = "untestable_not_printed"
        elif not unexplained:
            verdict = "confirm_candidate" if len(match_projects) >= CONFIRM_MIN_PROJECTS else "insufficient_projects"
        elif all(splits.values()):
            dated = all(all(s["attribute"] == "report_date" for s in found) for found in splits.values())
            verdict = "superseded_candidate" if dated else "conditional_candidate"
        else:
            verdict = "not_confirmed_unexplained"
        info = field_info(est.coil_type, est.ccsi_id)
        # After the push only a disagreement is evidence (an engineer changed the value); agreement may be an echo.
        contradicted = [r for r in printed if r["tier"] == "order_after_push" and not _same(r["ccsi"], target(r))]
        if info is not None and info.mapping_status == "confirmed" and contradicted:
            verdict = "confirmed_contradicted"
        holdout = None
        if est.evidence_basis == "independent":
            quotes = [r for r in printed if r["tier"] == "quote_only"
                      and (r.get("report_date") or "9999") < PUSH_START.isoformat()]
            same = [_same(r["ccsi"], target(r)) for r in quotes]
            holdout = {"match": sum(same), "differ": len(same) - sum(same)}
        out[est.key] = {
            "coil_type": est.coil_type, "ccsi_id": est.ccsi_id, "kind": est.kind, "value": est.value,
            "derived_from": est.derived_from, "decided": est.decided, "evidence_basis": est.evidence_basis,
            "verdict": verdict, "order_projects": len(match_projects), "order_coils": len(matches),
            "explained": dict(explained), "excluded": {k: v for k, v in excluded.items() if v},
            "unexplained": [{"project": r["project"], "tag": r["tag"], "coilforge": r["coilforge"],
                             "order": r["ccsi"], "rev0": r["rev0"], "report_date": r.get("report_date"),
                             "cause": r.get("cause")} for r in unexplained],
            "splits": splits, "holdout": holdout,
            "contradicted": [{"project": r["project"], "tag": r["tag"], "order": r["ccsi"]} for r in contradicted],
        }
    return out
