"""Copper-strap price adder for the outgoing quote package.

A thin, gated price layer over the R-090 copper-strap *count* rule
(``copper_strap_requirement``). Direct Coil charges a flat **$25.00 per copper
strap** (Ray Leroux email, 2026-06-22), so:

* DX  = 1 strap/header -> $25.00 per header
* HGRH = 2 straps/header -> $50.00 per header

Copper straps only apply to DX and HGRH headers, so CWC/HWC get **no copper-strap
note at all** (``not_applicable``) — never a price, never a review banner. The
result is a review-aid note stamped above each coil's quoted price; the original
quote numbers are never modified.
"""

from __future__ import annotations

from typing import Any

from coilforge.schemas.header_prepopulate import CoilType
from coilforge.services.header_prepopulate_engine import copper_strap_requirement

# Copper straps are a DX / HGRH header feature only. Water coils (CWC/HWC) never
# carry a copper-strap note — they fall through to ``not_applicable`` (note=None).
COPPER_STRAP_COIL_TYPES = frozenset({CoilType.DX, CoilType.HGRH})

# Direct Coil's flat per-strap adder (review aid; engineering/sales confirm before quoting).
COPPER_STRAP_UNIT_PRICE = 25.00
COPPER_STRAP_CURRENCY = "CAD"
COPPER_STRAP_PRICE_EVIDENCE = (
    "Ray Leroux (Direct Coil) email 2026-06-22: $25.00 per copper strap "
    "(example: a 2-header cond coil = $50.00 total)."
)


def copper_strap_price(coil_type: CoilType, header_count: int | None) -> dict[str, Any]:
    """Return the gated copper-strap price adder for one coil.

    Reuses R-090 for the strap count, then multiplies by the flat unit price.
    Mirrors the confidence gate: ``required`` (HIGH count -> price),
    ``not_applicable`` (CWC/HWC -> no strap note at all), ``review_required``
    (header count unknown -> no price). Never invents a price.
    """
    base: dict[str, Any] = {
        "coil_type": coil_type.value,
        "header_count": header_count,
        "unit_price": COPPER_STRAP_UNIT_PRICE,
        "currency": COPPER_STRAP_CURRENCY,
        "strap_count": None,
        "total": None,
        "evidence_refs": [COPPER_STRAP_PRICE_EVIDENCE],
    }

    if coil_type not in COPPER_STRAP_COIL_TYPES:  # water coils -> no copper-strap note
        return {**base, "status": "not_applicable", "note": None}

    result = copper_strap_requirement(coil_type, header_count)
    if result is None:  # header count unknown -> cannot count straps
        return {
            **base,
            "status": "review_required",
            "note": "COPPER STRAPS: header count unknown - review required",
        }

    strap_count = int(result.value)
    total = round(strap_count * COPPER_STRAP_UNIT_PRICE, 2)
    straps_word = "strap" if strap_count == 1 else "straps"
    header_word = "header" if header_count == 1 else "headers"
    # ``note`` is what gets stamped in red above the coil's price — keep it terse.
    # ``detail`` carries the full breakdown for the UI summary line.
    note = f"Copper Strap Adder {COPPER_STRAP_CURRENCY}${total:,.2f}"
    detail = (
        f"{coil_type.value}, {header_count} {header_word} "
        f"({strap_count} {straps_word} x ${COPPER_STRAP_UNIT_PRICE:.0f})"
    )
    return {
        **base,
        "strap_count": strap_count,
        "total": total,
        "status": "required",
        "note": note,
        "detail": detail,
    }
