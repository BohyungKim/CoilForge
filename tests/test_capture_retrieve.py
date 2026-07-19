"""Case retrieval (Stage 2.0): masked-Gower nearest-neighbor over the ledger.

The load-bearing regression is ``test_evidence_is_identity_grained``: features and corrections
live on DIFFERENT runs of the same logical coil, so a single-coil_uid design would return zero
evidence. Everything else pins the metric arithmetic, the guards, and the corpus meter.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from coilforge.capture import db  # noqa: E402
from coilforge.capture.observe import health  # noqa: E402
from coilforge.capture.retrieve import (  # noqa: E402
    CORPUS_MIN,
    corpus_status,
    similar_by_coil_uid,
    similar_by_features,
)

pytest.importorskip("numpy")


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(tmp_path / "capture.sqlite3"))
    monkeypatch.delenv(db.ENV_CAPTURE_ENABLED, raising=False)
    db.reset_caches_for_tests()
    yield tmp_path / "capture.sqlite3"
    db.reset_caches_for_tests()


# --------------------------------------------------------------------------- #
# insert helpers — params default None so a test controls axis PRESENCE precisely
# --------------------------------------------------------------------------- #
def _run(conn, run_id, *, project="P1", ts="2026-07-17T00:00:00+00:00",
         milestone="pdf_analyze", input_hash="H"):
    conn.execute(
        "INSERT INTO run (run_id, ts_utc, milestone, input_hash, code_version,"
        " capture_schema_version, project_number, ok) VALUES (?,?,?,?,'test',1,?,1)",
        (run_id, ts, milestone, input_hash, project),
    )


def _coil(conn, coil_uid, run_id, *, tag, seq=0, category=None, product=None,
          terra_variant=None, size=None, hand=None, header_type=None,
          special_feature=None, template_id=None, circuits=None):
    conn.execute(
        "INSERT INTO coil (coil_uid, run_id, coil_seq, tag, coil_category, product_line,"
        " terra_variant, unit_size, hand, header_type, special_feature, template_id, circuits)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (coil_uid, run_id, seq, tag, category, product, terra_variant, size, hand,
         header_type, special_feature, template_id, circuits),
    )


def _input(conn, run_id, seq, key, value):
    conn.execute(
        "INSERT INTO run_input (run_id, coil_seq, key, value_json) VALUES (?,?,?,?)",
        (run_id, seq, key, json.dumps(value)),
    )


def _correction(conn, run_id, coil_uid, field_key, before, after, *,
                stage="drawing_param", reason="header offset"):
    conn.execute(
        "INSERT INTO correction (run_id, coil_uid, field_key, stage, previous_value_json,"
        " new_value_json, override_reason) VALUES (?,?,?,?,?,?,?)",
        (run_id, coil_uid, field_key, stage, json.dumps(before), json.dumps(after), reason),
    )


def _count(path, table):
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# metric arithmetic
# --------------------------------------------------------------------------- #
def test_identical_coil_distance_zero(ledger):
    conn = db.connect()
    try:
        with conn:
            for uid, tag in (("a", "A"), ("b", "B")):
                _run(conn, f"r{uid}", project="P1")
                _coil(conn, f"c{uid}", f"r{uid}", tag=tag, category="DX", product="NOVA",
                      size="B20", hand="LH", circuits=1)
                _input(conn, f"r{uid}", 0, "rows", 4)
    finally:
        conn.close()
    res = similar_by_coil_uid("ca")
    assert res["neighbors"][0]["tag"] == "B"
    assert res["neighbors"][0]["distance"] == 0.0


def test_numeric_normalization_exact(ledger):
    # both coils identical except rows (4 vs 10); range over corpus = 6.
    conn = db.connect()
    try:
        with conn:
            for uid, tag, rows in (("a", "A", 4), ("b", "B", 10)):
                _run(conn, f"r{uid}")
                _coil(conn, f"c{uid}", f"r{uid}", tag=tag, category="DX", product="NOVA",
                      size="B20", circuits=1)
                _input(conn, f"r{uid}", 0, "rows", rows)
                _input(conn, f"r{uid}", 0, "feeds", 2)
    finally:
        conn.close()
    res = similar_by_coil_uid("ca")
    # present axes: coil_category, product_line, unit_size (cat) + circuits, rows, feeds (num) = 6
    # only rows differs: d = |4-10|/6 = 1.0 -> D = 1.0 / 6
    assert res["neighbors"][0]["distance"] == pytest.approx(1.0 / 6, abs=1e-3)  # 4-dp display
    assert res["neighbors"][0]["shared_axes"] == 6


def test_single_categorical_mismatch_exact(ledger):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "ra")
            _coil(conn, "ca", "ra", tag="A", category="DX", product="NOVA", size="B20", circuits=1)
            _run(conn, "rb")
            _coil(conn, "cb", "rb", tag="B", category="DX", product="TERRA", size="B20", circuits=1)
    finally:
        conn.close()
    res = similar_by_coil_uid("ca")
    # present shared axes: coil_category, product_line, unit_size, circuits = 4; only product differs.
    assert res["neighbors"][0]["distance"] == pytest.approx(1.0 / 4, abs=1e-3)


def test_missing_axes_are_masked_not_imputed(ledger):
    # query lacks feeds/finned_*; candidate also lacks them -> distance over shared axes only.
    conn = db.connect()
    try:
        with conn:
            for uid, tag in (("a", "A"), ("b", "B")):
                _run(conn, f"r{uid}")
                _coil(conn, f"c{uid}", f"r{uid}", tag=tag, category="DX", product="NOVA",
                      size="B20", hand="LH", circuits=1)
                _input(conn, f"r{uid}", 0, "rows", 4)
    finally:
        conn.close()
    res = similar_by_coil_uid("ca")
    n = res["neighbors"][0]
    assert n["distance"] == 0.0 and n["shared_axes"] == 6  # 5 cat + rows; no NaN penalty


# --------------------------------------------------------------------------- #
# the BLOCKER regression: features and corrections live on different runs
# --------------------------------------------------------------------------- #
def test_evidence_is_identity_grained(ledger):
    conn = db.connect()
    try:
        with conn:
            # identity (CDXC-2, P1): analyze run carries features; a LATER manual_fill run
            # carries the correction under a DIFFERENT coil_uid and NO run_input.
            _run(conn, "r_analyze", project="P1", ts="2026-07-17T01:00:00+00:00")
            _coil(conn, "c_analyze", "r_analyze", tag="CDXC-2", category="DX", product="NOVA",
                  size="B20", circuits=1)
            _input(conn, "r_analyze", 0, "rows", 4)
            _run(conn, "r_fill", project="P1", milestone="coil_manual_fill",
                 input_hash=None, ts="2026-07-17T02:00:00+00:00")
            _coil(conn, "c_fill", "r_fill", tag="CDXC-2", category="DX", product="NOVA",
                  size="B20", circuits=1)
            _correction(conn, "r_fill", "c_fill", "CD", 5.5, 9.5, reason="per submittal")
            # a query coil (different identity) similar to CDXC-2
            _run(conn, "r_q", project="P2")
            _coil(conn, "c_q", "r_q", tag="CDXC-9", category="DX", product="NOVA",
                  size="B20", circuits=1)
            _input(conn, "r_q", 0, "rows", 4)
    finally:
        conn.close()

    res = similar_by_coil_uid("c_q", redact=False)
    neighbor = next(n for n in res["neighbors"] if n["tag"] == "CDXC-2")
    # representative feature run is the analyze run; corrections aggregated across coil_uids.
    assert neighbor["coil_uid"] == "c_analyze"
    assert neighbor["corrections"] == [
        {"field_key": "CD", "stage": "drawing_param", "before": 5.5, "after": 9.5,
         "reason": "per submittal"}
    ]


# --------------------------------------------------------------------------- #
# filters + floors
# --------------------------------------------------------------------------- #
def test_same_category_prefilter_blocks_cross_category(ledger):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "rq")
            _coil(conn, "cq", "rq", tag="Q", category="DX", product="NOVA", size="B20",
                  hand="LH", circuits=1)
            _input(conn, "rq", 0, "rows", 4)
            _run(conn, "rdx")
            _coil(conn, "cdx", "rdx", tag="DXN", category="DX", product="NOVA", size="B20",
                  hand="LH", circuits=1)
            _input(conn, "rdx", 0, "rows", 4)
            _run(conn, "rhw")
            _coil(conn, "chw", "rhw", tag="HWN", category="HWC", product="NOVA", size="B20",
                  hand="LH", circuits=1)
            _input(conn, "rhw", 0, "rows", 4)
    finally:
        conn.close()
    tags_on = {n["tag"] for n in similar_by_coil_uid("cq", same_category=True)["neighbors"]}
    assert tags_on == {"DXN"}
    tags_off = {n["tag"] for n in similar_by_coil_uid("cq", same_category=False)["neighbors"]}
    assert tags_off == {"DXN", "HWN"}


def test_min_shared_axes_floor(ledger):
    # only 3 axes present in both -> below the floor of 4 -> not a neighbor.
    conn = db.connect()
    try:
        with conn:
            for uid, tag in (("a", "A"), ("b", "B")):
                _run(conn, f"r{uid}")
                _coil(conn, f"c{uid}", f"r{uid}", tag=tag, category="DX", product="NOVA", size="B20")
    finally:
        conn.close()
    assert similar_by_coil_uid("ca")["neighbors"] == []


# --------------------------------------------------------------------------- #
# guards
# --------------------------------------------------------------------------- #
def test_kill_switch_returns_empty(ledger, monkeypatch):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "ra")
            _coil(conn, "ca", "ra", tag="A", category="DX", product="NOVA", size="B20", circuits=1)
    finally:
        conn.close()
    monkeypatch.setenv(db.ENV_CAPTURE_ENABLED, "0")
    res = similar_by_coil_uid("ca")
    assert res["enabled"] is False and res["neighbors"] == []


def test_no_db_does_not_materialize(tmp_path, monkeypatch):
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(tmp_path / "never.sqlite3"))
    monkeypatch.delenv(db.ENV_CAPTURE_ENABLED, raising=False)
    db.reset_caches_for_tests()
    res = similar_by_features({"coil_category": "DX", "product_line": "NOVA"})
    assert res["exists"] is False
    assert not (tmp_path / "never.sqlite3").exists()
    db.reset_caches_for_tests()


def test_malformed_query_never_raises(ledger):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "ra")
            _coil(conn, "ca", "ra", tag="A", category="DX", product="NOVA", size="B20", circuits=1)
            _input(conn, "ra", 0, "rows", 4)
    finally:
        conn.close()
    # unhashable categorical value + a non-dict — both must degrade, never raise (contract).
    assert isinstance(similar_by_features({"coil_category": ["DX"]}), dict)
    assert isinstance(similar_by_features("not-a-dict"), dict)  # type: ignore[arg-type]
    assert similar_by_coil_uid("no-such-uid")["error"] == "unknown_coil_uid"


def test_k_zero_returns_no_neighbors(ledger):
    conn = db.connect()
    try:
        with conn:
            for uid, tag in (("a", "A"), ("b", "B")):
                _run(conn, f"r{uid}")
                _coil(conn, f"c{uid}", f"r{uid}", tag=tag, category="DX", product="NOVA",
                      size="B20", circuits=1)
                _input(conn, f"r{uid}", 0, "rows", 4)
    finally:
        conn.close()
    assert similar_by_coil_uid("ca", k=0)["neighbors"] == []


def test_below_gate_flags_insufficient_corpus(ledger):
    conn = db.connect()
    try:
        with conn:
            for i in range(3):
                _run(conn, f"r{i}", project=f"P{i}")
                _coil(conn, f"c{i}", f"r{i}", tag=f"T{i}", category="DX", product="NOVA",
                      size="B20", circuits=1)
                _input(conn, f"r{i}", 0, "rows", 4 + i)
    finally:
        conn.close()
    res = similar_by_coil_uid("c0")
    assert res["insufficient_corpus"] is True
    assert res["corpus_ready"] is False
    assert res["corpus_size"] == 3
    assert res["neighbors"]  # still computes — degrades, does not disappear


def test_http_redaction_drops_reason_and_project(ledger):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "ra", project="ACME-1")
            _coil(conn, "ca", "ra", tag="A", category="DX", product="NOVA", size="B20", circuits=1)
            _input(conn, "ra", 0, "rows", 4)
            _run(conn, "rb", project="ACME-1")
            _coil(conn, "cb", "rb", tag="B", category="DX", product="NOVA", size="B20", circuits=1)
            _input(conn, "rb", 0, "rows", 4)
            _correction(conn, "rb", "cb", "CD", 5.5, 9.5, reason="secret note")
    finally:
        conn.close()
    redacted = similar_by_coil_uid("ca", redact=True)["neighbors"][0]
    assert "project_number" not in redacted
    assert all("reason" not in c for c in redacted["corrections"])
    full = similar_by_coil_uid("ca", redact=False)["neighbors"][0]
    assert full["project_number"] == "ACME-1"
    assert full["corrections"][0]["reason"] == "secret note"


# --------------------------------------------------------------------------- #
# corpus meter
# --------------------------------------------------------------------------- #
def test_corpus_status_counts_distinct_identity(ledger):
    conn = db.connect()
    try:
        with conn:
            # T1 re-analyzed 3x (multiplicity), T2 once with a correction.
            for i in range(3):
                _run(conn, f"r1{i}", project="P1", ts=f"2026-07-17T0{i}:00:00+00:00")
                _coil(conn, f"c1{i}", f"r1{i}", tag="T1", category="DX", product="NOVA", size="B20")
            _run(conn, "r2", project="P1")
            _coil(conn, "c2", "r2", tag="T2", category="DX", product="NOVA", size="B20")
            _correction(conn, "r2", "c2", "CD", 5.5, 9.5)
            # a NULL-identity run must NOT count (derive/text runs)
            _run(conn, "rnull", project=None, input_hash=None)
            _coil(conn, "cnull", "rnull", tag=None, category="DX")
    finally:
        conn.close()
    status = corpus_status()
    assert status["distinct_coils"] == 2  # T1 (folded) + T2, NULL excluded
    assert status["coils_with_corrections"] == 1
    assert status["threshold"] == CORPUS_MIN
    assert status["ready"] is False


def test_health_embeds_corpus_meter(ledger):
    conn = db.connect()
    try:
        with conn:
            _run(conn, "r1", project="P1")
            _coil(conn, "c1", "r1", tag="T1", category="DX", product="NOVA", size="B20")
    finally:
        conn.close()
    h = health()
    assert h["corpus"]["distinct_coils"] == 1
    assert h["corpus"]["threshold"] == CORPUS_MIN
    assert h["raw_private_data_returned"] is False
