"""Pure mapping: submittal coils -> ``ChecklistFill`` (no Excel, no I/O).

Projects each coil's submittal-extracted header values and engine-resolved
dimensions onto its category sheet's column-C fields, encoding the business rules
John specified (sheet selection/rename, W/HGRH pairing, HGRH conn size from the
paired reheat coil, collared-holes-on / stacking-flanges-off, deterministic
APPLICATION for DX/HGRH/CWC, coating default NONE, UNIT/SIZE token translation).

Reuses the SAME engine path the drawing + mechanical-fit use
(``build_drawing_slots`` -> ``prepopulate``) for casing W/H and the lower dims, so
the checklist faithfully mirrors what CoilForge draws. It never invents a value:
an unresolved field is left blank (``value=None``) and flagged, never guessed.
"""
from __future__ import annotations

import re
from typing import Any

from coilforge.checklist.model import CellFill, ChecklistFill, DimCompare, SheetFill
from coilforge.checklist import template_map as T

# --------------------------------------------------------------------------- #
# Normalizers
# --------------------------------------------------------------------------- #
def _to_unit(product_label: str | None) -> str | None:
    if not product_label:
        return None
    return T.UNIT_BY_PRODUCT.get(str(product_label).strip().upper()) or T.UNIT_BY_PRODUCT.get(
        str(product_label).strip()
    )


def _to_size(unit: str | None, size_token: str | None) -> Any:
    """CoilForge R-076 token -> the checklist SIZE dropdown value, per UNIT.

    NOVA / VENTUM identity; TERRA H '009' -> 9 (numeric); TERRA V '084' -> 'TV084'.
    Returns None if it cannot be matched to a dropdown option (caller flags it).
    """
    if not unit or size_token in (None, ""):
        return None
    token = str(size_token).strip()
    if unit == "TERRA H":
        try:
            n = int(token)
        except ValueError:
            return None
        return n if n in T.SIZE_OPTIONS["TERRA H"] else None
    if unit == "TERRA V":
        try:
            cand = f"TV{int(token):03d}"
        except ValueError:
            cand = token.upper()
        return cand if cand in T.SIZE_OPTIONS["TERRA V"] else None
    opts = T.SIZE_OPTIONS.get(unit, ())
    return token if token in opts else None


def _to_handing(coil_hand: Any) -> str | None:
    if coil_hand in (None, ""):
        return None
    h = str(coil_hand).strip().upper()
    if h in ("LH", "L", "LEFT"):
        return "LH"
    if h in ("RH", "R", "RIGHT"):
        return "RH"
    return None


def _to_coating(coil_coating: Any) -> tuple[str, str]:
    """Return (value, status). Default NONE; pass a recognized special coating through."""
    if coil_coating in (None, "", "NONE", "STANDARD", "STD"):
        return T.COATING_DEFAULT, "constant"
    c = str(coil_coating).strip().upper()
    for opt in T.COATING_OPTIONS:
        if opt.upper() == c:
            return opt, "review_required"
    # Unrecognized coating string — surface it for review rather than dropping it.
    return str(coil_coating).strip(), "review_required"


# --------------------------------------------------------------------------- #
# Dimension label -> engine slot
# --------------------------------------------------------------------------- #
_DIM_BASE = {
    "CD": "slot.CD", "HF": "slot.HF", "RF": "slot.RF", "TF": "slot.TF",
    "BF": "slot.BF", "RB": "slot.RB", "OAL": "slot.OAL", "CH": "slot.CH",
    "DIST EXTENTION": "slot.DIST_EXT",
}
_DIM_NUM = re.compile(r"^(O|R|HD|SL|S|I)(\d+)$")


def _dim_slot(label: str) -> str | None:
    """Map a checklist dim label to the engine slot key it mirrors (or None)."""
    lab = T.normalize_label(label)
    if lab in _DIM_BASE:
        return _DIM_BASE[lab]
    if lab == "I/O":
        return "slot.O2"
    if lab == "HD":
        return "slot.HD2"
    if lab == "SL":
        return "slot.SL2"
    m = _DIM_NUM.match(lab)
    if m:
        pfx, n = m.group(1), int(m.group(2))
        if pfx == "HD":  # even id = return header HD; odd id = distributor HDx
            return f"slot.HD{n}" if n % 2 == 0 else f"slot.HDx{n}"
        return f"slot.{pfx}{n}"
    return None  # DIST ORIENTATION, ASC ORIENTATION — no engine source


def _circuit_index(label: str) -> int | None:
    """For a circuit-indexed dim (I1/S3/O2/R4/HD2/SL2...), the 1-based circuit k."""
    m = _DIM_NUM.match(T.normalize_label(label))
    if not m:
        return None
    n = int(m.group(2))
    return (n + 1) // 2  # supply odd id 2k-1 and return even id 2k both -> k


# --------------------------------------------------------------------------- #
# Engine resolution (same path as mechanical_fit.build_coil_fit)
# --------------------------------------------------------------------------- #
def _resolve_engine(coil: dict[str, Any], application: str | None) -> tuple[dict[str, Any], Any]:
    """Run the slot layer (dims) + an application-aware engine pass (casing) for one coil.

    Returns ``(slots, response)`` where ``slots`` carries the drawing dims and
    ``response`` is the prepopulate run WITH ``application`` set, so casing W/H
    (R-074, keyed on product|application|size) resolve like ``mechanical_fit``.
    Returns ({}, None) when product line / unit size are unknown or the engine
    raises — the caller then leaves casing/dims blank and flags them.
    """
    from coilforge.services.direct_coil_drawing_pipeline import (
        build_drawing_slots,
        build_header_request,
    )
    from coilforge.services.header_prepopulate_engine import prepopulate

    product = coil.get("product_label") or coil.get("product_type")
    unit_size = coil.get("unit_size") or coil.get("unit_size_token")
    coil_type = coil.get("coil_type")
    if not (product and unit_size and coil_type):
        return {}, None
    common = dict(
        coil_type=coil_type, product_type=product, unit_size=unit_size,
        rows=coil.get("rows"), feeds=coil.get("feeds"), circuits=coil.get("circuits"),
        suction_conn_size=coil.get("suction_conn_size"), conn_size=coil.get("conn_size"),
        qty_conn_per_header=coil.get("qty_conn_per_header"),
    )
    try:
        slots, _ = build_drawing_slots(
            finned_height=coil.get("finned_height"),
            finned_length=coil.get("finned_length"),
            tag=coil.get("tag"), **common,
        )
        request = build_header_request(**common)
        if application:
            request = request.model_copy(update={"application": application})
        response = prepopulate(request)
        return slots, response
    except Exception:  # noqa: BLE001 — never raise into the fill; flag instead
        return {}, None


def _engine_value(response: Any, field: str) -> Any:
    if response is None:
        return None
    if field in response.values:
        return response.values[field].value
    if field in response.suggestions:
        return response.suggestions[field].value
    return None


# --------------------------------------------------------------------------- #
# Cell builders
# --------------------------------------------------------------------------- #
def _passthrough(label: str, value: Any, src_field: str, kind: str = "number") -> CellFill:
    if value in (None, ""):
        return CellFill(label, None, kind, "blocked", f"submittal:{src_field}",
                        note=f"{src_field} absent from submittal")
    return CellFill(label, value, kind, "ready", f"submittal:{src_field}")


def _category_of(coil: dict[str, Any]) -> str:
    ct = str(coil.get("coil_type") or "").strip().upper()
    return ct if ct in T.CATEGORY_SHEET else ct


def _partner(coil: dict[str, Any], coils: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The drain-pan partner coil (DX<->HGRH / CWC<->HWC) by same tag number."""
    from coilforge.submittal.pdf_intake import drain_pan_partner_tag

    tag = coil.get("tag")
    if not tag:
        return None
    all_tags = [c.get("tag") for c in coils if c.get("tag")]
    partner_tag = drain_pan_partner_tag(tag, all_tags)
    if not partner_tag:
        return None
    return next((c for c in coils if c.get("tag") == partner_tag), None)


def _build_sheet(coil: dict[str, Any], coils: list[dict[str, Any]]) -> tuple[SheetFill, list[str]]:
    category = _category_of(coil)
    spec = T.SHEET_LABELS[category]
    warnings: list[str] = []
    cells: list[CellFill] = []
    tag = coil.get("tag") or category

    # Resolve UNIT + APPLICATION first: APPLICATION feeds the engine so casing
    # W/H (R-074, product|application|size) can resolve.
    unit = _to_unit(coil.get("product_label") or coil.get("product_type"))
    if category == "HWC":
        application = coil.get("application")
    else:
        application = T.APPLICATION_FIXED.get(unit or "")
    slots, response = _resolve_engine(coil, application)
    engine_ok = response is not None
    # The comparison's CoilForge column is resolved with the checklist's OWN product
    # (apples-to-apples with the sheet's formulas). We deliberately do NOT reuse the
    # per-coil drawing slot_values: the drawing's per-coil product detection can
    # diverge (e.g. one coil mis-read as NOVA), which would pollute the comparison.
    dim_slots = slots

    # --- UNIT / SIZE (detected) ---
    if unit:
        cells.append(CellFill("UNIT", unit, "dropdown", "detected", "detected:product_line"))
    else:
        cells.append(CellFill("UNIT", None, "dropdown", "blocked", "detected:product_line",
                              note="product line not detected — pick UNIT manually"))
        warnings.append(f"{tag}: UNIT not detected")
    size = _to_size(unit, coil.get("unit_size") or coil.get("unit_size_token"))
    if size is not None:
        cells.append(CellFill("SIZE", size, "dropdown", "detected", "detected:unit_size"))
    else:
        cells.append(CellFill("SIZE", None, "dropdown", "blocked", "detected:unit_size",
                              note="unit size not detected/validated — pick SIZE manually"))
        warnings.append(f"{tag}: SIZE not detected")

    # --- APPLICATION ---
    if category == "HWC":
        app = coil.get("application")
        if app:
            cells.append(CellFill("APPLICATION", app, "dropdown", "review_required",
                                  "submittal:application"))
        else:
            cells.append(CellFill("APPLICATION", None, "dropdown", "blocked",
                                  "submittal:application",
                                  note="HWC application has multiple options — choose manually"))
            warnings.append(f"{tag}: HWC APPLICATION needs a choice "
                            f"({', '.join(T.APPLICATION_HWC_OPTIONS.get(unit or '', ()))})")
    else:
        app = T.APPLICATION_FIXED.get(unit or "")
        if app:
            cells.append(CellFill("APPLICATION", app, "dropdown", "constant",
                                  "constant:application_fixed"))
        elif unit:
            cells.append(CellFill("APPLICATION", None, "dropdown", "blocked",
                                  "constant:application_fixed",
                                  note=f"no fixed application for {unit}"))

    # --- W/ HGRH + HOT GAS BYPASS (DX only special header) ---
    if category == "DX":
        partner = _partner(coil, coils)
        with_hgrh = bool(partner and _category_of(partner) == "HGRH")
        cells.append(CellFill("W/ HGRH", with_hgrh, "bool", "ready", "derived:partner_tag"))
        hgbp = bool(coil.get("hot_gas_bypass"))
        cells.append(CellFill("HOT GAS BYPASS", hgbp, "bool",
                              "ready" if "hot_gas_bypass" in coil else "constant",
                              "submittal:hot_gas_bypass"))

    # --- COATING ---
    coat_value, coat_status = _to_coating(coil.get("coating"))
    cells.append(CellFill("COATING", coat_value, "dropdown", coat_status, "submittal:coil_coating"))

    # --- CASING WIDTH / HEIGHT (engine MEDIUM, review-required) ---
    cw = _engine_value(response, "casing_width")
    ch_casing = _engine_value(response, "casing_height")
    for label, val_, fld in (("CASING WIDTH", cw, "casing_width"),
                             ("CASING HEIGHT", ch_casing, "casing_height")):
        if val_ is not None:
            cells.append(CellFill(label, val_, "number", "review_required", f"engine:{fld}"))
        else:
            cells.append(CellFill(label, None, "number", "blocked", f"engine:{fld}",
                                  note="casing dim unresolved (needs product line + size)"))
            warnings.append(f"{tag}: {label} unresolved")

    # --- COIL TAG / QTY ---
    cells.append(_passthrough("COIL TAG", coil.get("tag"), "tag", kind="text"))
    cells.append(_passthrough("QTY", coil.get("quantity"), "quantity"))

    # --- FH / FL / ROWS / FEEDS-CIRCUITS ---
    cells.append(_passthrough("FH", coil.get("finned_height"), "finned_height"))
    cells.append(_passthrough("FL", coil.get("finned_length"), "finned_length"))
    cells.append(_passthrough("ROWS", coil.get("rows"), "rows_deep"))
    fc = coil.get("feeds") if coil.get("feeds") is not None else coil.get("circuits")
    fc_src = "number_of_feeds" if coil.get("feeds") is not None else "circuits"
    fc_status = "ready" if coil.get("feeds") is not None else "review_required"
    if fc is not None:
        cells.append(CellFill("FEEDS/CIRCUITS", fc, "number", fc_status, f"submittal:{fc_src}"))
    else:
        cells.append(CellFill("FEEDS/CIRCUITS", None, "number", "blocked",
                              "submittal:number_of_feeds", note="feeds/circuits absent"))

    # --- Connection sizes (label set varies by category) ---
    conn_labels = spec["connections"]
    if category == "DX":
        cells.append(_passthrough(conn_labels[0], coil.get("suction_conn_size"), "suction_connection_size"))
        cells.append(_passthrough(conn_labels[1], coil.get("qty_conn_per_header"), "qty_connections_per_header"))
    elif category == "HGRH":
        cells.append(_passthrough(conn_labels[0], coil.get("conn_size"), "return_connection_size"))
        cells.append(_passthrough(conn_labels[1], coil.get("qty_conn_per_header"), "qty_connections_per_header"))
    else:  # HWC / CWC
        cells.append(_passthrough(conn_labels[0], coil.get("inlet_conn_size"), "inlet_connection_size"))
        cells.append(_passthrough(conn_labels[1], coil.get("outlet_conn_size"), "outlet_connection_size"))

    # --- HANDING ---
    hand = _to_handing(coil.get("coil_hand"))
    if hand:
        cells.append(CellFill("HANDING", hand, "dropdown", "ready", "submittal:coil_hand"))
    else:
        cells.append(CellFill("HANDING", None, "dropdown", "blocked", "submittal:coil_hand",
                              note="coil hand absent/unrecognized"))

    # --- Checkboxes: collared holes ON, stacking flanges OFF ---
    cells.append(CellFill("COLLARED HOLES", True, "bool", "constant", "constant"))
    cells.append(CellFill("STACKING FLANGES", False, "bool", "constant", "constant"))

    # --- HGRH CONN SZ on the DX sheet (from the paired reheat coil) ---
    if category == "DX":
        partner = _partner(coil, coils)
        if partner and _category_of(partner) == "HGRH":
            pconn = partner.get("conn_size")
            if pconn is not None:
                cells.append(CellFill("HGRH CONN SZ", pconn, "number", "ready",
                                      f"submittal:partner_conn_size({partner.get('tag')})"))
            else:
                cells.append(CellFill("HGRH CONN SZ", None, "number", "blocked",
                                      "submittal:partner_conn_size",
                                      note="paired HGRH connection size absent"))

    # --- RB (return bend): a direct-coil INPUT value, not a computed dim (John
    # 2026-07-01). CoilForge's rule value is authoritative (R-005 DX/HGRH=1.5,
    # R-006 CWC/HWC=1.875); the template's formula (1.75/2.25) is the old SOP. So
    # we WRITE RB (overwriting the stale formula in the copy) — OAL, which is still
    # a formula referencing RB, then recomputes from the correct value.
    rb = dim_slots.get("slot.RB")
    if rb is not None:
        cells.append(CellFill("RB", rb, "number", "ready", "engine:slot.RB (direct-coil value)"))
    else:
        cells.append(CellFill("RB", None, "number", "blocked", "engine:slot.RB",
                              note="return bend unresolved"))

    # --- Lower dimensional matrix: NOT written (these are Excel FORMULAS that
    # compute from the inputs above). We capture CoilForge's engine value for each
    # so the in-app comparison can show "checklist formula vs CoilForge engine".
    circuits = coil.get("circuits")
    compare: list[DimCompare] = []
    for label in spec["dims"]:
        if T.normalize_label(label) == "RB":
            continue  # RB is written as an input above, not compared as a formula
        slot = _dim_slot(label)
        if not slot:  # DIST ORIENTATION / ASC / ASC ORIENTATION — no CoilForge analog
            continue
        k = _circuit_index(label)
        if k is not None and circuits is not None and k > circuits:
            cf_value: Any = "N/A"
        else:
            cf_value = dim_slots.get(slot)
        compare.append(DimCompare(label=label, slot=slot, coilforge_value=cf_value))

    return SheetFill(category=category, source_sheet=T.CATEGORY_SHEET[category],
                     sheet_tag=tag, cells=tuple(cells),
                     compare_dims=tuple(compare)), warnings


def build_checklist_fill(coils: list[dict[str, Any]]) -> ChecklistFill:
    """Build a ``ChecklistFill`` for every coil in a submittal.

    Each ``coils`` entry is a plain dict (mirrors ``mechanical_fit`` inputs):
      ``{tag, coil_type, product_label|product_type, unit_size|unit_size_token,
         quantity, finned_height, finned_length, rows, feeds, circuits,
         suction_conn_size, conn_size, inlet_conn_size, outlet_conn_size,
         qty_conn_per_header, coil_hand, coating, application?, hot_gas_bypass?}``.
    Coils whose category is unknown are skipped with a warning (never silently dropped).
    """
    sheets: list[SheetFill] = []
    warnings: list[str] = []
    used_categories: set[str] = set()
    for coil in coils:
        category = _category_of(coil)
        if category not in T.CATEGORY_SHEET:
            warnings.append(f"{coil.get('tag') or '?'}: unknown coil category "
                            f"'{coil.get('coil_type')}' — no checklist sheet")
            continue
        sheet, sheet_warnings = _build_sheet(coil, coils)
        sheets.append(sheet)
        warnings.extend(sheet_warnings)
        used_categories.add(category)

    remove = tuple(s for s in T.CATEGORY_SHEETS if s not in used_categories)
    return ChecklistFill(sheets=tuple(sheets), remove_sheets=remove,
                         warnings=tuple(warnings))
