"""The single-feed HGRH SL1 divergence must stay VISIBLE.

CoilForge now draws 6 where checklist HGRH!C58 computes 3 (John 2026-08-06). That
disagreement is real and the compare must keep reporting it -- the registry only re-labels
the row from red to amber with the reasoning attached. Suppressing it inside `_match`, or
writing 6 into the sheet through the overrides channel, would both hide a divergence the
engineer is entitled to see (and the second would forge provenance: that channel means
"a human typed this on the drawing", and no human did).

The `delta_band` is the load-bearing part. The registry identity has no feed-count axis,
so a band-less ruling would silence SL1 for EVERY Nova/Terra H/Ventum+ HGRH coil --
including multi-feed ones, where CoilForge and the sheet agree today and any future
disagreement would be a genuine regression.
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


def _review(coilforge, checklist, tag="RHHGRC-1"):
    return {
        "sheets": [
            {
                "tag": tag,
                "category": "HGRH",
                "comparisons": [
                    {
                        "slot": "slot.SL1",
                        "label": "SL1",
                        "coilforge": coilforge,
                        "checklist": checklist,
                        "verdict": _match(coilforge, checklist),
                    }
                ],
            }
        ]
    }


def _identities(family, variant="-"):
    return {"RHHGRC-1": ("HGRH", family, variant, "V20")}


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
def test_every_ruled_line_is_annotated_amber_with_its_reasoning(family, variant):
    review = annotate_known_divergences(
        _review(6, 3),
        identities=_identities(family, variant),
        registry=load_registry(),
    )
    row = review["sheets"][0]["comparisons"][0]
    note = row.get("divergence")
    assert note is not None, f"{family} SL1 divergence was never adjudicated"
    assert note["applies"] is True
    assert note["verdict"] == "checklist_wrong"
    assert note["severity"] == "known_gap"          # amber, not red
    assert "SL1" in note["reason"] or "SL1=6" in note["reason"]
    assert row["verdict"] == "mismatch"             # the verdict itself is untouched


def test_terra_v_sl1_is_not_covered_by_the_ruling():
    """Terra V has no C26 add-headers branch and its SL1 (5) did not move, so nothing was
    ruled on. Registering it would silence a genuine future disagreement."""
    review = annotate_known_divergences(
        _review(5, 3),
        identities={"RHHGRC-1": ("HGRH", "TERRA_V", "TERRA_V", "012")},
        registry=load_registry(),
    )
    row = review["sheets"][0]["comparisons"][0]
    note = row.get("divergence")
    assert note is None or note["applies"] is False


def test_a_delta_outside_the_band_re_escalates():
    """The band pins the ruling to the single-feed case (6 - 3 = 3). A multi-feed SL1
    that ever disagreed would land at a different delta and must NOT be silenced by a
    ruling made about a different configuration."""
    review = annotate_known_divergences(
        _review(5.6875, 3),                          # multi-feed CoilForge value vs 3
        identities=_identities("VENTUM_PLUS"),
        registry=load_registry(),
    )
    note = review["sheets"][0]["comparisons"][0].get("divergence")
    assert note is not None
    assert note["applies"] is False
    assert note["severity"] == "re_escalated"
