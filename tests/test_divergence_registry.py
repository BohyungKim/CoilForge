"""Matching + merge semantics: scope isolation, the delta band, staging-wins, import boundary."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

yaml = pytest.importorskip("yaml")

from coilforge.review.divergence import (  # noqa: E402
    ANY_SIZE,
    annotate_known_divergences,
    coil_identity,
    divergence_key,
    load_registry,
)


def _write(path: Path, entries: list[dict]) -> Path:
    path.write_text(
        yaml.safe_dump({"version": 1, "divergences": entries}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _entry(**over):
    base = {
        "id": "KD-900", "coil_category": "HGRH", "product_family": "TERRA_V",
        "terra_variant": "TERRA_V", "unit_size_scope": ANY_SIZE, "slot": "slot.CD",
        "verdict": "checklist_wrong", "reason": "the sheet has no TERRA V branch",
        "evidence_refs": ["SOP:2024018#HGRH-TNVH"], "adjudicated_by": "John",
    }
    base.update(over)
    return base


def _review(coilforge=7.5, checklist=6.0, slot="slot.CD", tag="RHHGRC-1", verdict="mismatch"):
    return {
        "sheets": [
            {
                "tag": tag, "category": "HGRH",
                "comparisons": [
                    {"label": "CD", "slot": slot, "coilforge": coilforge,
                     "checklist": checklist, "verdict": verdict}
                ],
            }
        ]
    }


def _coils(label="TERRA V", size="072", tag="RHHGRC-1"):
    return [{"tag": tag, "coil_type": "HGRH", "product_label": label, "unit_size": size}]


def _row(review):
    return review["sheets"][0]["comparisons"][0]


# --------------------------------------------------------------------------- #
# identity + scope
# --------------------------------------------------------------------------- #
def test_terra_v_ruling_does_not_match_terra_h(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry()]),
        staging_path=tmp_path / "absent.yaml",
    )
    out = annotate_known_divergences(_review(), _coils(label="TERRA H"), registry=registry)
    assert "divergence" not in _row(out), (
        "a Terra V ruling silencing Terra H is the failure this identity exists to prevent"
    )


def test_terra_v_ruling_does_not_match_nova(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry()]),
        staging_path=tmp_path / "absent.yaml",
    )
    out = annotate_known_divergences(_review(), _coils(label="NOVA"), registry=registry)
    assert "divergence" not in _row(out)


def test_a_ruling_scoped_to_one_size_does_not_cover_another(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry(unit_size_scope="072")]),
        staging_path=tmp_path / "absent.yaml",
    )
    covered = annotate_known_divergences(_review(), _coils(size="072"), registry=registry)
    assert _row(covered)["divergence"]["id"] == "KD-900"
    other = annotate_known_divergences(_review(), _coils(size="024"), registry=registry)
    assert "divergence" not in _row(other)


def test_exact_size_ruling_wins_over_the_all_sizes_one(tmp_path):
    # The narrower declaration is the later, better-informed statement about that size.
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [
            _entry(id="KD-900", unit_size_scope=ANY_SIZE),
            _entry(id="KD-901", unit_size_scope="072", reason="size-specific ruling"),
        ]),
        staging_path=tmp_path / "absent.yaml",
    )
    out = annotate_known_divergences(_review(), _coils(size="072"), registry=registry)
    assert _row(out)["divergence"]["id"] == "KD-901"


def test_divergence_key_is_stable_and_case_insensitive():
    assert divergence_key("hgrh", "terra_v", "terra_v", "*", "slot.cd") == \
        divergence_key("HGRH", "TERRA_V", "TERRA_V", "*", "SLOT.CD")


def test_coil_identity_uses_the_split_terra_family():
    # Same resolver build_header_request uses, so the axis cannot drift from the engine.
    assert coil_identity({"coil_type": "HGRH", "product_label": "TERRA V",
                          "unit_size": "072"}) == ("HGRH", "TERRA_V", "TERRA_V", "072")


# --------------------------------------------------------------------------- #
# the delta band
# --------------------------------------------------------------------------- #
def test_inside_the_band_the_ruling_applies(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry(delta_band={"min": 1.0, "max": 2.0})]),
        staging_path=tmp_path / "absent.yaml",
    )
    out = annotate_known_divergences(_review(7.5, 6.0), _coils(), registry=registry)
    note = _row(out)["divergence"]
    assert note["delta"] == 1.5 and note["in_band"] and note["applies"]
    assert note["severity"] == "known_gap"


def test_outside_the_band_re_escalates_rather_than_staying_amber(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry(delta_band={"min": 1.0, "max": 2.0})]),
        staging_path=tmp_path / "absent.yaml",
    )
    out = annotate_known_divergences(_review(20.0, 6.0), _coils(), registry=registry)
    note = _row(out)["divergence"]
    assert not note["applies"] and note["severity"] == "re_escalated"
    assert "outside the adjudicated band" in note["note"]


def test_the_wrong_sign_re_escalates(tmp_path):
    # A signed band is what makes a sign flip escalate; an abs() band would suppress it.
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry(delta_band={"min": 1.0, "max": 2.0})]),
        staging_path=tmp_path / "absent.yaml",
    )
    out = annotate_known_divergences(_review(4.5, 6.0), _coils(), registry=registry)
    assert _row(out)["divergence"]["severity"] == "re_escalated"


def test_a_bandless_ruling_is_marked_unconditional_not_verified(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry()]),
        staging_path=tmp_path / "absent.yaml",
    )
    note = _row(annotate_known_divergences(_review(), _coils(), registry=registry))["divergence"]
    assert note["unconditional"] and note["applies"]
    assert "structural" in note["note"]


def test_an_expired_ruling_stops_suppressing(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry(expires_utc="2026-01-01")]),
        staging_path=tmp_path / "absent.yaml",
    )
    out = annotate_known_divergences(
        _review(), _coils(), registry=registry, now_utc="2026-08-05"
    )
    note = _row(out)["divergence"]
    assert note["expired"] and not note["applies"] and note["severity"] == "re_escalated"


# --------------------------------------------------------------------------- #
# severity routing
# --------------------------------------------------------------------------- #
def test_coilforge_wrong_stays_a_defect_and_is_not_dimmed(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry(verdict="coilforge_wrong")]),
        staging_path=tmp_path / "absent.yaml",
    )
    note = _row(annotate_known_divergences(_review(), _coils(), registry=registry))["divergence"]
    assert note["severity"] == "known_defect", (
        "a ruling that WE are wrong must not become amber — it is an open bug"
    )


def test_matched_and_overridden_rows_are_never_annotated(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry()]),
        staging_path=tmp_path / "absent.yaml",
    )
    for verdict in ("match", "overridden", "both_missing"):
        out = annotate_known_divergences(
            _review(verdict=verdict), _coils(), registry=registry
        )
        assert "divergence" not in _row(out), f"{verdict} is not an open question"


# --------------------------------------------------------------------------- #
# merge: staging wins, band conflicts are surfaced
# --------------------------------------------------------------------------- #
def test_staging_overrides_the_promoted_entry_for_the_same_key(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry(id="KD-001")]),
        staging_path=_write(tmp_path / "s.yaml", [_entry(id="KD-050", reason="re-ruled")]),
    )
    entry = registry.by_key[divergence_key("HGRH", "TERRA_V", "TERRA_V", ANY_SIZE, "slot.CD")]
    assert entry.id == "KD-050" and entry.promoted is False


def test_a_band_conflict_between_the_two_files_is_warned_not_silently_resolved(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml",
                             [_entry(id="KD-001", delta_band={"min": 0.0, "max": 1.0})]),
        staging_path=_write(tmp_path / "s.yaml",
                            [_entry(id="KD-050", delta_band={"min": 0.0, "max": 9.0})]),
    )
    assert any("different" in w and "delta band" in w for w in registry.warnings), (
        "the band decides suppression; a load-order-dependent band is silent corruption"
    )


def test_a_malformed_entry_is_skipped_with_a_warning_not_a_crash(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry(), {"id": "KD-BAD"}]),
        staging_path=tmp_path / "absent.yaml",
    )
    assert len(registry.entries) == 1
    assert any("KD-BAD" in w or "missing required field" in w for w in registry.warnings)


def test_registry_warnings_reach_the_review_summary(tmp_path):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry(), {"id": "KD-BAD"}]),
        staging_path=tmp_path / "absent.yaml",
    )
    out = annotate_known_divergences(_review(), _coils(), registry=registry)
    assert out["divergence_summary"]["registry_warnings"], (
        "a warning that only reaches a log is a warning nobody sees"
    )


def test_kill_switch_disables_annotation(tmp_path, monkeypatch):
    registry = load_registry(
        promoted_path=_write(tmp_path / "p.yaml", [_entry()]),
        staging_path=tmp_path / "absent.yaml",
    )
    monkeypatch.setenv("COILFORGE_DIVERGENCE", "0")
    out = annotate_known_divergences(_review(), _coils(), registry=registry)
    assert "divergence" not in _row(out)
    assert "divergence_summary" not in out


# --------------------------------------------------------------------------- #
# the import boundary (D5)
# --------------------------------------------------------------------------- #
def test_no_value_producing_module_imports_the_registry():
    """The registry must never reach a module that decides a drawn value.

    `coilforge.checklist` and `compatibility.mechanical_fit` are in the list alongside the
    obvious engine modules: both run their OWN `build_drawing_slots` + `prepopulate` pass,
    so a registry import there would let an adjudication feed back into the very column it
    is supposed to be judging.
    """
    forbidden = [
        "coilforge/services/header_prepopulate_engine.py",
        "coilforge/services/direct_coil_drawing_pipeline.py",
        "coilforge/compatibility/mechanical_fit.py",
    ]
    forbidden_dirs = ["coilforge/submittal", "coilforge/template_population", "coilforge/checklist"]
    src = ROOT / "src"
    targets = [src / f for f in forbidden]
    for d in forbidden_dirs:
        targets.extend((src / d).rglob("*.py"))
    offenders = [
        str(p.relative_to(src)) for p in targets
        if p.exists() and "review.divergence" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, f"these modules must not read the divergence registry: {offenders}"
