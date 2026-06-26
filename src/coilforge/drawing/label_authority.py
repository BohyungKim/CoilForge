"""Direct Coil label authority for drawing dimension callouts.

The review-aid drawing is built from EZ-coil-seeded CoilMaster templates. Its blue
(``#1c0a80``) dimension callouts carry labels in two flavours:

* **slot-driven** (``{{slot.I1}} I1``): the label already equals the Direct Coil slot
  name, so it needs no change;
* **literal EZ residue** (``2.31 I``, ``3.50 HD1``, ``8.00 SL1``): a hardcoded EZ value +
  EZ label baked into the frozen ``template.svg`` (the deferred 2026-06-22 un-redacted
  dims). On CWC/HWC every connection dim is this kind.

John 2026-06-26: the drawing's LABELS should read in Direct Coil terms (the parameter
panel), not EZ terms. This module is the single authority that maps a baked callout label
to its Direct Coil label, applied at render time so the frozen templates are never touched.

Scope is **labels only — never values**. The EZ *numbers* on the literal callouts stay
until those templates are re-seeded.
"""

from __future__ import annotations

import re

from coilforge.interfaces.direct_coil.fields import DRAWING_PARAMETER_FIELD_KEYS

# The only text-changing entries. The literal EZ-residue labels normalise to the Direct
# Coil parity-indexed convention (supply header = odd index, return = even index, per
# services/direct_coil_drawing_pipeline.build_drawing_slots). These bare/EZ forms appear
# ONLY as residue — there is no slot-driven I/S/O/R/HD1/SL1 callout in any template — so the
# mapping is unambiguous: a lone connection inlet/spacing belongs to the supply header (1);
# the lone outlet/return/HD/SL belongs to the return header (2).
_EZ_NORMALIZE: dict[str, str] = {
    "I": "I1",
    "S": "S1",
    "O": "O2",
    "R": "R2",
    "HD1": "HD2",
    "SL1": "SL2",
}

# Legitimate drawing-only labels that are not in the 13-key Drawing-Parameters panel set
# but ARE real Direct Coil drawing labels (geometry / derived). Listed so the authority
# recognises them as canonical rather than "unknown".
_GEOMETRY_LABEL_BASES: frozenset[str] = frozenset(
    {"FH", "FL", "CH", "CL", "OAL", "RB", "X", "HDx"}
)

# Canonical Direct Coil label bases the authority blesses as-is. Derived from the Direct
# Coil parameter registry (single source of truth) plus the geometry/derived labels, so a
# future rename in interfaces/direct_coil/fields.py flows through here.
CANONICAL_LABEL_BASES: frozenset[str] = (
    frozenset(DRAWING_PARAMETER_FIELD_KEYS) | _GEOMETRY_LABEL_BASES
)

_BASE_SUFFIX_RE = re.compile(r"^([A-Za-z]+?)(\d*)$")


def label_base(label: str) -> str:
    """Return a callout label's alphabetic base, dropping a trailing numeric index.

    ``"HD2" -> "HD"``, ``"I3" -> "I"``, ``"HDx1" -> "HDx"``, ``"BF" -> "BF"``. A label that
    does not match (empty / unexpected) is returned unchanged.
    """
    m = _BASE_SUFFIX_RE.match(label)
    return m.group(1) if m else label


def is_canonical_label(label: str) -> bool:
    """True if ``label``'s base is a Direct Coil label the authority recognises."""
    return label_base(label) in CANONICAL_LABEL_BASES


def direct_coil_label(label: str) -> str:
    """Map a baked drawing-callout label to its Direct Coil label.

    * EZ residue (``I``/``S``/``O``/``R``/``HD1``/``SL1``) -> parity-indexed Direct Coil form.
    * Already-canonical labels (``BF``, ``CD``, ``HD2``, ``SL5``, ``I3``, ``X`` …) -> unchanged.
    * Unknown labels -> unchanged (never blank, never raises).

    Pure function. Labels only — values are never touched here.
    """
    return _EZ_NORMALIZE.get(label, label)
