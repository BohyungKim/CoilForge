"""Rule Observatory (Stage 4.0): per-RULE disagreement over the ledger.

The load-bearing regression is ``test_zero_coverage_rule_is_never_reported_as_accurate``.
This stage's named worst case is not an arithmetic slip, it is sample bias: John only ever
reviews coils that were already flagged, so a rule nobody has checked would read as a
perfect rule and the wrong rules would stay invisible forever. The defence is structural
rather than advisory — there is no accuracy field, every rate divides by ``second_opinion``
instead of ``fired``, and an unchecked rule reports ``None`` plus a flag.

The rest pin the vocabulary bridge (five key vocabularies meet here and none of them
match), the identity-grain join Stages 2 and 3 were both built around, and the two
exclusions that would otherwise inflate a rule's apparent correctness: firings that feed no
drawing dimension, and firings whose provenance reconstruction drifted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from coilforge.capture import db  # noqa: E402
from coilforge.capture.observatory import (  # noqa: E402
    MIN_IDENTITIES,
    MIN_SECOND_OPINION,
    base_panel_key,
    measure_rule_observatory,
)


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
def _run(conn, run_id, *, project="P1", milestone="intake_drawing"):
    conn.execute(
        "INSERT INTO run (run_id, ts_utc, milestone, code_version, capture_schema_version,"
        " project_number, ok) VALUES (?,?,?,'test',1,?,1)",
        (run_id, "2026-08-01T00:00:00+00:00", milestone, project),
    )


def _coil(conn, coil_uid, run_id, *, tag, category="DX", family="NOVA",
          variant=None, unit_size="B20", seq=0):
    conn.execute(
        "INSERT INTO coil (coil_uid, run_id, coil_seq, tag, coil_category, product_line,"
        " terra_variant, unit_size) VALUES (?,?,?,?,?,?,?,?)",
        (coil_uid, run_id, seq, tag, category, family, variant, unit_size),
    )


def _firing(conn, run_id, coil_uid, field_key, *, rule_id="R-070", confidence="HIGH",
            source="recomputed", fidelity="verified"):
    conn.execute(
        "INSERT INTO rule_firing (run_id, coil_uid, field_key, rule_id, confidence,"
        " source, fidelity) VALUES (?,?,?,?,?,?,?)",
        (run_id, coil_uid, field_key, rule_id, confidence, source, fidelity),
    )


def _checklist(conn, run_id, *, key, verdict, coil_tag, slot=None):
    conn.execute(
        "INSERT INTO compare_observation (run_id, coil_tag, comparator, key, slot, verdict)"
        " VALUES (?,?,'checklist',?,?,?)",
        (run_id, coil_tag, key, slot, verdict),
    )


def _correction(conn, run_id, coil_uid, field_key, *, before=1.0, after=2.0,
                reason="engineer measured it"):
    conn.execute(
        "INSERT INTO correction (run_id, coil_uid, field_key, stage, previous_value_json,"
        " new_value_json, override_reason) VALUES (?,?,?,'drawing_param',?,?,?)",
        (run_id, coil_uid, field_key, json.dumps(before), json.dumps(after), reason),
    )


def _audit(conn, coil_uid, run_id, *, tag, reviewed=1):
    conn.execute(
        "INSERT INTO audit_sample (drawn_ts_utc, coil_uid, run_id, tag, reviewed)"
        " VALUES ('2026-08-01T00:00:00+00:00',?,?,?,?)",
        (coil_uid, run_id, tag, reviewed),
    )


def _adjudication(conn, *, slot, verdict, category="DX", family="NOVA",
                  variant="-", scope="*", reason="John ruled"):
    conn.execute(
        "INSERT INTO divergence_adjudication (ts_utc, divergence_key, coil_category,"
        " product_family, terra_variant, unit_size_scope, slot, verdict, reason)"
        " VALUES ('2026-08-01T00:00:00+00:00',?,?,?,?,?,?,?,?)",
        (f"{category}|{family}|{variant}|{scope}|{slot}", category, family, variant,
         scope, slot, verdict, reason),
    )


def _rule(report, rule_id):
    for entry in report["rules"]:
        if entry["rule_id"] == rule_id:
            return entry
    raise AssertionError(f"{rule_id} not in {[e['rule_id'] for e in report['rules']]}")


def _observed_corpus(conn, *, count=MIN_IDENTITIES, rule_id="R-FILLER"):
    """Enough independently observed identities to clear the global degrade, on a rule the
    assertions ignore. Lets a test isolate ONE rule's arithmetic."""
    for i in range(count):
        run, uid, tag = f"bg{i}", f"bgc{i}", f"BG-{i}"
        _run(conn, run, project=f"BG{i}")
        _coil(conn, uid, run, tag=tag)
        _firing(conn, run, uid, "casing_depth", rule_id=rule_id)
        _checklist(conn, run, key="CD", verdict="match", coil_tag=tag)


# --------------------------------------------------------------------------- #
# 1. sample bias — the structural defence
# --------------------------------------------------------------------------- #
def test_zero_coverage_rule_is_never_reported_as_accurate(ledger):
    """A rule that fired 40 times and was never independently checked. It must not be
    possible to read a correctness number off this entry — that misreading is exactly how
    a wrong rule stays invisible, because John only reviews coils already flagged."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(40):
            run, uid = f"u{i}", f"uc{i}"
            _run(conn, run, project=f"U{i}")
            _coil(conn, uid, run, tag=f"UNSEEN-{i}")
            _firing(conn, run, uid, "top_flange", rule_id="R-010")
        conn.commit()
    finally:
        conn.close()

    entry = _rule(measure_rule_observatory(), "R-010")

    assert entry["fired"] == 40
    assert entry["second_opinion"] == 0
    assert entry["coverage"] == 0.0
    assert entry["blind_spot"] == 40
    assert entry["disagreement_rate"] is None
    assert entry["flag"] == "no_second_opinion"
    # No field may be readable as "this rule is right".
    assert "accuracy" not in entry
    assert "correct" not in entry
    assert "agreement_rate" not in entry


def test_blind_spots_are_reported_beside_the_ranked_rules(ledger):
    """"Checked and wrong" and "never checked" have to be equally visible, so the unchecked
    rules get their own list rather than sorting to the bottom of the disagreement table."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(12):
            run, uid = f"b{i}", f"bc{i}"
            _run(conn, run, project=f"B{i}")
            _coil(conn, uid, run, tag=f"BLIND-{i}")
            _firing(conn, run, uid, "bottom_flange", rule_id="R-010b")
        conn.commit()
    finally:
        conn.close()

    report = measure_rule_observatory()
    blind = {e["rule_id"]: e for e in report["blind_spots"]}

    assert "R-010b" in blind
    assert blind["R-010b"]["blind_spot"] == 12


def test_denominator_is_second_opinion_not_fired(ledger):
    """100 firings, 6 observed, 3 disagreed -> 0.5. Dividing by `fired` would report 0.03
    and score 94 coils nobody looked at as agreement."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(100):
            run, uid, tag = f"d{i}", f"dc{i}", f"DEN-{i}"
            _run(conn, run, project=f"D{i}")
            _coil(conn, uid, run, tag=tag)
            _firing(conn, run, uid, "suction_io", rule_id="R-061v")
            if i < 6:
                _checklist(conn, run, key="O2", verdict="mismatch" if i < 3 else "match",
                           coil_tag=tag)
        conn.commit()
    finally:
        conn.close()

    entry = _rule(measure_rule_observatory(), "R-061v")

    assert entry["fired"] == 100
    assert entry["second_opinion"] == 6
    assert entry["disagreed"] == 3
    assert entry["disagreement_rate"] == 0.5
    assert entry["coverage"] == 0.06


def test_signal_too_weak_below_the_threshold(ledger):
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(MIN_SECOND_OPINION - 1):
            run, uid, tag = f"w{i}", f"wc{i}", f"WEAK-{i}"
            _run(conn, run, project=f"W{i}")
            _coil(conn, uid, run, tag=tag)
            _firing(conn, run, uid, "header_flange", rule_id="R-003")
            _checklist(conn, run, key="HF", verdict="mismatch", coil_tag=tag)
        conn.commit()
    finally:
        conn.close()

    entry = _rule(measure_rule_observatory(), "R-003")

    assert entry["second_opinion"] == MIN_SECOND_OPINION - 1
    assert entry["disagreement_rate"] is None
    assert entry["flag"] == "signal_too_weak"


def test_audit_only_evidence_marks_a_rule_review_conditional(ledger):
    """Evidence gathered from coils John was already suspicious of cannot support a
    statistical claim. The flag-independent audit draw is the only one that can, so a rule
    with none of it says so."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(6):
            run, uid, tag = f"rc{i}", f"rcc{i}", f"RC-{i}"
            _run(conn, run, project=f"RC{i}")
            _coil(conn, uid, run, tag=tag)
            _firing(conn, run, uid, "return_flange", rule_id="R-004")
            _checklist(conn, run, key="RF", verdict="match", coil_tag=tag)
        # One rule whose evidence includes a genuine audit draw.
        for i in range(6):
            run, uid, tag = f"au{i}", f"auc{i}", f"AU-{i}"
            _run(conn, run, project=f"AU{i}")
            _coil(conn, uid, run, tag=tag)
            _firing(conn, run, uid, "top_flange", rule_id="R-010")
            _audit(conn, uid, run, tag=tag)
        conn.commit()
    finally:
        conn.close()

    report = measure_rule_observatory()
    assert _rule(report, "R-004")["review_conditional"] is True
    assert _rule(report, "R-004")["audit_coverage"] == 0.0
    audited = _rule(report, "R-010")
    assert audited["review_conditional"] is False
    assert audited["by_audit"] == 6


# --------------------------------------------------------------------------- #
# 2. the identity-grain join (the trap Stages 2 and 3 were built around)
# --------------------------------------------------------------------------- #
def test_firing_and_checklist_join_across_different_runs(ledger):
    """The firing lands on an analyse run's coil_uid; the checklist observation lands on a
    LATER run carrying only a coil_tag (compare_observation has no coil_uid column). A
    single-coil_uid join would report zero coverage for every rule."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(6):
            analyse, fill, uid, tag = f"an{i}", f"fi{i}", f"anc{i}", f"SPLIT-{i}"
            _run(conn, analyse, project="SPLIT")
            _coil(conn, uid, analyse, tag=tag, seq=i)
            _firing(conn, analyse, uid, "casing_depth", rule_id="R-070")
            _run(conn, fill, project="SPLIT", milestone="checklist_filled")
            _checklist(conn, fill, key="CD", verdict="mismatch", coil_tag=tag)
        conn.commit()
    finally:
        conn.close()

    entry = _rule(measure_rule_observatory(), "R-070")

    assert entry["second_opinion"] == 6
    assert entry["disagreed"] == 6
    assert entry["disagreement_rate"] == 1.0


def test_join_quality_separates_same_run_from_identity_only(ledger):
    conn = db.connect()
    try:
        _observed_corpus(conn)  # firing + checklist share a run_id
        conn.commit()
    finally:
        conn.close()

    report = measure_rule_observatory()
    assert report["join_quality"]["same_run"] >= MIN_IDENTITIES


def test_a_correction_alone_is_a_second_opinion(ledger):
    """John changing the value IS an independent observation, even with no checklist row."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(6):
            run, uid, tag = f"c{i}", f"cc{i}", f"CORR-{i}"
            _run(conn, run, project=f"C{i}")
            _coil(conn, uid, run, tag=tag)
            _firing(conn, run, uid, "suction_hd", rule_id="R-048")
            _correction(conn, run, uid, "HD2")
        conn.commit()
    finally:
        conn.close()

    entry = _rule(measure_rule_observatory(), "R-048")
    assert entry["second_opinion"] == 6
    assert entry["corrected"] == 6
    assert entry["by_correction"] == 6


# --------------------------------------------------------------------------- #
# 3. the vocabulary bridge
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "key,expected",
    [("O2", "O"), ("O", "O"), ("I3", "I"), ("HD4", "HD"), ("HDx1", "HDx"),
     ("CD", "CD"), ("OAL", "OAL"), ("DIST EXTENTION", "DIST EXTENTION"), ("S1", "S")],
)
def test_panel_keys_fold_onto_their_base(key, expected):
    """One engine field feeds every header column, so O2/O3 are N observations of ONE
    firing. Folding must not mangle a key that merely ends in a digit (HDx1)."""
    assert base_panel_key(key) == expected


def test_a_per_header_panel_key_joins_the_base_engine_field(ledger):
    """`suction_io` is the engine's name; the sheet disagrees about `O2`. Without the
    bridge that disagreement never reaches the rule that produced it."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(6):
            run, uid, tag = f"p{i}", f"pc{i}", f"PER-{i}"
            _run(conn, run, project=f"P{i}")
            _coil(conn, uid, run, tag=tag)
            _firing(conn, run, uid, "suction_io", rule_id="R-061v")
            _checklist(conn, run, key="O2", verdict="mismatch", coil_tag=tag, slot="slot.O4")
        conn.commit()
    finally:
        conn.close()

    assert _rule(measure_rule_observatory(), "R-061v")["disagreed"] == 6


def test_dist_extension_is_attributable(ledger):
    """`slot.DIST_EXT` has no panel key, so `record._compare_rows` files its rows under the
    LABEL. R-033's constant 6 vs the sheet's IF(SIZE in {H05,H10},17,6) is a live open
    divergence — if the bridge only followed the panel-key half it would land in the
    unattributable bucket, which is the one row this tool most needs to attribute."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(6):
            run, uid, tag = f"de{i}", f"dec{i}", f"DE-{i}"
            _run(conn, run, project=f"DE{i}")
            _coil(conn, uid, run, tag=tag)
            _firing(conn, run, uid, "dist_extension", rule_id="R-033")
            _checklist(conn, run, key="DIST EXTENTION", verdict="mismatch", coil_tag=tag,
                       slot="slot.DIST_EXT")
        conn.commit()
    finally:
        conn.close()

    report = measure_rule_observatory()
    assert _rule(report, "R-033")["disagreed"] == 6
    assert "DIST EXTENTION" not in {
        e["panel_key"] for e in report["unattributed_divergences"]
    }


def test_return_spacing_reaches_the_R_dimension(ledger):
    """`return_spacing` is a per-circuit LIST, so it bypasses the i/o/hd/sl/hdx role table
    and `build_drawing_slots` consumes it by name to write slot.R{even}. Real firings
    exposed the gap: without this the DX return-spacing rules would look unmeasured on a
    dimension the checklist actually checks constantly."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(6):
            run, uid, tag = f"rs{i}", f"rsc{i}", f"RS-{i}"
            _run(conn, run, project=f"RS{i}")
            _coil(conn, uid, run, tag=tag)
            _firing(conn, run, uid, "return_spacing", rule_id="R-022")
            _checklist(conn, run, key="R2", verdict="mismatch", coil_tag=tag, slot="slot.R4")
        conn.commit()
    finally:
        conn.close()

    entry = _rule(measure_rule_observatory(), "R-022")
    assert entry["fired_not_drawn"] == 0
    assert entry["disagreed"] == 6


def test_unattributed_divergence_is_reported_not_dropped(ledger):
    """`S` is recomputed in the slot layer, `OAL`/`CH` are sums, `FH`/`FL` come off the
    submittal — real CoilForge error with no rule to hang it on. Dropping it would make the
    corpus look cleaner than it is."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        _run(conn, "un1", project="UN")
        _coil(conn, "unc1", "un1", tag="UNATTR-1")
        _firing(conn, "un1", "unc1", "casing_depth", rule_id="R-070")
        _checklist(conn, "un1", key="S1", verdict="mismatch", coil_tag="UNATTR-1")
        _checklist(conn, "un1", key="OAL", verdict="mismatch", coil_tag="UNATTR-1")
        conn.commit()
    finally:
        conn.close()

    report = measure_rule_observatory()
    unattributed = {e["panel_key"]: e for e in report["unattributed_divergences"]}

    assert "S" in unattributed and "OAL" in unattributed
    # ... and it was not silently folded into some rule's disagreement count.
    for entry in report["rules"]:
        assert entry["disagreed"] <= entry["second_opinion"]


# --------------------------------------------------------------------------- #
# 4. exclusions that would otherwise inflate correctness
# --------------------------------------------------------------------------- #
def test_a_firing_that_feeds_no_drawing_dimension_is_not_credited(ledger):
    """`collared_holes` / `notes` never reach a dimension, and the distributor `S` is
    recomputed by the slot layer rather than taken from the engine. Counting them as
    observed-and-agreed would hand a rule credit for a value the drawing never used."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(6):
            run, uid, tag = f"nd{i}", f"ndc{i}", f"ND-{i}"
            _run(conn, run, project=f"ND{i}")
            _coil(conn, uid, run, tag=tag)
            _firing(conn, run, uid, "collared_holes", rule_id="R-001")
            _checklist(conn, run, key="CD", verdict="match", coil_tag=tag)
        conn.commit()
    finally:
        conn.close()

    entry = _rule(measure_rule_observatory(), "R-001")

    assert entry["fired"] == 6
    assert entry["fired_not_drawn"] == 6
    assert entry["second_opinion"] == 0
    assert entry["disagreement_rate"] is None


def test_drifted_provenance_is_counted_but_excluded_from_rates(ledger):
    """A reconstruction that disagreed with the drawing is not trustworthy evidence about
    which rule produced what. It stays visible (the drift is itself a signal) but never
    reaches a numerator or a denominator."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(6):
            run, uid, tag = f"dr{i}", f"drc{i}", f"DR-{i}"
            _run(conn, run, project=f"DR{i}")
            _coil(conn, uid, run, tag=tag)
            _firing(conn, run, uid, "casing_depth", rule_id="R-DRIFT", fidelity="drifted")
            _checklist(conn, run, key="CD", verdict="mismatch", coil_tag=tag)
        conn.commit()
    finally:
        conn.close()

    entry = _rule(measure_rule_observatory(), "R-DRIFT")

    assert entry["fired"] == 6
    assert entry["fired_drifted"] == 6
    assert entry["second_opinion"] == 0
    assert entry["disagreed"] == 0


def test_live_and_recomputed_are_broken_out(ledger):
    conn = db.connect()
    try:
        _observed_corpus(conn)
        _run(conn, "lv1", project="LV")
        _coil(conn, "lvc1", "lv1", tag="LIVE-1")
        _firing(conn, "lv1", "lvc1", "casing_depth", rule_id="R-MIX", source="live")
        _run(conn, "rc1", project="RC")
        _coil(conn, "rcc1", "rc1", tag="RECOMP-1")
        _firing(conn, "rc1", "rcc1", "casing_depth", rule_id="R-MIX", source="recomputed")
        conn.commit()
    finally:
        conn.close()

    report = measure_rule_observatory()
    entry = _rule(report, "R-MIX")

    assert entry["fired_live"] == 1
    assert entry["fired_recomputed"] == 1
    assert report["provenance_mix"]["live"] >= 1
    assert report["provenance_mix"]["recomputed"] >= 1


def test_a_null_source_reads_as_live(ledger):
    """rule_firing rows written before migration 6 came from the 1c Tier-A seam, its only
    writer. The COALESCE convention is pinned here so it cannot be re-litigated."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        _run(conn, "nl1", project="NL")
        _coil(conn, "nlc1", "nl1", tag="NULLSRC-1")
        conn.execute(
            "INSERT INTO rule_firing (run_id, coil_uid, field_key, rule_id, confidence)"
            " VALUES ('nl1','nlc1','casing_depth','R-NULL','HIGH')"
        )
        conn.commit()
    finally:
        conn.close()

    assert _rule(measure_rule_observatory(), "R-NULL")["fired_live"] == 1


# --------------------------------------------------------------------------- #
# 5. adjudication scope
# --------------------------------------------------------------------------- #
def test_adjudication_is_attributed_to_the_rule(ledger):
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(6):
            run, uid, tag = f"aj{i}", f"ajc{i}", f"ADJ-{i}"
            _run(conn, run, project=f"AJ{i}")
            _coil(conn, uid, run, tag=tag)
            _firing(conn, run, uid, "casing_depth", rule_id="R-072")
            _checklist(conn, run, key="CD", verdict="mismatch", coil_tag=tag)
        _adjudication(conn, slot="slot.CD", verdict="coilforge_wrong")
        conn.commit()
    finally:
        conn.close()

    assert _rule(measure_rule_observatory(), "R-072")["adjudicated"] == {"coilforge_wrong": 6}


def test_a_terra_v_ruling_does_not_leak_onto_terra_h(ledger):
    """The variant axis exists precisely to stop a Terra V ruling silencing Terra H. If the
    scope match coarsened the token, one ruling would suppress a family it never examined."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(3):
            run, uid, tag = f"tv{i}", f"tvc{i}", f"TV-{i}"
            _run(conn, run, project=f"TV{i}")
            _coil(conn, uid, run, tag=tag, category="HGRH", family="TERRA_V",
                  variant="TERRA_V")
            _firing(conn, run, uid, "casing_depth", rule_id="R-TV")
            _checklist(conn, run, key="CD", verdict="mismatch", coil_tag=tag)
        for i in range(3):
            run, uid, tag = f"th{i}", f"thc{i}", f"TH-{i}"
            _run(conn, run, project=f"TH{i}")
            _coil(conn, uid, run, tag=tag, category="HGRH", family="TERRA_H",
                  variant="TERRA_H")
            _firing(conn, run, uid, "casing_depth", rule_id="R-TH")
            _checklist(conn, run, key="CD", verdict="mismatch", coil_tag=tag)
        _adjudication(conn, slot="slot.CD", verdict="checklist_wrong", category="HGRH",
                      family="TERRA_V", variant="TERRA_V")
        conn.commit()
    finally:
        conn.close()

    report = measure_rule_observatory()
    assert _rule(report, "R-TV")["adjudicated"] == {"checklist_wrong": 3}
    assert _rule(report, "R-TH")["adjudicated"] == {}


def test_a_size_scoped_ruling_does_not_match_another_size(ledger):
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(3):
            run, uid, tag = f"sz{i}", f"szc{i}", f"SZ-{i}"
            _run(conn, run, project=f"SZ{i}")
            _coil(conn, uid, run, tag=tag, unit_size="H05")
            _firing(conn, run, uid, "casing_depth", rule_id="R-SIZE")
            _checklist(conn, run, key="CD", verdict="mismatch", coil_tag=tag)
        _adjudication(conn, slot="slot.CD", verdict="checklist_wrong", scope="B20")
        conn.commit()
    finally:
        conn.close()

    assert _rule(measure_rule_observatory(), "R-SIZE")["adjudicated"] == {}


# --------------------------------------------------------------------------- #
# 6. degrade / safety / robustness
# --------------------------------------------------------------------------- #
def test_too_few_observed_identities_is_insufficient(ledger):
    conn = db.connect()
    try:
        _run(conn, "s1", project="S")
        _coil(conn, "sc1", "s1", tag="SMALL-1")
        _firing(conn, "s1", "sc1", "casing_depth", rule_id="R-070")
        _checklist(conn, "s1", key="CD", verdict="mismatch", coil_tag="SMALL-1")
        conn.commit()
    finally:
        conn.close()

    report = measure_rule_observatory()

    assert report["insufficient"] is True
    assert report["rules"] == []
    assert report["observed_identities"] == 1
    assert report["min_identities"] == MIN_IDENTITIES
    assert report["note"]


def test_no_ledger_is_reported_and_nothing_is_created(tmp_path, monkeypatch):
    """A GET must never bring a ledger into existence on a machine that never captured."""
    path = tmp_path / "absent.sqlite3"
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(path))
    monkeypatch.delenv(db.ENV_CAPTURE_ENABLED, raising=False)
    db.reset_caches_for_tests()
    try:
        report = measure_rule_observatory()
        assert report["exists"] is False
        assert report["insufficient"] is True
        assert not path.exists()
    finally:
        db.reset_caches_for_tests()


def test_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(tmp_path / "capture.sqlite3"))
    monkeypatch.setenv(db.ENV_CAPTURE_ENABLED, "0")
    db.reset_caches_for_tests()
    try:
        assert measure_rule_observatory()["enabled"] is False
    finally:
        db.reset_caches_for_tests()


def test_redaction_drops_every_entity_identifier(ledger):
    """A per-rule aggregate needs no coil tags, project numbers or free text at all, so the
    HTTP surface carries none."""
    conn = db.connect()
    try:
        _observed_corpus(conn)
        for i in range(6):
            run, uid, tag = f"rd{i}", f"rdc{i}", f"SECRET-TAG-{i}"
            _run(conn, run, project=f"SECRET-PROJECT-{i}")
            _coil(conn, uid, run, tag=tag)
            _firing(conn, run, uid, "casing_depth", rule_id="R-070")
            _correction(conn, run, uid, "CD", reason="SECRET-REASON")
        conn.commit()
    finally:
        conn.close()

    blob = json.dumps(measure_rule_observatory(redact=True))

    assert "SECRET-TAG" not in blob
    assert "SECRET-PROJECT" not in blob
    assert "SECRET-REASON" not in blob
    assert '"raw_private_data_returned": false' in blob.lower()


def test_malformed_rows_never_raise(ledger):
    conn = db.connect()
    try:
        _observed_corpus(conn)
        _run(conn, "m1", project="M")
        _coil(conn, "mc1", "m1", tag="MAL-1", category=None, family=None, unit_size=None)
        _firing(conn, "m1", "mc1", "not_a_real_engine_field", rule_id="R-UNKNOWN")
        _checklist(conn, "m1", key=None, verdict="mismatch", coil_tag="MAL-1")
        _checklist(conn, "m1", key="", verdict="mismatch", coil_tag="MAL-1")
        _adjudication(conn, slot="not.a.slot", verdict="coilforge_wrong")
        conn.commit()
    finally:
        conn.close()

    report = measure_rule_observatory()

    assert report.get("error") is None
    assert _rule(report, "R-UNKNOWN")["fired_not_drawn"] == 1


def test_the_route_exposes_the_review_aid_flags(ledger):
    fastapi = pytest.importorskip("fastapi")
    assert fastapi
    from fastapi.testclient import TestClient

    from coilforge.web_app import app

    conn = db.connect()
    try:
        _observed_corpus(conn)
        conn.commit()
    finally:
        conn.close()

    body = TestClient(app).get("/api/capture/rule-observatory").json()

    assert body["export_allowed"] is False
    assert body["production_drawing_approval_claimed"] is False
    assert body["raw_private_data_returned"] is False
    for entry in body.get("rules", []):
        assert "accuracy" not in entry
