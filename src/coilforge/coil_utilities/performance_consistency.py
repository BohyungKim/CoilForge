"""Performance self-consistency — do one coil's extracted values agree with each other?

A review aid for the moment a submittal is pushed to CCSI, when no ordered selection exists
to compare against. It reads the coil's performance values (airflow, air temperatures,
capacity, fluid conditions, face geometry) and reports, per relation, whether they are
mutually consistent. It never changes, corrects or fills a value: a missing or unreadable
input makes that check ``cannot_evaluate``.

Scope: **per-coil** Oxygen8 submittal values. The submittal's airflow, capacity and GPM are
all per coil (the ``x quantity`` step belongs to the CCSI map's ``number_times_quantity``
transform), so coil quantity is deliberately not read here. A document that states
"Capacity (All Coils)" (the Ambient quote) is out of scope.

What ``consistent`` means: *not contradicted*. On the measured corpus the Standard and
Actual air-basis expectations are closer than 0.04 on 100 of 118 heating coils, so the check
catches gross disagreement, not small misreads. A cooling coil's TOTAL capacity carries
latent load and has no two-sided relation at all — only its sensible capacity does.

Reference status of each relation (mirrors the project's captured / validated vocabulary):
``in_repo`` — the constant already lives in the repo; ``cited`` — a standard physical
relation John accepted, not one read from a CCSI document; ``captured`` — a band measured on the ordered-coil
corpus, not a formula. Constants and their evidence: ``docs/validation/performance_consistency.md``.

Pure: no I/O, no ``eval``, the input mapping is not mutated.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from coilforge.coil_utilities.geometry import face_area_sqft

Verdict = Literal["consistent", "inconsistent", "cannot_evaluate"]
AirBasis = Literal["standard", "actual", "indeterminate", "standard_only"]
ReferenceStatus = Literal["in_repo", "cited", "captured"]

PERF_OK = "PERF_OK"
PERF_MISMATCH = "PERF_MISMATCH"
PERF_OUTSIDE_CAPTURED_RANGE = "PERF_OUTSIDE_CAPTURED_RANGE"
PERF_SOURCE_MISSING = "PERF_SOURCE_MISSING"
PERF_SOURCE_BLOCKED = "PERF_SOURCE_BLOCKED"
PERF_VALUE_UNPARSEABLE = "PERF_VALUE_UNPARSEABLE"
PERF_UNIT_UNEXPECTED = "PERF_UNIT_UNEXPECTED"
PERF_DEGENERATE = "PERF_DEGENERATE"
PERF_NOT_APPLICABLE = "PERF_NOT_APPLICABLE"
PERF_NO_REFERENCE = "PERF_NO_REFERENCE"
PERF_COIL_TYPE_UNKNOWN = "PERF_COIL_TYPE_UNKNOWN"

# Sensible factor [BTU/h per CFM.degF] at standard air — the same 1.085 the workbook's Extras
# heating-capacity calc uses (coil_utilities/geometry.py). John 2026-10-01 (decision 1): keep
# 1.085. CCSI's Standard reports measure 1.084; at +/-0.02 the two give identical verdicts.
SENSIBLE_FACTOR = 1.085
K_TOLERANCE = 0.02  # John 2026-10-01 (decision 2). Narrower flags 16-30 % of DX coils (38 sit at k 1.095-1.105).
FACE_VELOCITY_REL_TOLERANCE = 0.01  # John 2026-10-01 (decision 6). 0.2 % to 5 % all give the same corpus result.

# Actual-air density relative to standard air (70 degF, sea level): ideal-gas temperature
# ratio at the entering air x the standard-atmosphere pressure ratio. Not taken from a CCSI
# document; John accepted it as the cited reference 2026-10-01 (decision 3) — every evaluable
# heating coil from project 3100 on fits it.
_STANDARD_AIR_RANKINE = 529.67
_RANKINE_OFFSET = 459.67
_ALTITUDE_LAPSE_PER_FT = 6.8754e-6
_ALTITUDE_EXPONENT = 5.2559

# Fluid-side factor = capacity [BTU/h] / (GPM x fluid delta-T). CAPTURED bands, not a
# property table: the unrounded extremes seen on the ordered-coil corpus (2026-09-30),
# rounded outward. (fluid, percent of that fluid) -> (low, high, coils measured).
FLUID_FACTOR_BANDS: dict[tuple[str, float], tuple[float, float, int]] = {
    ("water", 100.0): (488.0, 503.0, 10),
    ("propylene glycol", 40.0): (457.0, 467.0, 8),
    ("propylene glycol", 50.0): (443.0, 453.0, 9),
}
# John 2026-10-01 (decision 5): keep 3 %. Room for 2-significant-figure GPM rounding and for
# fluid temperatures the corpus does not reach (no water coil above 160 degF was measured).
FLUID_BAND_MARGIN = 0.03

_FLUID_ALIASES = {"water": "water", "propylene": "propylene glycol", "propylene glycol": "propylene glycol"}

_HEATING = frozenset({"HGRH", "HWC"})
_COOLING = frozenset({"DX", "CWC"})
_WATER = frozenset({"CWC", "HWC"})

_NUMBER_RE = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)")  # ASCII digits only: \d takes fullwidth ones
_DEGF = frozenset({"degf", "°f", "f"})

# logical input -> (keys tried in order: draft key first, then canonical path; accepted units)
_INPUTS: dict[str, tuple[tuple[str, ...], frozenset[str]]] = {
    "airflow_cfm": (("total_air_flow_cfm", "airside_conditions.total_air_flow_cfm"), frozenset({"cfm"})),
    "entering_dry_bulb_f": (("entering_dry_bulb_f", "airside_conditions.entering_dry_bulb_f"), _DEGF),
    "leaving_dry_bulb_f": (("leaving_dry_bulb_f", "airside_conditions.leaving_dry_bulb_f"), _DEGF),
    "entering_wet_bulb_f": (("entering_wet_bulb_f", "airside_conditions.entering_wet_bulb_f"), _DEGF),
    "altitude_ft": (("altitude_ft", "airside_conditions.altitude_ft"), frozenset({"ft"})),
    "face_velocity_fpm": (("face_velocity_fpm", "airside_conditions.face_velocity_fpm"), frozenset({"fpm"})),
    "finned_height_in": (("finned_height", "geometry.finned_height"), frozenset({"in"})),
    "finned_length_in": (("finned_length", "geometry.finned_length"), frozenset({"in"})),
    "total_capacity_mbh": (("total_capacity_mbh", "performance.total_capacity_mbh"), frozenset({"mbh"})),
    "sensible_capacity_mbh": (("performance.sensible_capacity_mbh",), frozenset({"mbh"})),
    "fluid_percent": (("airside_conditions.fluid_percent",), frozenset({"pct", "%"})),
    "fluid_entering_temp_f": (("airside_conditions.fluid_entering_temp_f",), _DEGF),
    "fluid_leaving_temp_f": (("airside_conditions.fluid_leaving_temp_f",), _DEGF),
    "fluid_flow_gpm": (("airside_conditions.fluid_flow_rate_gpm",), frozenset({"gpm"})),
}
_FLUID_TYPE_KEYS = ("airside_conditions.fluid_type",)


class ConsistencyFinding(BaseModel):
    """One relation between a coil's performance values, and whether they satisfy it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    check: str
    verdict: Verdict
    reason_code: str
    reason: str
    observed: float | None = None
    expected: dict[str, float] = Field(default_factory=dict)
    tolerance: float | None = None
    air_basis: AirBasis | None = None
    inputs_used: dict[str, float] = Field(default_factory=dict)
    source_keys: dict[str, str] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)
    reference_status: ReferenceStatus | None = None
    review_required: Literal[True] = True


class PerformanceConsistencyReport(BaseModel):
    """Every check for one coil. A review aid: it approves nothing and gates no export."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    coil_type: str | None
    findings: list[ConsistencyFinding]
    counts: dict[str, int]
    review_aid_only: Literal[True] = True
    export_allowed: Literal[False] = False


def parse_number(raw: Any) -> float | None:
    """A finite number, or None.

    Accepts a non-bool int/float, or a string that is entirely a plain decimal. ``"3,735"``,
    ``"95.0 °F"``, ``"N/A"`` and ``"1e3"`` are refused: the push path refuses them too, and
    stripping a unit or a separator here would be reading something the source did not say.
    """
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
        return value if math.isfinite(value) else None
    if isinstance(raw, str) and _NUMBER_RE.fullmatch(raw.strip()):
        return float(raw.strip())
    return None


def _unwrap(source: Any) -> tuple[Any, str | None, str | None]:
    """(value, status, unit) from a FieldValue / draft field, its dict form, or a bare value."""
    if hasattr(source, "model_dump"):
        source = source.model_dump()
    if isinstance(source, Mapping) and "value" in source:
        unit = source.get("unit")
        return source.get("value"), source.get("status"), None if unit is None else str(unit)
    return source, None, None


def _locate(sources: Mapping[str, Any], keys: tuple[str, ...]) -> tuple[Any, str | None, str | None, str | None]:
    """(value, unit, key, problem) from the first key that carries a value or is blocked."""
    for key in keys:
        value, status, unit = _unwrap(sources.get(key))
        if status == "blocked":
            return None, None, key, PERF_SOURCE_BLOCKED
        if value is not None:
            return value, unit, key, None
    return None, None, None, PERF_SOURCE_MISSING


class _Inputs:
    """Reads the logical inputs a check asks for and remembers which were unusable."""

    def __init__(self, sources: Mapping[str, Any]) -> None:
        self._sources = sources
        self.used: dict[str, float] = {}
        self.keys: dict[str, str] = {}
        self.problems: dict[str, str] = {}

    def number(self, name: str) -> float | None:
        keys, units = _INPUTS[name]
        raw, unit, key, problem = _locate(self._sources, keys)
        if problem is not None or key is None:
            self.problems[name] = problem or PERF_SOURCE_MISSING
            return None
        value = parse_number(raw)
        if value is None:
            self.problems[name] = PERF_VALUE_UNPARSEABLE
            return None
        if unit is not None and unit.strip() and unit.strip().lower() not in units:
            self.problems[name] = PERF_UNIT_UNEXPECTED
            return None
        self.used[name] = value
        self.keys[name] = key
        return value

    def numbers(self, *names: str) -> tuple[float, ...] | None:
        """Every named input, or None when any is unusable (all are read, so all are reported)."""
        values = [value for value in map(self.number, names) if value is not None]
        return tuple(values) if len(values) == len(names) else None

    def fluid(self) -> str | None:
        raw, _, key, problem = _locate(self._sources, _FLUID_TYPE_KEYS)
        if problem is not None or key is None:
            self.problems["fluid_type"] = problem or PERF_SOURCE_MISSING
            return None
        if not (isinstance(raw, str) and raw.strip()):
            self.problems["fluid_type"] = PERF_VALUE_UNPARSEABLE
            return None
        self.keys["fluid_type"] = key
        return raw.strip()


def _finding(check: str, inputs: _Inputs, verdict: Verdict, code: str, reason: str, **extra: Any) -> ConsistencyFinding:
    return ConsistencyFinding(
        check=check, verdict=verdict, reason_code=code, reason=reason,
        inputs_used=dict(inputs.used), source_keys=dict(inputs.keys), **extra,
    )


def _unusable(check: str, inputs: _Inputs, **extra: Any) -> ConsistencyFinding:
    """``cannot_evaluate`` for the inputs that were missing / blocked / unreadable."""
    names = list(inputs.problems)
    detail = ", ".join(f"{name} ({inputs.problems[name]})" for name in names)
    return _finding(check, inputs, "cannot_evaluate", inputs.problems[names[0]],
                    f"cannot evaluate: {detail}", missing=names, **extra)


def _skipped(check: str, sources: Mapping[str, Any], code: str, reason: str) -> ConsistencyFinding:
    return _finding(check, _Inputs(sources), "cannot_evaluate", code, reason)


def _within(value: float, target: float, tolerance: float) -> bool:
    return abs(value - target) <= tolerance + 1e-9


def _actual_factor(entering_dry_bulb_f: float, altitude_ft: float) -> float | None:
    pressure_base = 1.0 - _ALTITUDE_LAPSE_PER_FT * altitude_ft
    temperature_r = _RANKINE_OFFSET + entering_dry_bulb_f
    if pressure_base <= 0 or temperature_r <= 0:
        return None
    return SENSIBLE_FACTOR * _STANDARD_AIR_RANKINE / temperature_r * pressure_base**_ALTITUDE_EXPONENT


def _altitude_note(inputs: _Inputs) -> str:
    problem = inputs.problems.get("altitude_ft")
    return f"altitude is unusable ({problem})" if problem else "the stated altitude or entering air is out of range"


def _air_inputs(inputs: _Inputs, capacity_name: str, *, heating: bool) -> tuple[float, float, float | None] | None:
    """(k, entering dry bulb, altitude or None) for a sensible relation; None when unusable.

    Air that does not move in the coil's direction is recorded as ``problems["delta_t"]``
    and left to ``air_temp_direction`` to report: a negative k would say nothing here.
    """
    values = inputs.numbers(capacity_name, "airflow_cfm", "entering_dry_bulb_f", "leaving_dry_bulb_f")
    if values is None:
        return None
    capacity, airflow, entering, leaving = values
    delta_t = leaving - entering if heating else entering - leaving
    if airflow <= 0 or delta_t <= 0:
        inputs.problems["delta_t"] = PERF_DEGENERATE
        return None
    altitude = inputs.number("altitude_ft")  # optional: its absence is handled by the caller
    return capacity * 1000.0 / (airflow * delta_t), entering, altitude


def _air_sensible_balance(sources: Mapping[str, Any], coil_type: str) -> ConsistencyFinding:
    check = "air_sensible_balance"
    heating = coil_type in _HEATING
    inputs = _Inputs(sources)
    resolved = _air_inputs(inputs, "total_capacity_mbh" if heating else "sensible_capacity_mbh", heating=heating)
    if resolved is None:
        return _unusable(check, inputs, reference_status="cited")
    k, entering, altitude = resolved
    common = {"observed": k, "tolerance": K_TOLERANCE, "reference_status": "cited"}
    matches_standard = _within(k, SENSIBLE_FACTOR, K_TOLERANCE)
    actual = None if altitude is None else _actual_factor(entering, altitude)
    if actual is None:
        # Altitude is never assumed to be 0: the Actual basis cannot be ruled in or out.
        expected = {"standard": SENSIBLE_FACTOR}
        if matches_standard:
            return _finding(check, inputs, "consistent", PERF_OK,
                            "matches the Standard-air basis; Actual was not evaluated (no usable altitude)",
                            expected=expected, air_basis="standard_only", **common)
        return _finding(check, inputs, "cannot_evaluate", inputs.problems.get("altitude_ft", PERF_DEGENERATE),
                        "does not match the Standard-air basis and Actual cannot be evaluated: " + _altitude_note(inputs),
                        expected=expected, missing=["altitude_ft"], **common)
    expected = {"standard": SENSIBLE_FACTOR, "actual": actual}
    matches_actual = _within(k, actual, K_TOLERANCE)
    if matches_standard and matches_actual:
        return _finding(check, inputs, "consistent", PERF_OK, "matches both air bases",
                        expected=expected, air_basis="indeterminate", **common)
    if matches_standard or matches_actual:
        basis = "standard" if matches_standard else "actual"
        return _finding(check, inputs, "consistent", PERF_OK, f"matches the {basis}-air basis",
                        expected=expected, air_basis=basis, **common)
    return _finding(check, inputs, "inconsistent", PERF_MISMATCH,
                    "capacity, airflow and air temperatures fit neither the Standard nor the Actual air basis",
                    expected=expected, **common)


def _air_total_vs_sensible(sources: Mapping[str, Any]) -> ConsistencyFinding:
    """One-sided: a cooling coil's total capacity cannot be below its air-side sensible load."""
    check = "air_total_vs_sensible"
    inputs = _Inputs(sources)
    resolved = _air_inputs(inputs, "total_capacity_mbh", heating=False)
    if resolved is None:
        return _unusable(check, inputs, reference_status="cited")
    k_total, entering, altitude = resolved
    common = {"observed": k_total, "tolerance": K_TOLERANCE, "reference_status": "cited"}
    actual = None if altitude is None else _actual_factor(entering, altitude)
    if actual is None:
        expected = {"minimum": SENSIBLE_FACTOR - K_TOLERANCE}
        if k_total >= expected["minimum"] - 1e-9:
            return _finding(check, inputs, "consistent", PERF_OK,
                            "total capacity is at least the Standard-air sensible load", expected=expected, **common)
        return _finding(check, inputs, "cannot_evaluate", inputs.problems.get("altitude_ft", PERF_DEGENERATE),
                        "below the Standard-air sensible load and Actual cannot be evaluated: " + _altitude_note(inputs),
                        expected=expected, missing=["altitude_ft"], **common)
    expected = {"minimum": min(SENSIBLE_FACTOR, actual) - K_TOLERANCE}
    if k_total >= expected["minimum"] - 1e-9:
        return _finding(check, inputs, "consistent", PERF_OK,
                        "total capacity is at least the air-side sensible load", expected=expected, **common)
    return _finding(check, inputs, "inconsistent", PERF_MISMATCH,
                    "total capacity is below the sensible load the air temperatures imply",
                    expected=expected, **common)


def _sensible_le_total(sources: Mapping[str, Any]) -> ConsistencyFinding:
    check = "sensible_le_total"
    inputs = _Inputs(sources)
    values = inputs.numbers("sensible_capacity_mbh", "total_capacity_mbh")
    if values is None:
        return _unusable(check, inputs)
    sensible, total = values
    if sensible <= total + 1e-9:
        return _finding(check, inputs, "consistent", PERF_OK, "sensible capacity does not exceed total capacity",
                        observed=sensible, expected={"maximum": total})
    return _finding(check, inputs, "inconsistent", PERF_MISMATCH, "sensible capacity exceeds total capacity",
                    observed=sensible, expected={"maximum": total})


def _fluid_heat_balance(sources: Mapping[str, Any]) -> ConsistencyFinding:
    check = "fluid_heat_balance"
    inputs = _Inputs(sources)
    values = inputs.numbers("total_capacity_mbh", "fluid_flow_gpm", "fluid_entering_temp_f",
                            "fluid_leaving_temp_f", "fluid_percent")
    fluid = inputs.fluid()
    if values is None or fluid is None:
        return _unusable(check, inputs, reference_status="captured")
    capacity, flow, entering, leaving, percent = values
    delta_t = abs(entering - leaving)
    if flow <= 0 or delta_t == 0:
        return _finding(check, inputs, "cannot_evaluate", PERF_DEGENERATE,
                        "fluid flow or fluid temperature difference is zero", reference_status="captured")
    band = FLUID_FACTOR_BANDS.get((_FLUID_ALIASES.get(fluid.lower(), ""), percent))
    factor = capacity * 1000.0 / (flow * delta_t)
    if band is None:
        return _finding(check, inputs, "cannot_evaluate", PERF_NO_REFERENCE,
                        f"no captured reference for {fluid} at {percent:g} %", observed=factor,
                        reference_status="captured")
    low, high, _ = band
    expected = {"band_low": low, "band_high": high,
                "low_with_margin": low * (1.0 - FLUID_BAND_MARGIN), "high_with_margin": high * (1.0 + FLUID_BAND_MARGIN)}
    common = {"observed": factor, "expected": expected, "tolerance": FLUID_BAND_MARGIN, "reference_status": "captured"}
    if expected["low_with_margin"] - 1e-9 <= factor <= expected["high_with_margin"] + 1e-9:
        return _finding(check, inputs, "consistent", PERF_OK,
                        "capacity, flow and fluid temperatures sit inside the captured range", **common)
    return _finding(check, inputs, "inconsistent", PERF_OUTSIDE_CAPTURED_RANGE,
                    "capacity, flow and fluid temperatures fall outside the range measured on ordered coils "
                    "(an empirical band, not a formula)", **common)


def _face_velocity(sources: Mapping[str, Any]) -> ConsistencyFinding:
    check = "face_velocity"
    inputs = _Inputs(sources)
    values = inputs.numbers("airflow_cfm", "finned_height_in", "finned_length_in", "face_velocity_fpm")
    if values is None:
        return _unusable(check, inputs, reference_status="in_repo")
    airflow, height, length, stated = values
    # Always from FH x FL: the submittal's own "Face Area (sq.ft)" is printed rounded.
    area = face_area_sqft(fin_height=height, fin_length=length)
    if not area or area <= 0 or stated <= 0:
        return _finding(check, inputs, "cannot_evaluate", PERF_DEGENERATE,
                        "face area or stated face velocity is zero", reference_status="in_repo")
    computed = airflow / area
    common = {"observed": stated, "expected": {"computed": computed},
              "tolerance": FACE_VELOCITY_REL_TOLERANCE, "reference_status": "in_repo"}
    if abs(computed - stated) / stated <= FACE_VELOCITY_REL_TOLERANCE + 1e-9:
        return _finding(check, inputs, "consistent", PERF_OK, "stated face velocity equals airflow / face area", **common)
    return _finding(check, inputs, "inconsistent", PERF_MISMATCH,
                    "stated face velocity differs from airflow / face area", **common)


def _air_temp_direction(sources: Mapping[str, Any], coil_type: str) -> ConsistencyFinding:
    check = "air_temp_direction"
    inputs = _Inputs(sources)
    values = inputs.numbers("entering_dry_bulb_f", "leaving_dry_bulb_f")
    if values is None:
        return _unusable(check, inputs)
    entering, leaving = values
    heating = coil_type in _HEATING
    ok = leaving > entering if heating else leaving < entering
    wanted = "above" if heating else "below"
    if ok:
        return _finding(check, inputs, "consistent", PERF_OK, f"leaving dry bulb is {wanted} entering dry bulb")
    return _finding(check, inputs, "inconsistent", PERF_MISMATCH,
                    f"leaving dry bulb is not {wanted} entering dry bulb for a {coil_type} coil")


def _wet_bulb_le_dry_bulb(sources: Mapping[str, Any]) -> ConsistencyFinding:
    check = "wet_bulb_le_dry_bulb"
    if _locate(sources, _INPUTS["entering_wet_bulb_f"][0])[3] == PERF_SOURCE_MISSING:
        return _skipped(check, sources, PERF_NOT_APPLICABLE, "no entering wet bulb is stated")
    inputs = _Inputs(sources)
    values = inputs.numbers("entering_wet_bulb_f", "entering_dry_bulb_f")
    if values is None:
        return _unusable(check, inputs)
    wet, dry = values
    if wet <= dry + 1e-9:
        return _finding(check, inputs, "consistent", PERF_OK, "entering wet bulb does not exceed entering dry bulb")
    return _finding(check, inputs, "inconsistent", PERF_MISMATCH, "entering wet bulb exceeds entering dry bulb")


def check_performance_consistency(
    sources: Mapping[str, Any], *, coil_type: str | None
) -> PerformanceConsistencyReport:
    """Run every check for one coil and report each verdict separately.

    ``sources`` maps Direct Coil draft keys and/or canonical ``group.key`` paths to a
    FieldValue / draft field, its dict form, or a bare value — the shape the CCSI push
    resolves from. For each input the draft key is tried first, then the canonical path; a
    key counts only when it carries a non-null value. Fluid percent is the submittal's own
    statement: the share of the fluid it names (``Water`` 100, ``Propylene Glycol`` 40).

    All seven checks are always returned. One that does not apply to the coil type is
    ``cannot_evaluate`` / ``PERF_NOT_APPLICABLE`` rather than absent, so a reader can tell
    "not checked by design" from "checked and fine".
    """
    kind = coil_type.strip().upper() if isinstance(coil_type, str) else ""
    known = kind in _HEATING or kind in _COOLING
    cooling = kind in _COOLING

    def typed(check: str, applies: bool, run: Any) -> ConsistencyFinding:
        if not known:
            return _skipped(check, sources, PERF_COIL_TYPE_UNKNOWN, f"coil type {coil_type!r} is not recognised")
        if not applies:
            return _skipped(check, sources, PERF_NOT_APPLICABLE, f"does not apply to a {kind} coil")
        return run()

    findings = [
        typed("air_sensible_balance", True, lambda: _air_sensible_balance(sources, kind)),
        typed("air_total_vs_sensible", cooling, lambda: _air_total_vs_sensible(sources)),
        typed("sensible_le_total", cooling, lambda: _sensible_le_total(sources)),
        typed("fluid_heat_balance", kind in _WATER, lambda: _fluid_heat_balance(sources)),
        _face_velocity(sources),
        typed("air_temp_direction", True, lambda: _air_temp_direction(sources, kind)),
        _wet_bulb_le_dry_bulb(sources),
    ]
    counts = {verdict: sum(f.verdict == verdict for f in findings)
              for verdict in ("consistent", "inconsistent", "cannot_evaluate")}
    return PerformanceConsistencyReport(coil_type=kind if known else coil_type, findings=findings, counts=counts)
