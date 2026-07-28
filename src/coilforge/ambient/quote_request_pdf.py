"""Ambient Dynamics quote-request PDF — the paper artifact John hands the supplier.

The Ambient "package" mode already transcribes a submittal into a per-coil performance page
plus a drawing, but it lived only on screen: the whole panel's sole export was the
compare-mode Excel fill, so there was nothing to actually send Ambient. This module turns
that same payload into PDF bytes.

Deliberately NOT a renderer backend. It consumes ``AmbientPackage.as_dict()`` — an
already-transcribed, already-gated payload — computes no geometry and touches no geometry
model, so it stays outside the model -> layout -> backend pipeline (same standing as
``package/svg_to_pdf.py``). It lays out text on a page; that is all.

Two composition choices worth stating, because both were weighed:

* **Pages are drawn with ``fitz`` primitives, not built as an SVG string.** A performance
  page is a variable-width text table that needs measured columns and pagination, which
  ``fitz.get_text_length`` provides. Every SVG that reaches ``svg_to_pdf_bytes`` today is a
  seeded ``template.svg`` using presentation attributes, so MuPDF's handling of a
  ``<style>``-driven text table is unverified here — not something to bet the feature on.
  ``svg_to_pdf_bytes`` is still used for the drawing page, where the input already IS an SVG.
* **A missing value renders as a dash, never as 0, "N/A", or a guess.** This page goes to an
  external supplier; an invented number would be quoted against. (All text is transliterated
  to glyphs MuPDF's base-14 font can actually draw — see ``_ASCII_FALLBACKS`` — because an
  em dash silently renders as a middle dot.)

Pure function in, result object out — no file writes. ``export_allowed`` is hard-wired
``False`` and is not a constructor argument: a payload claiming otherwise cannot promote it.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from coilforge.package.assembler import REVIEW_WATERMARK
from coilforge.package.svg_to_pdf import svg_to_pdf_bytes
from coilforge.phase2a.renderer import _fmt

# US Letter, portrait. Drawing pages keep whatever size their SVG produces (the seeded
# templates are landscape), so the document is intentionally mixed-orientation: the
# performance table reads best portrait and the drawing best landscape.
_PAGE_W = 612.0
_PAGE_H = 792.0
_MARGIN = 48.0

_BANNER_HEIGHT = 20.0
_BANNER_BASELINE = 13.0

_FS_TITLE = 16
_FS_HEADING = 11
_FS_BODY = 9
_FS_SMALL = 8
_LINE_H = 13.0

# MuPDF's base-14 Helvetica has no em/en dash or curly quotes: it silently substitutes a
# middle dot, so "—" renders as "·" on the page. Degree and superscript-two DO render and are
# deliberately left alone (they carry engineering meaning in the unit labels). Transliteration
# happens at every insert point rather than in the literals, so a future edit that types an
# em dash cannot reintroduce the bug. Verified against fitz 1.26 — never map to blank.
_ASCII_FALLBACKS = {
    "—": "-",  # em dash   -> hyphen
    "–": "-",  # en dash   -> hyphen
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "…": "...",
    "→": "->",
}

# The single never-invent placeholder: "not stated in the submittal". A lone hyphen is the
# conventional engineering-table marker and cannot be misread as a number.
_MISSING = "-"

_LABEL_W = 210.0
_VALUE_W = 150.0


class AmbientQuoteRequestPdf(BaseModel):
    """Built quote-request PDF. ``pdf_base64`` is the whole document, base64-encoded."""

    model_config = ConfigDict(extra="forbid")

    pdf_base64: str
    page_count: int
    coil_count: int
    # One entry per coil, so the caller can say what landed where without re-parsing the PDF.
    coil_pages: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    watermarked: bool = True
    # Safety contract — never relaxed by this layer, never taken from the input payload.
    export_allowed: bool = False
    production_drawing_approval_claimed: bool = False
    raw_private_data_returned: bool = False


def build_ambient_quote_request_pdf(
    package: dict[str, Any],
    *,
    project_name: str | None = None,
    project_number: str | None = None,
    generated_on: date | None = None,
) -> AmbientQuoteRequestPdf:
    """Compose the quote-request PDF from an ``AmbientPackage.as_dict()`` payload.

    Page order: cover, then per coil its performance page(s) followed by its drawing page.
    Raises ``ValueError`` when the payload carries no coils — an empty quote request is a
    caller bug, not a document to hand a supplier.
    """
    import fitz  # PyMuPDF — lazy import (see package/svg_to_pdf.py)

    coils = list(package.get("coils") or [])
    if not coils:
        raise ValueError("build_ambient_quote_request_pdf: package contains no coils")

    warnings: list[str] = list(package.get("warnings") or [])
    coil_pages: list[dict[str, Any]] = []

    doc = fitz.open()
    try:
        _cover_page(
            doc,
            project_name=project_name,
            project_number=project_number,
            generated_on=generated_on,
            coils=coils,
        )
        for coil in coils:
            first_index = doc.page_count
            _performance_pages(doc, coil)
            performance_page_count = doc.page_count - first_index
            drawing_index = _drawing_page(doc, coil, warnings)
            coil_pages.append(
                {
                    "tag": coil.get("tag"),
                    "category": coil.get("category"),
                    "performance_page_index": first_index,
                    "performance_page_count": performance_page_count,
                    "drawing_page_index": drawing_index,
                    "drawing_omitted_reason": (coil.get("drawing") or {}).get("omitted_reason"),
                    "missing_field_count": len(coil.get("missing_fields") or []),
                }
            )
        pdf_bytes = doc.tobytes()
        page_count = doc.page_count
    finally:
        doc.close()

    import base64

    return AmbientQuoteRequestPdf(
        pdf_base64=base64.b64encode(pdf_bytes).decode("ascii"),
        page_count=page_count,
        coil_count=len(coils),
        coil_pages=coil_pages,
        warnings=warnings,
    )


# --- text output -----------------------------------------------------------------------


def _ascii(text: str) -> str:
    """Swap glyphs MuPDF's base-14 font cannot draw for ASCII equivalents."""
    out = str(text)
    for bad, good in _ASCII_FALLBACKS.items():
        out = out.replace(bad, good)
    return out


def _put(page, point, text: str, **kwargs) -> None:
    """The ONLY way this module writes text. Routing every call through here is what makes
    the base-14 transliteration above impossible to bypass."""
    page.insert_text(point, _ascii(text), **kwargs)


def _width(text: str, fontsize: float = _FS_BODY) -> float:
    import fitz

    return fitz.get_text_length(_ascii(text), fontname="helv", fontsize=fontsize)


# --- page builders ---------------------------------------------------------------------


def _review_banner(page, tag: str | None = None) -> None:
    """Opaque top band carrying the review watermark, on EVERY page including drawings.

    A local copy rather than ``assembler._stamp_watermark_banner``: that one's height is
    tuned to bury a drawing SVG's own top-left ``Tag:`` label on a 792x612 crop, which is
    the wrong constraint for a portrait text page.
    """
    import fitz

    width = page.rect.width
    page.draw_rect(
        fitz.Rect(0, 0, width, _BANNER_HEIGHT),
        color=(0.70, 0.70, 0.70),
        fill=(1.0, 1.0, 1.0),
        width=0.5,
    )
    _put(page, (10, _BANNER_BASELINE), REVIEW_WATERMARK, fontsize=_FS_SMALL, color=(0.80, 0, 0))
    tag = (tag or "").strip()
    if not tag:  # an unknown tag stays unstated rather than printing a blank "Tag:"
        return
    label = f"Tag: {tag}"
    length = _width(label, fontsize=9)
    _put(page, (max(10.0, width - length - 10.0), _BANNER_BASELINE), label, fontsize=9)


def _new_page(doc, tag: str | None = None):
    page = doc.new_page(width=_PAGE_W, height=_PAGE_H)
    _review_banner(page, tag)
    return page


def _cover_page(
    doc,
    *,
    project_name: str | None,
    project_number: str | None,
    generated_on: date | None,
    coils: list[dict[str, Any]],
) -> None:
    page = _new_page(doc)
    y = _MARGIN + 20.0
    _put(page, (_MARGIN, y), "AMBIENT DYNAMICS — QUOTE REQUEST", fontsize=_FS_TITLE)
    y += _LINE_H * 2

    rows = [
        ("Project", _text_or_missing(project_name)),
        ("Project number", _text_or_missing(project_number)),
        ("Prepared", generated_on.isoformat() if generated_on else _MISSING),
        ("Coils", str(len(coils))),
        ("Tags", ", ".join(t for t in (c.get("tag") for c in coils) if t) or _MISSING),
    ]
    y = _draw_kv_table(page, rows, top=y)
    y += _LINE_H

    for line in (
        "Every value in this document is transcribed from the customer submittal and is",
        "REVIEW-REQUIRED. Nothing here is calculated, approved, or exported, and no drawing",
        "is released for manufacturing. A field the submittal did not state is left blank",
        f"as “{_MISSING}” — it is never guessed or defaulted.",
    ):
        _put(page, (_MARGIN, y), line, fontsize=_FS_BODY)
        y += _LINE_H

    y += _LINE_H
    _put(page, 
        (_MARGIN, y),
        "export_allowed: false   production_drawing_approval_claimed: false   review_required: true",
        fontsize=_FS_SMALL,
        color=(0.35, 0.35, 0.35),
    )


def _performance_pages(doc, coil: dict[str, Any]) -> None:
    """Draw one coil's performance table, paginating when the rows overflow a page."""
    tag = coil.get("tag") or "Coil"
    page = _new_page(doc, tag)
    y = _MARGIN + 14.0
    _put(page, 
        (_MARGIN, y),
        f"{tag}   {coil.get('category') or ''}".strip(),
        fontsize=_FS_TITLE,
    )
    y += _LINE_H * 2

    band_rows = _acceptance_band_rows(coil.get("acceptance_band"))
    if band_rows:
        _put(page, (_MARGIN, y), "ACCEPTANCE BAND", fontsize=_FS_HEADING)
        y += _LINE_H
        y = _draw_kv_table(page, band_rows, top=y)
        y += _LINE_H

    _put(page, (_MARGIN, y), "PERFORMANCE", fontsize=_FS_HEADING)
    y += _LINE_H

    bottom = _PAGE_H - _MARGIN - (_LINE_H * 3)
    for label, value, unit in _performance_rows(coil):
        if y > bottom:
            page = _new_page(doc, tag)
            y = _MARGIN + 14.0
            _put(page, (_MARGIN, y), f"{tag} (continued)", fontsize=_FS_HEADING)
            y += _LINE_H * 2
        y = _draw_row(page, label, value, unit, y)

    y += _LINE_H
    missing = list(coil.get("missing_fields") or [])
    if missing:
        _put(page, 
            (_MARGIN, y),
            "Missing (not stated in the submittal — not guessed):",
            fontsize=_FS_BODY,
            color=(0.80, 0, 0),
        )
        y += _LINE_H
        for chunk in _wrap(", ".join(missing), 88):
            _put(page, (_MARGIN + 10.0, y), chunk, fontsize=_FS_BODY, color=(0.80, 0, 0))
            y += _LINE_H

    drawing = coil.get("drawing") or {}
    if not drawing.get("svg") and drawing.get("omitted_reason"):
        y += _LINE_H * 0.5
        _put(page, 
            (_MARGIN, y),
            f"Drawing omitted: {drawing['omitted_reason']}",
            fontsize=_FS_BODY,
            color=(0.80, 0, 0),
        )


def _drawing_page(doc, coil: dict[str, Any], warnings: list[str]) -> int | None:
    """Append the coil's drawing as its own page. Returns the 0-based index, or None.

    A drawing that will not convert must cost its own page, never the whole document — so
    the failure is caught, surfaced as a warning, and the quote request still ships.
    """
    drawing = coil.get("drawing") or {}
    svg = drawing.get("svg")
    if not svg:
        return None

    import fitz

    tag = coil.get("tag") or "Coil"
    try:
        pdf_bytes = svg_to_pdf_bytes(svg)
        drawing_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 — any converter failure degrades the same way
        warnings.append(
            f"{tag}: drawing could not be converted to PDF ({exc}) — attach it separately."
        )
        return None

    try:
        first_index = doc.page_count
        doc.insert_pdf(drawing_doc)
        for index in range(first_index, doc.page_count):
            _review_banner(doc[index], tag)
        return first_index
    finally:
        drawing_doc.close()


# --- row/value helpers -----------------------------------------------------------------


def _text_or_missing(value: Any) -> str:
    if value is None:
        return _MISSING
    text = str(value).strip()
    return text or _MISSING


def _value_text(value: Any) -> str:
    """Format a transcribed value, or the em dash when it was never stated.

    ``0`` and ``False`` are real stated values and must survive — only None/""/blank is
    absent. Reuses ``phase2a.renderer._fmt`` so number formatting has one definition.
    """
    if value is None:
        return _MISSING
    if isinstance(value, str):
        return value.strip() or _MISSING
    return _fmt(value)


def _performance_rows(coil: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [
        (
            str(line.get("label") or line.get("key") or ""),
            _value_text(line.get("value")),
            str(line.get("unit") or ""),
        )
        for line in (coil.get("performance_lines") or [])
    ]


def _acceptance_band_rows(band: dict[str, Any] | None) -> list[tuple[str, str]]:
    if not band:
        return []
    rows = [
        ("EKEXVA kit", _text_or_missing(band.get("ekexva_kit"))),
        ("Nominal tons", _value_text(band.get("nominal_tons"))),
        ("Capacity band (MBH)", _range_text(band.get("capacity_band_mbh"))),
        ("Coil volume band (cu in)", _range_text(band.get("coil_volume_band_cuin"))),
        ("Band basis", _text_or_missing(band.get("band_basis"))),
        ("Circuits", _value_text(band.get("circuits"))),
    ]
    if band.get("circuits_assumed"):
        # Surfaced loudly: the band is derived from circuits, and this one was not stated.
        rows.append(("", "! circuits assumed = 1 (not stated in the submittal)"))
    return rows


def _range_text(pair: Any) -> str:
    if not isinstance(pair, (list, tuple)) or len(pair) != 2:
        return _MISSING
    low, high = pair
    if low is None or high is None:
        return _MISSING
    return f"{_fmt(low)} – {_fmt(high)}"


def _draw_row(page, label: str, value: str, unit: str, y: float) -> float:
    _put(page, (_MARGIN, y), _clip(page, label, _LABEL_W), fontsize=_FS_BODY)
    _put(page, (_MARGIN + _LABEL_W, y), _clip(page, value, _VALUE_W), fontsize=_FS_BODY)
    if unit:
        _put(page, (_MARGIN + _LABEL_W + _VALUE_W, y), unit, fontsize=_FS_SMALL, color=(0.35, 0.35, 0.35))
    return y + _LINE_H


def _draw_kv_table(page, rows: list[tuple[str, str]], *, top: float) -> float:
    y = top
    for label, value in rows:
        _put(page, (_MARGIN, y), _clip(page, label, _LABEL_W), fontsize=_FS_BODY)
        _put(page, 
            (_MARGIN + _LABEL_W, y),
            _clip(page, value, _PAGE_W - _MARGIN * 2 - _LABEL_W),
            fontsize=_FS_BODY,
        )
        y += _LINE_H
    return y


def _clip(page, text: str, width: float) -> str:
    """Truncate to fit the column so a long label can never overrun the next one."""
    import fitz

    if _width(text) <= width:
        return text
    clipped = text
    while clipped and _width(clipped + "...") > width:
        clipped = clipped[:-1]
    return clipped + "..."


def _wrap(text: str, width: int) -> list[str]:
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]
