from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.direct_coil import map_canonical_to_direct_coil_draft
from coilforge.drawing import (
    DRAWING_PARAMETER_KEYS,
    DrawingParameterOverride,
    PreviewDefaultValue,
    resolve_drawing_parameters,
)
from coilforge.submittal import load_submittal_candidate_fixture
from coilforge.submittal.to_canonical import map_submittal_candidate_to_canonical


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "submittal_candidate_dx_header1_default.json"
)


def test_resolver_includes_all_drawing_parameters() -> None:
    parameter_set = resolve_drawing_parameters(_build_draft_from_sanitized_candidate())

    assert set(parameter_set.parameters) == set(DRAWING_PARAMETER_KEYS)
    assert list(parameter_set.parameters) == list(DRAWING_PARAMETER_KEYS)
    assert len(parameter_set.parameters) == 13


def test_missing_required_drawing_parameters_remain_blocked() -> None:
    parameter_set = resolve_drawing_parameters(_build_draft_from_sanitized_candidate())

    assert {"CD", "BF", "TF", "CH"}.issubset(set(parameter_set.blocked_parameters))
    for key in ("CD", "BF", "TF", "CH"):
        parameter = parameter_set.parameters[key]
        assert parameter.status == "blocked"
        assert parameter.blocked_reason == "required preview parameter missing"
    assert parameter_set.preview_allowed is False


def test_manual_override_is_preserved_and_review_required() -> None:
    parameter_set = resolve_drawing_parameters(
        _build_draft_from_sanitized_candidate(),
        manual_overrides=[
            DrawingParameterOverride(
                key="CD",
                value=5.5,
                unit="in",
                override_reason="sanitized manual preview entry",
                reviewed_by="SANITIZED_REVIEWER",
            )
        ],
    )

    parameter = parameter_set.parameters["CD"]
    assert parameter.value == 5.5
    assert parameter.mode == "manual"
    assert parameter.manual_override is True
    assert parameter.status == "review_required"
    assert parameter.review_required is True


def test_default_preview_value_is_review_required_not_ready() -> None:
    parameter_set = resolve_drawing_parameters(
        _build_draft_from_sanitized_candidate(),
        default_preview_values=[
            PreviewDefaultValue(key="CD", value=5.5),
        ],
    )

    parameter = parameter_set.parameters["CD"]
    assert parameter.value == 5.5
    assert parameter.mode == "default"
    assert parameter.status == "review_required"
    assert parameter.review_required is True
    assert parameter.source_evidence[0].source_type == "sanitized_fixture/default"


def test_preview_allowed_only_when_required_preview_parameters_are_present() -> None:
    draft = _build_draft_from_sanitized_candidate()
    blocked_set = resolve_drawing_parameters(draft)
    preview_set = resolve_drawing_parameters(
        draft,
        default_preview_values=[
            PreviewDefaultValue(key="CD", value=5.5),
            PreviewDefaultValue(key="BF", value=0.63),
            PreviewDefaultValue(key="TF", value=0.63),
            PreviewDefaultValue(key="CH", value=13.25),
        ],
    )

    assert blocked_set.preview_allowed is False
    assert preview_set.preview_allowed is True
    assert preview_set.review_required_parameters
    for key in ("CD", "BF", "TF", "CH"):
        assert preview_set.parameters[key].status == "review_required"


def test_export_allowed_remains_false() -> None:
    parameter_set = resolve_drawing_parameters(
        _build_draft_from_sanitized_candidate(),
        default_preview_values=[
            PreviewDefaultValue(key="CD", value=5.5),
            PreviewDefaultValue(key="BF", value=0.63),
            PreviewDefaultValue(key="TF", value=0.63),
            PreviewDefaultValue(key="CH", value=13.25),
        ],
    )

    assert parameter_set.preview_allowed is True
    assert parameter_set.export_allowed is False


def test_no_final_engineering_formula_is_claimed() -> None:
    parameter_set = resolve_drawing_parameters(
        _build_draft_from_sanitized_candidate(),
        default_preview_values=[
            PreviewDefaultValue(key="CD", value=5.5),
            PreviewDefaultValue(key="BF", value=0.63),
            PreviewDefaultValue(key="TF", value=0.63),
            PreviewDefaultValue(key="CH", value=13.25),
        ],
    )

    assert all(parameter.mode != "derived" for parameter in parameter_set.parameters.values())
    assert parameter_set.export_allowed is False
    assert "No engineering formulas are applied by this resolver." in parameter_set.notes


def _build_draft_from_sanitized_candidate():
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)
    record = map_submittal_candidate_to_canonical(candidate)
    return map_canonical_to_direct_coil_draft(record)
