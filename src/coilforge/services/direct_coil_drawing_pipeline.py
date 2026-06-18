"""Track A pipeline: coil inputs -> prepopulated header -> populated draft drawing.

End-to-end glue for the Direct-Coil-with-drawing MVP, for the DX / single-circuit
/ LH slice:

  step 1  build_header_request(...)        coil inputs -> HeaderPrepopulateRequest
  step 2  prepopulate(request)             SOP/checklist header rule engine
  step 3  map_engine_to_slots(...)         engine HIGH values -> template slots
          (via engine_slot_bridge in json_drawing_link_rules.yaml)
  step 4  run_direct_coil_drawing_pipeline select template + populate slots -> SVG

Confidence gate is preserved: only HIGH engine values auto-fill slots; MEDIUM
(suggestions) and LOW/CONFLICT (blocked) are surfaced as review items, never
silently drawn. Output remains a review aid, never manufacturing-approved.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from coilforge.schemas.header_prepopulate import (
    CoilType,
    HeaderPrepopulateRequest,
    HeaderPrepopulateResponse,
    ProductFamily,
    TerraVariant,
)
from coilforge.services.distributor_slots import distributor_drawing_slots
from coilforge.services.header_prepopulate_engine import prepopulate
from coilforge.services.topology_slots import (
    review_and_blocked_items,
    topology_drawing_slots,
)
from coilforge.submittal.coilmaster_drawing_extract import resolve_product_line
from coilforge.services.json_drawing_link import engine_slot_bridge
from coilforge.template_population.catalog import (
    TemplateSelectionRequest,
    select_drawing_template,
)
from coilforge.template_population.slot_population import populate_template_slots

_COIL_TYPE = {"DX": CoilType.DX, "HGRH": CoilType.HGRH, "CWC": CoilType.CWC, "HWC": CoilType.HWC}
_PRODUCT = {
    "NOVA": ProductFamily.NOVA,
    "TERRA": ProductFamily.TERRA,
    "VENTUM_H": ProductFamily.VENTUM_H,
    "VENTUM_PLUS": ProductFamily.VENTUM_PLUS,
}


@dataclass(frozen=True)
class PipelineResult:
    header_response: HeaderPrepopulateResponse
    template_found: bool
    template_id: str | None
    slot_values: dict[str, Any]
    svg: str
    populated_slots: tuple[str, ...]
    missing_required_slots: tuple[str, ...]
    review_items: list[str]
    population_status: str
    blocked_reason: str | None


# --------------------------------------------------------------------------- #
# Step 1 — input bridge
# --------------------------------------------------------------------------- #
def build_header_request(
    *,
    coil_type: str,
    product_type: str,
    unit_size: str,
    rows: int | None = None,
    feeds: int | None = None,
    circuits: int | None = None,
    suction_conn_size: float | None = None,
    conn_size: float | None = None,
    handing: str | None = None,
    coating: str | None = None,
    with_hgrh: bool | None = None,
    hgrh_conn_size: float | None = None,
    hot_gas_bypass: bool | None = None,
    terra_variant: str | None = None,
) -> HeaderPrepopulateRequest:
    """Map coil inputs to a HeaderPrepopulateRequest.

    product_type/unit_size are not on the Direct Coil form (they come from the
    submittal/unit context); the caller supplies them.

    ``product_type`` may be a picker label ("TERRA H" / "TERRA V"); it is
    resolved to the engine product family plus the matching ``terra_variant``,
    so the Terra orientation the engineer chose drives the variant-gated rules.
    An explicit ``terra_variant`` argument overrides the label-derived one.
    """
    family, derived_variant = resolve_product_line(product_type)
    variant_str = terra_variant or derived_variant
    return HeaderPrepopulateRequest(
        type_of_coil=_COIL_TYPE[coil_type.upper()],
        product_type=_PRODUCT[(family or product_type).upper()],
        terra_variant=TerraVariant(variant_str) if variant_str else None,
        unit_size=unit_size,
        rows=rows,
        feeds=feeds,
        circuits=circuits,
        suction_conn_size=suction_conn_size,
        conn_size=conn_size,
        handing=handing,
        coating=coating,
        with_hgrh=with_hgrh,
        hgrh_conn_size=hgrh_conn_size,
        hot_gas_bypass=hot_gas_bypass,
    )


def header_request_from_ez_geometry(
    geometry: dict[str, Any],
    *,
    product_type: str,
    unit_size: str,
    coil_type: str = "DX",
) -> HeaderPrepopulateRequest:
    """Build a request from an EZ Coil 'Geometry' object (rich schema)."""

    def num(key: str) -> float | None:
        value = geometry.get(key)
        return None if value in (None, -1, -1.0) else float(value)

    return build_header_request(
        coil_type=coil_type,
        product_type=product_type,
        unit_size=unit_size,
        rows=int(geometry["Nrows"]) if geometry.get("Nrows", -1) not in (None, -1) else None,
        feeds=int(geometry["Nfeeds"]) if geometry.get("Nfeeds", -1) not in (None, -1) else None,
        circuits=int(geometry["NumCircuits"]) if geometry.get("NumCircuits") else None,
        suction_conn_size=num("ReturnConnectionsSize"),
        handing="LH" if geometry.get("CoilHand") == 1 else "RH",
    )


# --------------------------------------------------------------------------- #
# Step 3 — engine output -> template slots
# --------------------------------------------------------------------------- #
def map_engine_to_slots(
    response: HeaderPrepopulateResponse,
    *,
    geometry_slots: dict[str, Any] | None = None,
    display: Mapping[str, Any] | None = None,
    ez_headers: Sequence[Mapping[str, Any]] | None = None,
    supply_ids: Sequence[int] | None = None,
    coil_category: str | None = None,
    special_feature: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """HIGH engine values -> slot values; MEDIUM/blocked -> review items.

    geometry_slots are non-engine slots (FH/FL/CH/CL/ROWS/Tag) sourced from the
    coil JSON/canonical record; they are merged in as-is.

    When ``display`` (drawing_callouts / distributors_display / airflow_direction) and/or
    ``ez_headers`` are provided, the V3 distributor slots are sourced UPSTREAM via
    :func:`distributor_drawing_slots` (Phase 4a): only its HIGH (``values``) slots merge into
    ``slot_values`` — review/blocked are surfaced as review items, never silently drawn.
    ``supply_ids`` defaults to the odd ``IsSupply`` ids in ``ez_headers`` when omitted.

    When ``coil_category`` is given, the Phase-5a per-category topology slots
    (``slot.conn_angle`` / ``slot.vent_drain`` / ``slot.HGBP`` / ``asc_orientation``) are sourced
    UPSTREAM via :func:`topology_drawing_slots`, gated the same way: HIGH merge into
    ``slot_values``; review/blocked become review items, never silently drawn.
    """
    slot_values: dict[str, Any] = dict(geometry_slots or {})
    for pair in engine_slot_bridge():
        field_name = pair["engine_field"]
        if field_name in response.values:
            value = response.values[field_name].value
            if isinstance(value, list):  # e.g. notes -> join lines
                value = " ".join(str(v) for v in value)
            slot_values[pair["slot"]] = value

    review_items: list[str] = []

    if display is not None or ez_headers is not None or supply_ids is not None:
        ids = list(supply_ids) if supply_ids is not None else _supply_ids_from_headers(ez_headers)
        if ids:
            dist = distributor_drawing_slots(
                engine_response=response, supply_ids=ids,
                ez_headers=ez_headers, display=display,
            )
            slot_values.update(dist.gated_slot_values())  # HIGH only
            for gs in dist.review.values():
                review_items.append(f"review:{gs.slot}={gs.value} ({gs.reason})")
            for gs in dist.blocked.values():
                review_items.append(f"blocked:{gs.slot} ({gs.reason})")
            review_items.extend(dist.notes)

    if coil_category is not None:
        topo = topology_drawing_slots(
            engine_response=response, category=coil_category, special=special_feature,
        )
        slot_values.update(topo.gated_slot_values())  # HIGH only
        review_items.extend(review_and_blocked_items(topo))

    for name, result in response.suggestions.items():
        review_items.append(f"suggestion:{name}={result.value} (review)")
    for name, result in response.blocked.items():
        review_items.append(f"blocked:{name} ({result.blocked_reason})")
    for inp in response.missing_inputs:
        review_items.append(f"missing_input:{inp}")
    return slot_values, review_items


def _supply_ids_from_headers(
    ez_headers: Sequence[Mapping[str, Any]] | None,
) -> list[int]:
    """Odd EZ ids of the supply/distributor headers present (e.g. [1, 3, 5])."""
    ids: list[int] = []
    for h in ez_headers or []:
        if isinstance(h, Mapping) and h.get("IsSupply") and "ID" in h:
            hid = int(h["ID"])
            if hid % 2 == 1:
                ids.append(hid)
    return sorted(ids)


# --------------------------------------------------------------------------- #
# Comprehensive value-driven slot resolver
# --------------------------------------------------------------------------- #
# Every drawing dimension label is driven by a mechanical value: engine HIGH
# value, recovered formula, coil input, or exact EZ JSON (when an export exists).
_SLOT_ENGINE_FIELD: dict[str, str] = {
    "slot.CD": "casing_depth",
    "slot.TF": "top_flange",
    "slot.BF": "bottom_flange",
    "slot.HF": "header_flange",
    "slot.RF": "return_flange",
    "slot.RB": "return_bend",
    "slot.HD2": "suction_hd",   # suction/return header HD
    "slot.HDx1": "dist_hd",     # distributor HD
    "slot.SL2": "suction_sl",
    "slot.I1": "dist_i",        # distributor I
    "slot.O2": "suction_io",    # return I/O
}
# EZ JSON as-built slots override the engine prediction for per-header positions.
_SLOT_EZ_OVERRIDE: tuple[str, ...] = (
    "slot.I1", "slot.S1", "slot.O2", "slot.R2", "slot.SL2", "slot.HD2", "slot.HDx1",
)


def build_drawing_slots(
    *,
    coil_type: str,
    product_type: str,
    unit_size: str,
    rows: int | None = None,
    feeds: int | None = None,
    circuits: int | None = None,
    suction_conn_size: float | None = None,
    finned_height: float | None = None,
    finned_length: float | None = None,
    tag: str | None = None,
    ez_json: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], HeaderPrepopulateResponse]:
    """Resolve EVERY dimension slot from mechanical values (engine/formula/JSON)."""
    request = build_header_request(
        coil_type=coil_type, product_type=product_type, unit_size=unit_size,
        rows=rows, feeds=feeds, circuits=circuits, suction_conn_size=suction_conn_size,
    )
    response = prepopulate(request)
    slots: dict[str, Any] = {}

    def val(field: str) -> Any:
        return response.values[field].value if field in response.values else None

    # 1. Direct engine HIGH values.
    for slot, field in _SLOT_ENGINE_FIELD.items():
        if field in response.values:
            slots[slot] = response.values[field].value
    if "notes" in response.values:
        slots["slot.NOTES"] = " ".join(str(v) for v in response.values["notes"].value)

    # 2. Recovered formulas (confirmed against reference cases).
    tf, bf, cd, rb = val("top_flange"), val("bottom_flange"), val("casing_depth"), val("return_bend")
    if finned_height is not None:
        slots["slot.FH"] = finned_height
        if tf is not None and bf is not None:
            slots["slot.CH"] = round(finned_height + tf + bf, 4)        # CH = FH+TF+BF
    if finned_length is not None:
        slots["slot.FL"] = finned_length
        slots["slot.CL"] = round(finned_length + 3, 4)                  # CL = FL+3
        if rb is not None:
            slots["slot.OAL"] = round(finned_length + 3 + rb, 4)        # OAL (derived/review)
    if rows is not None:
        slots["slot.ROWS"] = rows
    if tag:
        slots["slot.TAG"] = tag

    # 2b. Per-header positions for EVERY circuit (generalizes the old header-1/2
    # emission so multi-circuit coils are logic-derived, not as-built fallback).
    # For circuit k (1..circuits): the supply/distributor header has odd id 2k-1
    # and carries I/HDx/S; the return/suction header has even id 2k and carries
    # O/HD/SL/R. The positional constants (dist_i, dist_hd, suction_io/hd/sl)
    # repeat on every same-parity header; S is the recovered formula
    # k*CD/(circuits+1); R is the engine R-022 per-circuit list (return_spacing).
    # k=1 reproduces the legacy I1/S1/HDx1/O2/R2/HD2/SL2 values exactly.
    dist_i, dist_hd = val("dist_i"), val("dist_hd")
    suction_io, suction_hd, suction_sl = val("suction_io"), val("suction_hd"), val("suction_sl")
    return_spacing = val("return_spacing")  # R-022 per-circuit list (HIGH) or None
    if circuits:
        for k in range(1, circuits + 1):
            supply_id, return_id = 2 * k - 1, 2 * k
            if dist_i is not None:
                slots[f"slot.I{supply_id}"] = dist_i
            if dist_hd is not None:
                slots[f"slot.HDx{supply_id}"] = dist_hd
            if cd is not None:
                slots[f"slot.S{supply_id}"] = round(k * cd / (circuits + 1), 4)
            if suction_io is not None:
                slots[f"slot.O{return_id}"] = suction_io
            if suction_hd is not None:
                slots[f"slot.HD{return_id}"] = suction_hd
            if suction_sl is not None:
                slots[f"slot.SL{return_id}"] = suction_sl
            if isinstance(return_spacing, list) and k <= len(return_spacing):
                slots[f"slot.R{return_id}"] = round(return_spacing[k - 1], 4)
            elif suction_conn_size is not None and k == 1:
                slots[f"slot.R{return_id}"] = suction_conn_size         # fallback: R2 only

    # 3. EZ JSON as-built override for per-header positions (exact; multi-circuit).
    if ez_json:
        from coilforge.services.ez_json_drawing_loader import slots_from_ez_json

        json_slots, _ = slots_from_ez_json(ez_json)
        for slot in _SLOT_EZ_OVERRIDE:
            if slot in json_slots:
                slots[slot] = json_slots[slot]

    return slots, response


def material_title_slots(
    *,
    draft: Any | None = None,
    ez_json: dict[str, Any] | None = None,
    model_number: str | None = None,
    tag: str | None = None,
) -> dict[str, Any]:
    """Material / title-block slots, sourced from the draft and/or EZ JSON."""
    slots: dict[str, Any] = {}

    def draft_val(key: str) -> Any:
        if draft is None:
            return None
        field = draft.fields.get(key)
        return field.value if field and field.value not in (None, "") else None

    # From the Direct Coil draft (submittal/canonical) — string materials.
    for slot, key in {
        "slot.TUBE_MATERIAL": "tube_material",
        "slot.FIN_MATERIAL": "fin_material",
        "slot.CASING_MATERIAL": "casing_material",
        "slot.HEADER_MATERIAL": "header_material",
        "slot.RETURN_CONN_SIZE": "return_connection_size",
        "slot.CIRCUITING": "system_type",
        "slot.DISTRIBUTORS": "distributor_notes",
        "slot.COIL_TUBE_FACE": "finned_height",
    }.items():
        value = draft_val(key)
        if value is not None:
            slots[slot] = value

    # From an EZ Coil export.
    if ez_json:
        geometry = ez_json.get("Geometry")
        if geometry:  # rich schema: materials are supplier enums (skipped), text fields used
            if geometry.get("Distributors"):
                slots["slot.DISTRIBUTORS"] = ", ".join(map(str, geometry["Distributors"]))
            feeds, passes = geometry.get("MultiCircuitCoilFeeds"), geometry.get("MultiCircuitCoilPasses")
            if feeds and passes:
                slots["slot.CIRCUITING"] = f"{feeds[0]} Feed / {passes[0]} Pass"
            if geometry.get("ReturnConnectionsSize"):
                slots["slot.RETURN_CONN_SIZE"] = geometry["ReturnConnectionsSize"]
        else:  # PhysicalData: materials are readable strings
            physical = ez_json.get("PhysicalData") or {}
            construction = ez_json.get("Construction") or {}
            for slot, value in {
                "slot.TUBE_MATERIAL": physical.get("tubeMaterial"),
                "slot.FIN_MATERIAL": physical.get("finMaterial"),
                "slot.CASING_MATERIAL": construction.get("casingMaterial"),
                "slot.HEADER_MATERIAL": construction.get("headerMaterial"),
                "slot.RETURN_CONN_SIZE": physical.get("connectionSize"),
            }.items():
                if value not in (None, ""):
                    slots[slot] = value

    if model_number:
        slots["slot.MODEL_NUMBER"] = model_number
    if tag:
        slots["slot.TAG"] = tag
    return slots


# --------------------------------------------------------------------------- #
# Step 4 — end-to-end
# --------------------------------------------------------------------------- #
def run_direct_coil_drawing_pipeline(
    *,
    coil_type: str,
    product_type: str,
    unit_size: str,
    hand: str,
    header_type: str = "Header 1",
    supplier: str = "coilmaster",
    geometry_slots: dict[str, Any] | None = None,
    ez_json: dict[str, Any] | None = None,
    draft: Any | None = None,
    model_number: str | None = None,
    **request_inputs: Any,
) -> PipelineResult:
    """Run coil inputs -> header engine -> draft drawing for one coil."""
    geo = dict(geometry_slots or {})

    # steps 1-3: build EVERY dimension slot from mechanical values.
    slot_values, response = build_drawing_slots(
        coil_type=coil_type,
        product_type=product_type,
        unit_size=unit_size,
        rows=request_inputs.get("rows"),
        feeds=request_inputs.get("feeds"),
        circuits=request_inputs.get("circuits"),
        suction_conn_size=request_inputs.get("suction_conn_size"),
        finned_height=geo.get("slot.FH"),
        finned_length=geo.get("slot.FL"),
        tag=geo.get("slot.TAG"),
        ez_json=ez_json,
    )
    # material / title-block slots from the coil data.
    slot_values.update(
        material_title_slots(
            draft=draft, ez_json=ez_json, model_number=model_number,
            tag=geo.get("slot.TAG"),
        )
    )
    # Caller-provided slots fill any remaining gaps.
    for key, value in geo.items():
        slot_values.setdefault(key, value)

    _, review_items = map_engine_to_slots(response)

    # step 4 — select + populate template
    selection = select_drawing_template(
        TemplateSelectionRequest(
            supplier=supplier,
            coil_category=coil_type,
            coil_hand=hand,
            header_type=header_type,
        )
    )
    if not selection.found or selection.template_id is None:
        return PipelineResult(
            header_response=response,
            template_found=False,
            template_id=None,
            slot_values=slot_values,
            svg="",
            populated_slots=(),
            missing_required_slots=(),
            review_items=review_items + ["no_matching_template"],
            population_status="blocked",
            blocked_reason=response.blocked_reason,
        )

    populated = populate_template_slots(selection.template_id, slot_values)
    return PipelineResult(
        header_response=response,
        template_found=True,
        template_id=selection.template_id,
        slot_values=slot_values,
        svg=populated.svg,
        populated_slots=populated.populated_slots,
        missing_required_slots=populated.missing_required_slots,
        review_items=review_items,
        population_status=populated.metadata.get("template_population_status", ""),
        blocked_reason=response.blocked_reason,
    )
