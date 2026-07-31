from __future__ import annotations

import copy
import hashlib
import io
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

from coilforge.contracts.canonical import ManualOverride
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
    drain_pan_partner_tag,
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


# --- R12b: bounded memoization of the PDF -> drawing workflow ----------------
# Case deep-link and re-analyze flows re-run the SAME submittal PDF repeatedly,
# each time paying 30-60s of OCR/analysis. We memoize the whole workflow keyed on
# sha1(pdf_bytes) PLUS every other argument, because source_id / source_filename /
# cover_page_hint / preview_defaults / title_block are all embedded in the result
# (e.g. source_id -> "BRAIN-CASE-{id}"). Keying on the PDF bytes alone would hand
# back a result stamped with the WRONG source_id -- a silent cross-contamination.
# The stored result is never returned directly (callers mutate it -- see
# web_app.py::workflow_case_to_drawing), so every hit returns a deepcopy.
_WORKFLOW_CACHE_MAXSIZE = 32
_WORKFLOW_CACHE: "OrderedDict[tuple[str, str], dict[str, Any]]" = OrderedDict()


def _workflow_cache_key(
    pdf_bytes: bytes,
    source_id: str,
    source_filename: str | None,
    cover_page_hint: int | None,
    preview_defaults: list[dict[str, Any]] | None,
    title_block: dict[str, Any] | None,
) -> tuple[str, str]:
    pdf_sha1 = hashlib.sha1(pdf_bytes).hexdigest()
    meta = json.dumps(
        [source_id, source_filename, cover_page_hint, preview_defaults, title_block],
        default=str,
        sort_keys=True,
    )
    meta_hash = hashlib.sha256(meta.encode("utf-8")).hexdigest()
    return (pdf_sha1, meta_hash)


def clear_pdf_to_drawing_workflow_cache() -> None:
    """Drop all memoized workflow results (test hygiene / manual invalidation)."""
    _WORKFLOW_CACHE.clear()


def run_pdf_to_drawing_workflow(
    pdf_bytes: bytes,
    *,
    source_id: str = "PDF-UPLOAD-INTAKE-001",
    source_filename: str | None = None,
    cover_page_hint: int | None = None,
    preview_defaults: list[dict[str, Any]] | None = None,
    title_block: dict[str, Any] | None = None,
) -> dict[str, Any]:
    key = _workflow_cache_key(
        pdf_bytes,
        source_id,
        source_filename,
        cover_page_hint,
        preview_defaults,
        title_block,
    )
    cached = _WORKFLOW_CACHE.get(key)
    if cached is not None:
        _WORKFLOW_CACHE.move_to_end(key)
        return copy.deepcopy(cached)
    result = _run_pdf_to_drawing_workflow_uncached(
        pdf_bytes,
        source_id=source_id,
        source_filename=source_filename,
        cover_page_hint=cover_page_hint,
        preview_defaults=preview_defaults,
        title_block=title_block,
    )
    _WORKFLOW_CACHE[key] = result
    _WORKFLOW_CACHE.move_to_end(key)
    while len(_WORKFLOW_CACHE) > _WORKFLOW_CACHE_MAXSIZE:
        _WORKFLOW_CACHE.popitem(last=False)
    return copy.deepcopy(result)


def _run_pdf_to_drawing_workflow_uncached(
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
            hgrh_partner_conn=_hgrh_partner_conn_for(candidate, candidates),
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


def _coil_tag_for_drawing(drawing: dict[str, Any]) -> str | None:
    """The coil tag to stamp on the review-aid drawing, from the already-gated slot
    value (falling back to the as-built extract). Returns None when no real tag exists
    so nothing is drawn (never a blank 'Tag:' or 'REVIEW REQUIRED')."""
    slot_tag = (drawing.get("slot_values") or {}).get("slot.TAG")
    if isinstance(slot_tag, str) and slot_tag.strip():
        return slot_tag.strip()
    extract_tag = (drawing.get("extracted") or {}).get("tag")
    if isinstance(extract_tag, str) and extract_tag.strip():
        return extract_tag.strip()
    return None


def _inject_coil_tag_label(svg: str, tag: str | None) -> str:
    """Re-draw the coil tag INSIDE the cropped drawing region.

    The template's own ``Tag: {{slot.TAG}}`` lives in the bottom title block, which the
    viewBox crop above removes, so the tag would otherwise never render. We stamp it
    top-left inside the retained crop as a top-level ``<text>`` (root user space, no
    transform → absolute coords). Review-aid only; no geometry/frozen files touched."""
    tag = (tag or "").strip()
    if not tag or "</svg>" not in svg:
        return svg
    safe = tag.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    label = (
        f'<text x="{_CROP_X + 6}" y="{_CROP_Y + 15}" font-family="Arial, sans-serif" '
        f'font-size="12" font-weight="bold" fill="#222">Tag: {safe}</text>'
    )
    return svg.replace("</svg>", label + "</svg>", 1)


def _clean_template_svg(
    svg: str, coil_category: str | None = None, tag: str | None = None
) -> str:
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
    svg = _inject_coil_tag_label(svg, tag)
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
# for any genuinely unseeded future line. (Terra V CWC/HWC was withheld by its own
# branch here until 2026-07-28; John released it on the same reasoning — see
# _gate_unregistered_product_line.)
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
    """Force the template result to the omitted state for any product line still listed
    in _UNREGISTERED_PRODUCT_LINES (currently empty — Ventum Plus was removed 2026-07-03
    and now draws via the shared templates). No-op otherwise.

    Terra V CWC/HWC was gated here until 2026-07-28. John released it on the same
    reasoning that un-blocked Ventum Plus: a CoilMaster water-coil drawing has the same
    shape regardless of which Oxygen8 AHU it ships in — the unit only sets the dimension
    VALUES, and those are already computed per product/variant by the engine (the slot
    layer applies the Terra V water specials and R-067 supplies the Terra V vent/drain
    values). So the shared Nova/Ventum-H water template is the correct
    carrier and only the numbers printed into it are Terra-V-specific. Every drawing
    stays a review aid (export_allowed False)."""
    if not isinstance(result, dict):
        return result
    from coilforge.submittal.coilmaster_drawing_extract import resolve_product_line

    family, _variant = resolve_product_line(result.get("product_type"))

    if family in _UNREGISTERED_PRODUCT_LINES:
        label = str(family).replace("_", " ").title()
        _omit_drawing(
            result,
            f"{label} templates are tracked separately and have not been seeded yet — "
            "review required before a drawing can be linked.",
        )
        result["unregistered_product_line"] = family
        return result
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


# The frozen drawing path resolves the hand as
# `ctx.get("coil_hand") or extract.get("hand") or "LH"` (pdf_to_template_drawing.py), so a
# submittal that states no handing silently draws LEFT — and the UI then shows "HAND LH"
# as if it were read from the source. Oxygen8 cover rows carry handing for DX but leave it
# blank for water coils (2949 Ferguson Theatre: CDXC-* = 'Left'/'Right', HHWC-* = ''), so
# this is the normal case for HWC/CWC, not an edge case. The hand picks the LH vs RH
# template, i.e. it mirrors the whole drawing — the one assumption most worth stating.
_DEFAULTED_HAND_REVIEW = (
    "Coil hand was NOT stated in the submittal — the drawing defaults to LH. The hand "
    "mirrors the entire drawing (LH vs RH template), so confirm it before use; set it "
    "in the manual fill panel to redraw the other hand."
)


def _flag_defaulted_coil_hand(
    result: dict[str, Any], ctx: dict[str, Any] | None
) -> dict[str, Any]:
    """Mark a drawing whose hand came from the frozen path's ``or "LH"`` fallback.

    ``ctx`` is REQUIRED and cannot be recovered from ``result``: by the time the frozen
    path returns, the default has already been folded in, so ``extracted["hand"]`` reads
    "LH" for a stated-LH coil and an assumed-LH coil alike. Never blanks the drawing — the
    value stays, labelled as the assumption it is.

    Gated on the resolved hand still being "LH": when the context carries no hand but the
    as-built CoilMaster parse read "RH", that RH cannot have come from the default, so it
    is genuine and must not be labelled an assumption. The residual ambiguity is the other
    way round — an as-built-LH coil is flagged too — and that direction is the safe one
    (it asks the engineer to confirm a hand that is in fact correct, rather than letting a
    silent guess through)."""
    if not isinstance(result, dict) or not result.get("svg"):
        return result
    if (ctx or {}).get("coil_hand"):
        return result
    if str((result.get("extracted") or {}).get("hand") or "").upper() != "LH":
        return result
    result["coil_hand_defaulted"] = True
    result["coil_hand_review"] = _DEFAULTED_HAND_REVIEW
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


def _gate_unseeded_ventum_plus_dx(result: dict[str, Any]) -> dict[str, Any]:
    """Block an un-seeded Ventum+ DX drawing as 'not registered' instead of letting it
    fall back to a shared template. Ventum+ DX distributors mount ConnectionUP (R-032),
    but the shared CoilMaster templates were seeded ConnectionDOWN and the drawing path
    does NOT redraw the distributor by orientation — so a shared fallback would show the
    WRONG distributor direction. A dedicated Ventum+ DX template (seeded from a real UP
    reference) already drew UP and set ``dedicated_family_template``, so it is kept.
    HGRH/HWC/CWC have no distributor and are NOT gated (they still draw via the shared
    template). Runs AFTER :func:`_prefer_dedicated_family_template`; no-op unless a
    drawing was produced from a NON-dedicated (shared) template for a Ventum+ DX coil.

    This gate is about a real but UNSEEDED hand/header, so it must not speak for a
    Ventum+ **HGBP** coil -- that configuration does not exist and has no reference to
    seed. :func:`_gate_hgbp_unsupported_product_line` runs first and omits it, leaving
    the ``svg`` guard here to no-op."""
    if not isinstance(result, dict) or not result.get("svg"):
        return result
    if result.get("dedicated_family_template") == "VENTUM_PLUS":
        return result  # drawn from the seeded UP reference — keep it
    from coilforge.submittal.coilmaster_drawing_extract import resolve_product_line

    family, _ = resolve_product_line(result.get("product_type"))
    category = str((result.get("extracted") or {}).get("coil_category") or "").upper()
    if family == "VENTUM_PLUS" and category == "DX":
        _omit_drawing(
            result,
            "Ventum+ DX drawing template not registered — the distributor mounts "
            "ConnectionUP (R-032), but no seeded Ventum+ DX reference matches this "
            "hand/header and the shared template would draw it ConnectionDOWN. A real "
            "Ventum+ DX reference for this hand/header must be seeded first.",
        )
        result["unregistered_ventum_plus_dx"] = True
    return result


# Hot gas bypass is selectable on Nova and Ventum H ONLY (John, 2026-07-15) -- no other
# product line offers the option, so an HGBP coil resolving to another line means the
# classification is wrong, not that the coil is exotic. The two seeded HGBP templates
# (coilmaster_dx_{lh,rh}_hgbp) are Nova/Ventum-H-class references; lending them to a
# Terra would draw another line's geometry under this coil's tag.
_HGBP_PRODUCT_LINES = {"NOVA", "VENTUM_H"}


def _gate_hgbp_unsupported_product_line(result: dict[str, Any]) -> dict[str, Any]:
    """Omit an HGBP drawing whose product line cannot select the option.

    Runs BEFORE :func:`_gate_unseeded_ventum_plus_dx` on purpose. A Ventum+ DX HGBP coil
    would trip that gate too, but its reason ("no seeded Ventum+ DX reference matches --
    seed one first") reads as a coverage gap someone could close. **Ventum+ DX HGBP is
    not a gap; it is a configuration that does not exist** (John 2026-07-15), so there is
    no reference to seed and this gate must own the message.

    An UNKNOWN line is left alone (see :func:`_flag_hgbp_product_line_unverified`) --
    absence of a detected product code is not evidence of an unsupported one.
    """
    if not isinstance(result, dict) or not result.get("svg"):
        return result
    if str((result.get("extracted") or {}).get("special_feature") or "") != "HGBP":
        return result
    from coilforge.submittal.coilmaster_drawing_extract import resolve_product_line

    family, _ = resolve_product_line(result.get("product_type"))
    if not family or family in _HGBP_PRODUCT_LINES:
        return result
    label = str(family).replace("_", " ").title()
    _omit_drawing(
        result,
        f"Hot gas bypass (HGBP) is selectable on Nova and Ventum H only, but this coil "
        f"resolves to {label} — the seeded HGBP templates are Nova/Ventum-H references "
        "and are not borrowed for another line. Review the product line / the cover "
        "HGBP option before a drawing can be linked.",
    )
    result["unsupported_hgbp_product_line"] = family
    return result


def _flag_hgbp_product_line_unverified(result: dict[str, Any]) -> dict[str, Any]:
    """Warn when an HGBP drawing was produced without a resolved product line.

    HGBP is Nova/Ventum-H only, but ``product_type`` is set only when a model code
    validates, so an undetected line is the common case. Blanking the drawing on that
    absence would kill legitimate Nova HGBP coils whose code merely failed to parse, so
    the drawing stands and the unverified premise is surfaced instead. Once the engineer
    picks the line, the re-derive runs :func:`_gate_hgbp_unsupported_product_line` with
    the fact present. Never blocks -- surfaces the caveat only.
    """
    if not isinstance(result, dict) or not result.get("svg"):
        return result
    if str((result.get("extracted") or {}).get("special_feature") or "") != "HGBP":
        return result
    from coilforge.submittal.coilmaster_drawing_extract import resolve_product_line

    family, _ = resolve_product_line(result.get("product_type"))
    if family:
        return result
    result["hgbp_product_line_warning"] = (
        "Hot gas bypass (HGBP) is selectable on Nova and Ventum H only, but this coil's "
        "product line could not be resolved from its model code — so it is UNVERIFIED "
        "that this coil may carry the option. The HGBP drawing shown is a review aid on "
        "that unconfirmed premise; pick the product line to have it checked."
    )
    return result


def _rerun_slots_with_manual_inputs(
    result: dict[str, Any], spec: dict[str, Any]
) -> Any | None:
    """Human-in-the-loop Tier-A un-gate: re-run ``build_drawing_slots`` in this
    NON-frozen caller with the three engine inputs the frozen ``derive_slot_values``
    path drops (``application`` / ``header_count`` / ``qty_conn_per_header``), and
    merge the recomputed slots into ``result['slot_values']``. Fires ONLY when the
    engineer actually supplied one of those three (so a coil with no manual fill is
    byte-for-byte unchanged — the H4 regression guard). Returns the engine
    ``HeaderPrepopulateResponse`` (for the fill plan / unknown_unit_size), or None
    when the engine can't run (no product / size) or an input is invalid.

    Carries the with-HGRH casing-depth branch (R-072) in the SAME call rather than
    letting ``_apply_hgrh_pairing_cd`` run afterwards: that helper merges its FULL
    recomputed slot set, and it knows nothing about the three Tier-A inputs, so a
    second pass would silently undo the fill it was supposed to complement.
    """
    from coilforge.services.direct_coil_drawing_pipeline import (
        UnknownCoilInputError,
        build_drawing_slots,
    )
    from coilforge.services.drawing_param_resolver import _coerce_float

    ex = result.get("extracted") or {}
    product = result.get("product_type")
    unit_size = result.get("unit_size")
    coil_category = ex.get("coil_category")
    if not (product and unit_size and coil_category):
        return None
    conn = ex.get("return_conn_size")
    if conn is None:
        conn = spec.get("suction_conn_size") or spec.get("return_conn_size")
    partner_conn = (
        _coerce_float(_partner_conn_from_spec(spec))
        if str(coil_category).strip().upper() == "DX"
        else None
    )
    try:
        slots, response = build_drawing_slots(
            coil_type=coil_category,
            product_type=product,
            unit_size=unit_size,
            rows=ex.get("rows"),
            feeds=ex.get("feeds"),
            circuits=spec.get("circuits") or 1,
            suction_conn_size=_coerce_float(conn),
            qty_conn_per_header=spec.get("qty_conn_per_header"),
            application=spec.get("application"),
            header_count=spec.get("header_count"),
            with_hgrh=True if partner_conn is not None else None,
            hgrh_conn_size=partner_conn,
            finned_height=ex.get("finned_height"),
            finned_length=ex.get("finned_length"),
            tag=ex.get("tag"),
        )
    except (UnknownCoilInputError, ValueError):
        return None
    # setdefault: a gated/omitted result may lack the slot_values key. update() is
    # additive/overwrite so a base input the re-run didn't produce can never drop a slot.
    result.setdefault("slot_values", {}).update(slots)
    return response


def _partner_conn_from_spec(spec: dict[str, Any]) -> Any:
    """The reheat partner's connection size for a ``/derive`` spec, or None.

    ``derive`` resolves ONE coil, so the caller ships the sibling coils
    (``sibling_coils: [{tag, conn_size}]``) and the pairing itself is decided HERE by
    the canonical ``drain_pan_partner_tag`` — duplicating that rule in the browser
    would fork the tag-alias table (RHHGRC / RHHGRH / HGRC / HGRH) and drift.
    An explicit ``hgrh_partner_conn_size`` wins, for callers that already know it.
    """
    explicit = spec.get("hgrh_partner_conn_size")
    if explicit is not None:
        return explicit
    siblings = spec.get("sibling_coils")
    tag = spec.get("tag")
    if not isinstance(siblings, list) or not tag:
        return None
    by_tag = {
        str(s.get("tag")): s.get("conn_size")
        for s in siblings
        if isinstance(s, dict) and s.get("tag")
    }
    partner_tag = drain_pan_partner_tag(str(tag), list(by_tag))
    return by_tag.get(partner_tag) if partner_tag else None


def _apply_hgrh_pairing_cd(
    template_drawing: dict[str, Any], hgrh_partner_conn: Any
) -> None:
    """DX-with-reheat casing-depth correction, applied in this NON-frozen caller.

    The frozen ``derive_slot_values`` runs ``build_drawing_slots`` per coil in
    isolation, so a DX paired with an HGRH reheat never takes the with-HGRH R-072
    branch and its CD (and the S = k*CD/(circuits+1) it feeds) comes out low
    (e.g. 7.5 instead of the checklist's 8). Re-run ``build_drawing_slots`` with the
    SAME extracted inputs plus ``with_hgrh``/``hgrh_conn_size`` and merge the
    recomputed CD-family slots back in — mirroring ``_rerun_slots_with_manual_inputs``
    (never edit the frozen path). No-op unless the coil is a DX with a partner
    connection size, so standalone DX / non-DX coils stay byte-for-byte unchanged.
    """
    if not isinstance(template_drawing, dict) or "error" in template_drawing:
        return
    ex = template_drawing.get("extracted") or {}
    if str(ex.get("coil_category") or "").strip().upper() != "DX":
        return
    product = template_drawing.get("product_type")
    unit_size = template_drawing.get("unit_size")
    if not (product and unit_size and hgrh_partner_conn is not None):
        return
    from coilforge.services.direct_coil_drawing_pipeline import (
        UnknownCoilInputError,
        build_drawing_slots,
    )
    from coilforge.services.drawing_param_resolver import _coerce_float

    conn = ex.get("return_conn_size")
    try:
        slots, _resp = build_drawing_slots(
            coil_type="DX",
            product_type=product,
            unit_size=unit_size,
            rows=ex.get("rows"),
            feeds=ex.get("feeds"),
            circuits=ex.get("circuits") or 1,
            suction_conn_size=_coerce_float(conn),
            with_hgrh=True,
            hgrh_conn_size=_coerce_float(hgrh_partner_conn),
            finned_height=ex.get("finned_height"),
            finned_length=ex.get("finned_length"),
            tag=ex.get("tag"),
        )
    except (UnknownCoilInputError, ValueError):
        return
    # Only the CD-family slots change (CD and the S/derived it feeds); every other
    # slot recomputes identically. update() keeps it additive/overwrite.
    merged = template_drawing.setdefault("slot_values", {})
    merged.update(slots)
    # The template SVG (the packet drawing) renders slot.CD / slot.S1/S3/S5, and it
    # was rendered inside the frozen path from the pre-correction slots. Re-populate
    # it from the merged slots so the drawing itself shows CD=8 (not just the panel).
    template_id = template_drawing.get("template_id")
    if template_id and template_drawing.get("svg"):
        from coilforge.template_population.slot_population import populate_template_slots

        repop = populate_template_slots(template_id, merged)
        if repop.svg:
            template_drawing["svg"] = repop.svg
            template_drawing["populated_slots"] = list(repop.populated_slots)
            template_drawing["missing_required_slots"] = list(repop.missing_required_slots)


def _reflect_param_overrides_into_slots(
    result: dict[str, Any], spec: dict[str, Any], circuits: Any
) -> None:
    """Tier-B reflection (1b, John 2026-07-16 — reverses the earlier panel-only rule).

    Merge the engineer's drawing-param overrides into ``result['slot_values']`` and
    re-populate the template SVG so the printed dimension text shows the corrected
    value (not just the panel). Done in THIS non-frozen caller, mirroring
    ``_apply_hgrh_pairing_cd``'s re-population (904-912) — the frozen
    ``pdf_to_template_drawing`` is never touched. Fires ONLY when ``param_overrides``
    are present, so a no-fill derive stays byte-for-byte unchanged (H4 guard).

    Event-sources the before-value: BEFORE merging, it resolves the pristine baseline
    panel (no overrides) and snapshots ``{previous_value, previous_mode}`` per key into
    ``result['manual_override_events']``. The capture ledger reads that snapshot rather
    than recomputing after the fact — once the override lands in ``slot_values`` a later
    override-free re-resolve would read the OVERRIDDEN slot and silently drop the
    correction. ZD (and any param with no slot) is captured as an event but not
    reflected — it is not a drawn dimension.
    """
    overrides_raw = spec.get("param_overrides")
    if not overrides_raw or not isinstance(result, dict) or "error" in result:
        return

    from coilforge.drawing.parameters import DrawingParameterOverride
    from coilforge.services.drawing_param_resolver import (
        PARAM_TO_SLOT,
        _header_slot,
        parameter_set_from_template_drawing,
    )

    try:
        circuits_int = int(circuits) if circuits else None
    except (TypeError, ValueError):
        circuits_int = None

    # Pristine baseline (no overrides) — the machine proposal each override replaces.
    # Resolved BEFORE the merge so the slots it reads are still un-overridden.
    baseline = parameter_set_from_template_drawing(
        result, circuits=circuits_int
    ).parameters

    def _slot_for(key: str) -> str | None:
        if key in PARAM_TO_SLOT:  # base keys incl. HDx1 (has digits, matched first)
            return PARAM_TO_SLOT[key]
        base = key.rstrip("0123456789")
        digits = key[len(base):]
        if digits and int(digits) >= 2:  # logical header key S2/O3/HD2 -> parity slot
            return _header_slot(base, int(digits))
        return None

    slot_values = result.setdefault("slot_values", {})
    events: list[dict[str, Any]] = []
    keys: list[str] = []
    merged_any = False
    for item in overrides_raw:
        try:
            ov = DrawingParameterOverride.model_validate(item)
        except Exception:  # noqa: BLE001 — a bad override is skipped, never a 500
            continue
        if ov.value in (None, ""):
            continue
        base = baseline.get(ov.key)
        slot = _slot_for(ov.key)
        events.append(
            {
                "key": ov.key,
                "slot": slot,
                "previous_value": base.value if base is not None else None,
                "previous_mode": base.mode if base is not None else None,
                "new_value": ov.value,
                "override_reason": ov.override_reason,
                "source_evidence": [se.model_dump() for se in ov.source_evidence],
            }
        )
        keys.append(ov.key)
        if slot is not None:
            slot_values[slot] = ov.value
            merged_any = True

    if events:
        result["manual_override_events"] = events
        result["manual_override_keys"] = keys

    # Re-populate the template SVG from the merged slots (mirrors _apply_hgrh_pairing_cd
    # 904-912) so the drawing itself shows the override. watermark + export_allowed live
    # on the result envelope, not in the slots, so re-population can't flip them.
    if merged_any:
        template_id = result.get("template_id")
        if template_id and result.get("svg"):
            from coilforge.template_population.slot_population import (
                populate_template_slots,
            )

            repop = populate_template_slots(template_id, slot_values)
            if repop.svg:
                result["svg"] = repop.svg
                result["populated_slots"] = list(repop.populated_slots)
                result["missing_required_slots"] = list(repop.missing_required_slots)


def _attach_engine_provenance(result: dict[str, Any], response: Any) -> None:
    """1c seam-A: capture WHICH rule fired + its confidence from the Tier-A-fill engine
    response — the only wired non-frozen path that hands back the HeaderPrepopulateResponse
    (`_rerun_slots_with_manual_inputs`). PDF-analyze is out of scope (its response is
    discarded inside the frozen path). Pure provenance metadata under a single
    ``engine_provenance`` key; the capture ledger writes rule_firing + engine_call from it.
    Never changes a drawn value. No-op when the engine didn't run (response None)."""
    if response is None or not isinstance(result, dict):
        return
    firings: list[dict[str, Any]] = []
    for bucket in (response.values, response.suggestions, response.blocked):
        for field_key, fr in bucket.items():
            conf = fr.confidence
            firings.append(
                {
                    "field_key": field_key,
                    "rule_id": fr.rule_id,
                    "confidence": conf.value if hasattr(conf, "value") else str(conf),
                    "review_required": bool(fr.review_required),
                    "blocked_reason": fr.blocked_reason,
                }
            )
    result["engine_provenance"] = {
        "firings": firings,
        "call": {
            "n_values": len(response.values),
            "n_suggestions": len(response.suggestions),
            "n_blocked": len(response.blocked),
        },
    }


# Engine-input keys carried on a /derive spec that feed the rule engine (Tier A).
_MANUAL_ENGINE_INPUT_KEYS: tuple[str, ...] = (
    "application", "header_count", "qty_conn_per_header",
)


def manual_overrides_from_fills(spec: dict[str, Any]) -> list[ManualOverride]:
    """Build the ``ManualOverride`` audit trail for one /derive fill. Every human
    value is logged review-required (``review_status='unreviewed'``); nothing is
    promoted to confirmed. Engine-input fills note the recompute; param overrides
    note that they are preview-only and never flip ``export_allowed``."""
    reason = str(spec.get("override_reason") or "manual fill (human-in-the-loop)")
    reviewed_by = spec.get("reviewed_by")
    overrides: list[ManualOverride] = []
    for key in _MANUAL_ENGINE_INPUT_KEYS:
        if spec.get(key) is not None:
            overrides.append(
                ManualOverride(
                    target_field=key,
                    override_value=spec.get(key),
                    override_reason=reason,
                    reviewed_by=reviewed_by,
                    review_status="unreviewed",
                    downstream_effects=["rule_engine_recompute"],
                )
            )
    for item in spec.get("param_overrides") or []:
        key = (item or {}).get("key") if isinstance(item, dict) else getattr(item, "key", None)
        value = (item or {}).get("value") if isinstance(item, dict) else getattr(item, "value", None)
        if not key:
            continue
        overrides.append(
            ManualOverride(
                target_field=f"drawing_parameters.{key}",
                override_value=value,
                override_reason=(
                    (item.get("override_reason") if isinstance(item, dict) else None) or reason
                ),
                reviewed_by=reviewed_by,
                review_status="unreviewed",
                downstream_effects=["preview_only", "export_allowed=false"],
            )
        )
    return overrides


def derive_coil_template_drawing(spec: dict[str, Any]) -> dict[str, Any]:
    """Re-derive ONE coil's template drawing given its classification + geometry
    plus an engineer-chosen product line + unit size (the UI product/size picker)
    and any human-in-the-loop manual fills (Tier-A engine inputs + Tier-B param
    overrides).

    With product line + unit size present the rule engine runs, so the dimensions
    (CD/TF/BF/CH/HDx1/HD2/SL/I/O/R) become logic-derived instead of REVIEW
    REQUIRED. Stays review-aid only — the engineer explicitly chose the product.
    Every manual value stays review-required (never promoted to HIGH/confirmed) and
    ``export_allowed`` stays False.
    """
    from coilforge.services.drawing_param_resolver import (
        build_manual_fill_plan,
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
        # Carried through the re-derive so the coating note (R-080/R-081) survives a
        # product/size pick; absent -> no coating -> no note (same fail-closed rule).
        "coating": spec.get("coating"),
        # Carry the submittal spec-panel values back through the re-derive so the
        # right-side panel stays populated once dimensions are logic-derived.
        "panel": spec.get("panel"),
    }
    result = pdf_text_to_template_drawing("", cover_text="", header_context=ctx)

    # Tier-A un-gate (1.1a): only when a genuinely-dropped engine input was supplied —
    # keeps non-manual-fill coils byte-for-byte unchanged (H4). Keeps the engine
    # response for the fill plan (missing_inputs) and unknown_unit_size surfacing.
    fill_response = None
    if any(spec.get(key) is not None for key in _MANUAL_ENGINE_INPUT_KEYS):
        # The Tier-A re-run carries the with-HGRH branch itself (see its docstring).
        fill_response = _rerun_slots_with_manual_inputs(result, spec)
    else:
        # A DX paired with a reheat HGRH takes the with-HGRH casing-depth branch (R-072).
        # Analyze applies it (`_run_candidate_to_drawing_payload`), but this path never
        # did, so ANY manual fill on a reheat-paired DX silently reverted CD 8.125 -> 7.5
        # and dragged the distributor spacing S = k*CD/(circuits+1) with it (John
        # 2026-07-30, caught on the real 2901). The partner's connection size comes from
        # the caller because derive resolves ONE coil and cannot see its siblings.
        _apply_hgrh_pairing_cd(result, _partner_conn_from_spec(spec))

    # 1c seam-A: capture engine provenance (rule_id + confidence per field) from the
    # Tier-A-fill response — the only wired non-frozen path that returns it.
    _attach_engine_provenance(result, fill_response)

    # Tier-B reflection (1b): merge param overrides into slot_values + re-populate the
    # SVG so the drawing shows the corrected dimension, and event-source the pre-override
    # baseline for the correction ledger. No-op unless param_overrides are present.
    _reflect_param_overrides_into_slots(result, spec, ctx.get("circuits"))

    # Refresh the Drawing Parameters panel from the same slot values the re-derived
    # drawing renders (Tier-B param overrides also injected into the panel as mode=
    # 'manual'). Pass the circuit count so multi-header assemblies (I2/S2/...) surface.
    parameter_set = parameter_set_from_template_drawing(
        result, circuits=ctx.get("circuits"), param_overrides=spec.get("param_overrides")
    )
    result["drawing_parameter_set"] = parameter_set.model_dump()

    _gate_unregistered_product_line(result)
    _prefer_dedicated_family_template(result)
    _gate_hgbp_unsupported_product_line(result)
    _gate_unseeded_ventum_plus_dx(result)
    _flag_hgbp_product_line_unverified(result)
    _flag_distributor_orientation_review(result)
    _flag_defaulted_coil_hand(result, ctx)

    # Auto-surface fill plan — built AFTER the gates so a gate-omitted coil surfaces a
    # "drawing withheld" note instead of fill inputs (filling cannot un-gate it).
    result["manual_fill_plan"] = build_manual_fill_plan(
        result, fill_response, parameter_set
    ).model_dump()
    # Audit trail (session store on the result). Kept review-required; never confirmed.
    result["manual_overrides"] = [mo.model_dump() for mo in manual_overrides_from_fills(spec)]
    # Phase 2: echo the sanitized spec-field overrides so the capture ledger records them
    # as (before -> after) corrections at stage 'spec_field'. The engine-relevant fields
    # (circuits/rows/feeds/return_conn_size/coating) are already threaded into ctx above, so
    # the drawing itself recomputes; this is the parallel capture channel.
    if spec.get("spec_overrides"):
        result["spec_overrides"] = spec["spec_overrides"]
    # Phase 2b: attach the per-coil three-way review view (submittal / CoilForge / engineer).
    # Review aid only; the override column reads the event-sourced machine proposal so a
    # corrected field still shows what the engine originally proposed.
    from coilforge.services.three_way_view import build_three_way_view
    result["three_way"] = build_three_way_view(result)
    # Phase 2.1: attach the nearest past coils + John's prior corrections as EVIDENCE (review
    # aid, never auto-applied). Same derive seam as three_way; features_from_result mirrors the
    # ledger WRITE axes so a coil matches its own past. redact drops reason/project_number on
    # this browser surface. Fail-closed: similar_by_features never raises and degrades to an
    # empty/flagged dict (kill switch / no DB / n<50) — see capture.retrieve.
    from coilforge.capture.retrieve import features_from_result, similar_by_features
    try:
        result["case_neighbors"] = similar_by_features(
            features_from_result(result), k=5, same_category=True, redact=True
        )
    except Exception:  # noqa: BLE001 — the panel is a review aid; never let it 500 a derive.
        # similar_by_features already never raises; this also closes features_from_result,
        # so the whole attach is fail-closed (matches the /derive "never a 500" contract).
        result["case_neighbors"] = {"enabled": False, "raw_private_data_returned": False,
                                    "neighbors": []}
    # Safety: a manual fill must never flip export_allowed.
    result["export_allowed"] = False

    if result.get("svg"):
        result["svg"] = _clean_template_svg(
            result["svg"],
            (result.get("extracted") or {}).get("coil_category"),
            _coil_tag_for_drawing(result),
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


# ``ASC`` is EZ Coil's hot-gas-bypass term, but on the drawing it is a COUNT, not a
# flag: the distributor string reads "(1)501-2-3/16-1.5(0 ASC)" where **0 ASC means NO
# hot gas bypass**. A bare "ASC" substring test therefore INVERTS the truth for every
# non-HGBP DX coil whose Drawing Notes reach ``manufacturing_options`` — so only a
# count >= 1 counts. Word boundaries likewise keep "CASCADE" / "economizer bypass"
# from routing an ordinary coil to the HGBP template.
_HGBP_RE = re.compile(
    r"\bHGBP\b"
    r"|\bHOT[\s\-]*GAS[\s\-]*BY[\s\-]?PASS\b"
    r"|\b[1-9]\d*\s*ASC\b",
    re.IGNORECASE,
)


def _detect_hgbp(*texts: str | None) -> bool:
    """Best-effort hot-gas-bypass detection from coil-type/item/option text.

    Also matches the ``Cover option: hot-gas bypass (HGBP) ...`` note that
    ``pdf_intake._candidate_from_cover_row`` attaches to DX candidates when the cover
    page states an HGBP adder — the two sides share the literal ``HGBP`` token, so do
    not reword one without the other.
    """
    return bool(_HGBP_RE.search(" ".join(str(t or "") for t in texts)))


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
        # Gates the coating note (R-080/R-081) -- "do not coat the last 5-6 inches" is
        # meaningless unless a custom coating is actually being applied (John
        # 2026-07-15). Absent on an uncoated coil: Oxygen8 submittals simply do not
        # mention coating when there is none, so a missing value correctly reads as
        # "no coating" and the note is omitted rather than invented.
        "coating": _candidate_field_value(candidate, "manufacturing_options", "coil_coating"),
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


# P1-B (safe subset): the workflow run and the checklist fill each decode the SAME bytes
# with PyPDF2 via _safe_pdf_text (submittal_to_drawing.py + web_app.py). Memoize on the
# bytes so that PyPDF2 decode happens once. NOTE: we deliberately do NOT merge this with
# intake's pdfplumber text -- the drawing extraction (extract_coilmaster_drawing) is tuned
# to PyPDF2's text, so sharing across extractors could change a parsed value. str is
# immutable, so the cached value is returned directly.
_SAFE_PDF_TEXT_CACHE_MAXSIZE = 16
_SAFE_PDF_TEXT_CACHE: "OrderedDict[str, str]" = OrderedDict()


def _safe_pdf_text(pdf_bytes: bytes) -> str:
    key = hashlib.sha1(pdf_bytes).hexdigest()
    cached = _SAFE_PDF_TEXT_CACHE.get(key)
    if cached is not None:
        _SAFE_PDF_TEXT_CACHE.move_to_end(key)
        return cached

    from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "".join((page.extract_text() or "") for page in reader.pages)
    _SAFE_PDF_TEXT_CACHE[key] = text
    _SAFE_PDF_TEXT_CACHE.move_to_end(key)
    while len(_SAFE_PDF_TEXT_CACHE) > _SAFE_PDF_TEXT_CACHE_MAXSIZE:
        _SAFE_PDF_TEXT_CACHE.popitem(last=False)
    return text


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


def _engine_drawing_notes(ctx: dict[str, Any]) -> list[str]:
    """Assemble the engine drawing notes (copper straps / coating / distributor
    extension) for a candidate's resolved context. Returns ``[]`` when the product
    line / unit size is unknown so nothing is invented — the SAME gating the drawing's
    ``slot.NOTES`` uses (``build_drawing_slots`` runs only when product+size+category
    are known), so the paste "Drawing Notes" field and the drawing never diverge."""
    product = ctx.get("product_type")
    unit_size = ctx.get("unit_size")
    coil_category = ctx.get("coil_category")
    if not (product and unit_size and coil_category):
        return []
    from coilforge.services.direct_coil_drawing_pipeline import build_header_request
    from coilforge.services.header_prepopulate_engine import assemble_drawing_notes

    try:
        request = build_header_request(
            coil_type=coil_category,
            product_type=product,
            unit_size=unit_size,
            rows=ctx.get("rows"),
            feeds=ctx.get("feeds"),
            circuits=ctx.get("circuits"),
            # Gates the coating note (R-080/R-081) -- it fires only for a stated,
            # non-NONE coating. Omitted here and the note could never appear at all.
            coating=ctx.get("coating"),
            # Picks the distributor note between R-035b ("Distributor 6" Extension
            # Downwards") and R-035c ("Distributor Down w/ ASC & 6" Extension"). Reuses
            # the SAME special_feature that drove template selection, so this field and
            # the chosen template agree on whether the coil is HGBP.
            #
            # NOTE the sibling `slot.NOTES` does NOT: `build_drawing_slots` takes no
            # hot_gas_bypass argument, so it always emits the R-035b wording. That is
            # inert today -- no template.svg carries a `{{slot.NOTES}}` placeholder, so
            # slot.NOTES renders nowhere -- but it IS a trap: redacting a template's
            # hardcoded NOTES text to a real slot would start printing "Downwards" on
            # HGBP coils. Thread hot_gas_bypass through build_drawing_slots first.
            hot_gas_bypass=(ctx.get("special_feature") == "HGBP"),
        )
    except Exception:  # never break the workflow on an engine-input mismatch
        return []
    return assemble_drawing_notes(request)


def _hgrh_partner_conn_for(selected_candidate, candidates) -> Any:
    """The reheat-HGRH partner's connection size for a DX candidate (else None).

    Feeds the with-HGRH casing-depth correction (``_apply_hgrh_pairing_cd``). Needs
    the sibling candidates (drain-pan partner lives on another cover row), so it is
    resolved here where the full list is available, not inside the per-candidate
    context builder. None for a standalone DX or any non-DX coil.
    """
    if _coil_category_from_type(_candidate_attr_value(selected_candidate, "coil_type")) != "DX":
        return None
    tag = _candidate_attr_value(selected_candidate, "tag")
    if not tag:
        return None
    all_tags = [
        t for t in (_candidate_attr_value(c, "tag") for c in candidates) if t
    ]
    partner_tag = drain_pan_partner_tag(str(tag), all_tags)
    if not partner_tag:
        return None
    partner = next(
        (c for c in candidates if _candidate_attr_value(c, "tag") == partner_tag), None
    )
    if partner is None or _coil_category_from_type(
        _candidate_attr_value(partner, "coil_type")
    ) != "HGRH":
        return None
    return _candidate_connection_size(partner)


def _run_candidate_to_drawing_payload(
    selected_candidate,
    *,
    pdf_intake_summary: dict[str, Any] | None,
    source_id: str,
    preview_defaults: list[dict[str, Any]] | None,
    title_block: dict[str, Any] | None,
    pdf_text: str | None = None,
    hgrh_partner_conn: Any = None,
) -> dict[str, Any]:
    direct_result = _run_candidate_to_direct_draft_workflow(
        selected_candidate,
        pdf_intake_summary=pdf_intake_summary,
    )
    # Assemble the engine drawing notes once, up front, so BOTH the paste "Drawing
    # Notes" field and the SVG title block draw from the same source (never diverge).
    # Computed off a safe copy of the candidate context — [] when product is unknown.
    try:
        notes_ctx = _template_header_context_from_candidate(selected_candidate)
    except Exception:
        notes_ctx = {}
    engine_notes_list = _engine_drawing_notes(notes_ctx)
    draft_payload = direct_result["direct_coil_input_draft"]
    draft = DirectCoilInputDraft.model_validate(draft_payload)
    parameter_set = resolve_drawing_parameters(
        draft,
        default_preview_values=[
            PreviewDefaultValue.model_validate(item)
            for item in (preview_defaults or DEFAULT_PREVIEW_VALUES)
        ],
    )
    preview_title_block = title_block or {
        "coil_name": direct_result["selected_candidate_summary"]["tag"]
        or "PDF INTAKE REVIEW PREVIEW",
        "model_number": "PDF-INTAKE-DRAFT-PREVIEW",
        "source_case_id": source_id,
        "product_type": "DX",
        "coil_type": "DX_HEADER1_WORKFLOW_CANDIDATE",
    }
    if engine_notes_list and not preview_title_block.get("drawing_notes"):
        preview_title_block = {
            **preview_title_block,
            "drawing_notes": "; ".join(engine_notes_list),
        }
    preview = render_direct_coil_svg_preview(
        draft,
        parameter_set,
        title_block=preview_title_block,
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
        _gate_hgbp_unsupported_product_line(template_drawing)
        _gate_unseeded_ventum_plus_dx(template_drawing)
        _flag_hgbp_product_line_unverified(template_drawing)
        _flag_distributor_orientation_review(template_drawing)
        _flag_defaulted_coil_hand(template_drawing, ctx)
        # DX-with-reheat casing-depth correction (R-072 with-HGRH branch). Runs on the
        # RAW populated SVG, before _clean_template_svg / schematic / panel below, so
        # every downstream artifact shows the corrected CD. No-op unless DX + partner.
        _apply_hgrh_pairing_cd(template_drawing, hgrh_partner_conn)
    if isinstance(template_drawing, dict) and template_drawing.get("svg"):
        template_drawing["svg"] = _clean_template_svg(
            template_drawing["svg"],
            (template_drawing.get("extracted") or {}).get("coil_category"),
            _coil_tag_for_drawing(template_drawing),
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

    # Auto-surface fill plan so a blocked coil shows "fill these to complete the
    # drawing" on the very first analyze (before any /derive). Built from the
    # template drawing's review_items + the panel's blocked params (no engine
    # response here — the resolver falls back to the review_items strings).
    if isinstance(template_drawing, dict) and "error" not in template_drawing:
        from coilforge.services.drawing_param_resolver import build_manual_fill_plan

        template_drawing["manual_fill_plan"] = build_manual_fill_plan(
            template_drawing, None, panel_parameter_set
        ).model_dump()

    # Surface the engine-computed drawing dimensions (already rendered on the SVG)
    # in the paste-ready "DRAWING / DIMENSION" review table by wiring them through
    # the canonical record. Rebuild ONLY the review surface; the drawing and its
    # parameter panel are unchanged. Every value stays review-required.
    engine_dims = _engine_drawing_dims(panel_parameter_set)
    # Surface the same assembled notes on the paste "Drawing Notes" field via a
    # DEDICATED manufacturing_options key (never distributor_notes, which drives the
    # drawing's distributor callout). One newline-joined string; review-required.
    # Retry the notes with the product line + unit size the DRAWING actually resolved.
    # `notes_ctx` comes from the candidate, and a candidate can lack product/size while the
    # drawing still resolves them from the full-PDF model-code scan — which is exactly the
    # water-coil case (2949 Ferguson HHWC-1: ctx has no product_type/unit_size, the drawing
    # resolves TERRA V / 040). `_engine_drawing_notes` returns [] without them, so the coil
    # drew its vent/drain note on slot.NOTES while the paste "Drawing Notes" field read
    # unmapped — the exact divergence that function's docstring promises cannot happen.
    # Only fills a gap: a candidate that already resolved its own product is untouched.
    if not engine_notes_list and isinstance(template_drawing, dict):
        resolved_ctx = dict(notes_ctx)
        for key in ("product_type", "unit_size"):
            if not resolved_ctx.get(key) and template_drawing.get(key):
                resolved_ctx[key] = template_drawing[key]
        if not resolved_ctx.get("coil_category"):
            resolved_ctx["coil_category"] = (
                template_drawing.get("extracted") or {}
            ).get("coil_category")
        engine_notes_list = _engine_drawing_notes(resolved_ctx)
    engine_notes = "\n".join(engine_notes_list) if engine_notes_list else None
    if engine_dims or engine_notes:
        augmented = _run_candidate_to_direct_draft_workflow(
            selected_candidate,
            pdf_intake_summary=pdf_intake_summary,
            engine_dims=engine_dims,
            engine_notes=engine_notes,
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
    engine_notes: str | None = None,
) -> dict[str, Any]:
    canonical_result = map_submittal_candidate_to_canonical_result(
        selected_candidate, engine_dims=engine_dims, engine_notes=engine_notes
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


def _stamp_missing_drawing_tag(workflow: dict[str, Any], tag: str) -> None:
    """Ensure this coil's review-aid drawing carries its tag.

    ``page.tag`` resolves from the candidate OR the cover row, but the per-candidate
    drawing is stamped only from the candidate — so a coil whose tag lives only on the
    cover row leaves the drawing untagged (John then hand-writes it on the quote). Stamp
    the resolved ``page.tag`` here. No-op when the drawing already shows a tag (so we never
    double-stamp), when there is no drawing svg, or when ``tag`` is only the positional
    ``Coil N`` placeholder (never stamp a fake tag)."""
    template_drawing = workflow.get("template_drawing")
    if not isinstance(template_drawing, dict) or not template_drawing.get("svg"):
        return
    if _coil_tag_for_drawing(template_drawing):
        return
    if not tag or re.fullmatch(r"Coil \d+", tag):
        return
    template_drawing["svg"] = _inject_coil_tag_label(template_drawing["svg"], tag)


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
        _stamp_missing_drawing_tag(workflow, tag)
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
