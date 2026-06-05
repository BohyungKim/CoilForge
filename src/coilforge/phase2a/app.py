from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from coilforge.phase2a.fixtures import load_default_dx_header1_fixture
from coilforge.phase2a.models import DxHeader1ParameterState
from coilforge.phase2a.renderer import SvgRenderRequest, render_dx_header1_svg
from coilforge.phase2a.snapshot import (
    generate_checklist_snapshot,
    generate_drawing_metadata,
)
from coilforge.phase2a.validation import validate_dx_header1_state


REPO_ROOT = Path(__file__).resolve().parents[3]
WEB_DIR = REPO_ROOT / "web"

app = FastAPI(
    title="CoilForge Phase 2A Local MVP",
    version="0.2.0",
    description="Local-only DX Header 1 / EZC-0001 review-aid vertical slice.",
)
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


def _error_response(
    code: str,
    message: str,
    *,
    status_code: int = 400,
    details: list[Any] | None = None,
    blocked_fields: list[str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "blocked_fields": blocked_fields or [],
            }
        },
    )


def _validation_error_response(exc: ValidationError) -> JSONResponse:
    details = exc.errors()
    blocked_fields = [
        ".".join(str(part) for part in error.get("loc", [])) for error in details
    ]
    return _error_response(
        "phase2a_validation_error",
        "Payload failed Phase 2A model validation.",
        details=details,
        blocked_fields=blocked_fields,
    )


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    index_path = WEB_DIR / "index.html"
    try:
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return HTMLResponse(
            "<h1>CoilForge Phase 2A</h1><p>Local UI is missing.</p>",
            status_code=500,
        )


@app.get("/api/default-state")
async def get_default_state() -> Any:
    try:
        state_payload, fixture_metadata = load_default_dx_header1_fixture()
        state = DxHeader1ParameterState.model_validate(state_payload)
    except RuntimeError as exc:
        return _error_response(
            "phase2a_fixture_unavailable",
            str(exc),
            status_code=500,
        )
    except ValidationError as exc:
        return _validation_error_response(exc)

    return {
        "state": state.model_dump(),
        "fixture": fixture_metadata,
        "warnings": [],
    }


@app.post("/api/validate")
async def validate_state(state: dict[str, Any] = Body(...)) -> dict[str, Any]:
    report = validate_dx_header1_state(state)
    return report.model_dump()


@app.post("/api/render-svg")
async def render_svg(request: dict[str, Any] = Body(...)) -> Any:
    try:
        render_request = SvgRenderRequest.model_validate(request)
    except ValidationError as exc:
        return _validation_error_response(exc)

    response = render_dx_header1_svg(render_request)
    return response.model_dump()


@app.post("/api/generate-snapshot")
async def generate_snapshot(request: dict[str, Any] = Body(...)) -> Any:
    try:
        state = DxHeader1ParameterState.model_validate(request.get("state") or {})
        validation_report = request.get("validation_report")
        renderer_metadata = request.get("renderer_metadata") or {}
        checklist_snapshot = generate_checklist_snapshot(state, validation_report)
        drawing_metadata = generate_drawing_metadata(
            state,
            validation_report,
            renderer_metadata=renderer_metadata,
        )
    except ValidationError as exc:
        return _validation_error_response(exc)

    return {
        "checklist_snapshot": checklist_snapshot.model_dump(),
        "drawing_metadata": drawing_metadata.model_dump(),
        "warnings": drawing_metadata.warnings,
    }
