"""Adapter: submittal candidates -> checklist coil-input dicts.

Bridges the PDF/submittal workflow output (a list of ``SubmittalCoilCandidate``
model-dumps) to the plain coil-input dicts ``mapping.build_checklist_fill``
consumes. Product line + unit size are detected **per coil** from each candidate's
own cover model-code note (one submittal can carry several distinct units), falling
back to a drain-pan partner's product, then to a whole-PDF detection. An explicit
``product_line``/``unit_size`` argument overrides all detection. Defensive: a
missing field becomes ``None`` (flagged downstream), never invented.
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


def _candidate_model_text(cand: dict[str, Any], tag: Any) -> str:
    """Tag + this candidate's notes (which carry 'Cover product/model code: ...') —
    the same text basis the drawing's per-coil detection uses."""
    parts = [str(tag or "")]
    parts += [str(n) for n in (cand.get("notes") or [])]
    return " ".join(p for p in parts if p)


def coil_inputs_from_candidates(
    candidates: list[dict[str, Any]],
    *,
    pdf_text: str = "",
    product_line: str | None = None,
    unit_size: str | None = None,
) -> tuple[list[dict[str, Any]], tuple[str | None, str | None]]:
    """Build coil-input dicts from candidate model-dumps.

    Product/size are detected PER COIL (own model code -> drain-pan partner ->
    whole-PDF). An explicit ``product_line``/``unit_size`` overrides all detection
    for every coil. Returns ``(coils, (whole_pdf_line, whole_pdf_size))`` — the
    second element is the fallback/override pair, for logging.
    """
    from coilforge.submittal.coilmaster_drawing_extract import detect_product_and_size
    from coilforge.submittal.pdf_intake import coil_category_of_tag, drain_pan_partner_tag

    override = bool(product_line and unit_size)
    global_line, global_size = product_line, unit_size
    if not override:
        det_line, det_size = detect_product_and_size(pdf_text or "")
        global_line = global_line or det_line
        global_size = global_size or det_size

    # Per-coil own detection first (from each candidate's own model-code note).
    all_tags = [t for t in (_fv(c.get("tag")) for c in candidates) if t]
    own: dict[Any, tuple[str | None, str | None]] = {}
    for cand in candidates:
        tag = _fv(cand.get("tag"))
        if not tag:
            continue
        own[tag] = (
            (product_line, unit_size)
            if override
            else detect_product_and_size(_candidate_model_text(cand, tag))
        )

    def resolve(tag: Any) -> tuple[str | None, str | None]:
        line, size = own.get(tag, (None, None))
        if not (line and size) and not override:
            # inherit a reheat/partner coil's product from its drain-pan partner
            partner = drain_pan_partner_tag(tag, all_tags) if tag else None
            if partner and all(own.get(partner, (None, None))):
                line, size = own[partner]
        return (line or global_line, size or global_size)

    coils: list[dict[str, Any]] = []
    for cand in candidates:
        tag = _fv(cand.get("tag"))
        category = _CATEGORY_CODE.get(coil_category_of_tag(tag or "") or "")
        if not category:
            continue  # unknown category -> no checklist sheet (mapping warns)
        line, size = resolve(tag)
        geom = cand.get("geometry") or {}
        conn = cand.get("connections") or {}
        mfg = cand.get("manufacturing_options") or {}
        coils.append(
            {
                "tag": tag,
                "coil_type": category,
                "product_label": line,
                "unit_size": size,
                "quantity": _fv(cand.get("quantity")),
                "finned_height": _g(geom, "finned_height"),
                "finned_length": _g(geom, "finned_length"),
                "rows": _g(geom, "rows_deep", "rows"),
                "feeds": _g(geom, "number_of_feeds"),
                # circuits count for the drawing distributor math = the CoilMaster
                # prose circuit count if present, else QTY CONN/HEADER (the count the
                # checklist's own S/R/CD formulas key on — John 2026-07-01).
                "circuits": (
                    _g(geom, "circuits", "number_of_circuits", "num_circuits")
                    or _g(conn, "qty_connections_per_header")
                ),
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
    return coils, (global_line, global_size)
