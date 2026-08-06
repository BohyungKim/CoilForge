"""Phase 4 — build_ambient_comparison pairing, ranges, and loud unmatched coils."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.ambient.mapping import build_ambient_comparison
from coilforge.ambient.pdf_intake import _parse_report_page
from tests.test_ambient_pdf_intake import _DX_TEXT, _CONDENSING_TEXT


def _dx(tag="CDXC-1"):
    return _parse_report_page(_DX_TEXT.replace("CDXC-1", tag), page_number=1, source_id="B")


def _cond(tag="RHHGRC-1"):
    return _parse_report_page(_CONDENSING_TEXT.replace("RHHGRC-1", tag), page_number=1, source_id="B")


def test_self_compare_has_no_mismatches():
    b = [_dx(), _cond()]
    a = [_dx(), _cond()]
    result = build_ambient_comparison(b, a)
    assert result.mismatch_total == 0
    assert not result.not_compared
    # Coil Volume row present and matches (identical geometry).
    dx = next(c for c in result.coils if c.tag == "CDXC-1")
    vol = next(r for r in dx.rows if r.label == "Coil Volume")
    assert vol.verdict == "match"
    assert vol.baseline == vol.ambient


def test_capacity_mismatch_surfaces():
    b = [_dx()]
    ambient_text = _DX_TEXT.replace("171514 Btu/hr", "210000 Btu/hr")  # +22%
    a = [_parse_report_page(ambient_text, page_number=1, source_id="A")]
    result = build_ambient_comparison(b, a)
    cap = next(r for r in result.coils[0].rows if r.label == "Capacity")
    assert cap.verdict == "mismatch"


def test_range_rows_cannot_evaluate_without_provider():
    result = build_ambient_comparison([_dx()], [_dx()])
    rows = result.coils[0].rows
    cap_range = next(r for r in rows if r.label == "Capacity Range")
    vol_range = next(r for r in rows if r.label == "Coil Volume Range")
    assert cap_range.verdict == "cannot_evaluate"
    assert vol_range.verdict == "cannot_evaluate"
    assert "pending" in (cap_range.note or "")


def test_range_provider_bands_are_applied():
    def provider(kind, baseline, ambient):
        # Ambient DX capacity is 171.514 MBH; a band that contains it -> match.
        return (150.0, 200.0) if kind == "capacity" else None

    result = build_ambient_comparison([_dx()], [_dx()], range_provider=provider)
    cap_range = next(r for r in result.coils[0].rows if r.label == "Capacity Range")
    assert cap_range.verdict == "match"

    def tight(kind, baseline, ambient):
        return (10.0, 20.0) if kind == "capacity" else None

    r2 = build_ambient_comparison([_dx()], [_dx()], range_provider=tight)
    cap_range2 = next(r for r in r2.coils[0].rows if r.label == "Capacity Range")
    assert cap_range2.verdict == "mismatch"


def test_unmatched_coils_are_loud():
    # 4 baseline coils, 2 Ambient -> 2 not_compared, never silently dropped.
    baseline = [_dx("CDXC-1"), _dx("CDXC-2"), _cond("RHHGRC-1"), _cond("RHHGRC-2")]
    ambient = [_dx("CDXC-1"), _cond("RHHGRC-1")]
    result = build_ambient_comparison(baseline, ambient)
    assert set(result.not_compared) == {"CDXC-2", "RHHGRC-2"}
    for c in result.coils:
        if c.tag in ("CDXC-2", "RHHGRC-2"):
            assert c.not_compared_reason


def test_ambient_only_coil_is_loud():
    result = build_ambient_comparison([_dx("CDXC-1")], [_dx("CDXC-1"), _cond("RHHGRC-9")])
    orphan = next(c for c in result.coils if c.tag == "RHHGRC-9")
    assert orphan.not_compared_reason
    assert "no baseline" in orphan.not_compared_reason


def test_safety_flags():
    result = build_ambient_comparison([_dx()], [_dx()])
    assert result.export_allowed is False
    assert result.production_drawing_approval_claimed is False
    assert result.review_required is True
    d = result.as_dict()
    assert d["export_allowed"] is False
