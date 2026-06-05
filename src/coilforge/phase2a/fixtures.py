from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from coilforge.phase2a.models import (
    DEFAULT_DRAWING_STATUS,
    DEFAULT_FIXTURE_NAME,
    DEFAULT_RELEASE_STATUS,
    DxHeader1ParameterState,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FIXTURE_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "dx_header1_ezc0001_default.json"
)
FIXTURE_METADATA_KEYS = {"fixture_name", "fixture_status"}


def load_default_dx_header1_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the public sanitized fixture only."""
    try:
        fixture = json.loads(DEFAULT_FIXTURE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError("Sanitized Phase 2A fixture is missing.") from None
    except json.JSONDecodeError as exc:
        raise RuntimeError("Sanitized Phase 2A fixture is malformed.") from exc

    state_payload = {
        key: value for key, value in fixture.items() if key not in FIXTURE_METADATA_KEYS
    }
    state_payload.setdefault("coil_category", "DX")
    state_payload.setdefault("header_type", "Header 1")
    state_payload.setdefault("release_status", DEFAULT_RELEASE_STATUS)
    state_payload.setdefault("drawing_status", DEFAULT_DRAWING_STATUS)

    metadata = {
        "fixture_name": fixture.get("fixture_name", DEFAULT_FIXTURE_NAME),
        "fixture_status": fixture.get("fixture_status", "sanitized_example"),
        "source_case_id": state_payload.get("source_case_id", "EZC-0001"),
    }
    return state_payload, metadata


def load_default_dx_header1_state() -> DxHeader1ParameterState:
    state_payload, _metadata = load_default_dx_header1_fixture()
    return DxHeader1ParameterState.model_validate(state_payload)
