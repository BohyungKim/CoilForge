"""Recording a ruling: validation, the append-only ledger, and where it is allowed to write."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

yaml = pytest.importorskip("yaml")

from coilforge.capture import db  # noqa: E402
from coilforge.review.adjudicate import (  # noqa: E402
    AdjudicationError,
    record_adjudication,
)
from coilforge.review.divergence import load_registry  # noqa: E402


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv(db.ENV_CAPTURE_DB, str(tmp_path / "capture.sqlite3"))
    return tmp_path / "capture.sqlite3"


def _payload(**over):
    base = {
        "coil_category": "HGRH",
        "product_family": "TERRA_V",
        "terra_variant": "TERRA_V",
        "unit_size_scope": "*",
        "slot": "slot.CD",
        "verdict": "checklist_wrong",
        "reason": "the HGRH sheet has no TERRA V branch",
    }
    base.update(over)
    return base


def _rows(path: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM divergence_adjudication ORDER BY adj_id"
        ).fetchall()
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# validation -> 400
# --------------------------------------------------------------------------- #
def test_a_blank_reason_is_rejected(tmp_path, ledger):
    with pytest.raises(AdjudicationError, match="non-empty reason"):
        record_adjudication(_payload(reason="   "), staging_path=tmp_path / "s.yaml")


def test_an_unknown_verdict_is_rejected(tmp_path, ledger):
    with pytest.raises(AdjudicationError, match="verdict must be"):
        record_adjudication(_payload(verdict="probably_fine"), staging_path=tmp_path / "s.yaml")


def test_a_ruling_without_a_slot_is_rejected(tmp_path, ledger):
    with pytest.raises(AdjudicationError, match="slot"):
        record_adjudication(_payload(slot=""), staging_path=tmp_path / "s.yaml")


def test_an_inverted_band_is_rejected(tmp_path, ledger):
    with pytest.raises(AdjudicationError, match="min exceeds max"):
        record_adjudication(
            _payload(delta_band={"min": 5, "max": 1}), staging_path=tmp_path / "s.yaml"
        )


# --------------------------------------------------------------------------- #
# what gets written where
# --------------------------------------------------------------------------- #
def test_a_ruling_lands_in_staging_and_the_ledger(tmp_path, ledger):
    staging = tmp_path / "s.yaml"
    out = record_adjudication(
        _payload(), staging_path=staging, promoted_path=tmp_path / "absent.yaml"
    )
    assert out["registered"] and out["registry_id"] == "KD-001"
    assert out["promoted"] is False and out["export_allowed"] is False

    doc = yaml.safe_load(staging.read_text(encoding="utf-8"))
    assert [e["id"] for e in doc["divergences"]] == ["KD-001"]
    assert doc["divergences"][0]["status"] == "proposed"

    rows = _rows(ledger)
    assert len(rows) == 1
    assert rows[0]["verdict"] == "checklist_wrong"
    assert rows[0]["divergence_key"] == "HGRH|TERRA_V|TERRA_V|*|SLOT.CD"
    assert rows[0]["registry_id"] == "KD-001"


def test_unresolved_is_ledgered_but_never_registered(tmp_path, ledger):
    staging = tmp_path / "s.yaml"
    out = record_adjudication(
        _payload(verdict="unresolved", reason="need the SOP page first"),
        staging_path=staging, promoted_path=tmp_path / "absent.yaml",
    )
    assert out["registered"] is False and out["registry_id"] is None
    assert not staging.exists(), (
        "'I could not decide' must not create a suppression"
    )
    assert len(_rows(ledger)) == 1, "but it IS part of the audit trail"


def test_re_adjudicating_appends_a_row_rather_than_updating(tmp_path, ledger):
    staging = tmp_path / "s.yaml"
    kwargs = {"staging_path": staging, "promoted_path": tmp_path / "absent.yaml"}
    record_adjudication(_payload(), **kwargs)
    record_adjudication(_payload(reason="revised after reading the SOP"), **kwargs)

    rows = _rows(ledger)
    assert len(rows) == 2, "the ledger is append-only — the sequence of rulings is the point"
    assert rows[0]["reason"] != rows[1]["reason"]
    assert [r["registry_id"] for r in rows] == ["KD-001", "KD-002"]


def test_ids_do_not_collide_with_already_promoted_ones(tmp_path, ledger):
    promoted = tmp_path / "p.yaml"
    promoted.write_text(
        yaml.safe_dump({"version": 1, "divergences": [{
            "id": "KD-005", "coil_category": "DX", "slot": "slot.S",
            "verdict": "checklist_wrong", "reason": "x",
        }]}),
        encoding="utf-8",
    )
    out = record_adjudication(
        _payload(), staging_path=tmp_path / "s.yaml", promoted_path=promoted
    )
    assert out["registry_id"] == "KD-006", (
        "numbering only the staging file would re-issue a promoted id"
    )


def test_the_route_never_writes_to_the_tracked_registry(tmp_path, ledger):
    """The tracked file must be byte-identical after a ruling.

    A concurrent session auto-commits this working tree, so a browser action that touched
    a tracked path could carry an un-reviewed ruling into a commit.
    """
    from coilforge.review.divergence import _PROMOTED_PATH

    before = _PROMOTED_PATH.read_bytes()
    record_adjudication(_payload(), staging_path=tmp_path / "s.yaml")
    assert _PROMOTED_PATH.read_bytes() == before


def test_a_staged_ruling_annotates_immediately_but_reads_unpromoted(tmp_path, ledger):
    staging = tmp_path / "s.yaml"
    record_adjudication(
        _payload(), staging_path=staging, promoted_path=tmp_path / "absent.yaml"
    )
    registry = load_registry(promoted_path=tmp_path / "absent.yaml", staging_path=staging)
    assert len(registry.entries) == 1
    assert registry.entries[0].promoted is False


def test_a_ledger_outage_is_reported_not_swallowed(tmp_path, monkeypatch):
    monkeypatch.setenv(db.ENV_CAPTURE_ENABLED, "0")
    out = record_adjudication(
        _payload(), staging_path=tmp_path / "s.yaml", promoted_path=tmp_path / "absent.yaml"
    )
    assert out["recorded"] and out["warnings"], (
        "an unrecorded ruling must not look identical to a recorded one"
    )
