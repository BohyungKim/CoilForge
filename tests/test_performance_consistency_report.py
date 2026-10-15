from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import performance_consistency_report as script  # noqa: E402
from coilforge.corpus.performance_consistency_report import (  # noqa: E402
    ReportInputError,
    build_report,
    inputs_from_crosscheck_coil,
    load_cache_coils,
    render_markdown,
    select_cache_files,
    validate_crosscheck_document,
)

VERSION = "v-test"


def _row(ccsi_id, coilforge, ccsi=None, verdict="match"):
    return {"ccsi_id": ccsi_id, "source_key": "x", "coilforge": coilforge, "ccsi": ccsi, "verdict": verdict}


def _coil(tag, coil_type, **values):
    return {"tag": tag, "coil_type": coil_type, "rows": [_row(k, v) for k, v in values.items()]}


def _heating(tag="RHHGRC-1", edb="51", capacity="44.58", acfm="Actual"):
    coil = _coil(tag, "HGRH", TotalAirFlow="4000", AirFlowPerCoil="2000", CoilQuantity="2",
                 EnteringDryBulb=edb, LeavingDryBulb="70.88", Altitude="0", Capacity=capacity)
    coil["rows"].append(_row("ACFM", None, acfm, "unmapped_ccsi_field"))
    return coil


def _water(tag, fluid, glycol, flow, quantity, ewt, lwt, capacity):
    # Air side made Standard-consistent for the stated capacity, so only the fluid side is under test.
    leaving_air = f"{60 + float(capacity) / 1.085:.4f}"
    return _coil(tag, "HWC", AirFlowPerCoil="1000", EnteringDryBulb="60", LeavingDryBulb=leaving_air, Altitude="0",
                 Capacity=capacity, FluidType=fluid, GlycolRatio=glycol, FluidFlowRate=flow,
                 CoilQuantity=quantity, EnteringFluidTemp=ewt, LeavingFluidTemp=lwt)


def _doc(*coils):
    return {"code_version": VERSION, "projects": [{"project": "9001", "coils": list(coils)}]}


# --- adapter ----------------------------------------------------------------------------------

def test_adapter_keys_by_ccsi_id_and_takes_the_per_coil_airflow():
    sources = inputs_from_crosscheck_coil(_heating())
    assert sources["total_air_flow_cfm"] == "2000"  # AirFlowPerCoil, not TotalAirFlow (x quantity)


def test_adapter_divides_the_all_coils_flow_by_quantity():
    # 3154 HHWC-1 shape: the crosscheck column carries 1.98 GPM for three coils.
    sources = inputs_from_crosscheck_coil(_water("HHWC-1", "Water", "0", "1.98", "3", "122", "104", "5.8"))
    assert sources["airside_conditions.fluid_flow_rate_gpm"] == pytest.approx(0.66)


def test_adapter_restores_the_submittal_fluid_statement():
    water = inputs_from_crosscheck_coil(_water("HHWC-1", "Water", "0", "9.69", "1", "160", "130", "142.31"))
    glycol = inputs_from_crosscheck_coil(_water("PHWC-1", "Propylene Glycol", "40", "12.2", "1", "115", "95", "113.27"))
    assert (water["airside_conditions.fluid_type"], water["airside_conditions.fluid_percent"]) == ("Water", 100.0)
    assert (glycol["airside_conditions.fluid_type"], glycol["airside_conditions.fluid_percent"]) == ("Propylene Glycol", 40.0)


def test_adapter_reads_water_under_either_column_convention():
    # A crosscheck produced before the map's glycol_ratio transform carries the submittal's own 100.
    sources = inputs_from_crosscheck_coil(_water("HHWC-1", "Water", "100", "9.69", "1", "160", "130", "142.31"))
    assert (sources["airside_conditions.fluid_type"], sources["airside_conditions.fluid_percent"]) == ("Water", 100.0)


def test_adapter_leaves_a_self_contradicting_fluid_out():
    sources = inputs_from_crosscheck_coil(_water("HHWC-1", "Water", "20", "9.69", "1", "160", "130", "142.31"))
    assert "airside_conditions.fluid_type" not in sources


def test_band_self_check_says_how_many_coils_it_covered():
    unread = build_report(_doc(_water("HHWC-1", "Water", "20", "9.69", "1", "160", "130", "142.31")))
    assert (unread["fluid"]["band_self_check_outside"], unread["fluid"]["band_self_check_coils"]) == (0, 0)
    read = build_report(_doc(_water("HHWC-1", "Water", "0", "9.69", "1", "160", "130", "142.31")))
    assert (read["fluid"]["band_self_check_outside"], read["fluid"]["band_self_check_coils"]) == (0, 1)


# --- report -----------------------------------------------------------------------------------

def test_report_counts_bases_and_lists_the_inconsistent_coil():
    doc = _doc(_heating(), _heating("RHHGRC-2", edb="54", capacity="60.0", acfm="Standard"),
               _water("PHWC-1", "Propylene Glycol", "40", "12.2", "1", "115", "95", "113.27"))
    report = build_report(doc)
    assert report["heating"]["evaluable"] == 3
    assert report["heating"]["verdicts"]["actual"] == 1
    assert [c["tag"] for c in report["heating"]["inconsistent"]] == ["RHHGRC-2"]
    assert {"basis": "actual", "report_acfm": "Actual", "coils": 1} in report["heating"]["basis_vs_report_acfm"]
    assert report["fluid"]["band_self_check_outside"] == 0
    assert report["review_aid_only"] is True and report["export_allowed"] is False
    assert len(report["heating"]["sweep"]) == 12
    assert "F 1.085, tol ±0.02" in render_markdown(report)


def test_band_self_check_reports_a_coil_outside_its_unmargined_band():
    # 486 sits inside the +/- 3 % margin (consistent) but outside the 488-503 band itself.
    doc = _doc(_water("HHWC-9", "Water", "0", "10", "1", "140", "120", "97.2"))
    report = build_report(doc)
    assert report["fluid"]["groups"][0]["verdicts"] == {"consistent": 1}
    assert report["fluid"]["band_self_check_outside"] == 1
    assert report["fluid"]["groups"][0]["outside_unmargined_band"] == ["9001 HHWC-9"]


def test_validate_reports_structure_drift():
    assert validate_crosscheck_document(_doc(_heating())) == []
    assert validate_crosscheck_document({"projects": {}})
    assert validate_crosscheck_document({"projects": [{"project": "1", "coils": [{"tag": "A"}]}]})
    renamed = _doc(_heating())
    for row in renamed["projects"][0]["coils"][0]["rows"]:
        row["field"] = row.pop("ccsi_id")
    assert validate_crosscheck_document(renamed)
    assert validate_crosscheck_document(_doc(_coil("CDXC-1", "DX", Tag="CDXC-1")))  # no Capacity / airflow row at all


# --- sources cache ----------------------------------------------------------------------------

def _cache_file(cache_dir, sha, version, mtime, tag="CDXC-1"):
    path = cache_dir / f"{sha}_{version}_abc.json"
    sources = {"airside_conditions.total_air_flow_cfm": {"value": 1030, "unit": "cfm"},
               "airside_conditions.entering_dry_bulb_f": {"value": 86.1, "unit": "degF"},
               "airside_conditions.leaving_dry_bulb_f": {"value": 52.27, "unit": "degF"},
               "airside_conditions.altitude_ft": {"value": 43, "unit": "ft"},
               "performance.total_capacity_mbh": {"value": 134.31, "unit": "MBH"},
               "performance.sensible_capacity_mbh": {"value": 40.29, "unit": "MBH"}}
    path.write_text(json.dumps({"skip": None, "coils": [{"tag": tag, "coil_type": "DX", "sources": sources}]}),
                    encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def test_cache_selection_keeps_the_code_version_and_the_latest_per_pdf(tmp_path):
    old_code = _cache_file(tmp_path, "aaa", "v-old", 300)
    _cache_file(tmp_path, "aaa", VERSION, 100).rename(tmp_path / f"aaa_{VERSION}_first.json")
    newest = _cache_file(tmp_path, "aaa", VERSION, 200)
    other = _cache_file(tmp_path, "bbb", VERSION, 50)
    orphan = _cache_file(tmp_path, "ccc", "v-old", 400)  # only an older code version exists
    selected = select_cache_files(tmp_path, VERSION)
    assert selected == [newest, other]
    assert old_code not in selected and orphan not in selected


def test_dx_sensible_balance_is_measured_from_the_push_time_sources(tmp_path):
    _cache_file(tmp_path, "aaa", VERSION, 100, tag="CDXC-2")
    report = build_report(_doc(_heating()), load_cache_coils(tmp_path, VERSION))
    dx = report["push_time_sources"]["dx_sensible"]
    assert (dx["coils"], dx["evaluable"], dx["verdicts"]) == (1, 1, {"inconsistent": 1})
    assert dx["inconsistent"][0]["k"] == pytest.approx(1.156, abs=0.001)


def test_a_truncated_cache_file_is_refused(tmp_path):
    (tmp_path / f"aaa_{VERSION}_abc.json").write_text('{"coils": [{"tag": "CDXC-1", "so', encoding="utf-8")
    with pytest.raises(ReportInputError):
        load_cache_coils(tmp_path, VERSION)


# --- CLI --------------------------------------------------------------------------------------

def _write(path, doc):
    path.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    return path


def test_cli_writes_the_report_outside_the_repo(tmp_path, capsys):
    crosscheck = _write(tmp_path / "crosscheck.json", _doc(_heating()))
    out_dir = tmp_path / "out"
    assert script.main(["--crosscheck", str(crosscheck), "--out-dir", str(out_dir)]) == 0
    assert json.loads((out_dir / "report.json").read_text(encoding="utf-8"))["heating"]["evaluable"] == 1
    assert (out_dir / "report.md").read_text(encoding="utf-8").startswith("# Performance self-consistency")
    assert "9001" not in capsys.readouterr().out  # the console line carries counts only


@pytest.mark.parametrize(
    "content",
    ['{"code_version": "v", "projects": [{"project": "1", "coi', {"code_version": "v", "summary": {}},
     {"code_version": "v", "projects": [{"project": "1", "coils": [{"tag": "A", "coil_type": "DX", "rows": [{"id": 1}]}]}]}],
)
def test_cli_refuses_truncated_or_drifted_input_and_writes_nothing(tmp_path, content):
    crosscheck = _write(tmp_path / "crosscheck.json", content)
    out_dir = tmp_path / "out"
    assert script.main(["--crosscheck", str(crosscheck), "--out-dir", str(out_dir)]) == 2
    assert not out_dir.exists()


def test_cli_refuses_a_relative_input(tmp_path):
    assert script.main(["--crosscheck", "crosscheck.json", "--out-dir", str(tmp_path / "out")]) == 2


def test_cli_refuses_an_output_directory_inside_a_repo(tmp_path, capsys):
    crosscheck = _write(tmp_path / "crosscheck.json", _doc(_heating()))
    inside = ROOT / "outputs" / "performance_consistency_should_not_exist"
    assert script.main(["--crosscheck", str(crosscheck), "--out-dir", str(inside)]) == 2
    assert not inside.exists()
    message = capsys.readouterr().err
    assert "--out-dir is inside a git working tree" in message and "capture DB" not in message
