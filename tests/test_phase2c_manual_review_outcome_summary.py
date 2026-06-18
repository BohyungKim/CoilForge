from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_DOC = ROOT / "docs" / "PHASE2C_M6_MANUAL_REVIEW_OUTCOME_SUMMARY.md"
TEMPLATE_DOC = ROOT / "docs" / "templates" / "JOHN_REVIEW_OUTCOME_SUMMARY_TEMPLATE.md"


ALLOWED_OUTCOME_LABELS = (
    "keep_review_required",
    "keep_blocked",
    "accept_for_review_only",
    "request_more_source_evidence",
    "request_unit_conversion_rule",
    "request_drawing_semantics_review",
    "request_manual_engineering_override",
    "mark_not_applicable",
    "defer_decision",
)

EXCLUDED_OUTCOME_LABELS = (
    "engineering_approved",
    "production_approved",
    "export_ready",
    "quote_ready",
    "direct_coil_export_ready",
    "pdf_export_ready",
)


def _summary() -> str:
    return SUMMARY_DOC.read_text(encoding="utf-8")


def _template() -> str:
    return TEMPLATE_DOC.read_text(encoding="utf-8")


def _section_by_title(
    content: str,
    title_fragment: str,
    next_title_fragment: str | None = None,
) -> str:
    lines = content.splitlines()
    title_fragment_lower = title_fragment.lower()
    start = next(
        index
        for index, line in enumerate(lines)
        if line.startswith("##") and title_fragment_lower in line.lower()
    )
    end = len(lines)
    if next_title_fragment:
        next_title_fragment_lower = next_title_fragment.lower()
        end = next(
            index
            for index, line in enumerate(lines[start + 1 :], start + 1)
            if line.startswith("##") and next_title_fragment_lower in line.lower()
        )
    return "\n".join(lines[start:end])


def test_outcome_summary_template_exists() -> None:
    assert TEMPLATE_DOC.exists()
    assert "# John Review Outcome Summary Template" in _template()


def test_template_includes_review_metadata() -> None:
    content = _template()

    for field in (
        "review_date",
        "reviewer",
        "phase",
        "reviewed_commit",
        "case_or_fixture_id",
        "decision_scope",
    ):
        assert field in content


def test_template_includes_cd_bf_tf_ch_section() -> None:
    content = _template()

    assert "## CD/BF/TF/CH Outcome Section" in content
    for field_key in ("CD", "BF", "TF", "CH"):
        assert f"| {field_key} |" in content
    assert "do not approve drawing semantics" in content


def test_template_includes_drawing_impacting_field_section() -> None:
    content = _template()

    assert "## Drawing-Impacting Field Outcome Section" in content
    assert "Drawing-impacting outcomes remain review notes only." in content
    assert "do not approve production drawings" in content


def test_template_includes_pos_supported_field_section() -> None:
    content = _template()

    assert "## POs-Supported Field Outcome Section" in content
    assert "| header_type | recommended_for_rule_review_not_ready |" in content
    assert "| system_type | recommended_for_rule_review_not_ready |" in content
    assert "do not create quote readiness" in content


def test_template_includes_unit_conversion_section() -> None:
    content = _template()

    assert "## Unit Conversion Outcome Section" in content
    assert "request_unit_conversion_rule" in content
    assert "conversion_rule_needed" in content
    assert "does not create that rule" in content


def test_excluded_labels_are_excluded_values_not_allowed_values() -> None:
    for content in (_template(), _summary()):
        allowed_section = _section_by_title(
            content,
            "Allowed Outcome Labels",
            "Explicitly Excluded",
        )
        excluded_section = _section_by_title(content, "Explicitly Excluded")

        for label in ALLOWED_OUTCOME_LABELS:
            assert f"`{label}`" in allowed_section
        for label in EXCLUDED_OUTCOME_LABELS:
            assert f"`{label}`" in excluded_section
            assert label not in allowed_section


def test_template_states_decisions_do_not_apply_downstream() -> None:
    content = _template()

    assert "Outcomes do not apply downstream." in content
    assert "Outcomes do not change DirectCoilInputDraft readiness." in content
    assert "Outcomes do not change DrawingIntent approval." in content
    assert "| decisions_apply_downstream | false |" in content


def test_template_states_export_pdf_and_direct_coil_final_export_remain_disabled() -> None:
    content = _template()

    assert "| export_allowed | false |" in content
    assert "| pdf_export_enabled | false |" in content
    assert "| direct_coil_final_export_available | false |" in content
    assert "| export_still_disabled | true |" in content
    assert "| pdf_export_still_disabled | true |" in content
    assert "| direct_coil_final_export_still_disabled | true |" in content


def test_summary_doc_records_docs_only_scope_and_safety_flags() -> None:
    content = _summary()

    assert "docs-only manual review outcome summary format" in content
    assert "outcomes do not apply downstream" in content
    assert "`export_allowed=false`" in content
    assert "`pdf_export_enabled=false`" in content
    assert "`direct_coil_final_export_available=false`" in content
