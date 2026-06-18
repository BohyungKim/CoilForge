from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SourceEvidenceConfidence = Literal["confirmed", "inferred", "ambiguous", "missing"]
ReviewStatus = Literal["unreviewed", "review_required", "reviewed", "rejected"]
EvidenceStatus = Literal["candidate", "confirmed", "rejected", "superseded"]


class SourceEvidence(BaseModel):
    """Sanitized trace from a source artifact to a candidate field value."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    source_type: str
    source_id: str
    source_location: str
    source_page: int | None = None
    source_section: str | None = None
    source_table: str | None = None
    source_key: str | None = None
    source_value: Any = None
    normalized_value: Any = None
    unit: str | None = None
    confidence: SourceEvidenceConfidence = "inferred"
    review_status: ReviewStatus = "unreviewed"
    evidence_status: EvidenceStatus = "candidate"
    notes: list[str] = Field(default_factory=list)

    @field_validator(
        "evidence_id",
        "source_type",
        "source_id",
        "source_location",
        "source_section",
        "source_table",
        "source_key",
        "unit",
        mode="before",
    )
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
