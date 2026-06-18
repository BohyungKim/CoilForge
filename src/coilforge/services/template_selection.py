"""Link an extracted coil selection to its drawing template.

Given an extracted selection (coil type + an EZ Coil export and/or explicit
fields), classify it into the template bucket axes and select the template:

    coil_category  (DX | HGRH | CWC | HWC)        <- extracted coil type
    coil_hand      (LH | RH)                       <- CoilHand / coilHand
    header_type    (Header 1..4)                   <- DX: NumCircuits; HGRH: coilStyle
    special_feature(HGBP | None)                   <- DX: Headers[0].IsASC

Decode confirmed against the locked reference cases (Case/#1-3, EZC-0001..0015).
"""

from __future__ import annotations

from typing import Any

from coilforge.template_population.catalog import (
    TemplateSelectionRequest,
    TemplateSelectionResult,
    select_drawing_template,
)

# HGRH coilStyle -> header bucket (HG_1=standard, HG_2=faceSplit2Circ, ...).
_HGRH_STYLE_TO_HEADER: dict[str, str] = {
    "standard": "Header 1",
    "facesplit2circ": "Header 2",
    "facesplit3circ": "Header 3",
    "facesplit4circ": "Header 4",
}


def _hand_from(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return "LH" if int(value) == 1 else "RH"
    text = str(value).strip().lower()
    if "left" in text or text in ("l", "lh", "1"):
        return "LH"
    if "right" in text or text in ("r", "rh", "0"):
        return "RH"
    return None


def classify_template_request(
    *,
    coil_type: str,
    ez_json: dict[str, Any] | None = None,
    coil_hand: str | None = None,
    supplier: str = "coilmaster",
) -> TemplateSelectionRequest:
    """Classify an extracted selection into a TemplateSelectionRequest."""
    coil_category = coil_type.strip().upper()
    header_type: str | None = "Header 1"
    special_feature: str | None = None
    hand = _hand_from(coil_hand)

    if ez_json:
        geometry = ez_json.get("Geometry")
        if geometry:  # rich schema (DX / CWC / HWC)
            if hand is None:
                hand = _hand_from(geometry.get("CoilHand"))
            # DX header bucket = number of supply/return header pairs (NumCircuits).
            if coil_category == "DX":
                circuits = geometry.get("NumCircuits")
                if circuits:
                    header_type = f"Header {int(circuits)}"
                # HGBP detected by the distributor header's ASC flag.
                headers = geometry.get("Headers") or []
                first = headers[0] if headers else None
                if geometry.get("isASC") or (first and first.get("IsASC")):
                    special_feature = "HGBP"
                    header_type = None
        else:  # sparse schema (HGRH)
            construction = ez_json.get("Construction") or {}
            physical = ez_json.get("PhysicalData") or {}
            if hand is None:
                hand = _hand_from(construction.get("coilHand"))
            if coil_category == "HGRH":
                style = str(physical.get("coilStyle", "")).strip().lower()
                header_type = _HGRH_STYLE_TO_HEADER.get(style, "Header 1")

    return TemplateSelectionRequest(
        supplier=supplier,
        coil_category=coil_category,
        coil_hand=hand or "LH",
        header_type=header_type,
        special_feature=special_feature,
    )


def link_drawing_template(
    *,
    coil_type: str,
    ez_json: dict[str, Any] | None = None,
    coil_hand: str | None = None,
    supplier: str = "coilmaster",
) -> dict[str, Any]:
    """Classify + select the drawing template for an extracted coil selection."""
    request = classify_template_request(
        coil_type=coil_type, ez_json=ez_json, coil_hand=coil_hand, supplier=supplier
    )
    result: TemplateSelectionResult = select_drawing_template(request)
    return {
        "selection": {
            "coil_category": request.coil_category,
            "coil_hand": request.coil_hand,
            "header_type": request.header_type,
            "special_feature": request.special_feature,
        },
        "template_found": result.found,
        "template_id": result.template_id,
        "template_status": result.template_status,
        "generation_allowed": result.generation_allowed,
        "reasons": list(result.reasons),
    }
