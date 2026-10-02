"""TR-9: the /derive path rebuilds the Direct Coil review surfaces.

Analyze feeds `_engine_drawing_notes` + `_engine_drawing_dims` into the canonical record,
which is what puts the drawing notes and the engine dimensions on the paste-ready 52-field
surface. /derive never did, so a coil whose coating (or product/size) was corrected in the
browser kept showing the submittal-time notes — a manufacturing instruction that silently
never reached the order. Same family as the CD regression in 228d731: a post-process wired
into analyze only.

The rebuild needs the source candidate, which /derive does not receive (it resolves ONE
coil from a spec dict). The browser round-trips it back, and the backend checks its tag
against the coil being derived so a candidate read from the wrong coil page is discarded.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest  # noqa: E402

from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    _extract_candidates,
    derive_coil_template_drawing,
)

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from coilforge.web_app import app, _sanitize_derive_spec  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

REVIEW_SURFACE_KEYS = (
    "direct_coil_paste_ready",
    "readiness_report",
    "direct_coil_input_draft",
)


def _candidate_payload():
    """The candidate exactly as it crosses the wire: model_dump -> JSON -> dict."""
    candidate = _extract_candidates({})[0]
    return json.loads(json.dumps(candidate.model_dump(), default=str))


def _spec(**overrides):
    payload = _candidate_payload()
    spec = {
        "coil_category": "DX",
        "coil_hand": "LH",
        "tag": payload["tag"]["value"],
        "circuits": 2,
        "rows": 4,
        "feeds": 8,
        "finned_height": 24.0,
        "finned_length": 48.0,
        "suction_conn_size": 1.375,
        "product_type": "NOVA",
        "unit_size": "B20",
        "panel": {},
        "candidate": payload,
    }
    spec.update(overrides)
    return spec


def _attached(result):
    return [key for key in REVIEW_SURFACE_KEYS if key in result]


def _engine_dim_rows(result):
    return [
        field
        for field in result["direct_coil_paste_ready"]["fields"]
        if any(
            str(ref).startswith("EV-ENGINE-DIM-")
            for ref in (field.get("source_evidence_refs") or [])
        )
    ]


# --------------------------------------------------------------------------- #
# The no-op guard (H4): every existing caller must be unaffected
# --------------------------------------------------------------------------- #
def test_derive_without_candidate_attaches_nothing():
    """No candidate -> the response is what it has always been. The demo/text flow has no
    PDF coil pages and therefore no candidate, so it lands here too."""
    spec = _spec()
    spec.pop("candidate")
    result = derive_coil_template_drawing(spec)
    assert _attached(result) == []
    assert not result.get("manual_fill_errors")


# --------------------------------------------------------------------------- #
# The reported symptom
# --------------------------------------------------------------------------- #
def test_coating_correction_surfaces_the_r080_note():
    """R-080's 'Do Not Coat Last 5-6 inches...' must reach the paste-ready surface and be
    copyable — the paste set is what the engineer transcribes into the order."""

    def coating_rows(result):
        return [
            field
            for field in result["direct_coil_paste_ready"]["fields"]
            if field.get("value") and "Do Not Coat" in str(field["value"])
        ]

    plain = derive_coil_template_drawing(_spec())
    coated = derive_coil_template_drawing(_spec(coating="HERESITE"))

    assert not coating_rows(plain)
    rows = coating_rows(coated)
    assert rows, "the coating note never reached the paste-ready surface"
    assert rows[0]["status"] == "review_required"
    assert rows[0]["copy_enabled"] is True


def test_engine_dimensions_surface_as_a_whole_set():
    """`_engine_drawing_dims` returns every reviewable dimension the engine produced, so
    ~a dozen rows move — not just CD. Asserting one row would miss a regression in the
    other eleven."""
    result = derive_coil_template_drawing(_spec())
    rows = _engine_dim_rows(result)
    assert len(rows) >= 10, f"expected the full dim set, got {len(rows)}"
    assert all(row["value"] is not None for row in rows)
    assert all(row["status"] == "review_required" for row in rows)
    # Nothing the engine actually produced may be left blocked.
    assert result["readiness_report"]["summary_counts"]["blocked"] == 0


def test_draft_and_paste_surface_agree_on_the_same_dimension():
    """Both panels render side by side from the same draft. Refreshing one without the
    other shows a value in the paste table and a blank in the Direct Coil groups."""
    result = derive_coil_template_drawing(_spec(coating="HERESITE"))
    draft_cd = result["direct_coil_input_draft"]["fields"]["CD"]
    paste_cd = [
        field
        for field in result["direct_coil_paste_ready"]["fields"]
        if "EV-ENGINE-DIM-CD" in (field.get("source_evidence_refs") or [])
    ]
    assert paste_cd
    assert draft_cd["value"] == paste_cd[0]["value"]
    assert draft_cd["status"] == paste_cd[0]["status"]


def test_spec_field_edits_do_not_reach_the_candidate_sourced_rows():
    """KNOWN, DELIBERATE SHAPE — pinned so it is documented rather than discovered.

    The rebuild re-derives from the ORIGINAL candidate, so a spec-field edit (rows /
    return conn / coating) reaches `ctx` — and therefore the engine dims and notes — but
    not the candidate-sourced rows, which keep the submittal value. Editing rows 4 -> 6
    changes the computed dimensions while 'Rows Deep' still reads the submittal's 4.

    Not a regression: today every row is frozen at analyze time. Carrying spec edits into
    the candidate is a separate change (it would mean rewriting the source extract, which
    is where the submittal's own value has to stay visible).
    """
    four = derive_coil_template_drawing(_spec(rows=4))
    six = derive_coil_template_drawing(_spec(rows=6))

    def rows_deep(result):
        return [
            field
            for field in result["direct_coil_paste_ready"]["fields"]
            if str(field.get("direct_coil_label") or "").strip().lower().startswith("rows")
        ]

    # The candidate-sourced row is identical in both -- it never saw the edit.
    assert [f["value"] for f in rows_deep(four)] == [f["value"] for f in rows_deep(six)]
    # ...while the engine dims DID move with it, which is the point of the refresh.
    assert [f["value"] for f in _engine_dim_rows(four)] != [
        f["value"] for f in _engine_dim_rows(six)
    ]


# --------------------------------------------------------------------------- #
# Never invent provenance
# --------------------------------------------------------------------------- #
def test_manual_override_is_not_filed_as_engine_output():
    """A Tier-B override is a value the ENGINEER typed. `to_canonical` stamps every dim it
    receives with EV-ENGINE-DIM-<key> / source_type 'engine_rule', so letting one through
    would file a human value as engine output at `review_required` rather than
    `manual_override`. Analyze never hits this — it has no param_overrides."""
    result = derive_coil_template_drawing(
        _spec(
            param_overrides=[
                {"key": "CD", "value": 99.75, "override_reason": "field measured"}
            ]
        )
    )
    stamped_cd = [
        field
        for field in result["direct_coil_paste_ready"]["fields"]
        if "EV-ENGINE-DIM-CD" in (field.get("source_evidence_refs") or [])
    ]
    assert not stamped_cd, "a hand-typed value was filed with engine provenance"
    assert 99.75 not in [
        field.get("value") for field in result["direct_coil_paste_ready"]["fields"]
    ]
    # ...and the filter removed ONLY the overridden key.
    assert len(_engine_dim_rows(result)) >= 10


# --------------------------------------------------------------------------- #
# Identity guard — and its reasons are never silent
# --------------------------------------------------------------------------- #
def test_candidate_from_a_different_coil_is_discarded():
    """The cross-page mis-pairing guard: a concurrent re-analyze fan-out derives every coil
    at once, so a candidate read from the wrong page must never be used."""
    result = derive_coil_template_drawing(_spec(tag="CDXC-99"))
    assert _attached(result) == []
    assert any("mismatch" in err for err in result["manual_fill_errors"])


def test_coil_without_a_tag_is_skipped_with_a_stated_reason():
    """Some coils carry no candidate tag (it lives only on the cover row), so identity
    cannot be verified. Skipping is right; skipping SILENTLY is not — the engineer would
    see one coil's notes not move with no explanation."""
    result = derive_coil_template_drawing(_spec(tag=None))
    assert _attached(result) == []
    assert any("tag missing" in err for err in result["manual_fill_errors"])


def test_tag_comparison_ignores_case_and_surrounding_space():
    """The guard must not be so strict that it refuses every coil — that would disable the
    feature with nobody seeing an error."""
    tag = _candidate_payload()["tag"]["value"]
    result = derive_coil_template_drawing(_spec(tag=f"  {tag.lower()} "))
    assert sorted(_attached(result)) == sorted(REVIEW_SURFACE_KEYS)


def test_malformed_candidate_never_takes_down_the_fill():
    """The review surfaces are secondary; the drawing is the deliverable. A bad payload
    skips the refresh, it does not fail the manual fill."""
    result = derive_coil_template_drawing(_spec(candidate={"not": "a candidate"}))
    assert _attached(result) == []
    assert any("invalid" in err for err in result["manual_fill_errors"])
    assert result["svg"]


# --------------------------------------------------------------------------- #
# API boundary
# --------------------------------------------------------------------------- #
def test_api_merges_sanitizer_errors_with_the_workflow_reason():
    """web_app ASSIGNED `manual_fill_errors` after the workflow returned, which wiped the
    skip reason whenever any unrelated fill error fired — losing exactly the message that
    explains why a panel did not move."""
    spec = _spec(tag=None)
    spec["param_overrides"] = [{"key": "CD", "value": 3.5}]  # missing override_reason
    body = TestClient(app).post("/api/coil-drawing/derive", json=spec).json()
    errors = body["manual_fill_errors"]
    assert any("override_reason is required" in err for err in errors)
    assert any("tag missing" in err for err in errors)


def test_kill_switch_strips_the_candidate(monkeypatch):
    """COILFORGE_MANUAL_FILL=0 is the documented rollback lever for this whole feature, so
    it has to disable the review-surface refresh too."""
    monkeypatch.setenv("COILFORGE_MANUAL_FILL", "0")
    clean, _ = _sanitize_derive_spec(_spec())
    assert "candidate" not in clean


def test_api_rejects_a_non_object_candidate():
    clean, errors = _sanitize_derive_spec(_spec(candidate="nope"))
    assert "candidate" not in clean
    assert any("candidate must be an object" in err for err in errors)


# --------------------------------------------------------------------------- #
# The frontend half — the backend alone changes nothing on screen
# --------------------------------------------------------------------------- #
def test_frontend_ships_the_candidate_and_rerenders_the_shell():
    """app.js has to send the candidate and re-render, and the fan-out must read its
    EXPLICIT page rather than the shared active index (which would hand coil A's candidate
    to coil B)."""
    source = (REPO_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "opts.page.workflow?.candidates?.[0]" in source
    assert "activePdfCandidate()" in source
    assert (
        "deriveSpecFromTemplate(templateDrawing, productLine, unitSize, fills, candidate)"
        in source
    )
    assert "page.workflow.direct_coil_paste_ready = updated.direct_coil_paste_ready" in source
    assert "renderShell(workflowToUiState(state.ui, targetPage.workflow, null))" in source
