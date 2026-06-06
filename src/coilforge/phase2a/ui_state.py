from __future__ import annotations

from typing import Any

from coilforge.workflows import build_default_demo_workflow_input, run_submittal_to_drawing_workflow


def build_phase2b_default_ui_state() -> dict[str, Any]:
    demo = build_default_demo_workflow_input()
    workflow = run_submittal_to_drawing_workflow(demo["input"])
    readiness = workflow["readiness_report"]
    draft = workflow["direct_coil_input_draft"]
    drawing_intent = workflow["drawing_intent"]
    drawing_parameters = workflow["drawing_parameter_set"]

    return {
        "project": {
            "project_id": "SANITIZED-PROJECT-001",
            "project_name": "Sanitized CoilForge Demo",
            "coil_tag": workflow["selected_candidate_summary"]["tag"],
            "revision": "Rev A - Draft",
            "saved_status": "Draft saved locally",
            "breadcrumb": ["CoilForge", "Sanitized Demo", "DX Header 1"],
        },
        "import_summary": {
            "source_type": "sanitized_text",
            "candidate_count": len(workflow["candidates"]),
            "selected_candidate": workflow["selected_candidate_summary"],
            "raw_private_data_included": False,
            "pdf_parser_enabled": False,
            "ocr_enabled": False,
        },
        "direct_coil_draft": {
            "draft_id": draft["draft_id"],
            "source_canonical_record_id": draft["source_canonical_record_id"],
            "groups": draft["groups"],
            "fields": draft["fields"],
            "summary": draft["summary"],
            "export_status": draft["export_status"],
        },
        "readiness_report": readiness,
        "drawing_intent": drawing_intent,
        "drawing_parameters": drawing_parameters,
        "performance_summary": _build_performance_summary(draft),
        "validation": {
            **workflow["validation"],
            "readiness_counts": readiness["summary_counts"],
            "blocked_fields": [
                field["field_key"] for field in readiness["blocked_fields"]
            ],
            "review_required_fields": [
                field["field_key"] for field in readiness["review_required_fields"]
            ],
            "unmapped_field_count": len(readiness["unmapped_fields"]),
        },
        "source_evidence": {
            "summary": readiness["source_evidence_summary"],
            "fields": _source_evidence_fields(readiness),
        },
        "drawing_preview": {
            "svg": workflow["svg"],
            "metadata": workflow["metadata"],
            "preview_allowed": workflow["validation"]["preview_allowed"],
            "export_allowed": workflow["validation"]["export_allowed"],
        },
        "actions": {
            "save_draft": {"enabled": False, "placeholder": True},
            "analyze": {"enabled": True, "placeholder": False},
            "apply_to_direct_coil_draft": {"enabled": True, "placeholder": False},
            "update_drawing": {"enabled": True, "placeholder": False},
            "export_pdf": {"enabled": False, "placeholder": True},
        },
    }


def _build_performance_summary(draft: dict[str, Any]) -> dict[str, Any]:
    fields = draft["fields"]
    keys = (
        "total_air_flow_cfm",
        "entering_dry_bulb_f",
        "total_capacity_mbh",
        "refrigerant",
    )
    return {
        key: {
            "label": fields[key]["label"],
            "value": fields[key]["value"],
            "unit": fields[key]["unit"],
            "status": fields[key]["status"],
        }
        for key in keys
        if key in fields
    }


def _source_evidence_fields(readiness: dict[str, Any]) -> list[dict[str, Any]]:
    fields = readiness["review_required_fields"] + readiness["blocked_fields"]
    return [
        {
            "field_key": field["field_key"],
            "label": field["label"],
            "status": field["status"],
            "evidence_ids": [
                evidence["evidence_id"] for evidence in field.get("source_evidence", [])
            ],
        }
        for field in fields
        if field.get("source_evidence")
    ]
