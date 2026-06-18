"""Phase 5a — the coil type -> topology spec table loader (rules-as-data).

Reads ``rules/drawing_topology_rules.yaml`` (docs/design/ez-drawing-model.md §7) and resolves
a ``(category, header_type, special)`` request to the :class:`Topology` that says which views,
supply/return kind, features, labels and dims the parametric engine emits for that coil type.

This is a pure function with a single cached YAML I/O (mirrors
``header_prepopulate_engine.load_rule_table``). It contains NO drawing/layout/backend code and
invents nothing. **Fail-closed:** an unknown or ambiguous key raises
:class:`UnknownTopologyError` — there is no silent DX fallback (a §7 invariant).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_TOPOLOGY_PATH = Path(__file__).resolve().parents[1] / "rules" / "drawing_topology_rules.yaml"


class UnknownTopologyError(KeyError):
    """No (or more than one) topology row matches the requested coil type. Fail-closed:
    the engine must omit + annotate rather than fall back to another category's drawing."""


@dataclass(frozen=True)
class Topology:
    """One resolved coil-type topology row, hand-invariant (LH/RH share it)."""

    id: str
    category: str
    special: str | None
    circuits_from: str  # "header_type" (1/2/3) | "const_1"
    supply: str  # "distributor" | "plain_header" — the only structural geometry toggle (5a)
    return_kind: str  # "header"
    feed_type: str | None  # meaningful only for HGRH (drives port spread, wired 5b)
    views: tuple[str, ...]  # subset of ("front", "side", "plan")
    features: tuple[str, ...]
    labels: tuple[str, ...]
    dims: tuple[str, ...]
    new_primitives: tuple[str, ...]  # glyphs deferred to 5b
    extra_slots: tuple[str, ...]  # gated topology slots this type sources (conn_angle/vent_drain/HGBP)
    ref_ezc: tuple[str, ...]  # reference-only (decision-C; real-PDF validation deferred to 5b)
    status: str


def _norm_category(value: Any) -> str:
    return str(value).strip().upper()


def _norm_special(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() == "NONE":
        return None
    return text.upper()


def _norm_header(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text.upper() or None


@lru_cache(maxsize=1)
def load_topology_table() -> tuple[Topology, ...]:
    """Parse + cache the topology rows. Single I/O; the result is immutable."""
    with _TOPOLOGY_PATH.open(encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    rows: list[Topology] = []
    for raw in doc.get("topologies", []):
        header_type = raw.get("header_type")
        rows.append(
            Topology(
                id=str(raw["id"]),
                category=_norm_category(raw["category"]),
                special=_norm_special(raw.get("special")),
                circuits_from=str(raw.get("circuits_from", "header_type")),
                supply=str(raw["supply"]),
                return_kind=str(raw.get("return", "header")),
                feed_type=raw.get("feed_type"),
                views=tuple(raw.get("views", ())),
                features=tuple(raw.get("features", ())),
                labels=tuple(raw.get("labels", ())),
                dims=tuple(raw.get("dims", ())),
                new_primitives=tuple(raw.get("new_primitives", ())),
                extra_slots=tuple(raw.get("extra_slots", ())),
                ref_ezc=tuple(raw.get("ref_ezc", ())),
                status=str(raw.get("status", "")),
            )
        )
    return tuple(rows)


def _header_type_lists() -> dict[str, list[str] | None]:
    """Raw header_type lists per row id (None = matches any header type)."""
    with _TOPOLOGY_PATH.open(encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    out: dict[str, list[str] | None] = {}
    for raw in doc.get("topologies", []):
        ht = raw.get("header_type")
        if ht is None:
            out[str(raw["id"])] = None
        else:
            out[str(raw["id"])] = [_norm_header(h) for h in ht]  # type: ignore[misc]
    return out


@lru_cache(maxsize=1)
def _cached_header_type_lists() -> dict[str, tuple[str, ...] | None]:
    return {
        rid: (None if lst is None else tuple(h for h in lst if h is not None))
        for rid, lst in _header_type_lists().items()
    }


def resolve_topology(
    category: str, header_type: str | None, special: str | None
) -> Topology:
    """Resolve a coil type to its :class:`Topology`. Fail-closed (raises on no/ambiguous match).

    A row matches when category + special match (null special matches null) and the requested
    header_type is in the row's header_type list (a null list matches any). Hand is NOT a key.
    """
    cat = _norm_category(category)
    sp = _norm_special(special)
    ht = _norm_header(header_type)
    ht_lists = _cached_header_type_lists()

    matches = [
        topo
        for topo in load_topology_table()
        if topo.category == cat
        and topo.special == sp
        and (ht_lists[topo.id] is None or (ht is not None and ht in ht_lists[topo.id]))
    ]
    if not matches:
        raise UnknownTopologyError(
            f"no topology for (category={category!r}, header_type={header_type!r}, "
            f"special={special!r}) — review required (no DX fallback)."
        )
    if len(matches) > 1:
        raise UnknownTopologyError(
            f"ambiguous topology for (category={category!r}, header_type={header_type!r}, "
            f"special={special!r}): {[m.id for m in matches]}"
        )
    return matches[0]
