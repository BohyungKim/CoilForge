"""PDF -> coil type -> template link -> logic-derived, populated drawing.

The ultimate flow (per the documented md-file logic):

    PDF extracted data  ->  classify coil type / header count / hand
                        ->  select the matching drawing template
                        ->  feed header data (rows, FH/FL, circuits, conn,
                            product/unit) into the SOP/checklist rule engine +
                            recovered formulas + JSON link registry
                        ->  the engine/formula values ARE the drawing
                            dimensions (logic-derived is authoritative)
                        ->  populate the template; the values printed on an
                            as-built PDF are read only to VALIDATE (mismatch
                            flags), never to override the logic.

A slot the logic genuinely cannot derive falls back to the as-built reading
(tagged source=as_built_fallback), else it renders REVIEW REQUIRED. Output is a
review aid only — never manufacturing-approved.
"""

from __future__ import annotations

import io
import re
from typing import Any

from coilforge.services.direct_coil_drawing_pipeline import (
    _SLOT_ENGINE_FIELD,
    build_drawing_slots,
    map_engine_to_slots,
    material_title_slots,
)
from coilforge.submittal.coilmaster_drawing_extract import (
    TERRA_H_LABEL,
    TERRA_V_LABEL,
    detect_product_and_size,
    extract_coilmaster_drawing,
    extract_unit_size,
    product_for_unit_size,
    product_size_options,
)
from coilforge.template_population.catalog import (
    TemplateSelectionRequest,
    select_drawing_template,
)
from coilforge.template_population.slot_population import populate_template_slots

_COIL_CODE_TO_CATEGORY = {"DX": "DX", "HG": "HGRH", "CW": "CWC", "HW": "HWC"}
# Slots produced by the recovered formulas in build_drawing_slots (vs engine rules).
_FORMULA_SLOTS = {
    "slot.FH", "slot.CH", "slot.FL", "slot.CL", "slot.OAL", "slot.ROWS",
}
# Per-header positional families emitted by build_drawing_slots' per-circuit loop.
# Supply S{odd} is the recovered k*CD/(circuits+1) formula; the rest (per-header
# constants I/HDx/O/HD/SL and the engine R-022 list R{even}) are engine rules.
_PER_HEADER_FORMULA_RE = re.compile(r"^slot\.S\d+$")
_PER_HEADER_ENGINE_RE = re.compile(r"^slot\.(HDx|I|O|HD|SL|R)\d+$")


def slots_from_drawing_extract(extract: dict[str, Any]) -> dict[str, Any]:
    """Map the as-built drawing's printed values directly onto template slot ids.

    Used for VALIDATION of the logic-derived values and as a fallback for slots
    the logic cannot derive (e.g. multi-header per-pair positions without a JSON
    export).
    """
    slots: dict[str, Any] = {
        f"slot.{label}": value for label, value in extract.get("dimensions", {}).items()
    }
    if extract.get("tag"):
        slots["slot.TAG"] = extract["tag"]
    if extract.get("model_number"):
        slots["slot.MODEL_NUMBER"] = extract["model_number"]
    if extract.get("return_conn_size"):
        slots["slot.RETURN_CONN_SIZE"] = extract["return_conn_size"]
    feeds, circuits = extract.get("feeds"), extract.get("circuits")
    if feeds is not None:
        passes = extract.get("passes") or extract.get("passes_per_feed")
        slots["slot.CIRCUITING"] = (
            f"{feeds} Feed / {passes} Pass" if circuits == 1
            else f"{feeds} Feed / {circuits} circuits"
        )
    return slots


def _conn_float(value: Any) -> float | None:
    """Leading numeric inches from a connection-size string ('0.625" OD' -> 0.625)."""
    if value is None:
        return None
    m = re.search(r"[\d.]+", str(value))
    return float(m.group(0)) if m else None


def _slot_source(slot: str) -> str:
    if slot in _SLOT_ENGINE_FIELD or _PER_HEADER_ENGINE_RE.match(slot):
        return "engine_rule"
    if slot in _FORMULA_SLOTS or _PER_HEADER_FORMULA_RE.match(slot):
        return "recovered_formula"
    return "engine_or_formula"


def _validation(derived: Any, as_built: Any) -> str:
    if as_built is None:
        return "no_as_built_reference"
    try:
        return "match" if abs(float(derived) - float(as_built)) < 0.02 else f"mismatch:{as_built}"
    except (TypeError, ValueError):
        return "match" if str(derived) == str(as_built) else f"mismatch:{as_built}"


def _panel_slots(panel: dict[str, Any] | None, coil_category: str | None) -> dict[str, Any]:
    """Right-side specification-panel slots from the submittal-stated values.

    These are read straight off the submittal (materials, fins-per-inch, weight,
    circuiting, connection size) and surfaced review-required — they are NOT
    engine-derived, so they map whether or not a product line + unit size is
    known. Only source-backed values are emitted; anything the submittal does not
    state stays REVIEW REQUIRED rather than being invented.
    """
    if not panel:
        return {}
    slots: dict[str, Any] = {}

    def put(slot: str, value: Any) -> None:
        if value not in (None, ""):
            slots[slot] = value

    # Tube material block: "<thk> <material>" / surface.
    put("slot.TUBE_MATERIAL", panel.get("tube_material"))
    put("slot.TUBE_MATERIAL_2", panel.get("tube_surface"))
    # Fin material block: FPI / "<thk> <material>" / surface.
    fpi = panel.get("fins_per_inch")
    put("slot.FIN_MATERIAL", f"{fpi} FPI" if fpi not in (None, "") else None)
    put("slot.FIN_MATERIAL_2", panel.get("fin_material"))
    put("slot.FIN_MATERIAL_3", panel.get("fin_surface"))
    put("slot.CASING_MATERIAL", panel.get("casing_material"))
    put("slot.HEADER_MATERIAL", panel.get("header_material"))
    weight = panel.get("dry_weight")
    put("slot.DRY_WEIGHT", f"{weight} Lbs. Per Coil" if weight not in (None, "") else None)
    volume = panel.get("internal_volume")
    put("slot.INTERNAL_VOLUME", f"{volume} Cu. In." if volume not in (None, "") else None)

    feeds = panel.get("feeds")
    if feeds not in (None, ""):
        circuits = panel.get("circuits")
        put(
            "slot.CIRCUITING",
            f"{feeds} Feed / {circuits} circuits"
            if circuits and circuits > 1
            else f"{feeds} Feed",
        )

    conn = panel.get("conn_size")
    if conn not in (None, ""):
        # DX coils show a return connection; water / HGRH coils show supply.
        conn_slot = "slot.RETURN_CONN_SIZE" if coil_category == "DX" else "slot.SUPPLY_CONN_SIZE"
        put(conn_slot, f'{conn}"')

    if coil_category == "DX":
        put("slot.DISTRIBUTORS", panel.get("distributor_notes"))
    return slots


# Daikin/Oxygen8 unit family -> CoilForge product line, and the unit-size token
# (e.g. "TR_C_009" -> TERRA / "9"). Surfaced as a review-required SUGGESTION that
# pre-fills the product/size picker; the engineer still confirms before the engine
# derives any dimension (the gate is preserved — nothing is auto-drawn).
def _suggest_product_and_size(text: str | None) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    upper = text.upper()
    product: str | None = None
    if "TERRA" in upper:
        # Terra is split into orientation categories (John 2026-06-15): the cover
        # text states "Terra Vertical" / "Terra Horizontal". Default to H.
        product = TERRA_V_LABEL if "VERTICAL" in upper else TERRA_H_LABEL
    elif "VENTUM" in upper:
        product = (
            "VENTUM_PLUS"
            if ("VENTUM+" in upper or "VENTUM PLUS" in upper or "VENTUM-PLUS" in upper)
            else "VENTUM_H"
        )
    elif "NOVA" in upper:
        product = "NOVA"
    if product is None:
        return None, None

    try:
        valid_sizes = set(product_size_options().get(product, []))
    except Exception:  # rule table unavailable; still suggest the product line
        valid_sizes = set()

    size: str | None = None
    if product in (TERRA_H_LABEL, TERRA_V_LABEL):
        # "TR_C_009" / "TR-C-009" -> "009" (zero-padded 3-digit Terra size token).
        match = re.search(r"\bT[A-Z]?[_\- ]?C[_\- ]?0*(\d{1,3})\b", upper)
        if match:
            size = f"{int(match.group(1)):03d}"
    else:
        token = extract_unit_size(text)  # A16 / V60 / H10 style
        if token:
            size = token
    if size is not None and valid_sizes and size not in valid_sizes:
        size = None
    return product, size


def _submittal_geometry_slots(geo: dict[str, Any], circuits: int) -> dict[str, Any]:
    """Slots known directly from the submittal candidate, independent of the rule
    engine (so they map even when product/unit are unknown and the engine is gated).
    These are submittal-stated inputs, surfaced review-required — not derived.
    """
    slots: dict[str, Any] = {}
    if geo.get("finned_height") is not None:
        slots["slot.FH"] = geo["finned_height"]
    if geo.get("finned_length") is not None:
        slots["slot.FL"] = geo["finned_length"]
    if geo.get("rows") is not None:
        slots["slot.ROWS"] = geo["rows"]
    conn = geo.get("suction_conn_size")
    if conn is not None:
        slots["slot.RETURN_CONN_SIZE"] = conn
    feeds = geo.get("feeds")
    if feeds is not None:
        slots["slot.CIRCUITING"] = (
            f"{feeds} Feed / {circuits} circuits" if circuits and circuits > 1
            else f"{feeds} Feed"
        )
    return slots


def derive_slot_values(
    extract: dict[str, Any],
    *,
    coil_category: str | None,
    circuits: int,
    product: str | None,
    unit_size: str | None,
    geometry: dict[str, Any] | None = None,
    panel: dict[str, Any] | None = None,
    as_built_available: bool = True,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str], bool]:
    """Logic-derived slot values (authoritative) + per-slot source/validation report.

    Returns (slot_values, slot_sources, review_items, header_engine_used).

    When the as-built ``extract`` lacks geometry (a real submittal has no scanned
    drawing to read), ``geometry`` supplies the engine inputs the caller already
    resolved from the submittal candidate, and known-directly geometry is mapped to
    slots review-required. ``as_built_available`` is False on the submittal path
    (no genuine drawing) so the as-built text parse — which on a submittal is noise
    (e.g. CD=1.0) — is not used to fill slots.
    """
    geo = geometry or {}
    as_built = slots_from_drawing_extract(extract) if as_built_available else {}
    slot_values: dict[str, Any] = {}
    sources: dict[str, dict[str, Any]] = {}
    review_items: list[str] = []
    header_engine_used = False

    if product and unit_size and coil_category:
        rows = extract.get("rows") if extract.get("rows") is not None else geo.get("rows")
        feeds = extract.get("feeds") if extract.get("feeds") is not None else geo.get("feeds")
        finned_height = extract.get("fh") if extract.get("fh") is not None else geo.get("finned_height")
        finned_length = extract.get("fl") if extract.get("fl") is not None else geo.get("finned_length")
        conn = extract.get("return_conn_size")
        if conn is None:
            conn = geo.get("suction_conn_size")
        derived, response = build_drawing_slots(
            coil_type=coil_category,
            product_type=product,
            unit_size=unit_size,
            rows=rows,
            feeds=feeds,
            circuits=circuits,
            suction_conn_size=_conn_float(conn),
            finned_height=finned_height,
            finned_length=finned_length,
            tag=extract.get("tag"),
        )
        derived.update(
            material_title_slots(
                model_number=extract.get("model_number"), tag=extract.get("tag")
            )
        )
        _, review_items = map_engine_to_slots(response)
        header_engine_used = True
        for slot, value in derived.items():
            slot_values[slot] = value
            sources[slot] = {
                "value": value,
                "source": _slot_source(slot),
                "as_built": as_built.get(slot),
                "validation": _validation(value, as_built.get(slot)),
            }

    # Right-side spec panel (materials / fins / weight / circuiting / connection)
    # straight from the submittal -> map review-required, independent of the
    # engine gate. Does not overwrite an engine-derived value.
    for slot, value in _panel_slots(panel, coil_category).items():
        if slot not in slot_values:
            slot_values[slot] = value
            sources[slot] = {
                "value": value,
                "source": "submittal_input",
                "as_built": as_built.get(slot),
                "validation": "review_required",
            }

    # Header material: the locked evidence is consistently "Type L Copper" but
    # it is NOT universal, so surface it as a review-required DEFAULT (not a
    # confirmed/derived value) when the submittal does not state one.
    if "slot.HEADER_MATERIAL" not in slot_values:
        slot_values["slot.HEADER_MATERIAL"] = "Type L Copper"
        sources["slot.HEADER_MATERIAL"] = {
            "value": "Type L Copper",
            "source": "review_default",
            "as_built": as_built.get("slot.HEADER_MATERIAL"),
            "validation": "review_required",
        }

    # Slots the engine could not derive but the submittal stated directly
    # (FH/FL/ROWS/conn/circuiting) -> map them, review-required (not derived).
    for slot, value in _submittal_geometry_slots(geo, circuits).items():
        if slot not in slot_values:
            slot_values[slot] = value
            sources[slot] = {
                "value": value,
                "source": "submittal_input",
                "as_built": as_built.get(slot),
                "validation": "review_required",
            }

    # Remaining slots -> fall back to the as-built reading (genuine drawing only;
    # on the submittal path as_built is empty so nothing noisy leaks in).
    for slot, value in as_built.items():
        if slot not in slot_values:
            slot_values[slot] = value
            sources[slot] = {
                "value": value,
                "source": "as_built_fallback",
                "as_built": value,
                "validation": "as_built_only",
            }
    return slot_values, sources, review_items, header_engine_used


def pdf_text_to_template_drawing(
    text: str,
    *,
    cover_text: str | None = None,
    header_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify the coil, select its template, and populate it with logic-derived
    dimensions (validated against the as-built reading).

    When the caller already resolved the coil (e.g. the submittal intake's selected
    candidate), ``header_context`` carries the authoritative classification and
    engine inputs and takes precedence over the as-built model-number parse:
    ``coil_category``, ``coil_hand``, ``circuits``, ``special_feature`` (HGBP),
    ``product_type``/``unit_size``, and geometry (``rows``/``feeds``/
    ``finned_height``/``finned_length``/``suction_conn_size``). The
    ``extract_coilmaster_drawing`` parse stays as the fallback for genuine scanned
    CoilMaster drawing pages.
    """
    extract = extract_coilmaster_drawing(text)
    ctx = header_context or {}

    # Caller-resolved classification (the submittal candidate path) is
    # authoritative; the as-built model-number parse is the fallback for genuine
    # scanned CoilMaster drawing pages.
    coil_category = ctx.get("coil_category") or _COIL_CODE_TO_CATEGORY.get(
        extract.get("coil_code", ""), extract.get("coil_code")
    )
    hand = ctx.get("coil_hand") or extract.get("hand") or "LH"
    circuits = ctx.get("circuits") or extract.get("circuits") or 1
    special_feature = ctx.get("special_feature")
    header_type = None if special_feature else f"Header {circuits}"
    # The candidate tag (a real coil tag like CDXC-1) wins over the as-built
    # parse, which on a submittal grabs the unit tag (e.g. DOAS-1).
    tag = ctx.get("tag") or extract.get("tag")

    # Auto-detect the product line + unit size from the submittal model code
    # (e.g. "TR_C_009" -> TERRA H / 009) so the engine runs on feed. Deterministic
    # and R-076-validated; surfaced review-required and overridable in the picker.
    det_product, det_size = detect_product_and_size(cover_text)
    unit_size = (
        ctx.get("unit_size")
        or det_size
        or (extract_unit_size(cover_text) if cover_text else None)
    )
    product = ctx.get("product_type") or det_product or product_for_unit_size(unit_size)
    product_size_auto_detected = bool(
        det_product and not ctx.get("product_type") and not ctx.get("unit_size")
    )

    # The as-built text parse is trustworthy only when a genuine CoilMaster drawing
    # was read (it always carries a model number). On the submittal path (caller
    # classification, no model number) those readings are noise — don't fill slots.
    submittal_path = bool(header_context)
    as_built_available = (not submittal_path) or bool(extract.get("model_number"))

    selection = select_drawing_template(
        TemplateSelectionRequest(
            supplier="coilmaster",
            coil_category=coil_category,
            coil_hand=hand,
            header_type=header_type,
            special_feature=special_feature,
        )
    )

    slot_values, slot_sources, review_items, engine_used = derive_slot_values(
        extract,
        coil_category=coil_category,
        circuits=circuits,
        product=product,
        unit_size=unit_size,
        geometry=ctx,
        panel=ctx.get("panel"),
        as_built_available=as_built_available,
    )

    # Review-required product/size SUGGESTION from the unit family (e.g. a Terra
    # unit -> TERRA product line). Only when the engineer has not already chosen
    # a product line (the derive path supplies its own). Pre-fills the picker;
    # the gate stays — the engine runs only after the engineer confirms.
    suggested_product, suggested_unit_size = (
        _suggest_product_and_size(cover_text) if not (product and unit_size) else (None, None)
    )
    if tag:
        slot_values["slot.TAG"] = tag
        slot_sources.setdefault(
            "slot.TAG",
            {"value": tag, "source": "submittal_input", "as_built": None, "validation": "review_required"},
        )
    mismatches = {
        slot: meta["validation"]
        for slot, meta in slot_sources.items()
        if str(meta["validation"]).startswith("mismatch")
    }

    svg, populated_slots, missing, status = "", [], [], "seed_pending"
    if selection.found and selection.generation_allowed and selection.template_id:
        result = populate_template_slots(selection.template_id, slot_values)
        svg = result.svg
        populated_slots = list(result.populated_slots)
        missing = list(result.missing_required_slots)
        status = result.metadata.get("template_population_status", "")

    return {
        "extracted": {
            "coil_category": coil_category,
            "hand": hand,
            "circuits": circuits,
            "header_type": header_type,
            "special_feature": special_feature,
            "rows": extract.get("rows") if extract.get("rows") is not None else ctx.get("rows"),
            "feeds": extract.get("feeds") if extract.get("feeds") is not None else ctx.get("feeds"),
            "finned_height": extract.get("fh") if extract.get("fh") is not None else ctx.get("finned_height"),
            "finned_length": extract.get("fl") if extract.get("fl") is not None else ctx.get("finned_length"),
            "tag": tag,
            "return_conn_size": extract.get("return_conn_size") or ctx.get("suction_conn_size"),
            "dimension_count": len(extract.get("dimensions", {})),
        },
        "unit_size": unit_size,
        "product_type": product,
        "product_size_auto_detected": product_size_auto_detected,
        "suggested_product_type": suggested_product,
        "suggested_unit_size": suggested_unit_size,
        # Echo the submittal spec-panel values so the UI re-derive can resend them
        # and keep the right-side panel populated once dimensions are derived.
        "panel": ctx.get("panel") or {},
        "template_id": selection.template_id,
        "template_found": selection.found,
        "generation_allowed": selection.generation_allowed,
        "template_status": selection.template_status,
        "drawing_value_source": "logic_derived" if engine_used else "as_built_fallback",
        "header_engine_used": engine_used,
        "slot_values": slot_values,
        "slot_sources": slot_sources,
        "validation_mismatches": mismatches,
        "review_items": review_items,
        "svg": svg,
        "populated_slots": populated_slots,
        "missing_required_slots": missing,
        "population_status": status,
        "release_status": "review_aid_only",
        "export_allowed": False,
    }


def pdf_bytes_to_template_drawing(
    pdf_bytes: bytes,
    *,
    cover_text: str | None = None,
    header_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Read text from PDF bytes, then populate the matching template.

    When no explicit cover_text is given, the full PDF text is used so the
    cover-page unit-size token (e.g. 'A16_V_I_...') is found if present.
    """
    from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "".join((page.extract_text() or "") for page in reader.pages)
    return pdf_text_to_template_drawing(
        text, cover_text=cover_text or text, header_context=header_context
    )
