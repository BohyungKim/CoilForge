"""Cross-check a harvested CCSI coil form against CoilForge's submittal extraction.

The harvest (``web/ccsi/ccsi_harvest_snippet.js``) is a read-only dump of every field
on a past CCSI selection. For the same ``(project, tag)``, CoilForge's draft values go
through the mapping contract (``coil_data_map.resolve_coil_data``) and each CCSI field
gets one verdict:

* ``match`` / ``mismatch`` — both sides have a value (numbers via the shared
  ``checklist.compare._match``; computed quantities get a 1% relative band).
* ``off_vocabulary`` — the submittal value has no exact CCSI option.
* ``submittal_missing`` — CCSI has a value, CoilForge has none (or it is blocked).
* ``ccsi_blank`` — CoilForge has a value, the saved CCSI form leaves it blank (e.g. GPM, which
  CCSI derives from EWT/LWT when left empty).
* ``unmapped_ccsi_field`` — a CCSI field the map does not know, or knows without a source.
* ``not_persisted`` — a computed field the saved form holds as blank/zero.
* ``both_missing`` / ``absent_on_form`` — nothing to compare / map field not on this form.

Pure. The verdicts are the collection John reviews; nothing is corrected here.
"""
from __future__ import annotations

from typing import Any, Literal, Mapping

from coilforge.ccsi.coil_data_map import (
    CcsiCoilDataMap,
    CoilDataPushEntry,
    load_coil_data_map,
    resolve_coil_data,
)
from coilforge.checklist.compare import _match

Verdict = Literal[
    "match",
    "mismatch",
    "off_vocabulary",
    "submittal_missing",
    "ccsi_blank",
    "unmapped_ccsi_field",
    "not_persisted",
    "both_missing",
    "absent_on_form",
]

_COMPUTED_REL_TOL = 0.01
# Form furniture that is never coil data (3-D viewer toggles, distributor modal).
_IGNORED_IDS = frozenset(
    {"coilStepViewerShowEdges", "coilStepViewerUseModelColors", "modal_DXDistCircuitDraining", "modal_DXDistCycleValve"}
)


def map_for(coil_type: str) -> CcsiCoilDataMap | None:
    try:
        return load_coil_data_map(coil_type)
    except FileNotFoundError:
        return None


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _verdict(entry: CoilDataPushEntry, kind: str, ccsi_value: Any) -> Verdict:
    if entry.value is None:
        if entry.reason_code in ("CCSI_OPTION_UNMAPPED", "CCSI_VALUE_UNPARSEABLE"):
            return "off_vocabulary"
        if entry.reason_code == "CCSI_NO_SOURCE":
            return "unmapped_ccsi_field"
        return "both_missing" if _blank(ccsi_value) else "submittal_missing"
    if entry.role == "computed" and (
        _blank(ccsi_value) or _match(ccsi_value, 0) == "match" or str(ccsi_value).strip().casefold() == "calculate"
    ):
        return "not_persisted"
    if kind == "select" or entry.source_key == "tag":
        same = str(entry.value).strip().casefold() == str(ccsi_value or "").strip().casefold()
        return "match" if same else "mismatch"
    rel = _COMPUTED_REL_TOL if entry.role == "computed" else None
    result = _match(entry.value, ccsi_value, rel_tol=rel)
    if result == "missing_one":
        return "ccsi_blank" if _blank(ccsi_value) else "submittal_missing"
    return "match" if result == "match" else ("both_missing" if result == "both_missing" else "mismatch")


def crosscheck_coil(
    harvest: Mapping[str, Any],
    sources: Mapping[str, Any],
    *,
    coil_type: str,
    ignore_ids: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """One row per CCSI field (harvested or mapped) with its verdict and both values."""
    form: Mapping[str, Mapping[str, Any]] = harvest.get("fields") or {}
    cmap = map_for(coil_type)
    resolved = {e.ccsi_id: e for e in resolve_coil_data(sources, coil_type=coil_type)} if cmap else {}
    rows: list[dict[str, Any]] = []
    for ccsi_id, entry in resolved.items():
        if ccsi_id not in form:
            rows.append(_row(ccsi_id, entry.ccsi_label, entry.role, entry.source_key, entry.value, None, "absent_on_form",
                             entry.reason, entry.reason_code))
            continue
        field = form[ccsi_id]
        verdict = _verdict(entry, str(field.get("kind")), field.get("value"))
        rows.append(_row(ccsi_id, entry.ccsi_label, entry.role, entry.source_key,
                         entry.value if entry.value is not None else entry.source_value,
                         field.get("value"), verdict, entry.reason, entry.reason_code))
    for ccsi_id, field in form.items():
        if ccsi_id in resolved or ccsi_id in _IGNORED_IDS or ccsi_id in ignore_ids:
            continue
        rows.append(_row(ccsi_id, field.get("label"), None, None, None, field.get("value"),
                         "unmapped_ccsi_field", "CCSI field not in the CoilForge coil-data map"))
    return rows


def _row(ccsi_id: str, label: Any, role: Any, source_key: Any, coilforge: Any, ccsi: Any,
         verdict: Verdict, reason: str, reason_code: str | None = None) -> dict[str, Any]:
    # reason_code separates a default-profile or re-selection verdict from one on an extracted value.
    return {"ccsi_id": ccsi_id, "label": label, "role": role, "source_key": source_key,
            "coilforge": coilforge, "ccsi": ccsi, "verdict": verdict, "reason": reason, "reason_code": reason_code}
