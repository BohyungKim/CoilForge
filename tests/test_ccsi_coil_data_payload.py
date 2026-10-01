"""CCSI coil-data push payload (Step E stage 1): candidate + Direct Coil draft -> coil_data."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from coilforge.ccsi.coil_data_map import build_coil_data_payload, coil_type_for_tag  # noqa: E402
from coilforge.direct_coil import map_canonical_to_direct_coil_draft  # noqa: E402
from coilforge.submittal.candidate import SubmittalCoilCandidate  # noqa: E402
from coilforge.submittal.to_canonical import map_submittal_candidate_to_canonical_result  # noqa: E402
from coilforge.web_app import app  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
_FIXTURE = json.loads((ROOT / "examples/sanitized/submittal_candidate_dx_header1_default.json").read_text(encoding="utf-8"))
# the sanitized tag (COIL-TAG-001) names no coil category; give the copy a real DX tag
CANDIDATE = {**_FIXTURE, "tag": {**_FIXTURE["tag"], "value": "CDXC-1"}}


def _draft() -> dict:
    record = map_submittal_candidate_to_canonical_result(SubmittalCoilCandidate.model_validate(CANDIDATE)).record
    return map_canonical_to_direct_coil_draft(record).model_dump()


@pytest.mark.parametrize(("tag", "coil_type"), [
    ("CDXC-1", "DX"), ("RHHGRC-1", "HGRH"), ("RHHGRH-2", "HGRH"), ("CCWC-1", "CWC"),
    ("HHWC-1", "HWC"), ("PHWC-2", "HWC"), ("ERV-1", None),
])
def test_tag_selects_the_coil_data_map(tag, coil_type) -> None:
    assert coil_type_for_tag(tag) == coil_type


def test_payload_from_the_real_workflow_objects() -> None:
    payload = build_coil_data_payload(candidate=CANDIDATE, draft=_draft())
    assert payload["coil_type"] == "DX" and payload["export_allowed"] is False
    by = {e["ccsi_id"]: e for e in payload["entries"]}
    assert by["TubeDiameter"]["selector"] == "#TubeDiameter"
    # the default profile fills what the submittal never states, and it is pushable
    assert by["CasingMaterial"]["reason_code"] == "CCSI_DEFAULT_PROFILE" and by["CasingMaterial"]["pushable"]
    # only validated entries are pushable; computed ones never are
    for entry in payload["entries"]:
        if entry["role"] != "input":
            assert not entry["pushable"], entry["ccsi_id"]
    assert payload["summary"]["pushable"] == sum(e["pushable"] for e in payload["entries"])


def test_unknown_tag_returns_an_explicit_error_not_a_guess() -> None:
    payload = build_coil_data_payload(candidate=_FIXTURE, draft={"fields": {}})
    assert payload["entries"] == [] and "no coil-data map" in payload["error"]


def test_route_returns_the_same_payload() -> None:
    client = TestClient(app)
    body = {"candidate": CANDIDATE, "direct_coil_input_draft": _draft()}
    res = client.post("/api/ccsi/coil-data-payload", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["coil_type"] == "DX" and data["review_aid_only"] is True
    assert data == build_coil_data_payload(candidate=CANDIDATE, draft=_draft())


# --- userscript v3 stage 1: static guarantees ---------------------------------------

_USERSCRIPT = (ROOT / "web/ccsi/ccsi_autofill.user.js").read_text(encoding="utf-8")
_APP_JS = (ROOT / "web/app.js").read_text(encoding="utf-8")


def _stage1_source() -> str:
    start = _USERSCRIPT.index("// ===================== Stage 1: coil data")
    # stage 1 ends where the v3.1 one-button block begins (that block DOES press Calculate)
    end = _USERSCRIPT.index("// ===================== One button (v3.1)")
    # code only: the explanatory comments name the CCSI endpoints the stage deliberately avoids
    code = [line for line in _USERSCRIPT[start:end].splitlines() if not line.strip().startswith("//")]
    return "\n".join(code)


def test_stage1_never_presses_calculate_or_submits() -> None:
    src = _stage1_source()
    for forbidden in ("calculateCoilData", "calcBtn", ".submit(", "fetch(", "XMLHttpRequest", "Coils/"):
        assert forbidden not in src, forbidden


def test_stage1_fills_one_field_at_a_time_and_reverifies() -> None:
    src = _stage1_source()
    assert "await ajaxIdle()" in src  # waits for CCSI's getDependencyOptions refresh
    assert "reset_or_mismatch" in src  # a later dependency refresh that reset a select is reported
    assert "e.pushable" in src  # only validated / default-profile entries are written
    assert "target.readOnly || target.disabled" in src  # CCSI's own locks are skipped, never forced


def test_coil_data_rides_its_own_top_level_key() -> None:
    assert "coil_data: readCoilData()," in _USERSCRIPT
    assert "coil_data: readStampedCcsiCoilData()," in _APP_JS
    assert '"/api/ccsi/coil-data-payload"' in _APP_JS


def test_stage1_option_match_survives_ccsi_rerendering_the_select() -> None:
    # live 2026-09-30: after Tube Diameter changed, Tube Material's option text became
    # "Copper - 0.016 Plain" (= its value); the map's "Copper 0.016 Plain" must still land.
    src = _stage1_source()
    assert "optionForCoilData(target, entry.value)" in src
    assert "coilOptionKey(o.textContent) === want || coilOptionKey(o.value) === want" in src
    assert 'replace(/\\s+-\\s+/g, " ")' in src


# --- userscript v3.1 one button: static guarantees ----------------------------------

def _run_all_source() -> str:
    start = _USERSCRIPT.index("// ===================== One button (v3.1)")
    end = _USERSCRIPT.index("// Stage 2 (drawing parameters) needs CCSI's dimension grid")
    code = [line for line in _USERSCRIPT[start:end].splitlines() if not line.strip().startswith("//")]
    return "\n".join(code)


def test_run_all_presses_exactly_calculate_and_custom_dimensions() -> None:
    import re

    src = _run_all_source()
    assert src.count(".click()") == 2
    assert "calcButton.click()" in src and "cdButton.click()" in src
    assert 'document.getElementById("calcBtn")' in src
    assert 'document.getElementById("customDimensionsButton")' in src
    ids = set(re.findall(r'getElementById\("([^"]+)"\)', src))
    assert ids <= {"calcBtn", "customDimensionsButton", "mainResult", "cdFormId", "cf-calc-marker", "cf-grid-marker"}, ids


def test_run_all_never_saves_or_leaves_the_page() -> None:
    src = _run_all_source()
    for forbidden in ("saveToProject", "saveAndContinueToProject", "submitCoilData", "navigateTo",
                      "customDimensionsApply", ".submit(", "fetch(", "XMLHttpRequest", "location."):
        assert forbidden not in src, forbidden


def test_run_all_stops_early_and_bounds_every_wait() -> None:
    src = _run_all_source()
    # a coil-data failure other than a CCSI-locked field stops before anything is calculated
    assert 'r.status !== "ok" && r.status !== "locked"' in src
    assert src.index("return;") < src.index("calcButton.click()")
    # every wait is bounded, and arrival is detected by the marker CCSI's re-render removes
    assert src.count("60000") == 2 and "cf-calc-marker" in src and "cf-grid-marker" in src
    assert "Nothing was saved" in src


def test_userscript_is_v3_1() -> None:
    import re

    header = re.search(r"// @version\s+(\S+)", _USERSCRIPT).group(1)
    runtime = re.search(r'const SCRIPT_VERSION = "([^"]+)";', _USERSCRIPT).group(1)
    # 3.1.1 = + live-captured #DrainAndVentLocation; 3.1.2 = water ZD withheld (2026-10-01);
    # 3.1.3 = performance self-consistency warnings in the stage-1 panel (warning only);
    # 3.1.4 = the Send to CCSI path carries the Drawing Notes
    assert header == runtime == "3.1.4"
    assert "runAllSection(payload, gateCheck)," in _USERSCRIPT


def test_run_all_does_not_require_the_hidden_result_block_to_be_visible() -> None:
    # live 2026-09-30: with the dimension grid open CCSI renders #mainResult display:none, so a
    # visibility test on it never passes and Run all timed out after a successful Calculate.
    src = _run_all_source()
    assert 'visible(document.getElementById("mainResult"))' not in src
    assert 'visible(document.getElementById("customDimensionsButton"))' in src


def test_run_all_refuses_a_payload_without_coil_data() -> None:
    # without stage 1, Calculate would rate whatever the CCSI form already holds
    src = _run_all_source()
    guard = src.index("coilDataTargets(payload.coil_data).length")
    assert guard < src.index("calcButton.click()")
    assert "nothing was calculated" in src


def test_copy_status_says_whether_coil_data_is_included() -> None:
    assert "coil-data fields (Run all ready)" in _APP_JS
    assert "coil data not ready yet" in _APP_JS


# --- performance self-consistency: carried in the payload, shown as a warning only ----


def test_payload_carries_the_performance_consistency_report() -> None:
    payload = build_coil_data_payload(candidate=CANDIDATE, draft=_draft())
    report = payload["performance_consistency"]
    assert report["coil_type"] == "DX"
    assert len(report["findings"]) == 7 and sum(report["counts"].values()) == 7
    assert report["review_aid_only"] is True and report["export_allowed"] is False
    assert {f["verdict"] for f in report["findings"]} <= {"consistent", "inconsistent", "cannot_evaluate"}


_PUSHED = ("entries", "summary", "geometry_reselect_reason", "coil_type", "tag")


def _inconsistent_draft() -> dict:
    """The fixture draft with two values that contradict it: a DX coil that warms the air, and
    a face velocity that 1200 CFM over a 12 x 15 face (960 fpm) cannot give."""
    draft = _draft()
    for key, value in (("leaving_dry_bulb_f", 85.0), ("face_velocity_fpm", 450.0)):
        draft["fields"][key] = {**draft["fields"][key], "value": value, "status": "review_required"}
    return draft


def test_performance_consistency_never_changes_what_is_pushed(monkeypatch) -> None:
    from coilforge.coil_utilities import performance_consistency as pc

    with_check = build_coil_data_payload(candidate=CANDIDATE, draft=_inconsistent_draft())
    flagged = {f["check"] for f in with_check["performance_consistency"]["findings"] if f["verdict"] == "inconsistent"}
    assert flagged == {"air_temp_direction", "face_velocity"}  # the check really fired

    # The same coil with the check replaced by one that finds nothing: what is pushed is identical.
    silent = pc.PerformanceConsistencyReport(coil_type="DX", findings=[], counts={})
    monkeypatch.setattr(pc, "check_performance_consistency", lambda sources, coil_type: silent)
    without = build_coil_data_payload(candidate=CANDIDATE, draft=_inconsistent_draft())
    assert without["performance_consistency"]["findings"] == []
    for key in _PUSHED:
        assert with_check[key] == without[key], key


def test_a_failing_check_is_reported_and_never_breaks_the_payload(monkeypatch) -> None:
    from coilforge.coil_utilities import performance_consistency as pc

    expected = build_coil_data_payload(candidate=CANDIDATE, draft=_draft())

    def boom(sources, coil_type):
        raise OverflowError("simulated")

    monkeypatch.setattr(pc, "check_performance_consistency", boom)
    payload = build_coil_data_payload(candidate=CANDIDATE, draft=_draft())
    report = payload["performance_consistency"]
    assert report["findings"] == [] and report["error"] == "OverflowError: simulated"
    assert report["review_aid_only"] is True and report["export_allowed"] is False
    for key in _PUSHED:
        assert payload[key] == expected[key], key
    res = TestClient(app).post("/api/ccsi/coil-data-payload",
                               json={"candidate": CANDIDATE, "direct_coil_input_draft": _draft()})
    assert res.status_code == 200 and res.json()["entries"] == expected["entries"]


def test_an_absurd_value_does_not_break_the_route() -> None:
    # A 400-digit "number" used to parse to inf and make the JSON response fail (HTTP 500).
    draft = _draft()
    draft["fields"]["face_velocity_fpm"] = {**draft["fields"]["face_velocity_fpm"], "value": "9" * 400,
                                            "status": "review_required"}
    res = TestClient(app).post("/api/ccsi/coil-data-payload", json={"candidate": CANDIDATE, "direct_coil_input_draft": draft})
    assert res.status_code == 200
    face = next(f for f in res.json()["performance_consistency"]["findings"] if f["check"] == "face_velocity")
    assert (face["verdict"], face["reason_code"]) == ("cannot_evaluate", "PERF_VALUE_UNPARSEABLE")


def test_unknown_tag_carries_no_performance_report() -> None:
    payload = build_coil_data_payload(candidate=_FIXTURE, draft={"fields": {}})
    assert "performance_consistency" not in payload


def _performance_warning_source() -> str:
    start = _USERSCRIPT.index("const PERFORMANCE_CHECK_LABELS")
    return _USERSCRIPT[start:_USERSCRIPT.index("function coilDataSection(payload, gateCheck)")]


def test_userscript_shows_only_inconsistent_findings_as_warnings() -> None:
    src = _performance_warning_source()
    assert 'f.verdict === "inconsistent"' in src
    assert "warning only" in src and "nothing is held" in src
    # `consistent` earns no mark: it means "not contradicted", not "correct"
    assert '"consistent"' not in src and "#1a7f37" not in src
    assert "performanceWarnings(block).forEach((text) => wrap.append(note(text)));" in _USERSCRIPT


def test_performance_warnings_never_gate_a_button_or_the_one_button_flow() -> None:
    # John 2026-10-01: warn only. The findings must not reach any disable / stop / throw.
    assert "performance_consistency" not in _run_all_source()
    code = "\n".join(line for line in _USERSCRIPT.splitlines() if not line.strip().startswith("//"))
    assert code.count("performance_consistency") == 1  # read once, inside performanceWarnings()
    assert code.count("performanceWarnings(") == 2      # its definition + the one render call
    src = _performance_warning_source()
    for forbidden in ("disabled", ".click(", "throw ", "return false"):
        assert forbidden not in src, forbidden


def test_performance_warning_text_from_a_real_finding() -> None:
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    from coilforge.coil_utilities.performance_consistency import check_performance_consistency

    # 2755 RHHGRC-2: 1030 CFM, 54 -> 76.76 degF, 27.64 MBH, 43 ft fits neither air basis.
    report = check_performance_consistency(
        {"total_air_flow_cfm": 1030, "entering_dry_bulb_f": 54, "leaving_dry_bulb_f": 76.76,
         "total_capacity_mbh": 27.64, "altitude_ft": 43}, coil_type="HGRH").model_dump()
    script = (_performance_warning_source()
              + "\nconst out = performanceWarnings(JSON.parse(process.argv[1]));"
              + "\nconsole.log(JSON.stringify(out));")
    block = json.dumps({"performance_consistency": report})
    done = subprocess.run([node, "-e", script, block], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stderr
    warnings = json.loads(done.stdout)
    assert len(warnings) == 1
    assert "capacity vs airflow" in warnings[0] and "observed 1.179" in warnings[0]
    assert "standard 1.085" in warnings[0] and "actual 1.117" in warnings[0]
    # a payload from an older server has no report: nothing is shown, nothing breaks
    old = subprocess.run([node, "-e", script, "{}"], capture_output=True, text=True, encoding="utf-8")
    assert old.returncode == 0 and json.loads(old.stdout) == []
    # a malformed report never throws while the panel is being built; a failed check says so
    for block, shown in (
        ({"performance_consistency": {"findings": "oops"}}, []),
        ({"performance_consistency": {"findings": [None, {"verdict": "inconsistent", "check": "constructor"}]}}, None),
        ({"performance_consistency": {"findings": [], "error": "OverflowError: simulated"}},
         ["Submittal self-check did not run (OverflowError: simulated) — nothing is held."]),
    ):
        run = subprocess.run([node, "-e", script, json.dumps(block)], capture_output=True, text=True, encoding="utf-8")
        assert run.returncode == 0, run.stderr
        lines = json.loads(run.stdout)
        if shown is None:
            assert len(lines) == 1 and "— constructor:" in lines[0]  # the check id, not an inherited function
        else:
            assert lines == shown


def test_a_substituted_value_is_named_in_the_panel() -> None:
    """The fin CCSI cannot build goes out as its approved substitute — and the panel says so."""
    import shutil
    import subprocess

    assert "substitutionNotes(block).forEach((text) => wrap.append(note(text)));" in _USERSCRIPT
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    from coilforge.ccsi.coil_data_map import resolve_coil_data

    sources = {"fin_material": {"value": 0.0075, "unit": "Aluminum", "status": "review_required"},
               "fin_surface": {"value": "Sine", "status": "review_required"},
               "finned_height": {"value": 30, "status": "review_required"}}
    block = {"entries": [e.model_dump() for e in resolve_coil_data(sources, coil_type="DX")]}
    targets = _USERSCRIPT[_USERSCRIPT.index("function coilDataTargets(block)"):_USERSCRIPT.index("// CCSI re-renders")]
    notes = _USERSCRIPT[_USERSCRIPT.index("function substitutionNotes(block)"):
                        _USERSCRIPT.index("// The submittal's own performance values")]
    script = "\n".join([targets, notes, "console.log(JSON.stringify(substitutionNotes(JSON.parse(process.argv[1]))));"])
    for payload, expected in (
        (block, ["↔ Fin Material: submittal says 0.0075, CCSI gets Aluminum 0.008 (substituted — review).",
                 "↔ Fin Surface: submittal says Sine, CCSI gets Corrugated (substituted — review)."]),
        ({}, []), ({"entries": "oops"}, []),  # an older or malformed payload shows nothing and never throws
    ):
        run = subprocess.run([node, "-e", script, json.dumps(payload)], capture_output=True, text=True, encoding="utf-8")
        assert run.returncode == 0, run.stderr
        assert sorted(json.loads(run.stdout)) == sorted(expected)
    for forbidden in ("disabled", ".click(", "throw "):  # a note, never a gate
        assert forbidden not in notes, forbidden


def test_send_to_ccsi_carries_the_drawing_notes() -> None:
    # John 2026-10-01: the notes reached CCSI from "Copy" but not from "Send to CCSI" — the DOM-scraped
    # payload had no `drawing_notes` key, because nothing stamped the notes for it to read.
    assert "elements.drawingParameters.dataset.ccsiDrawingNotes = JSON.stringify(ccsiDrawingNotes(uiState));" in _APP_JS
    start = _USERSCRIPT.index("async function buildPayloadFromDom()")
    bridge = _USERSCRIPT[start:_USERSCRIPT.index("function toast(", start)]
    assert "drawing_notes: readDrawingNotes()," in bridge
    assert "dataset.ccsiDrawingNotes" in bridge
    # the receiving side is unchanged: notes still enter the panel through entriesOf()
    assert "const notes = payload.drawing_notes;" in _USERSCRIPT


def test_the_stamped_notes_round_trip_through_the_bridge_reader() -> None:
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    start = _USERSCRIPT.index("function readDrawingNotes()")
    source = _USERSCRIPT[start:_USERSCRIPT.index("function toast(", start)]
    script = "\n".join([
        "const stamp = process.argv[1];",
        "const document = { querySelector: () => (stamp === 'ABSENT' ? null"
        " : { dataset: stamp === 'EMPTY' ? {} : { ccsiDrawingNotes: stamp } }) };",
        source,
        "console.log(JSON.stringify(readDrawingNotes()));",
    ])
    notes = {"ccsi_label": "Drawing Notes", "status": "review_required",
             "value": "\n".join(["AA COATING REQUIRED", 'Distributor 6" ext. — "quoted"'])}
    for stamp, expected in ((json.dumps(notes), notes), ("{not json", None), ("EMPTY", None), ("ABSENT", None)):
        run = subprocess.run([node, "-e", script, stamp], capture_output=True, text=True, encoding="utf-8")
        assert run.returncode == 0, run.stderr
        assert json.loads(run.stdout) == expected, stamp
