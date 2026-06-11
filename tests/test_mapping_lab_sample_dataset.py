import csv
import json
from pathlib import Path


MAPPING_LAB_ROOT = Path(__file__).resolve().parents[1] / "examples" / "mapping_lab"
CASE_DIRS = [
    MAPPING_LAB_ROOT / "case_001_dx_hgrh",
    MAPPING_LAB_ROOT / "case_002_cwc_hwc",
    MAPPING_LAB_ROOT / "case_003_multi_phwc_hhwc",
    MAPPING_LAB_ROOT / "case_004_dx_image_seed",
    MAPPING_LAB_ROOT / "case_005_hgrh_condensing_image_seed",
    MAPPING_LAB_ROOT / "case_006_v60_dx_hgrh_combined_image_seed",
]
LABEL_COLUMNS = [
    "coil_tag",
    "direct_field_key",
    "direct_label",
    "target_value",
    "target_unit",
    "source_section",
    "source_label",
    "source_value",
    "source_unit",
    "transform",
    "source_type",
    "confidence",
    "review_note",
]
NO_SOURCE_TYPES = {"engineer_default", "calculated", "review_required"}


def test_mapping_lab_sample_cases_have_required_files_and_parse() -> None:
    assert MAPPING_LAB_ROOT.exists()
    for case_dir in CASE_DIRS:
      assert (case_dir / "input" / "pdf_extracted.json").is_file()
      assert (case_dir / "output" / "direct_coil_filled.json").is_file()
      assert (case_dir / "labels" / "field_links.csv").is_file()
      assert (case_dir / "notes.md").is_file()
      assert (case_dir / "input" / "source_images" / "README.md").is_file()

      extracted = json.loads((case_dir / "input" / "pdf_extracted.json").read_text(encoding="utf-8"))
      output = json.loads((case_dir / "output" / "direct_coil_filled.json").read_text(encoding="utf-8"))
      assert extracted["case_id"] == output["case_id"] == case_dir.name
      assert extracted["raw_pdf_stored"] is False
      assert extracted["coil_instances"]
      assert output["coils"]


def test_mapping_lab_field_links_match_extracted_and_output_data() -> None:
    for case_dir in CASE_DIRS:
        extracted = json.loads((case_dir / "input" / "pdf_extracted.json").read_text(encoding="utf-8"))
        output = json.loads((case_dir / "output" / "direct_coil_filled.json").read_text(encoding="utf-8"))
        output_by_tag = {coil["tag"]: coil for coil in output["coils"]}
        source_labels_by_tag = {
            coil["tag"]: {
                section["heading"]: set(section["fields"])
                for section in coil["sections"]
            }
            for coil in extracted["coil_instances"]
        }
        unit_summary_fields = set(extracted.get("unit_summary", {}).get("fields", {}))
        cover_labels = {"Qty", "Handing", "Tag", "Item", "Model"}

        with (case_dir / "labels" / "field_links.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

        assert rows
        assert rows[0].keys() == set(LABEL_COLUMNS)
        for row in rows:
            assert row["coil_tag"] in output_by_tag
            assert row["direct_field_key"] in output_by_tag[row["coil_tag"]]["fields"]
            assert row["target_value"] != ""
            assert row["source_type"] in {
                "pdf",
                "pdf_normalized",
                "engineer_default",
                "calculated",
                "review_required",
            }
            if row["source_type"] in NO_SOURCE_TYPES:
                continue
            if row["source_section"] == "Cover Page":
                assert row["source_label"] in cover_labels
            elif row["source_section"] == "Unit Details":
                section_fields = source_labels_by_tag.get(row["coil_tag"], {}).get("Unit Details", set())
                assert row["source_label"] in unit_summary_fields or row["source_label"] in section_fields
            else:
                assert row["source_label"] in source_labels_by_tag[row["coil_tag"]][row["source_section"]]


def test_mapping_lab_sequence_case_keeps_second_phwc_and_hhwc_distinct() -> None:
    extracted = json.loads(
        (MAPPING_LAB_ROOT / "case_003_multi_phwc_hhwc" / "input" / "pdf_extracted.json").read_text(
            encoding="utf-8"
        )
    )
    sequence_by_tag = {
        coil["tag"]: (coil["coil_format"], coil["sequence_index"], coil["section_occurrence"])
        for coil in extracted["coil_instances"]
    }
    assert sequence_by_tag == {
        "PHWC-1": ("preheat_hot_water", 1, 1),
        "HHWC-1": ("heating_hot_water", 1, 1),
        "PHWC-2": ("preheat_hot_water", 2, 2),
        "HHWC-2": ("heating_hot_water", 2, 2),
    }


def test_mapping_lab_v60_combined_case_keeps_dx_and_hgrh_distinct() -> None:
    extracted = json.loads(
        (
            MAPPING_LAB_ROOT
            / "case_006_v60_dx_hgrh_combined_image_seed"
            / "input"
            / "pdf_extracted.json"
        ).read_text(encoding="utf-8")
    )
    output = json.loads(
        (
            MAPPING_LAB_ROOT
            / "case_006_v60_dx_hgrh_combined_image_seed"
            / "output"
            / "direct_coil_filled.json"
        ).read_text(encoding="utf-8")
    )

    assert {coil["tag"]: coil["coil_format"] for coil in extracted["coil_instances"]} == {
        "CDXC-1": "dx",
        "RHHGRC-1": "condensing",
    }
    assert {coil["tag"]: coil["direct_coil_format"] for coil in output["coils"]} == {
        "CDXC-1": "dx",
        "RHHGRC-1": "condensing",
    }
