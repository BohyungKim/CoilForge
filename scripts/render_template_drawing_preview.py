"""Render the template-drawing preview panel to a self-contained HTML file.

Produces the *exact* markup that web/app.js renderTemplateDrawingPreview emits,
fed with the *real* populated drawing from pdf_to_template_drawing, styled with
the real web/style.css. Used to screenshot how the UI shows a PDF-reproduced
coil drawing (review-aid only).
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.submittal.pdf_to_template_drawing import (  # noqa: E402
    pdf_text_to_template_drawing,
)

DX1_TEXT = (
    "15 FL\n12 FH13.25 CH\n18.00 CL1.50 HF 1.50 RF0.63 TF\n0.63 BF5.50 CD\n"
    "20.25 OAL1.75 RB\n2.00 O2\n0.63 R23.00 I12.75 S13.50 HD28.00 SL2\n4.50 HDx1\n"
    "1.50 1.752 Feed / 24 Pass\n13 Fins Per Inch\n"
    'RETURN CONN SIZE\n0.625" OD Header\n'
    "DX-F-S-04-13-12.00x15.00-L\nTag: CDXC-1\n"
)
COVER = "1 CDXC- 1 DXC Cooling A16_V_I_ERV LH\n"
DX2_TEXT = (
    "34 FL\n26 FH27.25 CH\n37.00 CL1.50 HF 1.50 RF0.63 TF\n0.63 BF5.50 CD\n"
    "39.25 OAL1.75 RB\n2.00 O2\n1.13 R22.00 O4\n3.75 R43.00 I11.88 S1\n"
    "3.00 I33.63 S33.50 HD28.00 SL24.50 HDx1\n"
    "14 Passes per Feed\nC1: 3 Feed C2: 4 Feed\n"
    "DX-F-S-04-14-26.00x34.00-R\nTag: CDXC-2\n"
)


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _label(td: dict) -> str:
    if td.get("generation_allowed") and td.get("svg"):
        return f"Reproduced from submittal drawing: {td['template_id']}"
    if td.get("template_found"):
        return f"Links to {td['template_id']} — artwork not seeded yet"
    return "No drawing template registered for this coil"


def _reason(td: dict) -> str:
    ex = td.get("extracted", {})
    parts = [ex.get("coil_category"), ex.get("hand")]
    if ex.get("circuits"):
        parts.append(f"{ex['circuits']} circuit{'s' if ex['circuits'] > 1 else ''}")
    parts = [p for p in parts if p]
    base = f"{' / '.join(parts)}. " if parts else ""
    return f"{base}Read from the as-built drawing. Review-aid only — never manufacturing-approved."


def _caption(td: dict) -> str:
    ex = td.get("extracted", {})
    cells = [
        ("Tag", ex.get("tag")),
        ("Coil", ex.get("coil_category")),
        ("Hand", ex.get("hand")),
        ("Circuits", ex.get("circuits")),
        ("Rows", ex.get("rows")),
        ("Feeds", ex.get("feeds")),
        ("Return conn.", ex.get("return_conn_size")),
        ("Unit size", td.get("unit_size")),
        ("Product", td.get("product_type")),
        ("Dims read", ex.get("dimension_count")),
    ]
    return "".join(
        f"<span><em>{esc(label)}</em><strong>{esc(value)}</strong></span>"
        for label, value in cells
        if value not in (None, "")
    )


def _body(td: dict, rendered: bool) -> str:
    if rendered:
        return td["svg"]
    slots = td.get("slot_values", {})
    dims = "".join(
        f"<li><span>{esc(k.replace('slot.', ''))}</span><strong>{esc(v)}</strong></li>"
        for k, v in slots.items()
        if k.startswith("slot.")
    )
    slot_list = f'<ul class="template-drawing-slots">{dims}</ul>' if dims else ""
    return (
        '<div class="template-drawing-pending">'
        f"<strong>{esc(_label(td))}</strong>"
        "<p>The coil's values are fully extracted and ready to drop in as soon as "
        "this template's artwork is seeded.</p>"
        f"{slot_list}"
        "</div>"
    )


def panel(td: dict) -> str:
    rendered = bool(td.get("generation_allowed") and td.get("svg"))
    chip_cls = "status-review-required" if rendered else "status-blocked"
    chip_text = "Reproduced from PDF" if rendered else "Links — artwork not seeded"
    return f"""
    <section class="inspector-card drawing-card">
      <div class="card-title-row">
        <h3>Drawing Preview</h3>
        <span class="status-chip {chip_cls}">{esc(chip_text)}</span>
      </div>
      <div class="drawing-template-status {chip_cls}">
        <strong>{esc(_label(td))}</strong>
        <span>{esc(_reason(td))}</span>
      </div>
      <div class="drawing-preview">
        <div class="template-drawing-preview">
          <div class="template-drawing-caption">{_caption(td)}</div>
          <div class="template-drawing-canvas">{_body(td, rendered)}</div>
        </div>
      </div>
    </section>
    """


def main() -> None:
    dx1 = pdf_text_to_template_drawing(DX1_TEXT, cover_text=COVER)
    dx2 = pdf_text_to_template_drawing(DX2_TEXT)
    out_dir = ROOT / "build" / "ui_screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")

    for name, td in (("dx1_populated", dx1), ("dx2_seed_pending", dx2)):
        page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>{css}</style>
<style>
  body {{ background:#e8edf3; padding:24px; }}
  .harness {{ max-width:760px; margin:0 auto; display:grid; gap:14px; }}
  .harness-title {{ font-size:13px; color:#475569; font-weight:700;
    text-transform:uppercase; letter-spacing:.04em; }}
  .inspector-card {{ padding:16px; }}
  .card-title-row {{ display:flex; align-items:center;
    justify-content:space-between; }}
  .card-title-row h3 {{ margin:0; }}
</style></head>
<body><div class="harness">
  <div class="harness-title">CoilForge — PDF reproduction drawing preview ({name})</div>
  {panel(td)}
</div></body></html>"""
        (out_dir / f"{name}.html").write_text(page, encoding="utf-8")
        print(out_dir / f"{name}.html")


if __name__ == "__main__":
    main()
