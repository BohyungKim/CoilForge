from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


DEFAULT_RELEASE_STATUS = "review_aid_only"
DEFAULT_DRAWING_STATUS = "not_generated"
DEFAULT_SNAPSHOT_STATUS = "draft_review_aid"
DEFAULT_FIXTURE_NAME = "sanitized_dx_header1_ezc0001_default"


class DxHeader1ParameterState(BaseModel):
    """Editable Phase 2A DX Header 1 state.

    Scope checks are intentionally handled by the validation engine so the UI can
    show unsupported category/header edits as visible blockers instead of a 422.
    """

    model_config = ConfigDict(extra="allow")

    coil_name: str
    model_number: str
    coil_category: str = "DX"
    header_type: str = "Header 1"
    source_case_id: str = "EZC-0001"
    rows: int = Field(gt=0)
    fin_height: float = Field(gt=0)
    fin_length: float = Field(gt=0)
    fin_density_fpi: float = Field(gt=0)
    casing_height: float = Field(gt=0)
    casing_length: float = Field(gt=0)
    casing_depth: float = Field(gt=0)
    top_flange: float = Field(ge=0)
    bottom_flange: float = Field(ge=0)
    return_bend_allowance: float = Field(ge=0)
    coil_hand: str
    airflow_direction: str
    return_connection_size: float = Field(gt=0)
    circuiting_display: str
    notes: list[str] = Field(default_factory=list)
    release_status: str = DEFAULT_RELEASE_STATUS
    drawing_status: str = DEFAULT_DRAWING_STATUS

    @field_validator(
        "coil_name",
        "model_number",
        "coil_category",
        "header_type",
        "source_case_id",
        "coil_hand",
        "airflow_direction",
        "circuiting_display",
        "release_status",
        "drawing_status",
        mode="before",
    )
    @classmethod
    def normalize_string(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []


class ChecklistSnapshot(BaseModel):
    snapshot_id: str
    snapshot_status: str = DEFAULT_SNAPSHOT_STATUS
    source_fixture: str = DEFAULT_FIXTURE_NAME
    state: DxHeader1ParameterState
    validation_status: str
    created_by: str = "coilforge_local_mvp"


class DrawingMetadata(BaseModel):
    drawing_generation_run_id: str
    drawing_status: str
    release_status: str = DEFAULT_RELEASE_STATUS
    template_id: str = "phase2a_dx_header1_review_svg"
    viewBox: str = "0 0 1600 1200"
    source_case_id: str = "EZC-0001"
    warnings: list[str] = Field(default_factory=list)
    blocked_fields: list[str] = Field(default_factory=list)
    john_review_required: bool = True


def state_to_dict(state: DxHeader1ParameterState | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(state, DxHeader1ParameterState):
        return state.model_dump()
    return dict(state)
