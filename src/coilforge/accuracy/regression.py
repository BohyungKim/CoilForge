from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from coilforge.workflows import (
    build_default_demo_workflow_input,
    run_submittal_to_drawing_workflow,
)


@dataclass(frozen=True)
class AccuracyMismatch:
    path: str
    expected: Any
    actual: Any

    def format(self) -> str:
        return f"{self.path}: expected {self.expected!r}, actual {self.actual!r}"


@dataclass(frozen=True)
class AccuracyComparison:
    passed: bool
    mismatches: list[AccuracyMismatch]

    def readable_diff(self) -> str:
        if not self.mismatches:
            return "No accuracy mismatches."
        return "\n".join(mismatch.format() for mismatch in self.mismatches)


def load_expected_summary(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_submittal_to_drawing_summary(
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workflow_input = payload or build_default_demo_workflow_input()["input"]
    workflow = run_submittal_to_drawing_workflow(workflow_input)
    return summarize_submittal_to_drawing_workflow(workflow)


def summarize_submittal_to_drawing_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    candidate = workflow["candidates"][0]
    readiness = workflow["readiness_report"]
    metadata = workflow["metadata"]
    validation = workflow["validation"]
    drawing_intent = workflow["drawing_intent"]
    parameter_set = workflow["drawing_parameter_set"]

    return {
        "fixture_format_version": 1,
        "workflow": "phase2b_submittal_to_drawing",
        "input_policy": {
            "source": "sanitized_demo",
            "raw_private_text_expected": False,
            "pdf_parser_expected": False,
            "ocr_expected": False,
        },
        "candidate": {
            "count": len(workflow["candidates"]),
            "selected_tag": workflow["selected_candidate_summary"]["tag"],
            "review_status": workflow["selected_candidate_summary"]["review_status"],
            "review_required_count": len(
                workflow["selected_candidate_summary"]["review_required_fields"]
            ),
            "blocked_field_keys": sorted(workflow["selected_candidate_summary"]["blocked_fields"]),
            "unmapped_source_keys": sorted(
                field["source_key"] for field in candidate["unmapped_fields"]
            ),
        },
        "canonical": {
            "validation_status": workflow["canonical_summary"]["validation_status"],
            "blocked_fields": sorted(workflow["canonical_summary"]["blocked_fields"]),
            "review_required_count": len(workflow["canonical_summary"]["review_required_fields"]),
            "unmapped_field_count": workflow["canonical_summary"]["unmapped_field_count"],
        },
        "direct_coil_draft": {
            "field_count": len(workflow["direct_coil_input_draft"]["fields"]),
            "summary_counts": _count_subset(workflow["direct_coil_input_draft"]["summary"]),
            "export_status": workflow["direct_coil_input_draft"]["export_status"],
        },
        "readiness_report": {
            "total_fields": readiness["total_fields"],
            "summary_counts": _count_subset(readiness["summary_counts"]),
            "blocked_field_keys": sorted(field["field_key"] for field in readiness["blocked_fields"]),
            "review_required_field_keys": sorted(
                field["field_key"] for field in readiness["review_required_fields"]
            ),
            "unmapped_field_keys": sorted(field["field_key"] for field in readiness["unmapped_fields"]),
            "required_missing_field_keys": sorted(
                field["field_key"] for field in readiness["required_missing_fields"]
            ),
            "export_status": readiness["export_status"],
        },
        "source_evidence": {
            "fields_with_source_evidence": readiness["source_evidence_summary"][
                "fields_with_source_evidence"
            ],
            "total_source_evidence_refs": readiness["source_evidence_summary"][
                "total_source_evidence_refs"
            ],
            "field_keys": sorted(
                readiness["source_evidence_summary"]["evidence_ids_by_field"].keys()
            ),
            "raw_private_text_present": False,
        },
        "drawing": {
            "preview_allowed": drawing_intent["preview_allowed"],
            "export_allowed": drawing_intent["export_allowed"],
            "review_status": drawing_intent["review_status"],
            "blocked_reasons": sorted(drawing_intent["blocked_reasons"]),
            "svg_returned": bool(workflow["svg"]),
            "review_watermark_present": "REVIEW AID - NOT FOR MANUFACTURING" in workflow["svg"],
            "metadata": {
                "drawing_status": metadata.get("drawing_status"),
                "preview_allowed": metadata.get("preview_allowed"),
                "export_allowed": metadata.get("export_allowed"),
                "john_review_required": metadata.get("john_review_required"),
                "release_status": metadata.get("release_status"),
                "review_status": metadata.get("review_status"),
                "template_id": metadata.get("template_id"),
                "viewBox": metadata.get("viewBox"),
            },
            "parameter_set": {
                "preview_allowed": parameter_set["preview_allowed"],
                "export_allowed": parameter_set["export_allowed"],
                "blocked_parameters": sorted(parameter_set["blocked_parameters"]),
                "review_required_parameters": sorted(
                    parameter_set["review_required_parameters"]
                ),
                "required_preview_parameters": sorted(
                    parameter_set["required_preview_parameters"]
                ),
            },
        },
        "validation": {
            "workflow_status": validation["workflow_status"],
            "preview_allowed": validation["preview_allowed"],
            "export_allowed": validation["export_allowed"],
            "export_status": validation["export_status"],
            "drawing_status": validation["drawing_status"],
            "raw_private_data_returned": validation["raw_private_data_returned"],
            "drawing_approval_claimed": validation["drawing_approval_claimed"],
        },
    }


def compare_accuracy_summary(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> AccuracyComparison:
    mismatches: list[AccuracyMismatch] = []
    _compare_value("$", actual, expected, mismatches)
    return AccuracyComparison(passed=not mismatches, mismatches=mismatches)


def _compare_value(
    path: str,
    actual: Any,
    expected: Any,
    mismatches: list[AccuracyMismatch],
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            mismatches.append(AccuracyMismatch(path, expected, actual))
            return
        for key in sorted(expected):
            if key not in actual:
                mismatches.append(AccuracyMismatch(f"{path}.{key}", expected[key], "<missing>"))
                continue
            _compare_value(f"{path}.{key}", actual[key], expected[key], mismatches)
        for key in sorted(set(actual) - set(expected)):
            mismatches.append(AccuracyMismatch(f"{path}.{key}", "<absent>", actual[key]))
        return

    if isinstance(expected, list):
        if actual != expected:
            mismatches.append(AccuracyMismatch(path, expected, actual))
        return

    if actual != expected:
        mismatches.append(AccuracyMismatch(path, expected, actual))


def _count_subset(counts: dict[str, Any]) -> dict[str, int]:
    return {
        "ready": int(counts["ready"]),
        "review_required": int(counts["review_required"]),
        "blocked": int(counts["blocked"]),
        "unmapped": int(counts["unmapped"]),
    }
