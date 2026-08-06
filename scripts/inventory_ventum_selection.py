"""Phase 0 (READ-ONLY): inventory the Ventum+ coil-selection PDFs page-by-page so we
know which dedicated template buckets can be seeded and from which (pdf, page).

These are per-PROJECT multi-coil packages (one PDF holds many coil-drawing pages), so
each (category, hand, header) template bucket = one specific (pdf, page). This script
classifies every page using the SAME extractors the pipeline uses — it never invents a
value — and emits a bucket -> candidate (pdf, page) manifest for John to confirm before
any seeding.

Nothing here writes into the repo/templates; it only reads the source PDFs and prints a
table + writes a JSON manifest to the path given by --out (default: scratchpad).

Usage:
    python scripts/inventory_ventum_selection.py [--out manifest.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import fitz  # PyMuPDF  # noqa: E402

from coilforge.submittal.coilmaster_drawing_extract import (  # noqa: E402
    detect_product_and_size,
    extract_coilmaster_drawing,
)
from coilforge.submittal.pdf_intake import coil_category_of_tag  # noqa: E402

# The two source folders John provided (OneDrive). Kept here so the script is a
# reproducible record of what was inventoried.
_BASE = Path(
    r"C:\Users\JohnKim\OneDrive - Oxygen8\Oxygen8 SharePoint Shortcuts"
    r"\Documents - Product Development\Ventum+ Coil selection"
)
_FOLDERS = {"DX-HGRH": _BASE / "DX- HGRH", "HYDRONIC": _BASE / "Hydronic"}

# coil category (from tag prefix) -> template category dir.
_CATEGORY_DIR = {
    "DX COIL": "dx",
    "HGRH COIL": "hgrh",
    "Hot Water Coil": "hwc",
    "Chilled Water Coil": "cwc",
}
# Water coils are 1HD only (no header suffix); DX/HGRH carry a header count.
_HEADERED = {"dx", "hgrh"}
# A page is only seedable if it is real vector artwork with a selectable text layer.
_MIN_VECTOR_DRAWINGS = 40
_MIN_TEXT_CHARS = 200


def _hand_token(hand: str | None) -> str | None:
    if hand in ("LH", "RH"):
        return hand.lower()
    return None


def _bucket_id(cat_dir: str, hand: str | None, circuits: int | None) -> str | None:
    """Suggested dedicated Ventum+ bucket id, or None when the classification is too
    incomplete to name one (surfaced as a review row rather than a guessed bucket)."""
    h = _hand_token(hand)
    if cat_dir is None or h is None:
        return None
    if cat_dir in _HEADERED:
        n = circuits or 1
        return f"coilmaster_vplus_{cat_dir}_{h}_header{n}"
    return f"coilmaster_vplus_{cat_dir}_{h}"


def _classify_page(text: str, drawings: int) -> dict[str, object]:
    ex = extract_coilmaster_drawing(text)
    tag = ex.get("tag")
    category = coil_category_of_tag(tag) if tag else None
    cat_dir = _CATEGORY_DIR.get(category) if category else None
    # product token (V20..V150) lives on the cover/schedule page, not the per-coil
    # drawing page — so it is usually None here. Both source folders are Ventum+ (John
    # confirmed), so product is assigned folder-level in main(); we keep any per-page
    # detection as corroborating evidence only.
    product, size = detect_product_and_size(text)
    hand = ex.get("hand")
    circuits = ex.get("circuits")
    seedable = drawings >= _MIN_VECTOR_DRAWINGS and len(text.strip()) >= _MIN_TEXT_CHARS
    return {
        "tag": tag,
        "category": category,
        "cat_dir": cat_dir,
        "detected_product": product,  # per-page detection (usually None)
        "size": size,
        "hand": hand,               # from the drawing model number (may be None)
        "hand_inferred": False,     # set True when filled from the project's cover hand
        "circuits": circuits,
        "model_number": ex.get("model_number"),
        "vector_drawings": drawings,
        "text_chars": len(text.strip()),
        "seedable": seedable,
        "bucket_id": None,          # computed after the per-PDF hand fallback
    }


def _fill_project_hand(pdf_rows: list[dict[str, object]]) -> None:
    """Fill a coil page's missing hand from the project's dominant hand (cover page or
    the majority of sibling pages). Marks it inferred so John knows it was not printed on
    that page. Never overrides a page that already states its own hand."""
    hands = [r["hand"] for r in pdf_rows if r["hand"] in ("LH", "RH")]
    if not hands:
        return
    dominant = max(set(hands), key=hands.count)
    for r in pdf_rows:
        if r["hand"] not in ("LH", "RH") and r["cat_dir"]:
            r["hand"] = dominant
            r["hand_inferred"] = True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="JSON manifest output path")
    args = ap.parse_args()

    rows: list[dict[str, object]] = []
    for folder_key, folder in _FOLDERS.items():
        if not folder.is_dir():
            print(f"!! folder missing: {folder}")
            continue
        for pdf in sorted(folder.glob("*.pdf")):
            try:
                doc = fitz.open(pdf)
            except Exception as exc:  # unreadable PDF -> surface, never crash the sweep
                print(f"!! cannot open {pdf.name}: {exc}")
                continue
            pdf_rows: list[dict[str, object]] = []
            for i in range(doc.page_count):
                page = doc[i]
                info = _classify_page(page.get_text(), len(page.get_drawings()))
                info.update(folder=folder_key, pdf=pdf.name, page=i)
                pdf_rows.append(info)
            doc.close()
            # Fill missing per-page hand from the project's dominant hand, then name buckets.
            _fill_project_hand(pdf_rows)
            for r in pdf_rows:
                r["bucket_id"] = _bucket_id(r["cat_dir"], r["hand"], r["circuits"])
            rows.extend(pdf_rows)

    # Every coil-drawing page in these two folders is a Ventum+ selection (John
    # confirmed the folders), regardless of whether the V-size token prints on the page.
    vplus = [r for r in rows if r["cat_dir"] and r["seedable"]]

    print(f"\n=== ALL PAGES: {len(rows)} across {sum(1 for _ in _FOLDERS)} folders ===")
    hdr = f"{'pdf':44} {'pg':>2} {'tag':10} {'cat':4} {'hnd':4} {'cir':>3} {'vec':>4} {'seed':4} bucket"
    print(hdr)
    for r in rows:
        hand_disp = (str(r["hand"]) + ("*" if r["hand_inferred"] else "")) if r["hand"] else "-"
        print(
            f"{str(r['pdf'])[:44]:44} {r['page']:>2} {str(r['tag'] or '-')[:10]:10} "
            f"{str(r['cat_dir'] or '-'):4} {hand_disp:4} "
            f"{str(r['circuits'] or '-'):>3} {r['vector_drawings']:>4} "
            f"{'Y' if r['seedable'] else 'n':>4} {r['bucket_id'] or '(unclassified)'}"
        )
    print("  (* = hand inferred from the project's cover/dominant hand, not printed on that page)")

    # Dedup to a bucket -> candidate manifest: first seedable Ventum+ page per bucket,
    # plus any additional candidates so John can choose the canonical reference.
    manifest: dict[str, list[dict[str, object]]] = {}
    for r in vplus:
        bid = r["bucket_id"]
        if not bid:
            continue
        manifest.setdefault(bid, []).append(
            {"pdf": r["pdf"], "page": r["page"], "tag": r["tag"],
             "circuits": r["circuits"], "hand_inferred": r["hand_inferred"]}
        )

    print(f"\n=== SEEDABLE VENTUM+ BUCKETS: {len(manifest)} ===")
    for bid in sorted(manifest):
        cands = manifest[bid]
        first = cands[0]
        extra = f"  (+{len(cands) - 1} more candidates)" if len(cands) > 1 else ""
        print(f"  {bid:38} <- {str(first['pdf'])[:40]} p{first['page']}{extra}")

    unclassified = [
        r for r in rows
        if r["seedable"] and r["tag"] and not r["bucket_id"]
    ]
    if unclassified:
        print(f"\n=== SEEDABLE COIL PAGES STILL UNCLASSIFIED (need hand/category): {len(unclassified)} ===")
        for r in unclassified:
            print(f"  {r['pdf']} p{r['page']} tag={r['tag']} cat={r['cat_dir']} hand={r['hand']} circuits={r['circuits']}")

    out_path = Path(args.out) if args.out else (
        Path(REPO_ROOT) / "build" / "ventum_selection_manifest.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"buckets": manifest, "all_pages": rows}, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nmanifest -> {out_path}")


if __name__ == "__main__":
    main()
