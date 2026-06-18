"""Tests for engine-generated drawing parameters (replacing demo constants)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    build_default_demo_workflow_input,
    run_submittal_to_drawing_workflow,
)


def _run_demo():
    return run_submittal_to_drawing_workflow(build_default_demo_workflow_input()["input"])


def test_drawing_params_are_engine_generated_not_hardcoded() -> None:
    out = _run_demo()
    params = out["drawing_parameter_set"]["parameters"]

    def src(key: str) -> str:
        return (params[key]["source_evidence"] or [{}])[0].get("source_type", "")

    # Engine-generated values (correct, not the rounded 0.63 demo constants).
    assert params["TF"]["value"] == 0.625 and src("TF") == "rule_engine/generated"
    assert params["BF"]["value"] == 0.625 and src("BF") == "rule_engine/generated"
    assert params["CD"]["value"] == 5.5 and src("CD") == "rule_engine/generated"
    assert params["HD"]["value"] == 3.5 and src("HD") == "rule_engine/generated"  # suction
    assert params["I"]["value"] == 3 and src("I") == "rule_engine/generated"
    assert params["O"]["value"] == 2 and src("O") == "rule_engine/generated"
    assert params["SL"]["value"] == 8 and src("SL") == "rule_engine/generated"


def test_generation_report_lists_connected_and_unconnected() -> None:
    out = _run_demo()
    gen = out["drawing_parameter_generation"]
    assert gen["source"] == "rule_engine"
    # Engine connects these (incl. recovered logic: CH=FH+TF+BF, S=CD/(C+1)).
    for key in ("CD", "TF", "BF", "HF", "RF", "HD", "SL", "I", "O", "CH", "S"):
        assert key in gen["connected"], key
    # ZD has no rule anywhere (SOP/checklist/JSON) -> reported, not invented.
    assert "ZD" in gen["not_connected"]


def test_recovered_ch_and_s_match_asbuilt() -> None:
    out = _run_demo()
    params = out["drawing_parameter_set"]["parameters"]

    def src(key: str) -> str:
        return (params[key]["source_evidence"] or [{}])[0].get("source_type", "")

    assert params["CH"]["value"] == 13.25 and src("CH") == "rule_engine/generated"  # FH+TF+BF
    assert params["S"]["value"] == 2.75 and src("S") == "rule_engine/generated"  # CD/2


def test_distributor_hd_has_its_own_param_key() -> None:
    out = _run_demo()
    params = out["drawing_parameter_set"]["parameters"]
    assert params["HDx1"]["value"] == 4.5  # distributor HD
    assert params["HD"]["value"] == 3.5     # suction/return HD


def test_multi_circuit_s_sourced_from_ez_json_headers() -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from coilforge.direct_coil.draft import DirectCoilInputDraft
    from coilforge.services.drawing_param_resolver import engine_preview_values

    draft = DirectCoilInputDraft.model_validate(_run_demo()["direct_coil_input_draft"])
    multi = {"Geometry": {"FH": 26.0, "FL": 34.0, "CD": 5.5, "TSP": 0.625, "BSP": 0.625, "Headers": [
        {"ID": 1, "IsSupply": True, "HD": 4.5, "IO": [3.0], "SR": 1.875, "SL": [0]},
        {"ID": 2, "IsSupply": False, "HD": 3.5, "IO": [2.0], "SR": 1.125, "SL": [8.0]},
        {"ID": 3, "IsSupply": True, "HD": 4.5, "IO": [3.0], "SR": 3.625, "SL": [0]},
        {"ID": 4, "IsSupply": False, "HD": 3.5, "IO": [2.0], "SR": 3.75, "SL": [8.0]}]}}
    values, report = engine_preview_values(
        draft, coil_type="DX", product_type="NOVA", unit_size="B20",
        circuits=2, ez_json=multi,
    )
    by_key = {v.key: v for v in values}
    # Multi-circuit S comes exactly from Headers[0].SR (engine formula is single-only).
    assert by_key["S"].value == 1.875 and by_key["S"].source == "ez_json/as_built"
    assert "S" in report["json_sourced"]


def test_unconnected_params_fall_back_so_preview_still_allowed() -> None:
    out = _run_demo()
    params = out["drawing_parameter_set"]["parameters"]
    # CH is a REQUIRED preview param with no engine rule -> must still be filled
    # from the static fallback so the preview is not blocked.
    assert params["CH"]["value"] == 13.25
    assert out["drawing_parameter_set"]["preview_allowed"] is True
