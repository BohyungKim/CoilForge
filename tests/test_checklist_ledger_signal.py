"""Checklist divergences reach the review-triage ranking (Stage 3.1 groundwork).

Stage 3.0 measured the override rate and found the flag and the correction were
identity-disjoint: dims got flagged on one coil and corrected on another, overlap zero.
Part of that gap is mechanical. The project gate's ``engine_vs_checklist`` exception
joins the panel key against the CHECKLIST's label, and those disagree for every
per-header dimension — the panel's ``S`` is the sheet's ``S1``, the panel's ``O2`` is the
sheet's ``O4`` — so a per-header divergence was never counted at all.

Recording the comparison as its own ``compare_observation`` comparator, filed under the
PANEL key, is what makes the signal reachable. These tests pin that the rows are written,
that the key is the joinable one, and that they survive into ``measure_override_rate``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from coilforge.capture import db
from coilforge.capture.record import _compare_rows
from coilforge.capture.triage import measure_override_rate
from coilforge.services.drawing_param_resolver import (
    param_key_for_slot,
    slot_for_param_key,
)


REVIEW = {
    "sheets": [
        {
            "tag": "RHHGRC-1",
            "comparisons": [
                {"label": "CD", "slot": "slot.CD", "coilforge": 3.75,
                 "checklist": 4.125, "verdict": "mismatch"},
                # the sheet's S1 is the PANEL's S — the rename that broke the old join
                {"label": "S1", "slot": "slot.S1", "coilforge": 2.875,
                 "checklist": -0.875, "verdict": "mismatch"},
                # the sheet's O4 is the panel's O2
                {"label": "O4", "slot": "slot.O4", "coilforge": 2.75,
                 "checklist": 2, "verdict": "mismatch"},
                {"label": "HF", "slot": "slot.HF", "coilforge": 1.5,
                 "checklist": 1.5, "verdict": "match"},
                {"label": "O6", "slot": "slot.O6", "coilforge": "N/A",
                 "checklist": None, "verdict": "mismatch"},
            ],
        }
    ]
}


def test_rows_are_written_under_the_panel_key_not_the_sheet_label():
    rows = _compare_rows("run-1", {"comparator": "checklist", "report": REVIEW})
    by_slot = {r[4]: r for r in rows}

    assert by_slot["slot.S1"][3] == "S", "filed under the sheet's label, the join dies"
    assert by_slot["slot.O4"][3] == "O2"
    assert by_slot["slot.CD"][3] == "CD"
    # the human-readable sheet label is kept alongside, not instead
    assert by_slot["slot.S1"][5] == "S1"
    assert by_slot["slot.O4"][5] == "O4"


def test_the_coil_tag_is_carried_so_a_row_can_be_attributed():
    """Unlike ccsi rows (tag NULL by design), these must be joinable to a coil."""
    rows = _compare_rows("run-1", {"comparator": "checklist", "report": REVIEW})
    assert rows and all(r[1] == "RHHGRC-1" for r in rows)
    assert all(r[2] == "checklist" for r in rows)


def test_na_rows_are_dropped_so_they_cannot_inflate_the_divergence_rate():
    """mapping.py writes the literal "N/A" past the circuit count, and _match scores
    string-vs-number as a mismatch — a dimension that does not exist on this coil."""
    rows = _compare_rows("run-1", {"comparator": "checklist", "report": REVIEW})
    assert "slot.O6" not in {r[4] for r in rows}
    assert len(rows) == 4


def test_both_values_are_recorded_for_later_adjudication():
    rows = _compare_rows("run-1", {"comparator": "checklist", "report": REVIEW})
    cd = next(r for r in rows if r[4] == "slot.CD")
    assert json.loads(cd[6]) == 3.75      # left = CoilForge
    assert json.loads(cd[7]) == 4.125     # right = the sheet's formula
    assert cd[8] == "mismatch"


def test_the_key_round_trips_through_the_shared_bridge():
    """param_key_for_slot must be the exact inverse of the panel's own resolution."""
    for key in ("CD", "S", "O", "R", "I", "HD", "SL", "HDx1", "S2", "O2", "I3", "R4"):
        slot = slot_for_param_key(key)
        assert slot is not None, key
        assert param_key_for_slot(slot) == key, key


# --- end to end into the measurement ---------------------------------------
@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(tmp_path / "capture.sqlite3"))
    monkeypatch.delenv(db.ENV_CAPTURE_ENABLED, raising=False)
    db.reset_caches_for_tests()
    yield
    db.reset_caches_for_tests()


def test_a_checklist_flag_becomes_a_measurable_signal(ledger):
    """Flagged on one run, corrected on another — the identity grain must bridge them."""
    conn = db.connect()
    try:
        for run_id in ("r-flag", "r-fix"):
            conn.execute(
                "INSERT INTO run (run_id, ts_utc, milestone, input_hash, code_version,"
                " capture_schema_version, project_number, ok)"
                " VALUES (?,?,?,?, 'test', 1, 'P-2770', 1)",
                (run_id, "2026-08-04T00:00:00+00:00", "checklist_filled", None),
            )
        conn.execute(
            "INSERT INTO coil (coil_uid, run_id, coil_seq, tag) VALUES (?,?,?,?)",
            ("c-fix", "r-fix", 0, "RHHGRC-1"),
        )
        for row in _compare_rows("r-flag", {"comparator": "checklist", "report": REVIEW}):
            conn.execute(
                "INSERT INTO compare_observation (run_id, coil_tag, comparator, key, slot,"
                " label, left_json, right_json, verdict) VALUES (?,?,?,?,?,?,?,?,?)",
                row,
            )
        # John then corrects S on that same logical coil, in a different run.
        conn.execute(
            "INSERT INTO correction (run_id, coil_uid, field_key, stage,"
            " previous_value_json, new_value_json, override_reason)"
            " VALUES (?,?,?,?,?,?,?)",
            ("r-fix", "c-fix", "S", "drawing_param", "2.875", "1.5", "per the sheet"),
        )
        conn.commit()
    finally:
        conn.close()

    report = measure_override_rate()
    assert report["enabled"] is True
    fields = {f["field_key"]: f for f in report.get("fields") or []}

    assert "S" in fields, "the per-header divergence never reached the ranking"
    assert "checklist_mismatch" in fields["S"]["by_reason"], fields["S"]["by_reason"]
    assert fields["S"]["flagged"] >= 1 and fields["S"]["corrected"] >= 1
    assert fields["S"]["override_rate"] == 1.0
    # O2 was flagged too but never corrected, so it must measure LOWER — the point of
    # measuring rather than assuming every flag is worth John's attention.
    assert "O2" in fields
    assert fields["O2"]["corrected"] == 0
    assert fields["O2"]["override_rate"] == 0.0
