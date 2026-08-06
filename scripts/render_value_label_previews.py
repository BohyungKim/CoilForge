"""Render all 22 drawing templates populated with REAL engine values + inline labels.

John 2026-06-25: the slot-label previews (render_slot_label_previews.py) replaced each
value with its slot name, so a callout read "BF BF". He wants the existing drawing style
instead — the real number next to its label ("0.5 BF") — to check each dimension's position
and mark the misplaced ones.

The drawing-area dimension callouts already embed the label inline in the template
(`{{slot.BF}} BF`), so we only need real numbers. We get them from the rule engine via
build_drawing_slots for a representative coil per (category, header count), then HYBRID-fill:
start from {slot_id: label} (so nothing is ever blank) and override with the engine values.

Output (review-aid only; no engineering claims, no export):
  docs/template_preview/valuemap/<template_id>.svg
  docs/template_preview/valuemap/_contact_sheet.html

Run: python scripts/render_value_label_previews.py
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.services.direct_coil_drawing_pipeline import (  # noqa: E402
    build_drawing_slots,
)
from coilforge.template_population.catalog import (  # noqa: E402
    list_template_entries,
)
from coilforge.template_population.slot_population import (  # noqa: E402
    populate_template_slots,
)
from coilforge.workflows.submittal_to_drawing import (  # noqa: E402
    apply_label_authority,
)

OUT_DIR = ROOT / "docs" / "template_preview" / "valuemap"

# Representative engine inputs. NOVA + a valid size (R-076) resolves the most fields HIGH,
# so the dimension callouts fill with real numbers. circuits/qty track the header count.
_PRODUCT = "NOVA"
_UNIT_SIZE = "B20"
_GEOM = dict(
    rows=4, conn_size=0.625, suction_conn_size=0.625,
    finned_height=24.0, finned_length=48.0,
)


def _circuits_for(entry) -> int:
    """Header count drives circuits (header3 -> 3 assemblies -> I3/S3/O6/R6 ...)."""
    if entry.header_type:
        m = re.search(r"(\d+)", entry.header_type)
        if m:
            return int(m.group(1))
    return 1  # HGBP / water coils: single header assembly


def _engine_values(entry) -> dict[str, object]:
    circuits = _circuits_for(entry)
    try:
        slots, _ = build_drawing_slots(
            coil_type=entry.coil_category,
            product_type=_PRODUCT,
            unit_size=_UNIT_SIZE,
            circuits=circuits,
            qty_conn_per_header=circuits,
            tag=entry.template_id,
            **_GEOM,
        )
    except Exception as exc:  # graceful: fall back to labels-only for this bucket
        print(f"  (engine values unavailable for {entry.template_id}: {exc})")
        return {}
    # Drop non-string/number list slots (e.g. NOTES) that would clutter callouts.
    return {k: v for k, v in slots.items() if not isinstance(v, (list, dict))}


def _slot_label_baseline(slot_map_path: Path) -> dict[str, str]:
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
        baseline = _slot_label_baseline(ROOT / entry.slot_map_path)
        slot_values: dict[str, object] = dict(baseline)
        engine = _engine_values(entry)
        slot_values.update(engine)  # real numbers override the slot-id labels

        result = populate_template_slots(entry.template_id, slot_values)
        if not result.svg:
            print(f"SKIP {entry.template_id}: no svg ({result})")
            continue
        # Rewrite callout labels to their Direct Coil form (labels only) so the preview
        # matches the live drawing (John 2026-06-26). Values are untouched.
        svg = apply_label_authority(result.svg)
        (OUT_DIR / f"{entry.template_id}.svg").write_text(svg, encoding="utf-8")
        meta = (
            f"{entry.coil_category} / {entry.coil_hand} / "
            f"{entry.header_type or entry.special_feature or '-'} "
            f"({len(engine)} real values)"
        )
        cards.append(
            '<figure class="card">'
            f"<figcaption><strong>{html.escape(entry.template_id)}</strong>"
            f"<span>{html.escape(meta)}</span></figcaption>"
            f'<div class="art">{svg}</div>'
            "</figure>"
        )
        print(f"OK   {entry.template_id} ({len(engine)} real values)")

    contact = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>CoilForge value+label map — all {len(cards)} templates</title>
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
  <h1>CoilForge — value + label map (review aid, not for manufacturing)</h1>
  <p class="note">Each dimension callout shows its real engine-computed value next to its
  label in the existing drawing style (e.g. "0.5 BF", "0.625 R2"). Values are from a
  representative NOVA coil per category/header — for position checking only. Mark any
  callout whose text sits far from where the dimension belongs; those positions will be
  adjusted in a follow-up pass. Slots with no engine value fall back to their slot id.</p>
  <div class="grid">{''.join(cards)}</div>
</body></html>"""
    contact_path = OUT_DIR / "_contact_sheet.html"
    contact_path.write_text(contact, encoding="utf-8")
    print(f"\nContact sheet: {contact_path}")
    print(f"Per-template SVGs: {OUT_DIR}  ({len(cards)} files)")


if __name__ == "__main__":
    main()
