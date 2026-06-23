"""R-090 copper-strap rule: deterministic straps-per-header by coil type.

John, 2026-06-23: a DX coil needs ONE copper strap per header; an HG (HGRH)
coil needs TWO copper straps per header. The count is therefore
``header_count * multiplier(coil_type)``. CWC/HWC have no confirmed multiplier,
so they route to the blocked bucket (never invented). Written before the engine
change (TDD).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.schemas.header_prepopulate import (  # noqa: E402
    Confidence,
    CoilType,
    HeaderPrepopulateRequest,
    ProductFamily,
)
from coilforge.services.header_prepopulate_engine import prepopulate  # noqa: E402

_FIELD = "copper_straps_required"


def _req(coil: CoilType, **kw) -> HeaderPrepopulateRequest:
    # NOVA/B20 is a valid (product_family, unit_size) pair per R-076; R-090 is
    # product-family-agnostic so the family only needs to pass the size gate.
    return HeaderPrepopulateRequest(
        type_of_coil=coil, product_type=ProductFamily.NOVA, unit_size="B20", **kw
    )


def test_dx_one_strap_per_header() -> None:
    for header_count, expected in [(1, 1), (2, 2), (3, 3), (4, 4)]:
        resp = prepopulate(_req(CoilType.DX, header_count=header_count))
        assert _FIELD in resp.values, f"DX {header_count}HD should auto-populate"
        result = resp.values[_FIELD]
        assert result.value == expected
        assert result.confidence == Confidence.HIGH
        assert result.evidence_refs  # provenance required


def test_hgrh_two_straps_per_header() -> None:
    for header_count, expected in [(1, 2), (2, 4), (3, 6), (4, 8)]:
        resp = prepopulate(_req(CoilType.HGRH, header_count=header_count))
        assert _FIELD in resp.values, f"HGRH {header_count}HD should auto-populate"
        result = resp.values[_FIELD]
        assert result.value == expected
        assert result.confidence == Confidence.HIGH


def test_cwc_hwc_blocked_no_confirmed_multiplier() -> None:
    for coil in (CoilType.CWC, CoilType.HWC):
        resp = prepopulate(_req(coil, header_count=2))
        assert _FIELD in resp.blocked, f"{coil.value} multiplier is unconfirmed"
        result = resp.blocked[_FIELD]
        assert result.value is None
        assert result.review_required is True
        assert result.blocked_reason
        assert _FIELD not in resp.values


def test_missing_header_count_reports_missing_input() -> None:
    resp = prepopulate(_req(CoilType.DX))  # no header_count
    assert _FIELD not in resp.values
    assert _FIELD not in resp.suggestions
    assert "header_count" in resp.missing_inputs
