"""Past-order gate: tiers, mismatch causes, proposals, adapter calibration (plan Rev 3.1)."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ccsi import order_gate as og  # noqa: E402
from coilforge.ccsi.crosscheck import crosscheck_coil  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAL_KEYS = frozenset({("3237", "CDXC-1")})

SOURCES = {
    "tag": "CDXC-1",
    "coil_quantity": 1,
    "finned_height": {"value": 21, "status": "review_required"},
    "fin_surface": {"value": "Corrugated", "status": "review_required"},
    "total_air_flow_cfm": {"value": 1000, "status": "review_required"},
    "total_capacity_mbh": {"value": 36.1, "status": "review_required"},
    "leaving_dry_bulb_f": {"value": 50.75, "status": "review_required"},
}


def _report(**values):
    """A report record in the harvest shape selection_report emits (value text only)."""
    kinds = {"TubeDiameter": "select", "FinSurface": "select", "RowsDeep": "select", "Tag": "text"}
    base = {"Tag": "CDXC-1", "FinnedHeight": "21", "FinSurface": "Corrugated", "CoilQuantity": "1",
            "TotalAirFlow": "1000", "TubeDiameter": "3/8 1.00 x 0.866", "Capacity": "36.1", "LeavingDryBulb": "50.75"}
    base.update(values)
    return {"fields": {k: {"label": k, "kind": kinds.get(k, "number"), "value": v, "raw": v} for k, v in base.items()}}


def _coil(report=None, sources=None, flags=(), tag="CDXC-1"):
    rows = crosscheck_coil(report or _report(), sources or SOURCES, coil_type="DX")
    return {"project": "", "tag": tag, "coil_type": "DX", "rows": rows, "report_flags": list(flags)}


def _project(number, coil, kind="order", stamp="7_7_2026,_0_48_52_AM"):
    # A real CCSI export stamp (before PUSH_START): an undated order is fail-closed to order_after_push.
    coil["project"] = number
    return {"project": number, "report_kind": kind, "truth_file": f"{number}_REV1_{stamp}.pdf", "coils": [coil]}


def _by_id(rows):
    return {r["ccsi_id"]: r for r in rows}


# ------------------------------------------------------------------ tiers
def test_tiers_separate_calibration_order_and_quote_only() -> None:
    rows = og.annotate([_project("3237", _coil()), _project("3300", _coil()), _project("3301", _coil(), kind="quote_only")], CAL_KEYS)
    tiers = {r["project"]: r["tier"] for r in rows}
    assert tiers == {"3237": "calibration", "3300": "order", "3301": "quote_only"}


# ------------------------------------------------------------------ causes
def test_only_mismatch_rows_get_a_cause_and_tag_is_never_judged() -> None:
    rows = _by_id(og.annotate([_project("3300", _coil(_report(FinnedHeight="24")))], CAL_KEYS))
    assert "Tag" not in rows
    assert rows["FinnedHeight"]["cause"] == "unexplained" and rows["FinnedHeight"]["counts_as_defect"]
    for r in rows.values():
        if r["verdict"] != "mismatch":
            assert r["cause"] is None and not r["counts_as_defect"], r


def test_a_wrong_d2_default_is_a_defect_not_an_explanation() -> None:
    # TubeDiameter is not stated -> default profile 3/8; the order used 1/2" tube.
    rows = _by_id(og.annotate([_project("3300", _coil(_report(TubeDiameter="1/2 1.25 x 1.0825")))], CAL_KEYS))
    assert rows["TubeDiameter"]["reason_code"] == "CCSI_DEFAULT_PROFILE"
    assert rows["TubeDiameter"]["cause"] == "default_counterexample"
    assert rows["TubeDiameter"]["counts_as_defect"]


def test_airflow_off_by_the_quantity_is_a_push_defect_but_capacity_is_notation() -> None:
    report = _report(CoilQuantity="3", TotalAirFlow="3000", Capacity="108.3")
    rows = _by_id(og.annotate([_project("3300", _coil(report))], CAL_KEYS))
    assert rows["TotalAirFlow"]["cause"] == "quantity_semantics" and rows["TotalAirFlow"]["counts_as_defect"]
    assert rows["Capacity"]["cause"] == "notation" and not rows["Capacity"]["counts_as_defect"]


def test_changed_at_order_explains_only_when_coilforge_matches_rev0() -> None:
    coil = _coil(_report(FinnedHeight="24"))
    fh = next(r for r in coil["rows"] if r["ccsi_id"] == "FinnedHeight")
    fh.update(changed_at_order=True, rev0="21")
    assert og.mismatch_cause(fh, coil, None) == "changed_at_order"
    fh.update(rev0="18")
    assert og.mismatch_cause(fh, coil, None) == "changed_at_order_cf_differs"
    assert og.CAUSES["changed_at_order_cf_differs"] is True


def test_reselect_predicted_is_explained() -> None:
    row = {"ccsi_id": "RowsDeep", "verdict": "mismatch", "reason_code": "CCSI_GEOMETRY_RESELECT",
           "coilforge": "4", "ccsi": "6", "role": "input"}
    assert og.mismatch_cause(row, {"coil_type": "DX", "rows": [row]}, None) == "reselect_predicted"
    assert og.CAUSES["reselect_predicted"] is False


def test_report_flags_are_matched_per_field_and_never_mask_other_fields() -> None:
    flags = ["unmatched_option:FinSurface", "unparsed_composite:Connection Type"]
    assert og.field_flags(flags, "DX") == {
        "FinSurface": ["unmatched_option:FinSurface"],
        "RefrigerantConnectionType": ["unparsed_composite:Connection Type"],
        "ConnectionMaterial": ["unparsed_composite:Connection Type"],
    }
    coil = _coil(_report(FinSurface="Sine", FinnedHeight="24"), flags=flags)
    rows = _by_id(og.annotate([_project("3300", coil)], CAL_KEYS))
    assert rows["FinSurface"]["cause"] == "map_options_incomplete" and not rows["FinSurface"]["counts_as_defect"]
    assert rows["FinnedHeight"]["cause"] == "unexplained"


# ------------------------------------------------------------------ proposals
def _info(role="input", status="validated", has_source=True):
    return og.FieldInfo(role, status, "number", has_source)


def _row(project, verdict="match", *, ccsi="21", field="FinnedHeight", tier="order", cause=None, code="CCSI_OK"):
    return {"project": project, "tag": "CDXC-1", "coil_type": "DX", "tier": tier, "coil_reselect": False,
            "ccsi_id": field, "role": "input", "verdict": verdict, "reason_code": code, "cause": cause,
            "counts_as_defect": bool(cause and og.CAUSES[cause]), "coilforge": ccsi, "ccsi": ccsi, "rev0": None,
            "truth_file": None}


_PASS = {"status": "PASS", "fields": {"DX:FinnedHeight": {"status": "calibrated"}}}


def _proposal(rows, info, calibration=_PASS):
    return og.proposals(rows, calibration, field_info=lambda _t, _i: info)["DX:FinnedHeight"]


def test_a_defect_on_an_order_project_proposes_demotion_only_with_a_calibrated_adapter() -> None:
    rows = [_row("3300"), _row("3301", "mismatch", cause="unexplained")]
    assert _proposal(rows, _info())["proposal"] == "demote_candidate"
    failed = {"status": "FAIL", "fields": {"DX:FinnedHeight": {"status": "adapter_mismatch"}}}
    assert _proposal(rows, _info(), failed)["proposal"] == "held_adapter"
    incomplete = {"status": "INCOMPLETE", "fields": {"DX:FinnedHeight": {"status": "calibrated"}}}
    assert _proposal(rows, _info(), incomplete)["proposal"] == "held_adapter"


def test_explained_mismatches_and_other_tiers_never_demote() -> None:
    rows = [_row("3300"), _row("3301", "mismatch", cause="changed_at_order"),
            _row("3237", "mismatch", cause="unexplained", tier="calibration"),
            _row("3302", "mismatch", cause="unexplained", tier="quote_only")]
    assert _proposal(rows, _info())["proposal"] == "supported"


def test_promotion_needs_three_order_projects_two_values_an_input_and_a_source() -> None:
    three = [_row("3300", ccsi="21"), _row("3301", ccsi="24"), _row("3302", ccsi="21")]
    captured = _info(status="captured")
    assert _proposal(three, captured)["proposal"] == "promote_candidate"
    assert _proposal(three[:2], captured)["proposal"] == "insufficient"
    assert _proposal([_row(p, ccsi="21") for p in ("3300", "3301", "3302")], captured)["proposal"] == "insufficient"
    assert _proposal(three, _info(role="computed", status="captured"))["proposal"] == "read_back_only"
    assert _proposal(three, _info(status="captured", has_source=False))["proposal"] == "no_source"
    defaults = [_row(p, ccsi=v, code="CCSI_DEFAULT_PROFILE") for p, v in (("3300", "21"), ("3301", "24"), ("3302", "18"))]
    assert _proposal(defaults, captured)["proposal"] == "insufficient"
    calibration_only = [_row(p, ccsi=v, tier="calibration") for p, v in (("3300", "21"), ("3301", "24"), ("3302", "18"))]
    assert _proposal(calibration_only, captured)["proposal"] == "insufficient"


def test_fluid_temperatures_that_ccsi_solves_together_need_johns_decision() -> None:
    rows = [dict(_row(p, ccsi=v, field="LeavingFluidTemp"), coil_type="CWC") for p, v in (("1", "54"), ("2", "55"), ("3", "56"))]
    out = og.proposals(rows, {"status": "PASS", "fields": {}}, field_info=lambda _t, _i: _info(status="captured"))
    assert out["CWC:LeavingFluidTemp"]["proposal"] == "needs_decision"


def test_a_validated_field_the_report_never_prints_is_untestable() -> None:
    rows = [_row("3300", "absent_on_form"), _row("3301", "absent_on_form")]
    assert _proposal(rows, _info())["proposal"] == "untestable_from_report"


def test_a_printed_field_without_order_evidence_yet_is_insufficient_not_untestable() -> None:
    rows = [_row("3237", tier="calibration"), _row("3300", "absent_on_form")]
    assert _proposal(rows, _info())["proposal"] == "insufficient"


# ------------------------------------------------------------------ calibration
def _harvest(**values):
    return {k: {"value": v} for k, v in values.items()}


def test_calibration_agrees_across_formats_and_ignores_non_evidence() -> None:
    report = {"FinnedHeight": {"value": "21"}, "FaceVelocity": {"value": "429"}, "LeavingDryBulb": {"value": "50.75"},
              "Capacity": {"value": "108.93"}, "DXReturnConnectionSize": {"value": '7/8"'},
              "Refrigerant": {"value": "R-32"}, "RowsDeep": {"value": "4"}}
    harvest = _harvest(FinnedHeight="21.000", FaceVelocity="428.57", LeavingDryBulb="55.00", Capacity="0",
                       DXReturnConnectionSize="Calculate", Refrigerant="R32", RowsDeep="Optimise")
    cal = og.calibrate([{"project": "3237", "tag": "CDXC-1", "coil_type": "DX",
                         "report_fields": report, "harvest_fields": harvest}])
    fields = cal["fields"]
    assert fields["DX:FinnedHeight"]["status"] == "calibrated"
    assert fields["DX:FaceVelocity"]["status"] == "calibrated"  # computed: 1% band
    assert fields["DX:Refrigerant"]["status"] == "calibrated"
    for no_evidence in ("LeavingDryBulb", "Capacity", "DXReturnConnectionSize", "RowsDeep"):
        assert fields[f"DX:{no_evidence}"]["status"] == "adapter_uncalibrated", no_evidence
    assert cal["status"] == "PASS"


def test_a_calibration_disagreement_fails_and_a_missing_report_is_incomplete() -> None:
    bad = og.calibrate([{"project": "3237", "tag": "CDXC-1", "coil_type": "DX",
                         "report_fields": {"FinnedHeight": {"value": "24", "raw": '24.000"'}},
                         "harvest_fields": _harvest(FinnedHeight="21")}])
    assert bad["status"] == "FAIL" and bad["adapter_mismatch"] == ["DX:FinnedHeight"]
    missing = og.calibrate([{"project": "3154", "tag": "HHWC-1", "coil_type": "HWC", "report_fields": None,
                             "harvest_fields": {}, "missing_reason": "report:cloud_only_reports"}])
    assert missing["status"] == "INCOMPLETE"
    assert missing["coils"] == [{"coil": "3154/HHWC-1", "status": "report:cloud_only_reports"}]


# ------------------------------------------------------------------ tables + guarantees
def test_decision_tables_count_order_tier_only() -> None:
    rows = [_row("3300", "mismatch", field="TubeDiameter", cause="default_counterexample", code="CCSI_DEFAULT_PROFILE"),
            _row("3237", "mismatch", field="TubeDiameter", tier="calibration", code="CCSI_DEFAULT_PROFILE",
                 cause="default_counterexample")]
    tables = og.decision_tables(rows)
    assert tables["D2"]["DX"] == {"TubeDiameter": {"default_counterexample": 1}}


def test_fluid_table_shows_which_water_inputs_the_order_kept() -> None:
    def water(project, field, verdict):
        return dict(_row(project, verdict, field=field, cause="unexplained" if verdict == "mismatch" else None),
                    coil_type="HWC", tag="HHWC-1")
    rows = [water("3300", "EnteringFluidTemp", "match"), water("3300", "LeavingFluidTemp", "match"),
            water("3300", "FluidFlowRate", "mismatch"), water("3301", "EnteringFluidTemp", "match"),
            water("3301", "LeavingFluidTemp", "match"), water("3301", "FluidFlowRate", "mismatch"),
            dict(water("3237", "FluidFlowRate", "match"), tier="calibration")]
    assert og.decision_tables(rows)["fluid"] == {"HWC": {"EWT match, LWT match, GPM unexplained": 2}}


def test_rule_candidates_show_what_orders_printed_for_default_filled_fields() -> None:
    def ends(project, verdict, ccsi):
        return dict(_row(project, verdict, field="ConnectionEnds", code="CCSI_DEFAULT_PROFILE",
                         cause="default_counterexample" if verdict == "mismatch" else None),
                    coil_type="HGRH", coilforge="Same End Only", ccsi=ccsi)
    rows = [ends("3300", "mismatch", "Opposite End Only"), ends("3301", "mismatch", "Opposite End Only"),
            ends("3302", "absent_on_form", None)]
    table = og.decision_tables(rows)["rule_candidates"]["HGRH"]["ConnectionEnds"]
    assert table == {"source": "default_profile", "default": "Same End Only",
                     "report_values": {"Opposite End Only": 2}, "not_printed": 1}
    props = og.proposals(rows, _PASS | {"fields": {"HGRH:ConnectionEnds": {"status": "calibrated"}}},
                         field_info=lambda _t, _i: _info())
    assert props["HGRH:ConnectionEnds"]["positive_only"] is False  # only a Coating line is positive-only
    assert og.POSITIVE_ONLY_IDS == frozenset({"CoilCoating"})


def test_order_gate_module_is_pure() -> None:
    source = (ROOT / "src/coilforge/ccsi/order_gate.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    for banned in (r"\bopen\(", r"write_text", r"write_bytes", r"\.rename\(", r"\.unlink\(", r"sqlite3",
                   r"os\.scandir", r"read_bytes", r"requests\b"):
        assert not re.search(banned, code), banned


def test_the_summary_renders_from_a_computed_gate() -> None:
    spec = importlib.util.spec_from_file_location("ccsi_order_gate", ROOT / "scripts/ccsi_order_gate.py")
    assert spec is not None and spec.loader is not None
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    rows = og.annotate([_project("3300", _coil(_report(FinnedHeight="24")))], CAL_KEYS)
    cal = og.calibrate([])
    gate = {"input": "x.json", "code_version": "test", "stale_sources": ["scripts/ccsi_report_crosscheck.py"],
            "calibration": cal, "tiers": {"order": {"projects": 1, "coils": 1}}, "runner_skips": {},
            "cloud_only": {}, "proposals": og.proposals(rows, cal), "decision_tables": og.decision_tables(rows)}
    text = script.render(gate)
    assert "Stale cross-check" in text and "INCOMPLETE" in text
    assert "| held_adapter | DX `FinnedHeight`" in text  # a defect, held until calibration passes


def test_rule_candidates_include_fields_the_submittal_never_states() -> None:
    def vapor(project):
        return dict(_row(project, "submittal_missing", field="VaporTemperature", ccsi="140",
                         code="CCSI_SOURCE_MISSING"), coil_type="HGRH", coilforge=None)
    def basis(project, value):
        return dict(_row(project, "unmapped_ccsi_field", field="ACFM", ccsi=value, code="CCSI_NO_SOURCE"),
                    coilforge=None)
    rows = [vapor("3300"), vapor("3301"), basis("3300", "Actual"), basis("3301", "Standard"), basis("3302", "Actual")]
    tables = og.decision_tables(rows)["rule_candidates"]
    assert tables["HGRH"]["VaporTemperature"] == {"source": "submittal_silent", "default": None,
                                                  "report_values": {"140": 2}, "not_printed": 0}
    assert tables["DX"]["ACFM"]["source"] == "no_source"
    assert tables["DX"]["ACFM"]["report_values"] == {"Actual": 2, "Standard": 1}


def test_a_printed_precision_difference_is_rounding_not_a_defect() -> None:
    def row(cf, rep):
        return {"ccsi_id": "EnteringDryBulb", "verdict": "mismatch", "reason_code": "CCSI_OK",
                "coilforge": cf, "ccsi": rep, "role": "input"}
    assert og.mismatch_cause(row("77.9", "77.89"), {"coil_type": "DX", "rows": []}, None) == "rounding"
    assert og.mismatch_cause(row("1050", "1048"), {"coil_type": "DX", "rows": []}, None) == "rounding"
    assert og.mismatch_cause(row("68.4", "68"), {"coil_type": "DX", "rows": []}, None) == "unexplained"
    assert og.CAUSES["rounding"] is False


def test_a_standard_air_order_is_an_air_basis_difference_not_a_defect() -> None:
    """John 2026-10-01: CoilForge pushes Actual (Direct Coil selections were calculated in ACFM).

    An order rated on Standard air therefore disagrees on the basis itself, on Altitude (CCSI locks it
    to 0 under Standard) and on the rating — a known basis difference, never a defect. The basis row
    is now a default, so this must win over `default_counterexample`.
    """
    def row(ccsi_id, cf, rep, code="CCSI_OK", role="input"):
        return {"ccsi_id": ccsi_id, "verdict": "mismatch", "reason_code": code,
                "coilforge": cf, "ccsi": rep, "role": role}

    basis = row("ACFM", "Actual", "Standard", code="CCSI_DEFAULT_PROFILE")
    altitude = row("Altitude", "650", "0")
    capacity = row("Capacity", "48.2", "44.9", role="computed")
    standard = {"coil_type": "DX", "rows": [basis, altitude, capacity]}
    assert og.mismatch_cause(basis, standard, None) == "air_basis"
    assert og.mismatch_cause(altitude, standard, None) == "air_basis"
    assert og.mismatch_cause(capacity, standard, None) == "air_basis"
    assert og.CAUSES["air_basis"] is False

    # a different site altitude under Standard is NOT the lock
    other_site = row("Altitude", "650", "400")
    assert og.mismatch_cause(other_site, {"coil_type": "DX", "rows": [basis, other_site]}, None) == "unexplained"
    # on an Actual-air order nothing is explained by the basis: a wrong default stays a defect
    actual_basis = row("ACFM", "Standard", "Actual", code="CCSI_DEFAULT_PROFILE")
    actual = {"coil_type": "DX", "rows": [actual_basis, row("Capacity", "48.2", "44.9", role="computed")]}
    assert og.mismatch_cause(actual_basis, actual, None) == "default_counterexample"
    assert og.mismatch_cause(actual["rows"][1], actual, None) == "unexplained"
    # unrelated fields are untouched by a Standard basis
    edb = row("EnteringDryBulb", "80", "75")
    assert og.mismatch_cause(edb, {"coil_type": "DX", "rows": [basis, edb]}, None) == "unexplained"


def test_a_ruled_order_change_is_explained_only_for_that_exact_disagreement() -> None:
    """John 2026-10-12 ("셋 다 A"): CoilForge matches the submittal and the order changed — stop re-asking.

    The ruling is keyed to project + tag + field AND both values, so a moved CoilForge value, a new
    order value, or the same values on another coil is judged afresh.
    """
    def row(cf, rep, code="CCSI_OK"):
        return {"ccsi_id": "RowsDeep", "verdict": "mismatch", "reason_code": code,
                "coilforge": cf, "ccsi": rep, "role": "input"}

    hgrh = {"coil_type": "HGRH", "tag": "RHHGRC-1", "rows": []}
    assert og.mismatch_cause(row("2", "1"), hgrh, None, project="2447") == "ruled_order_change"
    assert og.CAUSES["ruled_order_change"] is False
    assert og.mismatch_cause(row("2", "1"), hgrh, None, project="9999") == "unexplained"
    assert og.mismatch_cause(row("3", "1"), hgrh, None, project="2447") == "unexplained"
    assert og.mismatch_cause(row("2", "4"), hgrh, None, project="2447") == "unexplained"
    # a ruled default counterexample stops counting against the default
    tube = {"ccsi_id": "TubeMaterial", "verdict": "mismatch", "reason_code": "CCSI_DEFAULT_PROFILE",
            "coilforge": "Copper 0.018 Plain", "ccsi": "Copper 0.020 Plain", "role": "input"}
    hwc = {"coil_type": "HWC", "tag": "HHWC-1", "rows": [tube]}
    assert og.mismatch_cause(tube, hwc, None, project="2811") == "ruled_order_change"
    assert og.mismatch_cause(tube, hwc, None, project="2812") == "default_counterexample"


def test_annotate_threads_the_project_into_the_ruling() -> None:
    coil = _coil(_report(EnteringDryBulb="75.59"), {**SOURCES, "tag": "CDXC-3",
                                                     "entering_dry_bulb_f": {"value": 74, "status": "review_required"}},
                 tag="CDXC-3")
    rows = _by_id(og.annotate([_project("3239", coil)], CAL_KEYS))
    assert rows["EnteringDryBulb"]["verdict"] == "mismatch"
    assert rows["EnteringDryBulb"]["cause"] == "ruled_order_change"
    assert rows["EnteringDryBulb"]["counts_as_defect"] is False


# ------------------------------------------------------------------ estimate confirmation (John 2026-10-12)
def test_report_date_reads_both_ccsi_export_stamps_and_nothing_else() -> None:
    from datetime import date
    assert og.report_date("2298_-_Rouge_Gateway_REV1_6_28_2026,11_24_38_PM.pdf") == date(2026, 6, 28)
    assert og.report_date("2600_-_Medical_Centre_REV1_9_9_2026,__47_30_PM.pdf") == date(2026, 9, 9)
    assert og.report_date("2623_-_CC_Fire_Station_8_REV0_2026-06-05_3_01_04_p.m..pdf") == date(2026, 6, 5)
    assert og.report_date("3300_REV1.pdf") is None
    assert og.report_date(None) is None


def test_an_order_exported_after_the_push_or_undated_is_not_independent_evidence() -> None:
    projects = [_project("3300", _coil()), _project("3301", _coil(), stamp="9_30_2026,1_00_00_PM"),
                _project("3302", _coil()), _project("3237", _coil(), stamp="10_1_2026,1_00_00_PM")]
    projects[2]["truth_file"] = "3302_REV1.pdf"
    tiers = {r["project"]: r["tier"] for r in og.annotate(projects, CAL_KEYS)}
    assert tiers == {"3300": "order", "3301": "order_after_push", "3302": "order_after_push", "3237": "calibration"}


def _est(rows, register, info=None):
    return og.evaluate_estimates(rows, register, field_info=lambda _t, _i: info or _info())


def _default(project, ccsi, *, tag="CDXC-1", field="TubeDiameter", cf="3/8 1.00 x 0.866", tier="order", rev0=None,
             cause=None, date="2026-07-07", verdict=None):
    verdict = verdict or ("match" if og.same_value(cf, ccsi) else "mismatch")
    cause = cause if cause is not None else ("default_counterexample" if verdict == "mismatch" else None)
    return dict(_row(project, verdict, field=field, tier=tier, cause=cause, code="CCSI_DEFAULT_PROFILE"),
                tag=tag, coilforge=cf, ccsi=ccsi, rev0=rev0, report_date=date, source_key=None, reason="default")


_TUBE = og.Estimate("DX:TubeDiameter=default", "DX", "TubeDiameter", "default", "3/8 1.00 x 0.866", "harvest",
                    "2026-09-29", lambda r: r.get("reason_code") == "CCSI_DEFAULT_PROFILE")
_HALF = "1/2 1.25 x 1.0825"
_EIGHTH = "3/8 1.00 x 0.866"


def test_a_default_match_counts_here_but_never_in_proposals() -> None:
    rows = [_default(p, _EIGHTH) for p in "12345"]
    assert _est(rows, [_TUBE])[_TUBE.key]["verdict"] == "confirm_candidate"
    assert _proposal([dict(r, ccsi_id="FinnedHeight") for r in rows], _info())["proposal"] == "insufficient"


def test_projects_not_coils_meet_the_threshold() -> None:
    four = [_default(p, _EIGHTH, tag=t) for p in "1234" for t in ("CDXC-1", "CDXC-2", "CDXC-3")]
    out = _est(four, [_TUBE])[_TUBE.key]
    assert (out["verdict"], out["order_projects"], out["order_coils"]) == ("insufficient_projects", 4, 12)
    assert _est(four + [_default("5", _EIGHTH)], [_TUBE])[_TUBE.key]["verdict"] == "confirm_candidate"


def test_one_unexplained_counterexample_blocks_confirmation() -> None:
    rows = [_default(p, _EIGHTH) for p in "12345"] + [_default("6", _HALF)]
    out = _est(rows, [_TUBE])[_TUBE.key]
    assert out["verdict"] == "not_confirmed_unexplained"
    assert out["unexplained"][0]["project"] == "6" and list(out["splits"].values()) == [[]]


def test_explained_counterexamples_and_excluded_rows() -> None:
    good = [_default(p, _EIGHTH) for p in "12345"]
    explained = [_default("6", _HALF, cause="ruled_order_change"), _default("7", _HALF, cause="air_basis"),
                 _default("8", _HALF, rev0=_EIGHTH)]
    excluded = [_default("9", _HALF, cause="report_unparsed"), _default("10", _HALF, cause="reselect_predicted"),
                _default("11", _HALF, tier="order_after_push"), _default("12", None, verdict="absent_on_form")]
    out = _est(good + explained + excluded, [_TUBE])[_TUBE.key]
    assert out["verdict"] == "confirm_candidate"
    assert out["explained"] == {"ruled_order_change": 1, "air_basis": 1, "changed_at_order": 1}
    assert out["excluded"] == {"report_unparsed": 1, "reselect_predicted": 1, "order_after_push": 1, "not_printed": 1}


def test_a_value_the_map_cannot_express_blocks_instead_of_hiding() -> None:
    rows = [_default(p, _EIGHTH) for p in "12345"] + [_default("6", _HALF, cause="map_options_incomplete")]
    assert _est(rows, [_TUBE])[_TUBE.key]["verdict"] == "not_confirmed_unexplained"


def test_rounding_explains_printed_precision_but_never_around_zero() -> None:
    fouling = og.Estimate("DX:AirSideFoulingFactor=default", "DX", "AirSideFoulingFactor", "default", "0",
                          "harvest", None, lambda r: True)
    good = [_default(p, "0", field="AirSideFoulingFactor", cf="0") for p in "12345"]
    near_zero = _default("6", "0.001", field="AirSideFoulingFactor", cf="0")
    assert _est(good + [near_zero], [fouling])[fouling.key]["verdict"] == "not_confirmed_unexplained"
    vapor = og.Estimate("HGRH:VaporTemperature=default", "HGRH", "VaporTemperature", "default", "140",
                        "order+quote", None, lambda r: True)
    good = [dict(_default(p, "140", field="VaporTemperature", cf="140"), coil_type="HGRH") for p in "12345"]
    printed = dict(_default("6", "140.2", field="VaporTemperature", cf="140"), coil_type="HGRH")
    out = _est(good + [printed], [vapor])[vapor.key]
    assert out["verdict"] == "confirm_candidate" and out["explained"] == {"rounding": 1}


def test_a_substitution_is_judged_on_the_value_actually_pushed() -> None:
    # The map says "0.008"; the push and the order say "Aluminum 0.008" — never a false counterexample.
    sub = og.Estimate("DX:FinMaterial=substitution", "DX", "FinMaterial", "substitution", "aluminum 0.0075 -> 0.008",
                      "order+quote", "2026-10-01", lambda r: og.SUBSTITUTED_MARK in str(r.get("reason") or ""))
    reason = "0.0075 is not a CCSI option — 0.008 sent in its place, as on the ordered selections"
    rows = [dict(_row(p, field="FinMaterial", ccsi="Aluminum 0.008"), report_date="2026-07-07",
                 source_key="fin_material", reason=reason) for p in "12345"]
    out = _est(rows, [sub])[sub.key]
    assert out["verdict"] == "confirm_candidate"
    assert out["evidence_basis"] == "in_sample" and out["holdout"] is None


def test_an_extra_estimate_is_judged_against_its_own_value() -> None:
    q9 = next(e for e in og.EXTRA_ESTIMATES if e.key == "HWC:FinSurface=silent")
    rows = [dict(_row(p, "submittal_missing", field="FinSurface", ccsi="Flat", code="CCSI_SOURCE_MISSING"),
                 coil_type="HWC", coilforge=None, report_date="2026-07-07") for p in "1234"]
    rows.append(dict(rows[0], project="5", ccsi="Corrugated"))
    out = _est(rows, [q9])[q9.key]
    assert out["verdict"] == "not_confirmed_unexplained" and out["order_projects"] == 4


def _capillary_rows(groups):
    rows = []
    for project, ccsi, rows_deep, when in groups:
        rows.append(_default(project, ccsi, field="DXDistCapillarySize", cf="1/4 x 0.025", date=when))
        rows.append(dict(_row(project, field="RowsDeep", ccsi=rows_deep), report_date=when))
    return rows


_CAP = og.Estimate("DX:DXDistCapillarySize=default", "DX", "DXDistCapillarySize", "default", "1/4 x 0.025",
                   "harvest", None, lambda r: r.get("reason_code") == "CCSI_DEFAULT_PROFILE")


def test_a_clean_split_is_proposed_and_a_date_only_split_is_superseded() -> None:
    early = [(p, "3/16 x 0.025", "6", "2026-06-03") for p in "123"]
    late = [(p, "1/4 x 0.025", "4", "2026-06-10") for p in "456"]
    out = _est(_capillary_rows(early + late), [_CAP])[_CAP.key]
    assert out["verdict"] == "conditional_candidate"  # rows-deep also separates them
    found = {s["attribute"]: s for s in next(iter(out["splits"].values()))}
    assert set(found) == {"RowsDeep", "report_date"} and all(s["ambiguous"] for s in found.values())
    assert (found["report_date"]["bad"], found["report_date"]["good"]) == ("<= 2026-06-03", ">= 2026-06-10")
    # same rows-deep on both sides: only the export date separates them — an order-side practice change
    same = [(p, c, "4", d) for p, c, _r, d in early + late]
    assert _est(_capillary_rows(same), [_CAP])[_CAP.key]["verdict"] == "superseded_candidate"
    # fewer than three projects on the counterexample side never proposes a condition
    two = [g for g in same if g[0] != "3"]
    assert _est(_capillary_rows(two), [_CAP])[_CAP.key]["verdict"] == "not_confirmed_unexplained"


def test_rating_values_never_split() -> None:
    attrs = {(p, "C"): {"Capacity": v} for p, v in (("1", 10), ("2", 11), ("3", 12), ("4", 50), ("5", 51), ("6", 52))}
    assert og.pure_splits([("1", "C"), ("2", "C"), ("3", "C")], [("4", "C"), ("5", "C"), ("6", "C")], attrs) == []
    assert "Capacity" not in og.SPLIT_CATEGORY_IDS + og.SPLIT_THRESHOLD_IDS


def test_after_the_push_only_a_disagreement_counts_against_a_confirmed_value() -> None:
    rows = [_default(p, _EIGHTH) for p in "12345"]
    echo = _default("6", _EIGHTH, tier="order_after_push", date="2026-10-05")
    changed = _default("7", _HALF, tier="order_after_push", date="2026-10-05")
    confirmed = _info(status="confirmed")
    assert _est(rows + [echo], [_TUBE], confirmed)[_TUBE.key]["verdict"] == "confirm_candidate"
    out = _est(rows + [echo, changed], [_TUBE], confirmed)[_TUBE.key]
    assert out["verdict"] == "confirmed_contradicted"
    assert out["contradicted"] == [{"project": "7", "tag": "CDXC-1", "order": _HALF}]
    assert _est(rows + [changed], [_TUBE])[_TUBE.key]["verdict"] == "confirm_candidate"  # validated: not watched yet


def test_holdout_is_shown_only_for_harvest_derived_estimates_and_only_before_the_push() -> None:
    rows = [_default(p, _EIGHTH) for p in "12345"]
    rows += [_default("8", _EIGHTH, tier="quote_only"), _default("9", _HALF, tier="quote_only"),
             _default("10", _HALF, tier="quote_only", date="2026-10-02")]
    assert _est(rows, [_TUBE])[_TUBE.key]["holdout"] == {"match": 1, "differ": 1}
    in_sample = og.Estimate(_TUBE.key, "DX", "TubeDiameter", "default", "x", "order+quote", None, _TUBE.select)
    assert _est(rows, [in_sample])[_TUBE.key]["holdout"] is None


def test_the_register_derives_from_the_maps_and_leaves_acfm_out() -> None:
    register = {e.key: e for e in og.estimate_register()}
    assert not any(e.ccsi_id == "ACFM" for e in register.values())
    assert register["HGRH:VaporTemperature=default"].evidence_basis == "in_sample"
    assert register["DX:TubeDiameter=default"].evidence_basis == "independent"
    assert register["DX:FinMaterial=substitution"].evidence_basis == "in_sample"
    assert register["DX:RefrigerationSystemType=style_map"].kind == "style_map"
    assert {e.key for e in og.EXTRA_ESTIMATES} <= set(register)


def test_the_substitution_mark_is_what_resolve_coil_data_writes() -> None:
    from coilforge.ccsi.coil_data_map import resolve_coil_data
    entries = {e.ccsi_id: e for e in resolve_coil_data({"fin_material": {"value": "0.0075", "unit": "Aluminum"}},
                                                        coil_type="DX")}
    assert og.SUBSTITUTED_MARK in entries["FinMaterial"].reason, entries["FinMaterial"].reason


def test_the_summary_renders_an_estimates_section_when_present() -> None:
    spec = importlib.util.spec_from_file_location("ccsi_order_gate", ROOT / "scripts/ccsi_order_gate.py")
    assert spec is not None and spec.loader is not None
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    rows = og.annotate([_project("3300", _coil())], CAL_KEYS)
    cal = og.calibrate([])
    gate = {"input": "x.json", "code_version": "test", "stale_sources": [], "calibration": cal,
            "tiers": {"order": {"projects": 1, "coils": 1}}, "runner_skips": {}, "cloud_only": {},
            "proposals": og.proposals(rows, cal), "decision_tables": og.decision_tables(rows),
            "estimates": og.evaluate_estimates(rows, og.estimate_register())}
    text = script.render(gate)
    assert "## Estimates — strict confirmation" in text and "`DX:TubeDiameter=default`" in text
