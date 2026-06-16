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


def _r076_enumerations() -> dict[str, list[str]]:
    return next(r for r in load_rule_table() if r["rule_id"] == "R-076")["enumerations"]


def product_for_unit_size(unit_size: str | None) -> str | None:
    """Product family whose R-076 enumeration contains the unit size."""
    if unit_size is None:
        return None
    for product, sizes in _r076_enumerations().items():
        if unit_size in sizes:
            return product
    return None


# Picker product-line labels. TERRA is split into H / V orientation categories
# (John 2026-06-15): the engineer picks the Terra orientation, which drives the
# engine's terra_variant ("TERRA H" -> resolved Terra H C; "TERRA V" -> Terra V).
TERRA_H_LABEL = "TERRA H"
TERRA_V_LABEL = "TERRA V"

# Picker label -> (engine product_family, terra_variant or None). Only Terra is
# special-cased; every other product line maps to itself with no variant.
_PRODUCT_LINE_RESOLUTION: dict[str, tuple[str, str | None]] = {
    TERRA_H_LABEL: ("TERRA", "TERRA_H_C"),
    TERRA_V_LABEL: ("TERRA", "TERRA_V"),
    "TERRA": ("TERRA", "TERRA_H_C"),  # bare Terra defaults to the resolved H C set
}


def resolve_product_line(label: str | None) -> tuple[str | None, str | None]:
    """Resolve a picker product-line label to (engine product_family, terra_variant).

    "TERRA H"/"TERRA V" carry the Terra orientation the engineer chose; every
    other label (NOVA, VENTUM_H, VENTUM_PLUS) maps to itself with no variant.
    """
    if label is None:
        return None, None
    return _PRODUCT_LINE_RESOLUTION.get(label.strip().upper(), (label, None))


def product_size_options() -> dict[str, list[str]]:
    """{product_line: [unit sizes]} from R-076 — the valid choices an engineer
    can pick to unlock the rule-engine dimensions for a submittal coil.

    TERRA is presented as two orientation categories (TERRA H / TERRA V); both
    share the R-076 Terra size set (zero-padded, e.g. 009)."""
    options: dict[str, list[str]] = {}
    for product, sizes in _r076_enumerations().items():
        if product == "TERRA":
            options[TERRA_H_LABEL] = list(sizes)
            options[TERRA_V_LABEL] = list(sizes)
        else:
            options[product] = list(sizes)
    return options


# Terra model code on a submittal schedule, e.g. "TR_C_009" / "TR-C-009" / "TR C 9".
# The C/V token carries the orientation (C -> TERRA H, V -> TERRA V); the trailing
# digits are the (zero-padded) Terra unit size.
_TERRA_MODEL_RE = re.compile(r"\bTR[_\- ]?([CV])[_\- ]?0*(\d{1,3})\b", re.IGNORECASE)


def _non_terra_size_tokens() -> list[str]:
    """Every R-076 unit-size token outside TERRA (whose sizes are bare digits and
    must only be matched via the explicit TR_* model code, never a loose digit
    search). Longest first so e.g. 'V100' wins over a hypothetical 'V10'."""
    tokens: list[str] = []
    for product, sizes in _r076_enumerations().items():
        if product == "TERRA":
            continue
        tokens.extend(sizes)
    return sorted(set(tokens), key=len, reverse=True)


def detect_product_and_size(text: str | None) -> tuple[str | None, str | None]:
    """Deterministically detect (picker product-line label, R-076 unit size) from a
    submittal's model code — without needing the brand word.

    Model-code driven and validated against the R-076 table (the single source of
    truth), so it never invents a value:
        TR_C_009 -> ("TERRA H", "009");  TR_V_012 -> ("TERRA V", "012")
        A16 / B20 / C24 ... -> ("NOVA", token)
        H05 ... H30        -> ("VENTUM_H", token)
        V20 ... V150       -> ("VENTUM_PLUS", token)

    Returns (None, None) when nothing validates. The explicit Terra model code wins
    over a loose size token if both appear.
    """
    if not text:
        return None, None
    upper = text.upper()

    # 1. Terra model code (orientation from the C/V token).
    match = _TERRA_MODEL_RE.search(upper)
    if match:
        label = TERRA_H_LABEL if match.group(1).upper() == "C" else TERRA_V_LABEL
        size = f"{int(match.group(2)):03d}"
        if size in set(product_size_options().get(label, [])):
            return label, size

    # 2. NOVA / VENTUM: any enumerated non-Terra size token as a whole word.
    for token in _non_terra_size_tokens():
        if re.search(rf"\b{re.escape(token)}\b", upper):
            product = product_for_unit_size(token)
            if product:  # NOVA / VENTUM_H / VENTUM_PLUS
                return product, token
    return None, None
