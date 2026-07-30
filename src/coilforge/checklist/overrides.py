"""Pure adapter: the engineer's browser manual fills -> checklist inputs/dims.

When John corrects a coil in the browser (the human-in-the-loop manual fill), the
drawing regenerates from the corrected value but the Coil Checklist used to keep
re-deriving itself from the raw submittal, so the sheet -- and the .xlsx filed with
the order -- silently disagreed with the drawing. This module carries those manual
fills into the checklist fill.

Two tiers, and they land in DIFFERENT places on the sheet:

- **Tier A -- engine inputs** (``rows``, ``application``, ``coil_hand``, ...) are
  column-C INPUT cells. Writing them is unambiguous: the sheet's own formulas then
  recompute from the same inputs CoilForge used, which STRENGTHENS the cross-check.
- **Tier B -- drawing params** (``CD``, ``TF``, ``S``, ``O2``, ...) are FORMULA
  cells. Their slot is resolved with the SAME helpers the drawing path uses
  (``drawing_param_resolver.PARAM_TO_SLOT`` / ``_header_slot``, via
  :func:`param_slot`) so the checklist and the drawing can never disagree about
  which dimension a key means. The writer overwrites the formula only AFTER reading
  its computed result back (see ``excel_writer``), so nothing is lost.

No I/O, no Excel, and nothing is invented: an override key this module cannot place
is returned in ``ignored_keys`` / left unmatched for the caller to surface as a
warning, never dropped in silence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from coilforge.checklist.model import OverrideNote

# Manual-fill engine-input key -> the coil-input dict key ``mapping._build_sheet`` reads.
# Keys mirror ``drawing_param_resolver._ENGINE_INPUT_META`` plus the picker/spec-field
# keys the frontend sends (``coil_hand``, ``coating``, ``product_type``, ``unit_size``).
_ENGINE_KEY_TO_COIL_KEY: dict[str, str] = {
    "rows": "rows",
    "feeds": "feeds",
    "circuits": "circuits",
    "qty_conn_per_header": "qty_conn_per_header",
    "suction_conn_size": "suction_conn_size",
    "conn_size": "conn_size",
    "inlet_conn_size": "inlet_conn_size",
    "outlet_conn_size": "outlet_conn_size",
    "application": "application",
    "coil_hand": "coil_hand",
    "coating": "coating",
    "product_type": "product_label",
    "unit_size": "unit_size",
}

# ``return_conn_size`` is the frontend's spec-field name for "the coil's return/suction
# connection". Which checklist cell that is depends on the category -- the DX sheet calls
# it SUCTION CONN SZ, the HGRH sheet CONN SZ, a water sheet OUT CONN SZ.
_RETURN_CONN_COIL_KEY: dict[str, str] = {
    "DX": "suction_conn_size",
    "HGRH": "conn_size",
    "HWC": "outlet_conn_size",
    "CWC": "outlet_conn_size",
}

# Engine inputs with no checklist analog. ``header_count`` un-gates the rule engine in the
# drawing path but is not a checklist field and is not an input to the checklist's own
# engine pass (``mapping._resolve_engine``), so applying it here would be theatre.
IGNORED_ENGINE_KEYS: frozenset[str] = frozenset({"header_count"})


@dataclass(frozen=True)
class CoilOverride:
    """One coil's manual fills, normalized. ``reasons`` is per key, falling back to the
    coil-level ``reason`` the engineer typed once for the whole Apply click."""

    tag: str
    engine_inputs: dict[str, Any] = field(default_factory=dict)
    param_overrides: dict[str, Any] = field(default_factory=dict)
    reasons: dict[str, str | None] = field(default_factory=dict)
    reason: str | None = None
    ignored_keys: tuple[str, ...] = ()

    def reason_for(self, key: str) -> str | None:
        return self.reasons.get(key) or self.reason


def _clean(value: Any) -> Any:
    """Trim strings; treat empty as absent (an untouched input field posts "")."""
    if isinstance(value, str):
        value = value.strip()
    return None if value in (None, "") else value


def normalize_coil_overrides(payload: Any) -> dict[str, CoilOverride]:
    """``[{tag, engine_inputs, param_overrides, reason}, ...]`` -> ``{tag: CoilOverride}``.

    Accepts the frontend's camelCase spelling (``engineInputs`` / ``paramOverrides``) as
    well, so a caller that forwards ``page.manualFills`` verbatim does not silently lose
    every fill. A malformed entry is skipped rather than raising -- the checklist must
    still fill when one coil's payload is junk.
    """
    out: dict[str, CoilOverride] = {}
    if not isinstance(payload, list):
        return out
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        tag = _clean(entry.get("tag"))
        if tag is None:
            continue
        coil_reason = _clean(entry.get("reason"))
        raw_inputs = entry.get("engine_inputs")
        if not isinstance(raw_inputs, dict):
            raw_inputs = entry.get("engineInputs")
        if not isinstance(raw_inputs, dict):
            raw_inputs = {}
        engine_inputs: dict[str, Any] = {}
        reasons: dict[str, str | None] = {}
        ignored: list[str] = []
        for key, value in raw_inputs.items():
            value = _clean(value)
            if value is None:
                continue
            key = str(key)
            if key in IGNORED_ENGINE_KEYS:
                ignored.append(key)
                continue
            if key != "return_conn_size" and key not in _ENGINE_KEY_TO_COIL_KEY:
                ignored.append(key)
                continue
            engine_inputs[key] = value

        raw_params = entry.get("param_overrides")
        if not isinstance(raw_params, list):
            raw_params = entry.get("paramOverrides")
        param_overrides: dict[str, Any] = {}
        for item in raw_params or []:
            if not isinstance(item, dict):
                continue
            key = _clean(item.get("key"))
            value = _clean(item.get("value"))
            if key is None or value is None:
                continue
            param_overrides[str(key)] = value
            reasons[str(key)] = _clean(item.get("override_reason"))

        if not engine_inputs and not param_overrides:
            continue
        out[str(tag)] = CoilOverride(
            tag=str(tag), engine_inputs=engine_inputs, param_overrides=param_overrides,
            reasons=reasons, reason=coil_reason, ignored_keys=tuple(ignored),
        )
    return out


def apply_engine_inputs(
    coil: dict[str, Any], override: CoilOverride | None, category: str
) -> tuple[dict[str, Any], dict[str, OverrideNote]]:
    """Return ``(coil_with_overrides, {coil_key: OverrideNote})``.

    The returned coil is a COPY -- the caller's extracted-from-submittal dict is never
    mutated, so a re-fill without overrides reproduces the original exactly. The notes
    are keyed by coil-input key (``rows``, ``coil_hand``, ...); ``mapping`` attaches each
    to the cell it builds from that key, because label knowledge lives there.
    """
    if override is None or not override.engine_inputs:
        return coil, {}
    updated = dict(coil)
    notes: dict[str, OverrideNote] = {}
    for key, value in override.engine_inputs.items():
        coil_key = (
            _RETURN_CONN_COIL_KEY.get(category)
            if key == "return_conn_size"
            else _ENGINE_KEY_TO_COIL_KEY.get(key)
        )
        if not coil_key:
            continue
        notes[coil_key] = OverrideNote(
            key=key, previous_value=coil.get(coil_key), reason=override.reason_for(key)
        )
        updated[coil_key] = value
    return updated, notes


def param_slot(key: str) -> str | None:
    """Drawing-parameter key -> engine slot id, using the DRAWING path's own helpers.

    Mirrors ``submittal_to_drawing._reflect_param_overrides_into_slots._slot_for``: base
    keys (and ``HDx1``, which carries digits, hence the direct lookup first) come from
    ``PARAM_TO_SLOT``; a logical multi-header key (``S2``, ``O3``) goes through
    ``_header_slot`` for the logical->parity bridge. Sharing those helpers is what keeps
    "which dimension is TF/S2" identical between the drawing and the checklist.
    """
    from coilforge.services.drawing_param_resolver import PARAM_TO_SLOT, _header_slot

    key = str(key)
    if key in PARAM_TO_SLOT:
        return PARAM_TO_SLOT[key]
    base = key.rstrip("0123456789")
    digits = key[len(base):]
    if base and digits:
        try:
            n = int(digits)
        except ValueError:
            return None
        if n >= 2:
            return _header_slot(base, n)
    return None


def dim_overrides_by_slot(
    override: CoilOverride | None,
) -> tuple[dict[str, tuple[str, Any, str | None]], tuple[str, ...]]:
    """``({slot: (key, value, reason)}, unmapped_keys)`` for the Tier-B overrides.

    ``unmapped_keys`` are params with no slot at all (e.g. ``ZD``, the owner-fixed
    constant) -- the caller warns rather than dropping them.
    """
    if override is None or not override.param_overrides:
        return {}, ()
    by_slot: dict[str, tuple[str, Any, str | None]] = {}
    unmapped: list[str] = []
    for key, value in override.param_overrides.items():
        slot = param_slot(key)
        if slot is None:
            unmapped.append(key)
            continue
        by_slot[slot] = (key, value, override.reason_for(key))
    return by_slot, tuple(unmapped)
