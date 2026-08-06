"""SVG -> PDF print/compose utility (NOT a geometry renderer backend).

Pure presentation conversion: an already-rendered SVG string (from the
parametric engine OR a seeded CoilMaster template) becomes single-page PDF
bytes. It computes no geometry and consumes no geometry model, so it does not
participate in the model -> layout -> backend pipeline and leaves the
three-layer invariant untouched. It exists only to place a finished drawing
onto a PDF page for the outgoing review-aid package.

Uses PyMuPDF (``fitz``), already a runtime dependency of ``submittal/pdf_intake.py``.
``fitz`` is imported lazily (same defensive pattern as pdf_intake) so importing
this module never hard-fails in a ``fitz``-less environment.
"""

from __future__ import annotations


def svg_to_pdf_bytes(svg: str) -> bytes:
    """Render an SVG string to a single-page PDF and return its bytes.

    Raises ``ValueError`` on empty input. Never writes to disk.
    """
    if not svg or not svg.strip():
        raise ValueError("svg_to_pdf_bytes: SVG content is empty")

    import fitz  # PyMuPDF — lazy import (see submittal/pdf_intake.py)

    svg_doc = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
    try:
        return svg_doc.convert_to_pdf()
    finally:
        svg_doc.close()
