"""Drawing-package workflow: combine the Direct Coil drawing with ours.

Ties the deterministic copper-strap rule (R-090, ``copper_strap_requirement``)
to the PDF assembler. The engineer feeds the Direct Coil drawing PDF; CoilForge
appends our own drawing right after it and stamps the copper-strap requirement
plus any uncertain-mapping callouts. Output is a watermarked review aid — the
workflow never claims production approval.
"""

from __future__ import annotations

import base64
from typing import Any

from coilforge.package import assemble_drawing_package
from coilforge.schemas.header_prepopulate import CoilType
from coilforge.services.header_prepopulate_engine import copper_strap_requirement


def _coerce_header_count(value: Any) -> int | None:
    """Best-effort int for a header/circuit count; unknown -> None (flags review)."""
    if value is None:
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count > 0 else None


def _compose_copper_strap_summary(coil_type: CoilType, header_count: int | None) -> dict[str, Any]:
    """Turn the R-090 result into a stampable note + a traceable summary."""
    result = copper_strap_requirement(coil_type, header_count)
    if result is None:
        note = "COPPER STRAPS: HEADER COUNT UNKNOWN - REVIEW REQUIRED"
        status = "review_required"
        count = None
    elif result.value is None:  # CWC/HWC — multiplier unconfirmed, never invented
        note = f"COPPER STRAPS: REVIEW REQUIRED - multiplier unconfirmed for {coil_type.value}"
        status = "blocked"
        count = None
    else:
        note = f"COPPER STRAPS REQUIRED: {result.value}"
        status = "required"
        count = result.value
    return {
        "note": note,
        "status": status,
        "count": count,
        "coil_type": coil_type.value,
        "header_count": header_count,
        "confidence": None if result is None else result.confidence.value,
        "evidence_refs": [] if result is None else list(result.evidence_refs),
        "blocked_reason": None if result is None else result.blocked_reason,
    }


def run_drawing_package_workflow(request: dict[str, Any]) -> dict[str, Any]:
    """Assemble ``[Direct Coil drawing] + [CoilForge drawing]`` into one PDF.

    Request keys:
      ``direct_coil_pdf_base64`` (str, required) — the Direct Coil drawing PDF.
      ``coilforge_drawing_svg``  (str, required) — our rendered drawing SVG.
      ``coil_type``              (str, required) — DX | HGRH | CWC | HWC.
      ``header_count``           (int | None)    — drawing header count (1HD-4HD).
      ``review_markups``         (list[str])     — uncertain-mapping callouts.

    The review-aid watermark is always applied here and is NOT caller-suppressible:
    an un-watermarked path is reserved for the future PDF submittal gate, which is
    the only place allowed to promote output past review-aid status.

    Raises ``ValueError`` on missing/invalid inputs (the route maps it to 400).
    """
    request = request or {}

    pdf_b64 = request.get("direct_coil_pdf_base64")
    if not pdf_b64:
        raise ValueError("direct_coil_pdf_base64 is required")
    try:
        direct_coil_pdf = base64.b64decode(pdf_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"direct_coil_pdf_base64 is not valid base64 ({exc})") from exc

    svg = request.get("coilforge_drawing_svg")
    if not svg or not str(svg).strip():
        raise ValueError("coilforge_drawing_svg is required")

    raw_coil_type = request.get("coil_type")
    if not raw_coil_type:
        raise ValueError("coil_type is required (DX | HGRH | CWC | HWC)")
    try:
        coil_type = CoilType(str(raw_coil_type).upper())
    except ValueError as exc:
        raise ValueError(f"unknown coil_type: {raw_coil_type!r}") from exc

    header_count = request.get("header_count")
    if header_count is not None:
        try:
            header_count = int(header_count)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"header_count must be an integer, got {header_count!r}") from exc

    review_markups = [str(line) for line in (request.get("review_markups") or [])]

    copper = _compose_copper_strap_summary(coil_type, header_count)

    package = assemble_drawing_package(
        direct_coil_pdf=direct_coil_pdf,
        coilforge_drawing_svg=str(svg),
        copper_strap_note=copper["note"],
        review_markups=review_markups,
        watermark=True,  # always on for the review-aid route (not caller-suppressible)
    )

    return {
        "package": package.model_dump(),
        "copper_straps": copper,
        # Safety contract surfaced at the workflow boundary (mirrors other routes).
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
        "raw_private_data_returned": False,
    }


def run_quote_package_workflow(request: dict[str, Any]) -> dict[str, Any]:
    """Multi-coil quote package from ONE Direct Coil quote+report+drawing PDF.

    CoilForge extracts every coil (tag + per-coil drawing), inserts our drawing right
    after each coil's source drawing page, and stamps a copper-strap price note above
    each coil's quoted price (note-only — the original quote numbers are never changed).

    Request keys:
      ``source_pdf_base64`` (str, required) — the Direct Coil quote+drawing PDF.
      ``source_id``         (str)           — provenance id for the intake.

    Output is a watermarked review aid; ``export_allowed`` stays False. Raises
    ``ValueError`` on missing/invalid input (the route maps it to 400).
    """
    from coilforge.package.assembler import assemble_multi_coil_package
    from coilforge.package.copper_strap_pricing import copper_strap_price
    from coilforge.workflows.submittal_to_drawing import run_pdf_to_drawing_workflow

    request = request or {}
    pdf_b64 = request.get("source_pdf_base64") or request.get("direct_coil_pdf_base64")
    if not pdf_b64:
        raise ValueError("source_pdf_base64 is required")
    try:
        source_pdf = base64.b64decode(pdf_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"source_pdf_base64 is not valid base64 ({exc})") from exc

    # Prefer the reviewed per-coil state the UI sends after John reviews each coil;
    # only re-extract from the PDF when the caller supplies nothing (back-compat).
    reviewed = request.get("coils")
    if reviewed:
        per_coil = [
            {
                "tag": c.get("tag"),
                "coil_type": c.get("coil_type"),
                "our_svg": c.get("our_svg"),
                "header_count": c.get("header_count"),
            }
            for c in reviewed
        ]
    else:
        drawing_result = run_pdf_to_drawing_workflow(
            source_pdf, source_id=str(request.get("source_id") or "QUOTE-PACKAGE-INTAKE")
        )
        per_coil = []
        for entry in drawing_result.get("pdf_coil_pages") or []:
            template_drawing = (entry.get("workflow") or {}).get("template_drawing") or {}
            extracted = template_drawing.get("extracted") or {}
            per_coil.append(
                {
                    "tag": entry.get("tag"),
                    "coil_type": extracted.get("coil_category"),
                    "our_svg": template_drawing.get("svg"),
                    # No silent ``or 1`` default: an unknown count must flag review,
                    # never be priced as a single header (R-090 / never-invent).
                    "header_count": extracted.get("circuits"),
                }
            )

    _PRICEABLE = {"DX", "HGRH", "CWC", "HWC"}
    coils: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for coil in per_coil:
        category = coil.get("coil_type")
        header_count = _coerce_header_count(coil.get("header_count"))
        price: dict[str, Any] = {}
        if category in _PRICEABLE:
            price = copper_strap_price(CoilType(category), header_count)
        coils.append(
            {
                "tag": coil.get("tag"),
                "coil_type": category,
                "our_svg": coil.get("our_svg"),
                "price_note": price.get("note"),
                "price_total": price.get("total"),
                "price_status": price.get("status"),
            }
        )
        summaries.append(
            {
                "tag": coil.get("tag"),
                "coil_type": category,
                "header_count": header_count,
                "copper_straps": price,
            }
        )

    package = assemble_multi_coil_package(source_pdf=source_pdf, coils=coils)

    return {
        "package": package.model_dump(),
        "coils": summaries,
        "coil_count": len(summaries),
        # Safety contract surfaced at the workflow boundary (mirrors other routes).
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
        "raw_private_data_returned": False,
    }
