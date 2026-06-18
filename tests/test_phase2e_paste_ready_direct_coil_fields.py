from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from coilforge.direct_coil import map_canonical_to_direct_coil_draft
from coilforge.direct_coil.paste_ready_fields import build_direct_coil_paste_ready_surface
from coilforge.submittal import load_submittal_candidate_fixture
from coilforge.submittal.to_canonical import map_submittal_candidate_to_canonical
from coilforge.web_app import app


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPO_ROOT / "examples" / "sanitized" / "submittal_candidate_dx_header1_default.json"
)

client = TestClient(app)


EXPECTED_LABELS = [
    "Tag",
    "Coil Quantity",
    "Tube Diameter (standard at top)",
    "Tubes High",
    "Finned Height(In)",
    "Finned Length(In)",
    "Rows Deep",
    "Fins Per Inch",
    "Number Of Feeds(Total)",
    "Tube Material",
    "Fin Material",
    "Fin Surface",
    "Header Material",
    "Header Wall Schedule",
    "Connection Material",
    "Connection Type",
    "Return Connection Size",
    "Casing Style",
    "Casing Material",
    "Connection Ends",
    "Coil Coating",
    "Coil Hand",
    "System Type",
    "Drain Pan Type",
    "Drain Pan Material",
    "Drawing Notes",
    "Total Air Flow(CFM)",
    "Air Flow Per Coil(CFM)",
    "Face Velocity(FPM)",
    "Altitude(FT)",
    "Entering Dry Bulb(\N{DEGREE SIGN}F)",
    "Entering Wet Bulb(\N{DEGREE SIGN}F)",
    "Entering Relative Humidity(%)",
    "Leaving Dry Bulb(\N{DEGREE SIGN}F)",
    "Total Capacity(MBH)(Per Coil)",
    "Refrigerant",
    "Evaporating Temperature(\N{DEGREE SIGN}F)",
    "Liquid Temperature(\N{DEGREE SIGN}F)",
    "Superheat(\N{DEGREE SIGN}F)",
    "DXDistCapillarySize",
    "Refrigerant Velocity (connection)",
    "Refrigerant Pressure Drop",
    "Refrigerant Mass Flow",
    "Air Side Fouling Factor(ft\N{SUPERSCRIPT TWO} \N{DEGREE SIGN}F h/Btu)",
    "CD",
    "BF",
    "TF",
    "RF",
    "HF",
    "CH",
    "SL",
    "Connections",
    "Mounting Holes",
    "I",
    "S",
    "O",
    "R",
    "HD",
    "ZD",
    "I2",
    "S2",
    "O2",
    "R2",
    "HD2",
    "ZD2",
    "Distributor Lead Area Max X",
    "Distributor Lead Area Max Y",
    "Cycle Valve Lead Length",
    "Apply Venting and Draining I/O Constraints",
    "Limit S/R to Standard Positions (for ease of manufacture)",
]


def test_paste_ready_formatter_returns_exact_required_field_order_and_labels() -> None:
    surface = build_direct_coil_paste_ready_surface(_build_draft_from_sanitized_candidate())

    assert surface.total_fields == 70
    assert [field.order for field in surface.fields] == list(range(1, 71))
    assert [field.direct_coil_label for field in surface.fields] == EXPECTED_LABELS


def test_required_minimum_labels_appear_in_order() -> None:
    surface = build_direct_coil_paste_ready_surface(_build_draft_from_sanitized_candidate())
    labels = [field.direct_coil_label for field in surface.fields]
    required_labels = [
        "Tag",
        "Coil Quantity",
        "Tube Diameter (standard at top)",
        "Tubes High",
        "Finned Height(In)",
        "Finned Length(In)",
        "Rows Deep",
        "Fins Per Inch",
        "Number Of Feeds(Total)",
        "Tube Material",
        "Fin Material",
        "Casing Material",
        "Total Air Flow(CFM)",
        "Entering Dry Bulb(\N{DEGREE SIGN}F)",
        "Refrigerant",
        "Evaporating Temperature(\N{DEGREE SIGN}F)",
        "DXDistCapillarySize",
        "Air Side Fouling Factor(ft\N{SUPERSCRIPT TWO} \N{DEGREE SIGN}F h/Btu)",
        "CD",
        "BF",
        "TF",
        "CH",
        "I",
        "S",
        "I2",
        "S2",
        "Distributor Lead Area Max X",
        "Distributor Lead Area Max Y",
        "Apply Venting and Draining I/O Constraints",
        "Limit S/R to Standard Positions (for ease of manufacture)",
    ]

    assert [labels.index(label) for label in required_labels] == sorted(
        labels.index(label) for label in required_labels
    )


def test_ready_fields_copy_only_exact_values() -> None:
    draft = _build_draft_from_sanitized_candidate()
    fields = dict(draft.fields)
    fields["finned_height"] = fields["finned_height"].model_copy(
        update={"status": "ready", "review_required": False}
    )
    draft = draft.model_copy(update={"fields": fields})

    surface = build_direct_coil_paste_ready_surface(draft)
    row = _field_by_label(surface, "Finned Height(In)")

    assert row.status == "ready"
    assert row.copy_enabled is True
    assert row.value == 12.0
    assert row.display_value == "12.0"


def test_blocked_unmapped_and_calculated_fields_remain_visible_with_safe_copy_state() -> None:
    surface = build_direct_coil_paste_ready_surface(_build_draft_from_sanitized_candidate())

    cd = _field_by_label(surface, "CD")
    tag = _field_by_label(surface, "Tag")
    capacity = _field_by_label(surface, "Total Capacity(MBH)(Per Coil)")
    pressure_drop = _field_by_label(surface, "Refrigerant Pressure Drop")

    assert cd.status == "blocked"
    assert cd.copy_enabled is False
    assert "DO NOT PASTE" in cd.display_value
    assert tag.status == "unmapped"
    assert tag.copy_enabled is False
    assert "UNMAPPED" in tag.display_value
    assert capacity.status == "calculated_read_only"
    assert capacity.copy_enabled is False
    assert pressure_drop.status == "calculated_read_only"
    assert pressure_drop.copy_enabled is False


def test_paste_ready_api_response_includes_surface_and_preserves_safety_flags() -> None:
    response = client.get("/api/direct-coil/paste-ready-fields")

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_packet_status"] == "quote_prep_review_only"
    assert payload["total_fields"] == 70
    assert payload["fields"][0]["direct_coil_label"] == "Tag"
    assert payload["fields"][-1]["direct_coil_label"] == (
        "Limit S/R to Standard Positions (for ease of manufacture)"
    )
    assert payload["raw_private_data_returned"] is False
    assert payload["final_export_enabled"] is False
    assert payload["pdf_export_enabled"] is False
    assert payload["production_drawing_approval_claimed"] is False


def test_workflow_and_ui_payloads_include_paste_ready_fields_without_enabling_export() -> None:
    workflow = client.post(
        "/api/workflow/submittal-to-drawing",
        json=client.get("/api/workflow/default-demo").json()["input"],
    ).json()
    ui_state = client.get("/api/ui/default").json()

    assert workflow["direct_coil_paste_ready"]["total_fields"] == 70
    assert ui_state["direct_coil_paste_ready"]["total_fields"] == 70
    assert workflow["validation"]["export_status"] == "not_implemented"
    assert workflow["validation"]["export_allowed"] is False
    assert ui_state["actions"]["export_pdf"]["enabled"] is False
    assert ui_state["drawing_preview"]["export_allowed"] is False


def _field_by_label(surface, label: str):
    return next(field for field in surface.fields if field.direct_coil_label == label)


def _build_draft_from_sanitized_candidate():
    candidate = load_submittal_candidate_fixture(FIXTURE_PATH)
    record = map_submittal_candidate_to_canonical(candidate)
    return map_canonical_to_direct_coil_draft(record)
