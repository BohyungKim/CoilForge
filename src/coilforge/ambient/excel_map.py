"""Pure mapping + model for the Ambient comparison Excel write-back (no I/O).

Builds a per-coil fill for the ``<proj> - Coilmaster-Ambiant Dynamics Coil Comparison.xlsx``
template: column **C** = "ours" (the submittal transcription = Coilmaster/EZ-Coil data) and
column **D** = Ambient's returned data, keyed to the template's real column-B labels.

Load-bearing detail: C and D read DIFFERENT candidate keys for the fin envelope — the
submittal path stores ``geometry.finned_height``/``finned_length`` while the Ambient parser
stores ``finned_height_in``/``finned_length_in`` (see ``_DX_SPECS``/``_HGRH_SPECS`` c_key vs
d_key). The acceptance ranges (C-only) reuse ``ambient.package._acceptance_band`` (the ours/
design band). Never invents: an absent value stays ``None`` -> the writer leaves that cell
blank. Formula cells (Coil Volume; HGRH Super Heat D / Vapor Temp C) are protected in the
writer via ``HasFormula`` — not here.

Pure/testable: no Excel, no COM. Review aid only (``export_allowed=False``).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from coilforge.ambient.package import _acceptance_band
from coilforge.submittal.candidate import SubmittalCoilCandidate
from coilforge.submittal.pdf_intake import coil_category_of_tag, coil_tag_aliases

# Category -> master template sheet. Only DX / HGRH have masters; water coils get no sheet.
_MASTER_SHEET: dict[str, str] = {"DX COIL": "CDXC-1", "HGRH COIL": "RHHGRC-1"}

# (column-B label, candidate group, C key [submittal], D key [ambient]).
# A None key means "not read generically for that side" (e.g. C-only capacity handled below).
_CONSTRUCTION: tuple[tuple[str, str, str | None, str | None], ...] = (
    ("Fin Surface", "materials_construction", "fin_surface", "fin_surface"),
    ("Fin Height [in]", "geometry", "finned_height", "finned_height_in"),
    ("Fin Length [in]", "geometry", "finned_length", "finned_length_in"),
    ("Rows", "geometry", "rows_deep", "rows_deep"),
    ("FPI", "geometry", "fins_per_inch", "fins_per_inch"),
    ("Feeds", "geometry", "number_of_feeds", "number_of_feeds"),
    ("Fin Thickness [in]", "geometry", "fin_thickness_in", "fin_thickness_in"),
    ("Fin Material", "materials_construction", "fin_material", "fin_material"),
    ("Tube Material", "materials_construction", "tube_material", "tube_material"),
)
_AIR_HEAD: tuple[tuple[str, str, str | None, str | None], ...] = (
    ("Airflow [SCFM]", "airside_conditions", "total_air_flow_cfm", "total_air_flow_cfm"),
    ("Face Velocity [FPM]", "airside_conditions", "face_velocity_fpm", "face_velocity_fpm"),
    ("EAT DB [°F]", "airside_conditions", "entering_dry_bulb_f", "entering_dry_bulb_f"),
)
_TAIL: tuple[tuple[str, str, str | None, str | None], ...] = (
    ("Air PD [inWC]", "performance", "air_pressure_drop_iwg", "air_pressure_drop_iwg"),
    ("Refrigerant PD [psi]", "performance", "refrigerant_pressure_drop_psi", "refrigerant_pressure_drop_psi"),
)

_DX_MID: tuple[tuple[str, str, str | None, str | None], ...] = (
    ("EAT WB [°F]", "airside_conditions", "entering_wet_bulb_f", "entering_wet_bulb_f"),
    ("Refrigerant", "refrigerant_conditions", "refrigerant", "refrigerant"),
    ("Liquid Temp [°F]", "refrigerant_conditions", "liquid_temp_f", "liquid_temp_f"),
    ("Evap Temp [°F]", "refrigerant_conditions", "evaporating_temp_f", "evaporating_temp_f"),
    ("Super Heat [°F]", "refrigerant_conditions", "superheat_f", "superheat_f"),
    ("LAT DB [°F]", "airside_conditions", "leaving_dry_bulb_f", "leaving_dry_bulb_f"),
    ("LAT WB [°F]", "airside_conditions", "leaving_wet_bulb_f", "leaving_wet_bulb_f"),
    ("Setpoint LAT DB [°F]", "performance", "operating_setpoint_db_f", "operating_setpoint_db_f"),
)
_HGRH_MID: tuple[tuple[str, str, str | None, str | None], ...] = (
    ("Refrigerant", "refrigerant_conditions", "refrigerant", "refrigerant"),
    ("Cond Temp [°F]", "refrigerant_conditions", "condensing_temp_f", "condensing_temp_f"),
    ("Sub Cooling Temp [°F]", "refrigerant_conditions", "subcooling_f", "subcooling_f"),
    ("Super Heat [°F]", "refrigerant_conditions", "superheat_f", "superheat_f"),
    # C Vapor Temp is a template formula (writer protects it); D is a real value.
    ("Vapor Temp [°F]", "refrigerant_conditions", "vapor_temp_f", "vapor_temp_f"),
    ("LAT DB [°F]", "airside_conditions", "leaving_dry_bulb_f", "leaving_dry_bulb_f"),
    ("Setpoint LAT DB [°F]", "performance", "operating_setpoint_db_f", "operating_setpoint_db_f"),
)

_DX_SPECS = _CONSTRUCTION + _AIR_HEAD + _DX_MID + _TAIL
_HGRH_SPECS = _CONSTRUCTION + _AIR_HEAD + _HGRH_MID + _TAIL

_SPECS_BY_CATEGORY: dict[str, tuple[tuple[str, str, str | None, str | None], ...]] = {
    "DX COIL": _DX_SPECS,
    "HGRH COIL": _HGRH_SPECS,
}
# Capacity is common to both but its C side reads under either label (see _capacity_c).
_CAPACITY_LABEL = "Capacity [MBH]"
_CAPACITY_KEYS = ("nominal_cooling_capacity_mbh", "total_capacity_mbh")


@dataclass(frozen=True)
class ExcelCell:
    """One template row: its exact column-B label + the C (ours) and D (ambient) values."""

    label: str
    c: Any = None
    d: Any = None


@dataclass(frozen=True)
class ExcelSheetFill:
    """One coil's sheet: which master to clone, the cells to write, per-coil warnings."""

    tag: str
    category: str  # "DX COIL" | "HGRH COIL"
    source_sheet: str  # "CDXC-1" | "RHHGRC-1"
    cells: tuple[ExcelCell, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AmbientExcelFill:
    """Project-level fill — a review aid, never an export."""

    sheets: tuple[ExcelSheetFill, ...] = ()
    warnings: tuple[str, ...] = ()
    export_allowed: bool = False
    production_drawing_approval_claimed: bool = False
    review_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "sheets": [
                {**asdict(s), "cells": [asdict(c) for c in s.cells], "warnings": list(s.warnings)}
                for s in self.sheets
            ],
            "warnings": list(self.warnings),
            "export_allowed": self.export_allowed,
            "production_drawing_approval_claimed": self.production_drawing_approval_claimed,
            "review_required": self.review_required,
        }


def _tag_of(cand: SubmittalCoilCandidate | None) -> str | None:
    if cand is None or cand.tag is None:
        return None
    v = cand.tag.value
    return str(v) if v not in (None, "") else None


def _val(cand: SubmittalCoilCandidate | None, group: str, key: str | None) -> Any:
    if cand is None or key is None:
        return None
    fv = getattr(cand, group, {}).get(key)
    return fv.value if fv is not None else None


def _capacity_c(cand: SubmittalCoilCandidate | None) -> Any:
    """Submittal capacity under either label (nominal cooling or total)."""
    for key in _CAPACITY_KEYS:
        v = _val(cand, "performance", key)
        if v is not None:
            return v
    return None


def _fmt_range(band: list[Any] | None) -> str | None:
    if not band or len(band) != 2 or band[0] is None or band[1] is None:
        return None
    return f"{band[0]} - {band[1]}"


def _cells_for(
    category: str,
    baseline: SubmittalCoilCandidate | None,
    ambient: SubmittalCoilCandidate | None,
) -> tuple[ExcelCell, ...]:
    cells: list[ExcelCell] = []
    for label, group, c_key, d_key in _SPECS_BY_CATEGORY[category]:
        cells.append(ExcelCell(label, _val(baseline, group, c_key), _val(ambient, group, d_key)))
    # Capacity: C reads either label; D is the ambient nominal cooling capacity.
    cells.append(
        ExcelCell(_CAPACITY_LABEL, _capacity_c(baseline), _val(ambient, "performance", "nominal_cooling_capacity_mbh"))
    )
    # Acceptance ranges (C-only) from the ours/design band; None -> blank (never invented).
    band = _acceptance_band(baseline, category) if baseline is not None else None
    if band is not None:
        cells.append(ExcelCell("Coil Volume Range [in^3]", _fmt_range(band.get("coil_volume_band_cuin")), None))
        cells.append(ExcelCell("Capacity Range [MBH]", _fmt_range(band.get("capacity_band_mbh")), None))
    return tuple(cells)


def build_ambient_excel_fill(
    baseline: list[SubmittalCoilCandidate],
    ambient: list[SubmittalCoilCandidate],
) -> AmbientExcelFill:
    """Per-coil C(ours)+D(ambient) fill over the UNION of both sides (alias-paired).

    A coil present on only one side still gets a sheet (its column filled, the other blank)
    plus a warning — never silently dropped. Coils whose category has no master sheet
    (water) are surfaced as a warning and get no sheet."""
    ambient_by_tag: dict[str, SubmittalCoilCandidate] = {}
    for cand in ambient:
        tag = _tag_of(cand)
        if tag:
            ambient_by_tag[tag.upper()] = cand

    sheets: list[ExcelSheetFill] = []
    warnings: list[str] = []
    matched_ambient: set[str] = set()

    def _add(tag: str, baseline_c, ambient_c, note: str | None) -> None:
        category = coil_category_of_tag(tag)
        source = _MASTER_SHEET.get(category or "")
        if source is None:
            warnings.append(
                f"{tag}: category {category or 'unknown'!r} has no comparison sheet in the "
                f"template (only DX / HGRH) — skipped."
            )
            return
        sheets.append(
            ExcelSheetFill(
                tag=tag,
                category=category,
                source_sheet=source,
                cells=_cells_for(category, baseline_c, ambient_c),
                warnings=(note,) if note else (),
            )
        )

    for b in baseline:
        b_tag = _tag_of(b)
        if not b_tag:
            warnings.append("A baseline coil has no tag — skipped (review).")
            continue
        match = None
        for alias in coil_tag_aliases(b_tag):
            if alias.upper() in ambient_by_tag:
                match = ambient_by_tag[alias.upper()]
                matched_ambient.add(alias.upper())
                break
        note = None if match is not None else f"no Ambient coil returned for {b_tag} — D column blank"
        _add(b_tag, b, match, note)

    # Ambient coils with no baseline counterpart -> still get a sheet, C blank, loud.
    for tag_upper, cand in ambient_by_tag.items():
        if tag_upper in matched_ambient:
            continue
        real_tag = _tag_of(cand) or tag_upper
        _add(real_tag, None, cand, f"Ambient coil {real_tag} has no baseline submittal coil — C column blank")

    return AmbientExcelFill(sheets=tuple(sheets), warnings=tuple(dict.fromkeys(warnings)))
