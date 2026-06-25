from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TemplateStatus = Literal[
    "seed_available",
    "needs_pair",
    "placeholder_blocked",
    "active_review_aid",
]

TEMPLATE_BUCKET_COUNT = 22

_GENERATION_ALLOWED_STATUSES = {"active_review_aid"}
_HAND_ALIASES = {
    "L": "LH",
    "LH": "LH",
    "LEFT": "LH",
    "LEFT HAND": "LH",
    "LEFT HANDING": "LH",
    "R": "RH",
    "RH": "RH",
    "RIGHT": "RH",
    "RIGHT HAND": "RH",
    "RIGHT HANDING": "RH",
}


# Templates seeded from the provided EZ drawing PDFs (real CoilMaster format,
# values redacted to slots). Each is an active review-aid template.
# value = (category_dir, source_case_id, reference_status).
#
# Mirror-derived RH/LH pairs are DISABLED (John, 2026-06-17): the horizontal
# mirror flips the dimension callouts' bounding boxes, so the cleaned numbers no
# longer sit on their leader lines (a char-width re-center heuristic could not
# reliably repair it). Each hand must be seeded from its own provided PDF. The
# `_MIRROR` entries are intentionally absent here; their buckets fall through to
# `needs_pair` (generation_allowed=False -> "template not registered") until a
# real seed arrives. The `mirror.py` helper is retained for possible future use
# but no longer activates a template.
_SEEDED = "seeded_from_provided_pdf_review_required"
ACTIVE_TEMPLATES: dict[str, tuple[str, str | None, str]] = {
    "coilmaster_dx_lh_header1": ("dx", "EZC-0001", _SEEDED),
    "coilmaster_dx_rh_header2": ("dx", "EZC-0011", _SEEDED),
    "coilmaster_dx_lh_header3": ("dx", "EZC-0007", _SEEDED),
    "coilmaster_hgrh_lh_header1": ("hgrh", "FEED-HG_1_LH-2572-BOWIE", _SEEDED),
    "coilmaster_hgrh_rh_header1": ("hgrh", "EZC-0012", _SEEDED),
    "coilmaster_hgrh_lh_header2": ("hgrh", "EZC-0008", _SEEDED),
    "coilmaster_hgrh_rh_header3": ("hgrh", "EZC-0016", _SEEDED),
    "coilmaster_dx_lh_hgbp": ("dx", "EZC-0013", _SEEDED),
    "coilmaster_cwc_lh": ("cwc", "EZC-0014", _SEEDED),
    "coilmaster_hwc_lh": ("hwc", "EZC-0005", _SEEDED),
    # 2026-06-21: the 8 former mirror hands + the 4 header-4 buckets are now seeded
    # from real per-hand EZ drawing PDFs (Case/feed/), so every bucket is active.
    # Mirroring is retired; source_case_id is a provenance token (FEED-*) until
    # real EZC IDs are supplied. Catalog is now 22/22 active review aids.
    "coilmaster_dx_rh_header1": ("dx", "FEED-DX_1_RH", _SEEDED),
    "coilmaster_dx_lh_header2": ("dx", "FEED-DX_2_LH", _SEEDED),
    "coilmaster_dx_rh_header3": ("dx", "FEED-DX_3_RH", _SEEDED),
    "coilmaster_dx_rh_hgbp": ("dx", "FEED-DX_HB_RH", _SEEDED),
    "coilmaster_hgrh_rh_header2": ("hgrh", "FEED-HG_2_RH", _SEEDED),
    "coilmaster_hgrh_lh_header3": ("hgrh", "FEED-HG_3_LH", _SEEDED),
    "coilmaster_cwc_rh": ("cwc", "FEED-CW_RH", _SEEDED),
    "coilmaster_hwc_rh": ("hwc", "FEED-HW_RH", _SEEDED),
    "coilmaster_dx_lh_header4": ("dx", "FEED-DX_4_LH", _SEEDED),
    "coilmaster_dx_rh_header4": ("dx", "FEED-DX_4_RH", _SEEDED),
    "coilmaster_hgrh_lh_header4": ("hgrh", "FEED-HG_4_LH", _SEEDED),
    "coilmaster_hgrh_rh_header4": ("hgrh", "FEED-HG_4_RH", _SEEDED),
}


def _active_entry(
    template_id: str,
    coil_category: str,
    hand: str,
    header_type: str | None,
    special_feature: str | None,
) -> "DrawingTemplateEntry":
    cat_dir, source_case_id, reference_status = ACTIVE_TEMPLATES[template_id]
    folder = f"templates/drawing/coilmaster/{cat_dir}/{template_id}"
    return DrawingTemplateEntry(
        template_id=template_id,
        supplier="coilmaster",
        coil_category=coil_category,
        coil_hand=hand,
        header_type=header_type,
        special_feature=special_feature,
        status="active_review_aid",
        generation_allowed=True,
        template_path=f"{folder}/template.svg",
        slot_map_path=f"{folder}/slot_map.json",
        metadata_path=f"{folder}/template_metadata.json",
        source_case_id=source_case_id,
        reference_status=reference_status,
    )


@dataclass(frozen=True)
class DrawingTemplateEntry:
    template_id: str
    supplier: str
    coil_category: str
    coil_hand: str
    header_type: str | None
    special_feature: str | None
    status: TemplateStatus
    generation_allowed: bool
    template_path: str | None
    slot_map_path: str | None
    metadata_path: str | None
    source_case_id: str | None = None
    reference_status: str = "review_required"
    blocked_reason: str | None = None


@dataclass(frozen=True)
class DrawingTemplateCatalog:
    catalog_id: str
    schema_version: str
    supplier: str
    entries: tuple[DrawingTemplateEntry, ...]

    def by_template_id(self) -> dict[str, DrawingTemplateEntry]:
        return {entry.template_id: entry for entry in self.entries}


@dataclass(frozen=True)
class TemplateSelectionRequest:
    supplier: str
    coil_category: str
    coil_hand: str
    header_type: str | None = None
    special_feature: str | None = None
    source_case_id: str | None = None


@dataclass(frozen=True)
class TemplateSelectionResult:
    found: bool
    template_id: str | None
    template_status: TemplateStatus | None
    generation_allowed: bool
    reasons: tuple[str, ...]
    entry: DrawingTemplateEntry | None = None


def load_drawing_template_catalog() -> DrawingTemplateCatalog:
    entries = tuple(_build_catalog_entries())
    if len(entries) != TEMPLATE_BUCKET_COUNT:
        raise RuntimeError(
            f"Template catalog must contain {TEMPLATE_BUCKET_COUNT} buckets; found {len(entries)}."
        )
    return DrawingTemplateCatalog(
        catalog_id="coilforge-template-first-v1",
        schema_version="template-first.1",
        supplier="coilmaster",
        entries=entries,
    )


def list_template_entries(
    *,
    supplier: str | None = None,
    coil_category: str | None = None,
    status: TemplateStatus | None = None,
) -> tuple[DrawingTemplateEntry, ...]:
    return tuple(
        entry
        for entry in load_drawing_template_catalog().entries
        if (supplier is None or entry.supplier == _normalize_supplier(supplier))
        and (
            coil_category is None
            or entry.coil_category == _normalize_category(coil_category)
        )
        and (status is None or entry.status == status)
    )


def get_template_entry(template_id: str) -> DrawingTemplateEntry | None:
    return load_drawing_template_catalog().by_template_id().get(template_id)


def select_drawing_template(
    request: TemplateSelectionRequest,
) -> TemplateSelectionResult:
    supplier = _normalize_supplier(request.supplier)
    category = _normalize_category(request.coil_category)
    hand = _normalize_hand(request.coil_hand)
    header = _normalize_header_type(request.header_type)
    special = _normalize_special_feature(request.special_feature)

    matches = [
        entry
        for entry in load_drawing_template_catalog().entries
        if entry.supplier == supplier
        and entry.coil_category == category
        and entry.coil_hand == hand
        and entry.special_feature == special
        and _header_matches(entry.header_type, header, special)
    ]
    if not matches:
        return TemplateSelectionResult(
            found=False,
            template_id=None,
            template_status=None,
            generation_allowed=False,
            reasons=(
                "No matching template bucket exists; drawing generation is blocked.",
            ),
        )

    entry = matches[0]
    reasons: list[str] = []
    if request.source_case_id and entry.source_case_id:
        if request.source_case_id != entry.source_case_id:
            reasons.append(
                "Selected by category/hand/header, but source_case_id differs from seed evidence."
            )
    if not entry.generation_allowed:
        reasons.append(entry.blocked_reason or "Template is not active for generation.")
    else:
        reasons.append("Template is active as a review-aid slot-population template.")
    return TemplateSelectionResult(
        found=True,
        template_id=entry.template_id,
        template_status=entry.status,
        generation_allowed=entry.generation_allowed,
        reasons=tuple(reasons),
        entry=entry,
    )


def _build_catalog_entries() -> list[DrawingTemplateEntry]:
    entries: list[DrawingTemplateEntry] = []
    for category in ("dx", "hgrh"):
        for header_number in range(1, 5):
            for hand in ("LH", "RH"):
                entries.append(
                    _entry_for_header_category(category, header_number, hand)
                )
    for hand in ("LH", "RH"):
        entries.append(_entry_for_dx_hgbp(hand))
    for category in ("cwc", "hwc"):
        for hand in ("LH", "RH"):
            entries.append(_entry_for_water_category(category, hand))
    return entries


def _entry_for_header_category(
    category: str,
    header_number: int,
    hand: str,
) -> DrawingTemplateEntry:
    template_id = f"coilmaster_{category}_{hand.lower()}_header{header_number}"
    if template_id in ACTIVE_TEMPLATES:
        return _active_entry(
            template_id, category.upper(), hand, f"Header {header_number}", None
        )

    source_case_id = _known_source_case(category, header_number, hand)
    no_reference = (
        (category == "dx" and header_number == 4)
        or (category == "hgrh" and header_number == 4)
    )
    return DrawingTemplateEntry(
        template_id=template_id,
        supplier="coilmaster",
        coil_category=category.upper(),
        coil_hand=hand,
        header_type=f"Header {header_number}",
        special_feature=None,
        status="placeholder_blocked" if no_reference else "needs_pair",
        generation_allowed=False,
        template_path=None,
        slot_map_path=None,
        metadata_path=None,
        source_case_id=source_case_id,
        reference_status="missing_reference" if no_reference else "known_reference_not_seeded",
        blocked_reason=(
            "No reference drawing exists; surrogate or mirror generation is not allowed."
            if no_reference
            else "Template drawing pair has not been seeded and slotted yet."
        ),
    )


def _entry_for_dx_hgbp(hand: str) -> DrawingTemplateEntry:
    template_id = f"coilmaster_dx_{hand.lower()}_hgbp"
    if template_id in ACTIVE_TEMPLATES:
        return _active_entry(template_id, "DX", hand, None, "HGBP")
    return DrawingTemplateEntry(
        template_id=template_id,
        supplier="coilmaster",
        coil_category="DX",
        coil_hand=hand,
        header_type=None,
        special_feature="HGBP",
        status="needs_pair",
        generation_allowed=False,
        template_path=None,
        slot_map_path=None,
        metadata_path=None,
        source_case_id="EZC-0013" if hand == "LH" else None,
        reference_status="known_reference_not_seeded" if hand == "LH" else "needs_pair",
        blocked_reason="HGBP drawing visibility and template slots require John review.",
    )


def _entry_for_water_category(category: str, hand: str) -> DrawingTemplateEntry:
    template_id = f"coilmaster_{category}_{hand.lower()}"
    if template_id in ACTIVE_TEMPLATES:
        return _active_entry(template_id, category.upper(), hand, "Header 1", None)
    source = None
    if category == "cwc" and hand == "LH":
        source = "EZC-0014"
    if category == "hwc" and hand == "LH":
        source = "EZC-0005"
    return DrawingTemplateEntry(
        template_id=template_id,
        supplier="coilmaster",
        coil_category=category.upper(),
        coil_hand=hand,
        header_type="Header 1",
        special_feature=None,
        status="needs_pair",
        generation_allowed=False,
        template_path=None,
        slot_map_path=None,
        metadata_path=None,
        source_case_id=source,
        reference_status="known_reference_not_seeded" if source else "needs_pair",
        blocked_reason="Water-coil template drawing pair has not been seeded and slotted yet.",
    )


def _known_source_case(category: str, header_number: int, hand: str) -> str | None:
    if category == "dx" and header_number == 2 and hand == "RH":
        return "EZC-0011"
    if category == "dx" and header_number == 3 and hand == "LH":
        return "EZC-0007"
    if category == "hgrh" and header_number == 1 and hand == "LH":
        return "EZC-0002"
    if category == "hgrh" and header_number == 1 and hand == "RH":
        return "EZC-0012"
    if category == "hgrh" and header_number == 2 and hand == "LH":
        return "EZC-0008"
    return None


def _normalize_supplier(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_category(value: str) -> str:
    return str(value or "").strip().upper()


def _normalize_hand(value: str) -> str:
    normalized = str(value or "").strip().upper().replace("_", " ")
    return _HAND_ALIASES.get(normalized, normalized)


def _normalize_header_type(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip()
    if normalized.lower().startswith("header"):
        parts = normalized.split()
        if parts and parts[-1].isdigit():
            return f"Header {parts[-1]}"
    if normalized.isdigit():
        return f"Header {normalized}"
    return normalized


def _normalize_special_feature(value: str | None) -> str | None:
    if value in (None, "", "None", "NONE"):
        return None
    normalized = str(value).strip().upper().replace(" ", "_")
    if normalized in {"ASC", "HOT_GAS_BYPASS", "HGBP"}:
        return "HGBP"
    return normalized


def _header_matches(
    entry_header: str | None,
    request_header: str | None,
    special_feature: str | None,
) -> bool:
    if special_feature == "HGBP":
        return True
    return entry_header == request_header
