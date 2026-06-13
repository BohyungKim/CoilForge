"""PDF -> linked, populated template-first drawing.

Wires the CoilMaster drawing extractor into the drawing path: the scanned coil
drawing's as-built values are read directly and pushed into the matching seeded
template (selected by coil type + circuit count + hand). The submittal cover
page (if provided) yields unit size -> product family for reference.

This is the reproduction path (read the existing drawing's values); the header
engine remains the prediction path for fresh coils with no drawing.
"""

from __future__ import annotations

import io
from typing import Any

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


def slots_from_drawing_extract(extract: dict[str, Any]) -> dict[str, Any]:
    """Map extracted drawing values directly onto template slot ids."""
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


def pdf_text_to_template_drawing(
    text: str, *, cover_text: str | None = None
) -> dict[str, Any]:
    """Extract a coil drawing's values and populate its matching template."""
    extract = extract_coilmaster_drawing(text)
    coil_category = _COIL_CODE_TO_CATEGORY.get(
        extract.get("coil_code", ""), extract.get("coil_code")
    )
    hand = extract.get("hand", "LH")
    circuits = extract.get("circuits", 1)
    header_type = f"Header {circuits}"

    unit_size = extract_unit_size(cover_text) if cover_text else None
    product = product_for_unit_size(unit_size)

    selection = select_drawing_template(
        TemplateSelectionRequest(
            supplier="coilmaster",
            coil_category=coil_category,
            coil_hand=hand,
            header_type=header_type,
        )
    )
    slot_values = slots_from_drawing_extract(extract)

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
        "slot_values": slot_values,
        "svg": svg,
        "populated_slots": populated_slots,
        "missing_required_slots": missing,
        "population_status": status,
        "release_status": "review_aid_only",
        "export_allowed": False,
    }


def pdf_bytes_to_template_drawing(
    pdf_bytes: bytes, *, cover_text: str | None = None
) -> dict[str, Any]:
    """Read text from PDF bytes, then populate the matching template."""
    from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "".join((page.extract_text() or "") for page in reader.pages)
    return pdf_text_to_template_drawing(text, cover_text=cover_text)
