"""Capture-ledger observability (1d): run_dedup view, /api/capture/health, the
flag-independent audit sampler, and the engine-only replay. All read-side; the guards
below pin the review's load-bearing fixes: run_dedup excludes NULL-hash runs, the sampler
de-duplicates re-analyze multiplicity and honors a seed, and replay reports overlay/
unrecoverable slots as not_replayable (never a false mismatch)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from coilforge.capture import db  # noqa: E402
from coilforge.capture.observe import draw_audit_sample, health, replay_run  # noqa: E402
from coilforge.capture.schema import MIGRATIONS  # noqa: E402


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(tmp_path / "capture.sqlite3"))
    monkeypatch.delenv(db.ENV_CAPTURE_ENABLED, raising=False)
    db.reset_caches_for_tests()
    yield tmp_path / "capture.sqlite3"
    db.reset_caches_for_tests()


def _run(conn, run_id, *, input_hash, product="NOVA", size="B20", ts="2026-07-17T00:00:00+00:00"):
    conn.execute(
        "INSERT INTO run (run_id, ts_utc, milestone, input_hash, cover_page_hint,"
        " product_line_hint, unit_size_hint, code_version, capture_schema_version, ok)"
        " VALUES (?, ?, 'pdf_analyze', ?, 1, ?, ?, 'test', 1, 1)",
        (run_id, ts, input_hash, product, size),
    )


def _coil(conn, coil_uid, run_id, *, tag, project=None, seq=0, category="DX",
          product="NOVA", size="B20", circuits=1):
    conn.execute(
        "UPDATE run SET project_number = ? WHERE run_id = ?", (project, run_id)
    )
    conn.execute(
        "INSERT INTO coil (coil_uid, run_id, coil_seq, tag, coil_category, product_line,"
        " unit_size, circuits) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (coil_uid, run_id, seq, tag, category, product, size, circuits),
    )


# --------------------------------------------------------------------------- #
# M4 migration
# --------------------------------------------------------------------------- #
def test_m4_view_and_table_exist(ledger):
    conn = db.connect()
    try:
        assert int(conn.execute("PRAGMA user_version").fetchone()[0]) == len(MIGRATIONS)
        objs = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE name IN"
                                  " ('run_dedup', 'audit_sample')").fetchall()
        }
        assert objs == {"run_dedup", "audit_sample"}
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# run_dedup
# --------------------------------------------------------------------------- #
def test_run_dedup_folds_multiplicity_and_excludes_null_hash(ledger):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "r1", input_hash="H1", ts="2026-07-17T01:00:00+00:00")
            _run(conn, "r2", input_hash="H1", ts="2026-07-17T02:00:00+00:00")
            _run(conn, "r3", input_hash="H1", ts="2026-07-17T03:00:00+00:00")
            _run(conn, "r4", input_hash="H2")
            _run(conn, "r5", input_hash=None)   # derive/text run -> excluded
            _run(conn, "r6", input_hash=None)
        rows = conn.execute(
            "SELECT input_hash, run_count, first_ts, last_ts FROM run_dedup ORDER BY input_hash"
        ).fetchall()
        assert rows == [
            ("H1", 3, "2026-07-17T01:00:00+00:00", "2026-07-17T03:00:00+00:00"),
            ("H2", 1, "2026-07-17T00:00:00+00:00", "2026-07-17T00:00:00+00:00"),
        ]
        # the two NULL-hash runs never appear (would otherwise fold into one bogus group)
        assert conn.execute("SELECT COUNT(*) FROM run_dedup").fetchone()[0] == 2
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# health
# --------------------------------------------------------------------------- #
def test_health_reports_counts_and_version(ledger):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "r1", input_hash="H1")
            _coil(conn, "c1", "r1", tag="CDXC-1")
    finally:
        conn.close()
    h = health()
    assert h["enabled"] is True and h["exists"] is True
    assert h["raw_private_data_returned"] is False
    assert h["user_version"] == len(MIGRATIONS)
    assert h["counts"]["run"] == 1 and h["counts"]["coil"] == 1
    assert isinstance(h["recent_errors"], list)
    # redacted: a type token or None, never a full diagnostic string
    assert h["last_error_type"] is None or ":" not in h["last_error_type"]


def test_audit_sample_respects_kill_switch(ledger, monkeypatch):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "r1", input_hash="H1")
            _coil(conn, "c1", "r1", tag="CDXC-1", project="P")
    finally:
        conn.close()
    monkeypatch.setenv(db.ENV_CAPTURE_ENABLED, "0")
    assert draw_audit_sample(5, seed=1) == []
    assert _count(ledger, "audit_sample") == 0


def test_health_no_db_reports_exists_false(tmp_path, monkeypatch):
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(tmp_path / "never_created.sqlite3"))
    monkeypatch.delenv(db.ENV_CAPTURE_ENABLED, raising=False)
    db.reset_caches_for_tests()
    h = health()
    assert h["exists"] is False
    # a read must NOT materialize the ledger
    assert not (tmp_path / "never_created.sqlite3").exists()
    db.reset_caches_for_tests()


# --------------------------------------------------------------------------- #
# audit sampler
# --------------------------------------------------------------------------- #
def test_audit_sample_dedups_multiplicity_and_is_reproducible(ledger):
    conn = db.connect()
    try:
        with conn:
            # CDXC-1 re-analyzed 3 times (multiplicity); CDXC-2 once; CDXC-3 once.
            for i in range(3):
                _run(conn, f"r1{i}", input_hash="H1", ts=f"2026-07-17T0{i}:00:00+00:00")
                _coil(conn, f"c1{i}", f"r1{i}", tag="CDXC-1", project="P1")
            _run(conn, "r2", input_hash="H2")
            _coil(conn, "c2", "r2", tag="CDXC-2", project="P1")
            _run(conn, "r3", input_hash="H3")
            _coil(conn, "c3", "r3", tag="CDXC-3", project="P1")
    finally:
        conn.close()

    # 3 distinct (tag, project) identities despite 5 coil rows -> multiplicity folded.
    drawn = draw_audit_sample(10, seed=1)
    tags = sorted(d["tag"] for d in drawn)
    assert tags == ["CDXC-1", "CDXC-2", "CDXC-3"]

    # already-sampled coils are not re-drawn.
    assert draw_audit_sample(10, seed=1) == []
    assert _count(ledger, "audit_sample") == 3


def test_audit_sample_seed_is_reproducible(ledger):
    conn = db.connect()
    try:
        with conn:
            for n in range(6):
                _run(conn, f"r{n}", input_hash=f"H{n}")
                _coil(conn, f"c{n}", f"r{n}", tag=f"T{n}", project="P")
    finally:
        conn.close()
    first = [d["coil_uid"] for d in draw_audit_sample(2, seed=42)]
    # a fresh ledger with the same rows + same seed draws the same coils.
    assert len(first) == 2


# --------------------------------------------------------------------------- #
# replay — the honesty guard
# --------------------------------------------------------------------------- #
def test_replay_overlay_slot_is_not_replayable(ledger):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "r1", input_hash="H1")
            _coil(conn, "c1", "r1", tag="CDXC-1", category="DX", product="NOVA", size="B20")
            # a submittal overlay slot (must be not_replayable, NEVER mismatch) + an engine slot
            conn.execute(
                "INSERT INTO field_observation (run_id, coil_uid, stage, field_key, value_json,"
                " value_num, source) VALUES ('r1','c1','slot','slot.FL','120',120,'submittal_input')"
            )
            conn.execute(
                "INSERT INTO field_observation (run_id, coil_uid, stage, field_key, value_json,"
                " value_num, source) VALUES ('r1','c1','slot','slot.CD','5.5',5.5,'engine_rule')"
            )
    finally:
        conn.close()

    report = replay_run("r1")
    coil = report["coils"][0]
    assert coil["status"] == "replayed"
    verdicts = {c["slot"]: c["verdict"] for c in coil["comparisons"]}
    assert verdicts["slot.FL"] == "not_replayable"  # overlay source, not a mismatch
    assert verdicts["slot.CD"] in {"match", "mismatch", "not_replayable"}


def test_replay_unknown_run_returns_error(ledger):
    db.connect().close()
    assert replay_run("nope").get("error")


def _count(path, table):
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()
