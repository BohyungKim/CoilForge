"""Render populated DX_1_LH and DX_2_LH template drawings to PNG (review aid).

Feeds LH PDF text through the logic-derived template path, writes each populated
SVG, and rasterizes it with headless Chrome so John can eyeball the drawings.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.submittal.pdf_to_template_drawing import (  # noqa: E402
    pdf_text_to_template_drawing,
)

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# Single-header DX, LEFT hand (mirrors CDXC-1.pdf).
DX1_LH_TEXT = (
    "15 FL\n12 FH13.25 CH\n18.00 CL1.50 HF 1.50 RF0.63 TF\n0.63 BF5.50 CD\n"
    "20.25 OAL1.75 RB\n2.00 O2\n0.63 R23.00 I12.75 S13.50 HD28.00 SL2\n4.50 HDx1\n"
    "1.50 1.752 Feed / 24 Pass\n13 Fins Per Inch\n"
    'RETURN CONN SIZE\n0.625" OD Header\n'
    "DX-F-S-04-13-12.00x15.00-L\nTag: CDXC-1\n"
)
DX1_COVER = "1 CDXC- 1 DXC Cooling A16_V_I_ERV LH\n"

# Two-circuit DX, LEFT hand (LH variant of the CDXC-2 layout). The RETURN CONN
# SIZE line lets the rule engine derive the per-header R positions (R-022 list),
# so H3/H4 (I3/S3/HDx3/O4/R4/HD4/SL4) populate logic-derived, not as-built.
DX2_LH_TEXT = (
    "34 FL\n26 FH27.25 CH\n37.00 CL1.50 HF 1.50 RF0.63 TF\n0.63 BF5.50 CD\n"
    "39.25 OAL1.75 RB\n2.00 O2\n1.13 R22.00 O4\n3.75 R43.00 I11.88 S1\n"
    "3.00 I33.63 S33.50 HD28.00 SL24.50 HDx1\n"
    'RETURN CONN SIZE\n1.125" OD Header\n'
    "14 Passes per Feed\nC1: 3 Feed C2: 4 Feed\n"
    "DX-F-S-04-14-26.00x34.00-L\nTag: CDXC-2\n"
)
DX2_COVER = "1 CDXC- 2 DXC Cooling A16_V_I_ERV LH\n"


def render(name: str, text: str, cover: str, out_dir: Path) -> None:
    td = pdf_text_to_template_drawing(text, cover_text=cover)
    print(f"\n=== {name} ===")
    print(f"  template_id        : {td['template_id']}")
    print(f"  generation_allowed : {td['generation_allowed']}")
    print(f"  drawing_value_source: {td['drawing_value_source']}")
    print(f"  product / unit     : {td['product_type']} / {td['unit_size']}")
    print(f"  validation_mismatches: {td['validation_mismatches']}")
    if not (td.get("generation_allowed") and td.get("svg")):
        print("  !! no SVG rendered (template not seeded)")
        return
    svg_path = out_dir / f"{name}.svg"
    png_path = out_dir / f"{name}.png"
    svg_path.write_text(td["svg"], encoding="utf-8")
    subprocess.run(
        [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=2",
            "--window-size=792,612",
            f"--screenshot={png_path}",
            svg_path.as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    print(f"  PNG -> {png_path}")


def main() -> None:
    out_dir = ROOT / "build" / "ui_screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    render("dx_1_lh", DX1_LH_TEXT, DX1_COVER, out_dir)
    render("dx_2_lh", DX2_LH_TEXT, DX2_COVER, out_dir)


if __name__ == "__main__":
    main()
