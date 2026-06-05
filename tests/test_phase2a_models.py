from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.phase2a.fixtures import (
    load_default_dx_header1_fixture,
    load_default_dx_header1_state,
)
from coilforge.phase2a.models import (
    DEFAULT_DRAWING_STATUS,
    DEFAULT_RELEASE_STATUS,
    DxHeader1ParameterState,
)


def test_default_fixture_loads_dx_header1_state() -> None:
    state = load_default_dx_header1_state()

    assert state.coil_name == "SAMPLE_DX_HEADER1"
    assert state.model_number == "DX-SAMPLE-HEADER1"
    assert state.coil_category == "DX"
    assert state.header_type == "Header 1"
    assert state.source_case_id == "EZC-0001"
    assert state.release_status == DEFAULT_RELEASE_STATUS
    assert state.drawing_status == DEFAULT_DRAWING_STATUS


def test_fixture_metadata_stays_separate_from_state() -> None:
    state_payload, metadata = load_default_dx_header1_fixture()

    assert "fixture_name" not in state_payload
    assert "fixture_status" not in state_payload
    assert metadata["fixture_name"] == "sanitized_dx_header1_ezc0001_default"
    assert metadata["source_case_id"] == "EZC-0001"


def test_model_applies_safe_status_defaults() -> None:
    state_payload, _metadata = load_default_dx_header1_fixture()
    state_payload.pop("release_status")
    state_payload.pop("drawing_status")

    state = DxHeader1ParameterState.model_validate(state_payload)

    assert state.release_status == DEFAULT_RELEASE_STATUS
    assert state.drawing_status == DEFAULT_DRAWING_STATUS


def test_model_rejects_invalid_numeric_values() -> None:
    state_payload, _metadata = load_default_dx_header1_fixture()
    state_payload["rows"] = 0

    with pytest.raises(ValidationError):
        DxHeader1ParameterState.model_validate(state_payload)
