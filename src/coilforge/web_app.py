import asyncio
import copy
import hashlib
import json
import os

from collections import OrderedDict
from datetime import date
from pathlib import Path
from typing import Any, NamedTuple

from fastapi import Body, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder

from coilforge import brain_case
from coilforge.adapters import load_sanitized_ez_json
from coilforge.capture import capture_milestone
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
from coilforge.phase2a.app import app, WEB_DIR
from coilforge.phase2a.fixtures import load_default_dx_header1_fixture
from coilforge.phase2a.ui_state import build_phase2b_default_ui_state
from coilforge.phase2a.renderer import DEFAULT_VIEWBOX, REVIEW_WATERMARK
from coilforge.review import build_default_review_packet, build_review_packet
from coilforge.review.adjudicate import AdjudicationError, record_adjudication
from coilforge.review.divergence import (
    annotate_known_divergences,
    divergence_enabled,
    identities_by_tag,
    load_registry,
)
from coilforge.submittal.po_based_intake import build_po_based_intake
from coilforge.submittal import SubmittalCoilCandidate, load_submittal_candidate_fixture
from coilforge.ambient.pdf_intake import parse_ambient_pdf
from coilforge.ambient.mapping import build_ambient_comparison
from coilforge.ambient.range_provider import coil_utilities_range_provider
from coilforge.ambient.rfq import build_ambient_rfq
from coilforge.ambient.package import build_ambient_package
from coilforge.ambient.excel_map import build_ambient_excel_fill
from coilforge.ambient.excel_writer import write_ambient_excel
from coilforge.ambient.quote_request_pdf import build_ambient_quote_request_pdf
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
from coilforge.common.excel_lock import ExcelBusyError
from coilforge.checklist.overrides import normalize_coil_overrides
from coilforge.case_journal import record_coil_milestone


def _journal_milestone(milestone: str, result: dict | None = None,
                       request_payload: dict | None = None,
                       detail: dict | None = None,
                       identity: str | None = None,
                       pdf_bytes: bytes | None = None,
                       cover_page_hint: int | None = None,
                       product: str | None = None,
                       size: str | None = None,
                       gate: dict | None = None,
                       compare: dict | None = None) -> None:
    """Capture the run into the ledger, then best-effort write the PO Release Case
    journal line (append-only, review-aid only — records that a milestone request
    ran; never claims approval). The journal line is skipped when no project
    identity is available (demo/sanitized-text paths); the LEDGER is not.

    ``identity`` is the REQUEST initiator (the ``X-CoilForge-Identity`` header —
    who/what fired the request), recorded as ``value.request_identity``. It is a
    distinct concept from the event's project identity (project_number/name);
    the two are never merged.

    ``pdf_bytes`` / ``cover_page_hint`` / ``product`` / ``size`` are ledger-only
    dedup components — the route layer is the one place that holds the real PDF
    bytes (some bodies are a base64 envelope, and case-to-drawing's body is just
    ``{case_id}`` with the PDF read from disk inside the route).

    ``gate`` is the project gate the route already computed. Pass it whenever the
    route has one: the ledger must record the verdict John was actually shown, not
    a re-derivation the caller fed different inputs."""
    # Journal FIRST so its event_id can be linked to the ledger run — the ledger is
    # append-only, so it cannot be back-patched after the fact. The journal is
    # identity-gated (returns (None, None) on demo/derive paths); the ledger is not.
    journal_event_id, journal_error = _write_journal_line(
        milestone, result, request_payload, detail, identity
    )
    # Ledger always, carrying the journal outcome. capture_milestone never raises.
    # This is the run that closes the gap: demo / sanitized / derive runs the journal
    # deliberately drops are still ML data and land here.
    capture_milestone(
        milestone, result=result, request_payload=request_payload,
        pdf_bytes=pdf_bytes, cover_page_hint=cover_page_hint,
        product=product, size=size, identity=identity, gate=gate, compare=compare,
        journal_event_id=journal_event_id, journal_error=journal_error,
    )


def _write_journal_line(milestone: str, result: dict | None, request_payload: dict | None,
                        detail: dict | None, identity: str | None) -> tuple[str | None, str | None]:
    """Best-effort PO Release Case journal write. Returns ``(event_id, error)`` —
    ``(None, None)`` when no project identity exists (the journal deliberately skips
    demo/sanitized paths). NEVER raises: a hook failure comes back as ``error`` so it
    is surfaced on the ledger run rather than discarded (discarding it is how four
    milestones journaled nothing for months)."""
    try:
        summary = (result or {}).get("pdf_intake_summary") or {}
        payload = request_payload or {}
        project_number = summary.get("project_number") or payload.get("project_number")
        project_name = summary.get("project_name") or payload.get("project_name")
        if not (project_number or project_name):
            return None, None
        tags: list[str] = []
        for page in (result or {}).get("pdf_coil_pages") or []:
            tag = page.get("tag") if isinstance(page, dict) else None
            if tag and tag not in tags:
                tags.append(tag)
        for coil in payload.get("coils") or []:
            tag = coil.get("tag") if isinstance(coil, dict) else None
            if tag and tag not in tags:
                tags.append(tag)
        # /derive is a single-coil path: its tag is payload["tag"] (singular), and
        # its result is the template_drawing itself (no pdf_coil_pages). Without
        # this the coil_manual_fill line journals coil_tags:[] -- the project
        # survives but the coil dies, exactly the identifier Case Retrieval needs.
        single_tag = payload.get("tag")
        if single_tag and single_tag not in tags:
            tags.append(single_tag)
        record_detail = dict(detail or {})
        if identity:
            # Request initiator (R12c) — kept separate from project identity.
            record_detail["request_identity"] = identity
        return record_coil_milestone(
            milestone,
            project_number=project_number,
            project_name=project_name,
            coil_tags=tags,
            detail=record_detail,
        )
    except Exception as exc:  # noqa: BLE001 — journaling must never break a request
        return None, f"journal hook failed: {type(exc).__name__}: {exc}"


def _cover_page_hint(raw_value: Any, label: str) -> int | None:
    """Validate a cover-page hint from a header or a JSON body field.

    Shared so every entry point produces the SAME value for the checklist cache key:
    the analyze-time fill sends it as a header and `deliverable_finalize` as a body
    field, and a hint that differs between them is a guaranteed cache miss (which is
    what made finalize re-run Excel without the hint and lose the checklist).
    """
    if raw_value in (None, ""):
        return None
    try:
        page_number = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{label} must be an integer.") from exc
    if page_number < 1:
        raise HTTPException(status_code=400, detail=f"{label} must be 1 or greater.")
    return page_number


def _cover_page_hint_from_request(request: Request) -> int | None:
    return _cover_page_hint(
        request.headers.get("x-coilforge-cover-page"), "X-CoilForge-Cover-Page"
    )


def _identity_from_request(request: Request) -> str | None:
    """Read the ``X-CoilForge-Identity`` request header (the initiator / call
    source, R12c). Degrades to ``None`` when absent or blank — never raises, so a
    request without the header still succeeds. This is the REQUEST identity, NOT
    the project identity (``brain_case.case_identity``)."""
    raw_value = request.headers.get("x-coilforge-identity")
    if raw_value is None:
        return None
    identity = raw_value.strip()
    return identity or None


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


@app.get("/api/capture/health")
async def capture_health():
    """Read-only capture-ledger status (1d): enabled flag, schema version, per-table row
    counts, and recent-error TYPES. Never returns raw customer data; never creates the DB
    on a machine that has never captured."""
    from coilforge.capture.observe import health

    return jsonable_encoder(health())


@app.get("/api/capture/override-rate")
async def capture_override_rate():
    """Read-only Stage 3.0 measurement: per-field override rate over the ledger — of the coil
    identities flagged for a field, the fraction John actually corrected. Returns
    ``insufficient`` until corrections accrue (never a fabricated weight). Aggregate counts
    only; redacts the free-text correction reason on this unauthenticated surface; never
    creates the DB on a machine that has never captured."""
    from coilforge.capture.triage import measure_override_rate

    report = measure_override_rate(redact=True)
    # The core dict carries only raw_private_data_returned (matching health()); the route
    # augments the two review-aid flags (as build_project_gate does).
    report["export_allowed"] = False
    report["production_drawing_approval_claimed"] = False
    return jsonable_encoder(report)


@app.get("/api/capture/rule-observatory")
async def capture_rule_observatory():
    """Read-only Stage 4.0 measurement: per-RULE disagreement over the ledger — one level up
    from override-rate, at the grain a YAML change is actually made at.

    Reports NO accuracy figure, by construction. Every rate divides by ``second_opinion``
    rather than ``fired``, and a rule nobody has ever checked comes back with
    ``disagreement_rate: None`` plus a ``no_second_opinion`` flag — because the failure mode
    this stage is most exposed to is an unexamined rule reading as a perfect one. The
    ``blind_spots`` list is returned alongside the ranked rules for the same reason.

    Aggregate counts only; redacts on this unauthenticated surface (a per-rule aggregate
    needs no coil tags or project numbers at all); never creates the DB."""
    from coilforge.capture.observatory import measure_rule_observatory

    report = measure_rule_observatory(redact=True)
    report["export_allowed"] = False
    report["production_drawing_approval_claimed"] = False
    return jsonable_encoder(report)


@app.get("/api/capture/similar")
async def capture_similar(coil_uid: str, k: int = 5, same_category: bool = True):
    """Read-only case retrieval (Stage 2): the nearest past coils to ``coil_uid`` plus John's
    own prior corrections as EVIDENCE (never auto-applied). Redacts the free-text override
    reason + raw project_number on this unauthenticated surface (health() redacts for the same
    reason); never creates the DB on a machine that has never captured."""
    from coilforge.capture.retrieve import similar_by_coil_uid

    return jsonable_encoder(
        similar_by_coil_uid(coil_uid, k=k, same_category=same_category, redact=True)
    )


@app.post("/api/capture/similar")
async def capture_similar_features(request: dict[str, Any] = Body(default_factory=dict)):
    """What-if case retrieval: POST a feature dict (``coil_category``, ``product_line``,
    ``unit_size``, ``rows``, ``feeds``, ``circuits``, ...) to find similar past coils. Accepts
    either ``{"features": {...}, "k": 5, "same_category": true}`` or a bare feature dict. Same
    redaction as the GET."""
    from coilforge.capture.retrieve import similar_by_features

    payload = request or {}
    features = payload.get("features")
    if not isinstance(features, dict):
        features = {k: v for k, v in payload.items() if k not in ("k", "same_category", "features")}
    try:
        k = int(payload.get("k", 5))
    except (TypeError, ValueError):
        k = 5
    return jsonable_encoder(
        similar_by_features(
            features,
            k=k,
            same_category=bool(payload.get("same_category", True)),
            redact=True,
        )
    )


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
    # Capture the coil surface (workflow_output), not the packet — it is the standard
    # workflow dict coil_views understands. workflow_output may be None (no input);
    # capture then records a coil-less run, which is fine.
    _journal_milestone("review_packet", result=workflow_output, request_payload=payload)
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
    result = run_submittal_to_direct_draft_workflow(request or {})
    # Same step as the PDF intake_draft path but a text workflow — reuse the
    # existing milestone so the AST guard passes and the journal accepts it.
    _journal_milestone("intake_draft", result=result, request_payload=request or {})
    return result


@app.post("/api/workflow/submittal-to-drawing")
async def workflow_submittal_to_drawing(request: dict[str, Any] = Body(default_factory=dict)):
    result = run_submittal_to_drawing_workflow(request or {})
    _journal_milestone("intake_drawing", result=result, request_payload=request or {})
    return result


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
    report_dict = mechanical_fit_report_dict(report)
    # Weak label for stage 3/4. The body has coil tags, so these rows join a coil
    # later. No project identity -> journal skips it, ledger keeps it (its reason
    # for existing), so call capture_milestone directly rather than via the journal.
    capture_milestone(
        "mechanical_fit",
        compare={"comparator": "mechanical_fit", "report": report_dict},
    )
    return report_dict


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
    result = compare_ccsi_fields(payload.get("fields") or [])
    # Weak label for stage 3/4. The body carries NO coil identity, so these rows are
    # recorded with coil_tag NULL — orphan rows, on purpose (1a'), never silently
    # dropped. Threading the tag from the frontend/CCSI skill is deferred to 1a'.
    capture_milestone("ccsi_compare", compare={"comparator": "ccsi", "report": result})
    return result


def _load_ccsi_field_map() -> dict[str, Any]:
    """Parse the CCSI field map (same file the live compare/fill use) from disk."""
    import json

    path = WEB_DIR / "ccsi" / "ccsi_dx_field_map.json"
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/ccsi/audit-export")
async def ccsi_audit_export(request: Request):
    """Offline CCSI-export audit — the green/red compare from a downloaded CCSI
    report PDF, with NO live CCSI site and NO browser session.

    POST the exported CCSI report PDF bytes. A CCSI export is a CoilMaster drawing,
    so the pdf-to-drawing workflow parses each coil's printed as-built dimensions
    (CCSI side) alongside CoilForge's engine values (CoilForge side); this route
    reshapes that into the shared comparator (tol 0.01) per coil. Review aid only
    (``export_allowed: False``); a dimension CCSI's drawing didn't print reads
    ``missing_one``, never guessed.
    """
    from coilforge.ccsi.export_audit import audit_export_result

    pdf_bytes = await request.body()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="POST the exported CCSI report PDF bytes.")
    try:
        result = run_pdf_to_drawing_workflow(
            pdf_bytes,
            source_id=request.headers.get("x-coilforge-source-id", "CCSI-EXPORT-AUDIT-001"),
            source_filename=request.headers.get("x-coilforge-filename"),
            cover_page_hint=_cover_page_hint_from_request(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    field_map = _load_ccsi_field_map()
    coils = audit_export_result(result, field_map)
    _journal_milestone("ccsi_export_audit", result=result,
                       detail={"coils_audited": len(coils)},
                       identity=_identity_from_request(request))
    return {
        "coils": coils,
        "field_map_version": field_map.get("version"),
        "review_aid_only": True,
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
        "raw_private_data_returned": False,
    }


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
                       detail={"candidates": len(result.get("candidates") or [])},
                       identity=_identity_from_request(request),
                       pdf_bytes=pdf_bytes,
                       cover_page_hint=_cover_page_hint_from_request(request))
    return result


@app.post("/api/workflow/pdf-to-drawing")
async def workflow_pdf_to_drawing(request: Request):
    pdf_bytes = await request.body()
    try:
        # P0-B: the 30-60s intake/OCR/per-coil workflow is CPU-bound; run it off the
        # event loop (like case_to_drawing) so it never blocks other requests. Single-
        # user local tool, so the module-level workflow caches stay lock-free (worst
        # case under concurrency is a duplicate recompute, never corruption).
        result = await asyncio.to_thread(
            run_pdf_to_drawing_workflow,
            pdf_bytes,
            source_id=request.headers.get("x-coilforge-source-id", "PDF-UPLOAD-INTAKE-001"),
            source_filename=request.headers.get("x-coilforge-filename"),
            cover_page_hint=_cover_page_hint_from_request(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _journal_milestone("intake_drawing", result=result,
                       detail={"candidates": len(result.get("candidates") or [])},
                       identity=_identity_from_request(request),
                       pdf_bytes=pdf_bytes,
                       cover_page_hint=_cover_page_hint_from_request(request))
    return result


def _resolve_brain_case(case_id: str) -> tuple[dict, Path]:
    """Shared resolve for the case-prefill endpoints: case JSON + staged PDF.
    Raises HTTPException with an actionable message on every miss."""
    if not brain_case.is_safe_case_id(case_id):
        raise HTTPException(status_code=400,
                            detail="case_id is required (path separators not allowed).")
    case = brain_case.load_case(case_id)
    if case is None:
        raise HTTPException(
            status_code=404,
            detail=f"Case {case_id} not found on the PO Release Case board "
                   f"(looked in {brain_case.cases_dir()}).")
    pdf_path = brain_case.find_submittal_pdf(case)
    if pdf_path is None:
        raise HTTPException(
            status_code=409,
            detail=f"No submittal PDF found for {case_id} — the case has no "
                   "journaled intake path (it may predate dashboard intake). "
                   "Drop the PDF manually instead.")
    return case, pdf_path


@app.post("/api/workflow/case-to-drawing")
async def workflow_case_to_drawing(request: Request, payload: dict = Body(...)):
    """Brain deep-link prefill: resolve the case's staged submittal PDF from the
    PO Release Case board (read-only) and run the standard pdf-to-drawing
    workflow on it. Response shape == /api/workflow/pdf-to-drawing plus a
    ``brain_case`` block; the Brain's project identity overrides the PDF-parsed
    one so downstream journaling keys to the right case."""
    case_id = str(payload.get("case_id") or "").strip()
    case, pdf_path = _resolve_brain_case(case_id)
    try:
        pdf_bytes = await asyncio.to_thread(pdf_path.read_bytes)
    except OSError as exc:
        raise HTTPException(status_code=409,
                            detail=f"Submittal PDF unreadable: {exc}") from exc
    try:
        # to_thread: the analysis blocks 30-60s — keep the event loop free.
        result = await asyncio.to_thread(
            run_pdf_to_drawing_workflow,
            pdf_bytes,
            source_id=f"BRAIN-CASE-{case_id}",
            source_filename=pdf_path.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    identity = brain_case.case_identity(case)
    summary = result.get("pdf_intake_summary")
    if isinstance(summary, dict):
        # Brain identity is authoritative (a filename like "SIGNED 2819 - ..."
        # can misparse; milestones must journal to the real project).
        if identity["project_number"]:
            summary["project_number"] = identity["project_number"]
            summary["project_context_source"] = "po_release_case_board"
        if identity["project_name"]:
            summary["project_name"] = identity["project_name"]
    result["brain_case"] = {
        "case_id": case_id,
        "label": identity["label"],
        "expected_coils": brain_case.expected_coils(case),
        "source_filename": pdf_path.name,
    }
    _journal_milestone("intake_drawing", result=result,
                       detail={"candidates": len(result.get("candidates") or []),
                               "brain_case_id": case_id},
                       identity=_identity_from_request(request),
                       pdf_bytes=pdf_bytes)
    return result


@app.get("/api/case/{case_id}/submittal-pdf")
async def case_submittal_pdf(case_id: str):
    """Raw staged submittal PDF for a Brain case, so the frontend can restore
    a File object after a case deep link (checklist fill, quote package and
    cover-page re-analyze all re-POST the original PDF bytes)."""
    _case, pdf_path = _resolve_brain_case(case_id)
    try:
        pdf_bytes = await asyncio.to_thread(pdf_path.read_bytes)
    except OSError as exc:
        raise HTTPException(status_code=409,
                            detail=f"Submittal PDF unreadable: {exc}") from exc
    return Response(content=pdf_bytes, media_type="application/pdf")


def _checklist_output_name(source_filename: str | None) -> str:
    stem = Path(source_filename).stem if source_filename else "Coil Checklist"
    return f"{stem} - Coil Checklist.xlsx"


# --- Bounded memoization of the Coil Checklist fill --------------------------
# The submittal is now auto-filled on analyze, then reused when the deliverable is
# finalized. Generating the checklist is the expensive step (an isolated Excel COM
# process: SaveCopyAs + CalculateFull + read-back), so re-running it for the same
# PDF would double John's wait. We memoize the review table + the Downloads copy
# path keyed on sha1(pdf_bytes) PLUS the product/size overrides -- the only inputs
# that change the sheet contents (the filename only names the file, so it is NOT
# in the key). A cached entry is reused only while its ``saved_path`` still exists
# on disk; a deleted copy falls through to a fresh write. source_id is deliberately
# excluded so the analyze-time fill and the finalize-time reuse share one entry.
# The 5th key element is a fingerprint of the engineer's manual overrides: correcting a
# coil in the browser MUST produce a new sheet instead of reusing the pre-override one
# (that reuse IS the "drawing updated but the checklist still shows the old value" bug).
# It is None when no override is supplied, so the plain analyze path keys as before.
_CHECKLIST_CACHE_MAXSIZE = 32
_CHECKLIST_CACHE: (
    "OrderedDict[tuple[str, str | None, str | None, int | None, str | None], dict[str, Any]]"
) = OrderedDict()


def _overrides_fingerprint(overrides: dict[str, Any] | None) -> str | None:
    """Stable sha1 over the normalized manual overrides (order-independent), else None."""
    if not overrides:
        return None
    canonical = json.dumps(
        {
            tag: {
                "engine_inputs": dict(sorted(ov.engine_inputs.items())),
                "param_overrides": dict(sorted(ov.param_overrides.items())),
            }
            for tag, ov in sorted(overrides.items())
        },
        sort_keys=True, default=str,
    )
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()


class _ChecklistOutcome(NamedTuple):
    """Result of :func:`_run_or_reuse_checklist`. ``review`` is ``None`` on any
    failure; ``reason`` / ``http_status`` describe it so each caller can map it to
    its own contract (route -> HTTPException, finalize -> status string, project
    gate -> best-effort skip). The helper never raises."""

    review: dict[str, Any] | None
    saved_path: str | None
    reason: str | None
    http_status: int | None
    # The workflow dict from a FRESH generation (for milestone journaling); ``None``
    # on a cache reuse (already journaled on first fill) or any failure.
    workflow_result: dict[str, Any] | None = None


def clear_checklist_cache() -> None:
    """Drop all memoized checklist results (test hygiene / manual invalidation)."""
    _CHECKLIST_CACHE.clear()


async def _run_or_reuse_checklist(
    pdf_bytes: bytes,
    *,
    product: str | None = None,
    size: str | None = None,
    filename: str | None = None,
    cover_page_hint: int | None = None,
    source_id: str = "CHECKLIST-FILL-001",
    coil_overrides: Any = None,
) -> _ChecklistOutcome:
    """Fill the Coil Checklist for a submittal PDF and return its review table,
    reusing an already-generated result (and its Downloads .xlsx) when the same PDF
    bytes were filled before. Never raises: returns an outcome whose ``review`` is
    ``None`` with a ``reason`` when no recognizable coils exist or Excel/pywin32 is
    unavailable, so callers degrade cleanly.

    ``coil_overrides`` is the raw ``[{tag, engine_inputs, param_overrides, reason}]``
    payload of the engineer's browser manual fills; it is normalized here and carried
    into ``build_checklist_fill`` so the sheet states the values CoilForge is actually
    drawing."""
    if not pdf_bytes:
        return _ChecklistOutcome(None, None, "POST the submittal PDF bytes.", 400)

    overrides = normalize_coil_overrides(coil_overrides)
    # cover_page_hint is in the key (like _WORKFLOW_CACHE): reselecting the cover
    # page on the same bytes changes which coils are read, so it must not hit a
    # stale entry computed under the previous selection.
    key = (
        hashlib.sha1(pdf_bytes).hexdigest(), product, size, cover_page_hint,
        _overrides_fingerprint(overrides),
    )
    cached = _CHECKLIST_CACHE.get(key)
    if cached is not None:
        saved_path = cached.get("saved_path")
        if saved_path and Path(saved_path).exists():
            _CHECKLIST_CACHE.move_to_end(key)
            # Annotate the COPY, never the cached original: a ruling John records in the
            # browser has to change the next render, and this result is memoized by PDF
            # bytes — baking the annotation into the cache would freeze the review at
            # first-fill time and the new ruling would appear to do nothing.
            return _ChecklistOutcome(
                annotate_known_divergences(
                    copy.deepcopy(cached["review"]),
                    identities=cached.get("identities"),
                ),
                saved_path, None, None,
            )
        # No path, or the filled copy was deleted -- drop the stale entry and regenerate.
        # A pathless entry must NOT short-circuit to "success": its review would be handed
        # back with saved_path=None, and `deliverable_finalize` then has no file to file --
        # the silent-skip John reported (docs filed, checklist absent, no warning).
        del _CHECKLIST_CACHE[key]

    try:
        result = run_pdf_to_drawing_workflow(
            pdf_bytes,
            source_id=source_id,
            source_filename=filename,
            cover_page_hint=cover_page_hint,
        )
    except ValueError as exc:
        return _ChecklistOutcome(None, None, str(exc), 400)
    except Exception as exc:  # noqa: BLE001 -- honor the never-raise contract
        return _ChecklistOutcome(None, None, f"Checklist workflow failed: {exc}", 500)

    try:
        from coilforge.workflows.submittal_to_drawing import _safe_pdf_text

        try:
            pdf_text = _safe_pdf_text(pdf_bytes)
        except Exception:  # noqa: BLE001 -- text extraction is best-effort
            pdf_text = ""
        coils, _detected = coil_inputs_from_candidates(
            result.get("candidates") or [],
            pdf_text=pdf_text,
            product_line=product,
            unit_size=size,
        )
    except Exception as exc:  # noqa: BLE001 -- candidate adaptation failure
        return _ChecklistOutcome(None, None, f"Checklist inputs unavailable: {exc}", 500)

    if not coils:
        return _ChecklistOutcome(
            None, None,
            "No recognizable coils (DX/HGRH/HWC/CWC) found for the checklist.", 400,
        )

    try:
        fill = build_checklist_fill(coils, overrides)
        writer_result = await asyncio.to_thread(
            write_checklist, fill, dest_name=_checklist_output_name(filename)
        )
        review = build_review(fill, writer_result)
    except ExcelBusyError as exc:  # another Excel write holds the single-flight guard
        # BEFORE the RuntimeError clause on purpose: 409 (retryable, someone else is
        # mid-write) must not be swallowed by the 501 that means "Excel is missing".
        return _ChecklistOutcome(None, None, str(exc), 409)
    except RuntimeError as exc:  # Excel / pywin32 unavailable
        return _ChecklistOutcome(None, None, str(exc), 501)
    except Exception as exc:  # noqa: BLE001 -- surface COM/fill failures clearly
        return _ChecklistOutcome(None, None, f"Excel write failed: {exc}", 500)

    saved_path = (writer_result or {}).get("saved_path")
    # A re-fill of the same submittal now REPLACES its .xlsx instead of writing a
    # "... (2).xlsx" (John 2026-07-30), so an older entry pointing at that same path is
    # describing a file whose CONTENT has just been overwritten — handing its saved_path
    # back would file the wrong workbook (e.g. finalize with no overrides reusing the
    # baseline entry after an override refill clobbered it). Drop those entries.
    if saved_path:
        for stale in [
            k for k, v in _CHECKLIST_CACHE.items()
            if k != key and v.get("saved_path") == saved_path
        ]:
            del _CHECKLIST_CACHE[stale]
    # The identity map rides along so a later cache hit can annotate without rebuilding
    # the coils (the workflow is memoized by PDF bytes and would not re-run).
    _CHECKLIST_CACHE[key] = {
        "review": review,
        "saved_path": saved_path,
        "identities": identities_by_tag(coils),
    }
    _CHECKLIST_CACHE.move_to_end(key)
    while len(_CHECKLIST_CACHE) > _CHECKLIST_CACHE_MAXSIZE:
        _CHECKLIST_CACHE.popitem(last=False)
    return _ChecklistOutcome(
        annotate_known_divergences(copy.deepcopy(review), coils),
        saved_path, None, None, workflow_result=result,
    )


@app.post("/api/checklist/fill")
async def checklist_fill(request: Request):
    """Auto-fill a COPY of the Coil Checklist from a submittal PDF and return the
    review table (checklist formula dims vs CoilForge engine dims).

    Two body forms:

    - ``application/pdf`` — the raw submittal bytes (the original contract, unchanged).
    - ``application/json`` — ``{submittal_pdf_base64, coil_overrides:[{tag,
      engine_inputs, param_overrides, reason}]}``, so the engineer's browser manual
      fills reach the sheet instead of it silently re-deriving the pre-override values.

    Optional headers override auto-detection: ``X-CoilForge-Product`` (e.g. ``NOVA``),
    ``X-CoilForge-Size`` (e.g. ``C24``), ``X-CoilForge-Filename`` (names the Downloads
    copy). The source template is never modified; the filled copy is written to the
    Downloads folder. Review aid only (``export_allowed: False``)."""
    coil_overrides = None
    if "application/json" in (request.headers.get("content-type") or "").lower():
        payload = await request.json()
        pdf_bytes = _b64_to_bytes(payload.get("submittal_pdf_base64"), "submittal_pdf_base64")
        coil_overrides = payload.get("coil_overrides")
    else:
        pdf_bytes = await request.body()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="POST the submittal PDF bytes.")
    outcome = await _run_or_reuse_checklist(
        pdf_bytes,
        product=request.headers.get("x-coilforge-product"),
        size=request.headers.get("x-coilforge-size"),
        filename=request.headers.get("x-coilforge-filename"),
        cover_page_hint=_cover_page_hint_from_request(request),
        source_id=request.headers.get("x-coilforge-source-id", "CHECKLIST-FILL-001"),
        coil_overrides=coil_overrides,
    )
    if outcome.review is None:
        raise HTTPException(status_code=outcome.http_status or 400, detail=outcome.reason)
    if outcome.workflow_result is not None:  # only journal a fresh fill, not a reuse
        _journal_milestone(
            "checklist_filled", result=outcome.workflow_result,
            detail={"saved_path": outcome.saved_path},
            identity=_identity_from_request(request),
            pdf_bytes=pdf_bytes,
            cover_page_hint=_cover_page_hint_from_request(request),
            product=request.headers.get("x-coilforge-product"),
            size=request.headers.get("x-coilforge-size"),
            # Weak label for review triage: every dimension the sheet and the engine
            # were compared on, with the coil tag, so a later correction on that tag
            # can be joined back to the flag that preceded it. Only on a FRESH fill —
            # a cache reuse re-reports numbers already recorded, and double-counting
            # them would skew the divergence rate.
            compare={"comparator": "checklist", "report": outcome.review},
        )
    return jsonable_encoder(outcome.review)


# ---------------------------------------------------------------------------
# Divergence adjudication — John rules on a checklist-vs-engine disagreement.
#
# The ruling re-LABELS a review row (red -> amber) and does nothing else: no value
# changes, no confidence changes, and `review/project_gate.py` is deliberately untouched,
# so `exceptions_K` keeps one meaning across the whole ledger corpus. A suppression that
# also lowered the gate would silently redefine every measurement taken before it.
#
# The route writes ONLY to the gitignored staging file; promotion into the tracked
# registry is a script John runs and a commit he makes.
# ---------------------------------------------------------------------------
@app.get("/api/divergence/registry")
async def divergence_registry() -> dict[str, Any]:
    """The merged registry as the review UI sees it — promoted + staged, with any
    band-conflict warnings. Read-only."""
    if not divergence_enabled():
        return {"enabled": False, "divergences": [], "warnings": []}
    registry = load_registry()
    return {
        "enabled": True,
        "divergences": [
            {
                "id": e.id, "key": e.key, "coil_category": e.coil_category,
                "product_family": e.product_family, "terra_variant": e.terra_variant,
                "unit_size_scope": e.unit_size_scope, "slot": e.slot,
                "verdict": e.verdict, "severity": e.severity, "reason": e.reason,
                "evidence_refs": list(e.evidence_refs),
                "delta_band": list(e.delta_band) if e.delta_band else None,
                "adjudicated_by": e.adjudicated_by, "adjudicated_utc": e.adjudicated_utc,
                "expires_utc": e.expires_utc, "status": e.status,
                "rule_proposal": e.rule_proposal, "promoted": e.promoted,
            }
            for e in registry.entries
        ],
        "warnings": list(registry.warnings),
        "raw_private_data_returned": False,
        "export_allowed": False,
    }


@app.post("/api/divergence/adjudicate")
async def divergence_adjudicate(request: Request) -> dict[str, Any]:
    """Record one ruling: ``{coil_category, product_family?, terra_variant?,
    unit_size_scope?, slot, verdict, reason, delta_band?, evidence_refs?, expires_utc?,
    run_id?, coil_tag?}``.

    ``reason`` is mandatory (400 when blank). The registry's only claim to not being a
    machine-accumulated suppression list is that every entry carries a human's stated why.
    """
    if not divergence_enabled():
        raise HTTPException(
            status_code=503,
            detail="Divergence adjudication is disabled (COILFORGE_DIVERGENCE=0).",
        )
    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object.")
    try:
        return record_adjudication(payload)
    except AdjudicationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Ambient Dynamics quote comparison (quick-ship supplier — review aid).
# ---------------------------------------------------------------------------
_AMBIENT_CACHE_MAXSIZE = 32
_AMBIENT_CACHE: "OrderedDict[tuple[str, str], dict[str, Any]]" = OrderedDict()


def clear_ambient_cache() -> None:
    """Drop all memoized Ambient comparisons (test hygiene / manual invalidation)."""
    _AMBIENT_CACHE.clear()


def _ambient_enabled() -> bool:
    """Kill switch: when ``COILFORGE_AMBIENT`` is off, the /api/ambient/* routes no-op,
    rolling back the feature WITHOUT reverting the branch. Read at request time. Default ON."""
    return os.environ.get("COILFORGE_AMBIENT", "1").strip().lower() not in (
        "0", "false", "no", "off", "",
    )


class _AmbientOutcome(NamedTuple):
    """Result of :func:`_run_or_reuse_ambient_comparison`; ``payload`` is ``None`` on
    failure with a ``reason``/``http_status``. Never raises."""

    payload: dict[str, Any] | None
    reason: str | None
    http_status: int | None


def _baseline_candidates(
    pdf_bytes: bytes, *, source_id: str, filename: str | None, cover_page_hint: int | None
) -> list[SubmittalCoilCandidate]:
    """Parse the baseline submittal PDF into candidates via the standard workflow."""
    result = run_pdf_to_drawing_workflow(
        pdf_bytes, source_id=source_id, source_filename=filename, cover_page_hint=cover_page_hint
    )
    candidates: list[SubmittalCoilCandidate] = []
    for dumped in result.get("candidates") or []:
        try:
            candidates.append(SubmittalCoilCandidate.model_validate(dumped))
        except Exception:  # noqa: BLE001 -- skip an unparseable candidate, never abort
            continue
    return candidates


async def _run_or_reuse_ambient_comparison(
    baseline_bytes: bytes,
    ambient_bytes: bytes,
    *,
    filename: str | None = None,
    cover_page_hint: int | None = None,
) -> _AmbientOutcome:
    """Compare a baseline submittal PDF vs an Ambient PDF; memoized on both shas.
    Never raises — returns an outcome whose ``payload`` is ``None`` with a reason."""
    if not baseline_bytes or not ambient_bytes:
        return _AmbientOutcome(
            None,
            "POST both PDFs as multipart form fields 'baseline' (submittal) and 'ambient'.",
            400,
        )
    key = (hashlib.sha1(baseline_bytes).hexdigest(), hashlib.sha1(ambient_bytes).hexdigest())
    cached = _AMBIENT_CACHE.get(key)
    if cached is not None:
        _AMBIENT_CACHE.move_to_end(key)
        return _AmbientOutcome(copy.deepcopy(cached), None, None)

    try:
        baseline = _baseline_candidates(
            baseline_bytes, source_id="AMBIENT-BASELINE-001",
            filename=filename, cover_page_hint=cover_page_hint,
        )
    except ValueError as exc:
        return _AmbientOutcome(None, f"Baseline PDF: {exc}", 400)
    except Exception as exc:  # noqa: BLE001 -- never-raise contract
        return _AmbientOutcome(None, f"Baseline workflow failed: {exc}", 500)

    try:
        intake = parse_ambient_pdf(ambient_bytes, source_id="AMBIENT-INTAKE-001", source_filename=filename)
    except Exception as exc:  # noqa: BLE001
        return _AmbientOutcome(None, f"Ambient PDF parse failed: {exc}", 500)

    comparison = build_ambient_comparison(
        baseline, intake.coils, range_provider=coil_utilities_range_provider
    )
    payload = comparison.as_dict()
    payload["ambient_warnings"] = list(intake.warnings)
    payload["raw_private_data_returned"] = False

    _AMBIENT_CACHE[key] = payload
    _AMBIENT_CACHE.move_to_end(key)
    while len(_AMBIENT_CACHE) > _AMBIENT_CACHE_MAXSIZE:
        _AMBIENT_CACHE.popitem(last=False)
    return _AmbientOutcome(copy.deepcopy(payload), None, None)


@app.post("/api/ambient/compare")
async def ambient_compare(request: Request):
    """Compare an Ambient Dynamics performance PDF vs the baseline submittal.

    Multipart form ``baseline`` (submittal PDF) + ``ambient`` (Ambient PDF). Returns a
    per-coil green/red/grey comparison with Coil-Utilities acceptance bands. Review aid
    only (``export_allowed: False``); every Ambient value is a vendor claim,
    review-required. Coils on only one side are surfaced with a ``not_compared_reason``."""
    if not _ambient_enabled():
        raise HTTPException(status_code=503, detail="Ambient comparison disabled (COILFORGE_AMBIENT=0).")
    form = await request.form()
    baseline_file = form.get("baseline")
    ambient_file = form.get("ambient")
    if baseline_file is None or ambient_file is None:
        raise HTTPException(
            status_code=400,
            detail="multipart form must include 'baseline' and 'ambient' PDF files.",
        )
    baseline_bytes = await baseline_file.read() if hasattr(baseline_file, "read") else bytes(baseline_file)
    ambient_bytes = await ambient_file.read() if hasattr(ambient_file, "read") else bytes(ambient_file)
    outcome = await _run_or_reuse_ambient_comparison(
        baseline_bytes, ambient_bytes,
        filename=getattr(ambient_file, "filename", None),
        cover_page_hint=_cover_page_hint_from_request(request),
    )
    if outcome.payload is None:
        raise HTTPException(status_code=outcome.http_status or 400, detail=outcome.reason)
    return jsonable_encoder(outcome.payload)


@app.post("/api/ambient/rfq")
async def ambient_rfq(request: Request):
    """Build a structured performance-target summary for an Ambient RFQ (Feature 1).

    POST the baseline submittal PDF bytes. Returns per-coil targets + the Coil-Utilities
    acceptance band. Review aid only; no email is sent."""
    if not _ambient_enabled():
        raise HTTPException(status_code=503, detail="Ambient disabled (COILFORGE_AMBIENT=0).")
    pdf_bytes = await request.body()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="POST the baseline submittal PDF bytes.")
    try:
        baseline = _baseline_candidates(
            pdf_bytes, source_id="AMBIENT-RFQ-001",
            filename=request.headers.get("x-coilforge-filename"),
            cover_page_hint=_cover_page_hint_from_request(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Baseline PDF: {exc}")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Baseline workflow failed: {exc}")
    return jsonable_encoder(build_ambient_rfq(baseline))


# ---------------------------------------------------------------------------
# Ambient submittal -> package (generate a performance page + drawing to HAND to
# Ambient from a submittal alone — no EZ Coil selection needed). Additive & optional;
# the compare path above is untouched.
# ---------------------------------------------------------------------------
_AMBIENT_PACKAGE_CACHE: "OrderedDict[tuple[str, str], dict[str, Any]]" = OrderedDict()


def clear_ambient_package_cache() -> None:
    """Drop all memoized Ambient packages (test hygiene / manual invalidation)."""
    _AMBIENT_PACKAGE_CACHE.clear()


def _baseline_workflow_and_candidates(
    pdf_bytes: bytes, *, source_id: str, filename: str | None, cover_page_hint: int | None
) -> tuple[list[SubmittalCoilCandidate], dict[str, tuple[str | None, str | None, str | None]]]:
    """Parse the submittal ONCE into candidates AND a ``tag -> (source, svg, omitted_reason)``
    drawing map, read off the SAME workflow (no second parse). The per-coil drawing is the
    gate-honest Track B ``template_drawing`` — the top-level ``svg`` is only the selected
    coil's preview and is never blanked, so it must NOT be used here (per plan-review)."""
    result = run_pdf_to_drawing_workflow(
        pdf_bytes, source_id=source_id, source_filename=filename, cover_page_hint=cover_page_hint
    )
    candidates: list[SubmittalCoilCandidate] = []
    for dumped in result.get("candidates") or []:
        try:
            candidates.append(SubmittalCoilCandidate.model_validate(dumped))
        except Exception:  # noqa: BLE001 -- skip an unparseable candidate, never abort
            continue

    drawings: dict[str, tuple[str | None, str | None, str | None]] = {}
    for page in result.get("pdf_coil_pages") or []:
        tag = page.get("tag")
        if not tag:
            continue
        template_drawing = (page.get("workflow") or {}).get("template_drawing") or {}
        if not isinstance(template_drawing, dict) or "error" in template_drawing:
            reason = "drawing unavailable"
            if isinstance(template_drawing, dict) and template_drawing.get("error"):
                reason = f"drawing unavailable: {template_drawing['error']}"
            drawings[tag] = (None, None, reason)
        elif template_drawing.get("svg"):
            drawings[tag] = ("track_b_generated", template_drawing["svg"], None)
        else:  # gate-withheld (svg == "") -> loud omission, never a borrowed drawing
            drawings[tag] = (
                None,
                None,
                template_drawing.get("not_registered_reason") or "drawing not generated",
            )
    return candidates, drawings


async def _run_or_reuse_ambient_package(
    submittal_bytes: bytes,
    ez_drawing_bytes: bytes,
    *,
    filename: str | None = None,
    cover_page_hint: int | None = None,
) -> _AmbientOutcome:
    """Build the submittal->Ambient package (performance page + per-coil drawing); memoized
    on ``(sha1(submittal), sha1(ez_drawing))``. Never raises — mirrors the compare path."""
    if not submittal_bytes:
        return _AmbientOutcome(
            None, "POST the submittal PDF as multipart form field 'submittal'.", 400
        )
    key = (
        hashlib.sha1(submittal_bytes).hexdigest(),
        hashlib.sha1(ez_drawing_bytes or b"").hexdigest(),
    )
    cached = _AMBIENT_PACKAGE_CACHE.get(key)
    if cached is not None:
        _AMBIENT_PACKAGE_CACHE.move_to_end(key)
        return _AmbientOutcome(copy.deepcopy(cached), None, None)

    try:
        candidates, drawings = _baseline_workflow_and_candidates(
            submittal_bytes, source_id="AMBIENT-PACKAGE-001",
            filename=filename, cover_page_hint=cover_page_hint,
        )
    except ValueError as exc:
        return _AmbientOutcome(None, f"Submittal PDF: {exc}", 400)
    except Exception as exc:  # noqa: BLE001 -- never-raise contract
        return _AmbientOutcome(None, f"Submittal workflow failed: {exc}", 500)

    payload = build_ambient_package(candidates).as_dict()

    # Attach the per-coil drawing (Track B), or the EZ Coil drawing if supplied. A single
    # supplied EZ drawing can only be honestly mapped when there is exactly one coil;
    # otherwise it is recorded at the package level rather than guessing which coil it is.
    coils = payload.get("coils") or []
    ez_supplied = bool(ez_drawing_bytes)
    for coil in coils:
        source, svg, omitted = drawings.get(coil.get("tag"), (None, None, "no matching coil drawing"))
        coil["drawing"] = {"source": source, "svg": svg, "omitted_reason": omitted}
    if ez_supplied:
        if len(coils) == 1:
            coils[0]["drawing"] = {"source": "ez_coil", "svg": None, "omitted_reason": None}
        else:
            payload.setdefault("warnings", []).append(
                f"EZ Coil drawing supplied ({len(ez_drawing_bytes)} bytes) — use it in place of "
                f"the generated drawing (not auto-mapped per coil across {len(coils)} coils)."
            )
    payload["raw_private_data_returned"] = False

    _AMBIENT_PACKAGE_CACHE[key] = payload
    _AMBIENT_PACKAGE_CACHE.move_to_end(key)
    while len(_AMBIENT_PACKAGE_CACHE) > _AMBIENT_CACHE_MAXSIZE:
        _AMBIENT_PACKAGE_CACHE.popitem(last=False)
    return _AmbientOutcome(copy.deepcopy(payload), None, None)


@app.post("/api/ambient/package")
async def ambient_package(request: Request):
    """Generate an Ambient-sendable performance page + drawing FROM A SUBMITTAL alone.

    Multipart form ``submittal`` (required PDF, dropped like Direct Coil) + optional
    ``ez_drawing`` (an EZ Coil selection drawing to use in place of the generated one).
    Returns a per-coil transcribed performance page (every value review-required), a
    Coil-Utilities acceptance band, and the per-coil drawing (Track B generated, or the
    supplied EZ drawing, or a loud omitted_reason). Review aid only (``export_allowed:
    False``); nothing is calculated, selected, or exported."""
    if not _ambient_enabled():
        raise HTTPException(status_code=503, detail="Ambient disabled (COILFORGE_AMBIENT=0).")
    form = await request.form()
    submittal_file = form.get("submittal")
    if submittal_file is None:
        raise HTTPException(
            status_code=400, detail="multipart form must include a 'submittal' PDF file."
        )
    ez_file = form.get("ez_drawing")
    submittal_bytes = (
        await submittal_file.read() if hasattr(submittal_file, "read") else bytes(submittal_file)
    )
    ez_bytes = b""
    if ez_file is not None:
        ez_bytes = await ez_file.read() if hasattr(ez_file, "read") else bytes(ez_file)
    outcome = await _run_or_reuse_ambient_package(
        submittal_bytes, ez_bytes,
        filename=getattr(submittal_file, "filename", None),
        cover_page_hint=_cover_page_hint_from_request(request),
    )
    if outcome.payload is None:
        raise HTTPException(status_code=outcome.http_status or 400, detail=outcome.reason)
    return jsonable_encoder(outcome.payload)


@app.post("/api/ambient/quote-request-pdf")
async def ambient_quote_request_pdf(request: Request):
    """Export the Ambient package as the quote-request PDF John hands the supplier.

    Same multipart form as ``/api/ambient/package`` (``submittal`` required, ``ez_drawing``
    optional) plus optional ``project_name`` / ``project_number`` text fields. Returns
    ``pdf_base64`` — a cover page, then per coil its transcribed performance page(s) followed
    by its drawing page, watermarked on every page.

    It re-POSTs the PDFs rather than accepting the browser's already-rendered package JSON:
    that payload embeds each coil's drawing SVG, and taking it from the client would feed an
    arbitrary client string to the SVG parser and let the client dictate the safety flags.
    ``_run_or_reuse_ambient_package`` is memoized on the uploaded bytes, so the normal path
    (export right after generating) is a cache hit rather than a second parse. Review aid only
    (``export_allowed: False``); a value the submittal did not state stays blank, never guessed.
    """
    if not _ambient_enabled():
        raise HTTPException(status_code=503, detail="Ambient disabled (COILFORGE_AMBIENT=0).")
    form = await request.form()
    submittal_file = form.get("submittal")
    if submittal_file is None:
        raise HTTPException(
            status_code=400, detail="multipart form must include a 'submittal' PDF file."
        )
    ez_file = form.get("ez_drawing")
    submittal_bytes = (
        await submittal_file.read() if hasattr(submittal_file, "read") else bytes(submittal_file)
    )
    ez_bytes = b""
    if ez_file is not None:
        ez_bytes = await ez_file.read() if hasattr(ez_file, "read") else bytes(ez_file)
    outcome = await _run_or_reuse_ambient_package(
        submittal_bytes, ez_bytes,
        filename=getattr(submittal_file, "filename", None),
        cover_page_hint=_cover_page_hint_from_request(request),
    )
    if outcome.payload is None:
        raise HTTPException(status_code=outcome.http_status or 400, detail=outcome.reason)

    def _text_field(name: str) -> str | None:
        value = form.get(name)
        if value is None or hasattr(value, "read"):  # ignore a file posted under a text name
            return None
        return str(value).strip() or None

    try:
        result = await asyncio.to_thread(
            build_ambient_quote_request_pdf,
            outcome.payload,
            project_name=_text_field("project_name"),
            project_number=_text_field("project_number"),
            generated_on=date.today(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — route contract: never surface a raw traceback
        raise HTTPException(
            status_code=500, detail=f"Ambient quote-request PDF failed: {exc}"
        ) from exc
    return jsonable_encoder(result)


@app.post("/api/ambient/excel")
async def ambient_excel(request: Request):
    """Fill the Ambient comparison workbook (C=ours from submittal, D=Ambient) -> Downloads.

    Multipart form ``baseline`` (submittal PDF) + ``ambient`` (Ambient PDF). Fills a COPY of
    the master template in Downloads (one sheet per coil, DX/HGRH); the source template and
    the OneDrive project file are NEVER touched. Review aid only (``export_allowed: False``);
    absent values are left blank (never guessed), template formula cells are preserved."""
    if not _ambient_enabled():
        raise HTTPException(status_code=503, detail="Ambient disabled (COILFORGE_AMBIENT=0).")
    form = await request.form()
    baseline_file = form.get("baseline")
    ambient_file = form.get("ambient")
    if baseline_file is None or ambient_file is None:
        raise HTTPException(
            status_code=400, detail="multipart form must include 'baseline' and 'ambient' PDF files."
        )
    baseline_bytes = await baseline_file.read() if hasattr(baseline_file, "read") else bytes(baseline_file)
    ambient_bytes = await ambient_file.read() if hasattr(ambient_file, "read") else bytes(ambient_file)
    if not baseline_bytes or not ambient_bytes:
        raise HTTPException(status_code=400, detail="both 'baseline' and 'ambient' PDFs are required.")

    try:
        baseline = _baseline_candidates(
            baseline_bytes, source_id="AMBIENT-XLSX-BASE-001",
            filename=getattr(baseline_file, "filename", None),
            cover_page_hint=_cover_page_hint_from_request(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Baseline PDF: {exc}")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Baseline workflow failed: {exc}")
    try:
        intake = parse_ambient_pdf(
            ambient_bytes, source_id="AMBIENT-XLSX-INTAKE-001",
            source_filename=getattr(ambient_file, "filename", None),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Ambient PDF parse failed: {exc}")

    try:
        fill = build_ambient_excel_fill(baseline, list(intake.coils))
    except Exception as exc:  # noqa: BLE001 — never-raise route contract (JSON 500, not bare text)
        raise HTTPException(status_code=500, detail=f"Excel fill mapping failed: {exc}")
    try:
        result = write_ambient_excel(fill)
    except ExcelBusyError as exc:  # the shared single-flight guard is held elsewhere
        # Must precede the RuntimeError clause, and must exist at all: without it the
        # generic `except Exception` below would report a busy guard as a 500
        # "Excel write failed" — the same misdiagnosis the guard was added to remove.
        raise HTTPException(status_code=409, detail=str(exc))
    except RuntimeError as exc:  # Excel COM / pywin32 unavailable
        raise HTTPException(status_code=501, detail=str(exc))
    except ValueError as exc:  # no coil sheets (e.g. only water coils)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Excel write failed: {exc}")
    result["raw_private_data_returned"] = False
    result["ambient_warnings"] = list(intake.warnings)
    return jsonable_encoder(result)


async def _try_checklist_review(pdf_bytes: bytes, request: Request, result: dict):
    """Best-effort engine-vs-checklist cross-check (Excel COM). Returns
    ``(review, None)`` or ``(None, reason)`` — never raises, so the project gate
    degrades to engine-only when Excel/pywin32 is absent. Shares the checklist
    cache, so a project review reuses an already-generated fill. ``result`` is the
    caller's workflow dict, kept for signature stability; the fill is re-derived
    (and memoized) from ``pdf_bytes`` inside the helper.

    NOTE: passes no ``coil_overrides`` — the project gate re-derives from the submittal
    alone, so it reads the machine proposal, not the engineer's browser manual fills."""
    outcome = await _run_or_reuse_checklist(
        pdf_bytes,
        product=request.headers.get("x-coilforge-product"),
        size=request.headers.get("x-coilforge-size"),
        filename=request.headers.get("x-coilforge-filename"),
        source_id=request.headers.get("x-coilforge-source-id", "PROJECT-REVIEW-001"),
    )
    return outcome.review, outcome.reason


# Fixed Oxygen8 DirectCoil hand-off recipients John confirmed (image #2). Display
# names resolve against his Outlook GAL; unresolved ones show in the open draft.
_DELIVERABLE_TO = "purchasing; rayl@directcoil.com"
_DELIVERABLE_CC = "David Newton"

# The browser saves the revised PDF asynchronously moments before it calls finalize,
# so its Downloads copy may not exist yet when we go to retire it. Bounded poll —
# never found is a reported status, not a failure.
_REVISED_DOWNLOAD_WAIT_S = 5.0


def _b64_to_bytes(value, field: str) -> bytes:
    import base64

    if not value:
        raise HTTPException(status_code=400, detail=f"missing {field}")
    try:
        return base64.b64decode(value)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"bad base64 in {field}") from exc


@app.post("/api/deliverable/finalize")
async def deliverable_finalize(request: Request):
    """Finalize a DirectCoil deliverable: MOVE the original quote, the revised quote,
    and the auto-generated Coil Checklist into the project's
    ``…/02 - POs/<project>/Accessory Order Forms/DirectCoil`` folder (only the
    ``DirectCoil`` leaf is created if absent; a differently-spelled one is renamed),
    then open a pre-filled Outlook DRAFT (subject ``Coils: <#> - <name>``, revised PDF
    attached) — never sent.

    POST JSON: ``submittal_pdf_base64`` (project identity + checklist),
    ``quote_pdf_base64`` (original source quote), ``revised_pdf_base64`` (the built
    revised PDF), plus ``submittal_filename`` / ``quote_filename`` and the optional
    ``checklist_overrides`` (the browser's manual fills, so the filed checklist matches
    the drawings). Two optional flags: ``skip_draft`` (file only — this is what the
    Build button sends) and ``overwrite`` (John's answer to a conflict).

    Filing is ALL-OR-NOTHING. A destination that already holds a byte-identical file is
    ``already_filed`` and passes; one holding DIFFERENT content stops the whole thing
    and returns ``status: "conflict"`` with nothing written — a 200, because a conflict
    is a decision waiting on John, not an error (a missing folder still 400/409s).
    The Downloads originals are then retired content-verified, so an unrelated
    same-named file can never be deleted. Review aid only (``export_allowed: False``)."""
    import asyncio

    from coilforge.deliverable.finalize import (
        FinalizeError,
        commit_placements,
        deliverable_subject,
        plan_placements,
        resolve_directcoil_folder,
        retire_download,
    )
    from coilforge.deliverable.outlook_draft import open_deliverable_draft

    payload = await request.json()
    submittal = _b64_to_bytes(payload.get("submittal_pdf_base64"), "submittal_pdf_base64")
    quote = _b64_to_bytes(payload.get("quote_pdf_base64"), "quote_pdf_base64")
    revised = _b64_to_bytes(payload.get("revised_pdf_base64"), "revised_pdf_base64")
    quote_name = Path(payload.get("quote_filename") or "quote.pdf").name
    submittal_name = payload.get("submittal_filename")
    overwrite = bool(payload.get("overwrite"))
    skip_draft = bool(payload.get("skip_draft"))
    # Same hint the browser sent to /api/checklist/fill. It is part of the checklist cache
    # key, so omitting it here guaranteed a MISS on every submittal whose cover page was
    # selected by hand -- finalize then re-derived the coils WITHOUT the hint, which can
    # yield "no recognizable coils" and drop the .xlsx from the deliverable.
    cover_page_hint = _cover_page_hint(payload.get("cover_page"), "cover_page")

    # Project identity from the submittal intake.
    try:
        result = run_pdf_to_drawing_workflow(
            submittal,
            source_id="DELIVERABLE-FINALIZE-001",
            source_filename=submittal_name,
            cover_page_hint=cover_page_hint,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    summary = result.get("pdf_intake_summary") or {}
    project_number = summary.get("project_number")
    project_name = summary.get("project_name")
    if not project_number:
        raise HTTPException(
            status_code=400,
            detail="No project number found in the submittal — cannot locate the PO folder.",
        )

    # Reuse the Coil Checklist auto-generated on analyze (best-effort — surfaced,
    # never silent). Shares the checklist cache, so the same submittal bytes hit the
    # already-written Downloads copy instead of re-running Excel (no double COM).
    # The same manual overrides the browser sent to /api/checklist/fill ride along, so the
    # .xlsx filed with the order is the override-bearing one AND hits its cache entry (a
    # missing payload here would key differently and quietly file the pre-override sheet).
    checklist_outcome = await _run_or_reuse_checklist(
        submittal, filename=submittal_name, source_id="DELIVERABLE-FINALIZE-001",
        cover_page_hint=cover_page_hint,
        coil_overrides=payload.get("checklist_overrides"),
    )
    # A BUSY guard is a hard error here, not a degraded status. Everywhere else a
    # checklist failure is absorbed into `checklist_status` and the order documents are
    # filed anyway — which was safe while failures meant "Excel is absent". The
    # single-flight guard adds a TRANSIENT failure, and absorbing that would file the
    # DirectCoil folder with no .xlsx purely because a fill was running in the next tab.
    if checklist_outcome.http_status == 409:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{checklist_outcome.reason} — the Coil Checklist is filed with this "
                "deliverable, so finalize was stopped rather than filing without it."
            ),
        )
    # NOT the checklist status yet -- only why the fill itself failed, if it did. The
    # status is derived from the FILING outcome below: reporting "ok" here because a
    # review table was built is exactly how a missing .xlsx read as a clean success.
    checklist_path = checklist_outcome.saved_path
    checklist_blocked_reason = (
        None if checklist_outcome.review is not None
        else (checklist_outcome.reason or "unavailable")
    )

    # Resolve/create the DirectCoil folder.
    try:
        folder = resolve_directcoil_folder(project_number)
    except FinalizeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    subject = deliverable_subject(project_number, project_name)
    revised_name = f"{Path(quote_name).stem}_Revised.pdf"
    items: list[tuple[str, bytes | str]] = [
        (quote_name, quote),
        (revised_name, revised),
    ]
    # INVARIANT: the checklist is only "ok" when it is actually in `items` (and therefore
    # in `files_written`). Every other outcome names its own cause -- there is no branch
    # left that can leave the status at a default while the .xlsx quietly stays behind.
    checklist_name = Path(checklist_path).name if checklist_path else None
    if checklist_path and Path(checklist_path).exists():
        items.append((checklist_name or "", checklist_path))
        checklist_status = "ok"
    elif checklist_name and (folder / checklist_name).exists():
        # The Downloads copy is gone because an earlier run MOVED it into the folder
        # (Build files the docs; the draft button re-runs over the same three). That is
        # a completed move, not a missing checklist — say so rather than "unavailable".
        checklist_status = "already filed"
    elif checklist_name:
        checklist_status = "Downloads copy missing — checklist not filed"
    else:
        # No path at all: the fill failed (Excel absent, no coils, COM error), or a
        # cache entry carried no path. Either way the deliverable goes out WITHOUT the
        # checklist, so say so in the same breath as the reason.
        checklist_status = (
            f"{checklist_blocked_reason} — checklist not filed"
            if checklist_blocked_reason
            else "checklist path unavailable — not filed"
        )

    # All-or-nothing: decide every destination first, and if any of them holds
    # DIFFERENT content under the same name, write nothing and hand the list back.
    placements = plan_placements(folder, items)
    conflicts = [p for p in placements if p.is_conflict]
    if conflicts and not overwrite:
        return {
            "status": "conflict",
            "project_number": project_number,
            "project_name": project_name,
            "subject": subject,
            "folder": str(folder),
            "conflicts": [
                {
                    "name": p.filename,
                    "existing_size": p.dest.stat().st_size,
                    "existing_modified": p.dest.stat().st_mtime,
                }
                for p in conflicts
            ],
            "files_written": [],
            "downloads_cleanup": [],
            "documents": [
                {
                    "kind": kind, "name": name, "filed": False, "state": "skipped",
                    "path": None, "downloads": None,
                    "detail": "nothing was filed — name conflict in the folder",
                }
                for kind, name in (
                    ("quote", quote_name), ("revised", revised_name),
                    ("checklist", checklist_name),
                )
            ],
            "checklist_status": checklist_status,
            "draft_opened": False,
            "draft_status": "skipped — nothing was filed",
            "email_sent": False,
            "review_aid_only": True,
            "export_allowed": False,
            "production_drawing_approval_claimed": False,
            "raw_private_data_returned": False,
        }
    try:
        files_written = commit_placements(placements, overwrite=overwrite)
    except FinalizeError as exc:
        # A per-file copy failure (locked source, over-long destination). Documents
        # ahead of it in the list may already be on disk, so report the named cause
        # rather than a bare 500 that says nothing about what did land.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Retire the Downloads originals. The checklist was moved by path above; the two
    # PDFs only reach us as bytes, so they are deleted only where the content matches.
    def _cleanup() -> list[dict]:
        entries = [
            {"name": quote_name, "status": retire_download(quote_name, quote)},
            {
                "name": revised_name,
                "status": retire_download(
                    revised_name, revised, wait_s=_REVISED_DOWNLOAD_WAIT_S
                ),
            },
        ]
        if checklist_name and any(
            Path(p).name == checklist_name for p in files_written
        ):
            entries.append({
                "name": checklist_name,
                "status": (
                    "moved"
                    if not (checklist_path and Path(checklist_path).exists())
                    else "could not delete — left in Downloads"
                ),
            })
        return entries

    downloads_cleanup = await asyncio.to_thread(_cleanup)

    # Per-document log (additive -- `files_written` / `downloads_cleanup` /
    # `checklist_status` keep their contracts). Matched by NAME, never by list order:
    # an `already_filed` entry makes the placement order unreliable, the same reason
    # the Outlook attachment is looked up by name below.
    cleanup_by_name = {e["name"]: e["status"] for e in downloads_cleanup}
    state_by_name = {p.filename: p.state for p in placements}
    filed_by_name = {Path(path).name: path for path in files_written}

    def _document(kind: str, name: str | None, detail: str | None = None) -> dict:
        filed_path = filed_by_name.get(name) if name else None
        return {
            "kind": kind,
            "name": name,
            "filed": filed_path is not None,
            "state": state_by_name.get(name) if filed_path else "skipped",
            "path": filed_path,
            "downloads": cleanup_by_name.get(name) if name else None,
            "detail": detail,
        }

    documents = [
        _document("quote", quote_name),
        _document("revised", revised_name),
        _document(
            "checklist",
            checklist_name,
            None if checklist_status == "ok" else checklist_status,
        ),
    ]

    # Open the Outlook draft with the revised PDF attached (never sent). Looked up by
    # NAME, not by index — `already_filed` entries make the list order unreliable.
    revised_dest = next(
        (p for p in files_written if Path(p).name == revised_name), None
    )
    if skip_draft:
        draft_opened, draft_status = False, "skipped"
    elif revised_dest is None:
        draft_opened, draft_status = False, "revised PDF not filed — no attachment"
    else:
        try:
            await asyncio.to_thread(
                open_deliverable_draft,
                subject=subject,
                to=_DELIVERABLE_TO,
                cc=_DELIVERABLE_CC,
                attachment_path=revised_dest,
            )
            draft_opened, draft_status = True, "ok"
        except RuntimeError as exc:  # pywin32 / Outlook unavailable
            draft_opened, draft_status = False, str(exc)
        except Exception as exc:  # noqa: BLE001 — surface COM failures clearly
            draft_opened, draft_status = False, f"Outlook draft failed: {exc}"

    _journal_milestone(
        "deliverable_finalized", result=result,
        detail={"folder": str(folder), "files": len(files_written),
                "draft_opened": draft_opened},
    )
    return {
        "status": "filed",
        "project_number": project_number,
        "project_name": project_name,
        "subject": subject,
        "folder": str(folder),
        "files_written": files_written,
        "conflicts": [],
        "downloads_cleanup": downloads_cleanup,
        "documents": documents,
        "checklist_status": checklist_status,
        "draft_opened": draft_opened,
        "draft_status": draft_status,
        "email_sent": False,
        "review_aid_only": True,
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
        "raw_private_data_returned": False,
    }


@app.post("/api/deliverable/open-folder")
async def deliverable_open_folder(request: Request):
    """Open a filed deliverable's DirectCoil folder in Explorer.

    POST JSON ``{folder}`` — the ``folder`` value the finalize response just returned.
    The path is validated against the SharePoint PO base before anything is opened, so
    this cannot be used to launch an arbitrary path. Any path we will not or cannot open
    (outside the base, empty, no longer there) is a 400 — the caller supplied it, so it is
    a bad request either way. Read-only: it opens a window and changes nothing on disk."""
    import asyncio

    from coilforge.deliverable.finalize import FinalizeError
    from coilforge.deliverable.open_folder import open_deliverable_folder

    payload = await request.json()
    try:
        opened = await asyncio.to_thread(open_deliverable_folder, payload.get("folder"))
    except FinalizeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:  # non-Windows
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except OSError as exc:  # Explorer refused to launch
        raise HTTPException(status_code=409, detail=f"could not open the folder: {exc}") from exc
    return {"opened": True, "folder": opened, "raw_private_data_returned": False}


@app.post("/api/review/project")
async def review_project(request: Request):
    """Exceptions-only project review — analyze EVERY coil at once and return only the
    ones that need review, via independent triangulation.

    POST the submittal PDF bytes. The gate always uses the engine (blocked/undrawn
    values surface as exceptions); set ``X-CoilForge-Checklist: 1`` to also run the
    Oxygen8 checklist cross-check (engine vs Excel formulas — a mismatch is an
    exception). CCSI overrides (engine vs the printed CCSI export) come from the
    separate ``/api/ccsi/audit-export`` panel. ``exceptions_K`` is the count of coils
    that actually need John's eyes — independent of coil count on a clean project.
    Review aid only (``export_allowed: False``)."""
    from coilforge.review.project_gate import build_project_gate

    pdf_bytes = await request.body()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="POST the submittal PDF bytes.")
    try:
        result = run_pdf_to_drawing_workflow(
            pdf_bytes,
            source_id=request.headers.get("x-coilforge-source-id", "PROJECT-REVIEW-001"),
            source_filename=request.headers.get("x-coilforge-filename"),
            cover_page_hint=_cover_page_hint_from_request(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    checklist_review = None
    checklist_note = None
    if request.headers.get("x-coilforge-checklist", "").strip().lower() in ("1", "true", "yes"):
        checklist_review, checklist_note = await _try_checklist_review(pdf_bytes, request, result)

    gate = build_project_gate(result, checklist_review=checklist_review)
    if checklist_note:
        gate["summary"]["checklist_note"] = checklist_note
    _journal_milestone("project_review", result=result,
                       detail={"coils": gate["summary"]["coils"],
                               "exceptions_K": gate["summary"]["exceptions_K"]},
                       identity=_identity_from_request(request),
                       pdf_bytes=pdf_bytes,
                       cover_page_hint=_cover_page_hint_from_request(request),
                       # The gate John is actually shown — it may fold in the
                       # checklist cross-check, which a re-derivation would miss.
                       gate=gate)
    return jsonable_encoder(gate)


@app.get("/api/coil-drawing/product-options")
async def coil_drawing_product_options():
    """Valid product line -> unit sizes (R-076) for the per-coil picker that
    unlocks the rule-engine dimensions."""
    return {"product_lines": product_size_options()}


def _manual_fill_enabled() -> bool:
    """Kill switch (M-NEW-5): when ``COILFORGE_MANUAL_FILL`` is off, the /derive
    endpoint strips human-in-the-loop fills and the manual_fill_plan, restoring
    today's product/size-only behavior WITHOUT reverting the branch. Read at request
    time so it can be toggled in a running process / tests. Default ON."""
    return os.environ.get("COILFORGE_MANUAL_FILL", "1").strip().lower() not in (
        "0", "false", "no", "off", "",
    )


def _known_drawing_param_key(key: str) -> bool:
    from coilforge.drawing.parameters import DRAWING_PARAMETER_KEYS
    from coilforge.services.drawing_param_resolver import (
        EXTRA_DRAWING_PARAMS,
        is_multi_header_param_key,
    )

    return (
        key in DRAWING_PARAMETER_KEYS
        or key in EXTRA_DRAWING_PARAMS
        or is_multi_header_param_key(key)
    )


# Phase 2 spec-field edits (per-field lock): the engine-relevant spec inputs the engineer
# can feed/correct. Each already flows through the derive spec/ctx, so an edit re-derives
# (coating -> R-080/081/035c notes; the rest -> slots). Template-selection fields
# (hand/header_type/product/unit_size) are deliberately NOT here — they change which
# template is chosen and stay with the existing pickers/classification path.
_KNOWN_SPEC_FIELD_KEYS: frozenset[str] = frozenset(
    {"circuits", "rows", "feeds", "return_conn_size", "coating"}
)


def _sanitize_derive_spec(spec: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """API-boundary validation for /derive fills (M-NEW-2): require override_reason,
    coerce numeric params, reject unknown keys — so a bad fill yields a surfaced error,
    never a 500 or a stored junk value. Honors the kill switch. Returns (clean, errors)."""
    from coilforge.services.drawing_param_resolver import _coerce_float

    clean = dict(spec or {})
    errors: list[str] = []

    if not _manual_fill_enabled():
        clean.pop("param_overrides", None)
        clean.pop("spec_overrides", None)
        # The Direct Coil review-surface refresh rides the same feature, so the documented
        # kill switch has to strip its input too -- otherwise the refresh keeps running
        # with COILFORGE_MANUAL_FILL=0 and the env var stops being a whole-feature lever.
        clean.pop("candidate", None)
        for key in ("application", "header_count", "qty_conn_per_header"):
            clean.pop(key, None)
        return clean, errors

    # Source candidate for the Direct Coil review-surface refresh (TR-9). The workflow
    # validates it and checks its tag against the coil being derived; here we only reject
    # a non-object so a junk value never reaches model_validate.
    if "candidate" in clean and clean["candidate"] is not None:
        if not isinstance(clean["candidate"], dict):
            errors.append("candidate must be an object")
            clean.pop("candidate", None)

    valid_overrides: list[dict[str, Any]] = []
    for item in spec.get("param_overrides") or []:
        if not isinstance(item, dict):
            errors.append("param override must be an object")
            continue
        key = str(item.get("key") or "").strip()
        if not key or not _known_drawing_param_key(key):
            errors.append(f"unknown drawing param: {item.get('key')!r}")
            continue
        if not str(item.get("override_reason") or "").strip():
            errors.append(f"{key}: override_reason is required")
            continue
        value = _coerce_float(item.get("value"))
        if value is None:
            errors.append(f"{key}: value must be a number (got {item.get('value')!r})")
            continue
        if value < 0:
            errors.append(f"{key}: value must not be negative")
            continue
        valid_overrides.append({**item, "key": key, "value": value})
    if "param_overrides" in clean:
        clean["param_overrides"] = valid_overrides

    # Phase 2 spec-field overrides: {field_key, previous_value, new_value, override_reason}.
    # Captured as (before -> after) corrections at stage 'spec_field'. Values may be strings
    # (coating) or numbers (circuits/rows/feeds/conn) so they are NOT coerced to float here;
    # the engine-relevant ones are separately threaded into the derive spec by the frontend.
    valid_specs: list[dict[str, Any]] = []
    for item in spec.get("spec_overrides") or []:
        if not isinstance(item, dict):
            errors.append("spec override must be an object")
            continue
        field_key = str(item.get("field_key") or "").strip()
        if not field_key or field_key not in _KNOWN_SPEC_FIELD_KEYS:
            errors.append(f"unknown spec field: {item.get('field_key')!r}")
            continue
        if not str(item.get("override_reason") or "").strip():
            errors.append(f"{field_key}: override_reason is required")
            continue
        new_value = item.get("new_value")
        if new_value is None or (isinstance(new_value, str) and not new_value.strip()):
            errors.append(f"{field_key}: new_value is required")
            continue
        valid_specs.append(
            {
                "field_key": field_key,
                "previous_value": item.get("previous_value"),
                "new_value": new_value,
                "override_reason": str(item.get("override_reason")).strip(),
            }
        )
    if "spec_overrides" in clean:
        clean["spec_overrides"] = valid_specs

    for key in ("header_count", "qty_conn_per_header"):
        if clean.get(key) is not None:
            coerced = _coerce_float(clean.get(key))
            if coerced is None:
                errors.append(f"{key}: must be a number")
                clean.pop(key, None)
            else:
                clean[key] = int(coerced)
    return clean, errors


@app.post("/api/coil-drawing/derive")
async def coil_drawing_derive(request: dict[str, Any] = Body(default_factory=dict)):
    """Re-derive a coil's template drawing with an engineer-chosen product line +
    unit size and any human-in-the-loop manual fills (Tier-A engine inputs + Tier-B
    param overrides) so the engine fills / the user completes the dimensions.
    Review-aid only; never flips export_allowed. A bad fill is surfaced, never a 500."""
    from pydantic import ValidationError
    from coilforge.services.direct_coil_drawing_pipeline import UnknownCoilInputError

    spec = request or {}
    clean, errors = _sanitize_derive_spec(spec)
    try:
        # P0-B: a multi-coil re-analyze fires one /derive per coil concurrently from the
        # browser; offloading this CPU-bound derive lets those actually run in parallel
        # instead of serializing on the event loop.
        result = await asyncio.to_thread(derive_coil_template_drawing, clean)
    except (UnknownCoilInputError, ValidationError) as exc:
        # Never 500 on a fill: return a minimal payload naming what to fix.
        return jsonable_encoder(
            {
                "manual_fill_plan": {"items": [], "withheld_reason": None},
                "manual_fill_errors": errors + [str(exc)],
                "export_allowed": False,
            }
        )
    if not _manual_fill_enabled():
        result.pop("manual_fill_plan", None)
    if errors:
        # MERGE, never assign: the workflow puts its own skip reasons here (e.g. the coil
        # tag could not be verified, so the Direct Coil review fields were not refreshed).
        # Assigning would drop that reason whenever any unrelated sanitizer error fired --
        # and an unexplained stale panel is exactly the failure this reporting exists for.
        existing = result.get("manual_fill_errors")
        result["manual_fill_errors"] = (list(existing) if existing else []) + errors
    # request_payload=clean carries the coil tag (singular) and the project
    # identity the frontend now sends; derive's result has neither pdf_intake_summary
    # nor pdf_coil_pages, so without this the milestone hits the identity gate and
    # journals nothing. (clean is a plain dict copy -- _sanitize_derive_spec never
    # dropped project_number/project_name, so they pass straight through.)
    _journal_milestone("coil_manual_fill", result=result, request_payload=clean)
    return jsonable_encoder(result)


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
