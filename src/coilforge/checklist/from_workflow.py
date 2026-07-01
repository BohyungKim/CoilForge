"""Adapter: submittal candidates -> checklist coil-input dicts.

Bridges the PDF/submittal workflow output (a list of ``SubmittalCoilCandidate``
model-dumps) to the plain coil-input dicts ``mapping.build_checklist_fill``
consumes. Product line + unit size come from one ``detect_product_and_size`` pass
over the submittal text (all coils in a unit share it) unless explicitly
overridden. Defensive: a missing field becomes ``None`` (flagged downstream),
never invented.
"""
from __future__ import annotations

from typing import Any

# Coil-category long name (from the tag prefix) -> the engine/checklist short code.
_CATEGORY_CODE = {
    "DX COIL": "DX",
    "HGRH COIL": "HGRH",
    "Chilled Water Coil": "CWC",
    "Hot Water Coil": "HWC",
}


def _fv(node: Any) -> Any:
    """Unwrap a FieldValue-shaped dict ({'value': ...}) or pass a bare value through."""
    if isinstance(node, dict) and "value" in node:
        return node["value"]
    return node


def _g(group: dict[str, Any] | None, *keys: str) -> Any:
    """First non-None value among ``keys`` in a candidate group dict."""
    if not isinstance(group, dict):
        return None
    for key in keys:
        if key in group:
            v = _fv(group[key])
            if v not in (None, ""):
                return v
    return None


def coil_inputs_from_candidates(
    candidates: list[dict[str, Any]],
    *,
    pdf_text: str = "",
    product_line: str | None = None,
    unit_size: str | None = None,
) -> tuple[list[dict[str, Any]], tuple[str | None, str | None]]:
    """Build coil-input dicts from candidate model-dumps.

    ``product_line``/``unit_size`` override the auto-detection (e.g. when the
    engineer picked them in the UI). Returns ``(coils, (product_line, unit_size))``.
    """
    from coilforge.submittal.coilmaster_drawing_extract import detect_product_and_size
    from coilforge.submittal.pdf_intake import coil_category_of_tag

    if not (product_line and unit_size):
        det_line, det_size = detect_product_and_size(pdf_text or "")
        product_line = product_line or det_line
        unit_size = unit_size or det_size

    coils: list[dict[str, Any]] = []
    for cand in candidates:
        tag = _fv(cand.get("tag"))
        category = _CATEGORY_CODE.get(coil_category_of_tag(tag or "") or "")
        if not category:
            continue  # unknown category -> no checklist sheet (mapping warns)
        geom = cand.get("geometry") or {}
        conn = cand.get("connections") or {}
        mfg = cand.get("manufacturing_options") or {}
        coils.append(
            {
                "tag": tag,
                "coil_type": category,
                "product_label": product_line,
                "unit_size": unit_size,
                "quantity": _fv(cand.get("quantity")),
                "finned_height": _g(geom, "finned_height"),
                "finned_length": _g(geom, "finned_length"),
                "rows": _g(geom, "rows_deep", "rows"),
                "feeds": _g(geom, "number_of_feeds"),
                "circuits": _g(geom, "circuits", "number_of_circuits", "num_circuits"),
                # DX suction line is the return/suction connection; water coils use in/out.
                "suction_conn_size": _g(conn, "suction_connection_size",
                                        "return_connection_size", "supply_connection_size"),
                "conn_size": _g(conn, "return_connection_size", "connection_size"),
                "inlet_conn_size": _g(conn, "inlet_connection_size", "supply_connection_size"),
                "outlet_conn_size": _g(conn, "outlet_connection_size", "return_connection_size"),
                "qty_conn_per_header": _g(conn, "qty_connections_per_header"),
                "coil_hand": _g(conn, "coil_hand"),
                "coating": _g(mfg, "coil_coating"),
            }
        )
    return coils, (product_line, unit_size)
