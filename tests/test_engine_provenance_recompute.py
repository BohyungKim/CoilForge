"""1c': rule_firing stops being empty.

Migration 3 created `rule_firing` / `engine_call` and then nothing filled them — 0 rows
against 392 runs — because `_attach_engine_provenance` only ever fired on a Tier-A manual
fill, the single wired path that hands the `HeaderPrepopulateResponse` back. The frozen
`pdf_to_template_drawing` discards its own response, so an ordinary analyse recorded which
DIMENSION came out of the engine but never which RULE produced it. That missing edge is
the whole distance between "O was wrong nine times" and "R-061v is wrong", and only the
second one can be acted on.

`_attach_recomputed_engine_provenance` closes it by re-running the engine caller-side,
purely to observe. The tests here exist because a reconstruction is a CLAIM, and the two
ways it can go wrong are both silent:

  1. it changes the drawing while pretending to observe it, or
  2. it reconstructs a DIFFERENT call from the one that drew, and the corpus quietly
     attributes real dimensions to rules that never produced them.

So: the drawn artifacts are snapshot-compared byte for byte, and every recomputed slot is
checked against the slot the drawing actually rendered. A mismatch is recorded as
`fidelity='drifted'` and KEPT — suppressing it would delete the only evidence that the
reconstruction is not to be believed.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from coilforge.capture import db  # noqa: E402
from coilforge.capture.record import capture_milestone  # noqa: E402
from coilforge.capture.schema import MIGRATIONS  # noqa: E402
from coilforge.services import direct_coil_drawing_pipeline as pipeline  # noqa: E402
from coilforge.workflows import submittal_to_drawing as s2d  # noqa: E402
from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    _attach_recomputed_engine_provenance,
    _extract_candidates,
    derive_coil_template_drawing,
)

# Everything the helper is forbidden to touch. `svg` and `slot_values` are the drawing;
# the rest are what the browser and the ledger read off the same result.
DRAWN_KEYS = (
    "svg",
    "slot_values",
    "slot_sources",
    "populated_slots",
    "missing_required_slots",
    "drawing_parameter_set",
    "template_id",
    "extracted",
)


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    """A throwaway ledger outside any git working tree."""
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(tmp_path / "capture.sqlite3"))
    monkeypatch.delenv(db.ENV_CAPTURE_ENABLED, raising=False)
    db.reset_caches_for_tests()
    yield tmp_path / "capture.sqlite3"
    db.reset_caches_for_tests()


def _rows(path: Path, sql: str) -> list[tuple]:
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def _spec(**overrides):
    """A DX/NOVA/B20 derive spec — the same shape test_derive_review_surfaces uses."""
    candidate = json.loads(json.dumps(_extract_candidates({})[0].model_dump(), default=str))
    spec = {
        "coil_category": "DX",
        "coil_hand": "LH",
        "tag": candidate["tag"]["value"],
        "circuits": 2,
        "rows": 4,
        "feeds": 8,
        "finned_height": 24.0,
        "finned_length": 48.0,
        "suction_conn_size": 1.375,
        "product_type": "NOVA",
        "unit_size": "B20",
        "panel": {},
    }
    spec.update(overrides)
    return spec


def _derived():
    return derive_coil_template_drawing(_spec())


# --------------------------------------------------------------------------- #
# It fires at all — the gap this whole change exists to close
# --------------------------------------------------------------------------- #
def test_an_ordinary_derive_now_carries_rule_attribution():
    """Before 1c' this result had no `engine_provenance` at all unless the engineer had
    manually filled something, which is why the table sat at zero rows."""
    provenance = _derived().get("engine_provenance")

    assert provenance, "no provenance attached — rule_firing would stay empty"
    assert provenance["source"] == "recomputed"
    assert provenance["fidelity"] == "verified", provenance.get("drift_keys")
    assert provenance["call"]["n_values"] > 0

    firings = provenance["firings"]
    assert firings, "an engine call with values must report the rules that produced them"
    # The edge that did not exist before: field -> rule.
    attributed = [f for f in firings if f.get("rule_id")]
    assert attributed, "every firing lost its rule_id — attribution is still broken"
    assert all(f.get("field_key") for f in firings)


# --------------------------------------------------------------------------- #
# 1. It observes. It does not draw.
# --------------------------------------------------------------------------- #
def test_recompute_never_changes_a_drawn_value():
    """The one invariant that makes a provenance re-run safe: it writes exactly one key
    and mutates nothing else. Re-running it on a finished result must be a pure addition."""
    result = _derived()
    result.pop("engine_provenance")
    before = copy.deepcopy(result)

    _attach_recomputed_engine_provenance(result, hgrh_partner_conn=None)

    assert set(result) - set(before) == {"engine_provenance"}
    for key in DRAWN_KEYS:
        assert result.get(key) == before.get(key), f"{key} was mutated by an observer"
    # Nothing else moved either — not just the drawing-shaped keys.
    for key in before:
        assert result[key] == before[key], f"{key} was mutated by an observer"


def test_recompute_leaves_the_svg_untouched():
    """Called out separately because the SVG is the artifact John eyeballs, and a helper
    that runs between `_apply_hgrh_pairing_cd` and `_apply_coating_note_to_drawing` sits
    in the middle of two helpers that DO re-render it."""
    result = _derived()
    svg = result.get("svg")
    assert svg, "fixture must actually produce a drawing for this test to mean anything"

    result.pop("engine_provenance")
    _attach_recomputed_engine_provenance(result, hgrh_partner_conn=None)

    assert result["svg"] == svg


# --------------------------------------------------------------------------- #
# 2. live and recomputed never mix
# --------------------------------------------------------------------------- #
def test_a_live_response_is_never_overwritten():
    """`live` is the call that really happened; `recomputed` is a reconstruction of it.
    If the reconstruction could overwrite the real thing, the weaker evidence would
    silently win on exactly the coils the engineer touched."""
    result = _derived()
    live = {"firings": [{"field_key": "casing_depth", "rule_id": "R-070"}],
            "call": {"n_values": 1, "n_suggestions": 0, "n_blocked": 0},
            "source": "live"}
    result["engine_provenance"] = copy.deepcopy(live)

    _attach_recomputed_engine_provenance(result, hgrh_partner_conn=None)

    assert result["engine_provenance"] == live


def test_one_coil_never_carries_two_sources_in_the_ledger(ledger):
    """The block-level label is copied onto every firing row, so "two sources inside one
    (run, coil)" is unrepresentable rather than merely unlikely."""
    assert capture_milestone("coil_manual_fill", result=_derived())

    sources = _rows(ledger, "SELECT DISTINCT source FROM rule_firing")
    assert sources == [("recomputed",)]
    per_coil = _rows(
        ledger,
        "SELECT coil_uid, COUNT(DISTINCT source) FROM rule_firing GROUP BY coil_uid",
    )
    assert per_coil, "nothing was captured — the join this feeds would be empty"
    assert all(count == 1 for _uid, count in per_coil)


def test_a_tier_a_fill_still_records_live(ledger):
    """The 1c seam keeps its meaning: a real manual fill labels its own response."""
    result = _derived()
    result["engine_provenance"]["source"] = "live"
    result["engine_provenance"].pop("fidelity", None)
    assert capture_milestone("coil_manual_fill", result=result)

    assert _rows(ledger, "SELECT DISTINCT source FROM rule_firing") == [("live",)]
    assert _rows(ledger, "SELECT DISTINCT fidelity FROM rule_firing") == [(None,)]


# --------------------------------------------------------------------------- #
# 3. drift is recorded, not hidden
# --------------------------------------------------------------------------- #
def test_drift_is_recorded_not_hidden(monkeypatch, ledger):
    """A reconstruction that disagrees with the drawing is the one case where the
    provenance must NOT be trusted — so it is labelled, not dropped. Dropping it would
    leave the corpus with no way to tell a checked attribution from an unchecked one."""
    result = _derived()
    result.pop("engine_provenance")
    real = pipeline.build_drawing_slots

    def _shifted(**kwargs):
        slots, response = real(**kwargs)
        shifted = dict(slots)
        shifted["slot.CD"] = float(shifted.get("slot.CD") or 0) + 5.0
        return shifted, response

    monkeypatch.setattr(pipeline, "build_drawing_slots", _shifted)
    _attach_recomputed_engine_provenance(result, hgrh_partner_conn=None)

    provenance = result["engine_provenance"]
    assert provenance["fidelity"] == "drifted"
    assert "slot.CD" in provenance["drift_keys"]
    # The firings are still there. A drifted row is evidence, not garbage.
    assert provenance["firings"]

    assert capture_milestone("coil_manual_fill", result=result)
    assert _rows(ledger, "SELECT DISTINCT fidelity FROM rule_firing") == [("drifted",)]
    drift_json = _rows(ledger, "SELECT drift_keys_json FROM engine_call")[0][0]
    assert "slot.CD" in drift_json


def test_a_matching_recompute_is_verified_with_no_drift_keys():
    provenance = _derived()["engine_provenance"]
    assert provenance["fidelity"] == "verified"
    assert "drift_keys" not in provenance


# --------------------------------------------------------------------------- #
# 4. it never costs the caller a drawing
# --------------------------------------------------------------------------- #
def test_recompute_failure_is_silent(monkeypatch):
    """Provenance is an observation. If observing fails, the engineer still gets the
    drawing — the failure costs a ledger row, never a request."""
    result = _derived()
    result.pop("engine_provenance")
    before = copy.deepcopy(result)

    def _boom(**kwargs):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(pipeline, "build_drawing_slots", _boom)
    _attach_recomputed_engine_provenance(result, hgrh_partner_conn=None)

    assert "engine_provenance" not in result
    assert result == before


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda r: r.update({"header_engine_used": False}), id="engine-not-used"),
        pytest.param(lambda r: r.update({"product_type": None}), id="no-product"),
        pytest.param(lambda r: r.update({"unit_size": None}), id="no-unit-size"),
        pytest.param(lambda r: r.update({"error": "boom"}), id="errored-result"),
    ],
)
def test_nothing_to_reconstruct_writes_nothing(mutate):
    """No engine call happened (or none can be rebuilt) -> no provenance. Inventing a
    firing here would put rules in the corpus that never ran on this coil."""
    result = _derived()
    result.pop("engine_provenance")
    mutate(result)

    _attach_recomputed_engine_provenance(result, hgrh_partner_conn=None)

    assert "engine_provenance" not in result


def test_no_provenance_writes_no_rows(ledger):
    result = _derived()
    result.pop("engine_provenance")
    assert capture_milestone("coil_manual_fill", result=result)

    assert _rows(ledger, "SELECT COUNT(*) FROM rule_firing")[0][0] == 0
    assert _rows(ledger, "SELECT COUNT(*) FROM engine_call")[0][0] == 0
    # ... and the rest of the run was still captured. Provenance is additive.
    assert _rows(ledger, "SELECT COUNT(*) FROM run")[0][0] == 1


# --------------------------------------------------------------------------- #
# 5. the DX-with-reheat ordering regression
# --------------------------------------------------------------------------- #
def test_paired_dx_provenance_reproduces_the_drawn_cd():
    """`_apply_hgrh_pairing_cd` re-derives CD off the with-HGRH R-072 branch, so the CD on
    the drawing is NOT the one the frozen call produced. Reconstructing the frozen call
    would therefore report drift against a value that is deliberately different — this
    fails if the helper is moved before the pairing, or stops threading with_hgrh."""
    spec = _spec(hgrh_partner_conn_size=1.375)
    result = derive_coil_template_drawing(spec)
    if not result.get("engine_provenance"):
        pytest.skip("fixture did not produce a paired-DX drawing")

    assert result["engine_provenance"]["fidelity"] == "verified", (
        result["engine_provenance"].get("drift_keys")
    )


def test_tier_b_override_is_not_reported_as_engine_drift():
    """Ordering, the other direction: the reflection that merges the engineer's override
    into slot_values runs AFTER this helper. If it ran before, the human's typed value
    would be compared against the engine's and logged as engine drift."""
    spec = _spec(
        param_overrides=[{"key": "CD", "value": 99.0, "override_reason": "engineer says so"}],
    )
    result = derive_coil_template_drawing(spec)
    provenance = result.get("engine_provenance")
    if not provenance:
        pytest.skip("fixture did not attach provenance")

    assert provenance["fidelity"] == "verified", provenance.get("drift_keys")


# --------------------------------------------------------------------------- #
# 6. migration 6
# --------------------------------------------------------------------------- #
def test_migration_6_is_additive_only():
    """Extends the forward-only guard: an ALTER must only ADD a NULLable COLUMN. A
    NOT NULL / DEFAULT would rewrite rows that are supposed to be append-only, and a
    default would also erase the "written before this migration" signal the readers rely
    on to treat a NULL source as the 1c seam."""
    for _description, statements in MIGRATIONS:
        for statement in statements:
            upper = " ".join(statement.upper().split())
            if not upper.startswith("ALTER TABLE"):
                continue
            assert " ADD COLUMN " in upper, statement
            assert "NOT NULL" not in upper, statement
            assert "DEFAULT" not in upper, statement


def test_migration_6_upgrades_an_existing_v5_ledger(tmp_path, monkeypatch):
    """The live ledger is already at user_version 5 with real rows in it. Build that exact
    shape, then let the runner upgrade it: the new columns must appear, the version must
    advance to 6, and the pre-existing row must survive reading NULL (which is the
    documented 'this came from the 1c seam' convention)."""
    path = tmp_path / "v5.sqlite3"
    conn = sqlite3.connect(str(path))
    try:
        for version, (description, statements) in enumerate(MIGRATIONS[:5], start=1):
            for statement in statements:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO migration (version, applied_ts, description, sql_sha256)"
                " VALUES (?, ?, ?, ?)",
                (version, "2026-01-01T00:00:00+00:00", description, "seeded"),
            )
        conn.execute("PRAGMA user_version = 5")
        conn.execute(
            "INSERT INTO rule_firing (run_id, coil_uid, field_key, rule_id, confidence)"
            " VALUES ('r0', 'c0', 'casing_depth', 'R-070', 'HIGH')"
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(path))
    monkeypatch.delenv(db.ENV_CAPTURE_ENABLED, raising=False)
    db.reset_caches_for_tests()
    try:
        upgraded = db.connect()
        try:
            assert upgraded.execute("PRAGMA user_version").fetchone()[0] == len(MIGRATIONS)
            firing_cols = {r[1] for r in upgraded.execute("PRAGMA table_info(rule_firing)")}
            assert {"source", "fidelity"} <= firing_cols
            call_cols = {r[1] for r in upgraded.execute("PRAGMA table_info(engine_call)")}
            assert {"source", "fidelity", "drift_keys_json"} <= call_cols

            legacy = upgraded.execute(
                "SELECT rule_id, source, COALESCE(source, 'live') FROM rule_firing"
            ).fetchall()
            assert legacy == [("R-070", None, "live")]
        finally:
            upgraded.close()
    finally:
        db.reset_caches_for_tests()


def test_the_helper_is_wired_into_both_paths():
    """A provenance helper wired into analyse only would rebuild the corpus with a hole
    exactly where manual fills happen — the same analyse-only-post-process defect as TR-9
    and 228d731. Assert both call sites by source, since neither path is easy to exercise
    end to end here."""
    source = Path(s2d.__file__).read_text(encoding="utf-8")
    assert source.count("_attach_recomputed_engine_provenance(") >= 3  # 1 def + 2 calls
