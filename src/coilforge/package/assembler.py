"""Assemble the outgoing drawing package (quote-prep review aid).

``assemble_drawing_package`` takes the Direct Coil drawing PDF and CoilForge's
own drawing SVG, appends our drawing *after* the Direct Coil pages, and stamps:

* the copper-strap requirement (computed upstream from header count x coil type),
* any uncertain-mapping callouts (review-required / mismatch slots),
* a review-aid watermark.

Pure function over bytes — no disk writes. Safety flags are hard-wired off:
the package is a watermarked review aid, never a production-approved export.
"""

from __future__ import annotations

import base64
import re

from pydantic import BaseModel, ConfigDict, Field

from coilforge.package.svg_to_pdf import svg_to_pdf_bytes
from coilforge.submittal.pdf_intake import coil_tag_aliases

# Same wording as phase2a/renderer.py + template_population/slot_population.py.
REVIEW_WATERMARK = "REVIEW AID - NOT FOR MANUFACTURING"

# Top band on an inserted CoilForge drawing page. Tall enough to fully cover the drawing
# SVG's own top-left "Tag: X" label (bottom edge y=18.7 -- see _stamp_watermark_banner),
# so the label is covered rather than half-clipped and the band can re-print the tag.
_BANNER_HEIGHT = 20.0
_BANNER_TEXT_BASELINE = 13.0

# Drawing pages carry these geometry callouts; report/quote pages do not.
_DRAWING_MARKER_RE = re.compile(r"\bF\.L\.|\bF\.H\.|\bFIN\b|\bO\.D\.", re.IGNORECASE)


class PackageResult(BaseModel):
    """Combined-package outcome. ``pdf_base64`` is the merged PDF, base64-encoded."""

    model_config = ConfigDict(extra="forbid")

    pdf_base64: str
    page_count: int
    direct_coil_page_count: int
    coilforge_page_index: int  # 0-based index of the first appended CoilForge page
    copper_strap_note: str
    review_markups: list[str] = Field(default_factory=list)
    watermarked: bool = True
    # Safety contract — never relaxed by this layer.
    export_allowed: bool = False
    production_drawing_approval_claimed: bool = False
    raw_private_data_returned: bool = False


def _stamp_pages(doc, copper_strap_note: str, review_markups: list[str], watermark: bool) -> None:
    """Stamp the copper-strap banner and watermark on every page of ``doc``.

    Stamps sit inside an opaque banner (like a drawing's revision band) so they
    stay legible regardless of the underlying drawing geometry. ``review_markups``
    (engine suggestion/missing-input bucket dumps) are intentionally NOT stamped —
    they belong in the on-screen review surface, not on the outgoing drawing.
    """
    import fitz

    lines: list[tuple[str, float, tuple[float, float, float]]] = []
    if watermark:
        lines.append((REVIEW_WATERMARK, 9, (0.80, 0.0, 0.0)))
    if copper_strap_note:  # water coils carry no strap note -> no banner line
        lines.append((copper_strap_note, 11, (0.0, 0.0, 0.55)))

    pad = 8.0
    band_height = pad + sum(size + 5 for _, size, _ in lines)
    for page in doc:
        width = page.rect.width
        page.draw_rect(
            fitz.Rect(0, 0, width, band_height),
            color=(0.70, 0.70, 0.70),
            fill=(1.0, 1.0, 1.0),
            width=0.6,
        )
        y = pad + 6
        for text, size, color in lines:
            page.insert_text((12, y), text, fontsize=size, color=color)
            y += size + 5


def assemble_drawing_package(
    *,
    direct_coil_pdf: bytes,
    coilforge_drawing_svg: str,
    copper_strap_note: str,
    review_markups: list[str] | None = None,
    watermark: bool = True,
) -> PackageResult:
    """Merge ``[Direct Coil pages] + [CoilForge drawing page]`` into one PDF.

    Raises ``ValueError`` if either input cannot be parsed.
    """
    if not direct_coil_pdf:
        raise ValueError("assemble_drawing_package: direct_coil_pdf is empty")
    markups = list(review_markups or [])

    import fitz  # PyMuPDF — lazy import (see submittal/pdf_intake.py)

    our_pdf_bytes = svg_to_pdf_bytes(coilforge_drawing_svg)

    try:
        dc_doc = fitz.open(stream=direct_coil_pdf, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 — surface a clean contract error
        raise ValueError(f"assemble_drawing_package: unreadable Direct Coil PDF ({exc})") from exc

    our_doc = fitz.open(stream=our_pdf_bytes, filetype="pdf")
    out = fitz.open()
    try:
        # Stamp ONLY our appended page(s) — never annotate the third-party
        # Direct Coil drawing, which is passed through unmodified.
        _stamp_pages(our_doc, copper_strap_note, markups, watermark)
        out.insert_pdf(dc_doc)  # Direct Coil drawing first ...
        dc_page_count = dc_doc.page_count
        out.insert_pdf(our_doc)  # ... CoilForge drawing appended right after.
        combined = out.tobytes()
        page_count = out.page_count
    finally:
        out.close()
        our_doc.close()
        dc_doc.close()

    return PackageResult(
        pdf_base64=base64.b64encode(combined).decode("ascii"),
        page_count=page_count,
        direct_coil_page_count=dc_page_count,
        coilforge_page_index=dc_page_count,
        copper_strap_note=copper_strap_note,
        review_markups=markups,
        watermarked=watermark,
    )


# --------------------------------------------------------------------------- #
# Multi-coil quote package (steps 9-12, evolved): one Direct Coil quote+report+
# drawing PDF in -> our drawing inserted right after each coil's drawing page,
# plus a copper-strap price note above each coil's quoted price. Source pages are
# passed through unmodified except for the added review-aid note/watermark
# overlays; quote numbers are never changed.
# --------------------------------------------------------------------------- #
class MultiCoilPackageResult(BaseModel):
    """Outcome of the multi-coil quote package. ``pdf_base64`` is the merged PDF."""

    model_config = ConfigDict(extra="forbid")

    pdf_base64: str
    page_count: int
    source_page_count: int
    inserted_coil_count: int
    coils: list[dict] = Field(default_factory=list)
    quote_page_index: int | None = None  # 0-based source index of the FIRST stamped quote page
    quote_page_indices: list[int] = Field(default_factory=list)  # every stamped quote page
    watermarked: bool = True
    # Safety contract — never relaxed by this layer.
    export_allowed: bool = False
    production_drawing_approval_claimed: bool = False
    raw_private_data_returned: bool = False


def _coil_drawing_page_index(doc, tag: str) -> int | None:
    """0-based index of a coil's DRAWING page in the source PDF.

    The drawing page contains the coil tag and drawing-geometry markers (F.L./FIN/
    O.D.) but is not the textual REPORT/QUOTE page. Prefer such a page (latest if
    several); else fall back to the latest non-quote page bearing the tag.

    The tag is matched across category-prefix aliases (e.g. a reviewed ``RHHGRH-1``
    matches a source page that spells the same coil ``RHHGRC-1``) so a spelling
    difference never silently drops a coil.
    """
    aliases = tuple(alias.upper() for alias in coil_tag_aliases(tag))
    hits: list[tuple[int, bool, bool]] = []
    for i in range(doc.page_count):
        upper = doc[i].get_text().upper()
        if not any(alias in upper for alias in aliases):
            continue
        is_textual = "REPORT" in upper or "COIL QUOTE" in upper
        has_drawing = bool(_DRAWING_MARKER_RE.search(doc[i].get_text()))
        hits.append((i, has_drawing, is_textual))
    drawing_pages = [i for i, has_drawing, is_textual in hits if has_drawing and not is_textual]
    if drawing_pages:
        return drawing_pages[-1]
    non_quote = [i for i, _hd, is_textual in hits if not ("COIL QUOTE" in doc[i].get_text().upper())]
    if non_quote:
        return non_quote[-1]
    return hits[-1][0] if hits else None


def _quote_page_indices(doc) -> list[int]:
    """0-based indices of EVERY page carrying quoted pricing rows.

    A many-coil quote schedule spills onto page 2+, and those continuation pages
    carry the per-row ``Cost Each`` anchor but NOT the ``COIL QUOTE`` header (which
    prints only on the first schedule page). ``Cost Each`` is the marker
    ``_stamp_quote_price_notes`` actually needs, so keying on it finds every pricing
    page — a ``COIL QUOTE`` page without any ``Cost Each`` row has nothing to stamp.
    """
    return [i for i in range(doc.page_count) if "COST EACH" in doc[i].get_text().upper()]


def _quote_page_index(doc) -> int | None:
    """First quote page (back-compat scalar; see ``_quote_page_indices``)."""
    indices = _quote_page_indices(doc)
    return indices[0] if indices else None


def _stamp_watermark_banner(page, tag: str | None = None) -> None:
    """Thin opaque watermark band at the top of an inserted CoilForge drawing page.

    The drawing SVG stamps its own ``Tag: X`` label at the crop's top-left, which lands
    at page y 2.2-18.7 — i.e. underneath this band. The band is opaque, so it BURIES the
    label and leaves only a clipped descender fragment poking out (what John saw on the
    quote package). Two things follow, and both are load-bearing:

    * ``_BANNER_HEIGHT`` must fully cover that label — a shorter band clips it instead of
      covering it;
    * the tag is re-printed HERE, on top of the band, where nothing can hide it.

    Placing the tag anywhere lower in the SVG is not an option: every page-relative row
    from y~20 down carries real drawing geometry on at least one seeded template.
    """
    import fitz

    width = page.rect.width
    page.draw_rect(
        fitz.Rect(0, 0, width, _BANNER_HEIGHT),
        color=(0.70, 0.70, 0.70),
        fill=(1.0, 1.0, 1.0),
        width=0.5,
    )
    page.insert_text((10, _BANNER_TEXT_BASELINE), REVIEW_WATERMARK, fontsize=8, color=(0.80, 0, 0))
    tag = (tag or "").strip()
    if not tag:  # never stamp a blank "Tag:" — an unknown tag stays unstated
        return
    label = f"Tag: {tag}"
    length = fitz.get_text_length(label, fontname="helv", fontsize=9)
    page.insert_text(
        (max(10.0, width - length - 10.0), _BANNER_TEXT_BASELINE),
        label,
        fontsize=9,
        color=(0.0, 0.0, 0.0),
    )


def _stamp_superseded_watermark(page) -> None:
    """Large translucent diagonal watermark on a source Direct Coil drawing page that
    has a CoilForge drawing inserted right after it.

    Marks the original as the drawing being revised and points the reviewer to the
    next page (our drawing) as the basis for the revised drawing. Drawn OVER the page
    at low opacity so the original stays readable for comparison — the source content
    is never edited. Review aid only.
    """
    import fitz

    rect = page.rect
    red = (0.80, 0.0, 0.0)
    text = "REVISED DRAWING - SEE NEXT PAGE"
    fs = max(26.0, min(48.0, rect.width / 12.0))
    placed = False
    try:  # diagonal banner across the page centre (preferred)
        tlen = fitz.get_text_length(text, fontsize=fs)
        pivot = fitz.Point(rect.width / 2.0, rect.height / 2.0)
        writer = fitz.TextWriter(rect, color=red)
        writer.append(fitz.Point(pivot.x - tlen / 2.0, pivot.y), text, fontsize=fs)
        writer.write_text(page, morph=(pivot, fitz.Matrix(45)), opacity=0.22)
        placed = True
    except Exception:  # noqa: BLE001 — fall back to a horizontal stamp
        placed = False
    if not placed:
        tlen = fitz.get_text_length(text, fontsize=fs)
        x = max(4.0, (rect.width - tlen) / 2.0)
        try:
            page.insert_text((x, rect.height / 2.0), text, fontsize=fs,
                             color=red, fill_opacity=0.22)
        except TypeError:  # older PyMuPDF without fill_opacity
            page.insert_text((x, rect.height / 2.0), text, fontsize=fs,
                             color=(0.93, 0.62, 0.62))
    # Unambiguous top header band (always rendered, opaque, small).
    page.draw_rect(fitz.Rect(0, 0, rect.width, 16),
                   color=(0.70, 0.70, 0.70), fill=(1.0, 1.0, 1.0), width=0.5)
    page.insert_text((10, 11),
                     "SUPERSEDED - CoilForge revised drawing on the next page (review aid)",
                     fontsize=8, color=red)


def _cost_each_rects(page) -> list:
    """Sorted-by-y 'Cost Each' anchor rects on ``page`` (case-insensitive).

    The page-detection predicate (``_quote_page_indices``) is case-insensitive, so the
    per-row anchor search must be too, or a page whose header renders 'COST EACH' would
    be detected yet yield zero anchors (silent no-op). Search both casings and dedupe by
    position so a case-insensitive PyMuPDF build does not double-count.
    """
    rects = list(page.search_for("Cost Each")) + list(page.search_for("COST EACH"))
    deduped: dict[tuple[float, float], object] = {}
    for r in rects:
        deduped.setdefault((round(r.x0, 1), round(r.y0, 1)), r)
    return sorted(deduped.values(), key=lambda r: r.y0)


def _tag_y_on_page(page, tag: str) -> float | None:
    """Topmost y of ``tag`` (alias-tolerant) on ``page``, or None if absent.

    Matches across the documented category-prefix aliases (e.g. reviewed ``RHHGRH-1``
    vs source ``RHHGRC-1``) — mirroring ``_coil_drawing_page_index`` — so a spelling
    difference never drops a coil's note.
    """
    ys = [
        rect.y0
        for alias in coil_tag_aliases(tag)
        for rect in page.search_for(alias)
    ]
    return min(ys) if ys else None


def _stamp_quote_price_notes(page, coils: list[dict], stamped: set[str] | None = None) -> None:
    """Draw each coil's copper-strap price note right above its 'Item Total' price.

    Anchors the note above the right-hand 'Item N Total' figure on the coil's pricing
    line. John 2026-06-25/26: right-edge alignment puts the note's trailing 'NN.00'
    directly above the total's — see the anchoring block below. Source quote numbers are
    never modified.

    Multi-page aware: a many-coil schedule spills its pricing rows onto quote page 2+,
    so this is called once per quote page with a shared ``stamped`` set (coil tags already
    noted on an earlier page). Two passes per page keep a fallback coil from stealing a
    tag-matched coil's row:

    * **Pass 1 (precise):** coils whose tag/alias appears on THIS page anchor to the first
      free 'Cost Each' at/below their tag.
    * **Pass 2 (fill):** remaining not-yet-stamped coils (list order) fill any leftover
      rows on this page — this absorbs a boundary coil whose tag printed on the previous
      page but whose pricing row spilled onto this one. Pass 1 MUST complete before pass 2
      so a fill never claims a row a tag-matched coil on this page still needs.
    """
    import fitz

    if stamped is None:
        stamped = set()
    fs = 7.2
    cost_rects = _cost_each_rects(page)
    used: set[int] = set()

    def _place(target, note: str) -> None:
        # Right-EDGE anchor: align the note's right edge to the rightmost text on
        # this coil's pricing line — the 'Item N Total' figure (e.g. CAD$1,952.00).
        # Fall back to the line's rightmost word, then to 'Cost Each' x, if no Total.
        line_x1 = [w[2] for w in page.get_text("words") if abs(w[1] - target.y0) <= 3]
        note_w = fitz.get_text_length(note, fontsize=fs)
        right_edge = max(line_x1, default=target.x0 + note_w)
        x = right_edge - note_w
        x = max(target.x0, min(x, page.rect.width - note_w - 4))
        band = fitz.Rect(x - 2, target.y0 - 11, x + note_w + 4, target.y0 - 1)
        page.draw_rect(band, color=(0.80, 0.0, 0.0), fill=(1.0, 1.0, 1.0), width=0.4)
        page.insert_text((x, target.y0 - 3), note, fontsize=fs, color=(0.80, 0.0, 0.0))

    # Pass 1 — precise: place coils whose tag is on this page at/below their tag row.
    for coil in coils:
        note = coil.get("price_note")
        tag = coil.get("tag")
        if not note or tag in stamped:
            continue
        tag_y = _tag_y_on_page(page, tag)
        if tag_y is None:  # coil belongs to another page (or is fill-only) -> pass 2
            continue
        target_idx = next(
            (idx for idx, rect in enumerate(cost_rects)
             if idx not in used and rect.y0 >= tag_y - 1),
            None,
        )
        if target_idx is None:  # tag here but no free row below it -> pass 2 fill
            continue
        used.add(target_idx)
        _place(cost_rects[target_idx], note)
        stamped.add(tag)

    # Pass 2 — fill: remaining unstamped noted coils take any leftover row on this page.
    for coil in coils:
        note = coil.get("price_note")
        tag = coil.get("tag")
        if not note or tag in stamped:
            continue
        target_idx = next((idx for idx in range(len(cost_rects)) if idx not in used), None)
        if target_idx is None:  # no free anchor here; a later quote page may take it
            continue
        used.add(target_idx)
        _place(cost_rects[target_idx], note)
        stamped.add(tag)


def assemble_multi_coil_package(
    *, source_pdf: bytes, coils: list[dict], mark_source_superseded: bool = True
) -> MultiCoilPackageResult:
    """Insert each coil's CoilForge drawing after its source drawing page and stamp a
    copper-strap price note above each coil's quoted price.

    ``coils`` entries: ``{tag, coil_type, our_svg, price_note, price_total, price_status}``
    (price_* optional). Coils without a drawing page or SVG are reported but not
    inserted. When ``mark_source_superseded`` is set, each source Direct Coil drawing
    page that gets a drawing inserted after it is stamped with a large "revised drawing
    next page" watermark so the reviewer compares it against the inserted drawing.
    Raises ``ValueError`` on unreadable input. The raw source file on disk is never
    written; only an in-memory copy is annotated.
    """
    if not source_pdf:
        raise ValueError("assemble_multi_coil_package: source_pdf is empty")

    import fitz  # PyMuPDF — lazy import (see submittal/pdf_intake.py)

    try:
        src = fitz.open(stream=source_pdf, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 — surface a clean contract error
        raise ValueError(f"assemble_multi_coil_package: unreadable source PDF ({exc})") from exc

    out = fitz.open()
    summary: list[dict] = []
    inserted = 0
    try:
        by_drawing_page: dict[int, list[dict]] = {}
        for coil in coils:
            drawing_index = _coil_drawing_page_index(src, coil["tag"])
            will_insert = drawing_index is not None and bool(coil.get("our_svg"))
            if will_insert:
                not_inserted_reason = None
            elif not coil.get("our_svg"):
                not_inserted_reason = "no CoilForge drawing generated — review this coil first"
            else:
                not_inserted_reason = f"no source drawing page found for tag {coil['tag']}"
            summary.append(
                {
                    "tag": coil["tag"],
                    "coil_type": coil.get("coil_type"),
                    "drawing_page_source_index": drawing_index,
                    "price_total": coil.get("price_total"),
                    "price_status": coil.get("price_status"),
                    "price_note": coil.get("price_note"),
                    "inserted": will_insert,
                    "not_inserted_reason": not_inserted_reason,
                }
            )
            if will_insert:
                by_drawing_page.setdefault(drawing_index, []).append(coil)

        # Stamp copper-strap price notes on EVERY quote page. A many-coil schedule
        # spills its pricing rows onto page 2+, so a single-page stamp would drop the
        # later coils' notes. The shared `stamped` set carries which coils are already
        # noted, so each page only claims its own (and any coil spilled from a prior page).
        quote_indices = _quote_page_indices(src)
        stamped: set[str] = set()
        for qi in quote_indices:
            _stamp_quote_price_notes(src[qi], coils, stamped)

        for i in range(src.page_count):
            out.insert_pdf(src, from_page=i, to_page=i)
            coils_here = by_drawing_page.get(i, [])
            if coils_here and mark_source_superseded:
                # The source Direct Coil drawing page is now the last page in `out`;
                # stamp the large "revised drawing next page" watermark on it.
                _stamp_superseded_watermark(out[out.page_count - 1])
            for coil in coils_here:
                our_doc = fitz.open(stream=svg_to_pdf_bytes(coil["our_svg"]), filetype="pdf")
                try:
                    for page in our_doc:
                        _stamp_watermark_banner(page, tag=coil.get("tag"))
                    out.insert_pdf(our_doc)
                    inserted += 1
                finally:
                    our_doc.close()

        combined = out.tobytes()
        page_count = out.page_count
        source_page_count = src.page_count
    finally:
        out.close()
        src.close()

    return MultiCoilPackageResult(
        pdf_base64=base64.b64encode(combined).decode("ascii"),
        page_count=page_count,
        source_page_count=source_page_count,
        inserted_coil_count=inserted,
        coils=summary,
        quote_page_index=quote_indices[0] if quote_indices else None,
        quote_page_indices=quote_indices,
    )
