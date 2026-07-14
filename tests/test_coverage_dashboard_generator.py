"""The coverage-dashboard generator must reflect the LIVE catalog, not a snapshot.

These tests pin the coverage model against the confirmed MVP taxonomy + the
2026-07-14 Ventum+ DX-only not-registered gate, and assert the built-in drift
guard (encoded taxonomy == live SHARED buckets). If a bucket is seeded/removed or
the taxonomy changes, these fail loudly instead of the dashboard silently drifting.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")  # catalog import chain is light, but keep parity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_coverage_dashboard as gen  # noqa: E402


def test_taxonomy_matches_live_shared_catalog() -> None:
    # The encoded MVP taxonomy must equal the live SHARED buckets exactly — the
    # generator's core correctness invariant (and the --check CI guard).
    assert gen.check_taxonomy_matches_shared() == []


def test_shared_all_seeded_22() -> None:
    s = gen.build_coverage_model()["shared"]["summary"]
    assert s["total"] == 22
    assert s["seeded"] == 22  # every shared bucket is currently a seeded review aid
    assert s["blocked"] == 0 and s["fallback"] == 0


def test_ventum_plus_gaps_split_dx_blocked_vs_nondx_fallback() -> None:
    v = gen.build_coverage_model()["ventum_plus"]["summary"]
    assert v["total"] == 22  # same taxonomy space as shared
    assert v["seeded"] == 11  # DX 5 + HGRH 3 + HWC 2 + CWC 1
    # Un-seeded DX (LH-H4, RH-H3, RH-H4, LH-HGBP, RH-HGBP) -> not registered (R-032 UP).
    assert v["blocked"] == 5
    # Un-seeded non-DX (HGRH LH-H2/LH-H3/RH-H3/LH-H4/RH-H4, CWC RH) -> shared fallback.
    assert v["fallback"] == 6
    assert v["seeded"] + v["blocked"] + v["fallback"] == v["total"]


def test_all_ventum_plus_blocked_cells_are_dx() -> None:
    cells = gen.build_coverage_model()["ventum_plus"]["cells"]
    blocked = [c for c in cells if c.gap_kind == gen.GAP_BLOCKED]
    assert blocked, "expected some blocked Ventum+ DX cells"
    assert all(c.category == "DX" for c in blocked)  # DX-only gate
    fallback = [c for c in cells if c.gap_kind == gen.GAP_FALLBACK]
    assert all(c.category != "DX" for c in fallback)  # non-DX only


def test_seeded_cells_carry_provenance() -> None:
    cells = gen.build_coverage_model()["ventum_plus"]["cells"]
    seeded = [c for c in cells if c.seeded]
    assert len(seeded) == 11
    # Each seeded dedicated cell resolves to a real template + VPLUS provenance token.
    assert all(c.template_id and c.source_case_id for c in seeded)


def test_render_html_is_self_contained_and_marks_gaps() -> None:
    model = gen.build_coverage_model()
    doc = gen.render_html(model, generated_on="2026-07-14")
    assert doc.startswith("<!DOCTYPE html>")
    assert "http" not in doc.split("<title>")[0]  # no external head assets before title
    for marker in ("Template Coverage", "not registered", "shared fallback",
                   "Ventum+ DX not registered", "R-032"):
        assert marker in doc, marker


def test_check_mode_writes_nothing(tmp_path) -> None:
    out = tmp_path / "should_not_exist.html"
    rc = gen.main(["--check", "--out", str(out)])
    assert rc == 0
    assert not out.exists()


def test_generate_writes_html(tmp_path) -> None:
    out = tmp_path / "coverage.html"
    rc = gen.main(["--out", str(out)])
    assert rc == 0
    assert out.exists() and out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
