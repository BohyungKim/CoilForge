"""Ambient Dynamics coil-supplier extension (quick-ship quote comparison).

CoilForge's main path is Direct Coil (geometry/drawing-centric). Ambient Dynamics
is an alternate **quick-ship** supplier whose workflow is *performance-data
validation*, not drawing generation: a submittal (Coilmaster EZ-Coil / DirectCoil
selection) is the performance **baseline**, Ambient returns its own performance PDF,
and the engineer compares baseline-vs-Ambient per coil tag to judge acceptability.

This package mirrors the ``checklist`` subsystem's layering:
- ``coil_volume`` — pure port of the Excel internal-volume formula (no I/O).
- ``units`` — Btu/hr <-> MBH normalization.
- ``pdf_intake`` — parse Ambient's returned PDF into ``SubmittalCoilCandidate`` shape.
- ``model`` / ``mapping`` / ``compare`` — pure: baseline + Ambient -> comparison rows.
- ``excel_writer`` — I/O: fill a copy of the comparison workbook (Windows-only).

Every output is a **review aid**: ``export_allowed=False``, every Ambient value is
``review_required`` (a vendor claim), missing inputs are surfaced (``cannot_evaluate``
/ ``missing_one``), never invented. The Direct Coil path is untouched.
"""
from __future__ import annotations
