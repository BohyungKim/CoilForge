from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

from coilforge.direct_coil import map_canonical_to_direct_coil_draft
from coilforge.direct_coil.draft import DirectCoilInputDraft
from coilforge.direct_coil.paste_ready_fields import build_direct_coil_paste_ready_surface
from coilforge.direct_coil.readiness import build_direct_coil_readiness_report
from coilforge.drawing import (
    PreviewDefaultValue,
    render_direct_coil_svg_preview,
    resolve_drawing_parameters,
)
from coilforge.submittal import extract_submittal_candidates_from_text
from coilforge.submittal.pdf_intake import (
    _normalize_handing,
    extract_coil_candidate_from_pdf_bytes,
)
from coilforge.submittal.to_canonical import map_submittal_candidate_to_canonical_result


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SANITIZED_TEXT_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "submittal_text_dx_header1_default.txt"
)
DEFAULT_PREVIEW_VALUES: tuple[dict[str, Any], ...] = (
    {"key": "CD", "value": 5.5},
    {"key": "BF", "value": 0.63},
    {"key": "TF", "value": 0.63},
    {"key": "CH", "value": 13.25},
    {"key": "HD", "value": 3.5},
    {"key": "SL", "value": 8.0},
    {"key": "I", "value": 3.0},
    {"key": "S", "value": 2.75},
    {"key": "O", "value": 2.0},
    {"key": "R", "value": 0.63},
    {"key": "HF", "value": 1.5},
    {"key": "RF", "value": 1.5},
)


def build_default_demo_workflow_input() -> dict[str, Any]:
    sanitized_text = DEFAULT_SANITIZED_TEXT_PATH.read_text(encoding="utf-8")
    return {
        "input": {
            "source_id": "SANITIZED-SOURCE-DOC-INTAKE-001",
            "submittal_text": sanitized_text,
            "title_block": {
                "coil_name": "SANITIZED WORKFLOW PREVIEW",
                "model_number": "DIRECT-COIL-DRAFT-PREVIEW",
                "source_case_id": "SANITIZED-WORKFLOW-DEMO",
                "product_type": "DX",
                "coil_type": "DX_HEADER1_WORKFLOW_CANDIDATE",
                "casing_length": 18.0,
                "return_bend_allowance": 1.75,
                "circuiting_display": "2 Feed / 24 Pass",
                "drawing_notes": "Copper Straps Required",
                "observed_oal": 20.25,
                # Positional/header dims now come from the Drawing Parameters set
                # (the single source of truth); they are intentionally NOT pinned
                # here so the drawing reflects the resolved/engine values.
                "header_assemblies": [
                    {
                        "ID": 1,
                        "IsSupply": True,
                        "IsDistributor": True,
                        "HD": 4.5,
                        "SL": [0.0, 0.0, 0.0],
                        "SR": 2.75,
                        "IO": [3.0, 0.0, 0.0],
                        "Diameter": 0.88,
                        "ConnectionSize": [0.0, 0.0, 0.0],
                    },
                    {
                        "ID": 2,
                        "IsSupply": False,
                        "IsDistributor": False,
                        "HD": 3.5,
                        "SL": [8.0, 0.0, 0.0],
                        "SR": 0.625,
                        "IO": [2.0, 0.0, 0.0],
                        "Diameter": 0.625,
                        "ConnectionSize": [0.625, 0.0, 0.0],
                    },
                ],
                "coil_id": "581401",
                "item_number": "001",
                "revision": "A",
                "quantity": 1,
            },
            "preview_defaults": list(DEFAULT_PREVIEW_VALUES),
            # Header engine context. product_type/unit_size are not on the
            # Direct Coil form; in the real flow they come from the submittal /
            # unit context (Track B). NOVA/B20 are documented demo assumptions
            # (NOVA matches the as-built TF/BF=0.625; geometry values do not
            # depend on size for this DX slice).
            "header_context": {
                "coil_type": "DX",
                "product_type": "NOVA",
                "unit_size": "B20",
                "circuits": 1,
            },
        },
        "summary": {
            "input_type": "sanitized_text",
            "raw_private_data_included": False,
            "pdf_parser_enabled": False,
            "ocr_enabled": False,
            "export_enabled": False,
        },
    }


def run_submittal_to_direct_draft_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    candidates = _extract_candidates(payload)
    selected_candidate = candidates[0]
    canonical_result = map_submittal_candidate_to_canonical_result(selected_candidate)
    draft = map_canonical_to_direct_coil_draft(canonical_result.record)
    readiness = build_direct_coil_readiness_report(draft)
    paste_ready = build_direct_coil_paste_ready_surface(draft)

    return {
        "candidates": [candidate.model_dump() for candidate in candidates],
        "selected_candidate_summary": _candidate_summary(selected_candidate),
        "canonical_summary": {
            "record_id": canonical_result.record.record_id,
            "validation_status": canonical_result.summary.validation_status,
            "review_required_fields": list(canonical_result.summary.review_required_fields),
            "blocked_fields": list(canonical_result.summary.blocked_fields),
            "unmapped_field_count": canonical_result.summary.unmapped_field_count,
        },
        "direct_coil_input_draft": draft.model_dump(),
        "readiness_report": readiness.model_dump(),
        "direct_coil_paste_ready": paste_ready.model_dump(),
        "validation": {
            "workflow_status": "blocked" if readiness.summary_counts["blocked"] else "review_required",
            "export_status": draft.export_status,
            "raw_private_data_returned": False,
            "drawing_approval_claimed": False,
        },
    }


def _inject_extra_drawing_params(parameter_set: Any, engine_values: list[Any]) -> None:
    """Add drawing-output params beyond the registry (e.g. HDx1 distributor HD)."""
    from coilforge.drawing.parameters import DrawingParameter
    from coilforge.services.drawing_param_resolver import EXTRA_DRAWING_PARAMS

    for value in engine_values:
        if value.key in EXTRA_DRAWING_PARAMS:
            parameter_set.parameters[value.key] = DrawingParameter(
                key=value.key,
                label=value.key,
                value=value.value,
                unit=value.unit,
                mode="default",
                status="review_required",
                review_required=True,
            )


def run_submittal_to_drawing_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    from coilforge.services.drawing_param_resolver import engine_preview_values

    direct_result = run_submittal_to_direct_draft_workflow(payload)
    draft_payload = direct_result["direct_coil_input_draft"]
    draft = DirectCoilInputDraft.model_validate(draft_payload)

    static_defaults = [
        PreviewDefaultValue.model_validate(item)
        for item in payload.get("preview_defaults", [])
    ]
    generation_report: dict[str, Any] = {
        "source": "static_default",
        "connected": [],
        "not_connected": {},
    }
    header_context = payload.get("header_context") or {}
    if header_context.get("product_type") and header_context.get("unit_size"):
        # Generate parameters from the header engine; static defaults fill only
        # the keys the engine has no logic for (CH, ZD, S, ...).
        engine_values, generation_report = engine_preview_values(
            draft,
            coil_type=header_context.get("coil_type", "DX"),
            product_type=header_context["product_type"],
            unit_size=header_context["unit_size"],
            circuits=header_context.get("circuits"),
            ez_json=header_context.get("ez_json"),
        )
        merged = {value.key: value for value in static_defaults}
        for value in engine_values:  # engine precedence
            merged[value.key] = value
        default_preview_values = list(merged.values())
    else:
        engine_values = []
        default_preview_values = static_defaults

    parameter_set = resolve_drawing_parameters(
        draft,
        default_preview_values=default_preview_values,
    )
    _inject_extra_drawing_params(parameter_set, engine_values)
    preview = render_direct_coil_svg_preview(
        draft,
        parameter_set,
        title_block=payload.get("title_block") or {},
    )

    return {
        **direct_result,
        "drawing_parameter_set": parameter_set.model_dump(),
        "drawing_parameter_generation": generation_report,
        "drawing_intent": preview.intent.model_dump(),
        "svg": preview.svg,
        "metadata": preview.metadata,
        "validation": {
            **direct_result["validation"],
            "preview_allowed": preview.intent.preview_allowed,
            "export_allowed": preview.intent.export_allowed,
            "drawing_status": preview.metadata.get("drawing_status"),
            "blocked_fields": list(preview.blocked_fields),
        },
    }


def run_pdf_to_direct_draft_workflow(
    pdf_bytes: bytes,
    *,
    source_id: str = "PDF-UPLOAD-INTAKE-001",
    source_filename: str | None = None,
    cover_page_hint: int | None = None,
) -> dict[str, Any]:
    intake = extract_coil_candidate_from_pdf_bytes(
        pdf_bytes,
        source_id=source_id,
        source_filename=source_filename,
        cover_page_hint=cover_page_hint,
    )
    candidates = intake.cover_candidates or [intake.candidate]
    workflows = [
        _run_candidate_to_direct_draft_workflow(
            candidate,
            pdf_intake_summary=_pdf_summary_for_candidate(
                intake.summary.model_dump(),
                candidate,
            ),
        )
        for candidate in candidates
    ]
    selected_index = _selected_candidate_index(candidates, intake.candidate)
    selected_result = dict(workflows[selected_index])
    selected_result["candidates"] = [candidate.model_dump() for candidate in candidates]
    selected_result["pdf_coil_pages"] = _pdf_coil_pages(
        workflows,
        intake.summary.cover_page_rows,
    )
    return selected_result


def run_pdf_to_drawing_workflow(
    pdf_bytes: bytes,
    *,
    source_id: str = "PDF-UPLOAD-INTAKE-001",
    source_filename: str | None = None,
    cover_page_hint: int | None = None,
    preview_defaults: list[dict[str, Any]] | None = None,
    title_block: dict[str, Any] | None = None,
) -> dict[str, Any]:
    intake = extract_coil_candidate_from_pdf_bytes(
        pdf_bytes,
        source_id=source_id,
        source_filename=source_filename,
        cover_page_hint=cover_page_hint,
    )
    candidates = intake.cover_candidates or [intake.candidate]
    try:
        pdf_text = _safe_pdf_text(pdf_bytes)
    except Exception:  # text extraction is best-effort; classification still works
        pdf_text = ""
    workflows = [
        _run_candidate_to_drawing_payload(
            candidate,
            pdf_intake_summary=_pdf_summary_for_candidate(
                intake.summary.model_dump(),
                candidate,
            ),
            source_id=source_id,
            preview_defaults=preview_defaults,
            title_block=title_block,
            pdf_text=pdf_text,
        )
        for candidate in candidates
    ]
    selected_index = _selected_candidate_index(candidates, intake.candidate)
    selected_result = dict(workflows[selected_index])
    selected_result["candidates"] = [candidate.model_dump() for candidate in candidates]
    selected_result["pdf_coil_pages"] = _pdf_coil_pages(
        workflows,
        intake.summary.cover_page_rows,
    )
    # Each candidate now carries its own linked template_drawing (built from the
    # submittal classification); the selected candidate's is surfaced top-level.
    return selected_result


# Dimension label codes that the CoilMaster template prints next to each value
# (e.g. "3.5 HD2"). For direct-coil ordering John wants numbers only, so the cleaner
# strips the trailing " LABEL" from the blue dimension callouts (fill="#1c0a80").
_DIM_LABELS = (
    "HDx1", "HD2", "SL2", "OAL", "BF", "CD", "CH", "CL", "FH", "FL",
    "HF", "I1", "O2", "R2", "RB", "RF", "S1", "TF",
)
_CALLOUT_LABEL_RE = re.compile(
    r'(fill="#1c0a80"[^>]*><tspan[^>]*>)([^<]*?) (?:' + "|".join(_DIM_LABELS) + r')(</tspan>)'
)

# Crop window (CoilMaster sheet is 792x612; all templates share this layout). Selecting
# just the drawing region clips away the sheet chrome that lives outside it — the right
# material panel, the bottom dim table + title block, and the top-left notes — leaving the
# geometry + dimensions only (image #7). Tuned against the blue dim-callout bounds.
_CROP_X, _CROP_Y, _CROP_W, _CROP_H = 40, 128, 527, 372
_VIEWBOX_RE = re.compile(r'viewBox="0 0 792 612"')
_SIZE_RE = re.compile(r'(<svg[^>]*?)width="792" height="612"')


def _clean_template_svg(svg: str) -> str:
    """Clean a populated CoilMaster template SVG to the direct-coil ordering view John
    wants (image #7):

    1. **Numbers-only** dimension callouts — drop the label codes, keep the value
       (``3.5 HD2`` -> ``3.5``). Scoped to the blue dim callouts so the materials panel /
       bottom dim table / title block text are untouched.
    2. **No chrome** — crop the ``viewBox`` to the drawing region, clipping the right
       material panel, the bottom dim table + title block, and the top-left notes.

    Pure string transform; the review watermark and ``export_allowed`` flags are untouched
    (they sit outside the crop, so they no longer render — safety is enforced server-side
    in the API payload regardless). Dimension re-centering is layered on next.
    """
    if not svg:
        return svg
    svg = _CALLOUT_LABEL_RE.sub(r"\1\2\3", svg)
    svg = _VIEWBOX_RE.sub(f'viewBox="{_CROP_X} {_CROP_Y} {_CROP_W} {_CROP_H}"', svg)
    svg = _SIZE_RE.sub(rf'\1width="{_CROP_W}" height="{_CROP_H}"', svg)
    return svg


def _attach_parametric_schematic(result: dict[str, Any]) -> None:
    """Attach the parametric, to-scale geometry+dimensions drawing (numbers-only) built
    from the same gated ``slot_values``. This is the drawing the UI shows for direct-coil
    ordering: front + header/side views, dims at computed datums, no sheet chrome.
    Review-aid only (``export_allowed=False`` + watermark). Never breaks the response.
    """
    from coilforge.drawing.schematic_renderer import render_scale_schematic

    ex = result.get("extracted") or {}
    slot_values = result.get("slot_values") or {}
    try:
        schem = render_scale_schematic(
            slot_values,
            coil_category=str(ex.get("coil_category") or "DX"),
            coil_hand=str(ex.get("hand") or "LH"),
            header_type=str(ex.get("header_type") or "Header 1"),
            special_feature=ex.get("special_feature"),
        )
    except Exception as exc:  # a drawing-engine issue must never break the workflow
        result["parametric_drawing"] = {"error": str(exc)}
        return
    result["parametric_drawing"] = {
        "front_svg": schem.svg,
        "side_svg": schem.side_svg,
        "omitted_features": list(schem.omitted_features),
        "export_allowed": schem.export_allowed,
        "watermark": schem.watermark,
        "metadata": schem.metadata,
    }


def derive_coil_template_drawing(spec: dict[str, Any]) -> dict[str, Any]:
    """Re-derive ONE coil's template drawing given its classification + geometry
    plus an engineer-chosen product line + unit size (the UI product/size picker).

    With product line + unit size present the rule engine runs, so the dimensions
    (CD/TF/BF/CH/HDx1/HD2/SL/I/O/R) become logic-derived instead of REVIEW
    REQUIRED. Stays review-aid only — the engineer explicitly chose the product.
    """
    from coilforge.services.drawing_param_resolver import (
        parameter_set_from_template_drawing,
    )
    from coilforge.submittal.pdf_to_template_drawing import pdf_text_to_template_drawing

    ctx = {
        "coil_category": spec.get("coil_category"),
        "coil_hand": spec.get("coil_hand"),
        "circuits": spec.get("circuits") or 1,
        "special_feature": spec.get("special_feature"),
        "tag": spec.get("tag"),
        "rows": spec.get("rows"),
        "feeds": spec.get("feeds"),
        "finned_height": spec.get("finned_height"),
        "finned_length": spec.get("finned_length"),
        "suction_conn_size": spec.get("suction_conn_size") or spec.get("return_conn_size"),
        "product_type": spec.get("product_type"),
        "unit_size": spec.get("unit_size"),
        # Carry the submittal spec-panel values back through the re-derive so the
        # right-side panel stays populated once dimensions are logic-derived.
        "panel": spec.get("panel"),
    }
    result = pdf_text_to_template_drawing("", cover_text="", header_context=ctx)
    # Refresh the Drawing Parameters panel from the same slot values the re-derived
    # drawing renders, so picking a product line + unit size updates BOTH.
    result["drawing_parameter_set"] = parameter_set_from_template_drawing(result).model_dump()
    if result.get("svg"):
        result["svg"] = _clean_template_svg(result["svg"])
    _attach_parametric_schematic(result)
    return result


def _coil_category_from_type(coil_type: str | None) -> str | None:
    """Map a submittal coil-type string to the drawing catalog's category code.

    Mirrors the inverse of pdf_intake._COIL_TYPE_BY_PREFIX; tolerant of the
    title-cased / abbreviated forms real submittals use.
    """
    text = str(coil_type or "").upper()
    if not text:
        return None
    if "CHILLED" in text or "CCW" in text or "CWC" in text:
        return "CWC"
    if "HOT WATER" in text or "HHW" in text or "PHW" in text or "HWC" in text:
        return "HWC"
    if "HGRH" in text or "HGRC" in text or "REHEAT" in text:
        return "HGRH"
    if "DX" in text or "COOLING" in text:
        return "DX"
    return None


def _detect_hgbp(*texts: str | None) -> bool:
    """Best-effort hot-gas-bypass detection from coil-type/item/option text."""
    blob = " ".join(str(t or "") for t in texts).upper()
    return "HGBP" in blob or "HOT GAS BYPASS" in blob or "BYPASS" in blob or "ASC" in blob


def _header_count_from_type(header_type: str | None) -> int | None:
    match = re.search(r"(\d+)", str(header_type or ""))
    return int(match.group(1)) if match else None


def _template_header_context_from_candidate(candidate) -> dict[str, Any]:
    """Build the authoritative classification + engine inputs for the template
    drawing from an already-resolved submittal candidate.

    Classification (category/hand/header/HGBP) drives template selection; geometry
    feeds the engine where it can run. product_type/unit_size are intentionally
    omitted unless a real CoilForge product line + unit size are known — the
    candidate's product_type (e.g. "DX") is a coil family, not a product line, so
    forcing it would invent engineering context. With them absent the engine stays
    gated and dimensions remain REVIEW REQUIRED.
    """
    coil_type = _candidate_attr_value(candidate, "coil_type")
    item_note = " ".join(candidate.notes or [])
    options_blob = " ".join(
        str(fv.value) for fv in (candidate.manufacturing_options or {}).values()
    )
    hand_raw = _candidate_field_value(candidate, "connections", "coil_hand")
    header_type = _candidate_attr_value(candidate, "header_type")
    circuits = (
        _candidate_field_value(candidate, "geometry", "circuits")
        or _header_count_from_type(header_type)
        or 1
    )

    ctx: dict[str, Any] = {
        "coil_category": _coil_category_from_type(coil_type),
        "circuits": circuits,
        "tag": _candidate_attr_value(candidate, "tag"),
        "rows": _candidate_field_value(candidate, "geometry", "rows_deep"),
        "feeds": _candidate_field_value(candidate, "geometry", "number_of_feeds"),
        "finned_height": _candidate_field_value(candidate, "geometry", "finned_height"),
        "finned_length": _candidate_field_value(candidate, "geometry", "finned_length"),
        "suction_conn_size": _candidate_connection_size(candidate),
        # Submittal-stated right-side spec panel values (materials, weight,
        # circuiting, connection). Mapped review-required; independent of the
        # rule engine (which only drives the dimension geometry).
        "panel": _candidate_panel(candidate),
    }
    if hand_raw:
        ctx["coil_hand"] = "RH" if _normalize_handing(str(hand_raw)) == "Right" else "LH"
    if _detect_hgbp(coil_type, item_note, options_blob):
        ctx["special_feature"] = "HGBP"
    # Derive the CoilForge product line + unit size from the submittal's product/
    # model code (e.g. "TR_C_040" -> Terra H / 040, R-076 validated) so the rule
    # engine runs without a manual pick. Review-aid only; the engineer can still
    # override in the product/size picker. Left absent when no code validates.
    from coilforge.submittal.coilmaster_drawing_extract import detect_product_and_size

    det_line, det_size = detect_product_and_size(
        " ".join(filter(None, [str(ctx.get("tag") or ""), item_note]))
    )
    if det_line:
        ctx["product_type"] = det_line
    if det_size:
        ctx["unit_size"] = det_size
    return ctx


def _candidate_connection_size(candidate) -> Any:
    """First stated connection size, in canonical-key order (return wins, then
    supply/inlet/outlet). Keys match coilforge.submittal.rules targets."""
    for key in (
        "return_connection_size",
        "supply_connection_size",
        "inlet_connection_size",
        "outlet_connection_size",
        "connection_size",
    ):
        value = _candidate_field_value(candidate, "connections", key)
        if value not in (None, ""):
            return value
    return None


# Unit tokens that are genuine dimensional units (vs. the overloaded material-name
# the submittal normaliser stows in FieldValue.unit, e.g. "Copper"/"Aluminium").
_DIMENSIONAL_UNITS = {
    "in", "lbs", "lb", "degf", "f", "cfm", "fpm", "mbh", "psi", "iwg", "inwg",
    "pct", "%", "gpm", "ft", "cuin", "ftwg", "fps", "kw", "v", "hz",
}


def _candidate_panel(candidate) -> dict[str, Any]:
    """Right-side specification-panel values pulled straight from the submittal
    candidate. Display-ready strings; every value stays review-required."""

    def field(group: str, key: str):
        grp = getattr(candidate, group, {}) or {}
        return grp.get(key)

    def plain(group: str, key: str) -> Any:
        fv = field(group, key)
        return None if fv is None else fv.value

    def material(group: str, key: str) -> str | None:
        fv = field(group, key)
        if fv is None or fv.value in (None, ""):
            return None
        value = fv.value
        text = (
            str(int(value))
            if isinstance(value, float) and value.is_integer()
            else str(value)
        )
        unit = str(fv.unit or "").strip()
        # The normaliser parks a trailing material name in `unit` (e.g.
        # "0.016 Copper" -> value=0.016, unit="Copper"); re-join it. Real
        # dimensional units are dropped (the slot block doesn't show them).
        if unit and unit.lower() not in _DIMENSIONAL_UNITS:
            return f"{text} {unit}"
        return text

    panel = {
        "tube_material": material("materials_construction", "tube_material"),
        "tube_surface": plain("materials_construction", "tube_surface"),
        "fin_material": material("materials_construction", "fin_material"),
        "fin_surface": plain("materials_construction", "fin_surface"),
        "fins_per_inch": plain("geometry", "fins_per_inch"),
        "casing_material": material("materials_construction", "casing_material"),
        "header_material": material("materials_construction", "header_material"),
        "dry_weight": plain("performance", "coil_weight_lbs"),
        "internal_volume": plain("performance", "internal_volume_cuin"),
        "feeds": plain("geometry", "number_of_feeds"),
        "circuits": plain("geometry", "circuits"),
        "conn_size": _candidate_connection_size(candidate),
        "distributor_notes": plain("manufacturing_options", "distributor_notes"),
    }
    return {key: value for key, value in panel.items() if value not in (None, "")}


def _candidate_attr_value(candidate, attr: str) -> Any:
    field = getattr(candidate, attr, None)
    return None if field is None else field.value


def _safe_pdf_text(pdf_bytes: bytes) -> str:
    from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "".join((page.extract_text() or "") for page in reader.pages)


def _run_candidate_to_drawing_payload(
    selected_candidate,
    *,
    pdf_intake_summary: dict[str, Any] | None,
    source_id: str,
    preview_defaults: list[dict[str, Any]] | None,
    title_block: dict[str, Any] | None,
    pdf_text: str | None = None,
) -> dict[str, Any]:
    direct_result = _run_candidate_to_direct_draft_workflow(
        selected_candidate,
        pdf_intake_summary=pdf_intake_summary,
    )
    draft_payload = direct_result["direct_coil_input_draft"]
    draft = DirectCoilInputDraft.model_validate(draft_payload)
    parameter_set = resolve_drawing_parameters(
        draft,
        default_preview_values=[
            PreviewDefaultValue.model_validate(item)
            for item in (preview_defaults or DEFAULT_PREVIEW_VALUES)
        ],
    )
    preview = render_direct_coil_svg_preview(
        draft,
        parameter_set,
        title_block=title_block
        or {
            "coil_name": direct_result["selected_candidate_summary"]["tag"]
            or "PDF INTAKE REVIEW PREVIEW",
            "model_number": "PDF-INTAKE-DRAFT-PREVIEW",
            "source_case_id": source_id,
            "product_type": "DX",
            "coil_type": "DX_HEADER1_WORKFLOW_CANDIDATE",
        },
    )
    generation_report = {
        "source": "static_default",
        "connected": [],
        "not_connected": {},
        "note": "PDF path uses static preview defaults; engine wiring pending product/size.",
    }

    # Link THIS candidate to its drawing template using the classification the
    # submittal intake already resolved (coil type / hand / header qty / HGBP),
    # rather than the as-built model-number parse a submittal does not satisfy.
    template_drawing: dict[str, Any]
    try:
        from coilforge.submittal.pdf_to_template_drawing import (
            pdf_text_to_template_drawing,
        )

        ctx = _template_header_context_from_candidate(selected_candidate)
        template_drawing = pdf_text_to_template_drawing(
            pdf_text or "",
            cover_text=pdf_text or "",
            header_context=ctx,
        )
    except Exception as exc:  # never break the workflow on extraction issues
        template_drawing = {"error": str(exc)}

    if isinstance(template_drawing, dict) and template_drawing.get("svg"):
        template_drawing["svg"] = _clean_template_svg(template_drawing["svg"])
    if isinstance(template_drawing, dict) and template_drawing.get("slot_values"):
        _attach_parametric_schematic(template_drawing)

    # The Drawing Parameters panel mirrors the template drawing's slot values (the
    # single source of truth the drawing renders), so the panel and the drawing
    # never diverge. Fall back to the static-default parameter set only when no
    # template/slots are available.
    if isinstance(template_drawing, dict) and template_drawing.get("slot_values"):
        from coilforge.services.drawing_param_resolver import (
            parameter_set_from_template_drawing,
        )

        panel_parameter_set = parameter_set_from_template_drawing(template_drawing)
    else:
        panel_parameter_set = parameter_set

    return {
        **direct_result,
        "drawing_parameter_set": panel_parameter_set.model_dump(),
        "drawing_parameter_generation": generation_report,
        "drawing_intent": preview.intent.model_dump(),
        "svg": preview.svg,
        "metadata": preview.metadata,
        "template_drawing": template_drawing,
        "validation": {
            **direct_result["validation"],
            "preview_allowed": preview.intent.preview_allowed,
            "export_allowed": preview.intent.export_allowed,
            "drawing_status": preview.metadata.get("drawing_status"),
            "blocked_fields": list(preview.blocked_fields),
        },
    }


def _extract_candidates(payload: dict[str, Any]):
    source_id = payload.get("source_id", "SANITIZED-SOURCE-DOC-INTAKE-001")
    submittal_text = payload.get("submittal_text")
    if submittal_text is None:
        submittal_text = build_default_demo_workflow_input()["input"]["submittal_text"]
    return extract_submittal_candidates_from_text(str(submittal_text), source_id=source_id)


def _run_candidate_to_direct_draft_workflow(
    selected_candidate,
    *,
    pdf_intake_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_result = map_submittal_candidate_to_canonical_result(selected_candidate)
    draft = map_canonical_to_direct_coil_draft(canonical_result.record)
    readiness = build_direct_coil_readiness_report(draft)
    paste_ready = build_direct_coil_paste_ready_surface(draft)

    return {
        "candidates": [selected_candidate.model_dump()],
        "selected_candidate_summary": _candidate_summary(selected_candidate),
        "canonical_summary": {
            "record_id": canonical_result.record.record_id,
            "validation_status": canonical_result.summary.validation_status,
            "review_required_fields": list(canonical_result.summary.review_required_fields),
            "blocked_fields": list(canonical_result.summary.blocked_fields),
            "unmapped_field_count": canonical_result.summary.unmapped_field_count,
        },
        "direct_coil_input_draft": draft.model_dump(),
        "readiness_report": readiness.model_dump(),
        "direct_coil_paste_ready": paste_ready.model_dump(),
        "pdf_intake_summary": pdf_intake_summary,
        "validation": {
            "workflow_status": "blocked" if readiness.summary_counts["blocked"] else "review_required",
            "export_status": draft.export_status,
            "raw_private_data_returned": False,
            "raw_pdf_stored": False,
            "drawing_approval_claimed": False,
        },
    }


def _candidate_summary(candidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "tag": None if candidate.tag is None else candidate.tag.value,
        "quantity": None if getattr(candidate, "quantity", None) is None else candidate.quantity.value,
        "review_status": candidate.review_status,
        "review_required_fields": list(candidate.review_required_fields),
        "blocked_fields": list(candidate.blocked_fields),
        "unmapped_field_count": len(candidate.unmapped_fields),
    }


def _selected_candidate_index(candidates, selected_candidate) -> int:
    selected_tag = _candidate_summary(selected_candidate)["tag"]
    for index, candidate in enumerate(candidates):
        if _candidate_summary(candidate)["tag"] == selected_tag:
            return index
    return 0


def _pdf_summary_for_candidate(summary: dict[str, Any], candidate) -> dict[str, Any]:
    candidate_summary = _candidate_summary(candidate)
    candidate_summary_fields = {
        "selected_candidate_id": candidate_summary["candidate_id"],
        "selected_tag": candidate_summary["tag"],
        "selected_quantity": candidate_summary["quantity"],
        "selected_handing": _candidate_field_value(candidate, "connections", "coil_hand"),
    }
    return {
        **summary,
        **candidate_summary_fields,
    }


def _pdf_coil_pages(
    workflows: list[dict[str, Any]],
    cover_rows: list[Any],
) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    for index, workflow in enumerate(workflows):
        summary = workflow["selected_candidate_summary"]
        cover_row = cover_rows[index] if index < len(cover_rows) else None
        cover_payload = (
            cover_row.model_dump()
            if hasattr(cover_row, "model_dump")
            else (cover_row or {})
        )
        tag = summary.get("tag") or cover_payload.get("tag") or f"Coil {index + 1}"
        quantity = summary.get("quantity") or cover_payload.get("quantity")
        pages.append(
            {
                "page_id": f"pdf-coil-{index + 1}-{_page_id_slug(tag)}",
                "index": index,
                "tag": tag,
                "quantity": quantity,
                "coil_type": cover_payload.get("item") or "",
                "product_type": cover_payload.get("product_type") or "",
                "coil_format": cover_payload.get("coil_format") or "",
                "handing": summary.get("handing") or cover_payload.get("handing") or "",
                "cover_page_number": cover_payload.get("page_number"),
                "cover_row_number": cover_payload.get("row_number"),
                "workflow": workflow,
            }
        )
    return pages


def _page_id_slug(value: Any) -> str:
    return "".join(
        char.lower() if char.isalnum() else "-"
        for char in str(value or "coil")
    ).strip("-")


def _candidate_field_value(candidate, group_name: str, field_key: str) -> Any:
    group = getattr(candidate, group_name, {}) or {}
    field = group.get(field_key)
    return None if field is None else field.value
