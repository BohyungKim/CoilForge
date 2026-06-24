from pathlib import Path
from typing import Any

from fastapi import Body, HTTPException, Request
from fastapi.encoders import jsonable_encoder

from coilforge.adapters import load_sanitized_ez_json
from coilforge.compatibility import (
    build_compatibility_diff_review_packet,
    build_decision_capture_template,
    build_decision_matrix_review_surface,
    build_field_decision_matrix,
    build_john_decision_capture_packet,
    build_mapping_rule_registry,
    build_reconciliation_plan,
    compare_submittal_and_ez,
)
from coilforge.phase2a.app import app
from coilforge.phase2a.fixtures import load_default_dx_header1_fixture
from coilforge.phase2a.ui_state import build_phase2b_default_ui_state
from coilforge.phase2a.renderer import DEFAULT_VIEWBOX, REVIEW_WATERMARK
from coilforge.review import build_default_review_packet, build_review_packet
from coilforge.submittal.po_based_intake import build_po_based_intake
from coilforge.submittal import SubmittalCoilCandidate, load_submittal_candidate_fixture
from coilforge.submittal.po_logic_bridge import build_po_logic_intake_summary
from coilforge.workflows import (
    build_default_demo_workflow_input,
    derive_coil_template_drawing,
    run_drawing_package_workflow,
    run_pdf_to_direct_draft_workflow,
    run_pdf_to_drawing_workflow,
    run_quote_package_workflow,
    run_submittal_to_direct_draft_workflow,
    run_submittal_to_drawing_workflow,
)
from coilforge.submittal.coilmaster_drawing_extract import product_size_options


def _cover_page_hint_from_request(request: Request) -> int | None:
    raw_value = request.headers.get("x-coilforge-cover-page")
    if raw_value in (None, ""):
        return None
    try:
        page_number = int(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-CoilForge-Cover-Page must be an integer.") from exc
    if page_number < 1:
        raise HTTPException(status_code=400, detail="X-CoilForge-Cover-Page must be 1 or greater.")
    return page_number


def load_default_state():
    """Compatibility wrapper for the earlier Phase 2A web shell entrypoint."""
    return load_default_dx_header1_fixture()


__all__ = ["DEFAULT_VIEWBOX", "REVIEW_WATERMARK", "app", "load_default_state"]


@app.get("/api/workflow/default-demo")
async def workflow_default_demo():
    return build_default_demo_workflow_input()


@app.get("/api/ui/default")
async def ui_default_state():
    return build_phase2b_default_ui_state()


@app.get("/api/direct-coil/paste-ready-fields")
async def direct_coil_paste_ready_fields():
    demo = build_default_demo_workflow_input()
    workflow = run_submittal_to_direct_draft_workflow(demo["input"])
    return jsonable_encoder(workflow["direct_coil_paste_ready"])


@app.get("/api/compatibility/default-review")
async def compatibility_default_review():
    return jsonable_encoder(_build_compatibility_payload())


@app.get("/api/compatibility/default-demo")
async def compatibility_default_demo():
    return jsonable_encoder(_build_compatibility_payload(include_packet=True))


@app.get("/api/compatibility/decision-matrix")
async def compatibility_decision_matrix():
    payload = _build_compatibility_payload()
    matrix = build_field_decision_matrix(
        payload["report"],
        payload["registry"],
        payload["reconciliation_plan"],
    )
    return jsonable_encoder(matrix.to_dict())


@app.get("/api/compatibility/decision-review")
async def compatibility_decision_review():
    return jsonable_encoder(_build_decision_review_surface().to_dict())


@app.get("/api/compatibility/decision-capture")
async def compatibility_decision_capture():
    review = _build_decision_review_surface()
    capture = build_john_decision_capture_packet(review)
    return jsonable_encoder(capture.to_dict())


@app.get("/api/compatibility/decision-capture/template")
async def compatibility_decision_capture_template():
    review = _build_decision_review_surface()
    return jsonable_encoder(build_decision_capture_template(review))


@app.get("/api/review/default-packet")
async def review_default_packet():
    return jsonable_encoder(build_default_review_packet().to_dict())


@app.post("/api/review/build-packet")
async def review_build_packet(request: dict[str, Any] = Body(default_factory=dict)):
    payload = request or {}
    workflow_output = payload.get("workflow_output")
    if workflow_output is None:
        workflow_input = payload.get("workflow_input") or payload.get("input")
        if workflow_input:
            workflow_output = run_submittal_to_drawing_workflow(workflow_input)
    intake_payload = payload.get("intake_input") or payload.get("workflow_input") or payload.get("input")
    intake = build_po_based_intake(intake_payload or {})
    return jsonable_encoder(
        build_review_packet(
            workflow_output,
            intake_result=intake,
        ).to_dict()
    )


def _build_decision_review_surface():
    payload = _build_compatibility_payload()
    matrix = build_field_decision_matrix(
        payload["report"],
        payload["registry"],
        payload["reconciliation_plan"],
    )
    review = build_decision_matrix_review_surface(
        matrix,
        build_po_logic_intake_summary(),
    )
    return review


@app.post("/api/compatibility/compare")
async def compatibility_compare(request: dict[str, Any] = Body(default_factory=dict)):
    candidate, ez_payload = _compatibility_inputs_from_request(request or {})
    return jsonable_encoder(
        _build_compatibility_payload(candidate=candidate, ez_payload=ez_payload)
    )


@app.post("/api/compatibility/review-packet")
async def compatibility_review_packet(request: dict[str, Any] = Body(default_factory=dict)):
    candidate, ez_payload = _compatibility_inputs_from_request(request or {})
    payload = _build_compatibility_payload(
        candidate=candidate,
        ez_payload=ez_payload,
        include_packet=True,
    )
    return jsonable_encoder(
        {
            "case_id": payload["report"].case_id,
            "review_packet": payload["review_packet"],
            "summary": payload["safe_summary"],
        }
    )


@app.post("/api/workflow/submittal-to-direct-draft")
async def workflow_submittal_to_direct_draft(request: dict[str, Any] = Body(default_factory=dict)):
    return run_submittal_to_direct_draft_workflow(request or {})


@app.post("/api/workflow/submittal-to-drawing")
async def workflow_submittal_to_drawing(request: dict[str, Any] = Body(default_factory=dict)):
    return run_submittal_to_drawing_workflow(request or {})


@app.post("/api/workflow/pdf-to-direct-draft")
async def workflow_pdf_to_direct_draft(request: Request):
    pdf_bytes = await request.body()
    try:
        return run_pdf_to_direct_draft_workflow(
            pdf_bytes,
            source_id=request.headers.get("x-coilforge-source-id", "PDF-UPLOAD-INTAKE-001"),
            source_filename=request.headers.get("x-coilforge-filename"),
            cover_page_hint=_cover_page_hint_from_request(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/workflow/pdf-to-drawing")
async def workflow_pdf_to_drawing(request: Request):
    pdf_bytes = await request.body()
    try:
        return run_pdf_to_drawing_workflow(
            pdf_bytes,
            source_id=request.headers.get("x-coilforge-source-id", "PDF-UPLOAD-INTAKE-001"),
            source_filename=request.headers.get("x-coilforge-filename"),
            cover_page_hint=_cover_page_hint_from_request(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/coil-drawing/product-options")
async def coil_drawing_product_options():
    """Valid product line -> unit sizes (R-076) for the per-coil picker that
    unlocks the rule-engine dimensions."""
    return {"product_lines": product_size_options()}


@app.post("/api/coil-drawing/derive")
async def coil_drawing_derive(request: dict[str, Any] = Body(default_factory=dict)):
    """Re-derive a coil's template drawing with an engineer-chosen product line +
    unit size so the engine fills the dimensions. Review-aid only."""
    return jsonable_encoder(derive_coil_template_drawing(request or {}))


@app.post("/api/package/assemble")
async def package_assemble(request: dict[str, Any] = Body(default_factory=dict)):
    """Combine the Direct Coil drawing PDF with our CoilForge drawing appended
    right after it, stamped with the copper-strap requirement (R-090) and any
    uncertain-mapping callouts. Returns a base64 watermarked review-aid PDF;
    never flips export_allowed or claims production approval."""
    try:
        return jsonable_encoder(run_drawing_package_workflow(request or {}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/package/quote")
async def package_quote(request: dict[str, Any] = Body(default_factory=dict)):
    """Multi-coil quote package: ONE Direct Coil quote+report+drawing PDF in.
    CoilForge identifies each coil (CDXC-1, RHHGRC-1, ...), inserts our drawing
    right after that coil's drawing page, and stamps a copper-strap price note
    above each coil's quoted price (note-only — quote numbers unchanged). Returns
    a base64 watermarked review-aid PDF; never flips export_allowed."""
    try:
        return jsonable_encoder(run_quote_package_workflow(request or {}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _build_compatibility_payload(
    *,
    candidate: SubmittalCoilCandidate | None = None,
    ez_payload: dict[str, Any] | None = None,
    include_packet: bool = False,
) -> dict[str, Any]:
    if candidate is None or ez_payload is None:
        candidate, ez_payload = _load_default_compatibility_inputs()
    report = compare_submittal_and_ez(candidate, ez_payload)
    registry = build_mapping_rule_registry()
    plan = build_reconciliation_plan(report, registry)
    payload: dict[str, Any] = {
        "report": report,
        "registry": registry,
        "reconciliation_plan": plan,
        "safe_summary": _safe_compatibility_summary(report, plan),
    }
    if include_packet:
        payload["review_packet"] = build_compatibility_diff_review_packet(report)
    return payload


def _compatibility_inputs_from_request(
    request: dict[str, Any],
) -> tuple[SubmittalCoilCandidate, dict[str, Any]]:
    default_candidate, default_ez_payload = _load_default_compatibility_inputs()
    candidate_payload = request.get("submittal_candidate") or request.get("candidate")
    ez_payload = request.get("ez_payload") or request.get("ez_json")
    candidate = (
        SubmittalCoilCandidate.model_validate(candidate_payload)
        if candidate_payload
        else default_candidate
    )
    return candidate, dict(ez_payload or default_ez_payload)


def _load_default_compatibility_inputs() -> tuple[SubmittalCoilCandidate, dict[str, Any]]:
    fixture_root = Path(__file__).resolve().parents[2] / "examples" / "sanitized"
    submittal_fixture = fixture_root / "submittal_candidate_dx_header1_default.json"
    ez_fixture = fixture_root / "dx_header1_ezc0001_default.json"
    return (
        load_submittal_candidate_fixture(submittal_fixture),
        load_sanitized_ez_json(ez_fixture),
    )


def _safe_compatibility_summary(report, plan) -> dict[str, Any]:
    return {
        "case_id": report.case_id,
        "raw_private_data_returned": False,
        "raw_source_text_returned": False,
        "export_allowed": False,
        "pdf_export_enabled": False,
        "direct_coil_final_export_available": False,
        "production_drawing_approval_claimed": False,
        "category_counts": dict(report.category_counts),
        "required_field_issues": list(report.required_field_issues),
        "drawing_impacting_issues": list(report.drawing_impacting_issues),
        "blocked_mismatches": plan.summary.blocked_mismatches,
        "review_required_decisions": plan.summary.review_required,
    }
