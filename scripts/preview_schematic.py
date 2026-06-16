"""Eyeball gate for the parametric drawing engine (Phase 1 / 1.5).

Renders contrasting DX coils from synthetic / sanitized dimensions (no customer data) to
``build/schematic_preview/`` and prints each drawing's scale + canvas fill. Required by
eye (Phase 1.5): flange offsets legible (leaders, not arrowhead clusters); no overlapping
labels; the sanitized DX fills the canvas and reads cleanly.

    python scripts/preview_schematic.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from coilforge.drawing.backends.svg import DEFAULT_CANVAS_H, DEFAULT_CANVAS_W, PAD_PX
from coilforge.drawing.schematic_layout import layout_dx_front_view
from coilforge.drawing.schematic_model import CoilGeometry
from coilforge.drawing.schematic_renderer import render_scale_schematic

# Synthetic / sanitized dimensions only — never real customer data.
CASES: dict[str, dict[str, float]] = {
    "tall_narrow": {
        "slot.FL": 18.0, "slot.FH": 60.0, "slot.CL": 24.0, "slot.CH": 66.0,
        "slot.TF": 3.0, "slot.BF": 3.0, "slot.HF": 3.0, "slot.RF": 3.0,
    },
    "short_wide": {
        "slot.FL": 120.0, "slot.FH": 18.0, "slot.CL": 126.0, "slot.CH": 24.0,
        "slot.TF": 3.0, "slot.BF": 3.0, "slot.HF": 3.0, "slot.RF": 3.0,
    },
    # The acceptance case: a real small DX coil with sub-1" flanges (must read cleanly).
    "sanitized_dx": {
        "slot.FH": 12.0, "slot.FL": 15.0, "slot.CH": 13.25, "slot.CL": 18.0,
        "slot.TF": 0.63, "slot.BF": 0.63, "slot.HF": 1.5, "slot.RF": 1.5,
    },
}


def _fill_percent(slot_values: dict[str, float], ppi: float) -> float:
    geom = CoilGeometry.from_slot_values(
        slot_values, coil_category="DX", coil_hand="LH", header_type="Header 1", special_feature=None
    )
    layout = layout_dx_front_view(geom)
    avail_w, avail_h = DEFAULT_CANVAS_W - 2 * PAD_PX, DEFAULT_CANVAS_H - 2 * PAD_PX
    return max(layout.extent_w * ppi / avail_w, layout.extent_h * ppi / avail_h) * 100.0


def main() -> int:
    out_dir = REPO_ROOT / "build" / "schematic_preview"
    out_dir.mkdir(parents=True, exist_ok=True)

    aspects: dict[str, float] = {}
    for name, slot_values in CASES.items():
        result = render_scale_schematic(
            slot_values, coil_category="DX", coil_hand="LH", header_type="Header 1"
        )
        path = out_dir / f"{name}.svg"
        path.write_text(result.svg, encoding="utf-8")
        _, _, w, h = result.metadata["casing_px"]
        ppi = result.metadata["px_per_inch"]
        aspects[name] = w / h
        print(f"{name:13s} -> {path}")
        print(
            f"              casing {w:.0f}x{h:.0f}px  aspect(w/h)={w / h:.2f}  "
            f"px_per_inch={ppi:.2f}  canvas_fill={_fill_percent(slot_values, ppi):.0f}%"
        )

    verdict = "VISIBLY DIFFERENT" if aspects["tall_narrow"] < 1.0 < aspects["short_wide"] else "TOO SIMILAR — FAILED"
    print(
        f"\nProportion check: tall_narrow={aspects['tall_narrow']:.2f} vs "
        f"short_wide={aspects['short_wide']:.2f}  ->  {verdict}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
