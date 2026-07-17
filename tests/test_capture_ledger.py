"""Capture ledger (1a): every coil selection's (inputs -> proposal -> correction)
triple is persisted to an append-only SQLite store instead of evaporating with the
HTTP response.

The load-bearing tests here are the two key traps — reading `page["coil_type"]` or
the top-level `drawing_parameter_set` would silently fill the corpus with plausible
garbage, which is worse than no corpus because it would be trusted. The rest guard
the ledger's promise that it is a pure observer: never breaks a request, never
stores raw bytes, never lands inside the repo, and never fails silently.
"""

from __future__ import annotations

import ast
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from coilforge.capture import db  # noqa: E402
from coilforge.capture.record import capture_milestone, coil_views  # noqa: E402
from coilforge.capture.schema import MIGRATIONS  # noqa: E402
from coilforge.case_journal import MILESTONES  # noqa: E402

_SRC = Path(__file__).resolve().parents[1] / "src" / "coilforge"


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


def _workflow_result(*, coils=2) -> dict:
    """A minimal stand-in shaped like run_pdf_to_drawing_workflow's return.

    Deliberately sets the DECOY keys to wrong-but-plausible values: page["coil_type"]
    carries cover-row item text and page["product_type"] carries the "DX" family
    default. A capture that reads those instead of template_drawing.extracted passes
    nothing here.
    """
    pages = []
    for index in range(coils):
        tag = f"CDXC-{index + 1}"
        pages.append(
            {
                "page_id": f"pdf-coil-{index + 1}",
                "index": index,
                "tag": tag,
                "coil_type": "DX Coil, 4 Row, Interlaced",  # decoy: cover item text
                "product_type": "DX",                        # decoy: coil family default
                "fit_inputs": {"tag": tag, "coil_type": "DX", "rows": 4},
                "workflow": {
                    "template_drawing": {
                        "extracted": {
                            "coil_category": "DX",
                            "hand": "LH",
                            "header_type": "HEADER_1",
                            "circuits": 3,
                            "tag": tag,
                        },
                        "product_type": "TERRA H",
                        "unit_size": "040",
                        "template_id": "coilmaster_dx_lh_header1",
                        "template_found": True,
                        "generation_allowed": True,
                        "slot_values": {"slot.CD": 5.5, "slot.TAG": tag},
                        "slot_sources": {
                            "slot.CD": {
                                "value": 5.5, "source": "engine_rule",
                                "as_built": None, "validation": "no_as_built_reference",
                            }
                        },
                        "svg": f"<svg data-tag='{tag}'></svg>",
                    },
                    "drawing_parameter_set": {
                        "parameters": {
                            "CD": {
                                "key": "CD", "label": "Casing Depth", "value": 5.5,
                                "unit": "in", "mode": "default", "status": "review_required",
                                "review_required": True, "blocked_reason": None,
                                "source_evidence": [],
                            }
                        },
                        "preview_allowed": True,
                    },
                    "direct_coil_input_draft": {
                        "fields": {
                            "rows_deep": {
                                "value": 4, "status": "review_required",
                                "review_required": True, "source_evidence": [],
                            }
                        }
                    },
                },
            }
        )
    return {
        "pdf_coil_pages": pages,
        "pdf_intake_summary": {
            "project_number": "24-118",
            "project_name": "Olympic",
            "source_id": "PDF-UPLOAD-INTAKE-001",
            "source_filename": "SIGNED 2819 - Olympic.pdf",
        },
        # Top-level set == the SELECTED coil only. A capture that reads this records
        # one coil out of N.
        "drawing_parameter_set": {"parameters": {"CD": {"key": "CD", "value": 99.9}}},
    }


# --- the two key traps ------------------------------------------------------

def test_capture_reads_real_coil_category_not_cover_item_text(ledger):
    """page["coil_type"] is the cover row's ITEM TEXT and page["product_type"]
    defaults to the "DX" family. The engine values live under
    workflow.template_drawing. Reading the obvious keys yields plausible garbage."""
    assert capture_milestone("intake_drawing", result=_workflow_result(coils=1))

    (row,) = _rows(ledger, "SELECT coil_category, product_line, terra_variant, unit_size FROM coil")
    coil_category, product_line, terra_variant, unit_size = row

    assert coil_category == "DX"  # from extracted, NOT "DX Coil, 4 Row, Interlaced"
    assert product_line == "TERRA H"  # from template_drawing, NOT the "DX" default
    # terra_variant is never carried on the result; it is derived from the label.
    assert terra_variant == "TERRA_H_C"
    assert unit_size == "040"


def test_capture_records_every_coil_not_just_the_selected_one(ledger):
    """result["drawing_parameter_set"] is the selected coil's set. Per-coil params
    live at pdf_coil_pages[i]["workflow"]. A capture that reads the top level would
    record N coils but only one coil's parameters — and the wrong value at that."""
    assert capture_milestone("intake_drawing", result=_workflow_result(coils=3))

    assert _rows(ledger, "SELECT COUNT(*) FROM coil")[0][0] == 3
    values = _rows(
        ledger,
        "SELECT value_num FROM field_observation WHERE stage='drawing_param' AND field_key='CD'",
    )
    assert len(values) == 3, "each coil must contribute its own drawing_param rows"
    # 99.9 is the top-level decoy; every coil's real value is 5.5.
    assert {v[0] for v in values} == {5.5}


# --- the ledger's promises --------------------------------------------------

def test_capture_survives_missing_project_identity(ledger):
    """The journal deliberately drops runs with no project identity (demo /
    sanitized / derive). Those are ML data — the ledger must keep them. This is the
    gap the ledger exists to close, so it is not a nice-to-have."""
    result = _workflow_result(coils=1)
    result.pop("pdf_intake_summary")

    assert capture_milestone("coil_manual_fill", result=result)
    (row,) = _rows(ledger, "SELECT project_number, coil_count FROM run")
    assert row == (None, 1)


def test_capture_records_derive_shape(ledger):
    """/derive's result IS the template_drawing (pdf_text_to_template_drawing's
    return with keys bolted on) — no pdf_coil_pages wrapper. The adapter must
    normalize all three result shapes, not just the PDF workflow's."""
    derive_result = {
        "extracted": {"coil_category": "HGRH", "tag": "RHHGRC-1"},
        "product_type": "TERRA V",
        "unit_size": "060",
        "slot_values": {"slot.CD": 7.25},
        "slot_sources": {},
        "drawing_parameter_set": {"parameters": {}},
    }
    assert capture_milestone("coil_manual_fill", result=derive_result)

    (row,) = _rows(ledger, "SELECT tag, coil_category, product_line, terra_variant FROM coil")
    assert row == ("RHHGRC-1", "HGRH", "TERRA V", "TERRA_V")


def test_gate_flags_absent_means_null(ledger):
    """Gate flags only exist on template_drawing when they fire — there is no
    false/default form. `.get(k) is not None` is the only correct test."""
    assert capture_milestone("intake_drawing", result=_workflow_result(coils=1))
    assert _rows(ledger, "SELECT gate_flags_json FROM coil")[0][0] is None

    blocked = _workflow_result(coils=1)
    td = blocked["pdf_coil_pages"][0]["workflow"]["template_drawing"]
    td["not_registered_reason"] = "no seeded Ventum+ DX reference"
    td["unregistered_ventum_plus_dx"] = True
    assert capture_milestone("intake_drawing", result=blocked)

    flags = _rows(ledger, "SELECT gate_flags_json FROM coil WHERE gate_flags_json IS NOT NULL")
    assert len(flags) == 1
    assert "unregistered_ventum_plus_dx" in flags[0][0]


def test_capture_failure_never_breaks_the_caller(ledger, monkeypatch):
    """A capture failure must never reach the request — and must never be silent
    either. Silent best-effort writes are exactly how four journal milestones were
    lost for months."""
    import coilforge.capture.record as record_module

    def _boom(*_args, **_kwargs):
        raise RuntimeError("ledger exploded")

    monkeypatch.setattr(record_module.db, "connect", _boom)
    # Must not raise.
    assert capture_milestone("intake_drawing", result=_workflow_result(coils=1)) is None
    # ...and the failure must be remembered somewhere.
    assert db.last_error() is not None


def test_capture_logs_adapter_failure_to_capture_error(ledger, monkeypatch):
    """When the DB is reachable but the adapter trips, the error lands in the
    ledger's own error table rather than vanishing."""
    import coilforge.capture.record as record_module

    monkeypatch.setattr(
        record_module, "coil_views", lambda _r: (_ for _ in ()).throw(ValueError("bad shape"))
    )
    assert capture_milestone("intake_drawing", result=_workflow_result()) is None

    errors = _rows(ledger, "SELECT phase, error FROM capture_error")
    assert len(errors) == 1
    assert "bad shape" in errors[0][1]


def test_capture_disabled_by_env(ledger, monkeypatch):
    """COILFORGE_CAPTURE=0 turns the ledger off without reverting the branch —
    mirrors the COILFORGE_MANUAL_FILL pattern, including that unset means ON."""
    monkeypatch.setenv(db.ENV_CAPTURE_ENABLED, "0")
    assert capture_milestone("intake_drawing", result=_workflow_result()) is None
    assert not ledger.exists(), "a disabled ledger must not even create the DB file"

    monkeypatch.setenv(db.ENV_CAPTURE_ENABLED, "1")
    assert capture_milestone("intake_drawing", result=_workflow_result())


def test_capture_db_refuses_a_path_inside_a_git_repo(tmp_path, monkeypatch):
    """The ledger accumulates every project it has ever seen into one file. It must
    never land in a checkout. Walks for .git rather than trusting a REPO_ROOT
    constant — inside a worktree that constant resolves to the WORKTREE root and
    would happily accept a path in the main checkout."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(repo / "sub" / "capture.sqlite3"))

    with pytest.raises(db.CaptureConfigError):
        db.connect()

    # A worktree marks itself with a .git FILE, not a directory.
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: ../repo/.git/worktrees/wt", encoding="utf-8")
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(worktree / "capture.sqlite3"))
    with pytest.raises(db.CaptureConfigError):
        db.connect()


def test_artifact_stores_hashes_never_bytes(ledger):
    """Privacy posture: hashes and normalized engineering values only. The customer
    filename carries their name, so it is hashed rather than stored."""
    assert capture_milestone(
        "intake_drawing", result=_workflow_result(coils=1), pdf_bytes=b"%PDF-1.4 fake"
    )

    conn = sqlite3.connect(str(ledger))
    try:
        columns = conn.execute("PRAGMA table_info(artifact)").fetchall()
    finally:
        conn.close()
    assert not [c for c in columns if "BLOB" in str(c[2]).upper()]

    kinds = {row[0] for row in _rows(ledger, "SELECT kind FROM artifact")}
    assert kinds == {"template_svg", "submittal_pdf"}

    (name_hash,) = _rows(ledger, "SELECT source_filename FROM run")[0]
    assert name_hash and "Olympic" not in name_hash


def test_migrations_are_forward_only_and_additive(ledger):
    """Append-only DATA. Derived VIEWs may be replaced (a view carries no
    information of its own) — that exception is what lets the dedup key be
    redefined later without a data migration."""
    for _description, statements in MIGRATIONS:
        for statement in statements:
            upper = " ".join(statement.upper().split())
            assert "DROP TABLE" not in upper
            assert not upper.startswith("UPDATE ")
            assert not upper.startswith("DELETE ")


def test_migration_runner_is_idempotent(ledger):
    assert capture_milestone("intake_drawing", result=_workflow_result(coils=1))
    assert capture_milestone("intake_drawing", result=_workflow_result(coils=1))

    versions = _rows(ledger, "SELECT version FROM migration ORDER BY version")
    assert versions == [(index + 1,) for index in range(len(MIGRATIONS))]
    assert _rows(ledger, "PRAGMA user_version")[0][0] == len(MIGRATIONS)
    assert _rows(ledger, "SELECT COUNT(*) FROM run")[0][0] == 2


def test_dedup_components_distinguish_result_deciding_inputs(ledger):
    """Reselecting the cover page on the same bytes changes WHICH COILS ARE READ,
    so it is a result-deciding input and must not be folded away. source_id is a
    provenance label and must not split the key. Both live as columns; the key
    itself is a view (1d) precisely so the definition stays revisable."""
    for hint in (3, 7):
        assert capture_milestone(
            "intake_drawing", result=_workflow_result(coils=1),
            pdf_bytes=b"%PDF same bytes", cover_page_hint=hint,
        )

    rows = _rows(ledger, "SELECT input_hash, cover_page_hint FROM run ORDER BY cover_page_hint")
    assert rows[0][0] == rows[1][0], "same PDF -> same input_hash"
    assert [r[1] for r in rows] == [3, 7], "cover_page_hint must survive as its own column"


def test_route_gate_wins_over_recomputation(ledger):
    """The ledger must record the verdict John was actually shown.

    build_project_gate is pure — but purity is not the same as taking the same
    arguments. /api/review/project passes checklist_review= so an engine-vs-Excel
    mismatch becomes an exception; recomputing without it would quietly file those
    coils as "pass" and corrupt the exact label review triage trains on.
    """
    result = _workflow_result(coils=1)
    route_gate = {
        "coils": [
            {
                "tag": "CDXC-1",
                "verdict": "exception",
                "exceptions": [{"key": "CD", "reason": "engine_vs_checklist"}],
                "overrides": [],
            }
        ]
    }
    assert capture_milestone("project_review", result=result, gate=route_gate)

    (row,) = _rows(ledger, "SELECT verdict, exceptions_json FROM gate_verdict")
    assert row[0] == "exception", "the route's gate must win over a re-derivation"
    assert "engine_vs_checklist" in row[1]


def test_gate_is_recomputed_when_the_route_has_none(ledger):
    """Milestones that never had a checklist to merge (intake_drawing) are safe to
    re-derive — the inputs are the same ones the route would have used."""
    assert capture_milestone("intake_drawing", result=_workflow_result(coils=2))
    verdicts = _rows(ledger, "SELECT verdict FROM gate_verdict")
    assert len(verdicts) == 2


def test_no_engine_stage_is_claimed(ledger):
    """The engine's confidence buckets cannot be recovered from the result —
    HeaderPrepopulateResponse is compressed to a review_items string list inside
    derive_slot_values and discarded. 1a must not pretend otherwise; capturing it
    needs an engine hook (1c)."""
    assert capture_milestone("intake_drawing", result=_workflow_result(coils=1))
    stages = {row[0] for row in _rows(ledger, "SELECT DISTINCT stage FROM field_observation")}
    assert stages == {"slot", "drawing_param", "draft"}


def test_coil_views_ignores_unrecognized_shapes(ledger):
    """A payload-only milestone (package_assembled / quote_package) has no coil
    surface. It should record a run with zero coils, not invent one."""
    assert coil_views({"some": "payload"}) == []
    assert capture_milestone("package_assembled", request_payload={"coils": [{"tag": "X"}]})
    assert _rows(ledger, "SELECT coil_count FROM run")[0][0] == 0


# --- 5b: journal recovery ---------------------------------------------------

def test_every_journaled_milestone_is_in_the_allowlist():
    """The regression guard for the original bug: four milestones fired from
    web_app.py but were absent from MILESTONES, so record_coil_milestone returned an
    "unknown milestone" string the caller discarded — they journaled nothing for
    months. A milestone literal that is not in the allowlist is silently dropped, so
    the seventh one cannot be allowed to repeat it."""
    source = (_SRC / "web_app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    fired: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_journal_milestone"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            fired.add(node.args[0].value)

    assert fired, "AST walk found no _journal_milestone calls — the guard is not looking"
    missing = fired - set(MILESTONES)
    assert not missing, f"milestones fired but not in the allowlist (silent drop): {missing}"


# --- 5c: bypass-route capture ------------------------------------------------

def test_mechanical_fit_capture_records_nested_verdicts_with_tags(ledger):
    """mechanical_fit's verdict is NESTED (width/height/drain_pan .verdict), one row
    per dimension, vocab PASS/FAIL/CANNOT_EVALUATE. The coil tag is present, so a row
    can join a coil later. Reading the entry-level (there is none) would capture 0."""
    report = {
        "coils": [
            {
                "tag": "CDXC-1",
                "width": {"verdict": "PASS", "basis": "FL", "margin": 2.5},
                "height": {"verdict": "CANNOT_EVALUATE", "basis": "FH", "margin": None},
                # drain_pan is a DrainPanFitResult (no basis) — labeled by partner_tag.
                "drain_pan": {"verdict": "PASS", "partner_tag": "RHHGRC-1"},
            },
            {"tag": "RHHGRC-1", "width": {"verdict": "FAIL", "basis": "OAL", "margin": -1.0},
             "height": None, "drain_pan": None},
        ],
        "review_required": True,
    }
    assert capture_milestone("mechanical_fit", compare={"comparator": "mechanical_fit", "report": report})

    rows = _rows(
        ledger,
        "SELECT coil_tag, key, label, verdict FROM compare_observation"
        " WHERE comparator='mechanical_fit' ORDER BY coil_tag, key",
    )
    # CDXC-1: width+height+drain_pan (3), RHHGRC-1: width only (height/drain_pan None) (1)
    assert rows == [
        ("CDXC-1", "drain_pan", "RHHGRC-1", "PASS"),   # drain_pan labeled by partner
        ("CDXC-1", "height", "FH", "CANNOT_EVALUATE"),
        ("CDXC-1", "width", "FL", "PASS"),
        ("RHHGRC-1", "width", "OAL", "FAIL"),
    ]


def test_ccsi_capture_records_flat_verdicts_as_orphan_rows(ledger):
    """ccsi's verdict is FLAT (fields[j].verdict), vocab match/mismatch/... The body
    has NO coil identity, so coil_tag is NULL — orphan rows recorded on purpose, so
    '0 rows' can't masquerade as 'captured'. Threading the tag is deferred to 1a'."""
    report = {
        "fields": [
            {"key": "CD", "coilforge": 5.5, "ccsi": 5.5, "verdict": "match"},
            {"key": "R", "coilforge": 3.317, "ccsi": 1.3125, "verdict": "mismatch"},
        ],
        "compared": 2, "mismatch_count": 1,
    }
    assert capture_milestone("ccsi_compare", compare={"comparator": "ccsi", "report": report})

    rows = _rows(
        ledger,
        "SELECT coil_tag, key, verdict FROM compare_observation WHERE comparator='ccsi'"
        " ORDER BY key",
    )
    assert rows == [(None, "CD", "match"), (None, "R", "mismatch")]
    # The orphan-ness is explicit: every ccsi row is coil_tag NULL by design.
    assert all(r[0] is None for r in rows)


def test_compare_capture_makes_a_coil_less_run(ledger):
    """A compare route carries no workflow dict, so the run has zero coils and only
    compare_observation rows — not a masquerade as a coil-bearing run."""
    assert capture_milestone(
        "mechanical_fit",
        compare={"comparator": "mechanical_fit",
                 "report": {"coils": [{"tag": "X", "width": {"verdict": "PASS"}}]}},
    )
    assert _rows(ledger, "SELECT coil_count FROM run")[0][0] == 0
    assert _rows(ledger, "SELECT COUNT(*) FROM coil")[0][0] == 0
    assert _rows(ledger, "SELECT COUNT(*) FROM compare_observation")[0][0] == 1


def test_journal_outcome_is_recorded_on_the_run(ledger, monkeypatch, tmp_path):
    """The journal's event_id links the ledger run to its JSONL line, and a journal
    failure surfaces as journal_error instead of vanishing. The journal runs first
    precisely so this link is possible on an append-only store."""
    import coilforge.web_app as web_app

    monkeypatch.setenv("PO_RELEASE_CASE_JOURNAL_DIR", str(tmp_path / "journal"))
    # A milestone WITH identity journals and links its event_id.
    web_app._journal_milestone(
        "coil_manual_fill",
        result={"template_drawing": {"extracted": {"coil_category": "DX", "tag": "CDXC-1"},
                                     "slot_values": {}, "slot_sources": {}}},
        request_payload={"project_number": "24-118", "tag": "CDXC-1"},
    )
    (event_id, error) = _rows(ledger, "SELECT journal_event_id, journal_error FROM run")[0]
    assert event_id and error is None

    line = (tmp_path / "journal").glob("coil-*.jsonl")
    import json
    events = [json.loads(l) for f in line for l in f.read_text(encoding="utf-8").splitlines()]
    assert any(e["event_id"] == event_id for e in events), "run must link a real JSONL line"
    (coil_line,) = [e for e in events if e["value"]["milestone"] == "coil_manual_fill"]
    assert coil_line["value"]["coil_tags"] == ["CDXC-1"], "the singular /derive tag must survive"


# --- 1b: correction capture (previous_value recovery) ------------------------

def _derive_with_override(*, panel, slot_values, circuits=None):
    """A /derive-shaped result: the result IS the template_drawing, with a
    drawing_parameter_set whose overridden fields carry mode=='manual' (exactly what
    parameter_set_from_template_drawing stamps on a Tier-B override)."""
    result = {
        "extracted": {"coil_category": "DX", "tag": "CDXC-1"},
        "product_type": "TERRA H",
        "unit_size": "040",
        "slot_values": slot_values,
        "slot_sources": {},
        "drawing_parameter_set": {"parameters": panel, "preview_allowed": True},
    }
    payload = {"tag": "CDXC-1"}
    if circuits is not None:
        payload["circuits"] = circuits
    return result, payload


def test_correction_captures_tier_b_before_and_after(ledger):
    """The correction half of the triple: a Tier-B override records BOTH the machine
    proposal (previous) and the human value (new). The 'before' is not stored raw —
    it is recomputed by re-resolving the panel WITHOUT overrides, which is
    deterministic because Tier-B is panel-only and never mutates slot_values."""
    panel = {
        "R": {"key": "R", "value": 3.5, "mode": "manual", "status": "review_required",
              "review_required": True, "blocked_reason": None, "source_evidence": [], "unit": "in"},
        "CD": {"key": "CD", "value": 5.5, "mode": "default", "status": "review_required",
               "review_required": True, "source_evidence": []},
    }
    # slot.R2 is R's representative slot -> baseline R re-resolves to 0.5 (machine value).
    result, payload = _derive_with_override(
        panel=panel, slot_values={"slot.R2": 0.5, "slot.CD": 5.5, "slot.TAG": "CDXC-1"},
    )
    assert capture_milestone("coil_manual_fill", result=result, request_payload=payload)

    rows = _rows(
        ledger,
        "SELECT field_key, previous_value_num, previous_mode, new_value_num, new_mode"
        " FROM correction",
    )
    # Only R was overridden (mode=='manual'); CD stayed 'default' -> not a correction.
    assert rows == [("R", 0.5, "default", 3.5, "manual")]


def test_correction_event_sourced_before_and_reason(ledger):
    """1b reflection path: when the derive stored manual_override_events, the ledger
    reads the before-value + reason straight from that snapshot — NOT a recompute.
    This is load-bearing: reflection merges the override into slot_values, so slot.CD
    is already 9.5 here; an override-free re-resolve would read 9.5 and drop the
    correction (before == after). The stored snapshot keeps the true machine proposal
    (5.5) and carries the reason (which the old panel-only path wrote as NULL)."""
    panel = {
        "CD": {"key": "CD", "value": 9.5, "mode": "manual", "status": "review_required",
               "review_required": True, "source_evidence": [], "unit": "in"},
    }
    result, payload = _derive_with_override(
        panel=panel, slot_values={"slot.CD": 9.5},  # already reflected by 1b
    )
    result["manual_override_events"] = [
        {"key": "CD", "slot": "slot.CD", "previous_value": 5.5, "previous_mode": "default",
         "new_value": 9.5, "override_reason": "field measured", "source_evidence": []},
    ]
    assert capture_milestone("coil_manual_fill", result=result, request_payload=payload)

    rows = _rows(
        ledger,
        "SELECT field_key, previous_value_num, previous_mode, new_value_num, new_mode,"
        " override_reason FROM correction",
    )
    assert rows == [("CD", 5.5, "default", 9.5, "manual", "field measured")]


def test_no_override_writes_no_correction(ledger):
    """A derive with no Tier-B override (no manual-mode panel field) writes no
    correction rows — the table only holds fields a human actually changed."""
    panel = {"CD": {"key": "CD", "value": 5.5, "mode": "default", "status": "review_required",
                    "review_required": True, "source_evidence": []}}
    result, payload = _derive_with_override(panel=panel, slot_values={"slot.CD": 5.5})
    assert capture_milestone("coil_manual_fill", result=result, request_payload=payload)
    assert _rows(ledger, "SELECT COUNT(*) FROM correction")[0][0] == 0


def test_correction_survives_missing_baseline(ledger, monkeypatch):
    """A recompute failure must degrade to no correction row, never propagate. It
    runs inside capture_milestone's single pre-transaction build, so an exception
    would sink the WHOLE milestone — including the human 'after' values already built
    for field_observation. Failure -> [] + a capture_error row (never silent)."""
    from coilforge.services import drawing_param_resolver

    def _boom(*args, **kwargs):
        raise RuntimeError("baseline recompute failed")

    monkeypatch.setattr(drawing_param_resolver, "parameter_set_from_template_drawing", _boom)

    panel = {"R": {"key": "R", "value": 3.5, "mode": "manual", "status": "review_required",
                   "review_required": True, "source_evidence": []}}
    result, payload = _derive_with_override(panel=panel, slot_values={"slot.R2": 0.5})
    assert capture_milestone("coil_manual_fill", result=result, request_payload=payload)

    # No correction row, but the request survived and the human "after" value is kept.
    assert _rows(ledger, "SELECT COUNT(*) FROM correction")[0][0] == 0
    after = _rows(
        ledger,
        "SELECT value_num FROM field_observation WHERE stage='drawing_param' AND field_key='R'",
    )
    assert after == [(3.5,)]
    # The failure was logged, not swallowed silently.
    assert _rows(ledger, "SELECT COUNT(*) FROM capture_error")[0][0] >= 1


def test_multi_header_override_previous_uses_circuits(ledger):
    """A multi-header override (I2) is surfaced only when circuits raises the header
    count above what the slots imply. The baseline recompute must thread the SAME
    circuits the live derive used, or the baseline has no I2 and previous_mode reads
    None instead of the real 'blocked' the machine panel showed. (previous_value stays
    None either way — the resolver uses .get, so the correction set is never dropped;
    circuits' load-bearing effect here is previous_mode fidelity.)"""
    panel = {"I2": {"key": "I2", "value": 2.0, "mode": "manual", "status": "review_required",
                    "review_required": True, "source_evidence": []}}
    # Only header-1 slots -> slot-inferred header count == 1; circuits=2 raises it so
    # the baseline surfaces I2 as a blocked (engine-underived) field.
    result, payload = _derive_with_override(
        panel=panel, slot_values={"slot.I1": 1.0, "slot.R2": 0.5}, circuits=2,
    )
    assert capture_milestone("coil_manual_fill", result=result, request_payload=payload)

    (row,) = _rows(
        ledger,
        "SELECT field_key, previous_value_num, previous_mode, new_value_num FROM correction",
    )
    # previous_mode=='blocked' proves circuits was threaded; None would mean it wasn't.
    assert row == ("I2", None, "blocked", 2.0)
