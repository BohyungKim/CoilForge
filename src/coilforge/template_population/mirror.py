"""Reusable LH <-> RH drawing-template mirror for the PDF-derived templates.

Any seeded template can auto-generate its opposite-hand pair. Only the central
coil-drawing region (the illustration + dimension lines + callouts) is reflected
about its own centre, so the connection geometry swaps to the opposite hand
while the title block, side spec panel, notes and logo stay exactly where they
are. Dimension-text glyphs are counter-flipped so they remain readable.

The result is a review aid; engineering must confirm the mirrored handing
geometry. Pure string/regex operations (no PDF library) so it is safe at
runtime as well as build time.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

# Central coil-drawing region in page points (excludes title block y>~495,
# side panel x>~640, top notes y<~95 and the bottom-left logo).
_COIL_REGION = (150.0, 640.0, 95.0, 492.0)
_PAGE_H = 612.0


def _path_bbox(d: str) -> tuple[float, float, float, float] | None:
    nums = [float(n) for n in re.findall(r"-?\d*\.?\d+", d)]
    if len(nums) < 2:
        return None
    xs, ys = nums[0::2], nums[1::2]
    n = min(len(xs), len(ys))
    xs, ys = xs[:n], ys[:n]
    # path transform is matrix(1,0,0,-1,0,612): x unchanged, page_y = 612 - y
    return min(xs), max(xs), _PAGE_H - max(ys), _PAGE_H - min(ys)


def _text_xy(attrs: str, inner: str) -> tuple[float, float] | None:
    xm = re.search(r'<tspan\b[^>]*\bx="([\-\d.]+)', inner)
    ym = re.search(r'<tspan\b[^>]*\by="([\-\d.]+)"', inner)
    fm = re.search(r"matrix\([^)]*?([\-\d.]+)\)", attrs)
    if not xm or not ym:
        return None
    f = float(fm.group(1)) if fm else _PAGE_H
    return float(xm.group(1)), f + float(ym.group(1))


def _in_region(cx: float, cy: float, region: tuple[float, float, float, float]) -> bool:
    x0, x1, y0, y1 = region
    return x0 <= cx <= x1 and y0 <= cy <= y1


def mirror_svg(svg: str, *, region: tuple[float, float, float, float] = _COIL_REGION) -> str:
    """Return the SVG with only the coil-drawing region horizontally mirrored."""
    m = re.search(r"<svg[^>]*>\s*", svg)
    if not m:
        return svg
    head, rest = svg[: m.end()], svg[m.end():]
    split = rest.find('<g id="zone.review_metadata">')
    if split == -1:
        split = rest.rfind("</svg>")
    content, trailer = rest[:split], rest[split:]

    # Pass 1: collect region element x-extents -> mirror axis.
    region_xs: list[float] = []
    for mm in re.finditer(r"<(path|text|image)\b([^>]*?)(?:>(.*?)</\1>|/>)", content, re.S):
        tag, attrs, body = mm.group(1), mm.group(2), mm.group(3)
        if tag == "text":
            xy = _text_xy(attrs, body or "")
            if xy and _in_region(xy[0], xy[1], region):
                region_xs.append(xy[0])
        elif tag == "path":
            dm = re.search(r'\bd="([^"]*)"', mm.group(0))
            bb = _path_bbox(dm.group(1)) if dm else None
            if bb and _in_region((bb[0] + bb[1]) / 2, (bb[2] + bb[3]) / 2, region):
                region_xs.extend([bb[0], bb[1]])
    if not region_xs:
        return svg
    cx = (min(region_xs) + max(region_xs)) / 2

    # Pass 2: pull region elements out, counter-flip region texts, wrap in the
    # reflection group; everything else stays exactly where it is.
    chunks: list[str] = []

    def take(mm: re.Match[str]) -> str:
        whole, tag, attrs, body = mm.group(0), mm.group(1), mm.group(2), mm.group(3)
        if tag == "text":
            xy = _text_xy(attrs, body or "")
            if not (xy and _in_region(xy[0], xy[1], region)):
                return whole
            x0 = xy[0]
            fm = re.search(r"matrix\([^)]*?([\-\d.]+)\)", attrs)
            f = fm.group(1) if fm else "612"
            new = f'transform="matrix(-1 0 0 1 {2 * x0:.2f} {f})"'
            new_attrs = (
                re.sub(r'transform="[^"]*"', new, attrs)
                if "transform=" in attrs else f"{attrs} {new}"
            )
            chunks.append(f"<text{new_attrs}>{body}</text>")
            return ""
        if tag == "path":
            dm = re.search(r'\bd="([^"]*)"', whole)
            bb = _path_bbox(dm.group(1)) if dm else None
            if bb and _in_region((bb[0] + bb[1]) / 2, (bb[2] + bb[3]) / 2, region):
                chunks.append(whole)
                return ""
        return whole

    content = re.sub(r"<(path|text)\b([^>]*?)(?:>(.*?)</\1>|/>)", take, content, flags=re.S)
    flip = f'<g transform="matrix(-1 0 0 1 {2 * cx:.2f} 0)">' + "".join(chunks) + "</g>"
    return f"{head}{content}{flip}{trailer}"


def _opposite_hand_id(template_id: str) -> str:
    if "_lh_" in template_id:
        return template_id.replace("_lh_", "_rh_")
    if "_rh_" in template_id:
        return template_id.replace("_rh_", "_lh_")
    if template_id.endswith("_lh"):
        return template_id[: -len("_lh")] + "_rh"
    if template_id.endswith("_rh"):
        return template_id[: -len("_rh")] + "_lh"
    raise ValueError(f"{template_id!r} has no LH/RH hand to mirror")


def create_mirror(src_template_id: str, *, category: str = "dx", **_: Any) -> str:
    """Generate the opposite-hand mirror template dir from a seeded template.

    Works LH->RH and RH->LH (one hand is seeded from a real PDF, the other is
    its mirror). Returns the new template id.
    """
    dst_template_id = _opposite_hand_id(src_template_id)
    new_hand = "RH" if "_rh" in dst_template_id else "LH"
    old_hand = "LH" if new_hand == "RH" else "RH"
    base = REPO_ROOT / "templates" / "drawing" / "coilmaster" / category
    src_dir, dst_dir = base / src_template_id, base / dst_template_id
    rh_template_id = dst_template_id  # local alias for the writer below
    lh_template_id = src_template_id
    dst_dir.mkdir(parents=True, exist_ok=True)

    dst_dir.mkdir(parents=True, exist_ok=True)
    svg = (src_dir / "template.svg").read_text(encoding="utf-8")
    svg = mirror_svg(svg)
    svg = svg.replace(src_template_id, dst_template_id).replace(f" {old_hand} ", f" {new_hand} ")
    (dst_dir / "template.svg").write_text(svg, encoding="utf-8")

    slot_map = json.loads((src_dir / "slot_map.json").read_text(encoding="utf-8"))
    slot_map["template_id"] = dst_template_id
    _write_json(dst_dir / "slot_map.json", slot_map)

    meta = json.loads((src_dir / "template_metadata.json").read_text(encoding="utf-8"))
    meta.update(
        template_id=dst_template_id,
        coil_hand=new_hand,
        seed_method="mirrored_from_seeded_pair_review_required",
        review_status="review_required",
    )
    meta["notes"] = (meta.get("notes") or []) + [
        f"{new_hand} generated by mirroring the coil region of {src_template_id} about its centre.",
        "Mirror is a review aid; engineering must confirm the mirrored handing geometry.",
    ]
    _write_json(dst_dir / "template_metadata.json", meta)

    if (src_dir / "seed_evidence.json").exists():
        evidence = json.loads((src_dir / "seed_evidence.json").read_text(encoding="utf-8"))
        if isinstance(evidence, dict):
            evidence["template_id"] = dst_template_id
            evidence["coil_hand"] = new_hand
            evidence["intake_status"] = "mirrored_review_required"
            _write_json(dst_dir / "seed_evidence.json", evidence)
        else:
            shutil.copy(src_dir / "seed_evidence.json", dst_dir / "seed_evidence.json")

    return dst_template_id


def create_rh_mirror(lh_template_id: str, *, category: str = "dx", **_: Any) -> str:
    """Back-compat alias: LH -> RH mirror (see create_mirror for both directions)."""
    if "_lh_" not in lh_template_id and not lh_template_id.endswith("_lh"):
        raise ValueError(f"{lh_template_id!r} is not an LH template id")
    return create_mirror(lh_template_id, category=category)


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
