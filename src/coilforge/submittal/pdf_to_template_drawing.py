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
    extract_coilmaster_drawing,
    extract_unit_size,
    product_for_unit_size,
)
from coilforge.template_population.catalog import (
    TemplateSelectionRequest,
    select_drawing_template,
)
from coilforge.template_population.slot_population import populate_template_slots

_COIL_CODE_TO_CATEGORY = {"DX": "DX", "HG": "HGRH", "CW": "CWC", "HW": "HWC"}
# Slots produced by the recovered formulas in build_drawing_slots (vs engine rules).
_FORMULA_SLOTS = {
    "slot.FH", "slot.CH", "slot.FL", "slot.CL", "slot.OAL", "slot.S1",
    "slot.R2", "slot.ROWS",
}


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
    if slot in _SLOT_ENGINE_FIELD:
        return "engine_rule"
    if slot in _FORMULA_SLOTS:
        return "recovered_formula"
    return "engine_or_formula"


def _validation(derived: Any, as_built: Any) -> str:
    if as_built is None:
        return "no_as_built_reference"
    try:
        return "match" if abs(float(derived) - float(as_built)) < 0.02 else f"mismatch:{as_built}"
    except (TypeError, ValueError):
        return "match" if str(derived) == str(as_built) else f"mismatch:{as_built}"


def derive_slot_values(
    extract: dict[str, Any],
    *,
    coil_category: str | None,
    circuits: int,
    product: str | None,
    unit_size: str | None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str], bool]:
    """Logic-derived slot values (authoritative) + per-slot source/validation report.

    Returns (slot_values, slot_sources, review_items, header_engine_used).
    """
    as_built = slots_from_drawing_extract(extract)
    slot_values: dict[str, Any] = {}
    sources: dict[str, dict[str, Any]] = {}
    review_items: list[str] = []
    header_engine_used = False

    if product and unit_size and coil_category:
        derived, response = build_drawing_slots(
            coil_type=coil_category,
            product_type=product,
            unit_size=unit_size,
            rows=extract.get("rows"),
            feeds=extract.get("feeds"),
            circuits=circuits,
            suction_conn_size=_conn_float(extract.get("return_conn_size")),
            finned_height=extract.get("fh"),
            finned_length=extract.get("fl"),
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

    # Slots the logic could not derive -> fall back to the as-built reading.
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

    product/unit come from the cover page token (cover_text) or, when the caller
    already resolved them (e.g. the submittal intake's selected candidate), from
    header_context["product_type"/"unit_size"] which takes precedence.
    """
    extract = extract_coilmaster_drawing(text)
    coil_category = _COIL_CODE_TO_CATEGORY.get(
        extract.get("coil_code", ""), extract.get("coil_code")
    )
    hand = extract.get("hand", "LH")
    circuits = extract.get("circuits", 1)
    header_type = f"Header {circuits}"

    ctx = header_context or {}
    unit_size = ctx.get("unit_size") or (extract_unit_size(cover_text) if cover_text else None)
    product = ctx.get("product_type") or product_for_unit_size(unit_size)

    selection = select_drawing_template(
        TemplateSelectionRequest(
            supplier="coilmaster",
            coil_category=coil_category,
            coil_hand=hand,
            header_type=header_type,
        )
    )

    slot_values, slot_sources, review_items, engine_used = derive_slot_values(
        extract,
        coil_category=coil_category,
        circuits=circuits,
        product=product,
        unit_size=unit_size,
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
            "rows": extract.get("rows"),
            "feeds": extract.get("feeds"),
            "tag": extract.get("tag"),
            "return_conn_size": extract.get("return_conn_size"),
            "dimension_count": len(extract.get("dimensions", {})),
        },
        "unit_size": unit_size,
        "product_type": product,
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
