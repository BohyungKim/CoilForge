"""Offline CCSI-export audit — run the green/red compare from a downloaded CCSI
report PDF instead of a live DOM read.

The live `/ccsi-compare` path (`ccsi/compare.py`) needs the CCSI page open and a
browser session scraping its form, because a localhost page cannot read across
origins into ``coil.ccsi.ie``. But a CCSI export IS a CoilMaster EZ-Coil drawing,
so ``run_pdf_to_drawing_workflow`` already parses CCSI's printed dimensions into
each coil's ``template_drawing.slot_sources[slot]["as_built"]`` while resolving
CoilForge's own engine values into the panel (``drawing_parameter_set.parameters``).
Both sides fall out of the SAME workflow pass.

This module is the thin reshape that pairs them: for each audited CCSI field-map
key it takes the engine value (CoilForge side) and the printed as-built value
(CCSI side) and hands ``[{key, coilforge, ccsi}]`` to ``compare_ccsi_fields`` —
the exact comparator (tol 0.01) the live path uses, so the offline surface can
never drift from the live one. Pure; no I/O, no network, no browser.

Review aid only: a key CCSI's drawing did not print stays ``missing_one`` (never
guessed), and the comparator stamps ``export_allowed: False``.
"""

from __future__ import annotations

import re
from typing import Any

from coilforge.ccsi.compare import compare_ccsi_fields
from coilforge.services.drawing_param_resolver import PARAM_TO_SLOT, _header_slot

# A logical header-2+ drawing-parameter key, e.g. "I2", "O3", "HD2", "ZD3". Base
# keys (I/S/O/R/HD) carry no digit and fall through to PARAM_TO_SLOT below.
_MULTI_HEADER_KEY_RE = re.compile(r"^(I|S|O|R|HD|ZD)(\d+)$")


def _slot_for_key(key: str) -> str | None:
    """Template slot whose printed as-built value corresponds to a CCSI field-map key.

    Base keys map via ``PARAM_TO_SLOT`` (I -> slot.I1, R -> slot.R2, ...). Logical
    header-2+ keys (I2/O3/...) map through the parity bridge (``_header_slot``), the
    single place the logical<->parity seam lives. ``ZD``/``ZD{n}`` are the owner-fixed
    constant with no slot and are never printed on the drawing -> None (so their CCSI
    side reads absent -> ``missing_one``, never a false green).
    """
    match = _MULTI_HEADER_KEY_RE.match(key)
    if match:
        base, index = match.group(1), int(match.group(2))
        if base == "ZD":
            return None
        return _header_slot(base, index)
    return PARAM_TO_SLOT.get(key)


def _coil_category(workflow: dict[str, Any]) -> str | None:
    ctx = workflow.get("template_header_context") or {}
    if ctx.get("coil_category"):
        return ctx["coil_category"]
    extracted = (workflow.get("template_drawing") or {}).get("extracted") or {}
    return extracted.get("coil_category")


def audit_coil(page: dict[str, Any], field_map: dict[str, Any]) -> dict[str, Any]:
    """Audit ONE coil page: pair its engine values (CoilForge) with the CCSI-drawing
    printed as-built values, per audited key, and run the shared comparator.

    ``page`` is one ``pdf_coil_pages`` entry from ``run_pdf_to_drawing_workflow``;
    ``field_map`` is the parsed ``ccsi_dx_field_map.json``. Returns the comparator
    report plus the coil's ``tag`` / ``coil_category`` so a multi-coil roll-up can
    name every coil.
    """
    workflow = page.get("workflow") or {}
    parameters = (workflow.get("drawing_parameter_set") or {}).get("parameters") or {}
    slot_sources = (workflow.get("template_drawing") or {}).get("slot_sources") or {}

    fields: list[dict[str, Any]] = []
    for key in (field_map.get("fields") or {}):
        # CoilForge side = the panel value the live compare also uses.
        coilforge = (parameters.get(key) or {}).get("value")
        # CCSI side = the value CCSI printed on its drawing (parsed as-built), or None
        # when this dimension isn't a printed callout (-> missing_one, never guessed).
        slot = _slot_for_key(key)
        ccsi = (slot_sources.get(slot) or {}).get("as_built") if slot else None
        fields.append({"key": key, "coilforge": coilforge, "ccsi": ccsi})

    report = compare_ccsi_fields(fields)
    report["tag"] = page.get("tag")
    report["coil_category"] = _coil_category(workflow)
    return report


def audit_export_result(
    workflow_result: dict[str, Any], field_map: dict[str, Any]
) -> list[dict[str, Any]]:
    """Audit every coil in a ``run_pdf_to_drawing_workflow`` result against the CCSI
    field map. Returns one per-coil report (green/red verdicts + mismatch count),
    tagged so no coil is silently dropped. Empty list when the PDF yielded no coils.
    """
    pages = (workflow_result or {}).get("pdf_coil_pages") or []
    return [audit_coil(page, field_map) for page in pages]
