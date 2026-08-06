"""Compare CoilForge drawing-parameter values against values read back from the
external CCSI Direct Coil form, so a divergence is flagged loudly (red) before the
engineer saves the CCSI record.

Pure. The numeric-agreement logic (tolerance 0.01") is **reused verbatim** from the
checklist comparator (`checklist/compare.py`) so CoilForge has ONE source of truth for
"do two independent sources agree" — the CCSI review surface can never drift from the
checklist one. Review aid only; this module never writes to CCSI and never approves.
"""
from __future__ import annotations

from typing import Any

from coilforge.checklist.compare import _match

# Verdict vocabulary is exactly the checklist comparator's:
#   match / mismatch / missing_one / both_missing


def compare_ccsi_fields(fields: list[dict[str, Any]]) -> dict[str, Any]:
    """Given ``[{key, coilforge, ccsi}, ...]``, return per-field verdicts + a summary.

    ``coilforge`` is the engine/panel value; ``ccsi`` is the value read back from the
    CCSI form (often a DOM string — ``_match`` coerces numerics, so "7.500" == 7.5).
    Numbers agree within 0.01"; a value present on only one side is flagged
    ``missing_one`` rather than guessed. Never an export approval.
    """
    rows: list[dict[str, Any]] = []
    mismatch_count = 0
    for field in fields or []:
        key = str(field.get("key", ""))
        coilforge = field.get("coilforge")
        ccsi = field.get("ccsi")
        verdict = _match(coilforge, ccsi)
        if verdict == "mismatch":
            mismatch_count += 1
        rows.append(
            {"key": key, "coilforge": coilforge, "ccsi": ccsi, "verdict": verdict}
        )
    return {
        "fields": rows,
        "compared": len(rows),
        "mismatch_count": mismatch_count,
        "review_aid_only": True,
        "export_allowed": False,
        "production_drawing_approval_claimed": False,
    }
