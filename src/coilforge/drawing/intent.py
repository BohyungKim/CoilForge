from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from coilforge.contracts.evidence import SourceEvidence
from coilforge.drawing.parameters import DrawingParameter


class DrawingIntent(BaseModel):
    """Renderer-facing drawing intent. Review aid only."""

    model_config = ConfigDict(extra="forbid")

    coil_name: str
    product_type: str | None = None
    coil_type: str | None = None
    header_type: str
    airflow_direction: str
    finned_height: float
    finned_length: float
    rows_deep: int
    fins_per_inch: float
    tubes_high: int | None = None
    coil_hand: str
    return_connection_size: float
    drawing_parameters: dict[str, DrawingParameter]
    title_block: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    source_evidence_summary: dict[str, list[str]] = Field(default_factory=dict)
    review_status: str = "review_required"
    preview_allowed: bool
    export_allowed: bool = False
    blocked_reasons: list[str] = Field(default_factory=list)


class DrawingPreviewResult(BaseModel):
    """SVG preview response with review-required metadata."""

    model_config = ConfigDict(extra="forbid")

    intent: DrawingIntent
    svg: str
    metadata: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    blocked_fields: list[str] = Field(default_factory=list)
