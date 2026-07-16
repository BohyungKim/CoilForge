"""Project baseline + Ambient candidates -> a per-coil comparison (pure).

Pairs coils by tag (alias-tolerant, reusing ``submittal.pdf_intake.coil_tag_aliases``),
projects the comparison field list (category-keyed: refrigerant fields for DX/HGRH,
fluid fields for water), computes each side's Coil Volume from its own geometry, and
stamps verdicts via ``ambient.compare``. Coils present on only one side are surfaced
LOUDLY with a ``not_compared_reason`` — never silently dropped (mirrors the package
assembler's ``not_inserted_reason``).

Acceptance RANGE rows (Coil Volume Range, Capacity Range) are resolved through an
optional ``range_provider``; absent one, they are ``cannot_evaluate`` — the band is
never invented.
"""
from __future__ import annotations

from typing import Any, Callable

from coilforge.ambient.coil_volume import coil_volume_cuin
from coilforge.ambient.compare import field_verdict, tolerance_label
from coilforge.ambient.model import AmbientComparison, CoilCompare, CompareRow
from coilforge.submittal.candidate import SubmittalCoilCandidate
from coilforge.submittal.pdf_intake import coil_category_of_tag, coil_tag_aliases

# range_provider(kind, baseline, ambient) -> (low, high) acceptable band, or None if no
# rule applies. The band is selected from the BASELINE (design intent); the Ambient value
# is then checked against it. kind in {"coil_volume", "capacity"}.
RangeProvider = Callable[[str, SubmittalCoilCandidate, SubmittalCoilCandidate], "tuple[float, float] | None"]


# One comparison row spec: pull ``group.key`` from each side, compare with ``tol_key``.
class _Spec:
    __slots__ = ("label", "group", "key", "unit", "tol_key")

    def __init__(self, label: str, group: str, key: str, unit: str | None, tol_key: str):
        self.label = label
        self.group = group
        self.key = key
        self.unit = unit
        self.tol_key = tol_key


# Common to every category (geometry / construction / air side).
_COMMON: tuple[_Spec, ...] = (
    _Spec("Fin Surface", "materials_construction", "fin_surface", None, "string"),
    _Spec("Fin Height", "geometry", "finned_height_in", "in", "dim"),
    _Spec("Fin Length", "geometry", "finned_length_in", "in", "dim"),
    _Spec("Rows", "geometry", "rows_deep", None, "count"),
    _Spec("FPI", "geometry", "fins_per_inch", None, "count"),
    _Spec("Feeds", "geometry", "number_of_feeds", None, "count"),
    _Spec("Fin Thickness", "geometry", "fin_thickness_in", "in", "dim"),
    _Spec("Fin Material", "materials_construction", "fin_material", None, "string"),
    _Spec("Tube Thickness", "geometry", "tube_thickness_in", "in", "dim"),
    _Spec("Tube Material", "materials_construction", "tube_material", None, "string"),
    _Spec("Airflow", "airside_conditions", "total_air_flow_cfm", "cfm", "airflow"),
    _Spec("Face Velocity", "airside_conditions", "face_velocity_fpm", "fpm", "face_velocity"),
    _Spec("EAT DB", "airside_conditions", "entering_dry_bulb_f", "degF", "temp"),
    _Spec("Air PD", "performance", "air_pressure_drop_iwg", "iwg", "air_pd"),
)

# DX / HGRH refrigerant-side fields.
_REFRIGERANT: tuple[_Spec, ...] = (
    _Spec("EAT WB", "airside_conditions", "entering_wet_bulb_f", "degF", "temp"),
    _Spec("LAT DB", "airside_conditions", "leaving_dry_bulb_f", "degF", "temp"),
    _Spec("Refrigerant", "refrigerant_conditions", "refrigerant", None, "string"),
    _Spec("Liquid Temp", "refrigerant_conditions", "liquid_temp_f", "degF", "temp"),
    _Spec("Evap Temp", "refrigerant_conditions", "evaporating_temp_f", "degF", "temp"),
    _Spec("Cond Temp", "refrigerant_conditions", "condensing_temp_f", "degF", "temp"),
    _Spec("Superheat", "refrigerant_conditions", "superheat_f", "degF", "temp"),
    _Spec("Subcooling", "refrigerant_conditions", "subcooling_f", "degF", "temp"),
    _Spec("Capacity", "performance", "nominal_cooling_capacity_mbh", "MBH", "capacity"),
    _Spec("Refrigerant PD", "performance", "refrigerant_pressure_drop_psi", "psi", "refrigerant_pd"),
)

# Water (Hot/Chilled) fluid-side fields — minimal until a Terra V water reference is
# seeded; capacity still compared.
_FLUID: tuple[_Spec, ...] = (
    _Spec("LAT DB", "airside_conditions", "leaving_dry_bulb_f", "degF", "temp"),
    _Spec("Fluid Flow", "airside_conditions", "fluid_flow_rate_gpm", "gpm", "airflow"),
    _Spec("Fluid Ent Temp", "airside_conditions", "fluid_entering_temp_f", "degF", "temp"),
    _Spec("Fluid Lvg Temp", "airside_conditions", "fluid_leaving_temp_f", "degF", "temp"),
    _Spec("Capacity", "performance", "nominal_cooling_capacity_mbh", "MBH", "capacity"),
)

_WATER_CATEGORIES = frozenset({"Hot Water Coil", "Chilled Water Coil"})


def _val(cand: SubmittalCoilCandidate, group: str, key: str) -> Any:
    fv = getattr(cand, group, {}).get(key)
    return fv.value if fv is not None else None


def _coil_volume(cand: SubmittalCoilCandidate) -> float | None:
    return coil_volume_cuin(
        feeds=_val(cand, "geometry", "number_of_feeds"),
        fin_height=_val(cand, "geometry", "finned_height_in"),
        rows=_val(cand, "geometry", "rows_deep"),
        fin_length=_val(cand, "geometry", "finned_length_in"),
        tube_thickness_in=_val(cand, "geometry", "tube_thickness_in"),
        tube_od_in=_val(cand, "geometry", "tube_od_in") or 0.375,
    )


def _tag_of(cand: SubmittalCoilCandidate) -> str | None:
    return cand.tag.value if cand.tag is not None else None


def _specs_for_category(category: str | None) -> tuple[_Spec, ...]:
    if category in _WATER_CATEGORIES:
        return _COMMON + _FLUID
    return _COMMON + _REFRIGERANT


def _range_row(
    label: str,
    kind: str,
    ambient_value: float | None,
    unit: str,
    range_provider: RangeProvider | None,
    baseline_cand: SubmittalCoilCandidate,
    ambient_cand: SubmittalCoilCandidate,
) -> CompareRow:
    """A Coil-Volume / Capacity Range row: is Ambient's value inside the acceptable band?"""
    band = range_provider(kind, baseline_cand, ambient_cand) if range_provider is not None else None
    if band is None:
        return CompareRow(
            label=label, group="range", key=kind, baseline=None, ambient=ambient_value,
            unit=unit, verdict="cannot_evaluate",
            tolerance="acceptance band",
            note="acceptance band pending the Coil Utilities range table",
        )
    low, high = band
    if ambient_value is None:
        verdict = "missing_one"
    else:
        verdict = "match" if low <= ambient_value <= high else "mismatch"
    return CompareRow(
        label=label, group="range", key=kind, baseline=f"{low:.1f}–{high:.1f}",
        ambient=round(ambient_value, 2) if ambient_value is not None else None,
        unit=unit, verdict=verdict,
        tolerance=f"[{low:.1f}, {high:.1f}]",
        note=None,
    )


def _build_rows(
    baseline: SubmittalCoilCandidate,
    ambient: SubmittalCoilCandidate,
    category: str | None,
    range_provider: RangeProvider | None,
) -> tuple[CompareRow, ...]:
    rows: list[CompareRow] = []

    # Skip a spec entirely when BOTH sides lack it (keeps water/refrigerant branches
    # from emitting a wall of both_missing rows for the other branch's fields).
    for spec in _specs_for_category(category):
        b = _val(baseline, spec.group, spec.key)
        a = _val(ambient, spec.group, spec.key)
        if b is None and a is None:
            continue
        rows.append(
            CompareRow(
                label=spec.label, group=spec.group, key=spec.key,
                baseline=b, ambient=a, unit=spec.unit,
                verdict=field_verdict(b, a, spec.tol_key),
                tolerance=tolerance_label(spec.tol_key),
            )
        )

    # Coil Volume — computed from each side's own geometry (mirrors the two Excel columns).
    b_vol = _coil_volume(baseline)
    a_vol = _coil_volume(ambient)
    if b_vol is not None or a_vol is not None:
        rows.append(
            CompareRow(
                label="Coil Volume", group="derived", key="coil_volume_cuin",
                baseline=round(b_vol, 2) if b_vol is not None else None,
                ambient=round(a_vol, 2) if a_vol is not None else None,
                unit="in^3", verdict=field_verdict(b_vol, a_vol, "coil_volume"),
                tolerance=tolerance_label("coil_volume"),
            )
        )
        rows.append(_range_row("Coil Volume Range", "coil_volume", a_vol, "in^3", range_provider, baseline, ambient))

    # Capacity Range — the acceptance band for Ambient's returned capacity.
    a_cap = _val(ambient, "performance", "nominal_cooling_capacity_mbh")
    rows.append(_range_row("Capacity Range", "capacity", a_cap, "MBH", range_provider, baseline, ambient))

    return tuple(rows)


def build_ambient_comparison(
    baseline: list[SubmittalCoilCandidate],
    ambient: list[SubmittalCoilCandidate],
    *,
    range_provider: RangeProvider | None = None,
) -> AmbientComparison:
    """Pair baseline<->Ambient by tag and build the per-coil comparison."""
    warnings: list[str] = []
    coils: list[CoilCompare] = []

    ambient_by_tag: dict[str, SubmittalCoilCandidate] = {}
    for cand in ambient:
        tag = _tag_of(cand)
        if tag:
            ambient_by_tag[tag.upper()] = cand
        warnings.extend(n for n in cand.notes if n.startswith("ambient_"))

    matched_ambient: set[str] = set()

    for b in baseline:
        b_tag = _tag_of(b)
        if not b_tag:
            continue
        match = None
        for alias in coil_tag_aliases(b_tag):
            if alias.upper() in ambient_by_tag:
                match = ambient_by_tag[alias.upper()]
                matched_ambient.add(alias.upper())
                break
        category = coil_category_of_tag(b_tag)
        if match is None:
            coils.append(
                CoilCompare(
                    tag=b_tag, category=category,
                    not_compared_reason=f"no Ambient coil returned for tag {b_tag}",
                )
            )
            continue
        coils.append(
            CoilCompare(tag=b_tag, category=category, rows=_build_rows(b, match, category, range_provider))
        )

    # Ambient coils with no baseline counterpart -> loud, never dropped.
    for tag_upper, cand in ambient_by_tag.items():
        if tag_upper in matched_ambient:
            continue
        real_tag = _tag_of(cand) or tag_upper
        coils.append(
            CoilCompare(
                tag=real_tag, category=coil_category_of_tag(real_tag),
                not_compared_reason=f"Ambient returned coil {real_tag} with no baseline submittal coil",
            )
        )

    return AmbientComparison(coils=tuple(coils), warnings=tuple(dict.fromkeys(warnings)))
