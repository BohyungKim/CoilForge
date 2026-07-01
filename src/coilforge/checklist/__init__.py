"""Coil Checklist auto-fill subsystem (review aid).

Projects CoilForge's already-resolved per-coil values (the same engine path
``compatibility/mechanical_fit.build_coil_fit`` uses) into Oxygen8's "Coil
Checklist Template.xlsx" so the engineer no longer hand-types column C. The fill
is a **review aid**: missing/blocked values are left blank and surfaced, never
guessed; the original template is never modified (a copy is written to Downloads).

Layers (kept separate):
- ``template_map`` — pure structural reference of the workbook (sheet names,
  fillable labels, dropdown vocabularies, checkbox defaults). No Excel dependency.
- ``model`` / ``mapping`` — pure: canonical coils -> ``ChecklistFill``.
- ``excel_writer`` — I/O: Excel COM writes the filled copy (Windows-only).
- ``compare`` — the in-app review table (value + evidence + cell + drawing slot).
"""
from __future__ import annotations
