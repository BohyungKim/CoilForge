"""A coil with NO manual fill draws exactly what it drew before (the H4 guarantee).

``test_manual_fill.py::test_no_manual_fill_output_is_unchanged`` runs the same code twice
and compares the two runs, so it proves determinism and nothing else: a change that moves
every no-fill drawing passes it. This file pins the drawing against a recorded baseline.

What is pinned, per coil: ``template_id``, ``export_allowed``, every ``slot_values`` entry,
each Drawing Parameters row's value / mode / blocked_reason, and the SVG (by sha256 -- the
rest stays as readable JSON so a red run shows WHICH slot moved). Review metadata added to
a response is deliberately not pinned.

A change John has ruled on goes into ``RULED_DELTAS`` below, stated slot by slot. The
recording itself is regenerated only through the controlled manual workflow (John runs
``python tests/test_no_fill_derive_pinned.py``), which then empties ``RULED_DELTAS``.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402

from coilforge.workflows import submittal_to_drawing as std  # noqa: E402
from coilforge.workflows.submittal_to_drawing import derive_coil_template_drawing  # noqa: E402
from derive_roundtrip import spec_from_template_drawing  # noqa: E402

BASELINE = Path(__file__).resolve().parent / "fixtures" / "no_fill_derive_baseline.json"

# Specs shaped as analyze hands them to the browser (``panel`` included: the title block's
# connection size and "N Feed" text come from it, not from the geometry keys).
SPECS: dict[str, dict[str, Any]] = {
    "dx_nova_1hd": dict(
        coil_category="DX", coil_hand="LH", tag="CDXC-1", circuits=1, rows=4, feeds=6,
        finned_height=20.0, finned_length=40.0, suction_conn_size=1.125,
        product_type="NOVA", unit_size="B20",
        panel={"conn_size": 1.125, "feeds": 6, "circuits": 1},
    ),
    "dx_terra_h_paired_with_hgrh": dict(
        coil_category="DX", coil_hand="RH", tag="CDXC-1", circuits=2, rows=4, feeds=8,
        finned_height=24.0, finned_length=36.0, suction_conn_size=1.125,
        product_type="TERRA H", unit_size="024",
        sibling_coils=[{"tag": "RHHGRC-1", "conn_size": 0.875}],
        panel={"conn_size": 1.125, "feeds": 8, "circuits": 2},
    ),
    "hgrh_terra_v_stated_qty": dict(
        coil_category="HGRH", coil_hand="RH", tag="RHHGRC-1", circuits=4, rows=2, feeds=4,
        finned_height=24, finned_length=15, return_conn_size=0.5,
        product_type="TERRA V", unit_size="012", stated_qty_conn_per_header=2,
        panel={"conn_size": 0.5, "feeds": 4, "circuits": 4},
    ),
    "hgrh_nova": dict(
        coil_category="HGRH", coil_hand="LH", tag="RHHGRC-1", circuits=1, rows=2, feeds=4,
        finned_height=20.0, finned_length=40.0, return_conn_size=0.875,
        product_type="NOVA", unit_size="B20",
        panel={"conn_size": 0.875, "feeds": 4, "circuits": 1},
    ),
    # John 2026-10-02: an HGRH with no connection size leaves S blank instead of printing
    # the DX-shaped even spacing. This is the ONE case that ruling moves.
    "hgrh_nova_no_conn": dict(
        coil_category="HGRH", coil_hand="LH", tag="RHHGRC-1", circuits=1, rows=2, feeds=4,
        finned_height=20.0, finned_length=40.0,
        product_type="NOVA", unit_size="B20",
        panel={"feeds": 4, "circuits": 1},
    ),
    "hwc_nova_extracted_conn": dict(
        coil_category="HWC", coil_hand="LH", tag="HHWC-1", circuits=1, rows=1, feeds=3,
        finned_height=30.0, finned_length=60.0, suction_conn_size=1.5,
        product_type="NOVA", unit_size="C24",
        water_conn_extracted={"inlet": 1.5, "outlet": 1.5},
        panel={"conn_size": 1.5, "feeds": 3, "circuits": 1},
    ),
    "cwc_terra_h": dict(
        coil_category="CWC", coil_hand="RH", tag="CCWC-1", circuits=1, rows=6, feeds=10,
        finned_height=18.0, finned_length=36.0, suction_conn_size=2.0,
        product_type="TERRA H", unit_size="024",
        water_conn_extracted={"inlet": 2.0, "outlet": 2.0},
        panel={"conn_size": 2.0, "feeds": 10, "circuits": 1},
    ),
    "dx_ventum_plus": dict(
        coil_category="DX", coil_hand="LH", tag="CDXC-1", circuits=1, rows=4, feeds=6,
        finned_height=24.0, finned_length=40.0, suction_conn_size=1.125,
        product_type="VENTUM_PLUS", unit_size="V30",
        panel={"conn_size": 1.125, "feeds": 6, "circuits": 1},
    ),
    "dx_no_product": dict(coil_category="DX", tag="CDXC-1", circuits=1),
}


def _snapshot(td: dict[str, Any]) -> dict[str, Any]:
    rows = (td.get("drawing_parameter_set") or {}).get("parameters") or {}
    return json.loads(
        json.dumps(
            {
                "template_id": td.get("template_id"),
                "export_allowed": td.get("export_allowed"),
                "slot_values": td.get("slot_values") or {},
                "panel_rows": {
                    key: [row.get("value"), row.get("mode"), row.get("blocked_reason")]
                    for key, row in rows.items()
                },
                "svg_sha256": hashlib.sha256((td.get("svg") or "").encode("utf-8")).hexdigest(),
            },
            sort_keys=True,
            default=str,
        )
    )


def _analyze_dx1() -> dict[str, Any]:
    from test_pdf_to_template_drawing import DX1_TEXT, _make_text_pdf

    std.clear_pdf_to_drawing_workflow_cache()
    try:
        return std.run_pdf_to_drawing_workflow(_make_text_pdf(DX1_TEXT.splitlines()))[
            "template_drawing"
        ]
    finally:
        std.clear_pdf_to_drawing_workflow_cache()


def _current() -> dict[str, Any]:
    snaps = {name: _snapshot(derive_coil_template_drawing(dict(spec))) for name, spec in SPECS.items()}
    analyzed = _analyze_dx1()
    # The analyze path (its panel rides elsewhere in the workflow payload, so only the
    # drawing is pinned here), and the first no-fill derive the browser sends after it.
    snaps["analyze_dx1"] = _snapshot(analyzed)
    snaps["analyze_dx1_then_no_fill_derive"] = _snapshot(
        derive_coil_template_drawing(spec_from_template_drawing(analyzed))
    )
    return snaps


@pytest.fixture(scope="module")
def current() -> dict[str, Any]:
    return _current()


@pytest.fixture(scope="module")
def baseline() -> dict[str, Any]:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def test_the_baseline_covers_exactly_the_pinned_cases(current, baseline):
    assert set(current) == set(baseline)


# Changes John ruled on AFTER the baseline was recorded, stated exactly rather than folded
# into a regenerated file: a case listed here must differ from its recording in precisely
# these slots and panel rows (and therefore its SVG), and match it everywhere else.
RULED_DELTAS: dict[str, dict[str, Any]] = {
    # John 2026-10-02: an HGRH with no connection size leaves supply S blank (and says why)
    # instead of printing the DX even spacing k*CD/(n+1) = 1.875 as a "default".
    "hgrh_nova_no_conn": {
        "slots_removed": {"slot.S1"},
        "rows_now_blocked": {"S": "HGRH supply S is placed from the connection size and CD"},
    },
}


@pytest.mark.parametrize("name", [*SPECS, "analyze_dx1", "analyze_dx1_then_no_fill_derive"])
def test_no_fill_drawing_matches_the_recorded_baseline(name, current, baseline):
    if name not in RULED_DELTAS:
        assert current[name] == baseline[name]
        return
    delta, now, then = RULED_DELTAS[name], current[name], baseline[name]
    assert set(then["slot_values"]) - set(now["slot_values"]) == delta["slots_removed"]
    assert {
        k: v for k, v in then["slot_values"].items() if k not in delta["slots_removed"]
    } == now["slot_values"]
    for key, reason_start in delta["rows_now_blocked"].items():
        value, mode, reason = now["panel_rows"][key]
        assert (value, mode) == (None, "blocked") and reason.startswith(reason_start)
    unchanged_rows = {k: v for k, v in then["panel_rows"].items() if k not in delta["rows_now_blocked"]}
    assert unchanged_rows == {k: now["panel_rows"][k] for k in unchanged_rows}
    assert now["template_id"] == then["template_id"]
    assert now["svg_sha256"] != then["svg_sha256"]


def test_every_pinned_case_actually_draws(current):
    """A baseline of empty SVGs would pin nothing."""
    empty = hashlib.sha256(b"").hexdigest()
    assert not [name for name, snap in current.items() if snap["svg_sha256"] == empty]


if __name__ == "__main__":
    BASELINE.write_text(
        json.dumps(_current(), indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {BASELINE}")
