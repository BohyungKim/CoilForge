from __future__ import annotations

import hashlib
import json
from typing import Any

from coilforge.phase2a.models import (
    DEFAULT_FIXTURE_NAME,
    DEFAULT_RELEASE_STATUS,
    ChecklistSnapshot,
    DrawingMetadata,
    DxHeader1ParameterState,
)
from coilforge.phase2a.renderer import DEFAULT_VIEWBOX, TEMPLATE_ID
from coilforge.phase2a.validation import ValidationReport, validate_dx_header1_state


def _stable_suffix(*parts: Any) -> str:
    payload = json.dumps(parts, default=str, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _coerce_report(
    state: DxHeader1ParameterState,
    validation_report: ValidationReport | dict[str, Any] | None,
) -> ValidationReport:
    if isinstance(validation_report, ValidationReport):
        return validation_report
    if isinstance(validation_report, dict) and validation_report:
        return ValidationReport.model_validate(validation_report)
    return validate_dx_header1_state(state)


def generate_checklist_snapshot(
    state: DxHeader1ParameterState,
    validation_report: ValidationReport | dict[str, Any] | None = None,
    *,
    source_fixture: str = DEFAULT_FIXTURE_NAME,
) -> ChecklistSnapshot:
    report = _coerce_report(state, validation_report)
    suffix = _stable_suffix(state.model_dump(), report.validation_status)
    return ChecklistSnapshot(
        snapshot_id=f"chk_phase2a_{suffix}",
        source_fixture=source_fixture,
        state=state,
        validation_status=report.validation_status,
    )


def generate_drawing_metadata(
    state: DxHeader1ParameterState,
    validation_report: ValidationReport | dict[str, Any] | None = None,
    renderer_metadata: dict[str, Any] | None = None,
) -> DrawingMetadata:
    report = _coerce_report(state, validation_report)
    renderer_metadata = renderer_metadata or {}
    suffix = _stable_suffix(state.model_dump(), report.validation_status, renderer_metadata)
    blocked = report.validation_status == "blocked"
    drawing_status = renderer_metadata.get(
        "drawing_status",
        "generation_blocked" if blocked else "generated_with_warnings",
    )
    return DrawingMetadata(
        drawing_generation_run_id=renderer_metadata.get(
            "drawing_generation_run_id", f"draw_phase2a_{suffix}"
        ),
        drawing_status=drawing_status,
        release_status=DEFAULT_RELEASE_STATUS,
        template_id=renderer_metadata.get("template_id", TEMPLATE_ID),
        viewBox=renderer_metadata.get("viewBox", DEFAULT_VIEWBOX),
        source_case_id=state.source_case_id,
        warnings=list(dict.fromkeys(report.warnings + renderer_metadata.get("warnings", []))),
        blocked_fields=list(
            dict.fromkeys(report.blocked_fields + renderer_metadata.get("blocked_fields", []))
        ),
        john_review_required=True,
    )
