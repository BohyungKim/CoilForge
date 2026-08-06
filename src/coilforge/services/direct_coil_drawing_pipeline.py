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
from coilforge.services.header_prepopulate_engine import prepopulate, round_eighth
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


class UnknownCoilInputError(ValueError):
    """A required classification input (coil_type / product_type) is not a known
    value, so the header request cannot be built. Carries the offending ``field``
    and the ``allowed`` set so a caller can prompt the engineer to pick a valid
    value (human-in-the-loop) instead of crashing with a bare KeyError."""

    def __init__(self, field: str, value: Any, allowed: list[str]) -> None:
        self.field = field
        self.value = value
        self.allowed = allowed
        super().__init__(
            f"unknown {field}: {value!r} (allowed: {', '.join(allowed)})"
        )


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
    application: str | None = None,
    header_count: int | None = None,
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
    # Guard the two hard halts: bare dict subscripts raise a bare KeyError on an
    # unknown coil_type / product_type. Convert to a typed error carrying the allowed
    # set so the caller can prompt the engineer to pick a valid value instead of 500ing.
    coil_key = coil_type.upper()
    if coil_key not in _COIL_TYPE:
        raise UnknownCoilInputError("coil_type", coil_type, sorted(_COIL_TYPE))
    product_key = (family or product_type).upper()
    if product_key not in _PRODUCT:
        raise UnknownCoilInputError("product_type", product_type, sorted(_PRODUCT))
    return HeaderPrepopulateRequest(
        type_of_coil=_COIL_TYPE[coil_key],
        product_type=_PRODUCT[product_key],
        terra_variant=TerraVariant(variant_str) if variant_str else None,
        unit_size=unit_size,
        rows=rows,
        feeds=feeds,
        circuits=circuits,
        suction_conn_size=suction_conn_size,
        conn_size=conn_size,
        qty_conn_per_header=qty_conn_per_header,
        application=application,
        header_count=header_count,
        handing=handing,
        coating=coating,
        with_hgrh=with_hgrh,
        hgrh_conn_size=hgrh_conn_size,
        hot_gas_bypass=hot_gas_bypass,
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
) -> tuple[dict[str, Any], list[str]]:
    """HIGH engine values -> slot values; MEDIUM/blocked -> review items.

    geometry_slots are non-engine slots (FH/FL/CH/CL/ROWS/Tag) sourced from the
    coil JSON/canonical record; they are merged in as-is.

    When ``display`` (drawing_callouts / distributors_display / airflow_direction) and/or
    ``ez_headers`` are provided, the V3 distributor slots are sourced UPSTREAM via
    :func:`distributor_drawing_slots` (Phase 4a): only its HIGH (``values``) slots merge into
    ``slot_values`` — review/blocked are surfaced as review items, never silently drawn.
    ``supply_ids`` defaults to the odd ``IsSupply`` ids in ``ez_headers`` when omitted.
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


def _hgrh_supply_s(request, cd: float, conn: float) -> float:  # type: ignore[no-untyped-def]
    """Checklist HGRH!C46 supply S (family-branched), NON-Terra-V only.

    TERRA H / VENTUM+ -> the connection size directly; NOVA / VENTUM H ->
    CD - ((n+2)*conn + (n-1)*1.5), where n = qty_conn_per_header (else circuits).
    Unlike the DX distributor S (k*CD/(circuits+1)), every odd HGRH S is the SAME
    value (the sheet's S1=S3=S5 share one formula), so this is not k-scaled. Terra V
    keeps its own S = CD - Rn path in the caller and never reaches here."""
    if request.product_type == ProductFamily.VENTUM_PLUS or request.terra_variant in (
        TerraVariant.TERRA_H,
        TerraVariant.TERRA_H_C,
    ):
        return round(conn, 4)
    n = request.qty_conn_per_header or request.circuits or 1
    return round(cd - ((n + 2) * conn + (n - 1) * 1.5), 4)


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
    application: str | None = None,
    header_count: int | None = None,
    with_hgrh: bool | None = None,
    hgrh_conn_size: float | None = None,
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
        application=application, header_count=header_count,
        with_hgrh=with_hgrh, hgrh_conn_size=hgrh_conn_size,
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
    is_dx = str(coil_type or "").strip().upper() == "DX"
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
            if hdr_i is not None and not (is_hgrh and is_terra_v and k > 1):
                # Terra V HGRH: R-046 asserts Supply **1** I/O = 2.75 and its own comment
                # says Supply 2/3/4 I/O "is NOT derivable here and stays review-required"
                # (a software default, per the SOP). Broadcasting the Supply-1 constant to
                # every odd header printed 2.75 on headers the SOP declines to specify —
                # exactly the "never invent an engineering value" line. Left blank instead,
                # with the panel naming why (drawing_param_resolver._WITHHELD_REASON...).
                # Scoped to Terra V HGRH: every other line's supply_io comes from rules
                # that DO cover all headers, so their broadcast is unchanged.
                slots[f"slot.I{supply_id}"] = hdr_i
            if hdr_hdx is not None:
                slots[f"slot.HDx{supply_id}"] = hdr_hdx
            if is_cwc_hwc:
                # CWC/HWC supply spacing S = the connection size (John 2026-07-29), and R
                # mirrors it below. This is the SAME shape the rest of the rule family
                # already takes for a SINGLE-connection header -- DX R-022 gives R1 = D and
                # HGRH R-052 gives R = D at n = 1 -- and a water coil is always 1HD with one
                # supply and one return, so it is that case, not a new convention.
                #
                # It replaces an even-spacing fallback (`k*CD/(circuits+1)`) whose own
                # comment admitted there was "no equation to mirror": the checklist sheets
                # carry no S row for water. That fallback matched NONE of the seven seeded
                # water references and printed CD/2 (1.6875 on 2949 Ferguson HHWC-1, where
                # the connection is 1"). It also reconciles SOP R-068 ("leave all S/R as
                # EZ Coil default values") -- the EZ default for a single connection IS the
                # connection size, so honouring the rule and computing this agree.
                #
                # NOTE this is deliberately OUTSIDE the `cd is not None` block below: S no
                # longer needs the casing depth, so a coil whose CD has not resolved still
                # gets S (and therefore R).
                water_conn = conn_size if conn_size is not None else suction_conn_size
                if water_conn is not None:
                    slots[f"slot.S{supply_id}"] = round(water_conn, 4)
            elif cd is not None:
                if (
                    is_terra_v
                    and isinstance(return_spacing, list)
                    and k <= len(return_spacing)
                ):
                    # Terra V DX AND HGRH: distributor/supply S = CD - Rn (SOP), where Rn is
                    # the Terra V return spacing (R-023). Replaces the checklist even-spacing;
                    # this branch wins for Terra V so the checklist-family HGRH S below never
                    # applies to Terra V (guards the SOP-confirmed Terra V geometry).
                    slots[f"slot.S{supply_id}"] = round(cd - return_spacing[k - 1], 4)
                elif is_terra_v and is_hgrh:
                    # Terra V HGRH past the return-spacing list has NO basis for S. Its S is
                    # CD - Rn (SOP, the branch above) and Rn only runs to the connections-
                    # per-header count, so this header has no Rn to subtract. Falling through
                    # reached the generic net below and printed the DX even-spacing
                    # k*CD/(circuits+1) on a REHEAT coil (a 6-circuit Terra V HGRH drew
                    # S5=1.6071 … S11=3.2143). Leave it blank; the panel names why.
                    pass
                elif is_hgrh and not is_terra_v and conn_size is not None:
                    # HGRH supply S is family-branched (checklist HGRH!C46), NOT the DX
                    # even-spacing: TERRA H / VENTUM+ -> conn, NOVA / VENTUM H -> CD-formula.
                    slots[f"slot.S{supply_id}"] = _hgrh_supply_s(request, cd, conn_size)
                elif is_dx:
                    # CHK DX!C46:C49 = ROUND(k*CD/(n+1)*8,0)/8 -- the sheet snaps the
                    # distributor centre to the nearest 1/8 (CD=5.5, n=2 -> 1.875 /
                    # 3.625, NOT 1.8333 / 3.6667). Rounding per-k, not once: the eighths
                    # are not proportional (2 x 1.875 != 3.625). John 2026-07-23.
                    slots[f"slot.S{supply_id}"] = round_eighth(k * cd / (circuits + 1))
                else:
                    # Safety net for a category outside DX/HGRH/CWC/HWC (none today —
                    # water takes the connection-size branch above).
                    slots[f"slot.S{supply_id}"] = round(k * cd / (circuits + 1), 4)
                # HGRH supply-side (odd) SL = stub POSITION:
                # Terra V -> 5 (SOP); single feed/circuit -> 6; else 6 + return_conn/2 - S.
                # The even SL (length) stays the return_sl clearance.
                if is_hgrh and conn_size is not None:
                    if is_terra_v:
                        # Terra V HGRH: all Supply SL = 5 (SOP), not the position formula.
                        slots[f"slot.SL{supply_id}"] = 5
                    elif (feeds if feeds is not None else circuits) == 1:
                        # SINGLE FEED = 6, not the 3 in checklist HGRH!C58 (John 2026-08-06).
                        #
                        # The sheet states this dimension TWICE and disagrees with itself.
                        # C58's dimension row computes 3; C26 (NOTES) emits an "Add Headers
                        # & Stubouts" instruction whenever C14 = 1 -- and all THREE of its
                        # product branches spell out "SL1=6" literally. A single-feed coil
                        # has no supply header of its own, so the header on the drawing IS
                        # the added one, and 6 is that header's dimension.
                        #
                        # Every other source agrees with the note, and only C58 dissents:
                        #   CHK HGRH!C26   "... SupConnAngle=LAS. S1=<C46>. SL1=6. ..." x3
                        #   R-044a         supply_sl = 6  (HGRH NOVA/VENTUM_H, MEDIUM)
                        #   R-044c         supply_sl = 6  (HGRH VENTUM_PLUS, HIGH)
                        #   EZC-0002 / EZC-0010 as-built notes (json_drawing_link_rules)
                        # The engine has been emitting the right number all along -- see
                        # test_engine_supply_sl_agrees_with_slot_layer_single_feed, which
                        # exists so the two can never silently drift apart again.
                        #
                        # This diverges from the sheet on purpose; the divergence is
                        # registered (KD-006..009), not hidden, so the checklist compare
                        # still shows it and John's ruling is what re-labels it.
                        #
                        # Keyed on the SAME value the checklist's "FEEDS/CIRCUITS" cell
                        # holds (feeds, else circuits — see checklist/mapping.py) so the
                        # BRANCH still matches the sheet even where the value no longer
                        # does; a submittal stating only one of the two lands identically.
                        slots[f"slot.SL{supply_id}"] = 6
                    else:
                        # Multi-feed keeps CHK HGRH!C58's position formula unchanged.
                        slots[f"slot.SL{supply_id}"] = round(
                            6 + conn_size / 2 - slots[f"slot.S{supply_id}"], 4
                        )
            if hdr_o is not None:
                # Return I/O = the engine's io value, for EVERY product line including
                # Terra V (John 2026-07-29).
                #
                # Terra V water used to write `CH - 2.75` here, from the SOP's "return
                # CH-2.75". That was a DATUM MISMATCH, and the old comment said as much
                # without noticing: it read "levels the return stubout with the supply
                # stubout" -- and if the two are level, the drawing must print the SAME
                # number on both, because `slot.O{even}` is the stubout I/O callout and
                # carries a 2-3" dimension. `CH - 2.75` is that same physical position
                # expressed from the OPPOSITE datum, so feeding it into this callout
                # printed 34.5 where ~2.75 belongs (2949 Ferguson HHWC-1, John).
                #
                # Evidence: all SEVEN seeded water references read `O{even} == I{odd}`
                # (2.31 = the R-060 stubout I/O), and `O == CH - 2.75` on ZERO of them --
                # across CH 17.00 to 38.75, so it is not a coincidence of one geometry.
                # Terra V was also the ONLY line whose O diverged from its own I.
                # Invisible until 2026-07-28 because the Terra V water drawing was gated.
                slots[f"slot.O{return_id}"] = hdr_o
            if hdr_hd is not None:
                slots[f"slot.HD{return_id}"] = hdr_hd
            if hdr_sl is not None:
                # Even/return slot = return_sl clearance (Terra V HGRH: 12 via R-046). The
                # supply reheat stub (SL{odd}=5) now has its OWN redacted SL1 callout in the
                # HGRH header1 template, so the old force-SL2=5 workaround (John 2026-07-02)
                # is removed — the return callout shows the true return_sl again (2026-07-03).
                slots[f"slot.SL{return_id}"] = hdr_sl
            if is_cwc_hwc:
                # CWC/HWC return spacing R = supply spacing S (John 2026-07-28). A water
                # coil's supply and return headers are symmetric: ALL SEVEN seeded water
                # references read R{even} == S{odd} (and O == I with them) --
                # coilmaster_{hwc,cwc}_{lh,rh} + the three vplus water buckets. There is no
                # `return_spacing` rule for water (R-022/R-023 are DX, R-052 is HGRH), and
                # the generic R-022 safety net below both excludes Terra V and keys off the
                # DX-named suction_conn_size, so water R was left blank on every product
                # line. Guarded on slot.S existing: S needs the connection size, and a coil
                # without one must leave R blank rather than raise. Documented here rather
                # than as a YAML rule because the water S it mirrors is itself a slot-layer
                # value the engine never emits -- same placement as the Terra V
                # `S = CD - Rn` special above.
                # This branch OWNS water R: it deliberately does not fall through to the
                # generic R-022 net below, which would otherwise hand a water coil an
                # R with no S beside it (a value whose supply twin is blank has no basis).
                supply_s = slots.get(f"slot.S{supply_id}")
                if supply_s is not None:
                    slots[f"slot.R{return_id}"] = supply_s
            elif isinstance(return_spacing, list) and k <= len(return_spacing):
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
