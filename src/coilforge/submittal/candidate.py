from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from coilforge.contracts import FieldValue, SourceEvidence
from coilforge.interfaces.direct_coil import is_header_type_supported


CandidateReviewStatus = Literal["unreviewed", "review_required", "reviewed", "blocked"]


class UnmappedField(BaseModel):
    """Preserved source field without an approved CoilForge mapping."""

    model_config = ConfigDict(extra="forbid")

    source_key: str
    source_value: Any = None
    reason: str
    source_evidence: list[SourceEvidence] = Field(default_factory=list)

    @field_validator("source_key", "reason", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()


class SubmittalCoilCandidate(BaseModel):
    """Review-first candidate created from sanitized submittal evidence."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    tag: FieldValue | None = None
    product_type: FieldValue | None = None
    coil_type: FieldValue | None = None
    header_type: FieldValue | None = None
    geometry: dict[str, FieldValue] = Field(default_factory=dict)
    airside_conditions: dict[str, FieldValue] = Field(default_factory=dict)
    refrigerant_conditions: dict[str, FieldValue] = Field(default_factory=dict)
    materials_construction: dict[str, FieldValue] = Field(default_factory=dict)
    connections: dict[str, FieldValue] = Field(default_factory=dict)
    performance: dict[str, FieldValue] = Field(default_factory=dict)
    drawing_parameters: dict[str, FieldValue] = Field(default_factory=dict)
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    review_required_fields: list[str] = Field(default_factory=list)
    blocked_fields: list[str] = Field(default_factory=list)
    unmapped_fields: list[UnmappedField] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    review_status: CandidateReviewStatus = "unreviewed"

    @field_validator("candidate_id", mode="before")
    @classmethod
    def normalize_candidate_id(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("review_required_fields", "blocked_fields", "notes", mode="before")
    @classmethod
    def normalize_string_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []

    @model_validator(mode="after")
    def apply_candidate_blocking_policy(self) -> SubmittalCoilCandidate:
        blocked_fields = list(dict.fromkeys(self.blocked_fields))
        review_required_fields = list(dict.fromkeys(self.review_required_fields))

        if self.tag is None or self.tag.value in (None, ""):
            blocked_fields.append("tag")

        if self.header_type is not None and self.header_type.value not in (None, ""):
            if not is_header_type_supported(str(self.header_type.value)):
                blocked_fields.append("header_type")

        for field_name in ("tag", "product_type", "coil_type", "header_type"):
            field_value = getattr(self, field_name)
            if field_value is not None and field_value.review_required:
                review_required_fields.append(field_name)

        for group_name in (
            "geometry",
            "airside_conditions",
            "refrigerant_conditions",
            "materials_construction",
            "connections",
            "performance",
            "drawing_parameters",
        ):
            group = getattr(self, group_name)
            for key, field_value in group.items():
                if field_value.review_required:
                    review_required_fields.append(f"{group_name}.{key}")
                if field_value.status == "blocked":
                    blocked_fields.append(f"{group_name}.{key}")

        self.blocked_fields = list(dict.fromkeys(blocked_fields))
        self.review_required_fields = list(dict.fromkeys(review_required_fields))
        if self.blocked_fields and self.review_status == "reviewed":
            self.review_status = "blocked"
        return self


def load_submittal_candidate_fixture(path: str | Path) -> SubmittalCoilCandidate:
    fixture_path = Path(path)
    return SubmittalCoilCandidate.model_validate_json(
        fixture_path.read_text(encoding="utf-8")
    )
