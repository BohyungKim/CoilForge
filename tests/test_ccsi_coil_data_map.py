"""CCSI coil-data mapping contract (Rating-mode push, Phase 1).

Pins: the coil-data map is separate from the dimension map, every source key is a real
Direct Coil draft field, computed/locked fields are never pushable, captured mappings
are never pushable, and select values land only on an exact captured option."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ccsi import coil_data_map as cdm  # noqa: E402
from coilforge.ccsi.coil_data_map import (  # noqa: E402
    IDENTITY_KEYS,
    TUBE_SURFACE_SOURCE,
    load_coil_data_map,
    resolve_coil_data,
    summarize,
)
from coilforge.interfaces.direct_coil.fields import (  # noqa: E402
    DIRECT_COIL_FIELD_REGISTRY,
    DRAWING_PARAMETER_FIELD_KEYS,
)

ROOT = Path(__file__).resolve().parents[1]

# The 3025 CDXC-1 draft values as the capture ledger recorded them (draft stage).
LEDGER_3025_CDXC1 = {
    "tag": "CDXC-1",
    "coil_quantity": 1,
    "finned_height": {"value": 30, "status": "review_required"},
    "finned_length": {"value": 33, "status": "review_required"},
    "rows_deep": {"value": 6, "status": "review_required"},
    "fins_per_inch": {"value": 11, "status": "review_required"},
    "number_of_feeds": {"value": 15, "status": "review_required"},
    "tube_material": {"value": "0.016", "status": "review_required"},
    "fin_material": {"value": "0.008", "status": "review_required"},
    "fin_surface": {"value": "Flat", "status": "review_required"},
    "coil_hand": {"value": "Left", "status": "review_required"},
    "return_connection_size": {"value": 1.125, "status": "review_required"},
    "total_air_flow_cfm": {"value": 2660, "status": "review_required"},
    "face_velocity_fpm": {"value": 386.91, "status": "review_required"},
    "altitude_ft": {"value": 10, "status": "review_required"},
    "entering_dry_bulb_f": {"value": 95, "status": "review_required"},
    "entering_wet_bulb_f": {"value": 78, "status": "review_required"},
    "leaving_dry_bulb_f": {"value": 52.18, "status": "review_required"},
    "total_capacity_mbh": {"value": 242.05, "status": "review_required"},
    "refrigerant": {"value": "R-32", "status": "review_required"},
    "evaporating_temp_f": {"value": 43, "status": "review_required"},
    "liquid_temp_f": {"value": 77, "status": "review_required"},
    "superheat_f": {"value": 9, "status": "review_required"},
    "system_type": {"value": "Heat Recovery System", "status": "review_required"},
    "casing_material": {"value": None, "status": "unmapped"},
    "airflow_direction": {"value": None, "status": "blocked", "blocked_reason": "not stated"},
}


def _by_id(entries):
    return {e.ccsi_id: e for e in entries}


@pytest.fixture
def validated_map(monkeypatch):
    """The DX map with every entry promoted to validated (simulates Phase 3 passing)."""
    base = load_coil_data_map("DX")
    promoted = base.model_copy(
        update={"fields": {k: v.model_copy(update={"mapping_status": "validated"}) for k, v in base.fields.items()}}
    )
    monkeypatch.setattr(cdm, "load_coil_data_map", lambda coil_type="DX": promoted)
    return promoted


def test_map_is_separate_from_the_dimension_map() -> None:
    fields = load_coil_data_map("DX").fields
    dimension_ids = {
        entry["selectors"][0].lstrip("#")
        for entry in json.loads((ROOT / "web/ccsi/ccsi_dx_field_map.json").read_text(encoding="utf-8"))["fields"].values()
    }
    assert not set(fields) & dimension_ids
    for entry in fields.values():
        assert entry.draft_key not in DRAWING_PARAMETER_FIELD_KEYS
    assert "DrawingNotes" not in fields  # carried by the existing top-level drawing_notes key


def test_every_source_key_is_a_real_draft_field_or_identity() -> None:
    for ccsi_id, entry in load_coil_data_map("DX").fields.items():
        if entry.draft_key is None:
            assert entry.no_source_reason or entry.canonical_path or entry.default or entry.role != "input", (
                f"{ccsi_id}: input without source needs a reason"
            )
            continue
        assert entry.draft_key in DIRECT_COIL_FIELD_REGISTRY or entry.draft_key in IDENTITY_KEYS, ccsi_id


from coilforge.submittal.pdf_intake import PDF_INTAKE_FIELD_RULES  # noqa: E402

_INTAKE_TARGETS = {f"{rule.target}.{rule.target_key}" for rule in PDF_INTAKE_FIELD_RULES.values()}


def test_canonical_path_reads_the_candidate_group_and_keeps_its_status() -> None:
    from coilforge.ccsi.coil_data_map import canonical_sources
    from coilforge.contracts.field_value import FieldValue
    from coilforge.submittal.candidate import SubmittalCoilCandidate

    fixture = SubmittalCoilCandidate.model_validate(
        json.loads((ROOT / "examples/sanitized/submittal_candidate_dx_header1_default.json").read_text(encoding="utf-8"))
    )
    assert fixture.tag is not None
    ev = fixture.tag.source_evidence
    cand = SubmittalCoilCandidate(
        candidate_id="C1",
        refrigerant_conditions={
            "condensing_temp_f": FieldValue(value=115, source_evidence=ev, confidence="confirmed", status="review_required"),
            "subcooling_f": FieldValue(value=None, status="blocked", blocked_reason="not printed"),
        },
    )
    by = _by_id(resolve_coil_data(canonical_sources(cand), coil_type="HGRH"))
    assert by["CondensingTemperature"].value == "115"
    assert by["CondensingTemperature"].source_key == "refrigerant_conditions.condensing_temp_f"
    assert by["Subcooling"].reason_code == "CCSI_SOURCE_BLOCKED"
    # not stated -> D2 default 140 (John 2026-09-30: 74/74 ordered HGRH reports print 140)
    assert by["VaporTemperature"].reason_code == "CCSI_DEFAULT_PROFILE" and by["VaporTemperature"].value == "140"


ALL_MAP_TYPES = sorted(
    p.name.split(".")[1].upper() for p in (ROOT / "web/ccsi").glob("ccsi_coil_data_map.*.json")
)


@pytest.mark.parametrize("coil_type", ALL_MAP_TYPES)
def test_every_map_file_honours_the_contract(coil_type) -> None:
    cmap = load_coil_data_map(coil_type)
    assert cmap.coil_type == coil_type
    for ccsi_id, entry in cmap.fields.items():
        assert entry.draft_key not in DRAWING_PARAMETER_FIELD_KEYS, ccsi_id
        if entry.draft_key is not None:
            assert entry.draft_key in DIRECT_COIL_FIELD_REGISTRY or entry.draft_key in IDENTITY_KEYS, ccsi_id
            assert entry.canonical_path is None, f"{ccsi_id}: one source per entry"
        elif entry.canonical_path is not None:
            assert entry.canonical_path in _INTAKE_TARGETS, f"{ccsi_id}: {entry.canonical_path} is not an intake field"
        elif entry.role == "input":
            assert entry.no_source_reason or entry.default, f"{coil_type}/{ccsi_id}: input without source needs a reason"
        if entry.default is not None:
            assert entry.role == "input" and entry.mapping_status == "validated" and entry.evidence, ccsi_id
            if entry.options:
                assert entry.default in entry.options, f"{coil_type}/{ccsi_id}: default must be a CCSI option"
        if entry.type == "select":
            assert entry.options and (entry.transform.startswith("option_") or entry.transform == "value_map"), ccsi_id
        if entry.value_map is not None:
            assert set(entry.value_map.values()) <= set(entry.options or []), f"{ccsi_id}: value_map leaves the CCSI list"
        if entry.style_path is not None:
            # a fallback for an empty canonical_path, never a source of its own
            assert entry.canonical_path is not None and entry.style_map, ccsi_id
            assert entry.style_path in _INTAKE_TARGETS, f"{ccsi_id}: {entry.style_path} is not an intake field"
            assert set(entry.style_map.values()) <= set(entry.options or []), f"{ccsi_id}: style_map leaves the CCSI list"
            assert all(key == key.casefold() for key in entry.style_map), f"{ccsi_id}: style_map keys are casefolded"
        if entry.substitutions is not None:
            # a replacement must itself be something this form's list can take
            for stated, replacement in entry.substitutions.items():
                assert stated == stated.casefold(), f"{ccsi_id}: substitution keys are casefolded"
                if entry.transform == "option_material_gauge":  # a gauge moves only for a named material
                    assert len(stated.split()) >= 2, f"{ccsi_id}: {stated!r} must be '<material> <gauge>'"
                assert any(replacement.casefold() in option.casefold() for option in entry.options or []), (
                    f"{coil_type}/{ccsi_id}: {replacement!r} is not on the CCSI list")
            assert entry.mapping_status == "validated" and entry.evidence, f"{ccsi_id}: a substitution is John's call"
        if entry.material is not None:
            assert entry.transform == "option_material_gauge" and entry.evidence, ccsi_id
            assert any(option.casefold().startswith(entry.material.casefold()) for option in entry.options or []), ccsi_id
        promoted = entry.mapping_status != "captured"
        assert promoted == (ccsi_id in JOHN_APPROVED_VALIDATED.get(coil_type, set())), (
            f"{coil_type}/{ccsi_id}: promotion is John's call — only his approved list may leave 'captured'"
        )
        if promoted:
            assert entry.mapping_status == "validated" and entry.evidence, ccsi_id
            assert entry.role == "input", f"{ccsi_id}: only an input can be promoted to pushable"


# John 2026-09-29 ("승격 A"): 3 projects (3183/3232/3237), 0 mismatch. Pinned by equality, so
# a map edit that promotes anything else — or silently drops one of these — fails here.
# John 2026-09-29 "전부 A": D2 default profile, W water promotion, D6 circuits -> system type.
_D2_COMMON = {"HeaderMaterial", "HeaderWallSchedule", "ConnectionEnds", "CoilCoating", "CasingStyle",
              "CasingMaterial", "AirSideFoulingFactor", "TubeDiameter", "ConnectionMaterial"}
_W_WATER = {"Tag", "FinnedHeight", "FinnedLength", "RowsDeep", "FinsPerInch", "FinSurface", "CoilHand",
            "EnteringDryBulb", "TotalAirFlow"}
_D2_WATER = {"ConnectionType", "TubeTurbulators", "AirFlowDirection", "DrainAndVent", "TubeSideFoulingFactor"}
# John 2026-09-30 (geometry "A"): rows / FPI / feeds / fin surface / hand pushable on DX and HGRH;
# the D7 gate still withholds rows / FPI / fin whenever the submittal fin cannot be built in CCSI.
_GEOMETRY_2026_09_30 = {"RowsDeep", "FinsPerInch", "NumberOfFeeds", "FinSurface", "CoilHand"}
JOHN_APPROVED_VALIDATED = {
    "DX": {"Tag", "FinnedHeight", "FinnedLength", "TotalAirFlow", "Altitude", "EnteringDryBulb",
           "EnteringWetBulb", "EvaporatingTemperature", "LiquidTemperature", "Superheat", "Refrigerant"}
    | _D2_COMMON | {"DraintrayTypeAlt", "DraintrayMaterialAlt", "RefrigerantConnectionType", "DXDistCapillarySize",
                    "RefrigerationSystemType"}
    | _GEOMETRY_2026_09_30,
    "HGRH": {"Tag", "FinnedHeight", "FinnedLength", "NumberOfFeeds", "TotalAirFlow", "Altitude",
             "EnteringDryBulb", "Refrigerant"}
    | _D2_COMMON | {"RefrigerantConnectionType", "TemperatureInput", "CoilType", "RefrigerationSystemType"}
    | {"TubeMaterial"}  # John 2026-09-30 (D1 "A"): 3183/3232/3237 match, 0 mismatch
    | (_GEOMETRY_2026_09_30 - {"NumberOfFeeds"}),  # HGRH feeds was already validated
    # FluidFlowRate was pushed from 2026-09-29 ("GPM 푸시 진행") and DEMOTED 2026-09-30 (order cross-check
    # "A"): GPM matched 8/16 ordered water coils while EWT/LWT matched — CCSI solves the flow.
    "CWC": _W_WATER | _D2_COMMON | _D2_WATER | {"DraintrayTypeAlt", "DraintrayMaterialAlt"},
    "HWC": _W_WATER | _D2_COMMON | _D2_WATER | {"CoilType"},
}
# John 2026-09-30 (order cross-check "A", 77 ordered projects, calibration PASS): the rating inputs.
_ORDER_2026_09_30 = {
    "DX": {"CoilQuantity"},
    "HGRH": {"CoilQuantity", "Subcooling", "CondensingTemperature", "VaporTemperature"},  # Vapor = default 140
    "CWC": {"FluidType", "GlycolRatio", "EnteringFluidTemp", "LeavingFluidTemp", "EnteringWetBulb"},
    "HWC": {"CoilQuantity", "FluidType", "GlycolRatio", "EnteringFluidTemp", "LeavingFluidTemp"},
}
for _type, _ids in _ORDER_2026_09_30.items():
    JOHN_APPROVED_VALIDATED[_type] = JOHN_APPROVED_VALIDATED[_type] | _ids
# John 2026-10-01: CCSI air flow basis = Actual (Direct Coil selections are calculated in ACFM), every form.
for _type in JOHN_APPROVED_VALIDATED:
    JOHN_APPROVED_VALIDATED[_type] = JOHN_APPROVED_VALIDATED[_type] | {"ACFM"}
# John 2026-10-01 ("complete the mapping"; ordered + quoted CCSI reports paired per coil): tube / fin
# material on DX and HGRH (fin 0.0075 -> 0.008 and Sine -> Corrugated as substitutions); on the water
# forms feeds from the submittal's Circuits, the fin from its Fin Thickness, the tube as a default,
# Altitude (it rides the Actual air basis), and CWC CoilQuantity.
_MAPPING_2026_10_01 = {
    "DX": {"TubeMaterial", "FinMaterial"},
    "HGRH": {"FinMaterial"},
    "CWC": {"NumberOfFeeds", "TubeMaterial", "FinMaterial", "Altitude", "CoilQuantity"},
    "HWC": {"NumberOfFeeds", "TubeMaterial", "FinMaterial", "Altitude"},
}
for _type, _ids in _MAPPING_2026_10_01.items():
    JOHN_APPROVED_VALIDATED[_type] = JOHN_APPROVED_VALIDATED[_type] | _ids
# D3: CCSI calculates connection sizes — never pushable, on every form.
_D3_CONNECTION_SIZES = {"DX": {"DXReturnConnectionSize"},
                        "HGRH": {"CondenserSupplyConnectionSize", "CondenserReturnConnectionSize"},
                        "CWC": {"ConnectionSize"}, "HWC": {"ConnectionSize"}}


def test_selects_carry_their_captured_options() -> None:
    for ccsi_id, entry in load_coil_data_map("DX").fields.items():
        if entry.type == "select":
            assert entry.options, ccsi_id
            assert entry.transform.startswith("option_") or entry.transform == "value_map", ccsi_id


def test_only_johns_validated_fields_are_pushable_on_the_real_map() -> None:
    fin = {"fin_material": {"value": "0.008", "unit": "Aluminum", "status": "review_required"}}
    entries = resolve_coil_data({**LEDGER_3025_CDXC1, **fin})
    pushable = {e.ccsi_id for e in entries if e.pushable}
    assert pushable <= JOHN_APPROVED_VALIDATED["DX"]
    by = _by_id(entries)
    assert by["EnteringDryBulb"].reason_code == "CCSI_OK" and by["EnteringDryBulb"].value == "95"
    assert by["FinMaterial"].reason_code == "CCSI_OK" and by["FinMaterial"].value == "Aluminum 0.008"
    # a still-captured mapping resolves (so validation can compare it) but is never pushed. Every DX
    # input with a source is promoted since 2026-10-01, so the HWC form's Leaving Dry Bulb carries the
    # pin now (CoilHand, CoilQuantity and FinMaterial served here before John promoted them).
    leaving = {"leaving_dry_bulb_f": {"value": 95, "status": "review_required"}}
    captured = _by_id(resolve_coil_data(leaving, coil_type="HWC"))["LeavingDryBulb"]
    assert captured.reason_code == "CCSI_NOT_VALIDATED" and captured.value == "95" and not captured.pushable
    assert by["CoilQuantity"].reason_code == "CCSI_OK" and by["CoilQuantity"].pushable  # order cross-check "A"
    assert by["CoilHand"].reason_code == "CCSI_OK" and by["CoilHand"].pushable


# --- D7 geometry re-selection gate -------------------------------------------------

_BASE = {
    "rows_deep": {"value": 6, "status": "review_required"},
    "fins_per_inch": {"value": 9, "status": "review_required"},
    "finned_height": {"value": 18, "status": "review_required"},
    "number_of_feeds": {"value": 9, "status": "review_required"},
    "entering_dry_bulb_f": {"value": 95.4, "status": "review_required"},
}


@pytest.mark.parametrize(
    ("surface", "gauge"),
    [("Sine", "0.008"), ("Flat", "0.0075"), ("Sine", "0.0075")],  # 3183 is the last one
)
def test_unbuildable_fin_withholds_only_fpi(validated_map, surface, gauge) -> None:
    # John 2026-10-01 narrowed D7: on the ordered selections rows survive the fin change (41/46 equal)
    # and the fin is substituted predictably, while FPI is what gets re-optimised (16/45 equal).
    src = {**_BASE, "fin_surface": {"value": surface, "status": "review_required"},
           "fin_material": {"value": gauge, "unit": "Aluminum", "status": "review_required"}}
    by = _by_id(resolve_coil_data(src))
    assert by["FinsPerInch"].reason_code == "CCSI_GEOMETRY_RESELECT" and not by["FinsPerInch"].pushable
    assert by["FinsPerInch"].value == "9"  # still resolved so the cross-check shows the difference
    assert (by["FinSurface"].value, by["FinSurface"].pushable) == ("Corrugated" if surface == "Sine" else "Flat", True)
    assert (by["FinMaterial"].value, by["FinMaterial"].pushable) == ("Aluminum 0.008", True)
    for ccsi_id in ("RowsDeep", "FinnedHeight", "NumberOfFeeds", "EnteringDryBulb"):
        assert by[ccsi_id].pushable, f"{ccsi_id} survives a re-selection and must still go"


def test_buildable_fin_does_not_trigger_the_gate(validated_map) -> None:
    src = {**_BASE, "fin_surface": {"value": "Flat", "status": "review_required"},
           "fin_material": {"value": "0.008", "status": "review_required"}}
    by = _by_id(resolve_coil_data(src))
    assert by["RowsDeep"].pushable and by["FinsPerInch"].pushable


def test_absent_fin_is_not_evidence_for_the_gate(validated_map) -> None:
    assert _by_id(resolve_coil_data(_BASE))["RowsDeep"].pushable


def test_gate_uses_each_forms_own_fin_list() -> None:
    from coilforge.ccsi.coil_data_map import geometry_reselect_reason

    # the water forms offer no 0.005 fin, the DX form does — and each form's gate reads the fin
    # from the key its own FinMaterial entry resolves from (water: the submittal's Fin Thickness)
    src = {"fin_material": {"value": "0.005", "status": "review_required"},
           "geometry.fin_thickness_in": {"value": 0.005, "unit": "in", "status": "review_required"}}
    assert geometry_reselect_reason(src, load_coil_data_map("DX")) is None
    assert "0.005" in (geometry_reselect_reason(src, load_coil_data_map("CWC")) or "")
    assert geometry_reselect_reason({"fin_material": src["fin_material"]}, load_coil_data_map("CWC")) is None


def test_computed_and_locked_fields_are_never_pushable(validated_map) -> None:
    by = _by_id(resolve_coil_data(LEDGER_3025_CDXC1))
    # Altitude left this list 2026-09-29: harvests show it editable whenever ACFM = Actual
    # (3183, 3237) and read-only only under Standard (3232, 3031) — it is an input.
    for ccsi_id in ("Capacity", "LeavingDryBulb", "FaceVelocity"):
        assert by[ccsi_id].reason_code == "CCSI_READ_BACK_ONLY"
        assert not by[ccsi_id].pushable
    assert by["Capacity"].value == "242.05"


def test_spelling_and_format_normalizations(validated_map) -> None:
    by = _by_id(resolve_coil_data(LEDGER_3025_CDXC1))
    assert by["Refrigerant"].value == "R32"
    assert by["DXReturnConnectionSize"].value == '1 1/8"'
    assert by["RowsDeep"].value == "6"
    assert by["CoilHand"].value == "Left"
    assert by["EnteringDryBulb"].pushable and by["EnteringDryBulb"].review_required


@pytest.mark.parametrize(
    ("key", "value", "ccsi_id"),
    [
        ("fin_material", "0.008", "FinMaterial"),  # thickness without material — never assume aluminum
        ("tube_material", "0.016", "TubeMaterial"),
        ("fin_surface", "Louvered", "FinSurface"),  # no CCSI equivalent (Sine left 2026-10-01: a substitution)
        ("fins_per_inch", 8.5, "FinsPerInch"),  # integer-only list, never rounded
        ("return_connection_size", 1.1, "DXReturnConnectionSize"),  # not a sixteenth
        # CoilCoating left this list on 2026-09-30 (John): a coating off the dropdown now selects
        # the form's coating option — tests/test_coating_ccsi_and_notes.py.
    ],
)
def test_values_off_the_captured_vocabulary_are_unmapped(validated_map, key, value, ccsi_id) -> None:
    entry = _by_id(resolve_coil_data({key: {"value": value, "status": "review_required"}}))[ccsi_id]
    assert entry.reason_code == "CCSI_OPTION_UNMAPPED"
    assert entry.value is None and not entry.pushable


# --- D1 tube / fin material (John 2026-09-30) ----------------------------------------
# The intake splits "0.016 Copper" into value 0.016 + unit "Copper"; the tube surface is canonical.


def _gauge(value, material=None):
    return {"value": value, "unit": material, "status": "review_required"}


_SMOOTH = {TUBE_SURFACE_SOURCE: {"value": "Smooth", "status": "review_required"}}


def test_the_tube_surface_source_is_a_real_intake_field() -> None:
    assert TUBE_SURFACE_SOURCE in _INTAKE_TARGETS


@pytest.mark.parametrize(
    ("coil_type", "sources", "ccsi_id", "expected"),
    [
        ("DX", {"tube_material": _gauge(0.016, "Copper"), **_SMOOTH}, "TubeMaterial", "Copper 0.016 Plain"),
        ("HGRH", {"tube_material": _gauge(0.016, "Copper"), **_SMOOTH}, "TubeMaterial", "Copper 0.016 Plain"),
        ("DX", {"fin_material": _gauge(0.008, "Aluminium")}, "FinMaterial", "Aluminum 0.008"),  # British spelling
        ("DX", {"fin_material": _gauge(0.01, "Aluminum")}, "FinMaterial", "Aluminum 0.010"),  # float lost its zero
        ("DX", {"fin_material": _gauge(0.006, "Aluminum")}, "FinMaterial", "Aluminum 0.006"),  # not "Coated aluminum"
        ("HGRH", {"fin_material": _gauge(0.008, "Aluminum")}, "FinMaterial", "Aluminum 0.008"),
        ("DX", {"tube_material": _gauge("Copper 0.016 Rifled")}, "TubeMaterial", "Copper 0.016 Rifled"),  # typed option
    ],
)
def test_material_and_gauge_land_on_the_exact_ccsi_option(coil_type, sources, ccsi_id, expected) -> None:
    entry = _by_id(resolve_coil_data(sources, coil_type=coil_type))[ccsi_id]
    assert entry.value == expected, entry.reason
    assert entry.review_required


def test_tube_and_fin_material_are_promoted_on_dx_and_hgrh() -> None:
    # HGRH TubeMaterial: John 2026-09-30 (D1 "A"). The other three: John 2026-10-01, on the ordered
    # CCSI reports paired per coil.
    src = {"tube_material": _gauge(0.016, "Copper"), "fin_material": _gauge(0.008, "Aluminum"), **_SMOOTH}
    hgrh = _by_id(resolve_coil_data(src, coil_type="HGRH"))
    dx = _by_id(resolve_coil_data(src, coil_type="DX"))
    for by, ccsi_id in ((hgrh, "TubeMaterial"), (hgrh, "FinMaterial"), (dx, "TubeMaterial"), (dx, "FinMaterial")):
        assert by[ccsi_id].reason_code == "CCSI_OK" and by[ccsi_id].pushable, ccsi_id
    # promotion does not loosen the rule: no stated surface is still never pushed
    bare = _by_id(resolve_coil_data({"tube_material": _gauge(0.016, "Copper")}, coil_type="HGRH"))["TubeMaterial"]
    assert bare.reason_code == "CCSI_OPTION_UNMAPPED" and not bare.pushable


@pytest.mark.parametrize(
    ("sources", "ccsi_id", "why"),
    [
        ({"fin_material": _gauge(0.0065, "Aluminium")}, "FinMaterial", "0.0065"),  # an unlisted gauge is never rounded
        ({"fin_material": _gauge(0.0075)}, "FinMaterial", "no material"),  # a substitution never supplies the material
        # the 0.0075 -> 0.008 substitution was approved on Aluminum orders only; no other material rides it
        ({"fin_material": _gauge(0.0075, "Copper")}, "FinMaterial", "Copper 0.0075"),
        ({"fin_material": _gauge(0.008)}, "FinMaterial", "no material"),  # never assume aluminum
        ({"tube_material": _gauge(0.016, "Copper")}, "TubeMaterial", "not stated"),  # Plain vs Rifled never assumed
        ({"tube_material": _gauge(0.016, "Copper"), TUBE_SURFACE_SOURCE: {"value": "Enhanced", "status": "review_required"}},
         "TubeMaterial", "Copper 0.016 Enhanced"),
        ({"tube_material": _gauge(0.016, "Copper"),
          TUBE_SURFACE_SOURCE: {"value": "Smooth", "status": "blocked", "blocked_reason": "conflict"}},
         "TubeMaterial", "not stated"),  # a blocked surface is not a stated one
        ({"tube_material": _gauge(0.018, "Copper"), **_SMOOTH}, "TubeMaterial", "Copper 0.018"),  # a water gauge on DX
        ({"tube_material": _gauge("0.016 Copper Refrig. PD")}, "TubeMaterial", "not a gauge"),  # intake column bleed
    ],
)
def test_material_gauge_that_does_not_land_exactly_is_unmapped(sources, ccsi_id, why) -> None:
    entry = _by_id(resolve_coil_data(sources))[ccsi_id]
    assert entry.reason_code == "CCSI_OPTION_UNMAPPED" and entry.value is None and not entry.pushable
    assert why in entry.reason


def test_a_lone_surface_candidate_is_still_never_assumed() -> None:
    water = load_coil_data_map("CWC").fields["TubeMaterial"].options or []
    assert cdm._material_gauge_option(0.035, "Copper", None, water)[0] is None  # only "Copper 0.035 Plain" exists
    assert cdm._material_gauge_option(0.035, "Copper", "Smooth", water)[0] == "Copper 0.035 Plain"
    assert cdm._material_gauge_option(0.049, "Copper/Nickel 90/10", "Smooth", water)[0] == (
        "Copper/Nickel 90/10 - 0.049 Plain"
    )


@pytest.mark.parametrize("coil_type", ["DX", "HGRH"])
def test_the_fin_ccsi_cannot_build_is_sent_as_the_ordered_substitute(coil_type) -> None:
    # 0.0075 is not a CCSI gauge and Sine is not a CCSI surface; the ordered selections carry
    # Aluminum 0.008 and Corrugated for them (John approved 2026-10-01).
    src = {"fin_material": _gauge(0.0075, "Aluminium"), "fin_surface": {"value": "Sine", "status": "review_required"}}
    by = _by_id(resolve_coil_data(src, coil_type=coil_type))
    assert (by["FinMaterial"].value, by["FinMaterial"].pushable) == ("Aluminum 0.008", True)
    assert (by["FinSurface"].value, by["FinSurface"].pushable) == ("Corrugated", True)
    for ccsi_id, stated in (("FinMaterial", "0.0075"), ("FinSurface", "Sine")):
        assert stated in by[ccsi_id].reason and "sent in its place" in by[ccsi_id].reason  # the reviewer sees it
        assert str(by[ccsi_id].source_value) == stated  # what the submittal said is still reported


# --- water coils (John 2026-10-01): feeds, fin and tube ------------------------------

_FIN_THICKNESS = "geometry.fin_thickness_in"
_WATER = {
    "geometry.circuits": {"value": 2, "status": "review_required"},
    _FIN_THICKNESS: {"value": 0.008, "unit": "in", "status": "review_required"},
}


def _thickness(value):
    return {_FIN_THICKNESS: {"value": value, "unit": "in", "status": "review_required"}}


@pytest.mark.parametrize("coil_type", ["CWC", "HWC"])
def test_water_feeds_fin_and_tube(coil_type) -> None:
    by = _by_id(resolve_coil_data(_WATER, coil_type=coil_type))
    # the submittal's Circuits is CCSI's Number Of Feeds
    feeds = by["NumberOfFeeds"]
    assert (feeds.value, feeds.source_key, feeds.pushable) == ("2", "geometry.circuits", True)
    # Fin Thickness is printed without a material ("in" is its unit, not one); the entry names Aluminum
    fin = by["FinMaterial"]
    assert (fin.value, fin.source_key, fin.pushable) == ("Aluminum 0.008", _FIN_THICKNESS, True)
    # the tube is never stated on a water submittal: the default profile, flagged as one
    tube = by["TubeMaterial"]
    assert (tube.value, tube.reason_code, tube.pushable) == ("Copper 0.018 Plain", "CCSI_DEFAULT_PROFILE", True)
    assert by["FinsPerInch"].reason_code != "CCSI_GEOMETRY_RESELECT"  # a buildable fin does not trip D7


@pytest.mark.parametrize("coil_type", ["CWC", "HWC"])
def test_water_fin_thickness_lands_on_the_ccsi_gauge(coil_type) -> None:
    assert _by_id(resolve_coil_data(_thickness(0.01), coil_type=coil_type))["FinMaterial"].value == "Aluminum 0.010"
    src = {**_thickness(0.0075), "fins_per_inch": {"value": 12, "status": "review_required"}}
    by = _by_id(resolve_coil_data(src, coil_type=coil_type))
    assert (by["FinMaterial"].value, by["FinMaterial"].pushable) == ("Aluminum 0.008", True)
    # the same D7 rule as DX / HGRH: a substituted fin withholds FPI, and only FPI
    assert by["FinsPerInch"].reason_code == "CCSI_GEOMETRY_RESELECT" and not by["FinsPerInch"].pushable
    assert by["FinsPerInch"].value == "12"


@pytest.mark.parametrize("coil_type", ["CWC", "HWC"])
@pytest.mark.parametrize("key", cdm.FIN_MATERIAL_SOURCES)
def test_a_stated_fin_material_is_never_replaced_by_the_maps_aluminum(coil_type, key) -> None:
    # the entry's ``material`` fills in for a thickness printed WITHOUT one — nothing more
    def fin(source):
        return _by_id(resolve_coil_data({**_thickness(0.008), key: source}, coil_type=coil_type))["FinMaterial"]

    for stated in (_gauge(0.008, "Copper"), _gauge("Copper 0.008"), _gauge(0.006, "Coated aluminum")):
        copper = fin(stated)
        assert copper.reason_code == "CCSI_OPTION_UNMAPPED" and copper.value is None and not copper.pushable
        assert "only for a thickness printed without a material" in copper.reason
    conflict = fin({"value": None, "status": "blocked", "blocked_reason": "conflicting sources"})
    assert conflict.reason_code == "CCSI_OPTION_UNMAPPED" and "not assumed over it" in conflict.reason
    # the same material, a bare gauge, or plain absence leave the approved mapping standing
    absent = {"value": None, "status": "blocked", "blocked_reason": "required canonical field missing"}
    for agreeing in (_gauge(0.008, "Aluminium"), _gauge(0.008), absent):
        assert (fin(agreeing).value, fin(agreeing).pushable) == ("Aluminum 0.008", True)


def test_the_stated_fin_material_sources_are_real_fields() -> None:
    draft_key, canonical = cdm.FIN_MATERIAL_SOURCES
    assert draft_key in DIRECT_COIL_FIELD_REGISTRY and canonical in _INTAKE_TARGETS


@pytest.mark.parametrize("coil_type", ["CWC", "HWC"])
def test_water_values_that_are_absent_or_unlisted_are_not_guessed(coil_type) -> None:
    by = _by_id(resolve_coil_data({}, coil_type=coil_type))
    for ccsi_id in ("NumberOfFeeds", "FinMaterial"):
        assert by[ccsi_id].reason_code == "CCSI_SOURCE_MISSING" and not by[ccsi_id].pushable, ccsi_id
    odd = _by_id(resolve_coil_data(_thickness(0.0065), coil_type=coil_type))["FinMaterial"]
    assert odd.reason_code == "CCSI_OPTION_UNMAPPED" and odd.value is None
    blocked = {_FIN_THICKNESS: {"value": 0.008, "unit": "in", "status": "blocked", "blocked_reason": "conflict"}}
    assert _by_id(resolve_coil_data(blocked, coil_type=coil_type))["FinMaterial"].reason_code == "CCSI_SOURCE_BLOCKED"
    # a stated tube always wins over the default, and a stated tube off the list stays unmapped
    stated = {"tube_material": {"value": "Copper 0.020 Plain", "status": "review_required"}}
    assert _by_id(resolve_coil_data(stated, coil_type=coil_type))["TubeMaterial"].value == "Copper 0.020 Plain"
    off = {"tube_material": {"value": "Steel 0.049", "status": "review_required"}}
    tube = _by_id(resolve_coil_data(off, coil_type=coil_type))["TubeMaterial"]
    assert tube.reason_code == "CCSI_OPTION_UNMAPPED" and tube.value is None and not tube.pushable
    conflict = {"tube_material": {"value": None, "status": "blocked", "blocked_reason": "conflicting sources"}}
    assert _by_id(resolve_coil_data(conflict, coil_type=coil_type))["TubeMaterial"].reason_code == "CCSI_SOURCE_BLOCKED"


def test_ledger_replay_reads_the_material_unit_and_the_stated_tube_surface() -> None:
    import sqlite3

    sys.path.insert(0, str(ROOT / "scripts"))
    import ccsi_coil_data_readiness as replay  # pyright: ignore[reportMissingImports]

    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        create table run (run_id text, ts_utc text, ok integer, project_number text, project_name text,
                          source_filename text, input_hash text);
        create table coil (coil_uid text, tag text, coil_category text, circuits integer);
        create table field_observation (run_id text, coil_uid text, stage text, field_key text,
                                        value_json text, unit text, status text, blocked_reason text);
        insert into run values ('r1', '2026-09-29T00:00:00Z', 1, '3237', 'P', 'p.pdf', 'abc123');
        insert into coil values ('c1', 'CDXC-1', 'DX', 2), ('c2', 'CDXC-2', 'DX', 1), ('c3', 'CDXC-3', 'DX', 1);
        insert into field_observation values
            ('r1', 'c1', 'draft', 'tube_material', '0.016', 'Copper', 'review_required', null),
            ('r1', 'c1', 'draft', 'fin_material', '0.008', 'Aluminum', 'review_required', null),
            ('r1', 'c1', 'slot', 'slot.TUBE_MATERIAL_2', '"Smooth"', null, null, null),
            ('r1', 'c2', 'draft', 'tube_material', '0.016', 'Copper', 'review_required', null),
            ('r1', 'c3', 'slot', 'slot.TUBE_MATERIAL_2', '"Smooth"', null, null, null);
    """)
    coils = {c["tag"]: c for c in replay.load_coils(conn, "DX")}
    assert set(coils) == {"CDXC-1", "CDXC-2"}  # a slot row alone does not make a coil
    assert coils["CDXC-1"]["input_hash"] == "abc123"  # pairs the coil with the PDF its draft read
    by = _by_id(resolve_coil_data(coils["CDXC-1"]["sources"]))
    assert by["TubeMaterial"].value == "Copper 0.016 Plain"
    assert by["FinMaterial"].value == "Aluminum 0.008"
    # CDXC-2's drawing recorded no surface: its tube stays unmapped, never borrowing CDXC-1's
    assert _by_id(resolve_coil_data(coils["CDXC-2"]["sources"]))["TubeMaterial"].reason_code == "CCSI_OPTION_UNMAPPED"


@pytest.mark.parametrize(("coil_type", "circuits", "expected"), [
    ("DX", 1, "Single-Circuit"), ("DX", 2, "Dual-Circuit Intertwined"), ("HGRH", 1, "Single-Circuit"),
    # John approved 2026-10-01 (System Type fix), observed on ordered reports: 17/17 and 8/8 coils.
    ("DX", 3, "3-Circuit Intertwined"), ("HGRH", 2, "Dual-Circuit Face-Split"),
])
def test_system_type_follows_circuits(coil_type, circuits, expected) -> None:
    src = {"geometry.circuits": {"value": circuits, "status": "review_required"}}
    entry = _by_id(resolve_coil_data(src, coil_type=coil_type))["RefrigerationSystemType"]
    assert entry.value == expected and entry.pushable


# DX 4 is observed but SPLIT across orders (4-Circuit Face-Split 4 / 3-Circuit Intertwined 2), so it
# is not mapped either; HGRH 3 has never been seen. (DX 3 and HGRH 2 stood here until 2026-10-01,
# when the ordered reports showed them 17/17 and 8/8.)
@pytest.mark.parametrize(("coil_type", "circuits"), [("DX", 4), ("HGRH", 3)])
def test_unobserved_circuit_count_is_unmapped_not_guessed(coil_type, circuits) -> None:
    src = {"geometry.circuits": {"value": circuits, "status": "review_required"}}
    entry = _by_id(resolve_coil_data(src, coil_type=coil_type))["RefrigerationSystemType"]
    assert entry.reason_code == "CCSI_OPTION_UNMAPPED" and not entry.pushable


_COIL_STYLE = "manufacturing_options.coil_style"


@pytest.mark.parametrize("coil_type", ["DX", "HGRH"])
def test_standard_coil_style_is_a_single_circuit(coil_type) -> None:
    # A one-circuit submittal prints no circuit count: Coil Style is "Standard" and geometry.circuits
    # is empty. Ordered reports: Single-Circuit on 93/93 DX and 80/80 HGRH such coils (John approved 2026-10-01).
    src = {_COIL_STYLE: {"value": " standard ", "status": "review_required"}}
    entry = _by_id(resolve_coil_data(src, coil_type=coil_type))["RefrigerationSystemType"]
    assert (entry.value, entry.reason_code, entry.pushable) == ("Single-Circuit", "CCSI_OK", True)
    assert entry.source_key == _COIL_STYLE and entry.source_value == "standard"
    assert "no circuit count" in entry.reason


@pytest.mark.parametrize(("coil_type", "style"), [("DX", "Intertwined (x2)"), ("HGRH", "Face Split"), ("DX", "Custom")])
def test_a_coil_style_without_a_count_that_is_not_standard_stays_unmapped(coil_type, style) -> None:
    # 2944 "Intertwined (x2)" and 2950 "Face Split" were ordered as DUAL circuits: a style that states
    # no count must never fall to Single-Circuit just because the count is missing.
    src = {_COIL_STYLE: {"value": style, "status": "review_required"}}
    entry = _by_id(resolve_coil_data(src, coil_type=coil_type))["RefrigerationSystemType"]
    assert entry.reason_code == "CCSI_OPTION_UNMAPPED" and entry.value is None and not entry.pushable


@pytest.mark.parametrize(("coil_type", "circuits", "style"), [
    ("DX", 3, "Face Split 3 Circuits"),   # would have gone out as 3-Circuit Intertwined
    ("DX", 2, "Dual Face Split"),         # would have gone out as Dual-Circuit Intertwined
    ("HGRH", 2, "Interlaced 2 Circuits"), # would have gone out as Dual-Circuit Face-Split
])
def test_a_style_naming_another_arrangement_is_not_sent_as_the_mapped_one(coil_type, circuits, style) -> None:
    src = {"geometry.circuits": {"value": circuits, "status": "review_required"},
           _COIL_STYLE: {"value": style, "status": "review_required"}}
    entry = _by_id(resolve_coil_data(src, coil_type=coil_type))["RefrigerationSystemType"]
    assert entry.reason_code == "CCSI_OPTION_UNMAPPED" and not entry.pushable
    assert "different arrangement" in entry.reason


@pytest.mark.parametrize(("coil_type", "circuits", "style", "expected"), [
    ("DX", 2, "Interlaced 2 Circuits", "Dual-Circuit Intertwined"), ("DX", 2, "Dual Interlaced", "Dual-Circuit Intertwined"),
    ("DX", 3, "Interlaced 3 Circuits", "3-Circuit Intertwined"), ("DX", 1, "Single-circuit", "Single-Circuit"),
    ("HGRH", 2, "Face Split 2 Circuits", "Dual-Circuit Face-Split"), ("HGRH", 2, "Dual Face Split", "Dual-Circuit Face-Split"),
])
def test_the_styles_seen_on_ordered_coils_still_resolve(coil_type, circuits, style, expected) -> None:
    src = {"geometry.circuits": {"value": circuits, "status": "review_required"},
           _COIL_STYLE: {"value": style, "status": "review_required"}}
    entry = _by_id(resolve_coil_data(src, coil_type=coil_type))["RefrigerationSystemType"]
    assert entry.value == expected and entry.pushable


def test_a_stated_circuit_count_wins_over_the_coil_style() -> None:
    src = {"geometry.circuits": {"value": 2, "status": "review_required"},
           _COIL_STYLE: {"value": "Standard", "status": "review_required"}}
    entry = _by_id(resolve_coil_data(src))["RefrigerationSystemType"]
    assert entry.value == "Dual-Circuit Intertwined" and entry.source_key == "geometry.circuits"


@pytest.mark.parametrize("src", [
    {"geometry.circuits": {"value": None, "status": "blocked", "blocked_reason": "conflicting circuit counts"},
     _COIL_STYLE: {"value": "Standard", "status": "review_required"}},
    {_COIL_STYLE: {"value": "Standard", "status": "blocked", "blocked_reason": "ambiguous"}},
    {},
])
def test_a_blocked_or_absent_source_never_becomes_a_single_circuit(src) -> None:
    entry = _by_id(resolve_coil_data(src))["RefrigerationSystemType"]
    assert entry.value is None and not entry.pushable
    assert entry.reason_code in {"CCSI_SOURCE_BLOCKED", "CCSI_SOURCE_MISSING"}


def test_the_oxygen8_unit_system_is_never_the_ccsi_system_type() -> None:
    # "Heat Recovery System" is the AHU system, not a circuit arrangement: without circuits -> missing
    entry = _by_id(resolve_coil_data(LEDGER_3025_CDXC1))["RefrigerationSystemType"]
    assert entry.reason_code == "CCSI_SOURCE_MISSING" and entry.value is None


@pytest.mark.parametrize("coil_type", ["DX", "HGRH", "CWC", "HWC"])
def test_absent_fields_take_the_default_profile(coil_type) -> None:
    by = _by_id(resolve_coil_data({}, coil_type=coil_type))
    assert by["CasingMaterial"].reason_code == "CCSI_DEFAULT_PROFILE"
    assert by["CasingMaterial"].value == "Galvanized Steel 16 gauge" and by["CasingMaterial"].pushable
    water = coil_type in ("CWC", "HWC")
    assert by["TubeDiameter"].value == ("5/8 1.50 x 1.299" if water else "3/8 1.00 x 0.866")
    assert by["ConnectionMaterial"].value == ("Steel" if water else "Copper")


@pytest.mark.parametrize("coil_type", ["DX", "HGRH", "CWC", "HWC"])
def test_air_flow_basis_is_actual_and_pushed_before_altitude(coil_type) -> None:
    """John 2026-10-01: Direct Coil selections are calculated in ACFM, so CCSI's basis is Actual.

    Order is load-bearing: under Standard CCSI locks Altitude to 0, and stage 1 skips a locked
    field — so the basis must be written (and its GetDependencies settled) before Altitude.
    Standard (SCFM) stays a roadmap question, not an option this map ever chooses.
    """
    acfm = _by_id(resolve_coil_data({}, coil_type=coil_type))["ACFM"]
    assert acfm.value == "Actual" and acfm.pushable and acfm.reason_code == "CCSI_DEFAULT_PROFILE"
    ids = list(load_coil_data_map(coil_type).fields)
    assert ids.index("ACFM") < ids.index("Altitude")


def test_a_stated_value_always_beats_the_default() -> None:
    finkote = {"coil_coating": {"value": "Finkote2 Epoxy Coil Coating", "status": "review_required"}}
    coated = _by_id(resolve_coil_data(finkote))["CoilCoating"]
    # never silently "Plain": a stated coating the dropdown lacks selects its coating option
    # (John 2026-09-30; until then it was left unmapped) and the notes name the real coating.
    assert coated.reason_code == "CCSI_OK" and coated.reason_code != "CCSI_DEFAULT_PROFILE"
    assert coated.value == "AA Coating" and coated.value != "Plain"
    stated = _by_id(resolve_coil_data({"coil_coating": {"value": "AA Coating", "status": "review_required"}}))
    assert stated["CoilCoating"].value == "AA Coating"


def test_a_block_other_than_absence_is_never_defaulted_over() -> None:
    conflict = {"airflow_direction": {"value": None, "status": "blocked", "blocked_reason": "conflicting sources"}}
    by = _by_id(resolve_coil_data(conflict, coil_type="CWC"))
    assert by["AirFlowDirection"].reason_code == "CCSI_SOURCE_BLOCKED"
    absent = {"airflow_direction": {"value": None, "status": "blocked",
                                    "blocked_reason": "required canonical field missing"}}
    assert _by_id(resolve_coil_data(absent, coil_type="CWC"))["AirFlowDirection"].value == "Horizontal"


@pytest.mark.parametrize("coil_type", ["DX", "HGRH", "CWC", "HWC"])
def test_connection_sizes_are_never_pushed(coil_type) -> None:
    src = {"return_connection_size": {"value": 0.875, "status": "review_required"},
           "supply_connection_size": {"value": 0.625, "status": "review_required"}}
    by = _by_id(resolve_coil_data(src, coil_type=coil_type))
    for ccsi_id in _D3_CONNECTION_SIZES[coil_type]:
        assert not by[ccsi_id].pushable, ccsi_id


def test_blocked_and_missing_sources_are_never_filled(validated_map) -> None:
    by = _by_id(resolve_coil_data(LEDGER_3025_CDXC1))
    assert by["EnteringRelativeHumidity"].reason_code == "CCSI_SOURCE_MISSING"  # no default -> stays missing
    blocked = _by_id(resolve_coil_data({"rows_deep": {"value": 4, "status": "blocked", "blocked_reason": "x"}}))
    assert blocked["RowsDeep"].reason_code == "CCSI_SOURCE_BLOCKED"
    assert blocked["RowsDeep"].value is None


def test_unparseable_number_is_reported_not_coerced(validated_map) -> None:
    entry = _by_id(resolve_coil_data({"total_air_flow_cfm": {"value": "2,660 cfm", "status": "review_required"}}))
    assert entry["TotalAirFlow"].reason_code == "CCSI_VALUE_UNPARSEABLE"


def test_accepts_a_real_draft_field_model(validated_map) -> None:
    from coilforge.direct_coil.draft import DirectCoilDraftField

    field = DirectCoilDraftField(
        field_key="superheat_f", label="Superheat", group="refrigerant", value=9,
        mapping_rule="test", status="review_required",
    )
    assert _by_id(resolve_coil_data({"superheat_f": field}))["Superheat"].value == "9"


def test_ledger_replay_tallies_reason_codes_per_field() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import ccsi_coil_data_readiness as replay  # pyright: ignore[reportMissingImports]

    coils = [
        {"project": "P1", "tag": "CDXC-1", "sources": LEDGER_3025_CDXC1},
        {"project": "P2", "tag": "CDXC-1", "sources": {"tag": "CDXC-1", "fin_surface": {"value": "Louvered", "status": "review_required"}}},
    ]
    report = replay.build_report(coils, "DX")
    assert report["coils"] == 2 and report["projects"] == 2
    fin = report["fields"]["FinSurface"]
    assert fin["reason_counts"] == {"CCSI_OK": 1, "CCSI_OPTION_UNMAPPED": 1}  # FinSurface validated 2026-09-30
    assert fin["off_vocabulary"] == {"'Louvered'": 1}  # Sine left on 2026-10-01: it is a substitution now
    assert "| `FinSurface` | input | 1/2 |" in replay.render_markdown(report)


def test_total_airflow_is_per_coil_cfm_times_quantity() -> None:
    # 3154 HHWC-1: submittal 400 CFM per coil, qty 3 -> CCSI Total Air Flow 1200, per coil 400
    src = {"coil_quantity": 3, "total_air_flow_cfm": {"value": 400, "status": "review_required"}}
    by = _by_id(resolve_coil_data(src))
    assert by["TotalAirFlow"].value == "1200" and by["TotalAirFlow"].pushable
    assert by["AirFlowPerCoil"].value == "400" and not by["AirFlowPerCoil"].pushable


def test_unknown_quantity_is_never_assumed_to_be_one() -> None:
    by = _by_id(resolve_coil_data({"total_air_flow_cfm": {"value": 400, "status": "review_required"}}))
    assert by["TotalAirFlow"].reason_code == "CCSI_SOURCE_MISSING"
    assert by["TotalAirFlow"].value is None and not by["TotalAirFlow"].pushable
    assert "quantity" in by["TotalAirFlow"].reason


@pytest.mark.parametrize("coil_type", ["CWC", "HWC"])
def test_gpm_covers_all_coils_of_the_tag_but_is_no_longer_pushed(coil_type) -> None:
    src = {"coil_quantity": 2,
           "airside_conditions.fluid_flow_rate_gpm": {"value": 8.44, "status": "review_required"}}
    gpm = _by_id(resolve_coil_data(src, coil_type=coil_type))["FluidFlowRate"]
    # still computed x quantity for read-back comparison; demoted 2026-09-30 (CCSI solves the flow)
    assert gpm.value == "16.88" and not gpm.pushable and gpm.reason_code == "CCSI_NOT_VALIDATED"
    unknown_qty = {"airside_conditions.fluid_flow_rate_gpm": {"value": 8.44, "status": "review_required"}}
    assert not _by_id(resolve_coil_data(unknown_qty, coil_type=coil_type))["FluidFlowRate"].pushable


def test_summary_carries_safety_flags() -> None:
    s = summarize(resolve_coil_data(LEDGER_3025_CDXC1))
    assert s["export_allowed"] is False and s["review_aid_only"] is True
    assert s["total"] == len(load_coil_data_map("DX").fields)
