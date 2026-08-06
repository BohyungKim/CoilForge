from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from coilforge.direct_coil.draft import DirectCoilDraftField, DirectCoilInputDraft


PasteReadyFieldStatus = Literal[
    "ready",
    "review_required",
    "blocked",
    "unmapped",
    "calculated_read_only",
    "not_applicable",
]

# Logical second-header columns. They exist only for multi-header (2HD+) DX/HGRH
# coils; on a single-header (1HD) coil — which includes every CWC/HWC — there is
# no second header, so these read "N/A" rather than "source needed".
_SECONDARY_HEADER_KEYS = frozenset({"i2", "s2", "o2", "r2", "hd2", "zd2"})

PasteReadyFieldKind = Literal[
    "text",
    "dropdown",
    "checkbox",
    "calculated",
    "read_only",
]


class DirectCoilPasteField(BaseModel):
    """Copy/paste-facing Direct Coil field row for review aid workflows only."""

    model_config = ConfigDict(extra="forbid")

    section: str
    order: int
    direct_coil_label: str
    normalized_key: str
    value: Any = None
    display_value: str
    status: PasteReadyFieldStatus
    notes: str
    source_evidence_refs: list[str] = Field(default_factory=list)
    copy_enabled: bool
    field_kind: PasteReadyFieldKind


class DirectCoilPasteReadySurface(BaseModel):
    """Review-only paste surface. This is not a Direct Coil export payload."""

    model_config = ConfigDict(extra="forbid")

    draft_id: str
    source_canonical_record_id: str
    review_packet_status: str = "quote_prep_review_only"
    total_fields: int
    summary_counts: dict[str, int]
    fields: list[DirectCoilPasteField]
    raw_private_data_returned: bool = False
    final_export_enabled: bool = False
    pdf_export_enabled: bool = False
    production_drawing_approval_claimed: bool = False


@dataclass(frozen=True)
class _PasteFieldSpec:
    order: int
    section: str
    label: str
    normalized_key: str
    draft_field_key: str | None = None
    field_kind: PasteReadyFieldKind = "text"
    calculated_read_only: bool = False
    notes: str = ""


_F = "\N{DEGREE SIGN}F"
_FT2_F = "ft\N{SUPERSCRIPT TWO} \N{DEGREE SIGN}F h/Btu"


DIRECT_COIL_PASTE_FIELD_ORDER: tuple[_PasteFieldSpec, ...] = (
    _PasteFieldSpec(1, "DX COIL DATA", "Tag", "tag"),
    _PasteFieldSpec(2, "DX COIL DATA", "Coil Quantity", "coil_quantity", "coil_quantity"),
    _PasteFieldSpec(
        3,
        "DX COIL DATA",
        "Tube Diameter (standard at top)",
        "tube_diameter_standard_at_top",
        "tube_diameter_od",
        "dropdown",
    ),
    _PasteFieldSpec(4, "DX COIL DATA", "Tubes High", "tubes_high", "tubes_high"),
    _PasteFieldSpec(5, "DX COIL DATA", "Finned Height(In)", "finned_height_in", "finned_height"),
    _PasteFieldSpec(6, "DX COIL DATA", "Finned Length(In)", "finned_length_in", "finned_length"),
    _PasteFieldSpec(7, "DX COIL DATA", "Rows Deep", "rows_deep", "rows_deep"),
    _PasteFieldSpec(8, "DX COIL DATA", "Fins Per Inch", "fins_per_inch", "fins_per_inch"),
    _PasteFieldSpec(
        9,
        "DX COIL DATA",
        "Number Of Feeds(Total)",
        "number_of_feeds_total",
        "number_of_feeds",
    ),
    _PasteFieldSpec(10, "OPTIONS", "Tube Material", "tube_material", "tube_material", "dropdown"),
    _PasteFieldSpec(11, "OPTIONS", "Fin Material", "fin_material", "fin_material", "dropdown"),
    _PasteFieldSpec(12, "OPTIONS", "Fin Surface", "fin_surface", "fin_surface", "dropdown"),
    _PasteFieldSpec(13, "OPTIONS", "Header Material", "header_material", "header_material", "dropdown"),
    _PasteFieldSpec(14, "OPTIONS", "Header Wall Schedule", "header_wall_schedule", field_kind="dropdown"),
    _PasteFieldSpec(
        15,
        "OPTIONS",
        "Connection Material",
        "connection_material",
        "connection_material",
        "dropdown",
    ),
    _PasteFieldSpec(16, "OPTIONS", "Connection Type", "connection_type", "connection_type", "dropdown"),
    _PasteFieldSpec(
        17,
        "OPTIONS",
        "Return Connection Size",
        "return_connection_size",
        "return_connection_size",
    ),
    _PasteFieldSpec(18, "OPTIONS", "Casing Style", "casing_style", "casing_style", "dropdown"),
    _PasteFieldSpec(19, "OPTIONS", "Casing Material", "casing_material", "casing_material", "dropdown"),
    _PasteFieldSpec(20, "OPTIONS", "Connection Ends", "connection_ends", "connection_ends", "dropdown"),
    _PasteFieldSpec(21, "OPTIONS", "Coil Coating", "coil_coating", "coil_coating", "dropdown"),
    _PasteFieldSpec(22, "OPTIONS", "Coil Hand", "coil_hand", "coil_hand", "dropdown"),
    _PasteFieldSpec(23, "OPTIONS", "System Type", "system_type", "system_type", "dropdown"),
    _PasteFieldSpec(24, "OPTIONS", "Drain Pan Type", "drain_pan_type", "drain_pan_type", "dropdown"),
    _PasteFieldSpec(25, "OPTIONS", "Drain Pan Material", "drain_pan_material", field_kind="dropdown"),
    _PasteFieldSpec(26, "OPTIONS", "Drawing Notes", "drawing_notes", "distributor_notes"),
    _PasteFieldSpec(
        27,
        "AIR DATA",
        "Total Air Flow(CFM)",
        "total_air_flow_cfm",
        "total_air_flow_cfm",
        notes="Adjacent Direct Coil airflow dropdown is not tracked by the draft unless separately mapped.",
    ),
    _PasteFieldSpec(28, "AIR DATA", "Air Flow Per Coil(CFM)", "air_flow_per_coil_cfm"),
    _PasteFieldSpec(29, "AIR DATA", "Face Velocity(FPM)", "face_velocity_fpm", "face_velocity_fpm", "read_only"),
    _PasteFieldSpec(30, "AIR DATA", "Altitude(FT)", "altitude_ft", "altitude_ft"),
    _PasteFieldSpec(31, "AIR DATA", f"Entering Dry Bulb({_F})", "entering_dry_bulb_f", "entering_dry_bulb_f"),
    _PasteFieldSpec(32, "AIR DATA", f"Entering Wet Bulb({_F})", "entering_wet_bulb_f", "entering_wet_bulb_f"),
    _PasteFieldSpec(
        33,
        "AIR DATA",
        "Entering Relative Humidity(%)",
        "entering_relative_humidity_pct",
        "relative_humidity_pct",
    ),
    _PasteFieldSpec(34, "AIR DATA", f"Leaving Dry Bulb({_F})", "leaving_dry_bulb_f", "leaving_dry_bulb_f"),
    _PasteFieldSpec(
        35,
        "AIR DATA",
        "Total Capacity(MBH)(Per Coil)",
        "total_capacity_mbh_per_coil",
        "total_capacity_mbh",
        "calculated",
        calculated_read_only=True,
    ),
    _PasteFieldSpec(36, "REFRIGERANT DATA", "Refrigerant", "refrigerant", "refrigerant", "dropdown"),
    _PasteFieldSpec(
        37,
        "REFRIGERANT DATA",
        f"Evaporating Temperature({_F})",
        "evaporating_temperature_f",
        "evaporating_temp_f",
    ),
    _PasteFieldSpec(
        38,
        "REFRIGERANT DATA",
        f"Liquid Temperature({_F})",
        "liquid_temperature_f",
        "liquid_temp_f",
    ),
    _PasteFieldSpec(39, "REFRIGERANT DATA", f"Superheat({_F})", "superheat_f", "superheat_f"),
    _PasteFieldSpec(
        40,
        "REFRIGERANT DATA",
        "DXDistCapillarySize",
        "dx_dist_capillary_size",
        "dx_dist_capillary_size",
    ),
    _PasteFieldSpec(
        41,
        "REFRIGERANT DATA",
        "Refrigerant Velocity (connection)",
        "refrigerant_velocity_connection",
        field_kind="calculated",
        calculated_read_only=True,
    ),
    _PasteFieldSpec(
        42,
        "REFRIGERANT DATA",
        "Refrigerant Pressure Drop",
        "refrigerant_pressure_drop",
        field_kind="calculated",
        calculated_read_only=True,
    ),
    _PasteFieldSpec(
        43,
        "REFRIGERANT DATA",
        "Refrigerant Mass Flow",
        "refrigerant_mass_flow",
        field_kind="calculated",
        calculated_read_only=True,
    ),
    _PasteFieldSpec(44, "FOULING FACTORS", f"Air Side Fouling Factor({_FT2_F})", "air_side_fouling_factor"),
    _PasteFieldSpec(45, "DRAWING / DIMENSION FIELDS", "CD", "cd", "CD"),
    _PasteFieldSpec(46, "DRAWING / DIMENSION FIELDS", "BF", "bf", "BF"),
    _PasteFieldSpec(47, "DRAWING / DIMENSION FIELDS", "TF", "tf", "TF"),
    _PasteFieldSpec(48, "DRAWING / DIMENSION FIELDS", "RF", "rf", "RF"),
    _PasteFieldSpec(49, "DRAWING / DIMENSION FIELDS", "HF", "hf", "HF"),
    _PasteFieldSpec(50, "DRAWING / DIMENSION FIELDS", "CH", "ch", "CH"),
    _PasteFieldSpec(51, "DRAWING / DIMENSION FIELDS", "SL", "sl", "SL"),
    _PasteFieldSpec(52, "DRAWING / DIMENSION FIELDS", "Connections", "connections"),
    _PasteFieldSpec(53, "DRAWING / DIMENSION FIELDS", "Mounting Holes", "mounting_holes"),
    _PasteFieldSpec(54, "DRAWING / DIMENSION FIELDS", "I", "i", "I"),
    _PasteFieldSpec(55, "DRAWING / DIMENSION FIELDS", "S", "s", "S"),
    _PasteFieldSpec(56, "DRAWING / DIMENSION FIELDS", "O", "o", "O"),
    _PasteFieldSpec(57, "DRAWING / DIMENSION FIELDS", "R", "r", "R"),
    _PasteFieldSpec(58, "DRAWING / DIMENSION FIELDS", "HD", "hd", "HD"),
    _PasteFieldSpec(59, "DRAWING / DIMENSION FIELDS", "ZD", "zd", "ZD"),
    _PasteFieldSpec(60, "DRAWING / DIMENSION FIELDS", "I2", "i2"),
    _PasteFieldSpec(61, "DRAWING / DIMENSION FIELDS", "S2", "s2"),
    _PasteFieldSpec(62, "DRAWING / DIMENSION FIELDS", "O2", "o2"),
    _PasteFieldSpec(63, "DRAWING / DIMENSION FIELDS", "R2", "r2"),
    _PasteFieldSpec(64, "DRAWING / DIMENSION FIELDS", "HD2", "hd2"),
    _PasteFieldSpec(65, "DRAWING / DIMENSION FIELDS", "ZD2", "zd2"),
    _PasteFieldSpec(66, "DRAWING / DIMENSION FIELDS", "Distributor Lead Area Max X", "distributor_lead_area_max_x"),
    _PasteFieldSpec(67, "DRAWING / DIMENSION FIELDS", "Distributor Lead Area Max Y", "distributor_lead_area_max_y"),
    _PasteFieldSpec(68, "DRAWING / DIMENSION FIELDS", "Cycle Valve Lead Length", "cycle_valve_lead_length"),
    _PasteFieldSpec(
        69,
        "DRAWING / DIMENSION FIELDS",
        "Apply Venting and Draining I/O Constraints",
        "apply_venting_and_draining_io_constraints",
        field_kind="checkbox",
    ),
    _PasteFieldSpec(
        70,
        "DRAWING / DIMENSION FIELDS",
        "Limit S/R to Standard Positions (for ease of manufacture)",
        "limit_s_r_to_standard_positions",
        field_kind="checkbox",
    ),
)


def _header_count(draft: DirectCoilInputDraft) -> int | None:
    """Header count from the draft's ``header_type`` ("Header 1" -> 1). ``None``
    when it is absent, so applicability is left unchanged (fail-open)."""
    field = draft.fields.get("header_type")
    if field is None or field.value in (None, ""):
        return None
    match = re.search(r"\d+", str(field.value))
    return int(match.group()) if match else None


def build_direct_coil_paste_ready_surface(
    draft: DirectCoilInputDraft,
) -> DirectCoilPasteReadySurface:
    header_count = _header_count(draft)
    fields = [
        _build_paste_field(spec, draft, header_count)
        for spec in DIRECT_COIL_PASTE_FIELD_ORDER
    ]
    return DirectCoilPasteReadySurface(
        draft_id=draft.draft_id,
        source_canonical_record_id=draft.source_canonical_record_id,
        total_fields=len(fields),
        summary_counts=_summarize(fields),
        fields=fields,
    )


def _build_paste_field(
    spec: _PasteFieldSpec,
    draft: DirectCoilInputDraft,
    header_count: int | None = None,
) -> DirectCoilPasteField:
    draft_field = (
        draft.fields.get(spec.draft_field_key)
        if spec.draft_field_key is not None
        else None
    )
    if draft_field is None and spec.draft_field_key == "coil_quantity":
        draft_field = draft.coil_quantity
    status = _paste_status(spec, draft_field)
    # A single-header (1HD) coil has no second header, so its 2nd-header columns
    # are not applicable — flag them rather than reading as "source needed".
    if (
        header_count is not None
        and header_count <= 1
        and spec.normalized_key in _SECONDARY_HEADER_KEYS
    ):
        status = "not_applicable"
    value = None if draft_field is None else draft_field.value
    return DirectCoilPasteField(
        section=spec.section,
        order=spec.order,
        direct_coil_label=spec.label,
        normalized_key=spec.normalized_key,
        value=value,
        display_value=_display_value(status, value),
        status=status,
        notes=_notes(spec, status, draft_field),
        source_evidence_refs=_source_evidence_refs(draft_field),
        copy_enabled=status in {"ready", "review_required"} and value not in (None, ""),
        field_kind=spec.field_kind,
    )


def _paste_status(
    spec: _PasteFieldSpec,
    draft_field: DirectCoilDraftField | None,
) -> PasteReadyFieldStatus:
    if spec.calculated_read_only:
        return "calculated_read_only"
    if draft_field is None:
        return "unmapped"
    if draft_field.status == "manual_override":
        return "review_required"
    if draft_field.status in {"ready", "review_required", "blocked", "unmapped"}:
        return draft_field.status
    return "review_required"


def _display_value(status: PasteReadyFieldStatus, value: Any) -> str:
    if status == "not_applicable":
        return "N/A - SINGLE HEADER (1HD)"
    if value not in (None, ""):
        return str(value)
    if status == "blocked":
        return "DO NOT PASTE - REVIEW REQUIRED"
    if status == "unmapped":
        return "UNMAPPED - SOURCE NEEDED"
    if status == "calculated_read_only":
        return "CALCULATED IN DIRECT COIL - READ ONLY"
    return ""


def _notes(
    spec: _PasteFieldSpec,
    status: PasteReadyFieldStatus,
    draft_field: DirectCoilDraftField | None,
) -> str:
    notes: list[str] = []
    if spec.notes:
        notes.append(spec.notes)
    if status == "ready":
        notes.append("Review aid only; copy the value field-by-field.")
    elif status == "review_required":
        notes.append("Human review required before paste/use.")
    elif status == "blocked":
        reason = draft_field.blocked_reason if draft_field is not None else None
        notes.append(f"DO NOT PASTE - REVIEW REQUIRED: {reason or 'blocked field'}")
    elif status == "unmapped":
        notes.append("UNMAPPED - SOURCE NEEDED.")
    elif status == "calculated_read_only":
        notes.append("Calculated/result field in Direct Coil; not a primary paste input.")
    elif status == "not_applicable":
        notes.append("Not applicable - a single-header (1HD) coil has no 2nd header.")
    if draft_field is not None and draft_field.manual_override:
        notes.append("Manual override metadata must remain review-only.")
    return " ".join(notes)


def _source_evidence_refs(draft_field: DirectCoilDraftField | None) -> list[str]:
    if draft_field is None:
        return []
    return [evidence.evidence_id for evidence in draft_field.source_evidence]


def _summarize(fields: list[DirectCoilPasteField]) -> dict[str, int]:
    counts = {
        "ready": 0,
        "review_required": 0,
        "blocked": 0,
        "unmapped": 0,
        "calculated_read_only": 0,
        "not_applicable": 0,
    }
    for field in fields:
        counts[field.status] += 1
    return counts
