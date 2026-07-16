"""Generate the template-coverage dashboard from the live drawing catalog.

Replaces the hand-authored ``docs/coverage_dashboard.html`` snapshot (which drifts
the moment a bucket is seeded) with a page derived from
``template_population.catalog.list_template_entries()`` — so "what is seeded vs
what is missing" is always exactly the code, never a stale transcription.

Coverage is over the confirmed MVP taxonomy (CLAUDE.md): a bucket is one
``(category, hand, header, special)`` drawing configuration. The catalog holds
only the SEEDED buckets, per product family (SHARED product-agnostic + dedicated
VENTUM_PLUS). Everything in the taxonomy that is NOT in the catalog is a gap:

- A SHARED gap would mean a core bucket is unseeded (currently none — all 22 seeded).
- A dedicated VENTUM_PLUS gap is classified by the 2026-07-14 DX-only gate:
  a **DX** gap is ``not registered`` (blocked — Ventum+ DX mounts ConnectionUP/R-032,
  the shared ConnectionDOWN template must not be borrowed), a **non-DX** gap
  (HGRH/HWC/CWC — no distributor) still falls back to the shared template and draws.

Pure: reads the catalog + emits HTML. ``--check`` validates the encoded taxonomy
against the live SHARED buckets (they must match exactly) and writes nothing —
a CI guard that fails if the taxonomy or the catalog drifts apart. Review aid only.
"""
from __future__ import annotations

import argparse
import datetime
import html
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coilforge.template_population.catalog import (  # noqa: E402
    list_template_entries,
)

DEFAULT_OUT = ROOT / "docs" / "coverage_dashboard.html"

# Confirmed MVP taxonomy (CLAUDE.md): the full bucket space per category. DX/HGRH
# carry Header 1-4; HWC/CWC are 1HD only; DX additionally has the HGBP special
# (per hand, no header). This is the "expected" set the catalog is measured against;
# --check asserts it equals the live SHARED buckets exactly.
_HEADERS_1_4 = ("Header 1", "Header 2", "Header 3", "Header 4")
EXPECTED_TAXONOMY: dict[str, dict[str, tuple]] = {
    "DX": {"hands": ("LH", "RH"), "headers": _HEADERS_1_4, "specials": ("HGBP",)},
    "HGRH": {"hands": ("LH", "RH"), "headers": _HEADERS_1_4, "specials": ()},
    "HWC": {"hands": ("LH", "RH"), "headers": ("Header 1",), "specials": ()},
    "CWC": {"hands": ("LH", "RH"), "headers": ("Header 1",), "specials": ()},
}

# Which product families a special is even selectable on — a special is NOT part of
# every family's bucket space. Hot gas bypass is a Nova / Ventum H option only (John
# 2026-07-15), and both draw from the SHARED (product-agnostic) buckets, so `None`
# (= SHARED) is the whole story: **a Ventum+ HGBP cell is not an unseeded gap, it is a
# configuration that does not exist**, and listing it would ask someone to go seed a
# reference drawing that cannot be produced. A special absent from this map is assumed
# selectable on every family.
SPECIAL_FAMILIES: dict[str, frozenset[str | None]] = {"HGBP": frozenset({None})}

# Gap classification for a dedicated-family bucket that is not seeded.
GAP_BLOCKED = "not_registered"  # Ventum+ DX — must be seeded from a real UP reference
GAP_FALLBACK = "shared_fallback"  # Ventum+ non-DX — draws via the shared template


def _bucket_key(category: str, hand: str, header, special) -> tuple:
    """Identity of one drawing configuration, normalized to the catalog's fields."""
    return (category, hand, header if not special else None, special)


def expected_buckets(category: str, family: str | None = None) -> list[tuple]:
    """Every ``(category, hand, header, special)`` bucket the taxonomy expects for one
    product family (``None`` = SHARED). Specials the family cannot select are omitted —
    they are non-existent configurations, not gaps (see :data:`SPECIAL_FAMILIES`)."""
    spec = EXPECTED_TAXONOMY[category]
    out: list[tuple] = []
    for hand in spec["hands"]:
        for header in spec["headers"]:
            out.append(_bucket_key(category, hand, header, None))
        for special in spec["specials"]:
            families = SPECIAL_FAMILIES.get(special)
            if families is not None and family not in families:
                continue
            out.append(_bucket_key(category, hand, None, special))
    return out


@dataclass(frozen=True)
class Cell:
    category: str
    hand: str
    header: str | None
    special: str | None
    seeded: bool
    template_id: str | None
    source_case_id: str | None
    gap_kind: str | None  # None if seeded; else GAP_BLOCKED / GAP_FALLBACK

    @property
    def label(self) -> str:
        return self.special or (self.header or "—")


def _seeded_index(family: str | None) -> dict[tuple, object]:
    """Catalog buckets for one family (None = SHARED), keyed by bucket identity."""
    idx: dict[tuple, object] = {}
    for e in list_template_entries():
        fam = e.product_family  # None for shared
        if fam != family:
            continue
        if not e.generation_allowed:  # a registered-but-blocked bucket is not "seeded"
            continue
        idx[_bucket_key(e.coil_category, e.coil_hand, e.header_type, e.special_feature)] = e
    return idx


def _classify_gap(category: str, family: str | None) -> str:
    # SHARED gaps (should be none) read as blocked — a missing core bucket cannot draw.
    if family is None:
        return GAP_BLOCKED
    # Dedicated Ventum+: DX gap is blocked (R-032 UP), non-DX falls back to shared.
    return GAP_BLOCKED if category == "DX" else GAP_FALLBACK


def build_family_cells(family: str | None) -> list[Cell]:
    seeded = _seeded_index(family)
    cells: list[Cell] = []
    for category in EXPECTED_TAXONOMY:
        for key in expected_buckets(category, family):
            _, hand, header, special = key
            entry = seeded.get(key)
            cells.append(
                Cell(
                    category=category,
                    hand=hand,
                    header=header,
                    special=special,
                    seeded=entry is not None,
                    template_id=getattr(entry, "template_id", None),
                    source_case_id=getattr(entry, "source_case_id", None),
                    gap_kind=None if entry else _classify_gap(category, family),
                )
            )
    return cells


def build_coverage_model() -> dict:
    shared = build_family_cells(None)
    vplus = build_family_cells("VENTUM_PLUS")

    def summarize(cells: list[Cell]) -> dict:
        seeded = [c for c in cells if c.seeded]
        blocked = [c for c in cells if c.gap_kind == GAP_BLOCKED]
        fallback = [c for c in cells if c.gap_kind == GAP_FALLBACK]
        return {
            "total": len(cells),
            "seeded": len(seeded),
            "blocked": len(blocked),
            "fallback": len(fallback),
        }

    return {
        "shared": {"cells": shared, "summary": summarize(shared)},
        "ventum_plus": {"cells": vplus, "summary": summarize(vplus)},
    }


def check_taxonomy_matches_shared() -> list[str]:
    """The encoded taxonomy must equal the live SHARED buckets exactly. Returns a
    list of drift messages (empty == in sync)."""
    expected: set[tuple] = set()
    for category in EXPECTED_TAXONOMY:
        expected.update(expected_buckets(category))
    actual = set(_seeded_index(None).keys())
    drift: list[str] = []
    for missing in sorted(expected - actual):
        drift.append(f"taxonomy expects but catalog is missing (SHARED): {missing}")
    for extra in sorted(actual - expected):
        drift.append(f"catalog has SHARED bucket not in taxonomy: {extra}")
    return drift


# --------------------------------------------------------------------------- #
# Rendering                                                                    #
# --------------------------------------------------------------------------- #

_CSS = """
:root{--bg:#0c0f14;--panel:#141922;--panel2:#1b2230;--ink:#e7ecf3;--muted:#8b97a8;
--line:#27303f;--ok:#3fb950;--warn:#d29922;--info:#58a6ff;--block:#f85149;
--font:ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
--mono:ui-monospace,"Cascadia Code","SF Mono",Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);line-height:1.45}
.wrap{max-width:1080px;margin:0 auto;padding:32px 24px 80px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px;margin:0 0 22px}
.badge{font-family:var(--mono);font-size:11px;color:var(--muted);border:1px solid var(--line);
border-radius:999px;padding:3px 10px;margin-left:8px}
.kpis{display:flex;gap:14px;flex-wrap:wrap;margin:2px 0 26px}
.kpi{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:12px 16px;min-width:150px}
.kpi .v{font-size:24px;font-weight:700;font-family:var(--mono)}
.kpi .k{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
section{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:22px 24px;margin-bottom:22px}
section h2{font-size:15px;margin:0 0 2px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
section h2 .n{font-family:var(--mono);font-size:12px;color:var(--muted);font-weight:500}
section .desc{color:var(--muted);font-size:12.5px;margin:0 0 16px;max-width:82ch}
.cat{margin:14px 0 6px;font-family:var(--mono);font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.6px}
.cells{display:flex;flex-wrap:wrap;gap:8px}
.cell{border:1px solid var(--line);border-radius:8px;padding:8px 11px;min-width:118px;background:var(--panel2)}
.cell .h{font-family:var(--mono);font-size:12px;font-weight:700}
.cell .m{font-family:var(--mono);font-size:10.5px;color:var(--muted);margin-top:3px;word-break:break-all}
.cell.seeded{border-color:rgba(63,185,80,.5)}
.cell.blocked{border-color:rgba(248,81,73,.55)}
.cell.fallback{border-color:rgba(88,166,255,.5)}
.pill{font-family:var(--mono);font-size:9.5px;padding:2px 7px;border-radius:999px;font-weight:700;display:inline-block}
.p-ok{background:rgba(63,185,80,.16);color:var(--ok)}
.p-block{background:rgba(248,81,73,.16);color:var(--block)}
.p-info{background:rgba(88,166,255,.16);color:var(--info)}
.legend{display:flex;flex-wrap:wrap;gap:16px;margin:4px 0 2px;font-size:12px;color:var(--muted)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.dot{width:11px;height:11px;border-radius:3px;display:inline-block}
footer{color:var(--muted);font-size:11.5px;margin-top:26px;font-family:var(--mono)}
"""


def _cell_html(c: Cell) -> str:
    if c.seeded:
        kind, pill, txt = "seeded", "p-ok", "seeded"
        meta = html.escape(c.source_case_id or c.template_id or "")
    elif c.gap_kind == GAP_BLOCKED:
        kind, pill, txt = "blocked", "p-block", "not registered"
        meta = "needs real Ventum+ DX reference (R-032 UP)" if c.category == "DX" else "no reference"
    else:
        kind, pill, txt = "fallback", "p-info", "shared fallback"
        meta = "draws via shared template"
    return (
        f'<div class="cell {kind}"><div class="h">{html.escape(c.hand)} · '
        f'{html.escape(c.label)}</div>'
        f'<div style="margin:5px 0 2px"><span class="pill {pill}">{txt}</span></div>'
        f'<div class="m">{meta}</div></div>'
    )


def _family_section(title: str, note: str, block_id: str, cells: list[Cell], summary: dict) -> str:
    rows = []
    for category in EXPECTED_TAXONOMY:
        cat_cells = [c for c in cells if c.category == category]
        rows.append(f'<div class="cat">{category} · {len(cat_cells)} buckets</div>')
        rows.append('<div class="cells">' + "".join(_cell_html(c) for c in cat_cells) + "</div>")
    return (
        f'<section><h2>{title} <span class="n">{block_id}</span></h2>'
        f'<p class="desc">{note}</p>'
        f'<p class="badge">seeded {summary["seeded"]}/{summary["total"]}'
        + (f' · not-registered {summary["blocked"]}' if summary["blocked"] else "")
        + (f' · shared-fallback {summary["fallback"]}' if summary["fallback"] else "")
        + "</p>" + "".join(rows) + "</section>"
    )


def render_html(model: dict, generated_on: str) -> str:
    s = model["shared"]["summary"]
    v = model["ventum_plus"]["summary"]
    kpis = [
        ("var(--ok)", f'{s["seeded"]}<span style="color:var(--muted);font-size:15px">/{s["total"]}</span>', "Shared buckets seeded"),
        ("var(--ok)", f'{v["seeded"]}<span style="color:var(--muted);font-size:15px">/{v["total"]}</span>', "Ventum+ dedicated seeded"),
        ("var(--block)", str(v["blocked"]), "Ventum+ DX not registered"),
        ("var(--info)", str(v["fallback"]), "Ventum+ non-DX shared fallback"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="v" style="color:{c}">{val}</div><div class="k">{k}</div></div>'
        for c, val, k in kpis
    )
    shared_note = (
        "Product-agnostic CoilMaster buckets every line draws through. No mirror/surrogate "
        "generation — each hand/header is seeded from its own real reference PDF."
    )
    vplus_note = (
        "Dedicated Ventum+ buckets (product_family fork, 2026-07-06) capture the R-032 "
        "ConnectionUP distributor from real references. An un-seeded Ventum+ <b>DX</b> combo is "
        "blocked as <b>not registered</b> (DX-only gate, John 2026-07-14) — never drawn with the "
        "shared ConnectionDOWN artwork; an un-seeded <b>non-DX</b> combo still falls back to the "
        "shared template and draws."
    )
    legend = (
        '<div class="legend">'
        '<span><i class="dot" style="background:var(--ok)"></i>seeded (dedicated / shared)</span>'
        '<span><i class="dot" style="background:var(--block)"></i>not registered (blocked)</span>'
        '<span><i class="dot" style="background:var(--info)"></i>shared fallback (draws)</span>'
        "</div>"
    )
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"/>"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>"
        "<title>CoilForge — Template Coverage (generated)</title>"
        f"<style>{_CSS}</style></head><body><div class=\"wrap\">"
        "<h1>CoilForge — Template Coverage<span class=\"badge\">auto-generated</span></h1>"
        f'<p class="sub">Seeded vs missing drawing buckets over the confirmed MVP taxonomy, '
        f'derived live from <code>catalog.list_template_entries()</code>. Review aid only.</p>'
        f'<div class="kpis">{kpi_html}</div>{legend}'
        + _family_section("1 · Shared (product-agnostic) buckets", shared_note,
                          f'{s["total"]} buckets · (category, hand, header, special)',
                          model["shared"]["cells"], s)
        + _family_section("2 · Ventum+ dedicated buckets", vplus_note,
                          f'{v["seeded"]}/{v["total"]} seeded · dedicated family fork',
                          model["ventum_plus"]["cells"], v)
        + f'<footer>Generated {generated_on} from template_population.catalog · '
        "no hand-authored snapshot · review aid only, not a production release.</footer>"
        "</div></body></html>"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"output HTML path (default: {DEFAULT_OUT})")
    parser.add_argument("--check", action="store_true",
                        help="validate the taxonomy against the live SHARED catalog; write nothing")
    args = parser.parse_args(argv)

    drift = check_taxonomy_matches_shared()
    if drift:
        print("Coverage taxonomy drift vs live catalog:", file=sys.stderr)
        for line in drift:
            print(f"  - {line}", file=sys.stderr)
        return 1

    if args.check:
        print("OK: coverage taxonomy matches the live SHARED catalog (no drift).")
        return 0

    model = build_coverage_model()
    generated_on = datetime.date.today().isoformat()
    args.out.write_text(render_html(model, generated_on), encoding="utf-8")
    s, v = model["shared"]["summary"], model["ventum_plus"]["summary"]
    print(f"Wrote {args.out}")
    print(f"  Shared: {s['seeded']}/{s['total']} seeded")
    print(f"  Ventum+: {v['seeded']}/{v['total']} seeded · "
          f"{v['blocked']} not-registered (DX) · {v['fallback']} shared-fallback (non-DX)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
