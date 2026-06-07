from __future__ import annotations

from coilforge.compatibility.regression import (
    CompatibilityComparison,
    CompatibilityRegressionReport,
)


def build_compatibility_diff_review_packet(
    report: CompatibilityRegressionReport,
) -> str:
    """Render a John/engineering review packet for compatibility diffs."""

    lines = [
        "# Phase 2C.3 Compatibility Diff Review Packet",
        "",
        "## Review status",
        "",
        f"- Case ID: `{report.case_id}`",
        f"- Packet status: `{report.review_status}`",
        f"- Export allowed: `{report.export_allowed}`",
        "- Production drawing approval: `not_requested_not_granted`",
        "",
        "## Source path summaries",
        "",
        _source_line("Submittal", report.submittal.validation_status, report.submittal.review_required_count, report.submittal.blocked_count, report.submittal.unmapped_count),
        _source_line("EZ JSON", report.ez.validation_status, report.ez.review_required_count, report.ez.blocked_count, report.ez.unmapped_count),
        "",
        "## Compatibility counts",
        "",
        f"- Matches: `{len(report.matching_field_keys)}`",
        f"- Mismatches: `{len(report.mismatch_field_keys)}`",
        f"- Submittal-only: `{len(report.submittal_only_field_keys)}`",
        f"- EZ-only: `{len(report.ez_only_field_keys)}`",
        f"- Missing both: `{len(report.missing_both_field_keys)}`",
        "",
        "## Mismatches requiring review",
        "",
    ]
    lines.extend(_comparison_lines(_filter(report.comparisons, "mismatch")))
    lines.extend(
        [
            "",
            "## Source-only values requiring review",
            "",
            "### Submittal-only",
            "",
        ]
    )
    lines.extend(_comparison_lines(_filter(report.comparisons, "submittal_only")))
    lines.extend(["", "### EZ-only", ""])
    lines.extend(_comparison_lines(_filter(report.comparisons, "ez_only")))
    lines.extend(
        [
            "",
            "## Matched values still requiring review",
            "",
        ]
    )
    matched_review = [
        comparison
        for comparison in _filter(report.comparisons, "match")
        if comparison.review_required
    ]
    lines.extend(_comparison_lines(matched_review))
    lines.extend(
        [
            "",
            "## John/Engineering decisions needed",
            "",
            "- Confirm whether matched sanitized values can be promoted from candidate evidence.",
            "- Review all source-only values before any downstream drawing or import/export use.",
            "- Resolve any mismatch before treating a field as approved.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _source_line(
    label: str,
    validation_status: str,
    review_required_count: int,
    blocked_count: int,
    unmapped_count: int,
) -> str:
    return (
        f"- {label}: validation=`{validation_status}`, "
        f"review_required=`{review_required_count}`, "
        f"blocked=`{blocked_count}`, unmapped=`{unmapped_count}`"
    )


def _filter(
    comparisons: tuple[CompatibilityComparison, ...],
    status: str,
) -> list[CompatibilityComparison]:
    return [comparison for comparison in comparisons if comparison.status == status]


def _comparison_lines(comparisons: list[CompatibilityComparison]) -> list[str]:
    if not comparisons:
        return ["- None."]
    return [
        (
            f"- `{comparison.field_key}` ({comparison.canonical_path}): "
            f"submittal=`{comparison.submittal_value}` {comparison.submittal_unit or ''}, "
            f"ez=`{comparison.ez_value}` {comparison.ez_unit or ''}; "
            f"{comparison.note}"
        ).replace("  ", " ")
        for comparison in comparisons
    ]
