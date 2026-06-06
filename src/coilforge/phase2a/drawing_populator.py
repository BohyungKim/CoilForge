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
        casing_length=float(params.get("SL").value or intent.finned_length),
        casing_depth=float(params["CD"].value),
        top_flange=float(params["TF"].value),
        bottom_flange=float(params["BF"].value),
        return_bend_allowance=float(params.get("R").value or 0),
        coil_hand=intent.coil_hand,
        airflow_direction=intent.airflow_direction,
        return_connection_size=intent.return_connection_size,
        circuiting_display=str(title.get("circuiting_display", "REVIEW REQUIRED")),
        notes=list(intent.notes),
        release_status="review_aid_only",
        drawing_status="generated_with_warnings" if intent.preview_allowed else "generation_blocked",
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
