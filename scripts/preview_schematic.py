"""Eyeball gate for the parametric drawing engine v0 (Phase 1).

Renders two contrasting DX coils from synthetic dimensions (no customer data) to
``build/schematic_preview/`` and prints each box's pixel aspect ratio. The two SVGs
MUST look visibly different in proportion: a tall-narrow coil vs a short-wide coil.
If they look the same, the slice has failed its purpose.

    python scripts/preview_schematic.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from coilforge.drawing.schematic_renderer import render_scale_schematic

# Synthetic dimensions only — never real customer data.
CASES: dict[str, dict[str, float]] = {
    "tall_narrow": {
        "slot.FL": 18.0, "slot.FH": 60.0, "slot.CL": 24.0, "slot.CH": 66.0,
        "slot.TF": 3.0, "slot.BF": 3.0, "slot.HF": 3.0, "slot.RF": 3.0,
    },
    "short_wide": {
        "slot.FL": 120.0, "slot.FH": 18.0, "slot.CL": 126.0, "slot.CH": 24.0,
        "slot.TF": 3.0, "slot.BF": 3.0, "slot.HF": 3.0, "slot.RF": 3.0,
    },
}


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
        aspect = w / h
        aspects[name] = aspect
        print(f"{name:12s} -> {path}")
        print(
            f"             casing {w:.0f}x{h:.0f}px  aspect(w/h)={aspect:.2f}  "
            f"px_per_inch={result.metadata['px_per_inch']:.2f}"
        )

    verdict = "VISIBLY DIFFERENT" if aspects["tall_narrow"] < 1.0 < aspects["short_wide"] else "TOO SIMILAR — FAILED"
    print(f"\nProportion check: tall_narrow={aspects['tall_narrow']:.2f} vs "
          f"short_wide={aspects['short_wide']:.2f}  ->  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
