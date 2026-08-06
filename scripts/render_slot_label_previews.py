"""Render all 22 drawing templates with each slot filled by its own slot-id label.

Purpose (John 2026-06-25): most populated values land in the right spot, but a few
slot text positions sit far from where the dimension belongs. Filling every slot
with its *label* (slot.R2 -> "R2", slot.CD -> "CD", ...) makes every dimension's
draw position visible, so John can mark the misplaced ones for a later coordinate
adjustment pass.

Output (review-aid only; no engineering values, no export):
  docs/template_preview/labelmap/<template_id>.svg   -- one per bucket
  docs/template_preview/labelmap/_contact_sheet.html -- all 22 in a grid, markable

Run: python scripts/render_slot_label_previews.py
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.template_population.catalog import (  # noqa: E402
    list_template_entries,
)
from coilforge.template_population.slot_population import (  # noqa: E402
    populate_template_slots,
)

OUT_DIR = ROOT / "docs" / "template_preview" / "labelmap"


def _slot_label_values(slot_map_path: Path) -> dict[str, str]:
    """Build {slot_id: label} so each slot renders its own name in place."""
    data = json.loads(slot_map_path.read_text(encoding="utf-8"))
    return {slot["slot_id"]: slot["label"] for slot in data.get("slots", [])}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = sorted(
        list_template_entries(status="active_review_aid"),
        key=lambda e: e.template_id,
    )

    cards: list[str] = []
    for entry in entries:
        slot_values = _slot_label_values(ROOT / entry.slot_map_path)
        result = populate_template_slots(entry.template_id, slot_values)
        if not result.svg:
            print(f"SKIP {entry.template_id}: no svg ({result})")
            continue
        (OUT_DIR / f"{entry.template_id}.svg").write_text(result.svg, encoding="utf-8")
        meta = (
            f"{entry.coil_category} / {entry.coil_hand} / "
            f"{entry.header_type or entry.special_feature or '-'} "
            f"({len(slot_values)} slots)"
        )
        cards.append(
            '<figure class="card">'
            f"<figcaption><strong>{html.escape(entry.template_id)}</strong>"
            f"<span>{html.escape(meta)}</span></figcaption>"
            f'<div class="art">{result.svg}</div>'
            "</figure>"
        )
        print(f"OK   {entry.template_id} ({len(slot_values)} slots)")

    contact = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>CoilForge slot-label map — all {len(cards)} templates</title>
<style>
  body {{ font-family: system-ui, "Segoe UI", sans-serif; background:#0f1115;
    color:#e6e6e6; margin:0; padding:24px; }}
  h1 {{ font-size:18px; }}
  p.note {{ color:#8a93a3; max-width:900px; }}
  .grid {{ display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:18px; }}
  .card {{ background:#171a21; border:1px solid #2a2f3a; border-radius:8px;
    margin:0; padding:10px; }}
  figcaption {{ display:flex; justify-content:space-between; gap:12px;
    font-size:13px; margin-bottom:8px; }}
  figcaption span {{ color:#8a93a3; }}
  .art {{ background:#fff; border-radius:6px; padding:6px; overflow:auto; }}
  .art svg {{ width:100%; height:auto; display:block; }}
  @media print {{ body {{ background:#fff; color:#000; }}
    .card {{ break-inside:avoid; border-color:#bbb; }} }}
</style></head>
<body>
  <h1>CoilForge — slot-label map (review aid, not for manufacturing)</h1>
  <p class="note">Every dimension slot is filled with its own slot id (e.g. "R2",
  "CD", "HD2") so its draw position is visible. Mark any label that sits far from
  where its dimension belongs; those text-element positions will be adjusted in a
  follow-up pass. Per-template SVGs are in this same folder.</p>
  <div class="grid">{''.join(cards)}</div>
</body></html>"""
    contact_path = OUT_DIR / "_contact_sheet.html"
    contact_path.write_text(contact, encoding="utf-8")
    print(f"\nContact sheet: {contact_path}")
    print(f"Per-template SVGs: {OUT_DIR}  ({len(cards)} files)")


if __name__ == "__main__":
    main()
