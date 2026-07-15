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

from dataclasses import dataclass, field
from typing import Any

from coilforge.schemas.header_prepopulate import (
    CoilType,
    HeaderPrepopulateRequest,
    HeaderPrepopulateResponse,
    ProductFamily,
    TerraVariant,
)
from coilforge.services.header_prepopulate_engine import prepopulate
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
    "TERRA_H": ProductFamily.TERRA_H,
    "TERRA_V": ProductFamily.TERRA_V,
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
    qty_conn_per_header: int | None = None,
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
        qty_conn_per_header=qty_conn_per_header,
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
) -> tuple[dict[str, Any], list[str]]:
    """HIGH engine values -> slot values; MEDIUM/blocked -> review items.

    geometry_slots are non-engine slots (FH/FL/CH/CL/ROWS/Tag) sourced from the
    coil JSON/canonical record; they are merged in as-is.
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
    for name, result in response.suggestions.items():
        review_items.append(f"suggestion:{name}={result.value} (review)")
    for name, result in response.blocked.items():
        review_items.append(f"blocked:{name} ({result.blocked_reason})")
    for inp in response.missing_inputs:
        review_items.append(f"missing_input:{inp}")
    return slot_values, review_items


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
    "slot.DIST_EXT": "dist_extension",  # supply distributor extension (e.g. 6")
}
# EZ JSON as-built slots override the engine prediction for per-header positions.
_SLOT_EZ_OVERRIDE: tuple[str, ...] = (
    "slot.I1", "slot.S1", "slot.O2", "slot.R2", "slot.SL2", "slot.HD2", "slot.HDx1",
)

# Per-category engine field that feeds each per-header drawing slot. The rule
# engine names this geometry differently by coil type, so the bridge must pick
# the right source field per category instead of assuming DX names:
#   - DX   names the supply header's distributor (dist_*) and the return/suction
#          header (suction_*) separately.
#   - HGRH names supply_*/return_* and a single header depth `hd`; no distributor.
#   - CWC/HWC carry a single shared header geometry (io/hd/sl); no distributor.
# `i`/`o` -> supply/return I-O offsets, `hd` -> return header depth, `sl` ->
# return stub length, `hdx` -> supply header depth (the DX distributor HD, or the
# shared header `hd` for HGRH/CWC/HWC which have no distributor). A missing key
# means that slot has no engine source for the category, so the slot is omitted,
# never guessed. These category->field correspondences are review-required
# mappings (see plan), not auto-confirmed engineering values.
_PER_HEADER_ENGINE_FIELDS: dict[str, dict[str, str]] = {
    "DX": {"i": "dist_i", "hdx": "dist_hd", "o": "suction_io", "hd": "suction_hd", "sl": "suction_sl"},
    "HGRH": {"i": "supply_io", "hdx": "hd", "o": "return_io", "hd": "hd", "sl": "return_sl"},
    "CWC": {"i": "io", "hdx": "hd", "o": "io", "hd": "hd", "sl": "sl"},
    "HWC": {"i": "io", "hdx": "hd", "o": "io", "hd": "hd", "sl": "sl"},
}


def build_drawing_slots(
    *,
    coil_type: str,
    product_type: str,
    unit_size: str,
    rows: int | None = None,
    feeds: int | None = None,
    circuits: int | None = None,
    suction_conn_size: float | None = None,
    conn_size: float | None = None,
    qty_conn_per_header: int | None = None,
    finned_height: float | None = None,
    finned_length: float | None = None,
    tag: str | None = None,
    ez_json: dict[str, Any] | None = None,
    terra_variant: str | None = None,
) -> tuple[dict[str, Any], HeaderPrepopulateResponse]:
    """Resolve EVERY dimension slot from mechanical values (engine/formula/JSON).

    ``terra_variant`` ("TERRA_V" etc.) is threaded so the slot layer can apply the
    Terra V drawing specials (DX S = CD - Rn, HGRH supply SL = 5, CWC return O = CH -
    2.75) and stop the generic R-022 safety net from leaking into Terra V. If omitted,
    ``build_header_request`` still derives it from a "TERRA V" product label.
    """
    # HGRH return spacing R (R-052) consumes `conn_size`. The frozen template path
    # (pdf_to_template_drawing) passes the read connection size only as `suction_conn_size`;
    # route it to `conn_size` for HGRH so R resolves. No-op for the Direct-Coil path, which
    # already sets conn_size. Unblocks Terra V HGRH R specifically — its slot-layer R safety
    # net is off (`and not is_terra_v`), unlike Terra H/Nova/VH which the net already rescued.
    if (
        str(coil_type or "").strip().upper() == "HGRH"
        and conn_size is None
        and suction_conn_size is not None
    ):
        conn_size = suction_conn_size
    request = build_header_request(
        coil_type=coil_type, product_type=product_type, unit_size=unit_size,
        rows=rows, feeds=feeds, circuits=circuits, suction_conn_size=suction_conn_size,
        conn_size=conn_size, qty_conn_per_header=qty_conn_per_header,
        terra_variant=terra_variant,
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

    # DX distributor orientation (R-031 DOWN / R-032 UP) is a HIGH engine value but a
    # STRING, not a dimension, so it rides its own slot rather than _SLOT_ENGINE_FIELD.
    # Surfacing it lets the parametric drawing engine redraw the distributor on the
    # correct side (Ventum+ = UP). Emitted only when the engine resolved it (DX only —
    # HGRH/CWC/HWC have no distributor), never invented.
    orientation = val("dist_orientation")
    if orientation is not None:
        slots["slot.DIST_ORIENTATION"] = orientation

    # 2. Recovered formulas (confirmed against reference cases).
    tf, bf, cd, rb = val("top_flange"), val("bottom_flange"), val("casing_depth"), val("return_bend")
    if cd is None:
        # HGRH multi-circuit casing_depth is MEDIUM (R-073, suggestions) when conn_size is
        # given. Surface it so supply S / SL populate — same review-aid policy as the
        # return_spacing R-052 fallback below (cd feeds only slot.S/slot.SL here).
        sug = response.suggestions.get("casing_depth")
        cd = sug.value if sug is not None else None
    if finned_height is not None:
        slots["slot.FH"] = finned_height
        if tf is not None and bf is not None:
            slots["slot.CH"] = round(finned_height + tf + bf, 4)        # CH = FH+TF+BF
    if finned_length is not None:
        slots["slot.FL"] = finned_length
        slots["slot.CL"] = round(finned_length + 3, 4)                  # CL = FL+3
        # OAL = FL + RB + HD2 is emitted after the per-header loop / EZ override below,
        # once slot.HD2 (return/suction header depth) is resolved (John 2026-06-29).
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
    # Source the per-header geometry from the fields THIS coil category emits
    # (DX dist_*/suction_*, HGRH supply_*/return_*/hd, CWC/HWC io/hd/sl). Without
    # this the bridge only read DX field names, so every non-DX category left
    # I/O/HD/SL (and HDx) blocked even when the engine had resolved them.
    field_map = _PER_HEADER_ENGINE_FIELDS.get(
        str(coil_type or "").strip().upper(), _PER_HEADER_ENGINE_FIELDS["DX"]
    )
    is_hgrh = str(coil_type or "").strip().upper() == "HGRH"
    is_cwc_hwc = str(coil_type or "").strip().upper() in ("CWC", "HWC")
    is_terra_v = request.terra_variant == TerraVariant.TERRA_V
    hdr_i = val(field_map["i"]) if "i" in field_map else None
    hdr_hdx = val(field_map["hdx"]) if "hdx" in field_map else None
    hdr_o = val(field_map["o"]) if "o" in field_map else None
    hdr_hd = val(field_map["hd"]) if "hd" in field_map else None
    hdr_sl = val(field_map["sl"]) if "sl" in field_map else None
    return_spacing = val("return_spacing")  # R-022 per-circuit list (HIGH) or None
    if return_spacing is None:
        # HGRH R-052 emits return_spacing at MEDIUM (suggestions). John 2026-06-25:
        # display it on the review-aid drawing as a review-required value. This does
        # not touch the confidence gate — the drawing layer is choosing to surface a
        # suggestion (export_allowed stays False; the value is already a review item).
        sug = response.suggestions.get("return_spacing")
        return_spacing = sug.value if sug is not None else None
    if circuits:
        for k in range(1, circuits + 1):
            supply_id, return_id = 2 * k - 1, 2 * k
            if hdr_i is not None:
                slots[f"slot.I{supply_id}"] = hdr_i
            if hdr_hdx is not None:
                slots[f"slot.HDx{supply_id}"] = hdr_hdx
            if cd is not None:
                if (
                    is_terra_v
                    and isinstance(return_spacing, list)
                    and k <= len(return_spacing)
                ):
                    # Terra V DX: distributor S = CD - Rn (SOP), where Rn is the Terra V
                    # return spacing (R-023). Replaces the checklist even-spacing.
                    slots[f"slot.S{supply_id}"] = round(cd - return_spacing[k - 1], 4)
                else:
                    slots[f"slot.S{supply_id}"] = round(k * cd / (circuits + 1), 4)
                # HGRH supply-side (odd) SL = stub POSITION = 6 + return_conn/2 - S
                # (John 2026-06-26). Sn is the per-slot drawing S just computed (differs
                # per slot). The even SL (length) stays the return_sl clearance. HGRH only;
                # conn_size carries the return connection size.
                if is_hgrh and conn_size is not None:
                    if is_terra_v:
                        # Terra V HGRH: all Supply SL = 5 (SOP), not the position formula.
                        slots[f"slot.SL{supply_id}"] = 5
                    else:
                        slots[f"slot.SL{supply_id}"] = round(
                            6 + conn_size / 2 - slots[f"slot.S{supply_id}"], 4
                        )
            if hdr_o is not None:
                if (
                    is_terra_v
                    and is_cwc_hwc
                    and slots.get("slot.CH") is not None
                ):
                    # Terra V CWC/HWC: Return I/O = CH - 2.75 (SOP) — levels the return
                    # stubout with the supply stubout. Supply I/O stays 2.75 (engine io).
                    slots[f"slot.O{return_id}"] = round(slots["slot.CH"] - 2.75, 4)
                else:
                    slots[f"slot.O{return_id}"] = hdr_o
            if hdr_hd is not None:
                slots[f"slot.HD{return_id}"] = hdr_hd
            if hdr_sl is not None:
                # Even/return slot = return_sl clearance (Terra V HGRH: 12 via R-046). The
                # supply reheat stub (SL{odd}=5) now has its OWN redacted SL1 callout in the
                # HGRH header1 template, so the old force-SL2=5 workaround (John 2026-07-02)
                # is removed — the return callout shows the true return_sl again (2026-07-03).
                slots[f"slot.SL{return_id}"] = hdr_sl
            if isinstance(return_spacing, list) and k <= len(return_spacing):
                slots[f"slot.R{return_id}"] = round(return_spacing[k - 1], 4)
            elif suction_conn_size is not None and not is_terra_v:
                # Safety net when the engine list is absent: the documented R-022
                # formula Rn = n*D + (n-1)*1.5 for every circuit (not just k==1), so
                # R4/R6 populate instead of leaving the second/third header blank.
                # Excluded for Terra V — it uses its own R-023 formula, never the generic.
                slots[f"slot.R{return_id}"] = round(
                    k * suction_conn_size + (k - 1) * 1.5, 4
                )

    # 3. EZ JSON as-built override for per-header positions (exact; multi-circuit).
    if ez_json:
        from coilforge.services.ez_json_drawing_loader import slots_from_ez_json

        json_slots, _ = slots_from_ez_json(ez_json)
        for slot in _SLOT_EZ_OVERRIDE:
            if slot in json_slots:
                slots[slot] = json_slots[slot]

    # 4. OAL = FL + RB + HD2 (return/suction header depth) — John 2026-06-29, all coils.
    # Computed from the FINAL drawn slot values (after the per-header loop and the EZ
    # override) so OAL always matches the HD2 the drawing shows. If HD2 is absent (e.g.
    # single-feed water coils where HD = "N/A"), OAL is omitted, never guessed.
    oal_fl, oal_rb, oal_hd = slots.get("slot.FL"), slots.get("slot.RB"), slots.get("slot.HD2")
    if all(isinstance(x, (int, float)) for x in (oal_fl, oal_rb, oal_hd)):
        slots["slot.OAL"] = round(oal_fl + oal_rb + oal_hd, 4)

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
        conn_size=request_inputs.get("conn_size"),
        qty_conn_per_header=request_inputs.get("qty_conn_per_header"),
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

    # step 4 — select + populate template. Prefer a dedicated per-family template when
    # one is seeded (e.g. Ventum+ DX with its ConnectionUP distributor); falls back to
    # the shared bucket when none exists (two-pass match in select_drawing_template).
    dpl_family, _ = resolve_product_line(product_type)
    selection = select_drawing_template(
        TemplateSelectionRequest(
            supplier=supplier,
            coil_category=coil_type,
            coil_hand=hand,
            header_type=header_type,
            product_family=dpl_family,
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
