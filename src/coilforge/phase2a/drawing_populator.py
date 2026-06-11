from __future__ import annotations

from coilforge.drawing.intent import DrawingIntent, DrawingPreviewResult
from coilforge.phase2a.models import DxHeader1ParameterState
from coilforge.phase2a.renderer import REVIEW_WATERMARK, SvgRenderRequest, render_dx_header1_svg


def build_phase2a_state_from_drawing_intent(
    intent: DrawingIntent,
) -> DxHeader1ParameterState:
    """Adapt a review-required DrawingIntent into the existing Phase 2A renderer state."""

    params = intent.drawing_parameters
    title = intent.title_block
    return DxHeader1ParameterState(
        coil_name=intent.coil_name,
        model_number=str(title.get("model_number", "DIRECT-COIL-DRAFT-PREVIEW")),
        coil_category=str(intent.product_type or "DX"),
        header_type=intent.header_type,
        source_case_id=str(title.get("source_case_id", "DIRECT-COIL-DRAFT")),
        rows=intent.rows_deep,
        fin_height=intent.finned_height,
        fin_length=intent.finned_length,
        fin_density_fpi=intent.fins_per_inch,
        casing_height=float(params["CH"].value),
        casing_length=float(title.get("casing_length") or intent.finned_length),
        casing_depth=float(params["CD"].value),
        top_flange=float(params["TF"].value),
        bottom_flange=float(params["BF"].value),
        return_bend_allowance=float(title.get("return_bend_allowance") or 0),
        coil_hand=intent.coil_hand,
        airflow_direction=intent.airflow_direction,
        return_connection_size=intent.return_connection_size,
        circuiting_display=str(title.get("circuiting_display", "REVIEW REQUIRED")),
        notes=list(intent.notes),
        release_status="review_aid_only",
        drawing_status="generated_with_warnings" if intent.preview_allowed else "generation_blocked",
        observed_oal=title.get("observed_oal"),
        return_header_diameter=title.get("return_header_diameter")
        or _drawing_param_value(params, "HD"),
        distributor_header_diameter=title.get("distributor_header_diameter")
        or _drawing_param_value(params, "HD"),
        return_stub_length=title.get("return_stub_length") or _drawing_param_value(params, "SL"),
        supply_offset_i1=title.get("supply_offset_i1") or _drawing_param_value(params, "I"),
        supply_spacing_s1=title.get("supply_spacing_s1") or _drawing_param_value(params, "S"),
        return_offset_o2=title.get("return_offset_o2") or _drawing_param_value(params, "O"),
        return_spacing_r2=title.get("return_spacing_r2") or _drawing_param_value(params, "R"),
        header_face=title.get("header_face") or _drawing_param_value(params, "HF"),
        return_face=title.get("return_face") or _drawing_param_value(params, "RF"),
        coil_id=title.get("coil_id", ""),
        item_number=title.get("item_number", "001"),
        revision=title.get("revision", "A"),
        quantity=title.get("quantity", "1"),
        drawing_notes=title.get("drawing_notes"),
        header_assemblies=title.get("header_assemblies"),
    )


def render_drawing_intent_preview(intent: DrawingIntent) -> DrawingPreviewResult:
    if not intent.preview_allowed:
        return DrawingPreviewResult(
            intent=intent,
            svg="",
            metadata={
                "drawing_status": "preview_blocked",
                "release_status": "review_aid_only",
                "review_status": intent.review_status,
                "john_review_required": True,
                "export_allowed": False,
                "review_watermark": REVIEW_WATERMARK,
            },
            warnings=["Drawing preview blocked because required review parameters are missing."],
            blocked_fields=list(intent.blocked_reasons),
        )

    state = build_phase2a_state_from_drawing_intent(intent)
    rendered = render_dx_header1_svg(SvgRenderRequest(state=state))
    metadata = {
        **rendered.metadata,
        "review_status": intent.review_status,
        "preview_allowed": intent.preview_allowed,
        "export_allowed": False,
        "source_evidence_summary": intent.source_evidence_summary,
    }
    return DrawingPreviewResult(
        intent=intent,
        svg=rendered.svg,
        metadata=metadata,
        warnings=list(rendered.warnings),
        blocked_fields=list(rendered.blocked_fields),
    )


def _drawing_param_value(params, key: str):
    parameter = params.get(key)
    if parameter is None:
        return None
    return parameter.value
