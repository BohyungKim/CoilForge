from pathlib import Path
from typing import Any

from fastapi import Body, HTTPException, Request
from fastapi.encoders import jsonable_encoder

from coilforge.adapters import load_sanitized_ez_json
from coilforge.direct_coil import (
    parse_direct_coil_page,
    verify_entered_against_candidate,
)
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
from coilforge.checklist.mapping import build_checklist_fill
from coilforge.checklist.from_workflow import coil_inputs_from_candidates
from coilforge.checklist.compare import build_review
from coilforge.checklist.excel_writer import write_checklist
from coilforge.case_journal import record_coil_milestone


def _journal_milestone(milestone: str, result: dict | None = None,
                       request_payload: dict | None = None,
                       detail: dict | None = None) -> None:
    """Best-effort PO Release Case journal write (append-only, review-aid only —
    records that a milestone request ran; never claims approval). Skipped when
    no project identity is available (demo/sanitized-text paths)."""
    try:
        summary = (result or {}).get("pdf_intake_summary") or {}
        payload = request_payload or {}
        project_number = summary.get("project_number") or payload.get("project_number")
        project_name = summary.get("project_name") or payload.get("project_name")
        if not (project_number or project_name):
            return
        tags: list[str] = []
        for page in (result or {}).get("pdf_coil_pages") or []:
            tag = page.get("tag") if isinstance(page, dict) else None
            if tag and tag not in tags:
                tags.append(tag)
        for coil in payload.get("coils") or []:
            tag = coil.get("tag") if isinstance(coil, dict) else None
            if tag and tag not in tags:
                tags.append(tag)
        record_coil_milestone(
            milestone,
            project_number=project_number,
            project_name=project_name,
            coil_tags=tags,
            detail=detail or {},
        )
    except Exception:  # noqa: BLE001 — journaling must never break a request
        pass


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


@app.post("/api/mechanical-fit")
async def mechanical_fit(request: dict[str, Any] = Body(default_factory=dict)):
    """Width / Height / drain-pan INSTALL fit (review aid) for 1..N coils.

    Body: ``{coils: [{tag, coil_type, product_type, unit_size, finned_height,
    finned_length, rows?, circuits?, application?, ...}], installed_on_drain_pan?}``.
    Pairs DX+HGRH / CWC+HWC across the list so the drain-pan check evaluates when a
    partner is present. Never an export approval (``export_allowed: False``).
    """
    from coilforge.compatibility.mechanical_fit import (
        build_mechanical_fit_report,
        mechanical_fit_report_dict,
    )

    payload = request or {}
    report = build_mechanical_fit_report(
        payload.get("coils") or [],
        installed_on_drain_pan=bool(payload.get("installed_on_drain_pan")),
    )
    return mechanical_fit_report_dict(report)


@app.post("/api/ccsi-compare")
async def ccsi_compare(request: dict[str, Any] = Body(default_factory=dict)):
    """Compare CoilForge drawing values vs values read back from the CCSI form.

    Body: ``{fields: [{key, coilforge, ccsi}, ...]}``. Returns per-field verdicts
    (match / mismatch / missing_one / both_missing) + a mismatch count, reusing the
    checklist comparator's 0.01" tolerance so a wrong value is flagged before the
    engineer saves. Review aid only (``export_allowed: False``); never writes to CCSI.
    """
    from coilforge.ccsi.compare import compare_ccsi_fields

    payload = request or {}
    return compare_ccsi_fields(payload.get("fields") or [])


@app.post("/api/workflow/pdf-to-direct-draft")
async def workflow_pdf_to_direct_draft(request: Request):
    pdf_bytes = await request.body()
    try:
        result = run_pdf_to_direct_draft_workflow(
            pdf_bytes,
            source_id=request.headers.get("x-coilforge-source-id", "PDF-UPLOAD-INTAKE-001"),
            source_filename=request.headers.get("x-coilforge-filename"),
            cover_page_hint=_cover_page_hint_from_request(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _journal_milestone("intake_draft", result=result,
                       detail={"candidates": len(result.get("candidates") or [])})
    return result


@app.post("/api/workflow/pdf-to-drawing")
async def workflow_pdf_to_drawing(request: Request):
    pdf_bytes = await request.body()
    try:
        result = run_pdf_to_drawing_workflow(
            pdf_bytes,
            source_id=request.headers.get("x-coilforge-source-id", "PDF-UPLOAD-INTAKE-001"),
            source_filename=request.headers.get("x-coilforge-filename"),
            cover_page_hint=_cover_page_hint_from_request(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _journal_milestone("intake_drawing", result=result,
                       detail={"candidates": len(result.get("candidates") or [])})
    return result


def _checklist_output_name(source_filename: str | None) -> str:
    stem = Path(source_filename).stem if source_filename else "Coil Checklist"
    return f"{stem} - Coil Checklist.xlsx"


@app.post("/api/checklist/fill")
async def checklist_fill(request: Request):
    """Auto-fill a COPY of the Coil Checklist from a submittal PDF and return the
    review table (checklist formula dims vs CoilForge engine dims).

    POST the submittal PDF bytes (``application/pdf``). Optional headers override
    auto-detection: ``X-CoilForge-Product`` (e.g. ``NOVA``), ``X-CoilForge-Size``
    (e.g. ``C24``), ``X-CoilForge-Filename`` (names the Downloads copy). The source
    template is never modified; the filled copy is written to the Downloads folder.
    Review aid only (``export_allowed: False``)."""
    pdf_bytes = await request.body()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="POST the submittal PDF bytes.")
    try:
        result = run_pdf_to_drawing_workflow(
            pdf_bytes,
            source_id=request.headers.get("x-coilforge-source-id", "CHECKLIST-FILL-001"),
            source_filename=request.headers.get("x-coilforge-filename"),
            cover_page_hint=_cover_page_hint_from_request(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        from coilforge.workflows.submittal_to_drawing import _safe_pdf_text

        pdf_text = _safe_pdf_text(pdf_bytes)
    except Exception:  # noqa: BLE001 — text extraction is best-effort
        pdf_text = ""

    coils, _detected = coil_inputs_from_candidates(
        result.get("candidates") or [],
        pdf_text=pdf_text,
        product_line=request.headers.get("x-coilforge-product"),
        unit_size=request.headers.get("x-coilforge-size"),
    )
    if not coils:
        raise HTTPException(
            status_code=400,
            detail="No recognizable coils (DX/HGRH/HWC/CWC) found for the checklist.",
        )
    fill = build_checklist_fill(coils)
    import asyncio

    try:
        writer_result = await asyncio.to_thread(
            write_checklist,
            fill,
            dest_name=_checklist_output_name(request.headers.get("x-coilforge-filename")),
        )
    except RuntimeError as exc:  # Excel/pywin32 unavailable
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface COM failures clearly
        raise HTTPException(status_code=500, detail=f"Excel write failed: {exc}") from exc
    _journal_milestone(
        "checklist_filled", result=result,
        detail={"saved_path": (writer_result or {}).get("saved_path"),
                "coils": len(coils)},
    )
    return jsonable_encoder(build_review(fill, writer_result))


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
        package = run_drawing_package_workflow(request or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _journal_milestone("package_assembled", request_payload=request or {})
    return jsonable_encoder(package)


@app.post("/api/package/quote")
async def package_quote(request: dict[str, Any] = Body(default_factory=dict)):
    """Multi-coil quote package: ONE Direct Coil quote+report+drawing PDF in.
    CoilForge identifies each coil (CDXC-1, RHHGRC-1, ...), inserts our drawing
    right after that coil's drawing page, and stamps a copper-strap price note
    above each coil's quoted price (note-only — quote numbers unchanged). Returns
    a base64 watermarked review-aid PDF; never flips export_allowed."""
    try:
        package = run_quote_package_workflow(request or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _journal_milestone("quote_package", request_payload=request or {})
    return jsonable_encoder(package)


@app.post("/api/direct-coil/verify")
async def direct_coil_verify(request: dict[str, Any] = Body(default_factory=dict)):
    """Read-and-alert step 6: compare what John entered into the Direct Coil web form
    against CoilForge's canonical record for that coil and highlight discrepancies.

    Request keys:
      ``page_text`` (str) — captured Direct Coil page text (browser-read or pasted), OR
      ``entered``   (dict) — already-parsed {normalized_key: value}.
      ``candidate`` (dict) — a per-coil SubmittalCoilCandidate (CoilForge side), OR
      ``source_pdf_base64`` (str) + ``coil_tag`` (str) — extract the coil from a PDF.

    CoilForge never edits the website; this only reads and alerts. Review aid only.
    Raises ``ValueError`` on missing/invalid input (mapped to 400)."""
    try:
        verify_result = _run_direct_coil_verify(request or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _journal_milestone(
        "direct_coil_verified", request_payload=request or {},
        detail={
            "coil_tag": (request or {}).get("coil_tag"),
            "match_count": verify_result.get("match_count"),
            "mismatch_count": verify_result.get("mismatch_count"),
        },
    )
    return jsonable_encoder(verify_result)


def _run_direct_coil_verify(request: dict[str, Any]) -> dict[str, Any]:
    entered = request.get("entered")
    if not entered:
        page_text = request.get("page_text")
        if not page_text or not str(page_text).strip():
            raise ValueError("provide either 'entered' values or 'page_text'")
        entered = parse_direct_coil_page(str(page_text))
    if not entered:
        raise ValueError("no Direct Coil fields could be read from the page text")

    coil_tag = request.get("coil_tag")
    candidate = request.get("candidate")
    if not candidate:
        source_pdf_b64 = request.get("source_pdf_base64")
        if not source_pdf_b64:
            raise ValueError("provide 'candidate' or 'source_pdf_base64' for the CoilForge side")
        candidate = _verify_candidate_from_pdf(source_pdf_b64, coil_tag)
    return verify_entered_against_candidate(entered, candidate, coil_tag=coil_tag)


def _verify_candidate_from_pdf(pdf_b64: str, coil_tag: str | None) -> dict[str, Any]:
    import base64

    try:
        pdf_bytes = base64.b64decode(pdf_b64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"source_pdf_base64 is not valid base64 ({exc})") from exc
    result = run_pdf_to_drawing_workflow(pdf_bytes, source_id="DIRECT-COIL-VERIFY-INTAKE")
    candidates = result.get("candidates") or []
    if not candidates:
        raise ValueError("no coil candidates were found in the PDF")
    if coil_tag:
        wanted = str(coil_tag).upper()
        for candidate in candidates:
            tag_field = candidate.get("tag") or {}
            tag_value = tag_field.get("value") if isinstance(tag_field, dict) else None
            if tag_value and str(tag_value).upper() == wanted:
                return candidate
        raise ValueError(f"coil_tag {coil_tag!r} was not found in the PDF")
    return candidates[0]


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
