"""Extract coil data from CoilMaster drawing PDF text + the submittal cover page.

The scanned CoilMaster drawing contains every mechanical value as value-label
callouts ("12 FH"), a model number ("DX-F-S-04-13-12.00x15.00-L" encoding
rows/FPI/FH/FL/hand), connection size, materials, and circuiting. The submittal
cover page carries the unit size token ("A16_V_I_ERV") from which the product
family is derived via the R-076 enumeration.

Operates on extracted PDF *text* (CI-safe; no PDF binary needed here).
"""

from __future__ import annotations

import re
from typing import Any

from coilforge.services.header_prepopulate_engine import load_rule_table

# Drawing dimension callouts. Longest / most-specific labels first; NO boundary
# assertion because each label glues to the next value ("12 FH13.25 CH"). The
# per-pair labels (I1/I3/I5, S1/S3/S5, O2/O4/O6, R2/R4/R6) must all be present so
# multi-header values don't corrupt the base ones.
_DIMENSION_LABELS = (
    "HDx1", "HDx3", "HDx5", "HD2", "HD4", "HD6", "SL2", "SL4", "SL6", "OAL",
    "CH", "CL", "CD", "FH", "FL", "HF", "RF", "TF", "BF", "RB",
    "I1", "I3", "I5", "I7", "S1", "S3", "S5", "S7",
    "O2", "O4", "O6", "O8", "R2", "R4", "R6", "R8",
)
_DIM_RE = re.compile(r"([\d.]+)\s*(" + "|".join(_DIMENSION_LABELS) + r")")
_CIRCUIT_FEED_RE = re.compile(r"C\d+:\s*(\d+)\s*Feed")
_SINGLE_FEED_RE = re.compile(r"([\d.]+)\s*Feed\s*/\s*(\d+)\s*Pass")
_PASS_PER_FEED_RE = re.compile(r"(\d+)\s*Pass(?:es)?\s*per\s*Feed")
_MODEL_RE = re.compile(
    r"([A-Z]{2,})-[A-Z]-[A-Z]-(\d+)-(\d+)-([\d.]+)x([\d.]+)-([LR])"
)
_FPI_RE = re.compile(r"(\d+)\s*Fins Per Inch")
_CONN_RE = re.compile(r"RETURN CONN SIZE\s*([\d./]+)\"")
_TAG_RE = re.compile(r"Tag:\s*([A-Za-z0-9-]+)")
# Cover-page unit-size token: A16_V_I_..., V20_..., H10_...
_SIZE_RE = re.compile(r"\b([A-C]\d{2}|V\d{2,3}|H\d{2})_[A-Z]_")


def extract_drawing_dimensions(text: str) -> dict[str, float]:
    """Return {label: value} for the drawing dimension callouts (first wins)."""
    dims: dict[str, float] = {}
    for value, label in _DIM_RE.findall(text):
        try:
            number = float(value)
        except ValueError:
            continue  # e.g. a lone "." callout (seen on HG drawings); not a value
        dims.setdefault(label, number)  # first occurrence = top callout
    return dims


def parse_model_number(text: str) -> dict[str, Any]:
    """Parse 'DX-F-S-04-13-12.00x15.00-L' -> coil/rows/fpi/FH/FL/hand."""
    m = _MODEL_RE.search(text)
    if not m:
        return {}
    return {
        "coil_code": m.group(1),
        "rows": int(m.group(2)),
        "fpi": int(m.group(3)),
        "fh": float(m.group(4)),
        "fl": float(m.group(5)),
        "hand": "LH" if m.group(6) == "L" else "RH",
    }


def extract_feeds_circuits(text: str, rb: float | None = None) -> dict[str, Any]:
    """Total feeds + circuit count from either feed format.

    Multi-circuit: 'C1: 3 Feed C2: 4 Feed' -> feeds=7, circuits=2.
    Single: '2 Feed / 24 Pass' (glued to RB as '1.752 Feed') -> feeds=2, circuits=1.
    """
    out: dict[str, Any] = {}
    per_circuit = _CIRCUIT_FEED_RE.findall(text)
    if per_circuit:
        out["circuits"] = len(per_circuit)
        out["feeds"] = sum(int(c) for c in per_circuit)
        if (m := _PASS_PER_FEED_RE.search(text)):
            out["passes_per_feed"] = int(m.group(1))
        return out
    if (m := _SINGLE_FEED_RE.search(text)):
        out["circuits"] = 1
        out["passes"] = int(m.group(2))
        glued = m.group(1)  # may be RB glued to feeds, e.g. "1.752"
        feeds: int | None = None
        if rb is not None:
            rb_str = f"{rb:g}"
            if glued.startswith(rb_str) and len(glued) > len(rb_str):
                feeds = int(glued[len(rb_str):])
        if feeds is None:
            try:
                feeds = int(float(glued))
            except ValueError:
                feeds = None
        if feeds is not None:
            out["feeds"] = feeds
    return out


def extract_coilmaster_drawing(text: str) -> dict[str, Any]:
    """Full mechanical extraction from a CoilMaster drawing PDF's text."""
    out: dict[str, Any] = {"dimensions": extract_drawing_dimensions(text)}
    out.update(parse_model_number(text))
    if (m := _MODEL_RE.search(text)):
        out["model_number"] = m.group(0)
    out.update(extract_feeds_circuits(text, out["dimensions"].get("RB")))
    if (m := _FPI_RE.search(text)) and "fpi" not in out:
        out["fpi"] = int(m.group(1))
    if (m := _CONN_RE.search(text)):
        out["return_conn_size"] = m.group(1)
    if (m := _TAG_RE.search(text)):
        out["tag"] = m.group(1)
    return out


def extract_unit_size(cover_text: str) -> str | None:
    """Unit size token from the submittal cover page (e.g. 'A16')."""
    m = _SIZE_RE.search(cover_text)
    return m.group(1) if m else None


def product_for_unit_size(unit_size: str | None) -> str | None:
    """Product family whose R-076 enumeration contains the unit size."""
    if unit_size is None:
        return None
    enumerations = next(
        r for r in load_rule_table() if r["rule_id"] == "R-076"
    )["enumerations"]
    for product, sizes in enumerations.items():
        if unit_size in sizes:
            return product
    return None
