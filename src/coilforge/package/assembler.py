"""Assemble the outgoing drawing package (quote-prep review aid).

``assemble_drawing_package`` takes the Direct Coil drawing PDF and CoilForge's
own drawing SVG, appends our drawing *after* the Direct Coil pages, and stamps:

* the copper-strap requirement (computed upstream from header count x coil type),
* any uncertain-mapping callouts (review-required / mismatch slots),
* a review-aid watermark.

Pure function over bytes — no disk writes. Safety flags are hard-wired off:
the package is a watermarked review aid, never a production-approved export.
"""

from __future__ import annotations

import base64

from pydantic import BaseModel, ConfigDict, Field

from coilforge.package.svg_to_pdf import svg_to_pdf_bytes

# Same wording as phase2a/renderer.py + template_population/slot_population.py.
REVIEW_WATERMARK = "REVIEW AID - NOT FOR MANUFACTURING"


class PackageResult(BaseModel):
    """Combined-package outcome. ``pdf_base64`` is the merged PDF, base64-encoded."""

    model_config = ConfigDict(extra="forbid")

    pdf_base64: str
    page_count: int
    direct_coil_page_count: int
    coilforge_page_index: int  # 0-based index of the first appended CoilForge page
    copper_strap_note: str
    review_markups: list[str] = Field(default_factory=list)
    watermarked: bool = True
    # Safety contract — never relaxed by this layer.
    export_allowed: bool = False
    production_drawing_approval_claimed: bool = False
    raw_private_data_returned: bool = False


def _stamp_pages(doc, copper_strap_note: str, review_markups: list[str], watermark: bool) -> None:
    """Stamp the copper-strap banner, markups, and watermark on every page of ``doc``.

    Stamps sit inside an opaque banner (like a drawing's revision band) so they
    stay legible regardless of the underlying drawing geometry.
    """
    import fitz

    lines: list[tuple[str, float, tuple[float, float, float]]] = []
    if watermark:
        lines.append((REVIEW_WATERMARK, 9, (0.80, 0.0, 0.0)))
    lines.append((copper_strap_note, 11, (0.0, 0.0, 0.55)))
    for line in review_markups:
        lines.append((f"! {line}", 8, (0.60, 0.30, 0.0)))

    pad = 8.0
    band_height = pad + sum(size + 5 for _, size, _ in lines)
    for page in doc:
        width = page.rect.width
        page.draw_rect(
            fitz.Rect(0, 0, width, band_height),
            color=(0.70, 0.70, 0.70),
            fill=(1.0, 1.0, 1.0),
            width=0.6,
        )
        y = pad + 6
        for text, size, color in lines:
            page.insert_text((12, y), text, fontsize=size, color=color)
            y += size + 5


def assemble_drawing_package(
    *,
    direct_coil_pdf: bytes,
    coilforge_drawing_svg: str,
    copper_strap_note: str,
    review_markups: list[str] | None = None,
    watermark: bool = True,
) -> PackageResult:
    """Merge ``[Direct Coil pages] + [CoilForge drawing page]`` into one PDF.

    Raises ``ValueError`` if either input cannot be parsed.
    """
    if not direct_coil_pdf:
        raise ValueError("assemble_drawing_package: direct_coil_pdf is empty")
    markups = list(review_markups or [])

    import fitz  # PyMuPDF — lazy import (see submittal/pdf_intake.py)

    our_pdf_bytes = svg_to_pdf_bytes(coilforge_drawing_svg)

    try:
        dc_doc = fitz.open(stream=direct_coil_pdf, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 — surface a clean contract error
        raise ValueError(f"assemble_drawing_package: unreadable Direct Coil PDF ({exc})") from exc

    our_doc = fitz.open(stream=our_pdf_bytes, filetype="pdf")
    out = fitz.open()
    try:
        # Stamp ONLY our appended page(s) — never annotate the third-party
        # Direct Coil drawing, which is passed through unmodified.
        _stamp_pages(our_doc, copper_strap_note, markups, watermark)
        out.insert_pdf(dc_doc)  # Direct Coil drawing first ...
        dc_page_count = dc_doc.page_count
        out.insert_pdf(our_doc)  # ... CoilForge drawing appended right after.
        combined = out.tobytes()
        page_count = out.page_count
    finally:
        out.close()
        our_doc.close()
        dc_doc.close()

    return PackageResult(
        pdf_base64=base64.b64encode(combined).decode("ascii"),
        page_count=page_count,
        direct_coil_page_count=dc_page_count,
        coilforge_page_index=dc_page_count,
        copper_strap_note=copper_strap_note,
        review_markups=markups,
        watermarked=watermark,
    )
