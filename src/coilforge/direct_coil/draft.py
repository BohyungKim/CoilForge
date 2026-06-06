from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from coilforge.contracts.evidence import SourceEvidence


DirectCoilDraftFieldStatus = Literal[
    "ready",
    "review_required",
    "blocked",
    "unmapped",
    "manual_override",
]


class DirectCoilDraftField(BaseModel):
    """Direct Coil-facing draft field with traceability and readiness metadata."""

    model_config = ConfigDict(extra="forbid")

    field_key: str
    label: str
    group: str
    value: Any = None
    unit: str | None = None
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    mapping_rule: str
    status: DirectCoilDraftFieldStatus
    review_required: bool = True
    blocked_reason: str | None = None
    manual_override: bool = False

    @field_validator("field_key", "label", "group", "unit", "mapping_rule", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value).strip()


class DirectCoilDraftSummary(BaseModel):
    ready: int = 0
    review_required: int = 0
    blocked: int = 0
    unmapped: int = 0
    manual_override: int = 0


class DirectCoilInputDraft(BaseModel):
    """Review-only Direct Coil input draft. This is not an export payload."""

    model_config = ConfigDict(extra="forbid")

    draft_id: str
    source_canonical_record_id: str
    groups: dict[str, list[str]]
    fields: dict[str, DirectCoilDraftField]
    summary: DirectCoilDraftSummary
    export_status: str = "not_implemented"
