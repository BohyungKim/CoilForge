from __future__ import annotations

from collections.abc import Iterable

from coilforge.compatibility.decision_capture import (
    ALLOWED_PROPOSED_DECISIONS,
    DecisionCaptureItem,
    DecisionCapturePacket,
    ProposedDecision,
)


EXCLUDED_REVIEWER_DECISION_VALUES = (
    "engineering_approved",
    "production_approved",
    "export_ready",
    "quote_ready",
)


def build_manual_review_checklist(packet: DecisionCapturePacket) -> str:
    """Return a Notion-ready manual review checklist without writing files."""

    lines: list[str] = [
        "# CoilForge Phase 2C-M5 Manual Review Checklist",
        "",
        "## Executive Summary",
        "",
        f"- Case ID: `{packet.case_id}`",
        f"- Decision items accounted for: `{len(packet.items)}/{len(packet.items)}`",
        f"- Decision sections: `{len(packet.sections)}`",
        "- Purpose: manual review checklist and copy-paste review format only.",
        "- Exact matches are not engineering approved.",
        "- Source-only values are not ready.",
        "- CD/BF/TF/CH are not downstream-approved.",
        "- Drawing-impacting fields need John/engineering review.",
        "- Unit conversion remains blocked until explicit conversion rule approval.",
        "- Captured decisions do not apply downstream.",
        "",
        "## Safety Status",
        "",
        _safety_table(packet),
        "",
        "## Field Category Summary",
        "",
        _summary_table(packet),
        "",
        "## Unresolved Decision Summary",
        "",
        _proposed_decision_table(packet),
        "",
        _section_block(
            "CD/BF/TF/CH Review",
            "Baseline drawing fields remain EZ-only, review-required, drawing-impacting, "
            "and not downstream-approved.",
            _items_for_keys(packet, packet.sections["cd_bf_tf_ch"].field_keys),
            packet.sections["cd_bf_tf_ch"].risk_if_skipped,
        ),
        "",
        _section_block(
            "Drawing-Impacting Fields",
            "Drawing-impacting fields need John/engineering review before drawing "
            "semantics can be treated as approved.",
            _items_for_keys(packet, packet.sections["drawing_impacting_fields"].field_keys),
            packet.sections["drawing_impacting_fields"].risk_if_skipped,
        ),
        "",
        _section_block(
            "Exact Match Section",
            "Exact matches remain confirmed for review only and are not engineering approved.",
            _items_for_keys(packet, packet.sections["exact_matches"].field_keys),
            packet.sections["exact_matches"].risk_if_skipped,
        ),
        "",
        _section_block(
            "Source-Only Values Section",
            "Submittal-only and EZ-only values remain review_required_source_only.",
            _items_for_keys(
                packet,
                (
                    *packet.sections["submittal_only_values"].field_keys,
                    *packet.sections["ez_only_values"].field_keys,
                ),
            ),
            "Source-only values could be mistaken for ready values.",
        ),
        "",
        _section_block(
            "Missing-Both Fields Section",
            "Missing-both fields remain unmapped or pending review and are not approved.",
            _items_for_keys(packet, packet.sections["missing_both_fields"].field_keys),
            packet.sections["missing_both_fields"].risk_if_skipped,
        ),
        "",
        _section_block(
            "POs-Supported Fields Section",
            "POs-supported values remain recommended_for_rule_review_not_ready.",
            _items_for_keys(packet, packet.sections["pos_supported_fields"].field_keys),
            packet.sections["pos_supported_fields"].risk_if_skipped,
        ),
        "",
        _section_block(
            "POs-Needs-Review Logic Section",
            "POs-needs-review logic remains a quote/BOM review signal only.",
            _items_for_keys(packet, packet.sections["pos_needs_review_logic"].field_keys),
            packet.sections["pos_needs_review_logic"].risk_if_skipped,
        ),
        "",
        _section_block(
            "Unit Conversion Decision Section",
            "Unit conversion remains blocked until explicit conversion rules are approved.",
            [
                item
                for item in packet.items
                if item.proposed_decision == "request_unit_conversion_rule"
                or "unit_conversion" in item.decision_reason
                or item.current_policy.startswith("blocked_requires_explicit_conversion_rule")
            ],
            "A unit mismatch could be used without an approved conversion rule.",
            empty_message="No unit conversion mismatches are present in the default packet.",
        ),
        "",
        "## Final Go/No-Go Review",
        "",
        "- [ ] John/engineering reviewed exact matches as review-only, not engineering approved.",
        "- [ ] Source-only values remain not ready.",
        "- [ ] CD/BF/TF/CH remain not downstream-approved.",
        "- [ ] Drawing-impacting fields have explicit follow-up owners.",
        "- [ ] Unit conversion decisions remain blocked unless future rules are approved.",
        "- [ ] Export remains disabled.",
        "- [ ] PDF export remains disabled.",
        "- [ ] Direct Coil final export remains unavailable.",
        "- [ ] Manual decisions were not applied to runtime behavior.",
        "",
    ]
    return "\n".join(lines)


def build_manual_decision_capture_template(
    *,
    phase: str = "Phase 2C-M5",
    decision_scope: str = "manual_review_intent_only",
) -> str:
    """Return the static copy-paste manual decision template."""

    allowed_rows = "\n".join(
        f"- `{decision}`" for decision in ALLOWED_PROPOSED_DECISIONS
    )
    excluded_rows = "\n".join(
        f"- `{decision}`" for decision in EXCLUDED_REVIEWER_DECISION_VALUES
    )
    return "\n".join(
        [
            "# John Decision Capture Template",
            "",
            "## Review Session Metadata",
            "",
            "| Field | Value |",
            "| --- | --- |",
            "| review_date |  |",
            "| reviewer |  |",
            f"| phase | {phase} |",
            "| reviewed_commit |  |",
            "| case_id |  |",
            f"| decision_scope | {decision_scope} |",
            "",
            "## Warning",
            "",
            "This template records review intent only.",
            "It does not update runtime behavior.",
            "It does not enable export.",
            "It does not approve drawing semantics.",
            "",
            "## Allowed Reviewer Decision Values",
            "",
            allowed_rows,
            "",
            "## Explicitly Excluded Approval / Export Values",
            "",
            excluded_rows,
            "",
            "## Decision Table",
            "",
            "| field_key | direct_coil_group | canonical_path | current_policy | "
            "proposed_decision | reviewer_decision | reviewer_notes | owner | "
            "follow_up_required | safe_for_mvp_test |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            "|  |  |  |  |  |  |  |  |  |  |",
            "",
        ]
    )


def _safety_table(packet: DecisionCapturePacket) -> str:
    rows = [
        ("export_allowed", packet.export_allowed),
        ("pdf_export_enabled", packet.pdf_export_enabled),
        ("direct_coil_final_export_available", packet.direct_coil_final_export_available),
        ("decisions_apply_downstream", packet.decisions_apply_downstream),
        ("raw_private_data_returned", packet.raw_private_data_returned),
    ]
    return _markdown_table(
        ("Safety flag", "Value"),
        ((key, _bool_text(value)) for key, value in rows),
    )


def _summary_table(packet: DecisionCapturePacket) -> str:
    summary = packet.summary
    keys = (
        "total_decision_items",
        "sections",
        "exact_match",
        "submittal_only",
        "ez_only",
        "missing_both",
        "drawing_impacting",
        "required_direct_coil",
        "pos_supported",
        "pos_needs_john_review",
    )
    return _markdown_table(
        ("Category", "Count"),
        ((key, str(summary[key])) for key in keys),
    )


def _proposed_decision_table(packet: DecisionCapturePacket) -> str:
    rows = [
        (decision, str(count))
        for decision, count in packet.counts_by_proposed_decision.items()
    ]
    status_rows = [
        (status, str(count))
        for status, count in packet.counts_by_proposed_decision_status.items()
    ]
    return "\n".join(
        [
            "### Counts by proposed decision",
            "",
            _markdown_table(("Proposed decision", "Count"), rows),
            "",
            "### Counts by proposed decision status",
            "",
            _markdown_table(("Proposed decision status", "Count"), status_rows),
        ]
    )


def _section_block(
    title: str,
    description: str,
    items: Iterable[DecisionCaptureItem],
    risk_if_skipped: str,
    *,
    empty_message: str = "No fields in this section.",
) -> str:
    item_tuple = tuple(items)
    lines = [
        f"## {title}",
        "",
        description,
        "",
        f"Risk if skipped: {risk_if_skipped}",
        "",
    ]
    if item_tuple:
        lines.append(_item_table(item_tuple, risk_if_skipped))
    else:
        lines.append(empty_message)
    return "\n".join(lines)


def _item_table(
    items: tuple[DecisionCaptureItem, ...],
    risk_if_skipped: str,
) -> str:
    return _markdown_table(
        (
            "field_key",
            "direct_coil_group",
            "canonical_path",
            "comparison_category",
            "current_policy",
            "proposed_decision",
            "proposed_decision_status",
            "required_owner",
            "drawing_impact",
            "direct_coil_impact",
            "quote_impact",
            "risk_if_skipped",
            "reviewer_notes",
        ),
        (
            (
                item.field_key,
                item.direct_coil_group,
                item.canonical_path,
                item.comparison_category,
                item.current_policy,
                item.proposed_decision,
                item.proposed_decision_status,
                item.decision_owner,
                _bool_text(item.drawing_impact),
                item.direct_coil_impact,
                item.quote_impact,
                risk_if_skipped,
                "[reviewer_notes]",
            )
            for item in items
        ),
    )


def _items_for_keys(
    packet: DecisionCapturePacket,
    field_keys: Iterable[str],
) -> tuple[DecisionCaptureItem, ...]:
    by_field = packet.by_field_key()
    return tuple(by_field[field_key] for field_key in field_keys if field_key in by_field)


def _markdown_table(
    headers: tuple[str, ...],
    rows: Iterable[tuple[object, ...]],
) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_escape_markdown_cell(value) for value in row) + " |")
    return "\n".join(lines)


def _escape_markdown_cell(value: object) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
