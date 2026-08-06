"""Eyeball gate for the parametric drawing engine (Phase 1 / 1.5 / 2).

Renders DX coils from synthetic / sanitized dimensions (no customer data) to
``build/schematic_preview/``. Phase 2 acceptance: the sanitized real DX in BOTH views
(front + header/side) for BOTH hands (LH/RH) — the side view shows header pipes /
connections to scale, LH and RH are clean mirror images, the front header-flange side
flips, and the Phase 1.5 dimensioning still holds.

    python scripts/preview_schematic.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from coilforge.drawing.backends.svg import DEFAULT_CANVAS_H, DEFAULT_CANVAS_W, PAD_PX
from coilforge.drawing.schematic_layout import build_dx_views
from coilforge.drawing.schematic_model import CoilGeometry
from coilforge.drawing.schematic_renderer import render_scale_schematic
from coilforge.services.direct_coil_drawing_pipeline import build_header_request
from coilforge.services.distributor_slots import distributor_drawing_slots
from coilforge.services.header_prepopulate_engine import prepopulate

# Synthetic front-only contrast cases (proportion sanity).
FRONT_CASES: dict[str, dict[str, float]] = {
    "tall_narrow": {
        "slot.FL": 18.0, "slot.FH": 60.0, "slot.CL": 24.0, "slot.CH": 66.0,
        "slot.TF": 3.0, "slot.BF": 3.0, "slot.HF": 3.0, "slot.RF": 3.0,
    },
    "short_wide": {
        "slot.FL": 120.0, "slot.FH": 18.0, "slot.CL": 126.0, "slot.CH": 24.0,
        "slot.TF": 3.0, "slot.BF": 3.0, "slot.HF": 3.0, "slot.RF": 3.0,
    },
}

# The acceptance case: a real small single-circuit DX coil (sanitized EZC-0001 values).
SANITIZED_DX: dict[str, float] = {
    "slot.FH": 12.0, "slot.FL": 15.0, "slot.CH": 13.25, "slot.CL": 18.0,
    "slot.TF": 0.63, "slot.BF": 0.63, "slot.HF": 1.5, "slot.RF": 1.5,
    "slot.CD": 5.5, "slot.ROWS": 4, "slot.HDx1": 4.5, "slot.HD2": 3.5,
    "slot.I1": 3.0, "slot.O2": 2.0, "slot.S1": 2.75, "slot.R2": 0.63,
    "slot.SL2": 8.0, "slot.RETURN_CONN_SIZE": 0.625,
}

# Phase 3 acceptance: a SANITIZED 3-circuit DX (EZC-0007 structure — constant I/O, increasing
# S/R per circuit; values altered so no raw customer numbers ship).
MULTI_CIRCUIT_DX: dict[str, float] = {
    "slot.FH": 22.0, "slot.FL": 26.0, "slot.CH": 24.0, "slot.CL": 28.0,
    "slot.TF": 1.0, "slot.BF": 1.0, "slot.HF": 1.5, "slot.RF": 1.5,
    "slot.CD": 8.0, "slot.ROWS": 5,
    "slot.HDx1": 4.5, "slot.I1": 3.0, "slot.S1": 1.5,
    "slot.HD2": 3.5, "slot.O2": 2.0, "slot.R2": 1.0, "slot.SL2": 6.0,
    "slot.HDx3": 4.5, "slot.I3": 3.0, "slot.S3": 4.0,
    "slot.HD4": 3.5, "slot.O4": 2.0, "slot.R4": 3.5, "slot.SL4": 6.0,
    "slot.HDx5": 4.5, "slot.I5": 3.0, "slot.S5": 6.5,
    "slot.HD6": 3.5, "slot.O6": 2.0, "slot.R6": 6.0, "slot.SL6": 6.0,
    "slot.RETURN_CONN_SIZE": 1.0,
}


def _fill_percent(view, ppi: float) -> float:
    avail_w, avail_h = DEFAULT_CANVAS_W - 2 * PAD_PX, DEFAULT_CANVAS_H - 2 * PAD_PX
    return max(view.extent_w * ppi / avail_w, view.extent_h * ppi / avail_h) * 100.0


# Phase 4b: source the V3 distributor slots through the REAL 4a path (distributor_drawing_slots)
# from each fixture's sanitized display block — Case/#3 is read for reference only, never committed.
SANITIZED_DIR = REPO_ROOT / "examples" / "sanitized"


def _distributor_inputs(fixture: str, supply_ids: list[int]) -> tuple[dict, dict, list[str]]:
    """Return (HIGH dist slots, dist_review, dist_blocked) sourced from a sanitized DX fixture's
    display block via the Phase-4a gate — exactly what the engine consumes in production."""
    fx = json.loads((SANITIZED_DIR / fixture).read_text(encoding="utf-8"))
    display = {k: fx.get(k) for k in ("drawing_callouts", "distributors_display", "airflow_direction")}
    engine = prepopulate(
        build_header_request(
            coil_type="DX", product_type="NOVA", unit_size="B20",
            rows=4, feeds=2, circuits=len(supply_ids), suction_conn_size=0.625, handing="LH",
        )
    )
    dist = distributor_drawing_slots(engine_response=engine, supply_ids=supply_ids, display=display)
    high = dist.gated_slot_values()  # AIRFLOW + confirmed DistExtension{id}
    review = {gs.slot: gs.value for gs in dist.review.values()}  # DistModel/DistOD (flagged)
    blocked = [gs.slot.replace("slot.", "") for gs in dist.blocked.values()]
    return high, review, blocked


def main() -> int:
    out_dir = REPO_ROOT / "build" / "schematic_preview"
    out_dir.mkdir(parents=True, exist_ok=True)

    aspects: dict[str, float] = {}
    for name, slot_values in FRONT_CASES.items():
        result = render_scale_schematic(slot_values, coil_category="DX", coil_hand="LH", header_type="Header 1")
        path = out_dir / f"{name}.svg"
        path.write_text(result.svg, encoding="utf-8")
        w, h = result.metadata["casing_px"][2], result.metadata["casing_px"][3]
        aspects[name] = w / h
        print(f"{name:22s} -> {path}  aspect(w/h)={w / h:.2f}")

    # Sanitized DX: front + side, LH + RH (the Phase 2 acceptance set).
    for hand in ("lh", "rh"):
        result = render_scale_schematic(
            SANITIZED_DX, coil_category="DX", coil_hand=hand.upper(), header_type="Header 1"
        )
        views = build_dx_views(
            CoilGeometry.from_slot_values(
                SANITIZED_DX, coil_category="DX", coil_hand=hand.upper(),
                header_type="Header 1", special_feature=None,
            )
        )
        for view_name, svg in (("front", result.svg), ("side", result.side_svg)):
            path = out_dir / f"sanitized_dx_{view_name}_{hand}.svg"
            path.write_text(svg, encoding="utf-8")
            ppi = result.metadata[f"{view_name}_px_per_inch"]
            print(
                f"sanitized_dx_{view_name}_{hand:2s}   -> {path}  "
                f"px_per_inch={ppi:.2f}  canvas_fill={_fill_percent(views[view_name], ppi):.0f}%"
            )

    # Phase 3: the SANITIZED multi-circuit DX side view, LH + RH (the spread/end view).
    for hand in ("lh", "rh"):
        result = render_scale_schematic(
            MULTI_CIRCUIT_DX, coil_category="DX", coil_hand=hand.upper(), header_type="Header 3"
        )
        views = build_dx_views(
            CoilGeometry.from_slot_values(
                MULTI_CIRCUIT_DX, coil_category="DX", coil_hand=hand.upper(),
                header_type="Header 3", special_feature=None,
            )
        )
        path = out_dir / f"multi_circuit_dx_side_{hand}.svg"
        path.write_text(result.side_svg, encoding="utf-8")
        ppi = result.metadata["side_px_per_inch"]
        print(
            f"multi_circuit_dx_side_{hand:2s} -> {path}  "
            f"px_per_inch={ppi:.2f}  canvas_fill={_fill_percent(views['side'], ppi):.0f}%"
        )

    # Phase 4b: the V3 distributor plan/top view, LH + RH, single (EZC-0001) + multi (EZC-0007).
    plan_cases = [
        ("single", SANITIZED_DX, "Header 1", "dx_header1_ezc0001_default.json", [1]),
        ("multi", MULTI_CIRCUIT_DX, "Header 3", "dx_header3_ezc0007_default.json", [1, 3, 5]),
    ]
    for name, geom_slots, header_type, fixture, supply_ids in plan_cases:
        high, review, blocked = _distributor_inputs(fixture, supply_ids)
        slot_values = {**geom_slots, **high}
        for hand in ("lh", "rh"):
            result = render_scale_schematic(
                slot_values, coil_category="DX", coil_hand=hand.upper(), header_type=header_type,
                dist_review=review, dist_blocked=blocked,
            )
            path = out_dir / f"plan_dx_{name}_{hand}.svg"
            path.write_text(result.plan_svg, encoding="utf-8")
            ppi = result.metadata["plan_px_per_inch"]
            print(f"plan_dx_{name}_{hand:2s}      -> {path}  px_per_inch={ppi:.2f}")

    verdict = "VISIBLY DIFFERENT" if aspects["tall_narrow"] < 1.0 < aspects["short_wide"] else "TOO SIMILAR — FAILED"
    print(f"\nProportion check: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
