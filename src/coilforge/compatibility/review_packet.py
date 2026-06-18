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
        f"- Exact matches: `{report.category_counts['exact_match']}`",
        f"- Unit mismatches: `{report.category_counts['unit_mismatch']}`",
        f"- Status mismatches: `{report.category_counts['status_mismatch']}`",
        f"- Blocked mismatches: `{report.category_counts['blocked_mismatch']}`",
        "",
        "## Grouped differences",
        "",
    ]
    lines.extend(_grouped_difference_lines(report.comparisons))
    lines.extend(
        [
            "",
            "## Required Direct Coil field issues",
            "",
        ]
    )
    lines.extend(_field_key_lines(report.required_field_issues))
    lines.extend(
        [
            "",
            "## Drawing-impacting issues",
            "",
        ]
    )
    lines.extend(_field_key_lines(report.drawing_impacting_issues))
    lines.extend(
        [
            "",
            "## DrawingIntent comparison",
            "",
            f"- Available: `{report.drawing_intent_comparison['available']}`",
            f"- Matching summary fields: `{len(report.drawing_intent_comparison['matching_summary_fields'])}`",
            f"- Mismatched summary fields: `{len(report.drawing_intent_comparison['mismatched_summary_fields'])}`",
            f"- Export allowed: `{report.drawing_intent_comparison['export_allowed']}`",
            "",
            "## Safety notes",
            "",
            "- Raw/private source text is excluded from this packet.",
            "- Draft and review-required rules do not imply engineering approval.",
            "- Conflicts remain review-required or blocked; no final export is enabled.",
        "",
        "## Mismatches requiring review",
        "",
        ]
    )
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
            f"category=`{comparison.category}`, "
            f"submittal=`{comparison.submittal_value}` {comparison.submittal_unit or ''}, "
            f"ez=`{comparison.ez_value}` {comparison.ez_unit or ''}; "
            f"{comparison.note}"
        ).replace("  ", " ")
        for comparison in comparisons
    ]


def _grouped_difference_lines(
    comparisons: tuple[CompatibilityComparison, ...],
) -> list[str]:
    bucket_order = (
        "geometry",
        "airside",
        "refrigerant",
        "materials",
        "connections",
        "drawing parameters",
        "validation/readiness",
    )
    buckets: dict[str, list[CompatibilityComparison]] = {
        bucket: [] for bucket in bucket_order
    }
    for comparison in comparisons:
        if comparison.category == "exact_match":
            continue
        buckets[_packet_bucket(comparison)].append(comparison)

    lines: list[str] = []
    for bucket in bucket_order:
        lines.extend(["", f"### {bucket.title()}", ""])
        lines.extend(_comparison_lines(buckets[bucket]))
    return lines


def _packet_bucket(comparison: CompatibilityComparison) -> str:
    if comparison.group == "Drawing Parameters":
        return "drawing parameters"
    if comparison.group == "Airside Conditions":
        return "airside"
    if comparison.group == "Refrigerant Conditions":
        return "refrigerant"
    if comparison.group == "Materials & Construction":
        if "connection" in comparison.field_key or comparison.field_key in {
            "coil_hand",
            "return_connection_size",
            "supply_connection_size",
        }:
            return "connections"
        return "materials"
    if comparison.group == "Coil Geometry":
        return "geometry"
    return "validation/readiness"


def _field_key_lines(field_keys: tuple[str, ...]) -> list[str]:
    if not field_keys:
        return ["- None."]
    return [f"- `{field_key}`" for field_key in field_keys]
