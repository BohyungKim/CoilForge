"""Build the in-app review table: checklist (formula) vs CoilForge (engine).

Pure (no Excel). Consumes the ``ChecklistFill`` and the writer's result (which
carries each sheet's formula-computed dim values, read back after recalc) and
produces a JSON-friendly structure the web UI renders: per sheet, the written
input cells and a dim-by-dim comparison flagged match / mismatch / missing.
"""
from __future__ import annotations

from typing import Any

from coilforge.checklist.model import ChecklistFill, OverrideNote
from coilforge.checklist.overrides import is_adopted_reason

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


def _from_header_end(value: Any, datum: str | None, ch: Any) -> Any:
    """A water O re-expressed from the header end: ``CH - O`` when measured from the
    opposite end, unchanged otherwise. ``None`` when that needs a CH nobody resolved --
    an honest ``missing_one`` beats a mismatch between two datums."""
    if datum != "opposite":
        return value
    o, c = _norm(value), _norm(ch)
    if isinstance(o, float) and isinstance(c, float):
        return round(c - o, 4)
    return None


def _override_payload(note: OverrideNote | None) -> dict[str, Any] | None:
    """JSON view of a manual override (or None) — what it replaced and why."""
    if note is None:
        return None
    return {"key": note.key, "previous_value": note.previous_value, "reason": note.reason}


def build_review(fill: ChecklistFill, writer_result: dict[str, Any]) -> dict[str, Any]:
    """Combine the fill + writer read-back into the review payload for the UI."""
    computed_by_tag = {
        s.get("tag"): s.get("computed_dims", {}) for s in writer_result.get("sheets", [])
    }
    sheets_out: list[dict[str, Any]] = []
    mismatch_total = 0
    override_total = 0
    adopted_total = 0
    for sheet in fill.sheets:
        inputs = [
            {
                "label": c.label,
                "value": c.value,
                "status": c.status,
                "source": c.source,
                "note": c.note,
                "override": _override_payload(c.override),
            }
            for c in sheet.cells
        ]
        override_total += sum(1 for c in sheet.cells if c.override is not None)
        computed = computed_by_tag.get(sheet.sheet_tag, {})
        ch_dim = next((d for d in sheet.compare_dims if d.label == "CH"), None)
        comparisons: list[dict[str, Any]] = []
        for dim in sheet.compare_dims:
            cf = dim.coilforge_value
            cl = computed.get(dim.label)
            # Water O: both sides on the header-end datum before matching (2026-09-23).
            # Each side is converted with the CH it was computed from -- the sheet's O
            # recalculates after a CH override, so it then stands on the override.
            compared: dict[str, Any] | None = None
            if "opposite" in (dim.coilforge_datum, dim.sheet_datum):
                sheet_ch = (
                    ch_dim.coilforge_value
                    if ch_dim is not None and ch_dim.override is not None
                    else computed.get("CH")
                )
                cf_ch = ch_dim.coilforge_value if ch_dim is not None else None
                cl_header = _from_header_end(cl, dim.sheet_datum, sheet_ch)
                compared = {
                    "coilforge": _from_header_end(cf, dim.coilforge_datum, cf_ch),
                    "checklist": cl_header,
                    "coilforge_datum": dim.coilforge_datum,
                    "checklist_datum": dim.sheet_datum,
                    # The sheet's O in the DRAWING's datum -- what "use checklist" may copy
                    # onto a blank O (the raw value would land on the wrong dimension line).
                    "checklist_as_drawn": (
                        cl if dim.sheet_datum == dim.coilforge_datum
                        else _from_header_end(cl_header, dim.coilforge_datum, cf_ch)
                    ),
                }
            if dim.override is not None and is_adopted_reason(dim.override.reason):
                # Adopted FROM the sheet onto a blank CoilForge row: the drawn value is a
                # copy of `cl`, so agreement is not evidence and disagreement is not a
                # defect. Neither a match, nor a mismatch, nor a human correction.
                verdict = "adopted"
                adopted_total += 1
            elif dim.override is not None:
                # The writer replaced this formula with the override AFTER reading the
                # formula's own result, so `computed` still holds what the sheet derived
                # on its own. Keep showing it: "the sheet says 0.875, we are using 1.25"
                # is the review signal — collapsing it to a match would hide the
                # divergence the override was made to resolve.
                verdict = "overridden"
                override_total += 1
            elif compared is not None:
                verdict = _match(compared["coilforge"], compared["checklist"])
                if verdict == "mismatch":
                    mismatch_total += 1
            else:
                verdict = _match(cf, cl)
                if verdict == "mismatch":
                    mismatch_total += 1
            row = {
                "label": dim.label,
                "slot": dim.slot,
                "coilforge": cf,
                "checklist": cl,
                "verdict": verdict,
                "override": _override_payload(dim.override),
            }
            if compared is not None:
                # `coilforge`/`checklist` stay the RAW values (the ledger and the
                # divergence delta read them); the header-end pair is what was matched.
                row["compared_from_header_end"] = compared
            comparisons.append(row)
        sheets_out.append(
            {
                "tag": sheet.sheet_tag,
                "category": sheet.category,
                "inputs": inputs,
                "comparisons": comparisons,
                "mismatch_count": sum(1 for c in comparisons if c["verdict"] == "mismatch"),
                "override_count": sum(1 for c in comparisons if c["verdict"] == "overridden"),
                "adopted_count": sum(1 for c in comparisons if c["verdict"] == "adopted"),
            }
        )
    return {
        "saved_path": writer_result.get("saved_path"),
        "sheets": sheets_out,
        "warnings": list(fill.warnings),
        "skipped_labels": writer_result.get("skipped_labels", []),
        "removed_sheets": writer_result.get("removed", []),
        "mismatch_total": mismatch_total,
        # Manual fills carried in from the browser (Tier-A cells + Tier-B dims). An
        # override is NOT a mismatch — it is a human decision, counted separately.
        "override_total": override_total,
        # Blank rows filled from the sheet's own formula result (review aid, never approval).
        "adopted_total": adopted_total,
        # Review aid — never a production artifact.
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
    }
