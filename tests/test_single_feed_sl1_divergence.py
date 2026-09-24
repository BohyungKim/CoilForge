"""The HGRH supply SL1 disagreement, before and after the 2026-09-22 template refresh.

Until 2026-09-22 CoilForge drew 6 where checklist HGRH!C58 computed 3 for a single feed
(John 2026-08-06), and KD-006..009 re-labelled that row amber with a delta_band of exactly
3 so multi-feed rows could never be silenced by a ruling made about a different case.

The refreshed template dropped C58's single-feed arm -- SL1 is `6 + D/2 - S1` for every
line and feed count -- and John ruled the checklist wins, so CoilForge computes the same
formula and KD-006..009 were RETIRED. What this file pins now:

* the comparator still calls a real disagreement a mismatch (unchanged);
* no SL1 ruling exists for the Nova / Ventum H / Terra H / Ventum+ lines any more -- a
  hypothetical 6-vs-3 row stays RED, because nothing has been adjudicated for it;
* Terra V's SL1 is no longer covered: KD-028 went with KD-001 on 2026-09-23 when Terra V
  HGRH CD began following the sheet, so both sides now agree and a gap would be RED;
* the delta_band mechanism itself still re-escalates, exercised on a banded ruling that
  still exists (KD-010, Omnia TF, band exactly -0.375).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

pytest.importorskip("yaml")

from coilforge.checklist.compare import _match  # noqa: E402
from coilforge.review.divergence import (  # noqa: E402
    annotate_known_divergences,
    load_registry,
)


def _review(coilforge, checklist, tag="RHHGRC-1", category="HGRH", slot="slot.SL1", label="SL1"):
    return {
        "sheets": [
            {
                "tag": tag,
                "category": category,
                "comparisons": [
                    {
                        "slot": slot,
                        "label": label,
                        "coilforge": coilforge,
                        "checklist": checklist,
                        "verdict": _match(coilforge, checklist),
                    }
                ],
            }
        ]
    }


def _identities(family, variant="-", size="V20"):
    return {"RHHGRC-1": ("HGRH", family, variant, size)}


def test_single_feed_sl1_is_reported_as_a_mismatch_not_hidden():
    """The comparator itself must still call it a mismatch. 6 vs 3 is a real
    disagreement; the registry re-labels it downstream, it does not erase it."""
    assert _match(6, 3) == "mismatch"
    review = _review(6, 3)
    assert review["sheets"][0]["comparisons"][0]["verdict"] == "mismatch"


@pytest.mark.parametrize(
    "family, variant",
    [
        ("NOVA", "-"),
        ("VENTUM_H", "-"),
        ("TERRA_H", "TERRA_H_C"),
        ("VENTUM_PLUS", "-"),
    ],
)
def test_the_retired_single_feed_ruling_no_longer_labels_anything(family, variant):
    """KD-006..009 are gone (2026-09-22): both sides now compute `6 + D/2 - S1`, so a
    6-vs-3 row can only mean a genuine regression and must stay RED, not amber."""
    review = annotate_known_divergences(
        _review(6, 3),
        identities=_identities(family, variant),
        registry=load_registry(),
    )
    row = review["sheets"][0]["comparisons"][0]
    note = row.get("divergence")
    assert note is None or note["applies"] is False, f"{family}: a retired SL1 ruling still applies"
    assert row["verdict"] == "mismatch"


def test_terra_v_sl1_gap_is_no_longer_ruled_away():
    """KD-028 (Terra V SL1) stood or fell with KD-001 (CD). Both retired 2026-09-23: John
    ruled Terra V HGRH CD is always the checklist's, so SL1 = 6 + D/2 - S1 agrees on both
    sides. The old live-fill gap (7.6875 vs 7.3125) must now read RED if it ever returns."""
    review = annotate_known_divergences(
        _review(7.6875, 7.3125),                     # the 2026-09-22 RHHGRC-1 TV072 gap
        identities={"RHHGRC-1": ("HGRH", "TERRA_V", "TERRA_V", "072")},
        registry=load_registry(),
    )
    row = review["sheets"][0]["comparisons"][0]
    note = row.get("divergence")
    assert note is None or note["applies"] is False, "a retired Terra V SL1 ruling still applies"
    assert row["verdict"] == "mismatch"


def test_a_delta_outside_the_band_re_escalates():
    """The delta_band mechanism, exercised on a banded ruling that still exists: KD-010
    (Omnia DX TF, sheet 1.0 vs CoilForge 0.625, band exactly -0.375). Inside the band the
    row is amber; any other magnitude is a different question and re-escalates."""
    inside = annotate_known_divergences(
        _review(0.625, 1.0, tag="CDXC-1", category="DX", slot="slot.TF", label="TF"),
        identities={"CDXC-1": ("DX", "OMNIA", "-", "OW060")},
        registry=load_registry(),
    )
    note = inside["sheets"][0]["comparisons"][0].get("divergence")
    assert note is not None and note["applies"] is True and note["id"] == "KD-010"

    outside = annotate_known_divergences(
        _review(0.625, 1.5, tag="CDXC-1", category="DX", slot="slot.TF", label="TF"),
        identities={"CDXC-1": ("DX", "OMNIA", "-", "OW060")},
        registry=load_registry(),
    )
    note = outside["sheets"][0]["comparisons"][0].get("divergence")
    assert note is not None
    assert note["applies"] is False
    assert note["severity"] == "re_escalated"
