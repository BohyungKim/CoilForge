"""Small cross-cutting helpers shared by otherwise independent CoilForge packages.

Nothing engineering-specific lives here — a module belongs in ``common`` only when
two packages that must not import each other both need it (e.g. ``checklist`` and
``ambient`` both driving Excel COM).
"""
