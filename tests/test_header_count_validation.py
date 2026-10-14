"""Header-count double validation (John 2026-10-14, project 2950 RHHGRC-1).

2950's reheat coil printed ``Coil Style: Face Split`` (no count) and ``Qty Conn. /
Header 2``. Nothing read the count, the intake's default ``Header 1`` answered, and a
two-header coil drew -- and shipped -- on single-header artwork.

Layer 1 (`submittal.header_count`) judges every statement the submittal makes about the
header count. Layer 2 (`_gate_header_count`) withholds a DX/HGRH drawing whose artwork
does not carry the count the submittal establishes, or whose submittal establishes none.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from coilforge.submittal.extract import SanitizedSubmittalLine  # noqa: E402
from coilforge.submittal.header_count import (  # noqa: E402
    as_built_signal,
    read_header_count,
    signals_from_candidate,
)
from coilforge.submittal.pdf_intake import _candidate_from_cover_row, _CoverRow  # noqa: E402
from coilforge.workflows import submittal_to_drawing as std  # noqa: E402
from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    _gate_header_count,
    _run_candidate_to_drawing_payload,
    derive_coil_template_drawing,
)
from derive_roundtrip import spec_from_template_drawing  # noqa: E402


def _sig(name, value, page=8):
    return {"name": name, "value": value, "page": page, "raw": str(value)}


def _candidate(*lines, tag="RHHGRC-1", item="HGRC Reheat", model="V60_I_ERV_BP", hand="RH"):
    return _candidate_from_cover_row(
        _CoverRow(page_number=1, row_number=1, qty=1, tag=tag, item=item, model=model, handing=hand),
        source_id="TEST",
        index=1,
        detail_lines=tuple(
            SanitizedSubmittalLine(source_key=key, source_value=value, line_number=i, source_page=8)
            for i, (key, value) in enumerate(lines, start=1)
        ),
    )


def _analyze(candidate, **kwargs):
    std.clear_pdf_to_drawing_workflow_cache()
    return _run_candidate_to_drawing_payload(
        candidate, pdf_intake_summary=None, source_id="TEST",
        preview_defaults=None, title_block=None, **kwargs,
    )


# --- Layer 1 ------------------------------------------------------------------
def test_circuit_signals_that_agree_with_the_qty_are_agreed():
    reading = read_header_count(
        [_sig("coil_style", 3), _sig("qty_conn_per_header", 3)], coil_category="DX"
    )
    assert (reading["value"], reading["status"]) == (3, "agreed")


def test_qty_alone_is_a_single_source_answer():
    """John Q1 = A: with no circuit count anywhere, the stated qty is the header count."""
    reading = read_header_count([_sig("qty_conn_per_header", 2)], coil_category="HGRH")
    assert (reading["value"], reading["status"]) == (2, "single_source")


def test_two_circuit_signals_that_differ_are_a_conflict_with_no_value():
    reading = read_header_count(
        [_sig("coil_style", 3), _sig("circuits_cell", 2)], coil_category="DX"
    )
    assert (reading["value"], reading["status"]) == (None, "conflict")


def test_nothing_stated_is_absent():
    assert read_header_count([], coil_category="DX")["status"] == "absent"


def test_qty_never_contradicts_a_circuit_count_it_only_warns_one_way():
    """Terra V HGRH draws four circuits on two connections per header -- ordinary
    geometry, not a contradiction. Only a qty ABOVE the circuits (the 3095 shape) warns."""
    more_circuits = read_header_count(
        [_sig("circuits_cell", 4), _sig("qty_conn_per_header", 2)], coil_category="HGRH"
    )
    assert (more_circuits["value"], more_circuits["status"]) == (4, "single_source")
    assert more_circuits["qty_disagrees"] is False
    more_qty = read_header_count(
        [_sig("circuits_cell", 1), _sig("qty_conn_per_header", 2)], coil_category="HGRH"
    )
    assert more_qty["value"] == 1 and more_qty["qty_disagrees"] is True


def test_water_coils_are_not_applicable():
    for category in ("CWC", "HWC"):
        reading = read_header_count([_sig("qty_conn_per_header", 2)], coil_category=category)
        assert (reading["value"], reading["status"]) == (None, "not_applicable")


def test_the_as_built_drawing_only_keeps_a_coil_from_reading_absent():
    """John 2026-10-14 held back any change on the scanned track: the as-built count
    never sets the value and never conflicts with a stated one."""
    built = as_built_signal(2)
    assert built is not None
    alone = read_header_count([built], coil_category="DX")
    assert (alone["value"], alone["status"]) == (None, "as_built_only")
    beside = read_header_count([built, _sig("coil_style", 3)], coil_category="DX")
    assert (beside["value"], beside["status"]) == (3, "single_source")


def test_the_intake_default_header_type_is_not_a_signal_and_standard_is_not_either():
    candidate = _candidate(("COIL_STYLE", "Standard"))
    names = [s["name"] for s in signals_from_candidate(candidate.model_dump())]
    assert names == []  # the default "Header 1" line and "Standard" both say nothing


def test_a_style_derived_count_is_not_counted_twice():
    """Intake copies the Coil Style count into geometry.circuits (CIRCUITS_FROM_STYLE);
    reading both would make one statement look like two agreeing ones."""
    candidate = _candidate(("COIL_STYLE", "Interlaced 2 Circuits"))
    assert [s["name"] for s in signals_from_candidate(candidate.model_dump())] == ["coil_style"]


def test_a_circuits_cell_and_the_style_are_two_signals():
    candidate = _candidate(("CIRCUITS", "2"), ("COIL_STYLE", "Interlaced 2 Circuits"))
    names = sorted(s["name"] for s in signals_from_candidate(candidate.model_dump()))
    assert names == ["circuits_cell", "coil_style"]


# --- the 2950 incident, end to end --------------------------------------------
def test_2950_face_split_with_two_connections_draws_two_headers():
    payload = _analyze(_candidate(
        ("COIL_STYLE", "Face Split"), ("QUANTITY_CONNECTIONS_PER_HEADER", "2"),
    ))
    td = payload["template_drawing"]
    assert td["template_id"] == "coilmaster_vplus_hgrh_rh_header2"
    verification = td["header_count_verification"]
    assert verification["status"] == "verified"
    assert verification["reading_status"] == "single_source"
    assert (verification["submittal"], verification["drawn"]) == (2, 2)
    assert not td.get("header_count_blocked")


def test_the_paste_fields_carry_the_second_header_too():
    """The Direct Coil paste surface took the header count from the intake's default
    "Header 1" and marked I2/S2/O2/R2/HD2/ZD2 not applicable while the drawing had two
    headers -- the same incident on another surface."""
    payload = _analyze(_candidate(
        ("COIL_STYLE", "Face Split"), ("QUANTITY_CONNECTIONS_PER_HEADER", "2"),
    ))
    draft_header = payload["direct_coil_input_draft"]["fields"]["header_type"]["value"]
    assert draft_header == "Header 2"


# --- Layer 2: withheld, and the lever that answers it --------------------------
def test_no_stated_header_count_withholds_the_drawing_and_offers_circuits():
    payload = _analyze(_candidate(("ROWS", "2")))
    td = payload["template_drawing"]
    assert td["header_count_blocked"] is True
    assert td["svg"] == "" and td["template_id"] is None
    assert "states no header count" in td["not_registered_reason"]
    assert td["input_baseline"]["circuits"] == {"value": None, "stated": False}
    plan = td["manual_fill_plan"]
    assert "circuits" in plan["critical_missing"]
    item = next(i for i in plan["items"] if i["key"] == "circuits")
    assert item["critical"] and item["unresolved"]


def test_typing_circuits_draws_it_and_clearing_it_withholds_again():
    """The round trip the browser makes: the plain `circuits` key is the previous
    response's echo (the frozen path's default 1), so only a TYPED value may release a
    withheld coil -- and clearing it must withhold the coil again."""
    analyzed = _analyze(_candidate(("ROWS", "2")))["template_drawing"]
    still = derive_coil_template_drawing(spec_from_template_drawing(analyzed))
    assert still["header_count_blocked"] is True, "an unrelated derive must not release it"

    typed = derive_coil_template_drawing(spec_from_template_drawing(analyzed, {"circuits": 1}))
    assert not typed.get("header_count_blocked")
    assert typed["template_id"] == "coilmaster_vplus_hgrh_rh_header1"
    assert typed["header_count_verification"]["status"] == "overridden"
    assert typed["header_count_verification"]["typed"] == 1
    # Recorded against what the submittal said (nothing), not dropped as 1 -> 1.
    row = next(r for r in typed["spec_overrides"] if r["field_key"] == "circuits")
    assert (row["previous_value"], row["new_value"]) == (None, 1)

    cleared = derive_coil_template_drawing(spec_from_template_drawing(typed))
    assert cleared["header_count_blocked"] is True


def test_typing_a_count_the_submittal_contradicts_is_drawn_and_marked_overridden():
    analyzed = _analyze(_candidate(
        ("COIL_STYLE", "Face Split"), ("QUANTITY_CONNECTIONS_PER_HEADER", "2"),
    ))["template_drawing"]
    typed = derive_coil_template_drawing(spec_from_template_drawing(analyzed, {"circuits": 1}))
    verification = typed["header_count_verification"]
    assert typed["template_id"] == "coilmaster_vplus_hgrh_rh_header1"
    assert (verification["status"], verification["submittal"]) == ("overridden", 2)


def test_the_check_survives_repeated_derives():
    analyzed = _analyze(_candidate(
        ("COIL_STYLE", "Face Split"), ("QUANTITY_CONNECTIONS_PER_HEADER", "2"),
    ))["template_drawing"]
    once = derive_coil_template_drawing(spec_from_template_drawing(analyzed))
    twice = derive_coil_template_drawing(spec_from_template_drawing(once))
    for result in (once, twice):
        assert result["template_id"] == "coilmaster_vplus_hgrh_rh_header2"
        assert result["header_count_verification"]["status"] == "verified"


def test_a_derive_without_the_reading_keeps_todays_drawing_and_says_unverified():
    analyzed = _analyze(_candidate(
        ("COIL_STYLE", "Interlaced 2 Circuits"), ("QUANTITY_CONNECTIONS_PER_HEADER", "2"),
    ), )["template_drawing"]
    spec = spec_from_template_drawing(analyzed)
    spec.pop("header_count_reading")
    result = derive_coil_template_drawing(spec)
    assert result["svg"] and not result.get("header_count_blocked")
    assert result["header_count_verification"]["status"] == "unverified"


def _drawn(template_id, header, **extra):
    result = {
        "svg": "<svg/>", "template_id": template_id, "template_found": True,
        "extracted": {"coil_category": "HGRH", "circuits": header, "tag": "RHHGRC-1"},
    }
    result.update(extra)
    return result


def test_artwork_with_the_wrong_header_count_is_withheld_with_both_numbers():
    reading = read_header_count([_sig("qty_conn_per_header", 2)], coil_category="HGRH")
    result = _gate_header_count(_drawn("coilmaster_hgrh_rh_header1", 1), reading)
    assert result["header_count_blocked"] is True
    reason = result["not_registered_reason"]
    assert "states 2 header(s)" in reason and "Header 1" in reason and "p8" in reason
    assert result["header_count_verification"]["status"] == "mismatch"


def test_conflicting_circuit_statements_are_withheld():
    reading = read_header_count([_sig("coil_style", 3), _sig("circuits_cell", 2)], coil_category="DX")
    result = _gate_header_count(_drawn("coilmaster_dx_rh_header3", 3), reading)
    assert result["header_count_blocked"] is True
    assert "conflicting" in result["not_registered_reason"]


def test_an_earlier_withhold_reason_is_never_overwritten():
    earlier = _drawn(None, 1, svg="", not_registered_reason="Ventum+ DX drawing template not registered")
    result = _gate_header_count(earlier, read_header_count([], coil_category="HGRH"))
    assert result["not_registered_reason"] == "Ventum+ DX drawing template not registered"
    assert not result.get("header_count_blocked")
    assert result["header_count_verification"]["checked"] is False


def test_hgbp_and_water_coils_are_never_withheld():
    hgbp = _drawn("coilmaster_dx_rh_hgbp", 1)
    hgbp["extracted"].update(coil_category="DX", special_feature="HGBP")
    result = _gate_header_count(hgbp, read_header_count([], coil_category="DX"))
    assert result["svg"] and result["header_count_verification"]["checked"] is False
    water = _drawn("coilmaster_hwc_rh", 1)
    water["extracted"]["coil_category"] = "HWC"
    assert "header_count_verification" not in _gate_header_count(water, None)


def test_a_scanned_drawing_keeps_todays_art_and_warns_when_its_circuits_differ():
    """DX2_TEXT prints C1:/C2: but has always drawn Header 1; John 2026-10-14 held that
    change back, so it is not withheld -- it is flagged."""
    from test_pdf_to_template_drawing import DX1_TEXT, DX2_TEXT, _make_text_pdf

    for text, warns in ((DX1_TEXT, False), (DX2_TEXT, True)):
        std.clear_pdf_to_drawing_workflow_cache()
        td = std.run_pdf_to_drawing_workflow(_make_text_pdf(text.splitlines()))["template_drawing"]
        assert td["svg"] and not td.get("header_count_blocked")
        verification = td["header_count_verification"]
        assert verification["status"] == "as_built_only"
        assert bool(verification.get("as_built_disagrees")) is warns


# --- the other surfaces read the same count ------------------------------------
def test_the_checklist_reads_the_same_header_count_for_dx_and_hgrh_only():
    from coilforge.checklist.from_workflow import coil_inputs_from_candidates

    hgrh = _candidate(("COIL_STYLE", "Face Split"), ("QUANTITY_CONNECTIONS_PER_HEADER", "2"))
    water = _candidate(("CIRCUITS", "4"), tag="HHWC-1", item="Hot Water Coil")
    coils, _ = coil_inputs_from_candidates([hgrh.model_dump(), water.model_dump()])
    by_tag = {c["tag"]: c for c in coils}
    assert by_tag["RHHGRC-1"]["circuits"] == 2
    assert by_tag["HHWC-1"]["circuits"] == 4  # water keeps its raw circuiting


def test_the_project_gate_names_the_header_count_not_a_missing_template():
    from coilforge.review.project_gate import _drawing_status

    reason = "Header count withheld: the submittal states no header count"
    workflow = {"template_drawing": {
        "svg": "", "template_found": False, "header_count_blocked": True,
        "not_registered_reason": reason,
    }}
    assert _drawing_status(workflow) == reason


def test_the_api_accepts_a_typed_circuits_and_bounds_it():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from coilforge.web_app import app

    analyzed = _analyze(_candidate(("ROWS", "2")))["template_drawing"]
    client = TestClient(app)
    ok = client.post(
        "/api/coil-drawing/derive",
        json=spec_from_template_drawing(analyzed, {"circuits": 1}, override_reason="test"),
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    drawing = body.get("template_drawing", body)
    assert not drawing.get("header_count_blocked")
    assert drawing["header_count_verification"]["status"] == "overridden"
    for bad in (0, 5, 1.5):
        rejected = client.post(
            "/api/coil-drawing/derive",
            json=spec_from_template_drawing(analyzed, {"circuits": bad}, override_reason="test"),
        )
        payload = rejected.json()
        errors = " ".join(payload.get("manual_fill_errors") or payload.get("errors") or [])
        assert "circuits" in errors, (bad, payload.keys())
