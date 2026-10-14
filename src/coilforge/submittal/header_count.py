"""How many headers the submittal says a DX / HGRH coil has -- and how sure that is.

Layer 1 of the header-count double validation (John 2026-10-14, project 2950). The
drawing path used to take the header count from ONE place, ``geometry.circuits``, and
when that was empty it fell to the intake's default ``HEADER_TYPE "Header 1"`` with
nothing marking it as a default. 2950 RHHGRC-1 printed ``Coil Style: Face Split`` (no
count) and ``Qty Conn. / Header 2``; the count was not read, the default answered, and
a two-header coil drew -- and shipped -- on single-header artwork.

This module reads every independent statement the source makes and says whether they
agree. It is pure: it takes the candidate in its ``model_dump`` shape (the checklist
already holds that shape; the drawing path dumps its Pydantic candidate) and decides
nothing about drawings. ``workflows.submittal_to_drawing._gate_header_count`` is
Layer 2: it compares the artwork actually drawn with this reading.

Signals, and why each one is (or is not) one:

* ``circuits_cell`` / ``coil_style`` / ``header_type_read`` state a CIRCUIT count,
  which is the header count on this path (``header_type = f"Header {circuits}"``).
  Two circuit signals that differ are a ``conflict``.
* ``qty_conn_per_header`` is a DIFFERENT physical quantity (a Terra V HGRH draws four
  circuits on two connections per header). It answers only when no circuit signal
  exists -- John 2026-10-14, Q1 = A, on 52/52 corpus agreement whenever both were
  printed -- and never contradicts one.
* ``Coil Style: Standard`` is NOT a signal (John 2026-10-14). The 2026-10-01 ruling
  "Standard -> Single-Circuit" was a CCSI System Type mapping, not a header-count rule.
* The intake's default ``HEADER_TYPE`` line (``source_location`` starting
  ``pdf-intake-default``) is not a signal: it is the very value this module replaces.
* ``as_built_drawing`` (a scanned CoilMaster drawing's ``C1:``/``C2:`` lines) only keeps
  a scanned drawing from reading as ``absent``. It never sets the value and never
  conflicts: John 2026-10-14 held back any behaviour change on the scanned track.
* ``Qty of Valves`` is left out: its agreement with the header count was never measured.
"""
from __future__ import annotations

import re
from typing import Any, Literal, Mapping, Sequence

HeaderCountStatus = Literal[
    "agreed", "single_source", "conflict", "absent", "as_built_only", "not_applicable"
]

# Statuses under which the source does not establish a header count, so a drawing
# built on one has nothing to stand on. The single place that decides "missing".
UNESTABLISHED_STATUSES: frozenset[str] = frozenset({"conflict", "absent"})

_DEFAULT_LOCATION_PREFIX = "pdf-intake-default"
_HEADER_CATEGORIES = ("DX", "HGRH")
_CIRCUIT_SIGNALS = ("circuits_cell", "coil_style", "header_type_read")


def _value(field: Any) -> Any:
    return field.get("value") if isinstance(field, Mapping) else None


def _evidence(field: Any) -> Mapping[str, Any]:
    evidence = field.get("source_evidence") if isinstance(field, Mapping) else None
    if isinstance(evidence, list) and evidence and isinstance(evidence[0], Mapping):
        return evidence[0]
    return {}


def _whole_number(value: Any) -> int | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return int(number) if number == int(number) and 1 <= number <= 8 else None


def _signal(name: str, value: int, evidence: Mapping[str, Any], raw: Any) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "page": evidence.get("source_page"),
        "raw": None if raw is None else str(raw),
    }


def signals_from_candidate(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every header-count statement a ``SubmittalCoilCandidate.model_dump()`` carries."""
    # Imported here: pdf_intake imports half the package, and this module must stay a
    # cheap import for the checklist and the resolver.
    from coilforge.submittal.pdf_intake import _circuits_from_coil_style

    geometry = candidate.get("geometry") or {}
    connections = candidate.get("connections") or {}
    options = candidate.get("manufacturing_options") or {}
    signals: list[dict[str, Any]] = []

    circuits = geometry.get("circuits")
    circuits_ev = _evidence(circuits)
    # A count derived from the Coil Style prose is the coil_style signal below; counting
    # it here as well would make one statement look like two agreeing ones.
    if circuits_ev.get("source_key") != "CIRCUITS_FROM_STYLE":
        count = _whole_number(_value(circuits))
        if count is not None:
            signals.append(_signal("circuits_cell", count, circuits_ev, _value(circuits)))

    style = options.get("coil_style")
    style_count = _circuits_from_coil_style(_value(style))
    if style_count is not None:
        signals.append(_signal("coil_style", style_count, _evidence(style), _value(style)))

    header_type = candidate.get("header_type")
    header_ev = _evidence(header_type)
    if not str(header_ev.get("source_location") or "").startswith(_DEFAULT_LOCATION_PREFIX):
        match = re.search(r"\d+", str(_value(header_type) or ""))
        count = _whole_number(match.group(0)) if match else None
        if count is not None:
            signals.append(_signal("header_type_read", count, header_ev, _value(header_type)))

    qty = connections.get("qty_connections_per_header")
    qty_count = _whole_number(_value(qty))
    if qty_count is not None:
        signals.append(_signal("qty_conn_per_header", qty_count, _evidence(qty), _value(qty)))
    return signals


def as_built_signal(circuits: Any, page: int | None = None) -> dict[str, Any] | None:
    """The scanned drawing's own circuit count, as a signal (``None`` when unread)."""
    count = _whole_number(circuits)
    if count is None:
        return None
    return {"name": "as_built_drawing", "value": count, "page": page, "raw": str(circuits)}


def read_header_count(
    signals: Sequence[Mapping[str, Any]], *, coil_category: str | None
) -> dict[str, Any]:
    """Judge the signals: ``{value, status, signals, qty_disagrees}``.

    ``value`` is what the drawing should use, or ``None`` when the source does not
    establish one (``conflict`` / ``absent``) or when it is not this module's call
    (``as_built_only``: today's behaviour is kept; ``not_applicable``: water coils).
    """
    signals = [dict(signal) for signal in signals]
    reading: dict[str, Any] = {
        "value": None,
        "status": "absent",
        "signals": signals,
        "qty_disagrees": False,
    }
    if str(coil_category or "").upper() not in _HEADER_CATEGORIES:
        reading["status"] = "not_applicable"
        return reading
    circuit_values = {s["value"] for s in signals if s["name"] in _CIRCUIT_SIGNALS}
    qty_values = {s["value"] for s in signals if s["name"] == "qty_conn_per_header"}
    if len(circuit_values) > 1:
        reading["status"] = "conflict"
        return reading
    if circuit_values:
        (value,) = circuit_values
        reading["value"] = value
        named = [s for s in signals if s["name"] in _CIRCUIT_SIGNALS]
        agreeing_qty = qty_values == {value}
        reading["status"] = "agreed" if (len(named) > 1 or agreeing_qty) else "single_source"
        # One direction only, as the 2026-08 banner did: a stated qty ABOVE the circuits
        # is the 3095 shape; more circuits than connections is ordinary Terra V geometry.
        reading["qty_disagrees"] = any(q > value for q in qty_values)
        return reading
    if len(qty_values) == 1:
        (reading["value"],) = qty_values
        reading["status"] = "single_source"
        return reading
    if any(s["name"] == "as_built_drawing" for s in signals):
        reading["status"] = "as_built_only"
    return reading


def header_count_reading(
    candidate: Mapping[str, Any],
    *,
    coil_category: str | None,
    as_built: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """``read_header_count`` over a candidate dump, plus an optional as-built signal."""
    signals = signals_from_candidate(candidate)
    if as_built:
        signals.append(dict(as_built))
    return read_header_count(signals, coil_category=coil_category)


def describe_signals(signals: Sequence[Mapping[str, Any]]) -> str:
    """``"Qty Conn./Header 2 (p8); Coil Style 'Face Split' (p8)"`` -- for reasons."""
    labels = {
        "circuits_cell": "Circuits",
        "coil_style": "Coil Style",
        "header_type_read": "Header Type",
        "qty_conn_per_header": "Qty Conn./Header",
        "as_built_drawing": "as-built drawing circuits",
    }
    parts = []
    for signal in signals:
        page = signal.get("page")
        where = f" (p{page})" if page else ""
        raw = signal.get("raw")
        shown = f"'{raw}'" if raw not in (None, "") and str(raw) != str(signal.get("value")) else signal.get("value")
        name = str(signal.get("name"))
        parts.append(f"{labels.get(name, name)} {shown}{where}")
    return "; ".join(parts)
