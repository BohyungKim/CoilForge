from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.adapters import load_sanitized_ez_json
from coilforge.compatibility import (
    build_decision_matrix_review_surface,
    build_field_decision_matrix,
    build_john_decision_capture_packet,
    build_manual_decision_capture_template,
    build_manual_review_checklist,
    build_mapping_rule_registry,
    build_reconciliation_plan,
    compare_submittal_and_ez,
)
from coilforge.submittal import build_po_logic_intake_summary, load_submittal_candidate_fixture


ROOT = Path(__file__).resolve().parents[1]
SANITIZED_DIR = ROOT / "examples" / "sanitized"
TEMPLATE_DOC = ROOT / "docs" / "templates" / "JOHN_DECISION_CAPTURE_TEMPLATE.md"


def _candidate():
    return load_submittal_candidate_fixture(
        SANITIZED_DIR / "submittal_candidate_dx_header1_default.json"
    )


def _ez_payload():
    return load_sanitized_ez_json(SANITIZED_DIR / "dx_header1_ezc0001_default.json")


def _packet(candidate=None, ez_payload=None):
    report = compare_submittal_and_ez(candidate or _candidate(), ez_payload or _ez_payload())
    registry = build_mapping_rule_registry()
    plan = build_reconciliation_plan(report, registry)
    matrix = build_field_decision_matrix(report, registry, plan)
    surface = build_decision_matrix_review_surface(
        matrix,
        build_po_logic_intake_summary(),
    )
    return build_john_decision_capture_packet(surface)


def _checklist(packet=None) -> str:
    return build_manual_review_checklist(packet or _packet())


def test_manual_review_checklist_can_be_generated_from_decision_capture_packet() -> None:
    content = _checklist()

    assert isinstance(content, str)
    assert "# CoilForge Phase 2C-M5 Manual Review Checklist" in content
    assert "manual review checklist and copy-paste review format only" in content
    assert "Case ID: `SCC-SANITIZED-DX-H1-001__EZC-0001`" in content


def test_checklist_accounts_for_all_52_decision_items() -> None:
    packet = _packet()
    content = _checklist(packet)

    assert "Decision items accounted for: `52/52`" in content
    for item in packet.items:
        assert f"| {item.field_key} |" in content


def test_checklist_includes_all_current_packet_sections() -> None:
    packet = _packet()
    content = _checklist(packet)

    assert "Decision sections: `9`" in content
    assert len(packet.sections) == 9
    for heading in (
        "## CD/BF/TF/CH Review",
        "## Drawing-Impacting Fields",
        "## Exact Match Section",
        "## Source-Only Values Section",
        "## Missing-Both Fields Section",
        "## POs-Supported Fields Section",
        "## POs-Needs-Review Logic Section",
        "## Unit Conversion Decision Section",
        "## Final Go/No-Go Review",
    ):
        assert heading in content


def test_cd_bf_tf_ch_are_present() -> None:
    content = _checklist()

    for field_key in ("CD", "BF", "TF", "CH"):
        assert f"| {field_key} |" in content
    assert "CD/BF/TF/CH are not downstream-approved" in content


def test_drawing_impacting_fields_are_present() -> None:
    content = _checklist()

    assert "| rows_deep |" in content
    assert "| finned_height |" in content
    assert "| header_type |" in content
    assert "Drawing-impacting fields need John/engineering review" in content


def test_exact_matches_are_marked_not_engineering_approved() -> None:
    content = _checklist()

    assert "Exact matches are not engineering approved." in content
    assert "confirmed_for_review_not_engineering_approved" in content
    assert "| rows_deep |" in content


def test_source_only_values_remain_review_required() -> None:
    content = _checklist()

    assert "Submittal-only and EZ-only values remain review_required_source_only." in content
    assert "review_required_source_only" in content
    assert "| CD |" in content


def test_pos_supported_values_are_not_approved() -> None:
    content = _checklist()

    assert "recommended_for_rule_review_not_ready" in content
    assert "| header_type |" in content
    assert "| system_type |" in content
    assert "POs-supported values remain recommended_for_rule_review_not_ready." in content


def test_unit_conversion_remains_blocked_request_rule_only() -> None:
    candidate = _candidate().model_copy(deep=True)
    candidate.geometry["finned_height"] = candidate.geometry["finned_height"].model_copy(
        update={"unit": "mm"}
    )
    content = _checklist(_packet(candidate=candidate))

    assert "Unit conversion remains blocked until explicit conversion rules are approved." in content
    assert "blocked_requires_explicit_conversion_rule" in content
    assert "request_unit_conversion_rule" in content
    assert "| finned_height |" in content


def test_manual_review_template_explicitly_excludes_approval_and_export_values() -> None:
    generated = build_manual_decision_capture_template()
    template_doc = TEMPLATE_DOC.read_text(encoding="utf-8")

    for content in (generated, template_doc):
        excluded_section = content.split("## Explicitly Excluded Approval / Export Values")[1]
        allowed_section = content.split("## Allowed Reviewer Decision Values")[1].split(
            "## Explicitly Excluded Approval / Export Values"
        )[0]
        for value in (
            "engineering_approved",
            "production_approved",
            "export_ready",
            "quote_ready",
        ):
            assert f"`{value}`" in excluded_section
            assert value not in allowed_section


def test_generated_checklist_includes_export_disabled_safety_status() -> None:
    content = _checklist()

    assert "| export_allowed | false |" in content
    assert "| pdf_export_enabled | false |" in content
    assert "| direct_coil_final_export_available | false |" in content
    assert "Export remains disabled." in content
    assert "PDF export remains disabled." in content


def test_generated_checklist_includes_decisions_apply_downstream_false() -> None:
    content = _checklist()

    assert "| decisions_apply_downstream | false |" in content
    assert "Captured decisions do not apply downstream." in content


def test_raw_private_source_text_is_absent() -> None:
    content = _checklist()
    template = build_manual_decision_capture_template()

    for text in (content, template):
        assert "FINNED_HEIGHT:" not in text
        assert "submittal_text" not in text
        assert "raw_pdf" not in text.lower()


def test_generator_returns_string_and_does_not_write_output_files_by_default(tmp_path: Path) -> None:
    before = set(tmp_path.iterdir())
    content = _checklist()
    template = build_manual_decision_capture_template()
    after = set(tmp_path.iterdir())

    assert isinstance(content, str)
    assert isinstance(template, str)
    assert before == after
