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
from dataclasses import replace
from typing import Any

from coilforge.checklist.model import (
    CellFill,
    ChecklistFill,
    DimCompare,
    OverrideNote,
    SheetFill,
)
from coilforge.checklist import template_map as T
from coilforge.checklist.overrides import (
    CoilOverride,
    apply_engine_inputs,
    dim_overrides_by_slot,
)

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
def _resolve_engine(
    coil: dict[str, Any],
    application: str | None,
    *,
    with_hgrh: bool | None = None,
    hgrh_conn_size: float | None = None,
) -> tuple[dict[str, Any], Any]:
    """Run the slot layer (dims) + an application-aware engine pass (casing) for one coil.

    Returns ``(slots, response)`` where ``slots`` carries the drawing dims and
    ``response`` is the prepopulate run WITH ``application`` set, so casing W/H
    (R-074, keyed on product|application|size) resolve like ``mechanical_fit``.
    Returns ({}, None) when product line / unit size are unknown or the engine
    raises — the caller then leaves casing/dims blank and flags them.

    ``with_hgrh``/``hgrh_conn_size`` (DX paired with a reheat HGRH) select the
    engine's with-HGRH casing-depth branch (R-072), matching the checklist's
    ``DX!C24 IF(C6=TRUE,...)`` formula so the CoilForge compare column agrees with
    the sheet (else a reheat-paired DX shows CD=7.5 vs the sheet's 8).
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
        with_hgrh=with_hgrh, hgrh_conn_size=hgrh_conn_size,
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


# --------------------------------------------------------------------------- #
# Manual-override stamping
# --------------------------------------------------------------------------- #
# Coil-input key -> the column-B label whose cell is built from it. Applied in ONE pass
# after the cells are built (rather than at each construction site) so a new manual-fill
# key cannot be silently forgotten at one of a dozen `cells.append(...)` calls.
def _label_by_coil_key(category: str, spec: dict[str, Any]) -> dict[str, str]:
    conn = spec["connections"]
    common = {
        "product_label": "UNIT", "unit_size": "SIZE", "application": "APPLICATION",
        "coating": "COATING", "rows": "ROWS", "feeds": "FEEDS/CIRCUITS",
        "circuits": "FEEDS/CIRCUITS", "coil_hand": "HANDING",
    }
    if category == "DX":
        return {**common, "suction_conn_size": conn[0], "qty_conn_per_header": conn[1]}
    if category == "HGRH":
        return {**common, "conn_size": conn[0], "qty_conn_per_header": conn[1]}
    return {**common, "inlet_conn_size": conn[0], "outlet_conn_size": conn[1]}


def _stamp_input_overrides(
    cells: list[CellFill], notes: dict[str, OverrideNote], category: str, spec: dict[str, Any]
) -> list[CellFill]:
    """Mark every cell whose value came from a manual fill (Tier A).

    The value itself is already the corrected one (``apply_engine_inputs`` rewrote the
    coil dict before the cells were built); this records WHAT it replaced and re-routes
    the cell to ``review_required`` -- a human-supplied value is never 'ready'.
    """
    if not notes:
        return cells
    label_of = _label_by_coil_key(category, spec)
    by_label: dict[str, OverrideNote] = {}
    for coil_key, note in notes.items():
        label = label_of.get(coil_key)
        if label:
            by_label[T.normalize_label(label)] = note
    if not by_label:
        return cells
    out: list[CellFill] = []
    for cell in cells:
        note = by_label.get(T.normalize_label(cell.label))
        if note is None:
            out.append(cell)
            continue
        was = "blank" if note.previous_value in (None, "") else note.previous_value
        reason = f" ({note.reason})" if note.reason else ""
        out.append(
            replace(
                cell,
                status="review_required",
                source=f"manual_override:{note.key}",
                note=f"manual override: was {was}{reason}",
                override=note,
            )
        )
    return out


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


# Checklist UNIT value -> engine product family key used by the R-077 lookup.
#
# "TERRA V" maps to TERRA_V, NOT the coarse TERRA it used to fold onto. That fold was the
# route AROUND the Terra V guard: `_drain_pan_row("TERRA", size, "D1")` happily returns the
# Terra **H** width, and this caller writes its result into the .xlsx that ships with the
# order. It was inert only while the option argument was hardcoded None — the moment the
# model-code parser started supplying a real D-option it would have become a wrong number
# in a customer-facing workbook. The guard now lives inside `_drain_pan_row`, so both
# callers are covered; this mapping just has to stop hiding which family is asking.
_FAMILY_FROM_UNIT = {
    "NOVA": "NOVA", "VENTUM H": "VENTUM_H", "VENTUM+": "VENTUM_PLUS",
    "TERRA H": "TERRA", "TERRA V": "TERRA_V",
}


def _install_widths(
    unit: str | None, unit_size: Any, drain_pan_option: str | None = None
) -> tuple[Any, Any]:
    """(INSTALL WIDTH, DRAIN PAN WIDTH) from R-077 for the INSTALL FIT rows.

    Reuses ``mechanical_fit._drain_pan_row`` (R-077). The sheet's INSTALL FIT formula
    compares against INSTALL WIDTH for VENTUM+ and DRAIN PAN WIDTH otherwise, so both
    cells are filled with the right R-077 columns. Returns (None, None) when unresolved
    (Terra H without a readable D-option; Terra V at all) — never invented.
    """
    from coilforge.compatibility.mechanical_fit import _drain_pan_row

    family = _FAMILY_FROM_UNIT.get(unit or "")
    if not family:
        return (None, None)
    row = _drain_pan_row(
        family, str(unit_size) if unit_size is not None else None, drain_pan_option
    )
    if not row:
        return (None, None)
    install_w = row.get("install_width", row.get("with_access"))
    drain_w = row.get("drain_pan_width", row.get("coil_module_only"))
    return (install_w, drain_w)


def _install_width_blocked_note(unit: str | None, drain_pan_option: str | None) -> str:
    """Why INSTALL/DRAIN PAN WIDTH is blank for THIS unit.

    Split by cause so the engineer is not sent after a value that would not help:
    Terra V cannot be unblocked by any option, and a Terra H that still blocks after the
    model code was read has a different problem from one whose code was never found.
    """
    if (unit or "").upper() == "TERRA V":
        return (
            "Terra V drain-pan width is keyed by unit size and the Install sheet has no "
            "Terra V rows yet — it deliberately does not borrow the Terra H widths"
        )
    if (unit or "").upper() == "TERRA H" and not drain_pan_option:
        return (
            "Terra H drain-pan width needs the D1/D2/D3 option, which could not be read "
            "from the unit model code on this submittal"
        )
    return "drain-pan/install width not found in R-077 for this unit and size"


def _build_sheet(
    coil: dict[str, Any],
    coils: list[dict[str, Any]],
    input_notes: dict[str, OverrideNote] | None = None,
    override: CoilOverride | None = None,
) -> tuple[SheetFill, list[str]]:
    category = _category_of(coil)
    spec = T.SHEET_LABELS[category]
    warnings: list[str] = []
    cells: list[CellFill] = []
    tag = coil.get("tag") or category
    input_notes = input_notes or {}

    # Resolve UNIT + APPLICATION first: APPLICATION feeds the engine so casing
    # W/H (R-074, product|application|size) can resolve.
    unit = _to_unit(coil.get("product_label") or coil.get("product_type"))
    if category == "HWC" or "application" in input_notes:
        # A manually filled APPLICATION beats the per-UNIT constant for EVERY category:
        # the engineer supplied it precisely because the coil's casing class is not the
        # default one, and it drives R-074 casing W/H below.
        application = coil.get("application")
    else:
        application = T.APPLICATION_FIXED.get(unit or "")
    # A DX paired with a reheat HGRH takes the engine's with-HGRH casing-depth
    # branch (R-072), same as the sheet's DX!C24 IF(W/HGRH=TRUE,...). Source the
    # partner connection size the same way the Excel "HGRH CONN SZ" cell is filled
    # (partner.conn_size) so the CoilForge compare value matches the sheet.
    dx_with_hgrh: bool | None = None
    dx_hgrh_conn: float | None = None
    if category == "DX":
        _dx_partner = _partner(coil, coils)
        if _dx_partner and _category_of(_dx_partner) == "HGRH":
            dx_with_hgrh = True
            dx_hgrh_conn = _dx_partner.get("conn_size")
    slots, response = _resolve_engine(
        coil, application, with_hgrh=dx_with_hgrh, hgrh_conn_size=dx_hgrh_conn
    )
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
    if category == "HWC" or "application" in input_notes:
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

    # --- INSTALL FIT inputs (HGRH + HWC sheets only; the fit lives on the reheat /
    # hot-water partner sheet). Fill the paired coil's CD/FH/FL, installed-on-drain-pan,
    # and R-077 install / drain-pan widths so the sheet's INSTALL FIT formula computes.
    if category in ("HGRH", "HWC"):
        partner = _partner(coil, coils)
        installed = partner is not None
        cells.append(CellFill("INSTALLED ON DP", installed, "bool",
                              "review_required" if installed else "constant",
                              "derived:partner_tag"))
        if partner:
            # The partner's CD must be resolved the SAME way that partner's OWN sheet
            # resolves it, or the number written here disagrees with the number the DX
            # sheet shows for the very same coil — and this cell is an INPUT to the
            # sheet's INSTALL FIT, so the disagreement propagates into the drain-pan
            # verdict. On an HGRH sheet the partner IS the reheat-paired DX, so it takes
            # R-072's with-HGRH branch exactly as `_build_sheet` does at :344-351.
            # Gated on the category because this block also serves the HWC sheet, whose
            # partner is a CWC — an ungated with_hgrh=True would apply the reheat branch
            # to a water coil.
            p_with_hgrh = True if category == "HGRH" else None
            p_hgrh_conn = coil.get("conn_size") if category == "HGRH" else None
            p_slots, _p = _resolve_engine(  # CD does not depend on application
                partner, None, with_hgrh=p_with_hgrh, hgrh_conn_size=p_hgrh_conn
            )
            p_cd = p_slots.get("slot.CD")
            ptag = partner.get("tag")
            if category == "HGRH":
                cells.append(CellFill("DX FH", partner.get("finned_height"), "number",
                                      "ready" if partner.get("finned_height") is not None else "blocked",
                                      f"submittal:partner_fh({ptag})"))
                cells.append(CellFill("DX FL", partner.get("finned_length"), "number",
                                      "ready" if partner.get("finned_length") is not None else "blocked",
                                      f"submittal:partner_fl({ptag})"))
                cells.append(CellFill("DX CD", p_cd, "number",
                                      "review_required" if p_cd is not None else "blocked",
                                      f"engine:partner slot.CD({ptag})",
                                      note=None if p_cd is not None else "partner DX CD unresolved"))
            else:  # HWC sheet -> paired CWC coil's CD
                cells.append(CellFill("CWC CD", p_cd, "number",
                                      "review_required" if p_cd is not None else "blocked",
                                      f"engine:partner slot.CD({ptag})",
                                      note=None if p_cd is not None else "partner CWC CD unresolved"))
        drain_pan_option = coil.get("drain_pan_option")
        iw, dpw = _install_widths(
            unit,
            coil.get("unit_size") or coil.get("unit_size_token"),
            drain_pan_option,
        )
        source = (
            f"engine:R-077 (drain-pan option {drain_pan_option} from the unit model code)"
            if drain_pan_option else "engine:R-077"
        )
        for lbl, val in (("INSTALL WIDTH", iw), ("DRAIN PAN WIDTH", dpw)):
            if val is not None:
                cells.append(CellFill(lbl, val, "number", "review_required", source))
            else:
                # Name the actual blocker. "Terra needs a D1/D2/D3 option" was right while
                # nothing produced one; now that the model code supplies it, a Terra H coil
                # that still blocks did so for a different reason, and Terra V blocks for a
                # reason no option can fix.
                cells.append(CellFill(lbl, None, "number", "blocked", "engine:R-077",
                                      note=_install_width_blocked_note(unit, drain_pan_option)))

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
    # Tier-B manual overrides, keyed by the SAME slot ids the drawing path merges into
    # slot_values — so a dim the engineer corrected on the drawing lands on the matching
    # checklist row and nowhere else.
    dim_ov_by_slot, unmapped_params = dim_overrides_by_slot(override)
    matched_slots: set[str] = set()
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
        dim_override: OverrideNote | None = None
        if slot in dim_ov_by_slot:
            # The override IS the drawn value, so it becomes the CoilForge column; the
            # engine proposal it replaced rides along as previous_value. Applied even
            # past the circuit count ("N/A") — the engineer typed it deliberately.
            key, value, reason = dim_ov_by_slot[slot]
            dim_override = OverrideNote(key=key, previous_value=cf_value, reason=reason)
            cf_value = value
            matched_slots.add(slot)
        compare.append(DimCompare(label=label, slot=slot, coilforge_value=cf_value,
                                  override=dim_override))

    # Never drop an override in silence: a param with no slot at all (ZD) or one whose
    # slot has no row on THIS category's sheet is surfaced for review.
    for key in unmapped_params:
        warnings.append(f"{tag}: manual override '{key}' has no checklist dimension row")
    for slot, (key, _value, _reason) in dim_ov_by_slot.items():
        if slot not in matched_slots:
            warnings.append(
                f"{tag}: manual override '{key}' ({slot}) is not on the {category} sheet"
            )

    cells = _stamp_input_overrides(cells, input_notes, category, spec)
    return SheetFill(category=category, source_sheet=T.CATEGORY_SHEET[category],
                     sheet_tag=tag, cells=tuple(cells),
                     compare_dims=tuple(compare)), warnings


def build_checklist_fill(
    coils: list[dict[str, Any]],
    overrides: dict[str, CoilOverride] | None = None,
) -> ChecklistFill:
    """Build a ``ChecklistFill`` for every coil in a submittal.

    Each ``coils`` entry is a plain dict (mirrors ``mechanical_fit`` inputs):
      ``{tag, coil_type, product_label|product_type, unit_size|unit_size_token,
         quantity, finned_height, finned_length, rows, feeds, circuits,
         suction_conn_size, conn_size, inlet_conn_size, outlet_conn_size,
         qty_conn_per_header, coil_hand, coating, application?, hot_gas_bypass?}``.
    Coils whose category is unknown are skipped with a warning (never silently dropped).

    ``overrides`` (``{tag: CoilOverride}``, from ``checklist.overrides``) carries the
    engineer's browser manual fills. Tier-A engine inputs are applied to EVERY coil
    before any sheet is built, so a partner-sourced cell (the DX sheet's HGRH CONN SZ,
    the HGRH sheet's DX CD) sees the corrected partner too. Omitting it reproduces the
    pre-override fill exactly.
    """
    overrides = overrides or {}
    # Pass 1 — apply Tier-A fills to every coil, so `coils` (used for partner lookups)
    # is uniformly the corrected set.
    applied: list[tuple[dict[str, Any], dict[str, OverrideNote], CoilOverride | None]] = []
    for coil in coils:
        override = overrides.get(str(coil.get("tag")))
        updated, notes = apply_engine_inputs(coil, override, _category_of(coil))
        applied.append((updated, notes, override))
    resolved_coils = [entry[0] for entry in applied]

    sheets: list[SheetFill] = []
    warnings: list[str] = []
    used_categories: set[str] = set()
    for coil, notes, override in applied:
        category = _category_of(coil)
        if category not in T.CATEGORY_SHEET:
            warnings.append(f"{coil.get('tag') or '?'}: unknown coil category "
                            f"'{coil.get('coil_type')}' — no checklist sheet")
            continue
        sheet, sheet_warnings = _build_sheet(coil, resolved_coils, notes, override)
        sheets.append(sheet)
        warnings.extend(sheet_warnings)
        used_categories.add(category)
        for key in (override.ignored_keys if override else ()):
            warnings.append(
                f"{coil.get('tag') or '?'}: manual fill '{key}' has no checklist field "
                f"(applied to the drawing only)"
            )

    remove = tuple(s for s in T.CATEGORY_SHEETS if s not in used_categories)
    return ChecklistFill(sheets=tuple(sheets), remove_sheets=remove,
                         warnings=tuple(warnings))
