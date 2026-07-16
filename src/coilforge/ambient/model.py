"""Pure data model for an Ambient-vs-baseline coil comparison (no I/O).

Mirrors ``checklist.model``'s frozen-dataclass style. One ``CompareRow`` per compared
attribute, ``CoilCompare`` per coil tag, ``AmbientComparison`` per project. Every object
carries the review-aid safety contract (``export_allowed=False``); the web layer and the
Excel writer both consume this same structure.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# match: agree within tolerance · mismatch: disagree · missing_one / both_missing: a
# side is absent · cannot_evaluate: no acceptance rule yet (e.g. range band pending).
Verdict = Literal["match", "mismatch", "missing_one", "both_missing", "cannot_evaluate"]


@dataclass(frozen=True)
class CompareRow:
    """One attribute compared: baseline (Coilmaster/submittal) vs Ambient."""

    label: str
    group: str  # geometry | airside_conditions | performance | ...
    key: str
    baseline: Any
    ambient: Any
    unit: str | None
    verdict: Verdict
    tolerance: str  # provenance of the band used (e.g. "rel 2%", "exact", "Allowable Ranges")
    note: str | None = None


@dataclass(frozen=True)
class CoilCompare:
    """All comparison rows for one coil tag (or a loud not-compared placeholder)."""

    tag: str
    category: str | None
    rows: tuple[CompareRow, ...] = ()
    not_compared_reason: str | None = None  # set when a coil is on only one side

    @property
    def mismatch_count(self) -> int:
        return sum(1 for r in self.rows if r.verdict == "mismatch")

    @property
    def cannot_evaluate_count(self) -> int:
        return sum(1 for r in self.rows if r.verdict == "cannot_evaluate")


@dataclass(frozen=True)
class AmbientComparison:
    """Project-level Ambient-vs-baseline comparison — a review aid, never an export."""

    coils: tuple[CoilCompare, ...] = ()
    warnings: tuple[str, ...] = ()
    # Safety contract — mirrors every other CoilForge result payload.
    export_allowed: bool = False
    production_drawing_approval_claimed: bool = False
    review_required: bool = True

    @property
    def mismatch_total(self) -> int:
        return sum(c.mismatch_count for c in self.coils)

    @property
    def not_compared(self) -> tuple[str, ...]:
        return tuple(c.tag for c in self.coils if c.not_compared_reason)

    def as_dict(self) -> dict[str, Any]:
        """JSON-friendly payload for the web layer (dataclasses.asdict + summary)."""
        return {
            "coils": [
                {
                    **asdict(c),
                    "rows": [asdict(r) for r in c.rows],
                    "mismatch_count": c.mismatch_count,
                    "cannot_evaluate_count": c.cannot_evaluate_count,
                }
                for c in self.coils
            ],
            "warnings": list(self.warnings),
            "mismatch_total": self.mismatch_total,
            "not_compared": list(self.not_compared),
            "export_allowed": self.export_allowed,
            "production_drawing_approval_claimed": self.production_drawing_approval_claimed,
            "review_required": self.review_required,
        }
