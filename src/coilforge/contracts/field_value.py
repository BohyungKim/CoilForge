from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from coilforge.contracts.evidence import SourceEvidence


FieldStatus = Literal[
    "ready",
    "review_required",
    "blocked",
    "unmapped",
    "manual_override",
]
FieldConfidence = Literal["confirmed", "inferred", "ambiguous", "missing"]


class FieldValue(BaseModel):
    """Traceable wrapper for imported, prepopulated, or reviewed field values."""

    model_config = ConfigDict(extra="forbid")

    value: Any = None
    unit: str | None = None
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    confidence: FieldConfidence = "inferred"
    status: FieldStatus = "review_required"
    review_required: bool = True
    blocked_reason: str | None = None
    manual_override: bool = False
    notes: list[str] = Field(default_factory=list)

    @field_validator("unit", "blocked_reason", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> str | None:
        if value is None:
            return None
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

    @model_validator(mode="after")
    def require_evidence_for_prepopulated_values(self) -> FieldValue:
        if self.value is not None and not self.manual_override and not self.source_evidence:
            raise ValueError("source_evidence is required for imported or prepopulated values")
        if self.status == "blocked" and not self.blocked_reason:
            raise ValueError("blocked fields require blocked_reason")
        return self
