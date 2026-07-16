"""Build the in-app review table: checklist (formula) vs CoilForge (engine).

Pure (no Excel). Consumes the ``ChecklistFill`` and the writer's result (which
carries each sheet's formula-computed dim values, read back after recalc) and
produces a JSON-friendly structure the web UI renders: per sheet, the written
input cells and a dim-by-dim comparison flagged match / mismatch / missing.
"""
from __future__ import annotations

from typing import Any

from coilforge.checklist.model import ChecklistFill

_TOL = 0.01  # inches — numeric agreement tolerance


def _norm(v: Any) -> Any:
    if isinstance(v, str):
        s = v.strip()
        if s.upper() in ("N/A", ""):
            return None if s == "" else "N/A"
        try:
            return float(s)
        except ValueError:
            return s.upper()
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    return v


def _match(coilforge: Any, checklist: Any, *, tol: float = _TOL, rel_tol: float | None = None) -> str:
    """Compare two values -> match / mismatch / missing_one / both_missing.

    ``tol`` is the absolute numeric tolerance (default ``_TOL`` = 0.01 in, the
    dimensional agreement the checklist/ccsi callers rely on — they pass no kwargs, so
    their behavior is unchanged). ``rel_tol``, when given, adds a relative band for
    performance quantities (capacity, GPM, ...) whose absolute magnitude makes a fixed
    0.01 tolerance meaningless: agreement = ``abs(a-b) <= max(tol, rel_tol*max(|a|,|b|))``.
    """
    a, b = _norm(coilforge), _norm(checklist)
    if a is None and b is None:
        return "both_missing"
    if a is None or b is None:
        return "missing_one"
    if isinstance(a, float) and isinstance(b, float):
        threshold = tol if rel_tol is None else max(tol, rel_tol * max(abs(a), abs(b)))
        return "match" if abs(a - b) <= threshold else "mismatch"
    return "match" if a == b else "mismatch"


def build_review(fill: ChecklistFill, writer_result: dict[str, Any]) -> dict[str, Any]:
    """Combine the fill + writer read-back into the review payload for the UI."""
    computed_by_tag = {
        s.get("tag"): s.get("computed_dims", {}) for s in writer_result.get("sheets", [])
    }
    sheets_out: list[dict[str, Any]] = []
    mismatch_total = 0
    for sheet in fill.sheets:
        inputs = [
            {
                "label": c.label,
                "value": c.value,
                "status": c.status,
                "source": c.source,
                "note": c.note,
            }
            for c in sheet.cells
        ]
        computed = computed_by_tag.get(sheet.sheet_tag, {})
        comparisons: list[dict[str, Any]] = []
        for dim in sheet.compare_dims:
            cf = dim.coilforge_value
            cl = computed.get(dim.label)
            verdict = _match(cf, cl)
            if verdict == "mismatch":
                mismatch_total += 1
            comparisons.append(
                {
                    "label": dim.label,
                    "slot": dim.slot,
                    "coilforge": cf,
                    "checklist": cl,
                    "verdict": verdict,
                }
            )
        sheets_out.append(
            {
                "tag": sheet.sheet_tag,
                "category": sheet.category,
                "inputs": inputs,
                "comparisons": comparisons,
                "mismatch_count": sum(1 for c in comparisons if c["verdict"] == "mismatch"),
            }
        )
    return {
        "saved_path": writer_result.get("saved_path"),
        "sheets": sheets_out,
        "warnings": list(fill.warnings),
        "skipped_labels": writer_result.get("skipped_labels", []),
        "removed_sheets": writer_result.get("removed", []),
        "mismatch_total": mismatch_total,
        # Review aid — never a production artifact.
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
    }
