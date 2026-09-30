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
    assert by["VaporTemperature"].reason_code == "CCSI_SOURCE_MISSING"


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
JOHN_APPROVED_VALIDATED = {
    "DX": {"Tag", "FinnedHeight", "FinnedLength", "TotalAirFlow", "Altitude", "EnteringDryBulb",
           "EnteringWetBulb", "EvaporatingTemperature", "LiquidTemperature", "Superheat", "Refrigerant"}
    | _D2_COMMON | {"DraintrayTypeAlt", "DraintrayMaterialAlt", "RefrigerantConnectionType", "DXDistCapillarySize",
                    "RefrigerationSystemType"},
    "HGRH": {"Tag", "FinnedHeight", "FinnedLength", "NumberOfFeeds", "TotalAirFlow", "Altitude",
             "EnteringDryBulb", "Refrigerant"}
    | _D2_COMMON | {"RefrigerantConnectionType", "TemperatureInput", "CoilType", "RefrigerationSystemType"}
    | {"TubeMaterial"},  # John 2026-09-30 (D1 "A"): 3183/3232/3237 match, 0 mismatch
    # FluidFlowRate: John 2026-09-29 ("GPM 푸시 진행") — a push decision, not match evidence.
    "CWC": {"FluidFlowRate"} | _W_WATER | _D2_COMMON | _D2_WATER | {"DraintrayTypeAlt", "DraintrayMaterialAlt"},
    "HWC": {"FluidFlowRate"} | _W_WATER | _D2_COMMON | _D2_WATER | {"CoilType"},
}
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
    entries = resolve_coil_data(LEDGER_3025_CDXC1)
    pushable = {e.ccsi_id for e in entries if e.pushable}
    assert pushable <= JOHN_APPROVED_VALIDATED["DX"]
    by = _by_id(entries)
    assert by["EnteringDryBulb"].reason_code == "CCSI_OK" and by["EnteringDryBulb"].value == "95"
    # a still-captured mapping resolves (so validation can compare it) but is never pushed
    assert by["CoilHand"].reason_code == "CCSI_NOT_VALIDATED"
    assert by["CoilHand"].value == "Left" and not by["CoilHand"].pushable


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
def test_unbuildable_fin_withholds_rows_fpi_and_fin(validated_map, surface, gauge) -> None:
    src = {**_BASE, "fin_surface": {"value": surface, "status": "review_required"},
           "fin_material": {"value": gauge, "status": "review_required"}}
    by = _by_id(resolve_coil_data(src))
    for ccsi_id in ("RowsDeep", "FinsPerInch"):
        assert by[ccsi_id].reason_code == "CCSI_GEOMETRY_RESELECT", ccsi_id
        assert not by[ccsi_id].pushable
        assert by[ccsi_id].value is not None  # still resolved so the cross-check shows the difference
    assert not by["FinSurface"].pushable and not by["FinMaterial"].pushable
    for ccsi_id in ("FinnedHeight", "NumberOfFeeds", "EnteringDryBulb"):
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

    # the water forms offer no 0.005 fin, the DX form does
    src = {"fin_material": {"value": "0.005", "status": "review_required"}}
    assert geometry_reselect_reason(src, load_coil_data_map("DX")) is None
    assert "0.005" in (geometry_reselect_reason(src, load_coil_data_map("CWC")) or "")


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
        ("fin_surface", "Sine", "FinSurface"),  # no CCSI equivalent
        ("fins_per_inch", 8.5, "FinsPerInch"),  # integer-only list, never rounded
        ("return_connection_size", 1.1, "DXReturnConnectionSize"),  # not a sixteenth
        ("coil_coating", "Finkote2 Epoxy Coil Coating", "CoilCoating"),
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


def test_only_hgrh_tube_material_is_promoted() -> None:
    # John 2026-09-30 (D1 "A"): HGRH TubeMaterial 3/3 match -> validated. DX TubeMaterial (3232 is the
    # D5 CCSI re-selection) and both FinMaterials (2 projects; 3183 is 0.0075) stay captured.
    src = {"tube_material": _gauge(0.016, "Copper"), "fin_material": _gauge(0.008, "Aluminum"), **_SMOOTH}
    hgrh = _by_id(resolve_coil_data(src, coil_type="HGRH"))
    dx = _by_id(resolve_coil_data(src, coil_type="DX"))
    assert hgrh["TubeMaterial"].reason_code == "CCSI_OK" and hgrh["TubeMaterial"].pushable
    for by, ccsi_id in ((hgrh, "FinMaterial"), (dx, "TubeMaterial"), (dx, "FinMaterial")):
        assert by[ccsi_id].reason_code == "CCSI_NOT_VALIDATED" and not by[ccsi_id].pushable, ccsi_id
    # promotion does not loosen the rule: no stated surface is still never pushed
    bare = _by_id(resolve_coil_data({"tube_material": _gauge(0.016, "Copper")}, coil_type="HGRH"))["TubeMaterial"]
    assert bare.reason_code == "CCSI_OPTION_UNMAPPED" and not bare.pushable


@pytest.mark.parametrize(
    ("sources", "ccsi_id", "why"),
    [
        ({"fin_material": _gauge(0.0075, "Aluminium")}, "FinMaterial", "0.0075"),  # never rounded to 0.008
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


def test_a_resolved_fin_is_still_withheld_by_the_reselect_gate(validated_map) -> None:
    src = {**_BASE, "fin_surface": {"value": "Sine", "status": "review_required"},
           "fin_material": _gauge(0.008, "Aluminum")}
    fin = _by_id(resolve_coil_data(src))["FinMaterial"]
    assert fin.reason_code == "CCSI_GEOMETRY_RESELECT" and fin.value == "Aluminum 0.008" and not fin.pushable


def test_ledger_replay_reads_the_material_unit_and_the_stated_tube_surface() -> None:
    import sqlite3

    sys.path.insert(0, str(ROOT / "scripts"))
    import ccsi_coil_data_readiness as replay  # pyright: ignore[reportMissingImports]

    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        create table run (run_id text, ts_utc text, ok integer, project_number text, project_name text,
                          source_filename text);
        create table coil (coil_uid text, tag text, coil_category text, circuits integer);
        create table field_observation (run_id text, coil_uid text, stage text, field_key text,
                                        value_json text, unit text, status text, blocked_reason text);
        insert into run values ('r1', '2026-09-29T00:00:00Z', 1, '3237', 'P', 'p.pdf');
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
    by = _by_id(resolve_coil_data(coils["CDXC-1"]["sources"]))
    assert by["TubeMaterial"].value == "Copper 0.016 Plain"
    assert by["FinMaterial"].value == "Aluminum 0.008"
    # CDXC-2's drawing recorded no surface: its tube stays unmapped, never borrowing CDXC-1's
    assert _by_id(resolve_coil_data(coils["CDXC-2"]["sources"]))["TubeMaterial"].reason_code == "CCSI_OPTION_UNMAPPED"


@pytest.mark.parametrize(("coil_type", "circuits", "expected"), [
    ("DX", 1, "Single-Circuit"), ("DX", 2, "Dual-Circuit Intertwined"), ("HGRH", 1, "Single-Circuit"),
])
def test_system_type_follows_circuits(coil_type, circuits, expected) -> None:
    src = {"geometry.circuits": {"value": circuits, "status": "review_required"}}
    entry = _by_id(resolve_coil_data(src, coil_type=coil_type))["RefrigerationSystemType"]
    assert entry.value == expected and entry.pushable


@pytest.mark.parametrize(("coil_type", "circuits"), [("DX", 3), ("HGRH", 2)])
def test_unobserved_circuit_count_is_unmapped_not_guessed(coil_type, circuits) -> None:
    src = {"geometry.circuits": {"value": circuits, "status": "review_required"}}
    entry = _by_id(resolve_coil_data(src, coil_type=coil_type))["RefrigerationSystemType"]
    assert entry.reason_code == "CCSI_OPTION_UNMAPPED" and not entry.pushable


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


def test_a_stated_value_always_beats_the_default() -> None:
    finkote = {"coil_coating": {"value": "Finkote2 Epoxy Coil Coating", "status": "review_required"}}
    coated = _by_id(resolve_coil_data(finkote))["CoilCoating"]
    assert coated.reason_code == "CCSI_OPTION_UNMAPPED"  # never silently "Plain"
    assert coated.value is None and not coated.pushable
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
        {"project": "P2", "tag": "CDXC-1", "sources": {"tag": "CDXC-1", "fin_surface": {"value": "Sine", "status": "review_required"}}},
    ]
    report = replay.build_report(coils, "DX")
    assert report["coils"] == 2 and report["projects"] == 2
    fin = report["fields"]["FinSurface"]
    assert fin["reason_counts"] == {"CCSI_NOT_VALIDATED": 1, "CCSI_OPTION_UNMAPPED": 1}
    assert fin["off_vocabulary"] == {"'Sine'": 1}
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
def test_gpm_is_pushed_for_all_coils_of_the_tag(coil_type) -> None:
    src = {"coil_quantity": 2,
           "airside_conditions.fluid_flow_rate_gpm": {"value": 8.44, "status": "review_required"}}
    gpm = _by_id(resolve_coil_data(src, coil_type=coil_type))["FluidFlowRate"]
    assert gpm.value == "16.88" and gpm.pushable
    unknown_qty = {"airside_conditions.fluid_flow_rate_gpm": {"value": 8.44, "status": "review_required"}}
    assert not _by_id(resolve_coil_data(unknown_qty, coil_type=coil_type))["FluidFlowRate"].pushable


def test_summary_carries_safety_flags() -> None:
    s = summarize(resolve_coil_data(LEDGER_3025_CDXC1))
    assert s["export_allowed"] is False and s["review_aid_only"] is True
    assert s["total"] == len(load_coil_data_map("DX").fields)
