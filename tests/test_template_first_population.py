from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import jsonschema

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.template_population import (
    TEMPLATE_BUCKET_COUNT,
    TemplateSelectionRequest,
    load_drawing_template_catalog,
    populate_template_slots,
    select_drawing_template,
)


ROOT = Path(__file__).resolve().parents[1]


def test_template_catalog_contains_22_buckets_and_validates_schema() -> None:
    catalog = load_drawing_template_catalog()
    payload = {
        "catalog_id": catalog.catalog_id,
        "schema_version": catalog.schema_version,
        "supplier": catalog.supplier,
        "entries": [asdict(entry) for entry in catalog.entries],
    }
    schema = json.loads(
        (ROOT / "schemas" / "drawing_template_catalog.schema.json").read_text(
            encoding="utf-8"
        )
    )

    # 22 shared buckets + any dedicated per-family buckets (e.g. seeded Ventum+).
    assert len(catalog.entries) == TEMPLATE_BUCKET_COUNT >= 22
    jsonschema.validate(payload, schema)


def test_header4_buckets_now_seeded_active() -> None:
    # Header-4 (DX + HGRH) were placeholder_blocked while no reference drawing
    # existed. Real per-hand reference PDFs were provided (2026-06-21), so they are
    # now seeded active review aids and no bucket remains placeholder_blocked.
    catalog = load_drawing_template_catalog()
    by_id = catalog.by_template_id()

    for template_id in (
        "coilmaster_dx_lh_header4",
        "coilmaster_dx_rh_header4",
        "coilmaster_hgrh_lh_header4",
        "coilmaster_hgrh_rh_header4",
    ):
        entry = by_id[template_id]
        assert entry.status == "active_review_aid"
        assert entry.generation_allowed is True

    assert not [e for e in catalog.entries if e.status == "placeholder_blocked"]


def test_selector_chooses_dx_lh_header1_seed_template() -> None:
    result = select_drawing_template(
        TemplateSelectionRequest(
            supplier="coilmaster",
            coil_category="DX",
            coil_hand="LH",
            header_type="Header 1",
            source_case_id="EZC-0001",
        )
    )

    assert result.found is True
    assert result.template_id == "coilmaster_dx_lh_header1"
    assert result.template_status == "active_review_aid"
    assert result.generation_allowed is True


def test_selector_allows_seeded_dx_header4_and_hgrh_header4() -> None:
    dx = select_drawing_template(
        TemplateSelectionRequest(
            supplier="coilmaster",
            coil_category="DX",
            coil_hand="RH",
            header_type="Header 4",
        )
    )
    hgrh = select_drawing_template(
        TemplateSelectionRequest(
            supplier="coilmaster",
            coil_category="HGRH",
            coil_hand="LH",
            header_type="Header 4",
        )
    )

    assert dx.template_id == "coilmaster_dx_rh_header4"
    assert dx.template_status == "active_review_aid"
    assert dx.generation_allowed is True
    assert hgrh.template_id == "coilmaster_hgrh_lh_header4"
    assert hgrh.template_status == "active_review_aid"
    assert hgrh.generation_allowed is True


def test_selector_chooses_hgrh_header3_both_hands_seeded() -> None:
    # HGRH Header 3 RH is seeded from EZC-0016. Its LH partner was a disabled mirror
    # until a real LH reference PDF was provided (2026-06-21); both hands are now
    # seeded active review aids.
    rh = select_drawing_template(
        TemplateSelectionRequest(
            supplier="coilmaster",
            coil_category="HGRH",
            coil_hand="RH",
            header_type="Header 3",
            source_case_id="EZC-0016",
        )
    )
    lh = select_drawing_template(
        TemplateSelectionRequest(
            supplier="coilmaster",
            coil_category="HGRH",
            coil_hand="LH",
            header_type="Header 3",
        )
    )

    assert rh.template_id == "coilmaster_hgrh_rh_header3"
    assert rh.template_status == "active_review_aid"
    assert rh.generation_allowed is True
    assert lh.template_id == "coilmaster_hgrh_lh_header3"
    assert lh.template_status == "active_review_aid"
    assert lh.generation_allowed is True


def test_hgbp_selects_special_feature_template_not_normal_header1() -> None:
    result = select_drawing_template(
        TemplateSelectionRequest(
            supplier="coilmaster",
            coil_category="DX",
            coil_hand="LH",
            header_type="Header 1",
            special_feature="HGBP",
            source_case_id="EZC-0013",
        )
    )

    assert result.template_id == "coilmaster_dx_lh_hgbp"
    assert result.template_id != "coilmaster_dx_lh_header1"
    # HGBP is now seeded from EZC-0013 (real EZ drawing) and active as a review aid.
    assert result.generation_allowed is True
    assert result.template_status == "active_review_aid"


def test_slot_map_schema_validates_seed_template() -> None:
    slot_map_path = (
        ROOT
        / "templates"
        / "drawing"
        / "coilmaster"
        / "dx"
        / "coilmaster_dx_lh_header1"
        / "slot_map.json"
    )
    schema = json.loads(
        (ROOT / "schemas" / "drawing_template_slot_map.schema.json").read_text(
            encoding="utf-8"
        )
    )
    payload = json.loads(slot_map_path.read_text(encoding="utf-8"))

    jsonschema.validate(payload, schema)
    assert {slot["slot_id"] for slot in payload["slots"]} >= {
        "slot.FH",
        "slot.FL",
        "slot.CH",
        "slot.CL",
        "slot.CD",
        "slot.TF",
        "slot.BF",
        "slot.HF",
        "slot.RF",
        "slot.RB",
        "slot.HDx1",
        "slot.HD2",
        "slot.I1",
        "slot.S1",
        "slot.O2",
        "slot.R2",
        "slot.TAG",
        "slot.MODEL_NUMBER",
    }


def test_seed_evidence_validates_and_preserves_review_only_boundary() -> None:
    evidence_path = (
        ROOT
        / "templates"
        / "drawing"
        / "coilmaster"
        / "dx"
        / "coilmaster_dx_lh_header1"
        / "seed_evidence.json"
    )
    metadata_path = evidence_path.with_name("template_metadata.json")
    schema = json.loads(
        (ROOT / "schemas" / "drawing_template_seed_evidence.schema.json").read_text(
            encoding="utf-8"
        )
    )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    jsonschema.validate(evidence, schema)
    assert metadata["source_folder"] == "Case/#2/EZC-0001 - DX_1_LH"
    assert metadata["source_evidence_path"].endswith("seed_evidence.json")
    assert evidence["source_folder"] == metadata["source_folder"]
    assert evidence["release_status"] == "review_aid_only"
    assert evidence["export_allowed"] is False
    assert evidence["production_approved"] is False
    assert evidence["pdf_export_enabled"] is False
    assert all(source["committed_copy"] is False for source in evidence["source_files"])
    assert any(
        source["role"] == "ez_drawing_pdf"
        and source["sha256"]
        == "B7BF71A2B5C7DE344B0D7F544E56B0C6F7CCC79BAC3F9A7C826F2970C2FE6D7E"
        for source in evidence["source_files"]
    )
    assert {slot["slot_id"] for slot in evidence["slot_evidence"]} >= {
        "slot.FH",
        "slot.FL",
        "slot.CH",
        "slot.CL",
        "slot.CD",
        "slot.HDx1",
        "slot.HD2",
        "slot.I1",
        "slot.S1",
        "slot.O2",
        "slot.R2",
        "slot.TAG",
        "slot.MODEL_NUMBER",
    }
    assert evidence["observed_candidates"] == [
        {
            "field": "OAL",
            "value": "20.25",
            "unit": "in",
            "source_channels": ["ez_drawing_pdf"],
            "review_status": "observed_candidate_review_required",
            "notes": "Observed on the EZ drawing only; not an approved CoilForge formula.",
        }
    ]


def test_slot_population_replaces_seed_values_and_keeps_safety_metadata() -> None:
    result = populate_template_slots(
        "coilmaster_dx_lh_header1",
        {
            "slot.FH": "12.00",
            "slot.FL": "15.00",
            "slot.CH": "13.25",
            "slot.CL": "18.00",
            "slot.CD": "5.50",
            "slot.TF": "0.63",
            "slot.BF": "0.63",
            "slot.HF": "1.50",
            "slot.RF": "1.50",
            "slot.RB": "1.75",
            "slot.OAL": "20.25",
            "slot.HDx1": "4.50",
            "slot.HD2": "3.50",
            "slot.SL2": "8.00",
            "slot.I1": "3.00",
            "slot.S1": "2.75",
            "slot.O2": "2.00",
            "slot.R2": "0.63",
            "slot.ROWS": "4.00",
            "slot.TAG": "CDXC-1",
            "slot.MODEL_NUMBER": "DX-F-S-04-13-12.00x15.00-L",
            "slot.NOTES": "Copper Straps Required",
            "slot.TUBE_MATERIAL": "0.375 x 0.016 / Copper Smooth",
            "slot.FIN_MATERIAL": "13 Fins Per Inch / 0.0075 Aluminum / Sine Wave",
            "slot.CIRCUITING": "2 Feed / 24 Pass",
            "slot.CALLOUT_1": "COLLARED HOLES REQUIRED",
        },
    )

    assert result.blocked_reasons == ()
    assert "{{slot." not in result.svg
    for expected in (
        "12.00 FH",
        "15.00 FL",
        "13.25 CH",
        "5.50 CD",
        "4.50 HDx1",
        "3.50 HD2",
        "3.00 I1",
        "2.75 S1",
        "2.00 O2",
        "0.63 R2",
        "Tag: CDXC-1",
    ):
        assert expected in result.svg
    assert "REVIEW AID - NOT FOR MANUFACTURING" in result.svg
    assert result.metadata["release_status"] == "review_aid_only"
    assert result.metadata["export_allowed"] is False
    assert result.metadata["production_approved"] is False
    assert result.metadata["pdf_export_enabled"] is False


def test_missing_required_slot_blocks_when_preview_not_allowed() -> None:
    result = populate_template_slots(
        "coilmaster_dx_lh_header1",
        {
            "slot.FL": "15.00",
            "slot.CH": "13.25",
            "slot.CL": "18.00",
            "slot.CD": "5.50",
            "slot.TF": "0.63",
            "slot.BF": "0.63",
            "slot.HDx1": "4.50",
            "slot.HD2": "3.50",
            "slot.ROWS": "4.00",
            "slot.TAG": "CDXC-1",
            "slot.MODEL_NUMBER": "DX-F-S-04-13-12.00x15.00-L",
        },
        preview_allowed=False,
    )

    assert result.svg == ""
    assert "slot.FH" in result.missing_required_slots
    assert result.metadata["template_population_status"] == "blocked"


def test_no_raw_pdf_files_are_committed_into_template_library() -> None:
    template_root = ROOT / "templates" / "drawing"

    assert template_root.exists()
    assert not list(template_root.rglob("*.pdf"))
