"""Direct Coil label authority: maps baked drawing-callout labels to Direct Coil labels.

The EZ-coil-seeded templates carry two kinds of blue dim-callout label — slot-driven ones
that already match the Direct Coil slot name, and literal EZ residue (bare I/S/O/R, EZ
HD1/SL1). The authority normalises the residue to the Direct Coil parity-indexed convention
and leaves everything else unchanged. Labels only — values are never touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.drawing.label_authority import (
    CANONICAL_LABEL_BASES,
    direct_coil_label,
    is_canonical_label,
    label_base,
)


def test_ez_residue_normalizes_to_parity_indexed_direct_coil_labels() -> None:
    # supply header = odd index (1); return header = even index (2).
    assert direct_coil_label("I") == "I1"
    assert direct_coil_label("S") == "S1"
    assert direct_coil_label("O") == "O2"
    assert direct_coil_label("R") == "R2"
    assert direct_coil_label("HD1") == "HD2"
    assert direct_coil_label("SL1") == "SL2"


def test_already_canonical_labels_are_identity() -> None:
    for label in ("BF", "CD", "TF", "RF", "HF", "CH", "OAL", "RB", "X",
                  "HD2", "HDx1", "SL2", "SL5", "SL7", "I1", "I3", "O4", "R6", "S1", "FH", "FL"):
        assert direct_coil_label(label) == label, label


def test_unknown_label_passes_through_unchanged() -> None:
    # Never blank, never raises — an unrecognised token is left as-is.
    assert direct_coil_label("ZZ9") == "ZZ9"
    assert direct_coil_label("") == ""


def test_label_base_strips_trailing_index() -> None:
    assert label_base("HD2") == "HD"
    assert label_base("I3") == "I"
    assert label_base("HDx1") == "HDx"
    assert label_base("BF") == "BF"
    assert label_base("SL7") == "SL"


def test_every_normalization_target_is_a_canonical_direct_coil_label() -> None:
    """The registry is the source of truth: a normalized label must resolve to a base the
    Direct Coil parameter/geometry registry recognises (no pointing at a non-registry label)."""
    for ez in ("I", "S", "O", "R", "HD1", "SL1"):
        assert is_canonical_label(direct_coil_label(ez)), ez


def test_canonical_bases_include_the_registry_param_keys() -> None:
    # Derived from interfaces/direct_coil/fields.py DRAWING_PARAMETER_FIELD_KEYS.
    for key in ("CD", "I", "S", "O", "R", "BF", "HD", "HF", "TF", "RF", "CH", "SL", "ZD"):
        assert key in CANONICAL_LABEL_BASES, key
