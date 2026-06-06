from typing import Any

from fastapi import Body

from coilforge.phase2a.app import app
from coilforge.phase2a.fixtures import load_default_dx_header1_fixture
from coilforge.phase2a.renderer import DEFAULT_VIEWBOX, REVIEW_WATERMARK
from coilforge.workflows import (
    build_default_demo_workflow_input,
    run_submittal_to_direct_draft_workflow,
    run_submittal_to_drawing_workflow,
)


def load_default_state():
    """Compatibility wrapper for the earlier Phase 2A web shell entrypoint."""
    return load_default_dx_header1_fixture()


__all__ = ["DEFAULT_VIEWBOX", "REVIEW_WATERMARK", "app", "load_default_state"]


@app.get("/api/workflow/default-demo")
async def workflow_default_demo():
    return build_default_demo_workflow_input()


@app.post("/api/workflow/submittal-to-direct-draft")
async def workflow_submittal_to_direct_draft(request: dict[str, Any] = Body(default_factory=dict)):
    return run_submittal_to_direct_draft_workflow(request or {})


@app.post("/api/workflow/submittal-to-drawing")
async def workflow_submittal_to_drawing(request: dict[str, Any] = Body(default_factory=dict)):
    return run_submittal_to_drawing_workflow(request or {})
