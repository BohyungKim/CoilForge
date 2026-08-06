"""Outgoing drawing-package assembly (quote-prep review aid).

Composes the outgoing package the engineer hands to purchasing / Direct Coil:
the Direct Coil drawing PDF with CoilForge's own drawing appended right after
it, marked up with the copper-strap requirement and any uncertain mappings.

This package is a *print/compose* layer, NOT a geometry renderer backend. It
consumes already-rendered presentation (an SVG string + a PDF byte stream) and
emits a combined PDF. It computes no geometry and never flips ``export_allowed``
or claims production approval — output stays a watermarked review aid.
"""

from __future__ import annotations

from coilforge.package.assembler import PackageResult, assemble_drawing_package
from coilforge.package.svg_to_pdf import svg_to_pdf_bytes

__all__ = ["PackageResult", "assemble_drawing_package", "svg_to_pdf_bytes"]
