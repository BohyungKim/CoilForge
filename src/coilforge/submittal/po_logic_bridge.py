from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal


PoLogicClassification = Literal[
    "reusable_now",
    "reusable_with_sanitization",
    "needs_john_review",
    "not_safe_for_coilforge",
    "not_found",
]


@dataclass(frozen=True)
class PoLogicRuleSummary:
    rule_id: str
    source_location: str
    source_logic_area: str
    coilforge_rule_category: str
    classification: PoLogicClassification
    reusable_summary: str
    safety_boundary: str
    requires_raw_source_data: bool
    raw_text_excluded: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "source_location": self.source_location,
            "source_logic_area": self.source_logic_area,
            "coilforge_rule_category": self.coilforge_rule_category,
            "classification": self.classification,
            "reusable_summary": self.reusable_summary,
            "safety_boundary": self.safety_boundary,
            "requires_raw_source_data": self.requires_raw_source_data,
            "raw_text_excluded": self.raw_text_excluded,
        }


@dataclass(frozen=True)
class PoLogicIntakeSummary:
    inspected_locations: tuple[str, ...]
    found_locations: tuple[str, ...]
    not_found_locations: tuple[str, ...]
    rule_summaries: tuple[PoLogicRuleSummary, ...]
    classification_counts: dict[str, int]
    raw_private_source_data_read: bool
    export_enabled: bool
    pdf_parsing_enabled: bool
    source_status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "inspected_locations": list(self.inspected_locations),
            "found_locations": list(self.found_locations),
            "not_found_locations": list(self.not_found_locations),
            "rule_summaries": [rule.to_dict() for rule in self.rule_summaries],
            "classification_counts": dict(self.classification_counts),
            "raw_private_source_data_read": self.raw_private_source_data_read,
            "export_enabled": self.export_enabled,
            "pdf_parsing_enabled": self.pdf_parsing_enabled,
            "source_status": self.source_status,
        }


_PO_PROJECT_SUBPATH = Path("PO Release Engineering Workflow") / "pdf_extractor"


def _discover_projects_root() -> Path:
    """Ancestor directory that contains the sibling PO project.

    Robust to running from a git worktree, where ``Path.cwd().parent`` is
    ``.claude/worktrees`` rather than the ``Projects`` root that holds the
    sibling PO project. Searches ancestors of both this module and the current
    working directory, and falls back to the legacy ``Path.cwd().parent`` anchor
    when the sibling project is genuinely absent (so the ``not_found`` path is
    preserved).
    """

    candidates: list[Path] = [
        *Path(__file__).resolve().parents,
        Path.cwd().resolve(),
        *Path.cwd().resolve().parents,
    ]
    seen: set[Path] = set()
    for ancestor in candidates:
        if ancestor in seen:
            continue
        seen.add(ancestor)
        if (ancestor / _PO_PROJECT_SUBPATH).is_dir():
            return ancestor
    return Path.cwd().parent


def default_po_logic_source_paths(projects_root: Path | None = None) -> tuple[Path, ...]:
    root = projects_root or _discover_projects_root()
    po_root = root / "PO Release Engineering Workflow" / "pdf_extractor"
    return (
        po_root / "pdf_processing.py",
        po_root / "bom_ordering_rules.py",
        po_root / "EXTRACTION_CONTRACT.md",
        po_root / "PROJECT_CONTEXT.md",
    )


def build_po_logic_intake_summary(
    source_paths: Iterable[Path | str] | None = None,
) -> PoLogicIntakeSummary:
    """Summarize reusable PO logic without importing sibling code or raw data."""

    paths = tuple(Path(path) for path in (source_paths or default_po_logic_source_paths()))
    inspected = tuple(str(path) for path in paths)
    found = tuple(str(path) for path in paths if path.exists() and path.is_file())
    missing = tuple(str(path) for path in paths if str(path) not in found)

    if not found:
        rules = (
            PoLogicRuleSummary(
                rule_id="po_logic_source_not_found",
                source_location="not_found",
                source_logic_area="POs source discovery",
                coilforge_rule_category="source_intake",
                classification="not_found",
                reusable_summary="No safe PO logic source file was found at the inspected paths.",
                safety_boundary="No implementation depends on missing PO source logic.",
                requires_raw_source_data=False,
            ),
        )
    else:
        rules = _known_safe_rule_summaries(found)

    return PoLogicIntakeSummary(
        inspected_locations=inspected,
        found_locations=found,
        not_found_locations=missing,
        rule_summaries=rules,
        classification_counts=_classification_counts(rules),
        raw_private_source_data_read=False,
        export_enabled=False,
        pdf_parsing_enabled=False,
        source_status="found" if found else "not_found",
    )


def _known_safe_rule_summaries(
    found_locations: tuple[str, ...],
) -> tuple[PoLogicRuleSummary, ...]:
    pdf_source = _first_matching(found_locations, "pdf_processing.py")
    bom_source = _first_matching(found_locations, "bom_ordering_rules.py")
    contract_source = _first_matching(found_locations, "EXTRACTION_CONTRACT.md")
    context_source = _first_matching(found_locations, "PROJECT_CONTEXT.md")

    return (
        PoLogicRuleSummary(
            rule_id="po_unit_tag_normalization",
            source_location=pdf_source,
            source_logic_area="coil tag recognition",
            coilforge_rule_category="submittal_identity_rules",
            classification="reusable_now",
            reusable_summary=(
                "Normalize unit tags by uppercasing, collapsing whitespace/dashes, "
                "and rejecting known component-like prefixes or suffixes."
            ),
            safety_boundary="Rule summary only; no raw tag values or PDF text are copied.",
            requires_raw_source_data=False,
        ),
        PoLogicRuleSummary(
            rule_id="po_cover_table_product_detection",
            source_location=pdf_source,
            source_logic_area="product type detection",
            coilforge_rule_category="source_field_detection",
            classification="reusable_with_sanitization",
            reusable_summary=(
                "Use unit-tag prefixes and item-column product keywords as candidate "
                "signals for equipment/product type detection."
            ),
            safety_boundary="Requires sanitized fixtures before any field extraction behavior is enabled.",
            requires_raw_source_data=False,
        ),
        PoLogicRuleSummary(
            rule_id="po_component_coil_detection",
            source_location=pdf_source,
            source_logic_area="coil type detection",
            coilforge_rule_category="component_classification",
            classification="reusable_with_sanitization",
            reusable_summary=(
                "Recognize coil/component families such as cooling, heating, electric "
                "coil, damper, and special component tags."
            ),
            safety_boundary="Can inform review categories only; not approved product logic.",
            requires_raw_source_data=False,
        ),
        PoLogicRuleSummary(
            rule_id="po_bom_linestring_decisions",
            source_location=bom_source,
            source_logic_area="POs workflow logic",
            coilforge_rule_category="quote_or_bom_review_signal",
            classification="needs_john_review",
            reusable_summary=(
                "Linestring-based BOM decisions produce Required/Inventory/Manufactured/N/A "
                "statuses for operational tasks."
            ),
            safety_boundary="Manufacturing/BOM rules are not Direct Coil drawing semantics without review.",
            requires_raw_source_data=False,
        ),
        PoLogicRuleSummary(
            rule_id="po_pdf_extraction_pipeline",
            source_location=pdf_source,
            source_logic_area="submittal PDF reading",
            coilforge_rule_category="out_of_scope_source_parser",
            classification="not_safe_for_coilforge",
            reusable_summary=(
                "PDF text/image extraction and vision fallback exist in the sibling project, "
                "but Phase 2C-M2 does not enable PDF parsing or OCR."
            ),
            safety_boundary="Do not import parser code, OCR, raw PDFs, or customer text.",
            requires_raw_source_data=True,
        ),
        PoLogicRuleSummary(
            rule_id="po_review_before_export_gate",
            source_location=_first_existing(contract_source, context_source),
            source_logic_area="review and export governance",
            coilforge_rule_category="review_gate_policy",
            classification="reusable_now",
            reusable_summary=(
                "Human review is required before export; unreviewed extraction values "
                "must not drive downstream outputs."
            ),
            safety_boundary="Matches CoilForge review-aid posture; export remains disabled.",
            requires_raw_source_data=False,
        ),
        PoLogicRuleSummary(
            rule_id="po_application_team_selection",
            source_location="not_found",
            source_logic_area="application-team selection logic",
            coilforge_rule_category="source_intake_gap",
            classification="not_found",
            reusable_summary="No safe application-team selection logic was found in inspected files.",
            safety_boundary="No team selection behavior is added to CoilForge.",
            requires_raw_source_data=False,
        ),
        PoLogicRuleSummary(
            rule_id="po_bto_selection_workflow",
            source_location="not_found",
            source_logic_area="BTO / selection workflow",
            coilforge_rule_category="source_intake_gap",
            classification="not_found",
            reusable_summary="No safe BTO selection workflow logic was found in inspected files.",
            safety_boundary="No BTO or final selection workflow is added to CoilForge.",
            requires_raw_source_data=False,
        ),
    )


def _classification_counts(
    rules: tuple[PoLogicRuleSummary, ...],
) -> dict[str, int]:
    counts = {
        "reusable_now": 0,
        "reusable_with_sanitization": 0,
        "needs_john_review": 0,
        "not_safe_for_coilforge": 0,
        "not_found": 0,
    }
    for rule in rules:
        counts[rule.classification] += 1
    return counts


def _first_matching(paths: tuple[str, ...], filename: str) -> str:
    for path in paths:
        if Path(path).name.lower() == filename.lower():
            return path
    return "not_found"


def _first_existing(*paths: str) -> str:
    for path in paths:
        if path != "not_found":
            return path
    return "not_found"
