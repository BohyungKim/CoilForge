from __future__ import annotations

import re
from typing import Any

from coilforge.direct_coil.draft import DirectCoilDraftField, DirectCoilInputDraft
from coilforge.drawing.intent import DrawingIntent, DrawingPreviewResult
from coilforge.drawing.parameters import DrawingParameterSet
from coilforge.phase2a.drawing_populator import render_drawing_intent_preview


_FRACTION_TEXT_PATTERN = re.compile(r"^\s*(?:(?P<whole>-?\d+)\s+)?(?P<num>\d+)\s*/\s*(?P<den>\d+)\s*(?:in|inch|inches|\")?\s*$", re.IGNORECASE)


def create_drawing_intent_from_direct_coil(
    draft: DirectCoilInputDraft,
    parameter_set: DrawingParameterSet,
    *,
    title_block: dict[str, Any] | None = None,
    notes: list[str] | None = None,
) -> DrawingIntent:
    title = dict(title_block or {})
    blocked_reasons = _intent_blockers(draft, parameter_set)
    preview_allowed = parameter_set.preview_allowed and not blocked_reasons

    return DrawingIntent(
        coil_name=str(title.get("coil_name") or f"Preview {draft.source_canonical_record_id}"),
        product_type=_field_text(draft, "system_type") or title.get("product_type"),
        coil_type=title.get("coil_type"),
        header_type=_required_text(draft, "header_type"),
        airflow_direction=_required_text(draft, "airflow_direction"),
        finned_height=_required_number(draft, "finned_height"),
        finned_length=_required_number(draft, "finned_length"),
        rows_deep=int(_required_number(draft, "rows_deep")),
        fins_per_inch=_required_number(draft, "fins_per_inch"),
        tubes_high=_optional_int(draft, "tubes_high"),
        coil_hand=_required_text(draft, "coil_hand"),
        return_connection_size=_required_number(draft, "return_connection_size"),
        drawing_parameters=dict(parameter_set.parameters),
        title_block={
            "model_number": title.get("model_number", "DIRECT-COIL-DRAFT-PREVIEW"),
            "source_case_id": title.get("source_case_id", draft.source_canonical_record_id),
            "template_id": "phase2a_dx_header1_review_svg",
            "release_status": "review_aid_only",
            **title,
        },
        notes=list(notes or []) + [
            "Drawing preview is review-required.",
            "John drawing semantics review remains pending.",
        ],
        source_evidence_summary=_source_evidence_summary(draft),
        review_status="review_required",
        preview_allowed=preview_allowed,
        export_allowed=False,
        blocked_reasons=blocked_reasons,
    )


def render_direct_coil_svg_preview(
    draft: DirectCoilInputDraft,
    parameter_set: DrawingParameterSet,
    *,
    title_block: dict[str, Any] | None = None,
    notes: list[str] | None = None,
) -> DrawingPreviewResult:
    intent = create_drawing_intent_from_direct_coil(
        draft,
        parameter_set,
        title_block=title_block,
        notes=notes,
    )
    return render_drawing_intent_preview(intent)


def _intent_blockers(
    draft: DirectCoilInputDraft,
    parameter_set: DrawingParameterSet,
) -> list[str]:
    blockers = list(parameter_set.blocked_parameters)
    for key in (
        "header_type",
        "airflow_direction",
        "finned_height",
        "finned_length",
        "rows_deep",
        "fins_per_inch",
        "coil_hand",
        "return_connection_size",
    ):
        field = draft.fields[key]
        if field.status == "blocked":
            blockers.append(key)
        elif key in _NUMERIC_INTENT_KEYS and _is_unparseable_number(field):
            blockers.append(key)
    return list(dict.fromkeys(blockers))


def _required_text(draft: DirectCoilInputDraft, field_key: str) -> str:
    field = draft.fields[field_key]
    return "" if field.value is None else str(field.value)


def _field_text(draft: DirectCoilInputDraft, field_key: str) -> str | None:
    field = draft.fields.get(field_key)
    if field is None or field.value in (None, ""):
        return None
    return str(field.value)


def _required_number(draft: DirectCoilInputDraft, field_key: str) -> float:
    field = draft.fields[field_key]
    return _coerce_number(field.value)


def _optional_int(draft: DirectCoilInputDraft, field_key: str) -> int | None:
    field = draft.fields.get(field_key)
    if field is None or field.value in (None, ""):
        return None
    return int(_coerce_number(field.value))


def _coerce_number(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    fraction = _FRACTION_TEXT_PATTERN.match(text)
    if fraction is not None and int(fraction.group("den")) != 0:
        whole = int(fraction.group("whole") or 0)
        numerator = int(fraction.group("num"))
        denominator = int(fraction.group("den"))
        sign = -1 if whole < 0 else 1
        return whole + sign * (numerator / denominator)
    try:
        return float(text)
    except ValueError:
        # The value is present but not a parseable number — e.g. a submittal cell
        # that PDF text extraction concatenated into one string ("24 WB (F) 75 DB
        # (F): 55"). Degrade to the 0.0 "no usable dimension" sentinel (same as a
        # missing value) instead of crashing the whole PDF preview; the field is
        # surfaced as a blocker (see `_is_unparseable_number` / `_intent_blockers`)
        # so the preview stays gated and the bad value is never drawn as real.
        return 0.0


# Intent fields parsed as required dimensional numbers. A non-empty but
# unparseable value here must gate the preview rather than be silently zeroed.
_NUMERIC_INTENT_KEYS = (
    "finned_height",
    "finned_length",
    "rows_deep",
    "fins_per_inch",
    "return_connection_size",
)


def _is_unparseable_number(field: DirectCoilDraftField | None) -> bool:
    """True when a numeric field carries a value that is present but cannot be
    parsed as a number (so it must block, not be drawn)."""
    if field is None or field.value in (None, ""):
        return False
    value = field.value
    if isinstance(value, (int, float)):
        return False
    text = str(value).strip()
    if _FRACTION_TEXT_PATTERN.match(text) is not None:
        return False
    try:
        float(text)
        return False
    except ValueError:
        return True


def _source_evidence_summary(draft: DirectCoilInputDraft) -> dict[str, list[str]]:
    return {
        field.field_key: [evidence.evidence_id for evidence in field.source_evidence]
        for field in draft.fields.values()
        if field.source_evidence
    }
