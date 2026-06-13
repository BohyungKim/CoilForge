from __future__ import annotations

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
from coilforge.submittal.pdf_intake import extract_coil_candidate_from_pdf_bytes
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
                "return_header_diameter": 3.5,
                "distributor_header_diameter": 4.5,
                "return_stub_length": 8.0,
                "supply_offset_i1": 3.0,
                "supply_spacing_s1": 2.75,
                "return_offset_o2": 2.0,
                "return_spacing_r2": 0.63,
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
                "header_face": 1.5,
                "return_face": 1.5,
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
    # Strong CoilMaster-drawing extraction -> linked, populated template-first
    # drawing (reads the scanned drawing's as-built values directly).
    try:
        from coilforge.submittal.pdf_to_template_drawing import (
            pdf_bytes_to_template_drawing,
        )

        selected_result["template_drawing"] = pdf_bytes_to_template_drawing(pdf_bytes)
    except Exception as exc:  # never break the existing workflow on extraction issues
        selected_result["template_drawing"] = {"error": str(exc)}
    return selected_result


def _run_candidate_to_drawing_payload(
    selected_candidate,
    *,
    pdf_intake_summary: dict[str, Any] | None,
    source_id: str,
    preview_defaults: list[dict[str, Any]] | None,
    title_block: dict[str, Any] | None,
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
