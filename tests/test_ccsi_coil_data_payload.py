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
    end = _USERSCRIPT.index("function watchDimensionGrid")
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
