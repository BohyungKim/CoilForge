"""Review Triage measurement (Stage 3.0): per-field override rate over the ledger.

The load-bearing regression is ``test_override_rate_is_identity_grained``: the flag and the
correction live on DIFFERENT runs / coil_uids of the same logical coil, so a single-coil_uid
design would measure a 0 override rate. ``test_fit_flag_has_no_coil_uid`` pins the second
identity path (compare_observation has no coil_uid column). The rest pin the arithmetic,
the expanded signal set, the degrade, redaction, and the kill switch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from coilforge.capture import db  # noqa: E402
from coilforge.capture.observe import health  # noqa: E402
from coilforge.capture.triage import COIL_PSEUDO_KEY, measure_override_rate  # noqa: E402


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(tmp_path / "capture.sqlite3"))
    monkeypatch.delenv(db.ENV_CAPTURE_ENABLED, raising=False)
    db.reset_caches_for_tests()
    yield tmp_path / "capture.sqlite3"
    db.reset_caches_for_tests()


# --------------------------------------------------------------------------- #
# insert helpers — params default None so a test controls presence precisely
# --------------------------------------------------------------------------- #
def _run(conn, run_id, *, project="P1", ts="2026-07-20T00:00:00+00:00",
         milestone="pdf_analyze", input_hash=None):
    conn.execute(
        "INSERT INTO run (run_id, ts_utc, milestone, input_hash, code_version,"
        " capture_schema_version, project_number, ok) VALUES (?,?,?,?,'test',1,?,1)",
        (run_id, ts, milestone, input_hash, project),
    )


def _coil(conn, coil_uid, run_id, *, tag, seq=0):
    conn.execute(
        "INSERT INTO coil (coil_uid, run_id, coil_seq, tag) VALUES (?,?,?,?)",
        (coil_uid, run_id, seq, tag),
    )


def _correction(conn, run_id, coil_uid, field_key, before, after, *,
                stage="drawing_param", reason="header offset"):
    conn.execute(
        "INSERT INTO correction (run_id, coil_uid, field_key, stage, previous_value_json,"
        " new_value_json, override_reason) VALUES (?,?,?,?,?,?,?)",
        (run_id, coil_uid, field_key, stage, json.dumps(before), json.dumps(after), reason),
    )


def _gate(conn, run_id, coil_uid, exceptions, *, verdict="exception"):
    conn.execute(
        "INSERT INTO gate_verdict (run_id, coil_uid, verdict, exceptions_json)"
        " VALUES (?,?,?,?)",
        (run_id, coil_uid, verdict, json.dumps(exceptions)),
    )


def _compare(conn, run_id, *, comparator, key, verdict, coil_tag=None, coil_uid=None):
    conn.execute(
        "INSERT INTO compare_observation (run_id, coil_uid, coil_tag, comparator, key, verdict)"
        " VALUES (?,?,?,?,?,?)",
        (run_id, coil_uid, coil_tag, comparator, key, verdict),
    )


def _field_obs(conn, run_id, coil_uid, field_key, *, stage="drawing_param", blocked_reason=None):
    conn.execute(
        "INSERT INTO field_observation (run_id, coil_uid, stage, field_key, blocked_reason)"
        " VALUES (?,?,?,?,?)",
        (run_id, coil_uid, stage, field_key, blocked_reason),
    )


def _rule_firing(conn, run_id, coil_uid, field_key, confidence):
    conn.execute(
        "INSERT INTO rule_firing (run_id, coil_uid, field_key, confidence) VALUES (?,?,?,?)",
        (run_id, coil_uid, field_key, confidence),
    )


def _engine_call(conn, run_id, coil_uid, n_blocked):
    conn.execute(
        "INSERT INTO engine_call (run_id, coil_uid, n_blocked) VALUES (?,?,?)",
        (run_id, coil_uid, n_blocked),
    )


def _field(report, field_key):
    return next((f for f in report["fields"] if f["field_key"] == field_key), None)


# --------------------------------------------------------------------------- #
# degrade
# --------------------------------------------------------------------------- #
def test_no_ledger_is_insufficient_and_creates_nothing(ledger):
    report = measure_override_rate()
    assert report["insufficient"] is True
    assert report["fields"] == []
    assert report["exists"] is False
    assert not ledger.exists()  # a read must not materialize the DB


def test_flags_but_no_corrections_degrade(ledger):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "rpr", milestone="project_review")
            _coil(conn, "cpr", "rpr", tag="CDXC-1")
            _gate(conn, "rpr", "cpr", [{"key": "CD", "reason": "blocked"}])
    finally:
        conn.close()
    report = measure_override_rate()
    assert report["insufficient"] is True
    assert report["fields"] == []
    assert report["correction_rows"] == 0
    assert report["identities_with_corrections"] == 0


# --------------------------------------------------------------------------- #
# the load-bearing regression
# --------------------------------------------------------------------------- #
def test_override_rate_is_identity_grained(ledger):
    """Flag on a project_review run, correction on a SEPARATE coil_manual_fill run, same
    (tag, project) but different coil_uids — a single-coil_uid join would score 0."""
    conn = db.connect()
    try:
        with conn:
            # project_review run flags CD as blocked
            _run(conn, "rpr", project="P1", milestone="project_review")
            _coil(conn, "cpr", "rpr", tag="CDXC-1")
            _gate(conn, "rpr", "cpr", [{"key": "CD", "reason": "blocked"}])
            # a DIFFERENT run (fill) with a DIFFERENT coil_uid carries the correction
            _run(conn, "rfill", project="P1", milestone="coil_manual_fill")
            _coil(conn, "cfill", "rfill", tag="CDXC-1")
            _correction(conn, "rfill", "cfill", "CD", 5.5, 3.25)
    finally:
        conn.close()

    report = measure_override_rate()
    assert report["insufficient"] is False
    assert report["identities_with_corrections"] == 1
    cd = _field(report, "CD")
    assert cd == {
        "field_key": "CD", "flagged": 1, "corrected": 1, "override_rate": 1.0,
        "by_reason": {"blocked": 1},
        "examples": [{"before": 5.5, "after": 3.25, "reason": "header offset"}],
    }
    # the smoke cross-check invariant: same identity quantity health reports
    assert health()["corpus"]["coils_with_corrections"] == report["identities_with_corrections"]


def test_flagged_but_not_corrected_is_rate_zero(ledger):
    conn = db.connect()
    try:
        with conn:
            # identity A: flagged CD, corrected CD -> rate 1.0
            _run(conn, "ra_pr", project="PA", milestone="project_review")
            _coil(conn, "ca_pr", "ra_pr", tag="A")
            _gate(conn, "ra_pr", "ca_pr", [{"key": "CD", "reason": "blocked"}])
            _run(conn, "ra_f", project="PA", milestone="coil_manual_fill")
            _coil(conn, "ca_f", "ra_f", tag="A")
            _correction(conn, "ra_f", "ca_f", "CD", 1, 2)
            # identity B: flagged CD, NEVER corrected (has a different-field correction so the
            # identity still counts as "with corrections")
            _run(conn, "rb_pr", project="PB", milestone="project_review")
            _coil(conn, "cb_pr", "rb_pr", tag="B")
            _gate(conn, "rb_pr", "cb_pr", [{"key": "CD", "reason": "blocked"}])
            _run(conn, "rb_f", project="PB", milestone="coil_manual_fill")
            _coil(conn, "cb_f", "rb_f", tag="B")
            _correction(conn, "rb_f", "cb_f", "S", 3, 4)
    finally:
        conn.close()

    report = measure_override_rate()
    cd = _field(report, "CD")
    assert cd["flagged"] == 2 and cd["corrected"] == 1 and cd["override_rate"] == 0.5


# --------------------------------------------------------------------------- #
# expanded signal set + second identity path
# --------------------------------------------------------------------------- #
def test_fit_flag_has_no_coil_uid(ledger):
    """A mechanical_fit FAIL row carries only (run_id, coil_tag) — no coil_uid. It must still
    attribute to the (tag, project) identity; a coil_uid-only join would drop it entirely."""
    conn = db.connect()
    try:
        with conn:
            # fit FAIL flag on the "width" dimension, tag+run only (no coil_uid, no coil row)
            _run(conn, "rfit", project="P2", milestone="mechanical_fit")
            _compare(conn, "rfit", comparator="mechanical_fit", key="width",
                     verdict="FAIL", coil_tag="RHHGRC-1")
            # correction to width on a separate fill run, same identity
            _run(conn, "rfit_f", project="P2", milestone="coil_manual_fill")
            _coil(conn, "cfit_f", "rfit_f", tag="RHHGRC-1")
            _correction(conn, "rfit_f", "cfit_f", "width", 40, 42)
    finally:
        conn.close()

    report = measure_override_rate()
    width = _field(report, "width")
    assert width["flagged"] == 1
    assert width["by_reason"] == {"fit": 1}
    assert width["override_rate"] == 1.0


def test_ccsi_mismatch_is_excluded(ledger):
    """ccsi compare rows have a NULL coil_tag by design -> unattributable, must contribute 0."""
    conn = db.connect()
    try:
        with conn:
            _run(conn, "rc", project="P3", milestone="ccsi_compare")
            _compare(conn, "rc", comparator="ccsi", key="R", verdict="mismatch", coil_tag=None)
            # a real correction elsewhere so we get past the insufficient gate
            _run(conn, "rc_pr", project="P3", milestone="project_review")
            _coil(conn, "cc_pr", "rc_pr", tag="Z")
            _gate(conn, "rc_pr", "cc_pr", [{"key": "CD", "reason": "blocked"}])
            _run(conn, "rc_f", project="P3", milestone="coil_manual_fill")
            _coil(conn, "cc_f", "rc_f", tag="Z")
            _correction(conn, "rc_f", "cc_f", "CD", 1, 2)
    finally:
        conn.close()

    report = measure_override_rate()
    assert _field(report, "R") is None  # ccsi mismatch never surfaces as a flag


def test_confidence_and_n_blocked_signals(ledger):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "rd", project="P4", milestone="coil_manual_fill")
            _coil(conn, "cd", "rd", tag="D")
            _rule_firing(conn, "rd", "cd", "HD", "MEDIUM")   # confidence flag on HD
            _field_obs(conn, "rd", "cd", "S", blocked_reason="No value derived")  # blocked flag on S
            _engine_call(conn, "rd", "cd", 2)               # n_blocked coil-grain flag
            _correction(conn, "rd", "cd", "HD", 1, 2)       # HD corrected
    finally:
        conn.close()

    report = measure_override_rate()
    hd = _field(report, "HD")
    assert hd["by_reason"] == {"confidence": 1} and hd["override_rate"] == 1.0
    s = _field(report, "S")
    assert s["by_reason"] == {"blocked": 1} and s["corrected"] == 0
    coil = _field(report, COIL_PSEUDO_KEY)
    # __coil__ counts corrected because the identity had ANY correction (coarse coil-grain).
    assert coil["by_reason"] == {"n_blocked": 1} and coil["corrected"] == 1


# --------------------------------------------------------------------------- #
# redaction + kill switch
# --------------------------------------------------------------------------- #
def test_redaction_drops_reason(ledger):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "rpr", project="P1", milestone="project_review")
            _coil(conn, "cpr", "rpr", tag="CDXC-1")
            _gate(conn, "rpr", "cpr", [{"key": "CD", "reason": "blocked"}])
            _run(conn, "rf", project="P1", milestone="coil_manual_fill")
            _coil(conn, "cf", "rf", tag="CDXC-1")
            _correction(conn, "rf", "cf", "CD", 5.5, 3.25, reason="checklist says 3.25")
    finally:
        conn.close()

    full = _field(measure_override_rate(redact=False), "CD")
    assert full["examples"][0]["reason"] == "checklist says 3.25"
    redacted = _field(measure_override_rate(redact=True), "CD")
    assert "reason" not in redacted["examples"][0]
    assert redacted["examples"][0]["before"] == 5.5  # values still present


def test_kill_switch_disables(ledger, monkeypatch):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "rf", project="P1", milestone="coil_manual_fill")
            _coil(conn, "cf", "rf", tag="CDXC-1")
            _correction(conn, "rf", "cf", "CD", 1, 2)
    finally:
        conn.close()
    monkeypatch.setenv(db.ENV_CAPTURE_ENABLED, "0")
    report = measure_override_rate()
    assert report["enabled"] is False
    assert report["insufficient"] is True
    assert report["fields"] == []
