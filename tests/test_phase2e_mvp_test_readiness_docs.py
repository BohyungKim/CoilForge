from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK_DOC = ROOT / "docs" / "PHASE2E_MVP_TEST_RUNBOOK.md"
METRICS_TEMPLATE = ROOT / "docs" / "templates" / "PHASE2E_MVP_TEST_METRICS_TEMPLATE.md"
REPORT_TEMPLATE = ROOT / "docs" / "templates" / "PHASE2E_MVP_TEST_REPORT_TEMPLATE.md"

PROHIBITED_STATUS_VALUES = (
    "engineering_approved",
    "production_approved",
    "export_ready",
    "quote_ready",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(content: str, title_fragment: str, next_title_fragment: str | None = None) -> str:
    lines = content.splitlines()
    start = next(
        index
        for index, line in enumerate(lines)
        if line.startswith("##") and title_fragment.lower() in line.lower()
    )
    end = len(lines)
    if next_title_fragment:
        end = next(
            index
            for index, line in enumerate(lines[start + 1 :], start + 1)
            if line.startswith("##") and next_title_fragment.lower() in line.lower()
        )
    return "\n".join(lines[start:end])


def test_phase2e_mvp_test_runbook_exists() -> None:
    assert RUNBOOK_DOC.exists()
    assert "# Phase 2E-M1 MVP Test Runbook + Metrics Pack" in _read(RUNBOOK_DOC)


def test_phase2e_metrics_template_exists() -> None:
    assert METRICS_TEMPLATE.exists()
    assert "# Phase 2E MVP Test Metrics Template" in _read(METRICS_TEMPLATE)


def test_phase2e_report_template_exists() -> None:
    assert REPORT_TEMPLATE.exists()
    assert "# Phase 2E MVP Test Report Template" in _read(REPORT_TEMPLATE)


def test_runbook_includes_prohibited_raw_data_policy() -> None:
    content = _read(RUNBOOK_DOC)

    for prohibited_input in (
        "raw PDFs",
        "raw customer data",
        "raw Excel exports",
        "raw quote documents",
        "unsanitized PO/source documents",
        "raw submittal PDFs",
        "raw PO/customer documents",
    ):
        assert prohibited_input in content


def test_runbook_includes_export_disabled_policy() -> None:
    content = _read(RUNBOOK_DOC)

    assert "`export_allowed=false`" in content
    assert "`pdf_export_enabled=false`" in content
    assert "`direct_coil_final_export_available=false`" in content
    assert "`production_drawing_approval_claimed=false`" in content
    assert "NO-GO if export/approval accidentally enabled" in content


def test_runbook_includes_drawing_review_snapshot_section() -> None:
    content = _read(RUNBOOK_DOC)

    assert "## 9. Drawing Review Snapshot" in content
    for item in (
        "Watermark visible",
        "Production approval not claimed",
        "Airflow convention status",
        "OAL policy status",
        "Title block wording status",
        "SVG metadata behavior",
    ):
        assert item in content


def test_runbook_includes_cd_bf_tf_ch_review_status() -> None:
    content = _read(RUNBOOK_DOC)

    assert "CD/BF/TF/CH status" in content
    assert "CD/BF/TF/CH drawing semantics" in content
    assert "not treated as production-approved drawing semantics" in content


def test_runbook_includes_timing_metrics() -> None:
    content = _read(RUNBOOK_DOC)

    for timing_metric in (
        "manual_baseline_time",
        "CoilForge_assisted_time",
        "estimated_time_saved",
        "current_manual_process_time",
        "application_team_selection_time",
        "engineering_adjustment_time",
        "drawing_markup/EZ snapshot time",
        "quote_prep_time",
        "intake time",
        "review time",
        "adjustment time",
        "drawing review time",
        "packet generation time",
    ):
        assert timing_metric in content


def test_runbook_includes_go_no_go_criteria() -> None:
    content = _read(RUNBOOK_DOC)

    for criterion in (
        "GO for continued MVP refinement",
        "GO with blockers",
        "NO-GO until drawing review",
        "NO-GO until source evidence improved",
        "NO-GO if export/approval accidentally enabled",
    ):
        assert criterion in content


def test_templates_do_not_allow_approval_or_export_ready_values() -> None:
    for path in (METRICS_TEMPLATE, REPORT_TEMPLATE):
        content = _read(path)
        allowed_section = _section(content, "Allowed Go / No-Go Values", "Prohibited Status Values")
        prohibited_section = _section(content, "Prohibited Status Values")

        for status_value in PROHIBITED_STATUS_VALUES:
            assert status_value not in allowed_section
            assert f"`{status_value}`" in prohibited_section


def test_metrics_template_includes_all_required_metrics() -> None:
    content = _read(METRICS_TEMPLATE)

    for metric in (
        "test_case_id",
        "source_type",
        "manual_baseline_time",
        "CoilForge_assisted_time",
        "estimated_time_saved",
        "total_fields",
        "ready_fields",
        "review_required_fields",
        "blocked_fields",
        "unmapped_fields",
        "exact_matches",
        "submittal_only_fields",
        "ez_only_fields",
        "conflicts",
        "POs_supported_fields",
        "POs_needs_review_fields",
        "engineering_adjustments",
        "manual_corrections",
        "drawing_issues",
        "CD_BF_TF_CH_status",
        "quote_prep_issues",
        "go_no_go_result",
    ):
        assert metric in content


def test_report_template_includes_required_report_sections() -> None:
    content = _read(REPORT_TEMPLATE)

    for section_title in (
        "## 1. Executive Summary",
        "## 2. Test Setup",
        "## 3. Case Used",
        "## 4. Workflow Completed / Not Completed",
        "## 5. Timing Result",
        "## 6. Field Coverage Result",
        "## 7. Drawing Result",
        "## 8. Engineering Adjustment Result",
        "## 9. Review Packet Result",
        "## 10. Blockers",
        "## 11. Go / No-Go Recommendation",
        "## 12. Next Recommended Fixes",
    ):
        assert section_title in content
