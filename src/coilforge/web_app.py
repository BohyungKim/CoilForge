import asyncio
import copy
import hashlib
import os

from collections import OrderedDict
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
                       detail: dict | None = None,
                       identity: str | None = None,
                       pdf_bytes: bytes | None = None,
                       cover_page_hint: int | None = None,
                       product: str | None = None,
                       size: str | None = None,
                       gate: dict | None = None) -> None:
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
        product=product, size=size, identity=identity, gate=gate,
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
        result = run_pdf_to_drawing_workflow(
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
_CHECKLIST_CACHE_MAXSIZE = 32
_CHECKLIST_CACHE: "OrderedDict[tuple[str, str | None, str | None, int | None], dict[str, Any]]" = (
    OrderedDict()
)


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
) -> _ChecklistOutcome:
    """Fill the Coil Checklist for a submittal PDF and return its review table,
    reusing an already-generated result (and its Downloads .xlsx) when the same PDF
    bytes were filled before. Never raises: returns an outcome whose ``review`` is
    ``None`` with a ``reason`` when no recognizable coils exist or Excel/pywin32 is
    unavailable, so callers degrade cleanly."""
    if not pdf_bytes:
        return _ChecklistOutcome(None, None, "POST the submittal PDF bytes.", 400)

    # cover_page_hint is in the key (like _WORKFLOW_CACHE): reselecting the cover
    # page on the same bytes changes which coils are read, so it must not hit a
    # stale entry computed under the previous selection.
    key = (hashlib.sha1(pdf_bytes).hexdigest(), product, size, cover_page_hint)
    cached = _CHECKLIST_CACHE.get(key)
    if cached is not None:
        saved_path = cached.get("saved_path")
        if not saved_path or Path(saved_path).exists():
            _CHECKLIST_CACHE.move_to_end(key)
            return _ChecklistOutcome(
                copy.deepcopy(cached["review"]), saved_path, None, None
            )
        # The filled copy was deleted -- drop the stale entry and regenerate.
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
        fill = build_checklist_fill(coils)
        writer_result = await asyncio.to_thread(
            write_checklist, fill, dest_name=_checklist_output_name(filename)
        )
        review = build_review(fill, writer_result)
    except RuntimeError as exc:  # Excel / pywin32 unavailable
        return _ChecklistOutcome(None, None, str(exc), 501)
    except Exception as exc:  # noqa: BLE001 -- surface COM/fill failures clearly
        return _ChecklistOutcome(None, None, f"Excel write failed: {exc}", 500)

    saved_path = (writer_result or {}).get("saved_path")
    _CHECKLIST_CACHE[key] = {"review": review, "saved_path": saved_path}
    _CHECKLIST_CACHE.move_to_end(key)
    while len(_CHECKLIST_CACHE) > _CHECKLIST_CACHE_MAXSIZE:
        _CHECKLIST_CACHE.popitem(last=False)
    return _ChecklistOutcome(
        copy.deepcopy(review), saved_path, None, None, workflow_result=result
    )


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
    outcome = await _run_or_reuse_checklist(
        pdf_bytes,
        product=request.headers.get("x-coilforge-product"),
        size=request.headers.get("x-coilforge-size"),
        filename=request.headers.get("x-coilforge-filename"),
        cover_page_hint=_cover_page_hint_from_request(request),
        source_id=request.headers.get("x-coilforge-source-id", "CHECKLIST-FILL-001"),
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
        )
    return jsonable_encoder(outcome.review)


async def _try_checklist_review(pdf_bytes: bytes, request: Request, result: dict):
    """Best-effort engine-vs-checklist cross-check (Excel COM). Returns
    ``(review, None)`` or ``(None, reason)`` — never raises, so the project gate
    degrades to engine-only when Excel/pywin32 is absent. Shares the checklist
    cache, so a project review reuses an already-generated fill. ``result`` is the
    caller's workflow dict, kept for signature stability; the fill is re-derived
    (and memoized) from ``pdf_bytes`` inside the helper."""
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
    """Finalize a DirectCoil deliverable: file the original quote, the revised quote,
    and the auto-generated Coil Checklist into the project's
    ``…/02 - POs/<project>/Accessory Order Forms/DirectCoil`` folder (only the
    ``DirectCoil`` leaf is created if absent), then open a pre-filled Outlook DRAFT
    (subject ``Coils: <#> - <name>``, revised PDF attached) — never sent.

    POST JSON: ``submittal_pdf_base64`` (project identity + checklist),
    ``quote_pdf_base64`` (original source quote), ``revised_pdf_base64`` (the built
    revised PDF), plus ``submittal_filename`` / ``quote_filename``. Original PDFs are
    copied, never modified. Review aid only (``export_allowed: False``)."""
    import asyncio

    from coilforge.deliverable.finalize import (
        FinalizeError,
        deliverable_subject,
        place_bytes,
        place_copy,
        resolve_directcoil_folder,
    )
    from coilforge.deliverable.outlook_draft import open_deliverable_draft

    payload = await request.json()
    submittal = _b64_to_bytes(payload.get("submittal_pdf_base64"), "submittal_pdf_base64")
    quote = _b64_to_bytes(payload.get("quote_pdf_base64"), "quote_pdf_base64")
    revised = _b64_to_bytes(payload.get("revised_pdf_base64"), "revised_pdf_base64")
    quote_name = Path(payload.get("quote_filename") or "quote.pdf").name
    submittal_name = payload.get("submittal_filename")

    # Project identity from the submittal intake.
    try:
        result = run_pdf_to_drawing_workflow(
            submittal,
            source_id="DELIVERABLE-FINALIZE-001",
            source_filename=submittal_name,
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
    checklist_outcome = await _run_or_reuse_checklist(
        submittal, filename=submittal_name, source_id="DELIVERABLE-FINALIZE-001"
    )
    checklist_path = checklist_outcome.saved_path
    checklist_status = "ok" if checklist_outcome.review is not None else (
        checklist_outcome.reason or "unavailable"
    )

    # Resolve/create the DirectCoil folder and file the docs (copies, never moves).
    try:
        folder = resolve_directcoil_folder(project_number)
    except FinalizeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    revised_name = f"{Path(quote_name).stem}_Revised.pdf"
    files_written = [
        place_bytes(folder, quote_name, quote),
        place_bytes(folder, revised_name, revised),
    ]
    if checklist_path and Path(checklist_path).exists():
        files_written.append(
            place_copy(folder, Path(checklist_path).name, checklist_path)
        )

    # Open the Outlook draft with the revised PDF attached (never sent).
    subject = deliverable_subject(project_number, project_name)
    try:
        await asyncio.to_thread(
            open_deliverable_draft,
            subject=subject,
            to=_DELIVERABLE_TO,
            cc=_DELIVERABLE_CC,
            attachment_path=files_written[1],
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
        "project_number": project_number,
        "project_name": project_name,
        "subject": subject,
        "folder": str(folder),
        "files_written": files_written,
        "checklist_status": checklist_status,
        "draft_opened": draft_opened,
        "draft_status": draft_status,
        "email_sent": False,
        "review_aid_only": True,
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
        "raw_private_data_returned": False,
    }


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


def _sanitize_derive_spec(spec: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """API-boundary validation for /derive fills (M-NEW-2): require override_reason,
    coerce numeric params, reject unknown keys — so a bad fill yields a surfaced error,
    never a 500 or a stored junk value. Honors the kill switch. Returns (clean, errors)."""
    from coilforge.services.drawing_param_resolver import _coerce_float

    clean = dict(spec or {})
    errors: list[str] = []

    if not _manual_fill_enabled():
        clean.pop("param_overrides", None)
        for key in ("application", "header_count", "qty_conn_per_header"):
            clean.pop(key, None)
        return clean, errors

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
        result = derive_coil_template_drawing(clean)
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
        result["manual_fill_errors"] = errors
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
