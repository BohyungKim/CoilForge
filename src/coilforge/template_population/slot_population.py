from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from coilforge.template_population.catalog import (
    DrawingTemplateEntry,
    get_template_entry,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_WATERMARK = "REVIEW AID - NOT FOR MANUFACTURING"


@dataclass(frozen=True)
class SlotPopulationResult:
    template_id: str
    svg: str
    metadata: dict[str, Any]
    populated_slots: tuple[str, ...]
    missing_required_slots: tuple[str, ...]
    blocked_reasons: tuple[str, ...]


def populate_template_slots(
    template_id: str,
    slot_values: dict[str, Any],
    *,
    preview_allowed: bool = True,
) -> SlotPopulationResult:
    entry = get_template_entry(template_id)
    if entry is None:
        return _blocked_result(
            template_id,
            "No template entry exists for the requested template_id.",
        )
    if not entry.generation_allowed:
        return _blocked_result(
            template_id,
            entry.blocked_reason or "Template is not active for generation.",
            entry=entry,
        )
    if entry.template_path is None or entry.slot_map_path is None:
        return _blocked_result(
            template_id,
            "Template entry is missing template_path or slot_map_path.",
            entry=entry,
        )

    template_path = REPO_ROOT / entry.template_path
    slot_map_path = REPO_ROOT / entry.slot_map_path
    template_svg = template_path.read_text(encoding="utf-8")
    slot_map = json.loads(slot_map_path.read_text(encoding="utf-8"))
    slot_definitions = slot_map["slots"]
    required_slots = {
        slot["slot_id"]
        for slot in slot_definitions
        if slot.get("required_for_preview") is True
    }
    replacements = {
        slot["slot_id"]: _slot_text(slot["slot_id"], slot_values)
        for slot in slot_definitions
    }
    missing_required_slots = tuple(
        sorted(
            slot_id
            for slot_id in required_slots
            if _is_blank(slot_values.get(slot_id))
        )
    )
    if missing_required_slots and not preview_allowed:
        return _blocked_result(
            template_id,
            "Missing required slots and preview_allowed=false.",
            entry=entry,
            missing_required_slots=missing_required_slots,
        )

    svg = template_svg
    for slot_id, value in replacements.items():
        svg = svg.replace("{{" + slot_id + "}}", html.escape(str(value), quote=True))

    metadata = _metadata(entry)
    metadata.update(
        {
            "template_population_status": (
                "generated_with_review_required_values"
                if missing_required_slots
                else "generated_review_aid"
            ),
            "populated_slot_count": len(slot_definitions) - len(missing_required_slots),
            "missing_required_slots": list(missing_required_slots),
        }
    )
    return SlotPopulationResult(
        template_id=template_id,
        svg=svg,
        metadata=metadata,
        populated_slots=tuple(sorted(slot_values)),
        missing_required_slots=missing_required_slots,
        blocked_reasons=(),
    )


def _slot_text(slot_id: str, slot_values: dict[str, Any]) -> str:
    value = slot_values.get(slot_id)
    if _is_blank(value):
        return "REVIEW REQUIRED"
    return str(value)


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _metadata(entry: DrawingTemplateEntry | None) -> dict[str, Any]:
    return {
        "template_id": None if entry is None else entry.template_id,
        "template_status": None if entry is None else entry.status,
        "release_status": "review_aid_only",
        "export_allowed": False,
        "production_approved": False,
        "pdf_export_enabled": False,
        "review_watermark": REVIEW_WATERMARK,
    }


def _blocked_result(
    template_id: str,
    reason: str,
    *,
    entry: DrawingTemplateEntry | None = None,
    missing_required_slots: tuple[str, ...] = (),
) -> SlotPopulationResult:
    metadata = _metadata(entry)
    metadata.update(
        {
            "template_id": template_id,
            "template_population_status": "blocked",
            "missing_required_slots": list(missing_required_slots),
        }
    )
    return SlotPopulationResult(
        template_id=template_id,
        svg="",
        metadata=metadata,
        populated_slots=(),
        missing_required_slots=missing_required_slots,
        blocked_reasons=(reason,),
    )
