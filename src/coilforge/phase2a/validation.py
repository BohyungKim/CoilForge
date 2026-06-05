from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field, ValidationError

from coilforge.phase2a.models import (
    DEFAULT_DRAWING_STATUS,
    DEFAULT_RELEASE_STATUS,
    DxHeader1ParameterState,
    state_to_dict,
)


CheckStatus = Literal["pass", "warn", "fail", "blocked", "not_applicable"]
Severity = Literal["info", "warning", "error", "blocking_error"]

REQUIRED_STATE_FIELDS = [
    "coil_name",
    "model_number",
    "source_case_id",
    "rows",
    "fin_height",
    "fin_length",
    "fin_density_fpi",
    "casing_height",
    "casing_length",
    "casing_depth",
    "top_flange",
    "bottom_flange",
    "return_bend_allowance",
    "coil_hand",
    "airflow_direction",
    "return_connection_size",
    "circuiting_display",
]

SAFE_DRAWING_STATUSES = {
    DEFAULT_DRAWING_STATUS,
    "generated_review_aid",
    "generated_with_warnings",
}
MANUFACTURING_STATUS_TOKENS = {
    "approved_for_manufacturing",
    "manufacturing",
    "released",
    "release_approved",
    "approved_outside_coilforge",
}
OAL_FIELDS = ("oal", "overall_length", "overall_length_oal")


class ValidationCheck(BaseModel):
    check_id: str
    status: CheckStatus
    severity: Severity
    target: str
    message: str
    requires_review: bool = False
    expected_value: Any = None
    actual_value: Any = None


class ValidationReport(BaseModel):
    validation_status: Literal["pass", "pass_with_warnings", "fail", "blocked"]
    summary: dict[str, int]
    checks: list[ValidationCheck] = Field(default_factory=list)
    blocked_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return len(value) == 0
    return False


def _status_counts(checks: list[ValidationCheck]) -> dict[str, int]:
    return {
        "pass_count": sum(check.status == "pass" for check in checks),
        "warn_count": sum(check.status == "warn" for check in checks),
        "fail_count": sum(check.status == "fail" for check in checks),
        "blocked_count": sum(check.status == "blocked" for check in checks),
        "not_applicable_count": sum(check.status == "not_applicable" for check in checks),
    }


def _overall_status(checks: list[ValidationCheck]) -> str:
    if any(check.status == "blocked" for check in checks):
        return "blocked"
    if any(check.status == "fail" for check in checks):
        return "fail"
    if any(check.status == "warn" for check in checks):
        return "pass_with_warnings"
    return "pass"


def _has_manufacturing_language(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return any(token in normalized for token in MANUFACTURING_STATUS_TOKENS)


def _coerce_raw_payload(
    state: DxHeader1ParameterState | Mapping[str, Any],
) -> dict[str, Any]:
    payload = state_to_dict(state)
    payload.setdefault("coil_category", "DX")
    payload.setdefault("header_type", "Header 1")
    payload.setdefault("release_status", DEFAULT_RELEASE_STATUS)
    payload.setdefault("drawing_status", DEFAULT_DRAWING_STATUS)
    return payload


def validate_dx_header1_state(
    state: DxHeader1ParameterState | Mapping[str, Any],
) -> ValidationReport:
    payload = _coerce_raw_payload(state)
    checks: list[ValidationCheck] = []
    blocked_fields: list[str] = []
    warnings: list[str] = []

    if _is_blank(payload.get("coil_name")):
        blocked_fields.append("coil_name")
        checks.append(
            ValidationCheck(
                check_id="phase2a_required_coil_name",
                status="fail",
                severity="error",
                target="coil_name",
                message="coil_name is required for the Phase 2A checklist state.",
                expected_value="non-empty string",
                actual_value=payload.get("coil_name"),
            )
        )
    else:
        checks.append(
            ValidationCheck(
                check_id="phase2a_required_coil_name",
                status="pass",
                severity="info",
                target="coil_name",
                message="coil_name is present.",
                actual_value=payload.get("coil_name"),
            )
        )

    missing_fields = [
        field
        for field in REQUIRED_STATE_FIELDS
        if field != "coil_name" and _is_blank(payload.get(field))
    ]
    for field in missing_fields:
        blocked_fields.append(field)
        status: CheckStatus = "blocked" if field == "airflow_direction" else "fail"
        checks.append(
            ValidationCheck(
                check_id=f"phase2a_required_{field}",
                status=status,
                severity="blocking_error" if status == "blocked" else "error",
                target=field,
                message=f"{field} is required for the DX Header 1 MVP slice.",
                expected_value="non-empty value",
                actual_value=payload.get(field),
            )
        )

    if not missing_fields:
        try:
            DxHeader1ParameterState.model_validate(payload)
        except ValidationError as exc:
            for error in exc.errors():
                field = ".".join(str(part) for part in error.get("loc", []))
                blocked_fields.append(field)
                checks.append(
                    ValidationCheck(
                        check_id=f"phase2a_model_field_{field}",
                        status="fail",
                        severity="error",
                        target=field,
                        message=error.get("msg", "Field failed model validation."),
                        actual_value=payload.get(field),
                    )
                )

    category = payload.get("coil_category")
    if category == "DX":
        checks.append(
            ValidationCheck(
                check_id="phase2a_category_dx",
                status="pass",
                severity="info",
                target="coil_category",
                message="Coil category is supported for Phase 2A.",
                expected_value="DX",
                actual_value=category,
            )
        )
    else:
        blocked_fields.append("coil_category")
        checks.append(
            ValidationCheck(
                check_id="phase2a_category_dx",
                status="blocked",
                severity="blocking_error",
                target="coil_category",
                message="Phase 2A supports DX only. Unsupported categories are blocked.",
                expected_value="DX",
                actual_value=category,
                requires_review=True,
            )
        )

    header_type = payload.get("header_type")
    if header_type == "Header 1":
        checks.append(
            ValidationCheck(
                check_id="phase2a_header1_only",
                status="pass",
                severity="info",
                target="header_type",
                message="Header type is supported for Phase 2A.",
                expected_value="Header 1",
                actual_value=header_type,
            )
        )
    else:
        blocked_fields.append("header_type")
        checks.append(
            ValidationCheck(
                check_id="phase2a_header1_only",
                status="blocked",
                severity="blocking_error",
                target="header_type",
                message="Phase 2A supports Header 1 only. Unsupported headers are blocked.",
                expected_value="Header 1",
                actual_value=header_type,
                requires_review=True,
            )
        )

    airflow_direction = payload.get("airflow_direction")
    if _is_blank(airflow_direction):
        blocked_fields.append("airflow_direction")
        checks.append(
            ValidationCheck(
                check_id="phase2a_required_airflow_direction",
                status="blocked",
                severity="blocking_error",
                target="airflow_direction",
                message="airflow_direction is required and must not be inferred silently.",
                expected_value="explicit reviewed airflow direction",
                actual_value=airflow_direction,
                requires_review=True,
            )
        )
    else:
        checks.append(
            ValidationCheck(
                check_id="phase2a_required_airflow_direction",
                status="pass",
                severity="info",
                target="airflow_direction",
                message="airflow_direction is explicit in the current state.",
                actual_value=airflow_direction,
                requires_review=True,
            )
        )

    oal_requested = bool(payload.get("oal_generation_requested"))
    oal_value_present = any(not _is_blank(payload.get(field)) for field in OAL_FIELDS)
    if oal_requested or oal_value_present:
        blocked_fields.append("OAL")
        checks.append(
            ValidationCheck(
                check_id="phase2a_oal_not_approved",
                status="blocked",
                severity="blocking_error",
                target="OAL",
                message="OAL active generation is not approved for Phase 2A.",
                expected_value="OAL: REVIEW REQUIRED",
                actual_value={
                    field: payload.get(field)
                    for field in ("oal_generation_requested", *OAL_FIELDS)
                    if field in payload
                },
                requires_review=True,
            )
        )
    else:
        warning = "OAL is not generated in Phase 2A; renderer must show OAL: REVIEW REQUIRED."
        warnings.append(warning)
        checks.append(
            ValidationCheck(
                check_id="phase2a_oal_not_approved",
                status="warn",
                severity="warning",
                target="OAL",
                message=warning,
                expected_value="OAL: REVIEW REQUIRED",
                actual_value=None,
                requires_review=True,
            )
        )

    release_status = payload.get("release_status", DEFAULT_RELEASE_STATUS)
    if release_status == DEFAULT_RELEASE_STATUS:
        checks.append(
            ValidationCheck(
                check_id="phase2a_release_status_safe",
                status="pass",
                severity="info",
                target="release_status",
                message="release_status is review_aid_only.",
                expected_value=DEFAULT_RELEASE_STATUS,
                actual_value=release_status,
            )
        )
    elif _has_manufacturing_language(release_status):
        blocked_fields.append("release_status")
        checks.append(
            ValidationCheck(
                check_id="phase2a_release_status_safe",
                status="blocked",
                severity="blocking_error",
                target="release_status",
                message="Manufacturing-like release_status is not allowed.",
                expected_value=DEFAULT_RELEASE_STATUS,
                actual_value=release_status,
                requires_review=True,
            )
        )
    else:
        warning = "release_status is not manufacturing-like, but Phase 2A normalizes metadata to review_aid_only."
        warnings.append(warning)
        checks.append(
            ValidationCheck(
                check_id="phase2a_release_status_safe",
                status="warn",
                severity="warning",
                target="release_status",
                message=warning,
                expected_value=DEFAULT_RELEASE_STATUS,
                actual_value=release_status,
                requires_review=True,
            )
        )

    drawing_status = payload.get("drawing_status", DEFAULT_DRAWING_STATUS)
    if drawing_status in SAFE_DRAWING_STATUSES:
        checks.append(
            ValidationCheck(
                check_id="phase2a_drawing_status_safe",
                status="pass",
                severity="info",
                target="drawing_status",
                message="drawing_status is safe for a review-aid workflow.",
                expected_value=sorted(SAFE_DRAWING_STATUSES),
                actual_value=drawing_status,
            )
        )
    else:
        blocked_fields.append("drawing_status")
        checks.append(
            ValidationCheck(
                check_id="phase2a_drawing_status_safe",
                status="blocked" if _has_manufacturing_language(drawing_status) else "fail",
                severity=(
                    "blocking_error"
                    if _has_manufacturing_language(drawing_status)
                    else "error"
                ),
                target="drawing_status",
                message="drawing_status must remain a non-release review-aid status.",
                expected_value=sorted(SAFE_DRAWING_STATUSES),
                actual_value=drawing_status,
                requires_review=True,
            )
        )

    checks.append(
        ValidationCheck(
            check_id="phase2a_full_json_adapter_not_applicable",
            status="not_applicable",
            severity="info",
            target="json_import_export_adapter",
            message="The full JSON import/export adapter is out of scope for Phase 2A.",
        )
    )

    unique_blocked_fields = list(dict.fromkeys(blocked_fields))
    return ValidationReport(
        validation_status=_overall_status(checks),
        summary=_status_counts(checks),
        checks=checks,
        blocked_fields=unique_blocked_fields,
        warnings=list(dict.fromkeys(warnings)),
    )
