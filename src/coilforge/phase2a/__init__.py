"""Phase 2A local web MVP package."""

from coilforge.phase2a.fixtures import load_default_dx_header1_state
from coilforge.phase2a.models import ChecklistSnapshot, DxHeader1ParameterState
from coilforge.phase2a.renderer import REVIEW_WATERMARK, render_dx_header1_svg
from coilforge.phase2a.snapshot import (
    generate_checklist_snapshot,
    generate_drawing_metadata,
)
from coilforge.phase2a.validation import validate_dx_header1_state

__all__ = [
    "ChecklistSnapshot",
    "DxHeader1ParameterState",
    "REVIEW_WATERMARK",
    "generate_checklist_snapshot",
    "generate_drawing_metadata",
    "load_default_dx_header1_state",
    "render_dx_header1_svg",
    "validate_dx_header1_state",
]
