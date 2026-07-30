"""Pure data model for a Coil Checklist fill (no I/O, no Excel).

A ``ChecklistFill`` fully describes what the writer should do to a copy of the
template: which category sheets to keep/remove, what to rename each to, and the
column-C value (with provenance) for every managed field. The Excel writer and the
in-app comparison both consume this same structure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CellKind = Literal["text", "number", "bool", "dropdown"]
CellStatus = Literal["ready", "review_required", "blocked", "constant", "detected"]


@dataclass(frozen=True)
class OverrideNote:
    """A value the engineer manually corrected in the browser, carried into the checklist.

    ``previous_value`` is what CoilForge proposed BEFORE the override (the machine
    proposal), so the filled sheet and the review table can both state what was
    replaced instead of silently showing the new number.
    """

    key: str  # the manual-fill key: an engine input ("rows") or a drawing param ("TF")
    previous_value: Any = None
    reason: str | None = None


@dataclass(frozen=True)
class CellFill:
    """One column-C cell to write (or leave blank when ``value is None``)."""

    label: str  # canonical column-B label, e.g. "FH", "SUCTION CONN SZ", "I1"
    value: Any  # value for column C; None => leave the cell blank
    kind: CellKind
    status: CellStatus
    source: str  # short provenance: "submittal:finned_height" | "engine:slot.CD" | "constant" | "detected"
    drawing_slot: str | None = None  # the slot it mirrors (for the compare view)
    note: str | None = None  # why blank / why review-required
    override: OverrideNote | None = None  # set when a manual fill supplied this value


@dataclass(frozen=True)
class DimCompare:
    """A dimension the checklist computes by formula and CoilForge computes by engine.

    Only the input cells are written; the sheet's formulas then compute this dim.
    After the write, the checklist's computed value is read back and compared to
    ``coilforge_value`` to surface divergence between the two implementations.
    """

    label: str  # the dim's column-B label, e.g. "CD", "S1", "OAL"
    slot: str  # the CoilForge slot it mirrors, e.g. "slot.CD"
    coilforge_value: Any  # CoilForge's engine value (or "N/A" beyond circuit count, or None)
    # Set when the engineer manually overrode this dimension (Tier B). ``coilforge_value``
    # is then the override — the value actually drawn — and ``override.previous_value`` is
    # the engine's proposal. The WRITER overwrites this formula cell with the override
    # AFTER reading the formula's own result back, so the cross-check survives (compare.py
    # reports it as verdict ``overridden``, never as a match).
    override: OverrideNote | None = None


@dataclass(frozen=True)
class SheetFill:
    """One coil -> one checklist sheet (a clone of ``source_sheet`` renamed to ``sheet_tag``)."""

    category: str  # DX | HGRH | HWC | CWC
    source_sheet: str  # the template sheet to base this on (== category sheet name)
    sheet_tag: str  # final sheet name / coil tag, e.g. "CDXC-1"
    cells: tuple[CellFill, ...] = ()  # INPUT cells written to column C
    compare_dims: tuple[DimCompare, ...] = ()  # formula-computed dims to read back & compare


@dataclass(frozen=True)
class ChecklistFill:
    """Everything the writer needs to fill one workbook copy for a submittal."""

    sheets: tuple[SheetFill, ...] = ()
    remove_sheets: tuple[str, ...] = ()  # category sheets with no coil -> delete
    warnings: tuple[str, ...] = ()  # global review flags (missing UNIT, unknown app, ...)
    # Safety contract — a review aid, never a production artifact.
    export_allowed: bool = False
    production_drawing_approval_claimed: bool = False

    @property
    def keep_sheets(self) -> tuple[str, ...]:
        """Distinct source sheets that survive (the rest of the category sheets are removed)."""
        seen: list[str] = []
        for s in self.sheets:
            if s.source_sheet not in seen:
                seen.append(s.source_sheet)
        return tuple(seen)
