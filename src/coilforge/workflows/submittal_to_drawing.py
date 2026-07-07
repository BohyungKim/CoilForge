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
from coilforge.drawing.label_authority import direct_coil_label
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
    """Add drawing-output params beyond the registry: the distributor HD (HDx1) and
    the logical header-2+ assemblies (I2/S2/O2/R2/HD2/ZD2, ...) which are not
    registry fields. All stay review-required (never auto-drawn)."""
    from coilforge.drawing.parameters import DrawingParameter
    from coilforge.services.drawing_param_resolver import (
        EXTRA_DRAWING_PARAMS,
        is_multi_header_param_key,
    )

    for value in engine_values:
        if value.key in EXTRA_DRAWING_PARAMS or is_multi_header_param_key(value.key):
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


# CoilMaster dim callouts print "value LABEL" (e.g. "3.5 HD2", "4.13 SL1", "1.25 X").
# John 2026-06-25 ("valuemap" view): keep the value AND its label together, in the existing
# drawing style, so each dimension reads "this number is for this label" — making it easy to
# check positions. This reverses the earlier numbers-only strip. Keeping the full pair
# preserves the original callout bounding box, so the mirrored-hand (matrix(-1 ...)) x-shift
# the numbers-only mode needed is no longer required — the text renders at its seeded
# position. The label is the final uppercase-led token (<=5 chars); for a blank slot the
# value is "REVIEW REQUIRED", which we replace with the label alone so the dim stays
# identified (no value yet).
_CALLOUT_RE = re.compile(
    r'(fill="#1c0a80"[^>]*\btransform="matrix\(\s*(-?1)\b[^"]*"[^>]*><tspan)([^>]*)(>)'
    r"([^<]*?) ([A-Za-z][A-Za-z0-9]{0,4})(</tspan>)"
)


def _clean_callout(m: "re.Match[str]", coil_category: str | None = None) -> str:
    head, _sign, attrs, gt, value, label, close = m.groups()
    # Direct Coil label authority (John 2026-06-26): rewrite the baked EZ label to its
    # Direct Coil form (e.g. "I" -> "I1", "HD1" -> "HD2"); identity for already-canonical
    # labels. Labels only — the value is never touched (EZ numbers stay until re-seed).
    # coil_category disambiguates SL1 (HGRH keeps its slot-driven supply SL1; CWC -> SL2).
    label = direct_coil_label(label, coil_category)
    if value.strip() == "REVIEW REQUIRED":
        # No value yet — show just the label so the dimension is still identified.
        return f"{head}{attrs}{gt}{label}{close}"
    # Keep "value label" (existing CoilMaster style) at the original position.
    return f"{head}{attrs}{gt}{value} {label}{close}"


def apply_label_authority(svg: str, coil_category: str | None = None) -> str:
    """Rewrite blue dim-callout labels to their Direct Coil form (labels only; values and
    positions untouched). Shared by ``_clean_template_svg`` (the live drawing) and the
    preview generator so both stay in sync. Pure string transform. ``coil_category``
    (DX/HGRH/CWC/HWC) lets the authority keep HGRH's slot-driven SL1 as SL1."""
    if not svg:
        return svg
    return _CALLOUT_RE.sub(lambda m: _clean_callout(m, coil_category), svg)

# Crop the CoilMaster sheet down to the geometry+dimensions section only (John's
# target view). Derived from the UNION of the visible-geometry bounding box across
# all 22 seeded templates (x[116,616] y[25,489]), clamped so the right edge stops
# just before the spec panel (x>=657) and the bottom stops just before the
# "Casing Style…" chrome line (y~495). This frames every category/hand/header —
# including the wider/taller 2HD/3HD/4HD multi-header layouts — without clipping
# geometry, while leaving the panel / dim table / title block / notes off-frame
# (still present in the SVG, just outside the viewBox = invisible).
_CROP_X, _CROP_Y, _CROP_W, _CROP_H = 110, 19, 542, 473
_VIEWBOX_RE = re.compile(r'viewBox="0 0 792 612"')
_SIZE_RE = re.compile(r'(<svg[^>]*?)width="792" height="612"')

# Two chrome blocks sit *inside* the geometry crop rectangle and so cannot be removed
# by the viewBox crop alone — they have to be dropped at the element level (still on the
# rendered copy only; the template file is untouched):
#   1. the top-left fabrication-notes block (COLLARED HOLES / LIFTING LUGS /
#      "DISTRIBUTOR N HAS 6\" EXTENSION") — the only bold text anchored far-left/top, and
#      on multi-header sheets it shares the geometry's vertical band so a rectangle can't
#      exclude it without clipping the drawing; it would otherwise render clipped mid-word.
#   2. the "Coil ID = … / Casing Style: … / Stacking Flanges: …" metadata line, whose
#      glyph tops poke just above the crop's bottom edge.
# Both are sheet metadata, not dimensional drawing data, and are absent from John's target
# geometry-only view.
# "DIST LIST" is the distributor-schedule heading; its companion entries are literal
# "(1)501-4-3/16-4 OD:5/8" part-number lines. Both are sheet metadata (and un-redacted
# as-built data), not dimensional drawing data, so they are dropped from the review view.
_CHROME_TEXT_TOKENS = ("Coil ID", "Casing Style", "Stacking Flanges", "DIST LIST")
_DIST_ENTRY_RE = re.compile(r"\(\s*\d+\s*\)\d{2,}-\d")  # distributor entry "(1)501-4-..."
_TEXT_ELEMENT_RE = re.compile(r"<text\b[^>]*>.*?</text>", re.DOTALL)
# NB: tspan x/y attributes can hold multiple space-separated coordinates
# (e.g. x="47.99 54.78 62.09 …"); capture only the first number of each.
_FIRST_TSPAN_RE = re.compile(r'<tspan\b[^>]*\by="(-?\d+(?:\.\d+)?)[^"]*"[^>]*\bx="(-?\d+(?:\.\d+)?)')


def _is_intruding_chrome(text_el: str) -> bool:
    """True if a ``<text>`` element is sheet chrome that lands inside the geometry crop."""
    if any(tok in text_el for tok in _CHROME_TEXT_TOKENS):
        return True
    if _DIST_ENTRY_RE.search(text_el):  # distributor-schedule entry block
        return True
    # Top-left fabrication-notes block: bold + anchored far-left in the top band.
    if 'font-weight="bold"' in text_el or "Arial,Bold" in text_el:
        m = _FIRST_TSPAN_RE.search(text_el)
        if m:
            y_screen = float(m.group(1)) + 612.0  # text transform translate(0, 612)
            x = float(m.group(2))
            if x < 130.0 and y_screen < 160.0:
                return True
    return False


def _strip_intruding_chrome(svg: str) -> str:
    return _TEXT_ELEMENT_RE.sub(
        lambda m: "" if _is_intruding_chrome(m.group(0)) else m.group(0), svg
    )


def _clean_template_svg(svg: str, coil_category: str | None = None) -> str:
    """Clean a populated CoilMaster template SVG to the direct-coil ordering view John
    wants (image #7):

    1. **Value + label** dimension callouts — keep the value next to its label code
       (``3.5 HD2`` stays ``3.5 HD2``; a blank slot reads as just the label). Scoped to the
       blue dim callouts so the materials panel / bottom dim table / title block are untouched.
    2. **No chrome** — crop the ``viewBox`` to the drawing region, clipping the right
       material panel, the bottom dim table + title block, and the top-left notes.
    3. **Drop intruding chrome** — remove the two chrome blocks that fall *inside* the
       crop rectangle (the top-left fabrication notes and the Coil ID / Casing Style
       metadata line) so only the geometry + dimensions remain.

    Pure string transform; the review watermark and ``export_allowed`` flags are untouched
    (they sit outside the crop, so they no longer render — safety is enforced server-side
    in the API payload regardless). Dimension re-centering is layered on next.
    """
    if not svg:
        return svg
    svg = apply_label_authority(svg, coil_category)
    # Drop every blank-slot "REVIEW REQUIRED" placeholder from the review-aid drawing.
    # All such text is slot-placeholder output (the source template carries no literal
    # watermark); the export gate (export_allowed=False) is enforced server-side.
    svg = svg.replace("REVIEW REQUIRED", "")
    svg = _strip_intruding_chrome(svg)
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


# Product lines with no CoilMaster template of their own were tracked here and
# forced to "not registered" rather than borrowing another line's artwork.
# Ventum Plus was removed 2026-07-03 after John reviewed its reference selection
# PDFs: they are CoilMaster EZ-Coil drawings in the SAME DX/HGRH/CWC/HWC format
# the shared templates were seeded from (a CoilMaster coil drawing is identical
# regardless of the Oxygen8 AHU it ships in — the unit only sets casing dims,
# which the engine already computes per product+size). So — like Nova, Terra, and
# Ventum H — Ventum Plus now draws through the existing product-agnostic templates
# with its own engine-computed dimensions. The set is kept as the extension point
# for any genuinely unseeded future line. (Terra V CWC/HWC stays withheld by its
# own branch below — no seeded Terra V water reference.)
_UNREGISTERED_PRODUCT_LINES: set[str] = set()


def _omit_drawing(result: dict[str, Any], reason: str) -> dict[str, Any]:
    """Blank the template result to the omitted/not-generated state with a reason.
    No drawing is borrowed from another product line/variant; the empty svg makes the
    omission surface loudly downstream (assembler not_inserted_reason, UI message)."""
    result["svg"] = ""
    result["template_id"] = None
    result["template_found"] = False
    result["generation_allowed"] = False
    result["template_status"] = None
    result["not_registered_reason"] = reason
    return result


def _gate_unregistered_product_line(result: dict[str, Any]) -> dict[str, Any]:
    """Force the template result to the omitted state for combos that must not draw:
    (1) any product line still listed in _UNREGISTERED_PRODUCT_LINES (currently empty —
        Ventum Plus was removed 2026-07-03 and now draws via the shared templates), and
    (2) Terra V CWC/HWC (no seeded Terra V water reference — Terra V DX/HGRH still draw).
    No drawing is borrowed from another line/variant. No-op otherwise."""
    if not isinstance(result, dict):
        return result
    from coilforge.submittal.coilmaster_drawing_extract import resolve_product_line

    family, variant = resolve_product_line(result.get("product_type"))
    category = str((result.get("extracted") or {}).get("coil_category") or "").upper()

    # Ventum+ : no seeded template for ANY category.
    if family in _UNREGISTERED_PRODUCT_LINES:
        label = str(family).replace("_", " ").title()
        _omit_drawing(
            result,
            f"{label} templates are tracked separately and have not been seeded yet — "
            "review required before a drawing can be linked.",
        )
        result["unregistered_product_line"] = family
        return result

    # Terra V CWC/HWC : deliberately omitted (no seeded Terra V water reference). Terra V
    # DX/HGRH and Terra H water are NOT gated — only the (TERRA_V, water) combo.
    if variant == "TERRA_V" and category in {"CWC", "HWC"}:
        return _omit_drawing(
            result,
            "Terra V CWC/HWC drawings are omitted — no seeded Terra V water-coil "
            "reference; review required before a drawing can be linked.",
        )
    return result


# The distributor orientation physically differs by product family: Nova/Terra/
# Ventum H mount the DX distributor ConnectionDown (R-031), but Ventum+ mounts it
# ConnectionUp (R-032, HIGH). The shared CoilMaster templates were seeded from
# ConnectionDown reference drawings and the drawing path does NOT consume
# `dist_orientation` (it is computed by the engine but never wired into slots /
# template geometry). So a Ventum+ DX review-aid draws the distributor DOWN — the
# wrong direction. Until the parametric engine consumes dist_orientation, flag it
# loudly so the wrong orientation is never trusted silently. Review aid only.
_DIST_ORIENTATION_REVIEW = (
    "Distributor orientation (R-032): Ventum+ DX distributors mount ConnectionUP, "
    "but this review-aid reuses the shared CoilMaster template seeded ConnectionDOWN "
    "and the drawing path does not yet redraw the distributor by orientation. The "
    "distributor direction shown is NOT representative for Ventum+ — do not rely on "
    "it. Review required."
)


def _flag_distributor_orientation_review(result: dict[str, Any]) -> dict[str, Any]:
    """Attach a loud review-required warning when a DRAWN Ventum+ DX drawing would
    show the distributor in the seeded ConnectionDown orientation instead of the
    Ventum+ ConnectionUp (R-032). No-op unless a drawing was actually produced and
    the coil is Ventum+ DX. Never blocks the drawing — surfaces the caveat only."""
    if not isinstance(result, dict) or not result.get("svg"):
        return result
    # A dedicated Ventum+ template (seeded from a real UP reference) already draws the
    # distributor ConnectionUP, so the caveat no longer applies — only the shared
    # ConnectionDown template needs it.
    if result.get("dedicated_family_template") == "VENTUM_PLUS":
        return result
    from coilforge.submittal.coilmaster_drawing_extract import resolve_product_line

    family, _ = resolve_product_line(result.get("product_type"))
    category = str((result.get("extracted") or {}).get("coil_category") or "").upper()
    if family == "VENTUM_PLUS" and category == "DX":
        result["distributor_orientation_warning"] = _DIST_ORIENTATION_REVIEW
    return result


def _prefer_dedicated_family_template(result: dict[str, Any]) -> dict[str, Any]:
    """When a dedicated per-family template is seeded for this coil's (family, category,
    hand, header, special), re-select + re-populate the drawing from it instead of the
    shared bucket. No-op unless a drawing was produced AND a dedicated bucket exists
    (VENTUM_PLUS_TEMPLATES). Keeps the frozen pdf_to_template_drawing path untouched —
    this runs in the workflow layer and only calls the public populate_template_slots."""
    if not isinstance(result, dict) or not result.get("svg"):
        return result
    from coilforge.submittal.coilmaster_drawing_extract import resolve_product_line
    from coilforge.template_population.catalog import (
        TemplateSelectionRequest,
        select_drawing_template,
    )
    from coilforge.template_population.slot_population import populate_template_slots

    family, _ = resolve_product_line(result.get("product_type"))
    if not family:
        return result
    ex = result.get("extracted") or {}
    sel = select_drawing_template(
        TemplateSelectionRequest(
            supplier="coilmaster",
            coil_category=str(ex.get("coil_category") or ""),
            coil_hand=str(ex.get("hand") or "LH"),
            header_type=ex.get("header_type"),
            special_feature=ex.get("special_feature"),
            product_family=family,
        )
    )
    # Only swap when a genuinely dedicated bucket matched (not the shared fallback) and
    # it differs from what the frozen path already drew.
    if not (sel.found and sel.entry and sel.entry.product_family == family):
        return result
    if sel.template_id == result.get("template_id"):
        return result
    repop = populate_template_slots(sel.template_id, result.get("slot_values") or {})
    if not repop.svg:  # re-population blocked -> keep the shared drawing, never blank it
        return result
    result["svg"] = repop.svg
    result["template_id"] = sel.template_id
    result["source_case_id"] = sel.entry.source_case_id
    result["dedicated_family_template"] = family
    return result


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
    # drawing renders, so picking a product line + unit size updates BOTH. Pass the
    # circuit count so multi-header assemblies (I2/S2/...) surface for 2HD+ coils.
    result["drawing_parameter_set"] = parameter_set_from_template_drawing(
        result, circuits=ctx.get("circuits")
    ).model_dump()
    _gate_unregistered_product_line(result)
    _prefer_dedicated_family_template(result)
    _flag_distributor_orientation_review(result)
    if result.get("svg"):
        result["svg"] = _clean_template_svg(
            result["svg"], (result.get("extracted") or {}).get("coil_category")
        )
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
    category = _coil_category_from_type(coil_type)
    circuit_count = (
        _candidate_field_value(candidate, "geometry", "circuits")
        or _header_count_from_type(header_type)
        or 1
    )
    feeds = _candidate_field_value(candidate, "geometry", "number_of_feeds")
    circuits = circuit_count
    # ``circuits`` drives the "Header N" template key downstream. For water coils
    # that is wrong: CWC/HWC are 1HD only (MVP taxonomy), and their
    # geometry.circuits is electrical circuiting (e.g. "Circuits: 4"), NOT a
    # header count. Left as-is it produces a non-existent "Header 4" bucket and
    # the drawing fails template selection. Force the single header (also the
    # correct single supply/return connection geometry for a water coil); the
    # true circuiting is still surfaced via the spec panel / paste fields.
    if category in ("CWC", "HWC"):
        # Water coils state "Circuits", not "Total Feeds". The engine's `feeds`
        # input gates the HIGH io/hd values (R-060/R-062: multi-feed -> 2.3125/4;
        # single-feed R-064 -> N/A). Without it the engine holds io/hd as
        # review suggestions and slot.I1/O2/HD2 stay blank. Derive feeds from the
        # stated circuit count when feeds is absent so those slots populate.
        if not feeds:
            feeds = circuit_count
        circuits = 1

    ctx: dict[str, Any] = {
        "coil_category": category,
        "circuits": circuits,
        "tag": _candidate_attr_value(candidate, "tag"),
        "rows": _candidate_field_value(candidate, "geometry", "rows_deep"),
        "feeds": feeds,
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


# Logical drawing-dimension keys with a paste-ready "DRAWING / DIMENSION" review
# field (mirrors to_canonical._REVIEWABLE_DRAWING_DIMS / the canonical_rules map).
_REVIEWABLE_DRAWING_DIMS: tuple[str, ...] = (
    "CD", "BF", "TF", "CH", "RF", "HF", "SL", "I", "S", "O", "R", "HD", "ZD",
)


def _engine_drawing_dims(parameter_set: Any) -> dict[str, Any]:
    """Engine-derived drawing dimensions (from the SAME slot values the SVG renders)
    that have a Direct Coil review field. Only dimensions the engine actually
    produced are returned; surfaced review-required downstream, never confirmed."""
    params = getattr(parameter_set, "parameters", None) or {}
    out: dict[str, Any] = {}
    for key in _REVIEWABLE_DRAWING_DIMS:
        param = params.get(key)
        value = getattr(param, "value", None) if param is not None else None
        if value is not None:
            out[key] = value
    return out


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

    if isinstance(template_drawing, dict):
        _gate_unregistered_product_line(template_drawing)
        _prefer_dedicated_family_template(template_drawing)
        _flag_distributor_orientation_review(template_drawing)
    if isinstance(template_drawing, dict) and template_drawing.get("svg"):
        template_drawing["svg"] = _clean_template_svg(
            template_drawing["svg"],
            (template_drawing.get("extracted") or {}).get("coil_category"),
        )
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

        panel_parameter_set = parameter_set_from_template_drawing(
            template_drawing, circuits=ctx.get("circuits")
        )
    else:
        panel_parameter_set = parameter_set

    # Surface the engine-computed drawing dimensions (already rendered on the SVG)
    # in the paste-ready "DRAWING / DIMENSION" review table by wiring them through
    # the canonical record. Rebuild ONLY the review surface; the drawing and its
    # parameter panel are unchanged. Every value stays review-required.
    engine_dims = _engine_drawing_dims(panel_parameter_set)
    if engine_dims:
        augmented = _run_candidate_to_direct_draft_workflow(
            selected_candidate,
            pdf_intake_summary=pdf_intake_summary,
            engine_dims=engine_dims,
        )
        for key in (
            "canonical_summary",
            "direct_coil_input_draft",
            "readiness_report",
            "direct_coil_paste_ready",
            "validation",
        ):
            direct_result[key] = augmented[key]

    return {
        **direct_result,
        "drawing_parameter_set": panel_parameter_set.model_dump(),
        "drawing_parameter_generation": generation_report,
        "drawing_intent": preview.intent.model_dump(),
        "svg": preview.svg,
        "metadata": preview.metadata,
        "template_drawing": template_drawing,
        # Engine inputs for the mechanical-fit check (read by _pdf_coil_pages -> the
        # per-coil fit_inputs the /api/mechanical-fit endpoint consumes).
        "template_header_context": ctx,
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
    engine_dims: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical_result = map_submittal_candidate_to_canonical_result(
        selected_candidate, engine_dims=engine_dims
    )
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
                "fit_inputs": _fit_inputs_from_ctx(
                    workflow.get("template_header_context"), tag
                ),
                "workflow": workflow,
            }
        )
    return pages


def _fit_inputs_from_ctx(ctx: dict[str, Any] | None, tag: str) -> dict[str, Any] | None:
    """Compact mechanical-fit inputs for one coil (consumed by /api/mechanical-fit).

    ``coil_category`` (DX/HGRH/CWC/HWC) is the engine coil_type token. product_type
    (product line) / unit_size may be absent when no model code validated — the fit
    endpoint then reports the coil as needing those inputs rather than guessing.
    """
    if not ctx:
        return None
    return {
        "tag": ctx.get("tag") or tag,
        "coil_type": ctx.get("coil_category"),
        "product_type": ctx.get("product_type"),
        "unit_size": ctx.get("unit_size"),
        "finned_height": ctx.get("finned_height"),
        "finned_length": ctx.get("finned_length"),
        "rows": ctx.get("rows"),
        "feeds": ctx.get("feeds"),
        "circuits": ctx.get("circuits"),
        "suction_conn_size": ctx.get("suction_conn_size"),
    }


def _page_id_slug(value: Any) -> str:
    return "".join(
        char.lower() if char.isalnum() else "-"
        for char in str(value or "coil")
    ).strip("-")


def _candidate_field_value(candidate, group_name: str, field_key: str) -> Any:
    group = getattr(candidate, group_name, {}) or {}
    field = group.get(field_key)
    return None if field is None else field.value
