from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from coilforge.contracts.evidence import SourceEvidence
from coilforge.contracts.field_value import FieldValue
from coilforge.submittal.candidate import UnmappedField


CanonicalValidationStatus = Literal[
    "not_validated",
    "review_required",
    "blocked",
    "validated",
]


class ManualOverride(BaseModel):
    """Explicit reviewed change that must not erase prior evidence."""

    model_config = ConfigDict(extra="forbid")

    target_field: str
    previous_value: Any = None
    override_value: Any = None
    override_reason: str
    reviewed_by: str | None = None
    review_status: str = "unreviewed"
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    downstream_effects: list[str] = Field(default_factory=list)

    @field_validator(
        "target_field",
        "override_reason",
        "reviewed_by",
        "review_status",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value).strip()

    @field_validator("downstream_effects", mode="before")
    @classmethod
    def normalize_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []


class CanonicalCoilRecord(BaseModel):
    """Shared review-first CoilForge core record."""

    model_config = ConfigDict(extra="forbid")

    record_id: str
    project: dict[str, FieldValue] = Field(default_factory=dict)
    coil_identity: dict[str, FieldValue] = Field(default_factory=dict)
    product_type: FieldValue | None = None
    coil_type: FieldValue | None = None
    header_type: FieldValue | None = None
    geometry: dict[str, FieldValue] = Field(default_factory=dict)
    airside_conditions: dict[str, FieldValue] = Field(default_factory=dict)
    refrigerant_conditions: dict[str, FieldValue] = Field(default_factory=dict)
    materials_construction: dict[str, FieldValue] = Field(default_factory=dict)
    connections: dict[str, FieldValue] = Field(default_factory=dict)
    manufacturing_options: dict[str, FieldValue] = Field(default_factory=dict)
    drawing_parameters: dict[str, FieldValue] = Field(default_factory=dict)
    performance: dict[str, FieldValue] = Field(default_factory=dict)
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    unmapped_fields: list[UnmappedField] = Field(default_factory=list)
    review_required_fields: list[str] = Field(default_factory=list)
    blocked_fields: list[str] = Field(default_factory=list)
    manual_overrides: list[ManualOverride] = Field(default_factory=list)
    validation_status: CanonicalValidationStatus = "not_validated"

    @field_validator("record_id", mode="before")
    @classmethod
    def normalize_record_id(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("review_required_fields", "blocked_fields", mode="before")
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
    def collect_review_required_fields(self) -> CanonicalCoilRecord:
        review_required_fields = list(dict.fromkeys(self.review_required_fields))
        blocked_fields = list(dict.fromkeys(self.blocked_fields))

        for field_name in ("product_type", "coil_type", "header_type"):
            field_value = getattr(self, field_name)
            if field_value is not None and field_value.review_required:
                review_required_fields.append(field_name)
            if field_value is not None and field_value.status == "blocked":
                blocked_fields.append(field_name)

        for group_name in (
            "project",
            "coil_identity",
            "geometry",
            "airside_conditions",
            "refrigerant_conditions",
            "materials_construction",
            "connections",
            "manufacturing_options",
            "drawing_parameters",
            "performance",
        ):
            for key, field_value in getattr(self, group_name).items():
                path = f"{group_name}.{key}"
                if field_value.review_required:
                    review_required_fields.append(path)
                if field_value.status == "blocked":
                    blocked_fields.append(path)

        self.review_required_fields = list(dict.fromkeys(review_required_fields))
        self.blocked_fields = list(dict.fromkeys(blocked_fields))
        return self
