"""Seed drawing templates from the real CoilMaster EZ Coil drawing PDFs.

Build-time tool (depends on PyMuPDF/fitz). For each coil-type/header-type bucket
it takes the provided EZ Coil drawing PDF, converts the page to a real-text SVG
(so the coil illustration, dimension lines, side panel and title block are kept
exactly as drawn), and turns every variable value into a stable {{slot.X}}
token. The result is a slotted template.svg that the existing
`populate_template_slots` fills with an uploaded coil's extracted values, and
that the existing catalog/web pipeline render unchanged.

Opposite handing is produced by mirroring the LH template (flip the coil image
and dimension lines about the page centre, counter-flip text so it stays
readable). Output is a review aid only — never manufacturing-approved.

Raw PDFs are NOT copied into the template folders; only the vectorised,
value-redacted skeleton (values replaced by slots) is stored.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

REPO_ROOT = Path(__file__).resolve().parents[1]

# Dimension callout labels (longest first so HDx1 wins over HD). The regex sorts
# by length, so list order here is not significant.
# "X" (uppercase, single char) is the tube-projection callout; it is case-
# sensitive so it never matches the lowercase "x" in tube specs (e.g.
# "0.375 x 0.016"). Added 2026-06-23 (John) so "1.13 X" redacts to {{slot.X}}.
_DIM_LABELS = [
    "HDx1", "HDx3", "HDx5", "HD2", "HD4", "HD6", "SL2", "SL4", "SL6", "OAL",
    "CH", "CL", "CD", "FH", "FL", "HF", "RF", "TF", "BF", "RB",
    "I1", "I3", "I5", "I7", "S1", "S3", "S5", "S7",
    "O2", "O4", "O6", "O8", "R2", "R4", "R6", "R8",
    "X",
]
_CALLOUT_RE = re.compile(
    r"^([\d.]+)\s+(" + "|".join(sorted(_DIM_LABELS, key=len, reverse=True)) + r")$"
)
# Title-block summary column header -> slot id (drawing-area value reused).
_TB_COLUMN_SLOT = {
    "ROWS": "slot.ROWS", "FH": "slot.FH", "FL": "slot.FL", "CH": "slot.CH",
    "CL": "slot.CL", "CD": "slot.CD", "HD": "slot.HD2", "OAL": "slot.OAL",
    "SL": "slot.SL2", "I": "slot.I1", "S": "slot.S1", "O": "slot.O2",
    "R": "slot.R2", "TF": "slot.TF", "BF": "slot.BF", "HF": "slot.HF",
    "RF": "slot.RF", "RB": "slot.RB",
}
# Side-panel heading -> slot id. The FIRST value line under a heading takes the
# bare slot; subsequent lines take slot_2, slot_3 (see _side_panel_map).
_PANEL_HEADING_SLOT = {
    "TUBE MATERIAL": "slot.TUBE_MATERIAL",
    "FIN MATERIAL": "slot.FIN_MATERIAL",
    "CASING MATERIAL": "slot.CASING_MATERIAL",
    "COIL TUBE FACE": "slot.COIL_TUBE_FACE",
    "CIRCUITING": "slot.CIRCUITING",
    "HEADER MATERIAL": "slot.HEADER_MATERIAL",
    "DISTRIBUTORS": "slot.DISTRIBUTORS",
    "SUPPLY CONN SIZE": "slot.SUPPLY_CONN_SIZE",
    "RETURN CONN SIZE": "slot.RETURN_CONN_SIZE",
    "FASTENER TYPE": "slot.FASTENER_TYPE",
    "DRY WEIGHT": "slot.DRY_WEIGHT",
    "INTERNAL VOLUME": "slot.INTERNAL_VOLUME",
}
# Generic boilerplate at the foot of the spec panel — never tokenized; its
# appearance also ends the current section's value capture.
_PANEL_BOILERPLATE_RE = re.compile(
    r"TUBE SUPPORTS|ALL COILS ARE TESTED|P\.S\.I|DRY NITROGEN|DRAWING CREATED|"
    r"COILS OVER|PROPERTY OF|REPRODUCED",
    re.I,
)
# CoilMaster identity to strip (de-brand -> Oxygen8 own drawing, review aid).
_COILMASTER_NOTE = "Coilmaster will revise any drawing that contains component interferences"
_MODEL_RE = re.compile(r"^[A-Z]{2}-[A-Z]-[A-Z]-[\d.x-]+-[LR]$")


@dataclass
class SeedResult:
    svg: str
    slot_ids: set[str] = field(default_factory=set)
    reference: dict[str, str] = field(default_factory=dict)


def populate(svg: str, values: dict[str, str], *, blank: str = "") -> str:
    import html as _html
    import re as _re

    for slot in set(_re.findall(r"\{\{(slot\.[A-Za-z0-9_]+)\}\}", svg)):
        svg = svg.replace("{{" + slot + "}}", _html.escape(values.get(slot, blank)))
    return svg


def _first_xy(tspan_attrs: str) -> tuple[float, float] | None:
    xm = re.search(r'x="([\-\d.]+)', tspan_attrs)
    ym = re.search(r'y="([\-\d.]+)"', tspan_attrs)
    if not xm or not ym:
        return None
    return float(xm.group(1)), float(ym.group(1))


def _text_attrs(attrs: str) -> str:
    """Keep font-size/fill/font-family/transform from the original <text>."""
    keep = []
    for name in ("font-size", "fill", "font-family", "transform", "xml:space"):
        m = re.search(rf'{name}="([^"]*)"', attrs)
        if m:
            keep.append(f'{name}="{m.group(1)}"')
    if not any(a.startswith("font-family") for a in keep):
        keep.append('font-family="Arial"')
    return " " + " ".join(keep)


def _build_value_words(page: fitz.Page) -> dict[str, list]:
    """Group words by (block,line) for callout label-adjacency + title block."""
    by_line: dict[tuple[int, int], list] = {}
    for w in page.get_text("words"):
        by_line.setdefault((w[5], w[6]), []).append(w)
    for ws in by_line.values():
        ws.sort(key=lambda w: w[0])
    return by_line


def _pick_drawing_page(doc: "fitz.Document") -> "fitz.Page":
    """The drawing page = the one with the most dimension-callout 'VALUE LABEL'
    pairs (some submittals put a cover/info page before the drawing)."""
    best, best_score = doc[0], -1
    for page in doc:
        text = page.get_text()
        score = len(re.findall(r"[\d.]+\s+(?:" + "|".join(_DIM_LABELS) + r")\b", text))
        if score > best_score:
            best, best_score = page, score
    return best


def seed_pdf(pdf_path: Path) -> SeedResult:
    page = _pick_drawing_page(fitz.open(pdf_path))
    svg = page.get_svg_image(text_as_path=False)
    used: set[str] = set()

    tb_tokens = _title_block_tokens(page)        # [(x0, slot)] per value column
    panel_map = _side_panel_map(page)            # {value_text: slot}
    ref: dict[str, str] = {}

    def rewrite_text(m: re.Match[str]) -> str:
        attrs, inner = m.group(1), m.group(2)
        content = re.sub(r"<[^>]+>", "", inner).strip()
        keep = _text_attrs(attrs)

        def single(text: str) -> str:
            t = re.search(r"<tspan\b([^>]*)>", inner)
            xy = _first_xy(t.group(1)) if t else None
            x, y = (xy if xy else (0.0, 0.0))
            return f"<text{keep}><tspan x=\"{x:.2f}\" y=\"{y:.2f}\">{text}</tspan></text>"

        # 1) Drawing-area dimension callout: "VALUE LABEL".
        cm = _CALLOUT_RE.match(content)
        if cm:
            slot = f"slot.{cm.group(2)}"
            used.add(slot)
            ref[slot] = cm.group(1)
            return single(f"{{{{{slot}}}}} {cm.group(2)}")

        # 2) Title-block summary row (headers + glued values in two tspans).
        if _looks_like_title_block(content) and tb_tokens:
            for _, slot, value in tb_tokens:
                used.add(slot)
                ref.setdefault(slot, value)
            return _rewrite_title_block(attrs, inner, [(x, s) for x, s, _ in tb_tokens])

        # 3) Multi-line element with tag / model / side-panel values: per-tspan.
        new_inner, hit = _rewrite_tspans(inner, used, panel_map, ref)
        if hit:
            return f"<text{attrs}>{new_inner}</text>"
        return m.group(0)

    svg = re.sub(r"<text\b([^>]*)>(.*?)</text>", rewrite_text, svg, flags=re.S)
    svg = debrand(svg)  # CoilMaster identity removed -> Oxygen8's own drawing
    return SeedResult(svg=svg, slot_ids=used, reference=ref)


def _looks_like_title_block(content: str) -> bool:
    return content.startswith("ROWS") and "OAL" in content and "RB" in content


def _title_block_tokens(page: fitz.Page) -> list[tuple[float, str]]:
    """Return [(x0, slot_id)] for each title-block summary value column.

    Header labels and values are each their own word; gather by y-band and map
    every value to the nearest header column by x-centre.
    """
    words = page.get_text("words")
    label_words = [w for w in words if w[4] in _TB_COLUMN_SLOT or w[4] == "X"]
    if not label_words:
        return []
    # The title-block header row is the y-band where the MOST labels co-occur
    # (drawing-area labels appear singly at scattered y values).
    counts: dict[int, int] = {}
    for w in label_words:
        counts[round(w[1])] = counts.get(round(w[1]), 0) + 1
    header_y = max(counts, key=lambda y: (counts[y], y))
    if counts[header_y] < 6:  # not a real summary row
        return []
    header = [w for w in label_words if abs(w[1] - header_y) < 4]
    values = [
        w for w in words
        if re.fullmatch(r"[\d.]+", w[4]) and header_y < w[1] < header_y + 25
    ]
    if not values:
        return []
    cols = [((w[0] + w[2]) / 2, w[4]) for w in header]
    tokens: list[tuple[float, str, str]] = []
    for vw in sorted(values, key=lambda w: w[0]):
        cx = (vw[0] + vw[2]) / 2
        label = min(cols, key=lambda c: abs(c[0] - cx))[1]
        slot = _TB_COLUMN_SLOT.get(label)
        if slot:
            tokens.append((vw[0], slot, vw[4]))
    return tokens


def _side_panel_map(page: fitz.Page) -> dict[str, str]:
    """{value-line-text: slot_id} for each right-column spec section.

    First value line under a heading -> bare slot; subsequent lines -> slot_2,
    slot_3 (capped at 3). Generic boilerplate ends the section so the bottom
    title-block / test notes are never tokenized.
    """
    lines: list[tuple[float, float, str]] = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            txt = "".join(s["text"] for s in ln["spans"]).strip()
            x0, y0 = ln["bbox"][0], ln["bbox"][1]
            if txt and x0 > 600:  # right spec column
                lines.append((y0, x0, txt))
    lines.sort()
    mapping: dict[str, str] = {}
    current: str | None = None
    idx = 0
    for _, _, txt in lines:
        if txt in _PANEL_HEADING_SLOT:
            current, idx = _PANEL_HEADING_SLOT[txt], 0
            continue
        if _PANEL_BOILERPLATE_RE.search(txt):
            current = None
            continue
        if current and idx < 3:
            idx += 1
            mapping.setdefault(txt, current if idx == 1 else f"{current}_{idx}")
    return mapping


def _rewrite_title_block(attrs: str, inner: str, tokens: list[tuple[float, str]]) -> str:
    """Keep the header tspan, replace the glued value tspan with per-column tspans."""
    tspans = list(re.finditer(r"<tspan\b([^>]*)>(.*?)</tspan>", inner, re.S))
    out = f"<text{attrs}>"
    for t in tspans:
        txt = re.sub(r"<[^>]+>", "", t.group(2))
        if re.search(r"[A-Za-z]", txt):  # header tspan -> keep
            out += t.group(0)
            continue
        # value tspan -> rebuild as per-column tokens
        ym = re.search(r'y="([\-\d.]+)"', t.group(1))
        y = ym.group(1) if ym else "0"
        for x0, slot in tokens:
            out += f'<tspan x="{x0:.2f}" y="{y}">{{{{{slot}}}}} </tspan>'
    out += "</text>"
    return out


def _rewrite_tspans(
    inner: str, used: set[str], panel_map: dict[str, str], ref: dict[str, str]
) -> tuple[str, bool]:
    """Swap individual value tspans (tag, model, side-panel values) for tokens."""
    hit = False

    def fix(t: re.Match[str]) -> str:
        nonlocal hit
        attrs, txt = t.group(1), t.group(2)
        plain = re.sub(r"<[^>]+>", "", txt).strip()
        token = None
        if plain.startswith("Tag:"):
            token = "Tag: {{slot.TAG}}"
            used.add("slot.TAG")
            ref["slot.TAG"] = plain[4:].strip()
        elif _MODEL_RE.match(plain):
            token = "{{slot.MODEL_NUMBER}}"
            used.add("slot.MODEL_NUMBER")
            ref["slot.MODEL_NUMBER"] = plain
        elif re.fullmatch(r"\d+\s*Feed\s*/\s*\d+\s*Pass", plain):
            token = "{{slot.CIRCUITING}}"
            used.add("slot.CIRCUITING")
            ref["slot.CIRCUITING"] = plain
        elif plain in panel_map:
            slot = panel_map[plain]
            token = f"{{{{{slot}}}}}"
            used.add(slot)
            ref[slot] = plain
        if token is None:
            return t.group(0)
        hit = True
        return f"<tspan{attrs}>{token}</tspan>"

    new_inner = re.sub(r"<tspan\b([^>]*)>(.*?)</tspan>", fix, inner, flags=re.S)
    return new_inner, hit


def _is_other_heading(text: str) -> bool:
    return text in {"FASTENER TYPE", "DRY WEIGHT", "INTERNAL VOLUME"}


# Coil-drawing region (page points): the central illustration + dimension lines
# + callouts. Excludes the title block (y>~495), side spec panel (x>~640),
# top notes (y<~95) and the bottom-left logo. Mirroring is restricted to this
# region so the sheet furniture stays in place.
_COIL_REGION = (150.0, 640.0, 95.0, 492.0)  # x0, x1, y0, y1
_PAGE_H = 612.0


def _path_bbox(attrs: str, d: str) -> tuple[float, float, float, float] | None:
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


def _in_region(cx: float, cy: float, region: tuple) -> bool:
    x0, x1, y0, y1 = region
    return x0 <= cx <= x1 and y0 <= cy <= y1


def mirror_svg(svg: str, region: tuple = _COIL_REGION) -> str:
    """Horizontally mirror only the coil-drawing region of the PDF-derived SVG.

    The coil illustration + dimension lines reflect about the region's own
    centre (so connections swap to the opposite hand) while the title block,
    side spec panel, notes and logo stay exactly where they are. Dimension-text
    glyphs are counter-flipped so they remain readable. Review aid only;
    engineering must confirm the mirrored handing geometry.
    """
    m = re.search(r"<svg[^>]*>\s*", svg)
    head, rest = svg[: m.end()], svg[m.end():]
    split = rest.find('<g id="zone.review_metadata">')
    if split == -1:
        split = rest.rfind("</svg>")
    content, trailer = rest[:split], rest[split:]

    # Pass 1: find the region elements and their combined bbox -> mirror axis cx.
    region_xs: list[float] = []

    def scan(mm: re.Match[str]) -> None:
        tag = mm.group(1)
        if tag == "text":
            xy = _text_xy(mm.group(2), mm.group(3))
            if xy and _in_region(xy[0], xy[1], region):
                region_xs.extend([xy[0], xy[0]])
        elif tag == "path":
            dm = re.search(r'\bd="([^"]*)"', mm.group(0))
            bb = _path_bbox(mm.group(2), dm.group(1)) if dm else None
            if bb and _in_region((bb[0] + bb[1]) / 2, (bb[2] + bb[3]) / 2, region):
                region_xs.extend([bb[0], bb[1]])

    for mm in re.finditer(r"<(path|text|image)\b([^>]*?)(?:>(.*?)</\1>|/>)", content, re.S):
        scan(mm)
    if not region_xs:
        return svg
    cx = (min(region_xs) + max(region_xs)) / 2

    # Pass 2: pull region elements out, counter-flip region texts, wrap in the
    # reflection group; leave everything else exactly where it is.
    region_chunks: list[str] = []

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
            region_chunks.append(f"<text{new_attrs}>{body}</text>")
            return ""
        if tag == "path":
            dm = re.search(r'\bd="([^"]*)"', whole)
            bb = _path_bbox(attrs, dm.group(1)) if dm else None
            if bb and _in_region((bb[0] + bb[1]) / 2, (bb[2] + bb[3]) / 2, region):
                region_chunks.append(whole)
                return ""
        return whole

    content = re.sub(
        r"<(path|text)\b([^>]*?)(?:>(.*?)</\1>|/>)", take, content, flags=re.S
    )
    flip = (
        f'<g transform="matrix(-1 0 0 1 {2 * cx:.2f} 0)">'
        + "".join(region_chunks)
        + "</g>"
    )
    return f"{head}{content}{flip}{trailer}"


def debrand(svg: str) -> str:
    """Remove CoilMaster identity so the drawing is Oxygen8's own (CoilMaster
    *style* only): drop the logo image, the "Coilmaster will revise" note, the
    "PROPERTY OF COILMASTER" legal block and the CoilMaster drafter name; drop an
    OXYGEN8 wordmark placeholder into the logo cell (swap for the real logo asset
    when provided). Style/layout/dimensions are untouched.
    """
    # 1. Logo image group (tiny-scale matrix wrapping an <image>) -> OXYGEN8 wordmark.
    svg = re.sub(
        r'<g transform="matrix\(\.\d[^"]*"\s*>\s*<image\b.*?</g>',
        '<text x="54" y="560" font-family="Arial" font-size="16" '
        'font-weight="bold" fill="#0f3d62">OXYGEN8</text>',
        svg, flags=re.S, count=1,
    )

    # 2. "PROPERTY OF COILMASTER ..." legal <text> element -> remove entirely.
    def drop_legal(m: re.Match[str]) -> str:
        return "" if "PROPERTY OF" in m.group(0) and "COILMASTER" in m.group(0) else m.group(0)

    svg = re.sub(r"<text\b[^>]*>.*?</text>", drop_legal, svg, flags=re.S)

    # 3. "Coilmaster will revise ..." note (any occurrence) -> remove.
    svg = svg.replace(_COILMASTER_NOTE, "")
    # 4. CoilMaster drafter name after "Qty: N" -> remove, keep the quantity.
    svg = re.sub(r"(Qty:\s*\d+)\s*[A-Z]\.\s*[A-Za-z]+", r"\1", svg)
    return svg


_SLOT_TSPAN_RE = re.compile(
    r'(<tspan\b[^>]*\bx=")([^"]*)("[^>]*>)(.*?)(</tspan>)', re.S
)


def collapse_slot_tspans(svg: str) -> str:
    """Collapse per-glyph x-lists on placeholder-bearing tspans to a single x.

    PyMuPDF emits one x coordinate per character of the *original* value. When a
    slot is substituted with a different-length string (notably the multi-word
    'REVIEW REQUIRED' placeholder), those fixed per-glyph positions pin the new
    characters to the old slots and smear/overlap. Keeping only the first x lets
    the substituted text flow naturally with the font's own kerning.
    """

    def _fix(match: re.Match) -> str:
        head, x_list, mid, body, tail = match.groups()
        if "{{slot." not in body:
            return match.group(0)
        first_x = x_list.split()[0] if x_list.split() else x_list
        return f"{head}{first_x}{mid}{body}{tail}"

    return _SLOT_TSPAN_RE.sub(_fix, svg)


def finalize(svg: str, template_id: str, height: float = 612.0) -> str:
    """Add the review-aid watermark + template identity line before </svg>."""
    svg = collapse_slot_tspans(svg)
    band = (
        f'<g id="zone.review_metadata">'
        f'<text x="8" y="{height - 4:.0f}" font-family="Arial" font-size="7" '
        f'fill="#b91c1c" font-weight="bold">REVIEW AID - NOT FOR MANUFACTURING '
        f'&#183; template_id={template_id} &#183; export_allowed=false '
        f'&#183; production_approved=false</text></g>'
    )
    return svg.replace("</svg>", band + "</svg>")


# Bucket -> source. PDF buckets seed from a provided EZ drawing; mirror buckets
# reflect a seeded LH/RH pair. (DX H4, HGRH H3/H4 have no reference -> left blocked.)
_REQUIRED_SLOTS = {
    "slot.FH", "slot.FL", "slot.CH", "slot.CL", "slot.CD", "slot.TF", "slot.BF",
    "slot.HDx1", "slot.HD2", "slot.ROWS", "slot.TAG", "slot.MODEL_NUMBER",
}
BUCKETS = [
    # template_id, category_dir, coil_category, hand, header_type, special, src
    ("coilmaster_dx_lh_header1", "dx", "DX", "LH", "Header 1", None,
     "Case/#2/EZC-0001 - DX_1_LH/CDXC-1.pdf", "EZC-0001"),
    ("coilmaster_dx_rh_header2", "dx", "DX", "RH", "Header 2", None,
     "Case/#2/EZC-0011 - DX_2_RH/CDXC-2.pdf", "EZC-0011"),
    ("coilmaster_dx_lh_header3", "dx", "DX", "LH", "Header 3", None,
     "Case/#2/EZC-0007 - DX_3_LH/CDXC-1.pdf", "EZC-0007"),
    # 2026-06-23: re-seeded from a more complete HG_1_LH reference (John). The
    # original EZC-0002 drawing lacked header/stubout dimension callouts, so
    # I1/S1/O2/R2/HD2/SL2 baked into the NOTES text instead of slotting; the new
    # reference carries them as real callouts -> they redact to slots cleanly.
    ("coilmaster_hgrh_lh_header1", "hgrh", "HGRH", "LH", "Header 1", None,
     "Case/feed/HG_1_LH/HG_1_LH.pdf", "FEED-HG_1_LH"),
    ("coilmaster_hgrh_rh_header1", "hgrh", "HGRH", "RH", "Header 1", None,
     "Case/#2/EZC-0012 - HG_1_RH/RHHGRC-2.pdf", "EZC-0012"),
    ("coilmaster_hgrh_lh_header2", "hgrh", "HGRH", "LH", "Header 2", None,
     "Case/#2/EZC-0008 - HG_2_LH/RHHGRC-1.pdf", "EZC-0008"),
    ("coilmaster_hgrh_rh_header3", "hgrh", "HGRH", "RH", "Header 3", None,
     "Case/#3/EZC-0016 - HG_3_RH/RHHGRC-1.pdf", "EZC-0016"),
    ("coilmaster_cwc_lh", "cwc", "CWC", "LH", "Header 1", None,
     "Case/#2/EZC-0014 - CW_LH/CCWC-1.pdf", "EZC-0014"),
    ("coilmaster_hwc_lh", "hwc", "HWC", "LH", "Header 1", None,
     "Case/#2/EZC-0005 - HW_LH/PHWC-1.pdf", "EZC-0005"),
    ("coilmaster_dx_lh_hgbp", "dx", "DX", "LH", None, "HGBP",
     "Case/#2/EZC-0013 - DX_HB_LH/CDXC-1.pdf", "EZC-0013"),
    # --- 2026-06-21: the 8 former mirror hands + the 4 header-4 buckets are now
    # seeded from real per-hand EZ drawing PDFs provided in Case/feed/. Mirroring
    # is retired (it smeared callouts); MIRRORS is now empty. source_case_id is a
    # provenance token until real EZC IDs are supplied.
    ("coilmaster_dx_rh_header1", "dx", "DX", "RH", "Header 1", None,
     "Case/feed/DX_1_RH/DX_1_RH.pdf", "FEED-DX_1_RH"),
    ("coilmaster_dx_lh_header2", "dx", "DX", "LH", "Header 2", None,
     "Case/feed/DX_2_LH/DX_2_LH.pdf", "FEED-DX_2_LH"),
    ("coilmaster_dx_rh_header3", "dx", "DX", "RH", "Header 3", None,
     "Case/feed/DX_3_RH/DX_3_RH.pdf", "FEED-DX_3_RH"),
    ("coilmaster_dx_rh_hgbp", "dx", "DX", "RH", None, "HGBP",
     "Case/feed/DX_HB_RH/DX_HB_RH.pdf", "FEED-DX_HB_RH"),
    ("coilmaster_hgrh_rh_header2", "hgrh", "HGRH", "RH", "Header 2", None,
     "Case/feed/HG_2_RH/HG_2_RH.pdf", "FEED-HG_2_RH"),
    ("coilmaster_hgrh_lh_header3", "hgrh", "HGRH", "LH", "Header 3", None,
     "Case/feed/HG_3_LH/HG_3_LH.pdf", "FEED-HG_3_LH"),
    ("coilmaster_cwc_rh", "cwc", "CWC", "RH", "Header 1", None,
     "Case/feed/CW_RH/CW_RH.pdf", "FEED-CW_RH"),
    ("coilmaster_hwc_rh", "hwc", "HWC", "RH", "Header 1", None,
     "Case/feed/HW_RH/HW_RH.pdf", "FEED-HW_RH"),
    ("coilmaster_dx_lh_header4", "dx", "DX", "LH", "Header 4", None,
     "Case/feed/DX_4_LH/DX_4_LH.pdf", "FEED-DX_4_LH"),
    ("coilmaster_dx_rh_header4", "dx", "DX", "RH", "Header 4", None,
     "Case/feed/DX_4_RH/DX_4_RH.pdf", "FEED-DX_4_RH"),
    ("coilmaster_hgrh_lh_header4", "hgrh", "HGRH", "LH", "Header 4", None,
     "Case/feed/HG_4_LH/HG_4_LH.pdf", "FEED-HG_4_LH"),
    ("coilmaster_hgrh_rh_header4", "hgrh", "HGRH", "RH", "Header 4", None,
     "Case/feed/HG_4_RH/HG_4_RH.pdf", "FEED-HG_4_RH"),
]
# Mirroring retired (John, 2026-06-17/2026-06-21): every hand is now seeded from
# its own real PDF. The mirror.py helper is retained for possible future use but
# activates no template.
MIRRORS: list[tuple[str, str, str]] = []


def _slot_map(template_id: str, slot_ids: set[str]) -> dict:
    slots = []
    for sid in sorted(slot_ids):
        slots.append({
            "slot_id": sid,
            "label": sid.replace("slot.", ""),
            "required_for_preview": sid in _REQUIRED_SLOTS,
            "review_status": "review_required",
            "source_candidates": ["pdf_drawing_value_redacted_to_slot"],
            "notes": "Seeded from the provided EZ drawing PDF; review required.",
        })
    return {
        "template_id": template_id,
        "schema_version": "template-first.1",
        "source_policy": [
            "reviewed_canonical_value", "ez_json_evidence",
            "source_pdf_candidate", "manual_reviewed_value",
            "blocked_or_review_required",
        ],
        "slots": slots,
    }


def build_bucket(spec: tuple) -> set[str]:
    template_id, cat_dir, coil_cat, hand, header_type, special, src, case_id = spec
    out_dir = REPO_ROOT / "templates" / "drawing" / "coilmaster" / cat_dir / template_id
    out_dir.mkdir(parents=True, exist_ok=True)
    res = seed_pdf(REPO_ROOT / src)
    (out_dir / "template.svg").write_text(finalize(res.svg, template_id), encoding="utf-8")
    src_folder = str(Path(src).parent).replace("\\", "/")
    page_count = fitz.open(REPO_ROOT / src).page_count
    # slot_map: preserve hand-authored entries, but MERGE in any new slot ids the
    # template now uses (additive; tests check the slot set with >=, so safe).
    slot_map_path = out_dir / "slot_map.json"
    if slot_map_path.exists():
        existing = json.loads(slot_map_path.read_text(encoding="utf-8"))
        have = {s["slot_id"] for s in existing.get("slots", [])}
        added = [s for s in _slot_map(template_id, res.slot_ids)["slots"] if s["slot_id"] not in have]
        if added:
            existing["slots"].extend(added)
            slot_map_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    else:
        slot_map_path.write_text(json.dumps(_slot_map(template_id, res.slot_ids), indent=2), encoding="utf-8")
    if (out_dir / "template_metadata.json").exists() and (out_dir / "seed_evidence.json").exists():
        return res.slot_ids
    (out_dir / "template_metadata.json").write_text(json.dumps({
        "template_id": template_id, "schema_version": "template-first.1",
        "supplier": "coilmaster", "coil_category": coil_cat, "coil_hand": hand,
        "header_type": header_type, "special_feature": special,
        "status": "active_review_aid", "source_case_id": case_id,
        "source_folder": src_folder,
        "seed_method": "vectorised_from_provided_ez_drawing_pdf_values_redacted_to_slots",
        "review_status": "review_required", "release_status": "review_aid_only",
        "export_allowed": False, "production_approved": False, "pdf_export_enabled": False,
        "notes": [
            "Artwork is the vectorised EZ drawing with values replaced by slots.",
            "Raw PDFs are not copied into this template folder.",
            "Review aid only; engineering must confirm before any use.",
        ],
    }, indent=2), encoding="utf-8")
    slot_evidence = [
        {
            "slot_id": sid,
            "value": str(res.reference.get(sid, "review_required")),
            "source_channels": ["ez_drawing_pdf"],
            "review_status": "review_required",
        }
        for sid in sorted(res.slot_ids)
    ]
    (out_dir / "seed_evidence.json").write_text(json.dumps({
        "schema_version": "template-first.1", "template_id": template_id,
        "source_case_id": case_id, "supplier": "coilmaster",
        "coil_category": coil_cat, "coil_hand": hand,
        "header_type": header_type or "HGBP", "source_folder": src_folder,
        "intake_status": "seeded_review_required", "review_status": "review_required",
        "release_status": "review_aid_only", "export_allowed": False,
        "production_approved": False, "pdf_export_enabled": False,
        "source_files": [{
            "role": "ez_drawing_pdf", "filename": Path(src).name,
            "filename_policy": "not_committed", "page_count": page_count,
            "committed_copy": False,
            "notes": "Vectorised to a slotted review template; raw PDF not copied.",
        }],
        "slot_evidence": slot_evidence, "observed_candidates": [],
    }, indent=2), encoding="utf-8")
    return res.slot_ids


def build_all() -> None:
    for spec in BUCKETS:
        ids = build_bucket(spec)
        print(f"seeded {spec[0]:32} slots={len(ids)}")
    from coilforge.template_population.mirror import create_mirror
    for rh_id, cat_dir, lh_id in MIRRORS:
        made = create_mirror(lh_id, category=cat_dir)
        assert made == rh_id, f"{made} != {rh_id}"
        print(f"mirrored {rh_id:32} <- {lh_id}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "build-all":
        sys.path.insert(0, str(REPO_ROOT / "src"))
        build_all()
        raise SystemExit(0)

    src = sys.argv[1] if len(sys.argv) > 1 else "Case/#2/EZC-0001 - DX_1_LH/CDXC-1.pdf"
    name = sys.argv[2] if len(sys.argv) > 2 else "seed_dx1_lh"
    res = seed_pdf(REPO_ROOT / src)
    out = REPO_ROOT / "build/case_probe" / f"{name}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(res.svg, encoding="utf-8")
    # Reference-populated proof: tokens filled with the source coil's own values
    # (should render identical to the source PDF -> confirms format fidelity).
    (REPO_ROOT / "build/case_probe" / f"{name}_ref.svg").write_text(
        populate(res.svg, res.reference, blank="REVIEW REQUIRED"), encoding="utf-8"
    )
    print("slots:", len(res.slot_ids), sorted(res.slot_ids))
    print("tokens in svg:", res.svg.count("{{slot."))
    print("written:", out)
