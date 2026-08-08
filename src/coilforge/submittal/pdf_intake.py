from __future__ import annotations

import io
import base64
import hashlib
import os
import re
from collections import OrderedDict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from coilforge.submittal.candidate import SubmittalCoilCandidate
from coilforge.submittal.extract import (
    SanitizedSubmittalLine,
    circuits_count_or_none,
    extract_submittal_candidate_from_structured,
)
from coilforge.submittal.rules import SUBMITTAL_FIELD_RULES, SubmittalFieldRule, normalize_source_key


COVER_PAGE_REQUIRED_HEADERS: tuple[str, ...] = (
    "Qty",
    "Tag",
    "Item",
    "Model",
    "Voltage",
    "Controls Preference",
    "Installation",
    "Duct Connection",
    "Handing",
)
COVER_PAGE_HEADER_KEYS: tuple[str, ...] = tuple(
    re.sub(r"[^a-z0-9]", "", header.lower()) for header in COVER_PAGE_REQUIRED_HEADERS
)


class PdfCoverRowSummary(BaseModel):
    """Cover-page coil row surfaced without returning raw PDF text."""

    model_config = ConfigDict(extra="forbid")

    page_number: int
    row_number: int
    quantity: int | None = None
    tag: str
    item: str = ""
    model: str = ""
    voltage: str = ""
    controls_preference: str = ""
    installation: str = ""
    duct_connection: str = ""
    handing: str = ""
    product_type: str = "DX"
    coil_format: str = "dx"
    # CoilForge product line + unit size derived from the cover product/model code
    # (e.g. "TR_C_040" -> "TERRA H" / "040") via the R-076-validated rule. Review-aid;
    # blank when the code is unrecognised. product_type above stays the coil family.
    product_line: str = ""
    unit_size: str = ""


class PdfCoilIntakeSummary(BaseModel):
    """Sanitized PDF intake summary. Raw PDF text is intentionally not returned."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_filename: str | None = None
    project_number: str | None = None
    project_name: str | None = None
    project_context_source: str | None = None
    extraction_engine: str
    pdf_pages: int
    extracted_field_count: int
    unmapped_line_count: int
    selected_candidate_id: str
    selected_tag: str | None = None
    selected_quantity: int | float | str | None = None
    selected_handing: str | None = None
    raw_private_data_returned: bool = False
    raw_pdf_stored: bool = False
    ocr_enabled: bool = False
    final_export_enabled: bool = False
    pdf_export_enabled: bool = False
    review_status: str = "quote_prep_review_only"
    reused_rule_sources: list[str] = Field(default_factory=list)
    cover_page_detected: bool = False
    cover_page_number: int | None = None
    cover_page_detection_method: str | None = None
    cover_page_required_headers: list[str] = Field(
        default_factory=lambda: list(COVER_PAGE_REQUIRED_HEADERS)
    )
    cover_page_detected_headers: list[str] = Field(default_factory=list)
    cover_page_row_count: int = 0
    cover_page_rows: list[PdfCoverRowSummary] = Field(default_factory=list)
    cover_page_ocr_required: bool = False
    cover_page_user_input_required: bool = False
    cover_page_review_note: str | None = None
    # Project-level hot-gas-bypass (HGBP/ASC) option, stated as a cover line item
    # ("HGBP VALVE - DANFOSS AXV-H and hot-gas bypass stub-out on coils adder"). The
    # pages are surfaced as evidence because the flag is applied package-wide to DX
    # coils -- see _package_hgbp_pages.
    cover_page_hgbp_detected: bool = False
    cover_page_hgbp_pages: list[int] = Field(default_factory=list)
    ocr_attempted: bool = False
    ocr_status: str = "not_requested"
    ocr_provider: str | None = None
    ocr_model: str | None = None
    ocr_page_number: int | None = None
    ocr_error: str | None = None
    # Pages whose embedded fonts extract as machine-unreadable text (broken ToUnicode
    # CMap -> "(cid:NN)" glyph soup or an ASCII-shifted cipher). Surfaced so the UI can
    # explain the condition instead of silently reporting "no coils".
    text_extraction_degraded: bool = False
    degraded_page_numbers: list[int] = Field(default_factory=list)
    ocr_pages: list[int] = Field(default_factory=list)
    # Loud alert when OCR was needed (degraded pages) but could not run/complete -- most
    # importantly OpenAI token/quota exhausted, also missing/expired key, rate-limit, or a
    # token-truncated response. Surfaced as a red banner so recovery never fails silently.
    ocr_blocked: bool = False
    ocr_alert: str | None = None


class PdfCoilIntakeResult(BaseModel):
    """Review-only PDF intake result feeding the existing CoilForge workflow."""

    model_config = ConfigDict(extra="forbid")

    summary: PdfCoilIntakeSummary
    candidate: SubmittalCoilCandidate
    cover_candidates: list[SubmittalCoilCandidate] = Field(default_factory=list)


@dataclass(frozen=True)
class _TextPage:
    page_number: int
    text: str
    tables: tuple[tuple[tuple[str, ...], ...], ...] = ()


@dataclass(frozen=True)
class _CoverRow:
    page_number: int
    row_number: int
    qty: int | None
    tag: str
    item: str = ""
    model: str = ""
    voltage: str = ""
    controls_preference: str = ""
    installation: str = ""
    duct_connection: str = ""
    handing: str = ""


@dataclass(frozen=True)
class _CoverPageDetection:
    detected: bool
    page_number: int | None = None
    detection_method: str | None = None
    detected_headers: tuple[str, ...] = ()
    rows: tuple[_CoverRow, ...] = ()
    ocr_required: bool = False
    user_page_input_required: bool = False
    review_note: str | None = None


# Hot gas bypass is quoted as a project-level cover line item, never as a coil row --
# "660024-001 HGBP VALVE - DANFOSS AXV-H and hot-gas bypass stub-out on coils adder".
# That row is (correctly) discarded by _is_cover_coil_row as an accessory, so the flag
# is read from PAGE TEXT rather than from parsed rows.
#
# Deliberately NARROWER than workflows.submittal_to_drawing._detect_hgbp: this scan spans
# many pages, so it must match only an EXPLICIT statement of the option. Two readings of
# the same words are NOT the option and must not match:
#   * the EZ coil drawing states hot gas bypass as an ASC count --
#     "(1)501-2-3/16-1.5(1 ASC)" -- so ASC is excluded entirely; matching it would let
#     one HGBP coil's drawing page blanket every DX coil in the package;
#   * a consulting engineer's spec narrative names the field refrigerant PIPE --
#     "...liquid line, insulated hot gas bypass line, insulated hot gas line..."
#     (2968 HTS Houston / College of the Mainland p.12) -- which tagged every DX coil in
#     that package HGBP and got their drawings withheld by the Nova/Ventum-H product-line
#     gate. "<token> line/pipe/piping" is the piping-run form, never the line item; the
#     quoted option reads "HGBP VALVE ... hot-gas bypass stub-out on coils adder".
_PACKAGE_HGBP_RE = re.compile(
    r"(?:\bHGBP\b|\bHOT[\s\-]*GAS[\s\-]*BY[\s\-]?PASS\b)"
    r"(?![\s\-]*(?:line|pipe|piping)\b)",
    re.IGNORECASE,
)


# Coating stated as a COVER line item (John 2026-08-05). Until now coating was read only
# from a coil's detail block, so a package that quotes it once on the cover -- the way the
# hot-gas-bypass adder is quoted -- read as "no coating" on every coil, which silently
# dropped the R-080/R-081 note AND left the drawing printing whatever coating its seeded
# template happened to carry.
#
# Vocabulary-anchored, never free-text: the value has to be one of the coating families the
# company's own Coil Checklist dropdown offers, so a stray sentence cannot invent a coating
# name. `_COATING_FAMILY_RE` keeps the submittal's own wording (e.g. "Finkote2 Epoxy Coil
# Coating") rather than snapping it to the dropdown spelling -- normalizing here would
# assert a specific variant the document may not have stated.
# Each alternative ends at a KNOWN variant suffix and no further. An open-ended trailing
# character class over-captures: the EZ drawing writes "Coil Coating: ElectroFin" with the
# next column's label butted straight up against it, which produced the nonsense
# instruction "ELECTROFIN EVAP TEMP COATING REQUIRED". Bounded alternatives keep the value
# inside the company's own vocabulary instead of swallowing whatever follows.
_COATING_FAMILY_RE = re.compile(
    r"\b("
    r"finkote\s*2\s*w/\s*uv\s*topcoat"
    r"|finkote\s*(?:zx\s*\(?zpex\)?|cc|hp|zx|2)"
    r"|finkote"
    r"|heresite\s*(?:hydrophilic|uv)"
    r"|heresite"
    r"|electrofin\s*uv"
    r"|electrofin"
    r"|blygold\s*anti-?\s*(?:corrosive|microbial)"
    r"|blygold"
    r"|black\s+poly(?:\s+coated\s+fin)?"
    r")",
    re.IGNORECASE,
)


def coating_family(text: Any) -> str | None:
    """The coating family named inside ``text``, or None.

    The long-standing ``Coil Coating: <value>`` label pattern captures to end-of-line, and
    the EZ drawing butts the next column's label straight against the value -- so the
    stored coating can read "ElectroFin Evap Temp 45". Harmless while nothing printed it;
    once the drawing carries a coating INSTRUCTION the trailing words become nonsense on a
    manufacturing note. Callers that render the coating normalize through this.

    Recognition, not invention: it returns a span of the input, never a substituted
    spelling, and None when no known family is present (the caller then keeps the raw
    value rather than dropping a coating the document really states).
    """
    if text is None:
        return None
    match = _COATING_FAMILY_RE.search(str(text))
    return None if match is None else _clean_line(match.group(1))


def _package_coating(
    pages: list[_TextPage], *, cover_page: int | None = None
) -> str | None:
    """The coating quoted once for the whole package, or None.

    Same scan window and reasoning as :func:`_package_hgbp_pages`: the option is a cover
    LINE ITEM, so pages BEFORE the cover -- the consulting engineer's spec sections, which
    routinely discuss coatings in the abstract -- cannot be quoting it and are skipped.
    That exclusion is what makes a document-wide scan safe here; without it a spec
    paragraph mentioning "epoxy coating" would coat every coil in the package.

    Callers apply it ONLY to coils that stated no coating of their own, and never to water
    coils (a water coil is never coated -- see `_drop_coating_from_water_coil`).
    """
    for page in sorted(pages, key=lambda p: p.page_number):
        if cover_page is not None and page.page_number < cover_page:
            continue
        for raw_line in (page.text or "").splitlines():
            line = _clean_line(raw_line)
            if not line or "coat" not in line.lower():
                continue
            match = _COATING_FAMILY_RE.search(line)
            if match:
                return _clean_line(match.group(1))
    return None


def _package_hgbp_pages(
    pages: list[_TextPage], *, cover_page: int | None = None
) -> tuple[int, ...]:
    """Page numbers explicitly stating the hot-gas-bypass (HGBP) option, ascending.

    Empty when the option is absent. Callers treat a non-empty result as a
    PROJECT-level fact applied to the package's DX coils (never water/reheat coils --
    no HGBP template bucket exists for those).

    ``cover_page`` (when the cover schedule was located) starts the scan window: the
    option is a cover LINE ITEM, so pages BEFORE the cover -- the consulting engineer's
    spec sections -- cannot state it and are skipped. The window has no upper bound
    because the adder can sit on a cover continuation page that yields no coil rows;
    :data:`_PACKAGE_HGBP_RE` carries the rest. Without a cover page the whole document
    is scanned (previous behavior).
    """
    return tuple(
        page.page_number
        for page in sorted(pages, key=lambda p: p.page_number)
        if (cover_page is None or page.page_number >= cover_page)
        and _PACKAGE_HGBP_RE.search(page.text or "")
    )


@dataclass(frozen=True)
class _DetailSectionBlock:
    coil_format: str
    lines: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class _OcrPageResult:
    page_number: int
    text: str = ""
    provider: str = "openai"
    model: str | None = None
    status: str = "not_requested"
    error: str | None = None


@dataclass(frozen=True)
class _FieldPattern:
    source_key: str
    labels: tuple[str, ...]
    value_pattern: str = r"(?P<value>[^\n\r]+?)"


# These deterministic rules intentionally mirror the safe portions of the POs
# pdf_extractor: unit tag anchors, Qty/Tag table rows, and line-level regexes.
_COIL_TYPE_BY_PREFIX = {
    "CDXC": "DX COIL",
    "RHHGRC": "HGRH COIL",
    "HGRC": "HGRH COIL",
    # RHHGRH/HGRH: alternate hot-gas-reheat tag spelling seen in Oxygen8 submittals
    # (e.g. 2766 Olympic-Broadway uses RHHGRH-1/-2); same HGRH category as RHHGRC.
    "RHHGRH": "HGRH COIL",
    "HGRH": "HGRH COIL",
    "HHWC": "Hot Water Coil",
    "PHWC": "Hot Water Coil",
    "CCWC": "Chilled Water Coil",
}
_PRODUCT_TYPE_BY_PREFIX = {
    "CDXC": "DX",
    "RHHGRC": "HGRC",
    "HGRC": "HGRC",
    "RHHGRH": "HGRC",
    "HGRH": "HGRC",
    "HHWC": "HW",
    "PHWC": "HW",
    "CCWC": "CHW",
}
_COIL_FORMAT_BY_PREFIX = {
    "CDXC": "dx",
    "RHHGRC": "condensing",
    "HGRC": "condensing",
    "RHHGRH": "condensing",
    "HGRH": "condensing",
    "HHWC": "heating_hot_water",
    "PHWC": "preheat_hot_water",
    "CCWC": "cooling_chilled_water",
}
_COIL_TAG_PREFIXES = tuple(_COIL_TYPE_BY_PREFIX)


# Tag-prefix spelling variants: prefixes that are the SAME coil written differently.
# Only hot-gas-reheat appears under multiple spellings in the wild (Oxygen8 writes both
# ``RHHGRC`` and ``RHHGRH``). HHWC vs PHWC are DISTINCT coils (heating vs preheat), NOT
# spelling variants — they must never be grouped here, or a package could match the
# wrong source drawing page.
_COIL_TAG_SPELLING_VARIANTS: tuple[tuple[str, ...], ...] = (
    ("RHHGRC", "HGRC", "RHHGRH", "HGRH"),
)


def coil_tag_aliases(tag: str) -> tuple[str, ...]:
    """All equivalent spellings of a coil tag across known tag-spelling variants.

    Some coils are written more than one way (e.g. Oxygen8 writes hot-gas-reheat as
    both ``RHHGRC-1`` and ``RHHGRH-1``). This returns every spelling that names the
    *same* coil, so a tag can be matched against source text that uses a different
    spelling. The original tag is always included; a prefix with no known variant
    yields just ``(tag,)`` — never invents a match.
    """
    match = re.match(r"^\s*(?P<prefix>[A-Za-z]+)-(?P<seq>\d+)\s*$", tag or "")
    if not match:
        return (tag,)
    prefix = match.group("prefix").upper()
    seq = match.group("seq")
    for group in _COIL_TAG_SPELLING_VARIANTS:
        if prefix in group:
            aliases = [f"{variant}-{seq}" for variant in group]
            if tag not in aliases:
                aliases.insert(0, tag)
            return tuple(aliases)
    return (tag,)


# Coils that share one drain pan, paired for the INSTALL FIT mechanical check:
# a DX cooling coil with its HGRH reheat coil, and a chilled-water coil with its
# hot-water coil. Both members of a pair sit in the same unit (same casing) and
# carry the same tag sequence number (e.g. CDXC-1 <-> RHHGRH-1, CCWC-2 <-> HHWC-2).
_DRAIN_PAN_PARTNER_CATEGORY = {
    "DX COIL": "HGRH COIL",
    "HGRH COIL": "DX COIL",
    "Chilled Water Coil": "Hot Water Coil",
    "Hot Water Coil": "Chilled Water Coil",
}


def coil_category_of_tag(tag: str) -> str | None:
    """Coil category for a tag (``CDXC-1`` -> ``DX COIL``), or ``None`` if unknown."""
    match = re.match(r"^\s*(?P<prefix>[A-Za-z]+)-\d+\s*$", tag or "")
    if not match:
        return None
    return _COIL_TYPE_BY_PREFIX.get(match.group("prefix").upper())


def drain_pan_partner_tag(tag: str, candidate_tags: list[str]) -> str | None:
    """The drain-pan-sharing partner tag for ``tag`` among ``candidate_tags``.

    Matches the partner CATEGORY (DX<->HGRH, CWC<->HWC) at the SAME tag sequence
    number. Returns the first such candidate, or ``None`` when no partner exists
    (a standalone coil — normal, never invented). Never pairs HHWC with PHWC
    (both Hot Water, but each other's category is Chilled Water, not Hot Water).
    """
    match = re.match(r"^\s*(?P<prefix>[A-Za-z]+)-(?P<seq>\d+)\s*$", tag or "")
    if not match:
        return None
    category = _COIL_TYPE_BY_PREFIX.get(match.group("prefix").upper())
    partner_category = _DRAIN_PAN_PARTNER_CATEGORY.get(category or "")
    if partner_category is None:
        return None
    seq = match.group("seq")
    for cand in candidate_tags:
        cm = re.match(r"^\s*(?P<prefix>[A-Za-z]+)-(?P<seq>\d+)\s*$", cand or "")
        if not cm or cm.group("seq") != seq:
            continue
        if _COIL_TYPE_BY_PREFIX.get(cm.group("prefix").upper()) == partner_category:
            return cand
    return None


# Accessory line items that must never be detected as coils, even when their
# description mentions a coil keyword (e.g. an electronic expansion valve kit
# tagged "EKEXV-CDXC-1" with item "EKEXV Valve (DX Coil)"). Tag-prefix signal +
# item-token signal; both are checked before the coil-keyword fallthrough.
_NON_COIL_TAG_PREFIXES = {"EKEXV", "EEV", "EXV"}
_NON_COIL_ITEM_TOKENS = ("valve", "ekexv", "eev", "expansionvalve")
_UNIT_PREFIXES = (
    r"(?:ERV|DOAS|AHU|RTU|MAU|FCU|WSHP|TV|TH|NV|NH|VH|VV|PU|"
    + "|".join(_COIL_TAG_PREFIXES)
    + r")"
)
_RE_COIL_TAG_TOKEN = re.compile(
    rf"\b(?P<prefix>{'|'.join(_COIL_TAG_PREFIXES)})-(?P<sequence>\d+)\b",
    re.IGNORECASE,
)
_RE_UNIT_TAG_ANCHOR = re.compile(
    r"(?:Unit\s+Tag|Coil\s+Tag|Tag)\s*[:#]?\s*(?P<value>[A-Z][A-Z0-9][\w\-\s]*\d+)",
    re.IGNORECASE,
)
_RE_QTY_TAG_ROW = re.compile(
    rf"^\s*(?P<qty>\d+)\s+(?P<tag>{_UNIT_PREFIXES}(?:[\-\s](?:[\w]+-)*)?\d+)\b",
    re.IGNORECASE,
)
_RE_COMPONENT_COIL = re.compile(
    r"\b(?P<qty>\d+)\s+(?P<tag>CDXC-\d+|RHHGRC-\d+|RHHGRH-\d+|HGRC-\d+|HGRH-\d+"
    r"|PHWC-\d+|HHWC-\d+|CCWC-\d+)\b",
    re.IGNORECASE,
)
_RE_EZ_DX_MODEL_NUMBER = re.compile(
    r"\b(?P<model>DX-[A-Z]-(?P<circuit>S)-\d{2}-\d{2}-\d+(?:\.\d+)?x\d+(?:\.\d+)?-(?P<hand>L|R))(?=\b|Tag:)",
    re.IGNORECASE,
)
_DETAIL_SECTION_HEADER_PATTERN = re.compile(
    r"\b(?:Cooling\s+DX|Cooling\s+CWC|Heating\s+HWC|Preheat\s+HWC|"
    r"Reheat\s+Hot\s+Gas\s+Reheat\s+Coil|"
    r"HGRH\s+COIL\s+DATA|HGRC\s+COIL\s+DATA|CONDENSING\s+COIL\s+DATA|"
    r"HOT\s+WATER\s+COIL\s+DATA|HEATING\s+HOT\s+WATER\s+COIL\s+DATA|"
    r"PREHEAT\s+HOT\s+WATER\s+COIL\s+DATA|CHILLED\s+WATER\s+COIL\s+DATA|"
    r"FLUID\s+COIL\s+DATA)\b",
    re.IGNORECASE,
)
_DETAIL_SECTION_STOP_PATTERN = re.compile(
    r"\b(?:Heating\s+DX|Supply\s+Fan)\b",
    re.IGNORECASE,
)


_FIELD_PATTERNS: tuple[_FieldPattern, ...] = (
    _FieldPattern("COIL_TAG", ("Coil Unit Tag", "Unit Tag", "Coil Tag", "Tag"), r"(?P<value>[A-Z][A-Z0-9][\w\-\s]*\d+)"),
    _FieldPattern("COIL_QUANTITY", ("Coil Quantity", "Quantity", "Qty"), r"(?P<value>\d+)"),
    _FieldPattern("HANDING", ("Handing", "Coil Hand", "Hand"), r"(?P<value>Left|Right|L|R)\b"),
    _FieldPattern("PRODUCT_TYPE", ("Product Type", "Coil Type"), r"(?P<value>DX|CHW|HW|CW)\b"),
    _FieldPattern("HEADER_TYPE", ("Header Type",), r"(?P<value>Header\s*\d+)"),
    _FieldPattern("ALTITUDE_FT", ("Altitude (ft)", "Altitude(ft)", "Altitude"), r"(?P<value>-?\d+(?:\.\d+)?)(?:\s*ft)?"),
    _FieldPattern("ROWS_DEEP", ("Rows Deep", "Rows"), r"(?P<value>\d+(?:\.\d+)?)"),
    _FieldPattern("FINS_PER_INCH", ("Fins Per Inch", "FPI"), r"(?P<value>\d+(?:\.\d+)?)"),
    _FieldPattern("TUBES_HIGH", ("Tubes High",), r"(?P<value>\d+(?:\.\d+)?)"),
    _FieldPattern("FINNED_HEIGHT", ("Finned Height(In)", "Finned Height", "Fin Height"), r"(?P<value>\d+(?:\.\d+)?)(?:\s*(?:in|inch|inches))?"),
    _FieldPattern("FINNED_LENGTH", ("Finned Length(In)", "Finned Length", "Fin Length"), r"(?P<value>\d+(?:\.\d+)?)(?:\s*(?:in|inch|inches))?"),
    _FieldPattern("NUMBER_OF_FEEDS_TOTAL", ("Number Of Feeds(Total)", "Number Of Feeds", "Feeds"), r"(?P<value>\d+(?:\.\d+)?)"),
    _FieldPattern("TOTAL_AIR_FLOW_CFM", ("Total Air Flow(CFM)", "Total Air Flow", "Air Flow"), r"(?P<value>\d+(?:\.\d+)?)(?:\s*cfm)?"),
    _FieldPattern("ENTERING_DRY_BULB_F", ("Entering Dry Bulb(°F)", "Entering Dry Bulb", "EDB"), r"(?P<value>\d+(?:\.\d+)?)(?:\s*(?:degF|°F|F))?"),
    _FieldPattern("ENTERING_WET_BULB_F", ("Entering Wet Bulb(°F)", "Entering Wet Bulb", "EWB"), r"(?P<value>\d+(?:\.\d+)?)(?:\s*(?:degF|°F|F))?"),
    _FieldPattern("ENTERING_RELATIVE_HUMIDITY", ("Entering Relative Humidity(%)", "Relative Humidity", "RH"), r"(?P<value>\d+(?:\.\d+)?)(?:\s*%)?"),
    _FieldPattern("LEAVING_DRY_BULB_F", ("Leaving Dry Bulb(°F)", "Leaving Dry Bulb", "LDB"), r"(?P<value>\d+(?:\.\d+)?)(?:\s*(?:degF|°F|F))?"),
    _FieldPattern("LEAVING_WET_BULB_F", ("Leaving Wet Bulb(°F)", "Leaving Wet Bulb", "LWB"), r"(?P<value>\d+(?:\.\d+)?)(?:\s*(?:degF|°F|F))?"),
    _FieldPattern("TOTAL_CAPACITY_MBH", ("Total Capacity(MBH)(Per Coil)", "Total Capacity", "Capacity"), r"(?P<value>\d+(?:\.\d+)?)(?:\s*mbh)?"),
    _FieldPattern("REFRIGERANT", ("Refrigerant",), r"(?P<value>R[-\s]?\d+[A-Z]?|R\d+[A-Z]?|CO2|Ammonia)"),
    _FieldPattern("EVAPORATING_TEMPERATURE_F", ("Evaporating Temperature(°F)", "Evaporating Temperature", "SST"), r"(?P<value>-?\d+(?:\.\d+)?)(?:\s*(?:degF|°F|F))?"),
    _FieldPattern("LIQUID_TEMPERATURE_F", ("Liquid Temperature(°F)", "Liquid Temperature"), r"(?P<value>-?\d+(?:\.\d+)?)(?:\s*(?:degF|°F|F))?"),
    _FieldPattern("SUPERHEAT_F", ("Superheat(°F)", "Superheat"), r"(?P<value>-?\d+(?:\.\d+)?)(?:\s*(?:degF|°F|F))?"),
    _FieldPattern("DXDISTCAPILLARYSIZE", ("DXDistCapillarySize", "Capillary Size"), r"(?P<value>[\w./ xX-]+)"),
    _FieldPattern("TUBE_MATERIAL", ("Tube Material",), r"(?P<value>[A-Za-z0-9 .\"/-]+)"),
    _FieldPattern("FIN_MATERIAL", ("Fin Material",), r"(?P<value>[A-Za-z0-9 .\"/-]+)"),
    _FieldPattern("FIN_SURFACE", ("Fin Surface",), r"(?P<value>[A-Za-z0-9 .\"/-]+)"),
    _FieldPattern("HEADER_MATERIAL", ("Header Material",), r"(?P<value>[A-Za-z0-9 .\"/-]+)"),
    _FieldPattern("HEADER_WALL_SCHEDULE", ("Header Wall Schedule", "Wall Schedule"), r"(?P<value>[A-Za-z0-9 ().\"/-]+)"),
    _FieldPattern("CONNECTION_MATERIAL", ("Connection Material",), r"(?P<value>[A-Za-z0-9 .\"/-]+)"),
    _FieldPattern("CONNECTION_TYPE", ("Connection Type",), r"(?P<value>[A-Za-z0-9 .\"/-]+)"),
    _FieldPattern("RETURN_CONNECTION_SIZE", ("Return Connection Size",), r"(?P<value>\d+\s*/\s*\d+|\d+(?:\.\d+)?)"),
    _FieldPattern("SUPPLY_CONNECTION_SIZE", ("Supply Connection Size",), r"(?P<value>\d+\s*/\s*\d+|\d+(?:\.\d+)?)"),
    _FieldPattern("CASING_MATERIAL", ("Casing Material",), r"(?P<value>[A-Za-z0-9 .\"/-]+)"),
    _FieldPattern("CASING_STYLE", ("Casing Style",), r"(?P<value>[A-Za-z0-9 .\"/-]+)"),
    _FieldPattern("CONNECTION_ENDS", ("Connection Ends",), r"(?P<value>[A-Za-z0-9 .\"/-]+)"),
    _FieldPattern("COIL_COATING", ("Coil Coating",), r"(?P<value>[A-Za-z0-9 .\"/-]+)"),
    _FieldPattern("SYSTEM_TYPE", ("System Type",), r"(?P<value>[A-Za-z0-9 .\"/-]+)"),
    _FieldPattern("DRAIN_PAN_TYPE", ("Drain Pan Type",), r"(?P<value>[A-Za-z0-9 .\"/-]+)"),
    _FieldPattern("DRAWING_NOTES", ("Drawing Notes",), r"(?P<value>[^\n\r]+)"),
    *(
        _FieldPattern(key, (key,), r"(?P<value>\d+(?:\.\d+)?)(?:\s*(?:in|inch|inches))?")
        for key in ("CD", "BF", "TF", "RF", "HF", "CH", "SL", "I", "S", "O", "R", "HD", "ZD")
    ),
)


PDF_INTAKE_FIELD_RULES: dict[str, SubmittalFieldRule] = {
    **SUBMITTAL_FIELD_RULES,
    "COIL_QUANTITY": SubmittalFieldRule(
        "COIL_QUANTITY",
        "quantity",
        "coil_quantity",
        confidence="confirmed",
        review_note="Quantity extracted from PDF intake requires review.",
    ),
    "QTY": SubmittalFieldRule(
        "QTY",
        "quantity",
        "coil_quantity",
        confidence="confirmed",
        review_note="Quantity extracted from PDF intake requires review.",
    ),
    "TUBES_HIGH": SubmittalFieldRule("TUBES_HIGH", "geometry", "tubes_high", "tubes"),
    "NUMBER_OF_FEEDS": SubmittalFieldRule("NUMBER_OF_FEEDS", "geometry", "number_of_feeds", "feeds"),
    "NUMBER_OF_FEEDS_TOTAL": SubmittalFieldRule("NUMBER_OF_FEEDS_TOTAL", "geometry", "number_of_feeds", "feeds"),
    "CIRCUITS": SubmittalFieldRule("CIRCUITS", "geometry", "circuits"),
    "CIRCUITS_FROM_STYLE": SubmittalFieldRule(
        "CIRCUITS_FROM_STYLE",
        "geometry",
        "circuits",
        confidence="inferred",
        review_note="Circuit count derived from 'Coil Style' description; confirm before use.",
    ),
    "FACE_AREA_SQFT": SubmittalFieldRule("FACE_AREA_SQFT", "geometry", "face_area_sqft", "sqft"),
    "FIN_THICKNESS_IN": SubmittalFieldRule("FIN_THICKNESS_IN", "geometry", "fin_thickness_in", "in"),
    "COIL_DEPTH_IN": SubmittalFieldRule("COIL_DEPTH_IN", "geometry", "coil_depth_in", "in"),
    "TOTAL_AIR_FLOW_CFM": SubmittalFieldRule("TOTAL_AIR_FLOW_CFM", "airside_conditions", "total_air_flow_cfm", "cfm"),
    "ALTITUDE_FT": SubmittalFieldRule("ALTITUDE_FT", "airside_conditions", "altitude_ft", "ft"),
    "ENTERING_DRY_BULB_F": SubmittalFieldRule("ENTERING_DRY_BULB_F", "airside_conditions", "entering_dry_bulb_f", "degF"),
    "ENTERING_WET_BULB_F": SubmittalFieldRule("ENTERING_WET_BULB_F", "airside_conditions", "entering_wet_bulb_f", "degF"),
    "ENTERING_RELATIVE_HUMIDITY": SubmittalFieldRule("ENTERING_RELATIVE_HUMIDITY", "airside_conditions", "relative_humidity_pct", "pct"),
    "LEAVING_DRY_BULB_F": SubmittalFieldRule("LEAVING_DRY_BULB_F", "airside_conditions", "leaving_dry_bulb_f", "degF"),
    "LEAVING_WET_BULB_F": SubmittalFieldRule("LEAVING_WET_BULB_F", "airside_conditions", "leaving_wet_bulb_f", "degF"),
    "FACE_VELOCITY_FPM": SubmittalFieldRule("FACE_VELOCITY_FPM", "airside_conditions", "face_velocity_fpm", "fpm"),
    "FLUID_TYPE": SubmittalFieldRule("FLUID_TYPE", "airside_conditions", "fluid_type"),
    "FLUID_PERCENT": SubmittalFieldRule("FLUID_PERCENT", "airside_conditions", "fluid_percent", "pct"),
    "FLUID_ENTERING_TEMP_F": SubmittalFieldRule("FLUID_ENTERING_TEMP_F", "airside_conditions", "fluid_entering_temp_f", "degF"),
    "FLUID_LEAVING_TEMP_F": SubmittalFieldRule("FLUID_LEAVING_TEMP_F", "airside_conditions", "fluid_leaving_temp_f", "degF"),
    "FLUID_FLOW_RATE_GPM": SubmittalFieldRule("FLUID_FLOW_RATE_GPM", "airside_conditions", "fluid_flow_rate_gpm", "gpm"),
    "FLUID_PRESSURE_DROP_FTWG": SubmittalFieldRule("FLUID_PRESSURE_DROP_FTWG", "airside_conditions", "fluid_pressure_drop_ftwg", "ftWG"),
    "FLUID_VELOCITY_FPS": SubmittalFieldRule("FLUID_VELOCITY_FPS", "airside_conditions", "fluid_velocity_fps", "fps"),
    "EVAPORATING_TEMPERATURE_F": SubmittalFieldRule("EVAPORATING_TEMPERATURE_F", "refrigerant_conditions", "evaporating_temp_f", "degF"),
    "LIQUID_TEMPERATURE_F": SubmittalFieldRule("LIQUID_TEMPERATURE_F", "refrigerant_conditions", "liquid_temp_f", "degF"),
    "SUPERHEAT_F": SubmittalFieldRule("SUPERHEAT_F", "refrigerant_conditions", "superheat_f", "degF"),
    "CONDENSING_TEMPERATURE_F": SubmittalFieldRule("CONDENSING_TEMPERATURE_F", "refrigerant_conditions", "condensing_temp_f", "degF"),
    "SUBCOOLING_F": SubmittalFieldRule("SUBCOOLING_F", "refrigerant_conditions", "subcooling_f", "degF"),
    "VAPOR_TEMPERATURE_F": SubmittalFieldRule("VAPOR_TEMPERATURE_F", "refrigerant_conditions", "vapor_temp_f", "degF"),
    "DXDISTCAPILLARYSIZE": SubmittalFieldRule(
        "DXDISTCAPILLARYSIZE",
        "refrigerant_conditions",
        "dx_dist_capillary_size",
        confidence="ambiguous",
        review_note="Distributor/capillary source requires review.",
    ),
    "HANDING": SubmittalFieldRule(
        "HANDING",
        "connections",
        "coil_hand",
        confidence="inferred",
        review_note="Handing normalized to Direct Coil hand candidate; confirm before use.",
    ),
    "HAND": SubmittalFieldRule(
        "HAND",
        "connections",
        "coil_hand",
        confidence="inferred",
        review_note="Hand normalized to Direct Coil hand candidate; confirm before use.",
    ),
    "TUBE_MATERIAL": SubmittalFieldRule("TUBE_MATERIAL", "materials_construction", "tube_material"),
    "FIN_MATERIAL": SubmittalFieldRule("FIN_MATERIAL", "materials_construction", "fin_material"),
    "FIN_SURFACE": SubmittalFieldRule(
        "FIN_SURFACE",
        "materials_construction",
        "fin_surface",
        confidence="inferred",
        review_note="Fin surface normalized to Direct Coil candidate; confirm before use.",
    ),
    "HEADER_MATERIAL": SubmittalFieldRule("HEADER_MATERIAL", "materials_construction", "header_material"),
    # The fixed confidence here is only a fallback; the real per-value tier
    # (confirmed for explicit L/K, inferred for the default, ambiguous + blocked for
    # unknown) is resolved in extract._build_field_value.
    "HEADER_WALL_SCHEDULE": SubmittalFieldRule(
        "HEADER_WALL_SCHEDULE",
        "materials_construction",
        "header_wall_schedule",
        confidence="inferred",
        review_note="Header wall schedule normalized to Direct Coil (L)/(K) candidate; confirm before use.",
    ),
    "TUBE_SURFACE": SubmittalFieldRule("TUBE_SURFACE", "materials_construction", "tube_surface"),
    "CASING_MATERIAL": SubmittalFieldRule("CASING_MATERIAL", "materials_construction", "casing_material"),
    "CASING_STYLE": SubmittalFieldRule("CASING_STYLE", "materials_construction", "casing_style"),
    "CONNECTION_MATERIAL": SubmittalFieldRule("CONNECTION_MATERIAL", "connections", "connection_material"),
    "CONNECTION_TYPE": SubmittalFieldRule("CONNECTION_TYPE", "connections", "connection_type"),
    "SUPPLY_CONNECTION_SIZE": SubmittalFieldRule("SUPPLY_CONNECTION_SIZE", "connections", "supply_connection_size", "in", confidence="ambiguous"),
    "QUANTITY_CONNECTIONS_PER_HEADER": SubmittalFieldRule("QUANTITY_CONNECTIONS_PER_HEADER", "connections", "qty_connections_per_header"),
    "INLET_CONNECTION_SIZE": SubmittalFieldRule("INLET_CONNECTION_SIZE", "connections", "inlet_connection_size", "in"),
    "OUTLET_CONNECTION_SIZE": SubmittalFieldRule("OUTLET_CONNECTION_SIZE", "connections", "outlet_connection_size", "in"),
    "VALVE_SPEC": SubmittalFieldRule("VALVE_SPEC", "connections", "valve_spec"),
    "VALVE_ACTUATOR": SubmittalFieldRule("VALVE_ACTUATOR", "connections", "valve_actuator"),
    "VALVE_SIZE": SubmittalFieldRule("VALVE_SIZE", "connections", "valve_size", "in"),
    "CONTROL_VALVE_CV": SubmittalFieldRule("CONTROL_VALVE_CV", "connections", "control_valve_cv"),
    "VALVE_DESCRIPTION": SubmittalFieldRule("VALVE_DESCRIPTION", "connections", "valve_description"),
    "CONNECTION_ENDS": SubmittalFieldRule("CONNECTION_ENDS", "connections", "connection_ends"),
    "COIL_MODEL": SubmittalFieldRule("COIL_MODEL", "manufacturing_options", "coil_model"),
    "COIL_STYLE": SubmittalFieldRule("COIL_STYLE", "manufacturing_options", "coil_style"),
    "VRV_KIT_TYPE": SubmittalFieldRule("VRV_KIT_TYPE", "manufacturing_options", "vrv_kit_type"),
    "VRV_KIT_MANUFACTURER": SubmittalFieldRule("VRV_KIT_MANUFACTURER", "manufacturing_options", "vrv_kit_manufacturer"),
    "VRV_SYSTEM_TYPE": SubmittalFieldRule("VRV_SYSTEM_TYPE", "manufacturing_options", "vrv_system_type"),
    "VRV_KIT_MODEL": SubmittalFieldRule("VRV_KIT_MODEL", "manufacturing_options", "vrv_kit_model"),
    "VRV_QUANTITY_OF_VALVES": SubmittalFieldRule("VRV_QUANTITY_OF_VALVES", "manufacturing_options", "vrv_quantity_of_valves"),
    "VRV_NOMINAL_TONNAGE": SubmittalFieldRule("VRV_NOMINAL_TONNAGE", "manufacturing_options", "vrv_nominal_tonnage"),
    "COIL_COATING": SubmittalFieldRule("COIL_COATING", "manufacturing_options", "coil_coating"),
    "SYSTEM_TYPE": SubmittalFieldRule("SYSTEM_TYPE", "manufacturing_options", "system_type"),
    "DRAIN_PAN_TYPE": SubmittalFieldRule("DRAIN_PAN_TYPE", "manufacturing_options", "drain_pan_type"),
    "DRAWING_NOTES": SubmittalFieldRule("DRAWING_NOTES", "manufacturing_options", "distributor_notes", confidence="ambiguous"),
    "COIL_WEIGHT_LBS": SubmittalFieldRule("COIL_WEIGHT_LBS", "performance", "coil_weight_lbs", "lbs"),
    "NOMINAL_COOLING_CAPACITY_MBH": SubmittalFieldRule("NOMINAL_COOLING_CAPACITY_MBH", "performance", "nominal_cooling_capacity_mbh", "MBH"),
    "OPERATING_SETPOINT_DB_F": SubmittalFieldRule("OPERATING_SETPOINT_DB_F", "performance", "operating_setpoint_db_f", "degF"),
    "SENSIBLE_CAPACITY_MBH": SubmittalFieldRule("SENSIBLE_CAPACITY_MBH", "performance", "sensible_capacity_mbh", "MBH"),
    "MAX_DRY_BULB_F": SubmittalFieldRule("MAX_DRY_BULB_F", "performance", "max_dry_bulb_f", "degF"),
    "MAX_WET_BULB_F": SubmittalFieldRule("MAX_WET_BULB_F", "performance", "max_wet_bulb_f", "degF"),
    "AIR_PRESSURE_DROP_IWG": SubmittalFieldRule("AIR_PRESSURE_DROP_IWG", "performance", "air_pressure_drop_iwg", "iwg"),
    "INTERNAL_VOLUME_CUIN": SubmittalFieldRule("INTERNAL_VOLUME_CUIN", "performance", "internal_volume_cuin", "cuin"),
    "REFRIGERANT_PRESSURE_DROP_PSI": SubmittalFieldRule("REFRIGERANT_PRESSURE_DROP_PSI", "performance", "refrigerant_pressure_drop_psi", "psi"),
    **{
        key: SubmittalFieldRule(
            key,
            "drawing_parameters",
            key,
            "in",
            confidence="ambiguous",
            review_note="Drawing parameter extracted from PDF requires engineering review.",
        )
        for key in ("CD", "I", "S", "O", "R", "BF", "HD", "HF", "TF", "RF", "CH", "SL", "ZD")
    },
}


def extract_coil_candidate_from_pdf_bytes(
    pdf_bytes: bytes,
    *,
    source_id: str = "PDF-UPLOAD-INTAKE-001",
    source_filename: str | None = None,
    cover_page_hint: int | None = None,
) -> PdfCoilIntakeResult:
    pages, engine = extract_text_pages_from_pdf_bytes(pdf_bytes)
    # Detect pages whose fonts extracted as unreadable glyph soup / shifted cipher and,
    # if any, auto-OCR them (no manual page hint needed) so both the cover schedule and
    # the coil-detail dimensions are recovered before the normal pipeline runs.
    degraded_page_numbers = _degraded_page_numbers(pages)
    auto_ocr_results: list[_OcrPageResult] = []
    auto_ocr_pages: list[int] = []
    auto_ocr_truncated = len(degraded_page_numbers) > _MAX_AUTO_OCR_PAGES
    if degraded_page_numbers:
        replacements, auto_ocr_results = _auto_ocr_degraded_pages(
            pdf_bytes,
            degraded_pages=degraded_page_numbers,
        )
        if replacements:
            pages = _pages_with_replaced_text(pages, replacements)
            auto_ocr_pages = sorted(replacements)
            engine = f"{engine}+auto_llm_ocr"
    project_context = _extract_project_context(
        pages,
        source_filename=source_filename,
    )
    cover_detection = detect_cover_page_from_pdf_pages(pages, cover_page_hint=cover_page_hint)
    ocr_result = _maybe_run_llm_ocr(
        pdf_bytes,
        pages=pages,
        cover_detection=cover_detection,
        cover_page_hint=cover_page_hint,
    )
    if ocr_result.text:
        pages = _pages_with_ocr_text(pages, ocr_result)
        engine = f"{engine}+llm_ocr"
        cover_detection = detect_cover_page_from_pdf_pages(pages)
        if not cover_detection.detected:
            cover_detection = _CoverPageDetection(
                detected=False,
                page_number=ocr_result.page_number,
                detection_method="llm_ocr_text_no_cover_signature",
                ocr_required=False,
                user_page_input_required=False,
                review_note=(
                    f"LLM OCR completed for page {ocr_result.page_number}; cover table "
                    "signature was not detected, so extracted label/value candidates require review."
                ),
            )
    lines = extract_coil_lines_from_pdf_text(pages, cover_detection=cover_detection)
    candidate = extract_submittal_candidate_from_structured(
        lines,
        source_id=source_id,
        field_rules=PDF_INTAKE_FIELD_RULES,
    )
    intake_notes = [
        *candidate.notes,
        "Created by Phase 2E PDF intake adapter using deterministic POs-style parsing rules.",
        "Raw PDF text is not returned to the UI response.",
    ]
    if auto_ocr_truncated:
        intake_notes.append(
            f"Auto-OCR was capped at {_MAX_AUTO_OCR_PAGES} of {len(degraded_page_numbers)} "
            "unreadable pages; the remaining pages were not OCR'd and may miss values (review required)."
        )
    candidate = candidate.model_copy(
        update={
            "candidate_id": f"SCC-{source_id}",
            "notes": intake_notes,
        }
    )
    cover_shared_lines = _shared_unit_lines_for_cover_candidates(pages)
    cover_detail_lines = _detail_lines_by_cover_row(pages, cover_detection)
    # Read after both OCR passes have rebuilt `pages`, so the scan covers every cover
    # detection tier -- including the two that never look at page text themselves.
    hgbp_pages = _package_hgbp_pages(pages, cover_page=cover_detection.page_number)
    package_coating = _package_coating(pages, cover_page=cover_detection.page_number)
    cover_candidates = [
        _candidate_from_cover_row(
            row,
            source_id=source_id,
            index=index,
            detail_lines=(
                *cover_shared_lines,
                *cover_detail_lines.get(row.tag, ()),
            ),
            package_hgbp_pages=hgbp_pages,
            package_coating=package_coating,
        )
        for index, row in enumerate(cover_detection.rows, start=1)
    ]
    # Report the hint-based OCR result when it actually ran; otherwise reflect auto-OCR so
    # the existing ocr_* UI indicators light up for the auto path too.
    if ocr_result.status != "not_requested":
        effective_ocr = ocr_result
    else:
        auto_status, auto_error = _combined_auto_ocr_status(auto_ocr_results)
        effective_ocr = _OcrPageResult(
            page_number=(auto_ocr_pages[0] if auto_ocr_pages else 1),
            model=(auto_ocr_results[0].model if auto_ocr_results else None),
            status=auto_status,
            error=auto_error,
        )
    ocr_blocked, ocr_alert = _ocr_blocked_alert(
        degraded=bool(degraded_page_numbers),
        auto_ocr_results=auto_ocr_results,
    )
    summary = PdfCoilIntakeSummary(
        source_id=source_id,
        source_filename=source_filename,
        project_number=project_context.get("project_number"),
        project_name=project_context.get("project_name"),
        project_context_source=project_context.get("project_context_source"),
        extraction_engine=engine,
        pdf_pages=len(pages),
        extracted_field_count=len(lines),
        unmapped_line_count=len(candidate.unmapped_fields),
        selected_candidate_id=candidate.candidate_id,
        selected_tag=None if candidate.tag is None else candidate.tag.value,
        selected_quantity=None if candidate.quantity is None else candidate.quantity.value,
        selected_handing=_field_value(candidate.connections, "coil_hand"),
        ocr_enabled=effective_ocr.status == "completed",
        ocr_attempted=effective_ocr.status != "not_requested",
        ocr_status=effective_ocr.status,
        ocr_provider=effective_ocr.provider if effective_ocr.status != "not_requested" else None,
        ocr_model=effective_ocr.model,
        ocr_page_number=effective_ocr.page_number if effective_ocr.status != "not_requested" else None,
        ocr_error=effective_ocr.error,
        text_extraction_degraded=bool(degraded_page_numbers),
        degraded_page_numbers=list(degraded_page_numbers),
        ocr_pages=list(auto_ocr_pages),
        ocr_blocked=ocr_blocked,
        ocr_alert=ocr_alert,
        cover_page_detected=cover_detection.detected,
        cover_page_number=cover_detection.page_number,
        cover_page_detection_method=cover_detection.detection_method,
        cover_page_detected_headers=list(cover_detection.detected_headers),
        cover_page_row_count=len(cover_detection.rows),
        cover_page_rows=[_cover_row_summary(row) for row in cover_detection.rows],
        cover_page_ocr_required=cover_detection.ocr_required,
        cover_page_user_input_required=cover_detection.user_page_input_required,
        cover_page_review_note=cover_detection.review_note,
        cover_page_hgbp_detected=bool(hgbp_pages),
        cover_page_hgbp_pages=list(hgbp_pages),
        reused_rule_sources=[
            "PO_Release_Engineering_Workflow/pdf_extractor: cover-page Qty/Tag table structure",
            "PO_Release_Engineering_Workflow/pdf_extractor: deterministic line regex style",
            "PO_Release_Engineering_Workflow/pdf_extractor: Unit Tag anchor rule",
            "PO_Release_Engineering_Workflow/pdf_extractor: Qty/Tag table-row rule",
            "PO_Release_Engineering_Workflow/pdf_extractor: .env-backed OpenAI vision fallback pattern",
        ],
    )
    return PdfCoilIntakeResult(
        summary=summary,
        candidate=candidate,
        cover_candidates=cover_candidates,
    )


def _extract_project_context(
    pages: list[_TextPage],
    *,
    source_filename: str | None,
) -> dict[str, str | None]:
    text_context = _project_context_from_pdf_text(pages)
    filename_context = _project_context_from_filename(source_filename)
    project_number = text_context.get("project_number") or filename_context.get("project_number")
    project_name = text_context.get("project_name") or filename_context.get("project_name")
    if text_context.get("project_number") or text_context.get("project_name"):
        source = "pdf_text_label"
    elif filename_context.get("project_number") or filename_context.get("project_name"):
        source = "source_filename"
    else:
        source = None
    return {
        "project_number": project_number,
        "project_name": project_name,
        "project_context_source": source,
    }


def _project_context_from_pdf_text(pages: list[_TextPage]) -> dict[str, str | None]:
    text = "\n".join(page.text for page in pages)
    return {
        "project_number": _first_label_value(
            text,
            (
                r"\bProject\s*(?:Number|No\.?|#)\s*[:#-]?\s*(?P<value>[^\n\r]+)",
                r"\bJob\s*(?:Number|No\.?|#)\s*[:#-]?\s*(?P<value>[^\n\r]+)",
            ),
        ),
        "project_name": _first_label_value(
            text,
            (
                r"\bProject\s*Name\s*[:#-]?\s*(?P<value>[^\n\r]+)",
                r"\bProject\s*[:#-]\s*(?P<value>[^\n\r]+)",
            ),
        ),
    }


def _first_label_value(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is None:
            continue
        value = _clean_project_context_value(match.group("value"))
        if value:
            return value
    return None


def _project_context_from_filename(source_filename: str | None) -> dict[str, str | None]:
    if not source_filename:
        return {"project_number": None, "project_name": None}
    stem = Path(source_filename).stem
    parts = [part.strip() for part in re.split(r"\s+-\s+", stem) if part.strip()]
    project_number = (
        parts[0]
        if len(parts) > 1
        and re.fullmatch(r"[A-Z0-9][A-Z0-9_.-]*", parts[0], re.IGNORECASE)
        and re.search(r"\d", parts[0])
        else None
    )
    project_name = next(
        (
            part
            for part in parts[1:]
            if re.search(r"\bproject\b", part, re.IGNORECASE)
            and not re.search(r"\b(?:submittal|as\s*built|drawing|pdf)\b", part, re.IGNORECASE)
        ),
        None,
    )
    return {
        "project_number": _clean_project_context_value(project_number),
        "project_name": _clean_project_context_value(project_name),
    }


def _clean_project_context_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip(" :-#\t")
    cleaned = re.split(
        r"\s{2,}|\b(?:Date|Address|Submitted|Submittal|Prepared|Page|Qty|Tag)\b",
        cleaned,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" :-#\t")
    return cleaned[:120] or None


# --- P0-A: memoize the two identity-free heavy sub-operations ----------------
# analyze and the checklist auto-fill push the SAME pdf_bytes through intake twice
# (different source_id -> _WORKFLOW_CACHE miss), re-paying the dominant cost: the
# pdfplumber page extraction and the per-page gpt-4o OCR. Both are PURE functions of
# the bytes (and page/model), so we memoize them HERE -- below candidate assembly.
# Control flow is untouched: project-context, cover detection and per-source_id
# stamping still run identically, so output stays byte-identical and source_filename
# never enters a cache key. Caches are small, bounded LRUs (single-user local tool).
_INTAKE_CACHE_MAXSIZE = 16
_PAGES_CACHE: "OrderedDict[str, tuple[list[_TextPage], str]]" = OrderedDict()
_OCR_PAGE_CACHE: "OrderedDict[tuple[str, int, str], _OcrPageResult]" = OrderedDict()


def _pdf_bytes_sha1(pdf_bytes: bytes) -> str:
    return hashlib.sha1(pdf_bytes).hexdigest()


def _bound_intake_cache(cache: "OrderedDict[Any, Any]") -> None:
    while len(cache) > _INTAKE_CACHE_MAXSIZE:
        cache.popitem(last=False)


def clear_pdf_intake_caches() -> None:
    """Drop the page-extraction and per-page OCR memo caches (test hygiene / manual
    invalidation). The intake control flow is unchanged by these caches."""
    _PAGES_CACHE.clear()
    _OCR_PAGE_CACHE.clear()


def extract_text_pages_from_pdf_bytes(pdf_bytes: bytes) -> tuple[list[_TextPage], str]:
    """Extract per-page text (pdfplumber, PyPDF2 fallback), memoized on the PDF bytes.

    ``_TextPage`` is frozen, so a cache hit returns a FRESH list wrapping the shared
    immutable pages -- a caller that rebuilds its page list never mutates the cached one.
    Only successful extraction is cached (the uncached impl raises on total failure).
    """
    key = _pdf_bytes_sha1(pdf_bytes)
    cached = _PAGES_CACHE.get(key)
    if cached is not None:
        _PAGES_CACHE.move_to_end(key)
        pages, engine = cached
        return list(pages), engine
    pages, engine = _extract_text_pages_from_pdf_bytes_uncached(pdf_bytes)
    _PAGES_CACHE[key] = (list(pages), engine)
    _PAGES_CACHE.move_to_end(key)
    _bound_intake_cache(_PAGES_CACHE)
    return pages, engine


def _extract_text_pages_from_pdf_bytes_uncached(
    pdf_bytes: bytes,
) -> tuple[list[_TextPage], str]:
    try:
        import pdfplumber  # type: ignore

        pages: list[_TextPage] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                tables = tuple(
                    tuple(tuple(_clean_cell(cell) for cell in row) for row in table)
                    for table in page.extract_tables()
                    if table
                )
                pages.append(
                    _TextPage(
                        page_number=index,
                        text=page.extract_text() or "",
                        tables=tables,
                    )
                )
        return pages, "pdfplumber"
    except Exception:
        pass

    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = [
            _TextPage(page_number=index, text=page.extract_text() or "")
            for index, page in enumerate(reader.pages, start=1)
        ]
        return pages, "PyPDF2"
    except Exception as exc:
        raise ValueError(f"Unable to extract text from PDF bytes: {exc}") from exc


def _maybe_run_llm_ocr(
    pdf_bytes: bytes,
    *,
    pages: list[_TextPage],
    cover_detection: _CoverPageDetection,
    cover_page_hint: int | None,
) -> _OcrPageResult:
    if cover_detection.detected:
        return _OcrPageResult(page_number=cover_detection.page_number or 1)
    if cover_page_hint is None:
        return _OcrPageResult(page_number=1)
    if cover_page_hint > len(pages):
        return _OcrPageResult(
            page_number=cover_page_hint,
            status="skipped_invalid_page",
            error=f"Requested OCR page {cover_page_hint}, but PDF has {len(pages)} page(s).",
        )
    return _extract_page_text_with_llm_ocr(pdf_bytes, cover_page_hint)


def _classify_openai_ocr_error(exc: Exception) -> tuple[str, str]:
    """Map an OpenAI OCR exception to a distinct status + human message.

    Attribute-based (not ``isinstance``) so it never NameErrors when ``openai`` failed to
    import, and so it is trivially testable with lightweight fake exceptions. The
    token/quota case (``insufficient_quota``) is the one John most needs surfaced.
    """
    name = type(exc).__name__
    status_code = getattr(exc, "status_code", None)
    code = str(getattr(exc, "code", "") or "")
    message = str(getattr(exc, "message", "") or "") or str(exc)
    haystack = f"{code} {message}".lower()
    if status_code == 429 or name == "RateLimitError" or "rate limit" in haystack:
        if "insufficient_quota" in haystack or "quota" in haystack or "billing" in haystack:
            return (
                "blocked_openai_quota_exhausted",
                "OpenAI token/quota exhausted (insufficient_quota).",
            )
        return ("blocked_openai_rate_limited", f"OpenAI rate limit hit: {message}")
    if name in ("AuthenticationError", "PermissionDeniedError") or status_code in (401, 403):
        return ("blocked_openai_auth", f"OpenAI key rejected: {message}")
    return ("failed_openai_request", str(exc))


def _extract_page_text_with_llm_ocr(pdf_bytes: bytes, page_number: int) -> _OcrPageResult:
    """gpt-4o page OCR, memoized on (bytes, page, model).

    Only a SUCCESSFUL result (non-empty text) is cached -- a transient failure (rate
    limit, network, missing key, empty render) has empty text and is NOT cached, so a
    later re-analyze can still recover the page. ``_OcrPageResult`` is frozen, so the
    cached instance is safe to hand back directly.
    """
    model = os.environ.get("COILFORGE_OCR_MODEL", "gpt-4o")
    key = (_pdf_bytes_sha1(pdf_bytes), page_number, model)
    cached = _OCR_PAGE_CACHE.get(key)
    if cached is not None:
        _OCR_PAGE_CACHE.move_to_end(key)
        return cached
    result = _extract_page_text_with_llm_ocr_uncached(pdf_bytes, page_number)
    if result.text:  # cache only the expensive success path
        _OCR_PAGE_CACHE[key] = result
        _OCR_PAGE_CACHE.move_to_end(key)
        _bound_intake_cache(_OCR_PAGE_CACHE)
    return result


def _extract_page_text_with_llm_ocr_uncached(
    pdf_bytes: bytes, page_number: int
) -> _OcrPageResult:
    _load_dotenv_if_available()
    model = os.environ.get("COILFORGE_OCR_MODEL", "gpt-4o")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return _OcrPageResult(
            page_number=page_number,
            model=model,
            status="skipped_missing_openai_api_key",
            error="OPENAI_API_KEY was not found in environment or .env.",
        )

    try:
        mime_type, encoded_image = _render_pdf_page_to_image_data(pdf_bytes, page_number)
    except Exception as exc:
        return _OcrPageResult(
            page_number=page_number,
            model=model,
            status="failed_render_pdf_page",
            error=str(exc),
        )

    try:
        import openai  # type: ignore

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=int(os.environ.get("COILFORGE_OCR_MAX_TOKENS", "2200")),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You perform OCR for HVAC coil submittal pages. Return only visible text. "
                        "Preserve line breaks, table row order, labels, units, and tag/quantity values. "
                        "Do not infer missing engineering values and do not add commentary. "
                        "Never wrap output in markdown code fences. "
                        "If a Qty/Tag schedule (cover) table is present, emit its header on ONE single "
                        "line using exactly these column names in this order: "
                        "'Qty Tag Item Model Voltage Controls Preference Installation Duct Connection Handing' "
                        "(never split 'Controls Preference' across two lines), then one coil row per line "
                        "with the same column order, single spaces between columns."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "OCR this PDF page for CoilForge review intake. Return plain text only, "
                                "no markdown fences. If a cover schedule table is visible, put the full "
                                "header on one line and one coil row per line, columns in order."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{encoded_image}",
                            },
                        },
                    ],
                },
            ],
        )
        choice = response.choices[0]
        text = _strip_markdown_code_fences((choice.message.content or "").strip())
        if not text:
            return _OcrPageResult(
                page_number=page_number,
                model=model,
                status="completed_empty",
                error="OpenAI OCR returned no text.",
            )
        if getattr(choice, "finish_reason", None) == "length":
            # Output hit the max_tokens ceiling: the text is real but likely cut off, so
            # trailing coil rows may be missing. Keep the text, flag as a blocking status.
            return _OcrPageResult(
                page_number=page_number,
                text=text,
                model=model,
                status="completed_truncated",
                error="OCR output hit the token limit and may be truncated.",
            )
        return _OcrPageResult(
            page_number=page_number,
            text=text,
            model=model,
            status="completed",
        )
    except Exception as exc:
        status, message = _classify_openai_ocr_error(exc)
        return _OcrPageResult(
            page_number=page_number,
            model=model,
            status=status,
            error=message,
        )


def _strip_markdown_code_fences(text: str) -> str:
    """Remove ```-fenced wrapping that vision OCR often adds around table output.

    The downstream cover/detail parsers expect plain text lines; a leading/trailing
    ``` fence (optionally language-tagged) would otherwise pollute the first/last row.
    """
    lines = text.splitlines()
    if lines and lines[0].lstrip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
        repo_env = Path(__file__).resolve().parents[3] / ".env"
        if repo_env.exists():
            load_dotenv(repo_env)
    except Exception:
        return


def _render_pdf_page_to_image_data(pdf_bytes: bytes, page_number: int) -> tuple[str, str]:
    try:
        import fitz  # type: ignore
    except Exception as exc:
        raise RuntimeError("PyMuPDF is required for LLM OCR page rendering.") from exc

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if page_number < 1 or page_number > document.page_count:
            raise ValueError(
                f"Requested OCR page {page_number}, but PDF has {document.page_count} page(s)."
            )
        page = document.load_page(page_number - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image_bytes = pixmap.tobytes("png")
    finally:
        document.close()
    return "image/png", base64.b64encode(image_bytes).decode("ascii")


def _pages_with_ocr_text(
    pages: list[_TextPage],
    ocr_result: _OcrPageResult,
) -> list[_TextPage]:
    merged: list[_TextPage] = []
    replaced = False
    for page in pages:
        if page.page_number != ocr_result.page_number:
            merged.append(page)
            continue
        combined_text = "\n".join(
            part for part in (page.text.strip(), ocr_result.text.strip()) if part
        )
        merged.append(
            _TextPage(
                page_number=page.page_number,
                text=combined_text,
                tables=page.tables,
            )
        )
        replaced = True
    if not replaced:
        merged.append(_TextPage(page_number=ocr_result.page_number, text=ocr_result.text))
    return sorted(merged, key=lambda page: page.page_number)


# --- Un-extractable-font detection + auto OCR ------------------------------------------
# Some Oxygen8 submittal exports embed subset fonts with a missing/broken ToUnicode CMap.
# The pages render fine on screen but extract as machine-unreadable text: pdfplumber emits
# one "(cid:NN)" token per unmapped glyph, and PyPDF2 falls back to the font's built-in
# encoding, which on these files is ASCII shifted by a fixed offset (e.g. "Project" ->
# "3URMHFW"). Either way the tag-prefix scan and cover-header signature match nothing, so
# detection must route these pages through visual OCR instead of reporting "no coils".
_CID_TOKEN_RE = re.compile(r"\(cid:\d+\)")
# Extremely common words that any readable submittal content page carries. A text-heavy
# page with NONE of them didn't decode to real words -- the PyPDF2 fixed-offset-cipher
# fallback turns "the coil" into "WKH FRLO", erasing every one of these.
_READABLE_WORD_RE = re.compile(
    r"\b(?:the|and|coil|air|tag|model|size|unit|water|flow|total|type)\b",
    re.IGNORECASE,
)
_DEGRADED_MIN_CHARS = 200
_MAX_AUTO_OCR_PAGES = 12


def _page_text_is_degraded(text: str) -> bool:
    """True when a text-heavy page extracted as unreadable glyph soup / shifted cipher."""
    stripped = (text or "").strip()
    if len(stripped) < _DEGRADED_MIN_CHARS:
        # Too little text to judge; genuinely empty pages route through the normal
        # not-detected / OCR-hint path, not this one.
        return False
    cid_tokens = _CID_TOKEN_RE.findall(stripped)
    if cid_tokens:
        # pdfplumber emits one "(cid:N)" per unmapped glyph; a page dominated by them is
        # unreadable. A handful can be legit, so require a large share.
        cid_char_span = sum(len(token) for token in cid_tokens)
        if cid_char_span / max(len(stripped), 1) > 0.30:
            return True
    # Secondary signal for the PyPDF2 fixed-offset-cipher fallback: substantial text with
    # not one recognizable common English word.
    return _READABLE_WORD_RE.search(stripped) is None


def _degraded_page_numbers(pages: list[_TextPage]) -> list[int]:
    return [page.page_number for page in pages if _page_text_is_degraded(page.text)]


def _pages_with_replaced_text(
    pages: list[_TextPage],
    replacements: dict[int, str],
) -> list[_TextPage]:
    """Return pages with the given page numbers' text FULLY replaced (garbage dropped).

    Unlike ``_pages_with_ocr_text`` (which appends OCR text to the existing text), this
    discards the unreadable original text and its garbage tables so downstream table-first
    parsing does not consume cid-soup cells.
    """
    merged: list[_TextPage] = []
    for page in pages:
        new_text = replacements.get(page.page_number)
        if new_text is None:
            merged.append(page)
        else:
            merged.append(_TextPage(page_number=page.page_number, text=new_text, tables=()))
    return merged


def _auto_ocr_degraded_pages(
    pdf_bytes: bytes,
    *,
    degraded_pages: list[int],
) -> tuple[dict[int, str], list[_OcrPageResult]]:
    """OCR each degraded page (bounded) so cover + detail text are both recovered."""
    replacements: dict[int, str] = {}
    results: list[_OcrPageResult] = []
    for page_number in degraded_pages[:_MAX_AUTO_OCR_PAGES]:
        result = _extract_page_text_with_llm_ocr(pdf_bytes, page_number)
        results.append(result)
        if result.text:
            replacements[page_number] = result.text
    return replacements, results


def _combined_auto_ocr_status(results: list[_OcrPageResult]) -> tuple[str, str | None]:
    """Aggregate per-page auto-OCR outcomes into one (status, error) for the summary."""
    if not results:
        return "not_requested", None
    if any(result.status == "completed" for result in results):
        return "completed", None
    first = results[0]
    return first.status, first.error


# Blocking OCR statuses -> the alert shown when recovery of a degraded PDF could not
# complete. Dict order is priority: the first status any page hit is the one surfaced.
_OCR_ALERT_MESSAGES: dict[str, str] = {
    "blocked_openai_quota_exhausted": (
        "OCR blocked: OpenAI token/quota exhausted — top up billing or set a new key; "
        "coil pages could not be read."
    ),
    "blocked_openai_auth": (
        "OCR blocked: OpenAI key rejected (expired/invalid) — set a valid OPENAI_API_KEY."
    ),
    "skipped_missing_openai_api_key": (
        "OCR needed but OPENAI_API_KEY is not set — coil pages could not be read."
    ),
    "blocked_openai_rate_limited": (
        "OCR rate-limited by OpenAI — re-analyze shortly; coil pages could not be fully read."
    ),
    "failed_openai_request": (
        "OCR request to OpenAI failed — coil pages could not be read."
    ),
    "failed_render_pdf_page": (
        "OCR could not render a page image — coil pages could not be read."
    ),
    "completed_truncated": (
        "OCR output hit the token limit and was truncated — some coil rows may be missing."
    ),
    "completed_empty": (
        "OCR returned no text for an unreadable page — coil pages could not be read."
    ),
}


def _ocr_blocked_alert(
    *,
    degraded: bool,
    auto_ocr_results: list[_OcrPageResult],
) -> tuple[bool, str | None]:
    """Alert when OCR was needed (degraded pages) but a page ended in a blocking status."""
    if not degraded:
        return False, None
    for status, message in _OCR_ALERT_MESSAGES.items():
        if any(result.status == status for result in auto_ocr_results):
            return True, message
    return False, None


def detect_cover_page_from_pdf_pages(
    pages: list[_TextPage],
    *,
    cover_page_hint: int | None = None,
) -> _CoverPageDetection:
    for page in pages:
        table_detection = _detect_cover_page_from_tables(page)
        if table_detection.detected:
            return _with_continuation_cover_rows(pages, table_detection)

    for page in pages:
        text_detection = _detect_cover_page_from_text(page)
        if text_detection.detected:
            return _with_continuation_cover_rows(pages, text_detection)

    for page in pages:
        dc_quote_detection = _detect_cover_page_from_direct_coil_quote(page)
        if dc_quote_detection.detected:
            return _with_continuation_cover_rows(pages, dc_quote_detection)

    if cover_page_hint is not None:
        return _CoverPageDetection(
            detected=False,
            page_number=cover_page_hint,
            detection_method="manual_page_input_ocr_required",
            ocr_required=True,
            user_page_input_required=False,
            review_note=(
                "Cover page signature was not found in extracted text/tables. "
                f"User selected page {cover_page_hint}; LLM OCR capture is required before cover rows can be trusted."
            ),
        )

    return _CoverPageDetection(
        detected=False,
        ocr_required=True,
        user_page_input_required=True,
        review_note=(
            "Cover page signature was not found in extracted text/tables. "
            "This is likely an image/JPEG page; request user page input before LLM OCR capture."
        ),
    )


def extract_coil_lines_from_pdf_text(
    pages: list[_TextPage],
    *,
    cover_detection: _CoverPageDetection | None = None,
) -> list[SanitizedSubmittalLine]:
    extracted: dict[str, SanitizedSubmittalLine] = {}
    order = 1
    cover_detection = cover_detection or detect_cover_page_from_pdf_pages(pages)

    if cover_detection.detected:
        order = _add_cover_page_lines(extracted, cover_detection, order)

    for page in pages:
        for line_number, line in enumerate(page.text.splitlines(), start=1):
            normalized_line = _clean_line(line)
            if not normalized_line:
                continue

            qty_tag = _RE_QTY_TAG_ROW.search(normalized_line)
            if qty_tag:
                order = _add_line(extracted, "COIL_QUANTITY", qty_tag.group("qty"), order, page, line_number, "POs-style Qty/Tag row")
                order = _add_line(extracted, "COIL_TAG", _normalize_tag(qty_tag.group("tag")), order, page, line_number, "POs-style Qty/Tag row")

            component = _RE_COMPONENT_COIL.search(normalized_line)
            if component:
                coil_tag = _normalize_tag(component.group("tag"))
                existing_tag = extracted.get(normalize_source_key("COIL_TAG"))
                # A coil listed as a component (e.g. a preheat coil beneath its parent
                # air-handling unit) must win over a unit tag captured earlier by the
                # generic Qty/Tag row rule; otherwise the unit (ERV/AHU/...) shadows the
                # actual coil. Only override when no coil tag has been captured yet.
                if existing_tag is None or not _tag_prefix_is_coil(existing_tag.source_value):
                    reason = "POs-style coil component row (coil tag prioritized over unit tag)"
                    order = _set_line(extracted, "COIL_QUANTITY", component.group("qty"), order, page, line_number, reason)
                    order = _set_line(extracted, "COIL_TAG", coil_tag, order, page, line_number, reason)

            anchor = _RE_UNIT_TAG_ANCHOR.search(normalized_line)
            if anchor:
                order = _add_line(extracted, "COIL_TAG", _normalize_tag(anchor.group("value")), order, page, line_number, "POs-style Unit Tag anchor")

            ez_dx_model = _RE_EZ_DX_MODEL_NUMBER.search(normalized_line)
            if ez_dx_model:
                order = _add_line(extracted, "COIL_MODEL", ez_dx_model.group("model"), order, page, line_number, "EZ Coil drawing model number")
                order = _add_line(extracted, "HANDING", _normalize_handing(ez_dx_model.group("hand")), order, page, line_number, "EZ Coil drawing model hand suffix")
                if ez_dx_model.group("circuit").upper() == "S":
                    order = _add_line(extracted, "SYSTEM_TYPE", "Single-Circuit", order, page, line_number, "EZ Coil drawing model single-circuit suffix")

            for field_pattern in _FIELD_PATTERNS:
                if field_pattern.source_key in extracted:
                    continue
                value = _match_field_value(normalized_line, field_pattern)
                if value is None:
                    continue
                order = _add_line(extracted, field_pattern.source_key, value, order, page, line_number, "Direct Coil label match")

    if "PRODUCT_TYPE" not in extracted:
        order = _add_default_line(
            extracted,
            "PRODUCT_TYPE",
            "DX",
            order,
            "Default DX candidate for current CoilForge PDF intake scope",
        )
    if "COIL_TYPE" not in extracted:
        order = _add_default_line(
            extracted,
            "COIL_TYPE",
            "DX_HEADER1_WORKFLOW_CANDIDATE",
            order,
            "Default current CoilForge Direct Coil workflow candidate",
        )
    if "HEADER_TYPE" not in extracted:
        order = _add_default_line(
            extracted,
            "HEADER_TYPE",
            "Header 1",
            order,
            "Default current CoilForge Header 1 workflow candidate",
        )
    if "HEADER_WALL_SCHEDULE" not in extracted:
        order = _add_default_line(
            extracted,
            "HEADER_WALL_SCHEDULE",
            "",
            order,
            "Direct Coil software default header wall schedule (L)",
        )

    return list(extracted.values())


def _detect_cover_page_from_tables(page: _TextPage) -> _CoverPageDetection:
    for table in page.tables:
        header_idx, header_map = _find_cover_header_row(table)
        if header_idx is None or header_map is None:
            continue
        rows = tuple(_extract_cover_rows_from_table(page, table, header_idx, header_map))
        return _CoverPageDetection(
            detected=True,
            page_number=page.page_number,
            detection_method="pdfplumber_table_header",
            detected_headers=COVER_PAGE_REQUIRED_HEADERS,
            rows=rows,
            review_note="Cover page detected by required Qty/Tag/Item/Model/Voltage/Controls/Installation/Duct/Handing table headers.",
        )
    for table in page.tables:
        header_idx, header_map = _find_cover_coil_table(table)
        if header_idx is None or header_map is None:
            continue
        rows = tuple(_extract_cover_rows_from_table(page, table, header_idx, header_map))
        if not rows:
            continue
        return _CoverPageDetection(
            detected=True,
            page_number=page.page_number,
            detection_method="pdfplumber_table_positional_no_header",
            detected_headers=(),
            rows=rows,
            review_note=(
                "Cover coil rows detected by canonical column order in a borderless table "
                "whose header band was dropped during extraction; the column mapping is "
                "positional and requires review."
            ),
        )
    return _CoverPageDetection(detected=False)


def _detect_cover_page_from_text(page: _TextPage) -> _CoverPageDetection:
    if not _has_cover_header_signature(page.text):
        return _CoverPageDetection(detected=False)
    rows = tuple(_extract_cover_rows_from_text(page))
    return _CoverPageDetection(
        detected=True,
        page_number=page.page_number,
        detection_method="text_header_signature",
        detected_headers=COVER_PAGE_REQUIRED_HEADERS,
        rows=rows,
        review_note="Cover page detected by required header signature in extracted page text.",
    )


# Item marker: "1." alone (fitz layout) or "1. <model> ..." inline (pdfplumber layout).
_RE_DC_QUOTE_ITEM_NO = re.compile(r"^\s*(\d+)\.(?:\s+(.+))?$")


def _dc_quote_value_after_label(lines: list[str], label: str, start: int, end: int) -> str:
    """Value for a ``label:`` field within ``lines[start:end]``.

    Handles both Direct Coil quote layouts: ``Tagged: CDXC-1`` inline on one line
    (pdfplumber) and ``Tagged:`` followed by ``CDXC-1`` on the next line (fitz)."""
    want = label.strip().rstrip(":").upper()
    inline = re.compile(rf"^\s*{re.escape(want)}\s*:\s*(\S.*)$", re.IGNORECASE)
    for k in range(start, end):
        cleaned = _clean_line(lines[k])
        if (match := inline.match(cleaned)) is not None:
            return match.group(1).strip()
        if cleaned.rstrip(":").strip().upper() == want:
            for j in range(k + 1, end):
                value = _clean_line(lines[j])
                if value:
                    return value
            return ""
    return ""


def _detect_cover_page_from_direct_coil_quote(page: _TextPage) -> _CoverPageDetection:
    """Direct Coil ``COIL QUOTE`` format: a numbered item list where each item carries a
    ``Tagged:`` coil code, a model/description line, handing and quantity.

    Additive — tried only after the table/text cover detectors fail (the Oxygen8
    submittal path returns ``detected=False`` for this layout), so existing detection
    is untouched. No values are invented: each row is built straight from the quote
    text and stays review-required downstream."""
    if "COIL QUOTE" not in (page.text or "").upper():
        return _CoverPageDetection(detected=False)
    lines = page.text.splitlines()
    item_starts = [i for i, ln in enumerate(lines) if _RE_DC_QUOTE_ITEM_NO.match(ln)]
    if not item_starts:
        return _CoverPageDetection(detected=False)
    rows: list[_CoverRow] = []
    for idx, start in enumerate(item_starts):
        end = item_starts[idx + 1] if idx + 1 < len(item_starts) else len(lines)
        tag = _normalize_tag(_dc_quote_value_after_label(lines, "Tagged", start, end))
        if not tag:
            continue
        # Model/description: inline on the "N. <model>" marker (pdfplumber) or the
        # first non-empty line after a bare "N." marker (fitz).
        marker = _RE_DC_QUOTE_ITEM_NO.match(lines[start])
        model_line = (marker.group(2) or "").strip()
        if not model_line:
            for j in range(start + 1, end):
                model_line = _clean_line(lines[j])
                if model_line:
                    break
        if not _is_cover_coil_row(tag, model_line):
            continue
        rows.extend(
            _expand_cover_row(
                page_number=page.page_number,
                row_number=int(marker.group(1)),
                qty=_extract_qty(_dc_quote_value_after_label(lines, "Quantity", start, end)),
                tag=tag,
                item=model_line,
                model=model_line,
                handing=_normalize_handing(
                    _dc_quote_value_after_label(lines, "Handing", start, end)
                ),
            )
        )
    if not rows:
        return _CoverPageDetection(detected=False)
    return _CoverPageDetection(
        detected=True,
        page_number=page.page_number,
        detection_method="direct_coil_quote_numbered_items",
        rows=tuple(rows),
        review_note=(
            "Cover page detected as a Direct Coil quote (numbered 'Tagged:' coil items)."
        ),
    )


def _find_cover_header_row(
    table: tuple[tuple[str, ...], ...],
) -> tuple[int | None, dict[str, int] | None]:
    for row_index, row in enumerate(table):
        joined = "".join(_normalize_header_token(cell) for cell in row)
        if not _contains_required_cover_headers(joined):
            continue
        header_map: dict[str, int] = {}
        for key in COVER_PAGE_HEADER_KEYS:
            for column_index, cell in enumerate(row):
                normalized_cell = _normalize_header_token(cell)
                if key == normalized_cell or key in normalized_cell:
                    header_map[key] = column_index
                    break
        if all(key in header_map for key in COVER_PAGE_HEADER_KEYS):
            return row_index, header_map
    return None, None


def _find_cover_coil_table(
    table: tuple[tuple[str, ...], ...],
) -> tuple[int | None, dict[str, int] | None]:
    """Recognize a cover coil table that pdfplumber extracted without a header row.

    Some submittals render the Qty/Tag/Item/... columns as a borderless table whose
    header band is dropped during extraction, so `_find_cover_header_row` finds nothing
    even though the coil rows themselves are cleanly structured (e.g. a coil listed as a
    component beneath its parent air-handling unit). When the table is at least as wide
    as the standard cover layout and contains at least one recognizable coil row in the
    canonical column order (col 0 = quantity, col 1 = coil tag), map the columns
    positionally. The mapping stays review-required downstream; no values are invented.
    Returns ``header_idx = -1`` so `_extract_cover_rows_from_table` treats every row as
    data.
    """
    if max((len(row) for row in table), default=0) < len(COVER_PAGE_HEADER_KEYS):
        return None, None
    header_map = {key: index for index, key in enumerate(COVER_PAGE_HEADER_KEYS)}
    for row in table:
        qty = _extract_qty(_cell_at(row, header_map["qty"]))
        tag = _normalize_tag(_cell_at(row, header_map["tag"]))
        item = _cell_at(row, header_map["item"])
        if qty is not None and tag and _is_cover_coil_row(tag, item):
            return -1, header_map
    return None, None


def _extract_cover_rows_from_table(
    page: _TextPage,
    table: tuple[tuple[str, ...], ...],
    header_idx: int,
    header_map: dict[str, int],
) -> list[_CoverRow]:
    rows: list[_CoverRow] = []
    for row_number, row in enumerate(table[header_idx + 1 :], start=header_idx + 2):
        qty = _extract_qty(_cell_at(row, header_map["qty"]))
        tag = _normalize_tag(_cell_at(row, header_map["tag"]))
        item = _cell_at(row, header_map["item"])
        if not tag or not _is_cover_coil_row(tag, item):
            continue
        rows.extend(
            _expand_cover_row(
                page_number=page.page_number,
                row_number=row_number,
                qty=qty,
                tag=tag,
                item=item,
                model=_cell_at(row, header_map["model"]),
                voltage=_cell_at(row, header_map["voltage"]),
                controls_preference=_cell_at(row, header_map["controlspreference"]),
                installation=_cell_at(row, header_map["installation"]),
                duct_connection=_cell_at(row, header_map["ductconnection"]),
                handing=_cell_at(row, header_map["handing"]),
            )
        )
    return rows


def _extract_cover_rows_from_text(page: _TextPage) -> list[_CoverRow]:
    rows: list[_CoverRow] = []
    for line_number, line in enumerate(page.text.splitlines(), start=1):
        line = _clean_line(line)
        if not line or _has_cover_header_signature(line):
            continue
        row = _cover_row_from_text_line(page, line_number, line)
        if row is not None:
            rows.extend(row)
    return rows


def _with_continuation_cover_rows(
    pages: list[_TextPage],
    detection: _CoverPageDetection,
) -> _CoverPageDetection:
    if not detection.detected or detection.page_number is None:
        return detection

    rows: list[_CoverRow] = list(detection.rows)
    seen = {(row.page_number, row.row_number, row.tag) for row in rows}
    for page in sorted(pages, key=lambda item: item.page_number):
        if page.page_number <= detection.page_number:
            continue
        # Table-first, mirroring the primary cover page: continuation pages rarely
        # repeat the header row, but `_detect_cover_page_from_tables` falls back to
        # the header-less positional parser (`_find_cover_coil_table`), which reads
        # every column INCLUDING `model`. The text-line parser
        # (`_cover_row_from_text_line`) never captures `model`, so a coil whose row
        # spilled onto page 2+ used to lose its product/model code and could not
        # resolve its product line + unit size. Fall back to text only when no
        # cover table is found on the page.
        page_detection = _detect_cover_page_from_tables(page)
        continuation_rows = (
            page_detection.rows
            if page_detection.detected
            else tuple(_extract_cover_rows_from_text(page))
        )
        if not continuation_rows:
            break
        for row in continuation_rows:
            key = (row.page_number, row.row_number, row.tag)
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    if tuple(rows) == detection.rows:
        return detection
    return _CoverPageDetection(
        detected=detection.detected,
        page_number=detection.page_number,
        detection_method=detection.detection_method,
        detected_headers=detection.detected_headers,
        rows=tuple(rows),
        ocr_required=detection.ocr_required,
        user_page_input_required=detection.user_page_input_required,
        review_note=(
            f"{detection.review_note} Continuation cover rows were detected on following page(s)."
        ),
    )


def _model_code_from_row_text(text: str) -> str:
    """The unit model code embedded in a cover row's free text (e.g. ``TR_C_015``).

    The text-path row parser splits columns positionally, which drops the model on
    short / OCR-recovered rows (``1 CDXC-1 DXC Cooling TR_C_015 LH``). Recover it by
    returning the first whitespace token the product/size detector recognizes as a
    product line -- reusing ``detect_product_and_size`` so this can never drift from
    detection (matches ``TR_C_015`` and Nova/Ventum size codes alike). Returns ``""``
    when no product code is present (voltage/handing/item tokens never match).
    """
    from coilforge.submittal.coilmaster_drawing_extract import detect_product_and_size

    for token in text.split():
        token = token.strip(",;")
        if token and detect_product_and_size(token)[0]:
            return token
    return ""


def _cover_row_from_text_line(
    page: _TextPage,
    line_number: int,
    line: str,
) -> list[_CoverRow] | None:
    match = re.match(
        r"^(?P<qty>\d+)\s+(?P<tag>[A-Z0-9]+(?:\s*-\s*[A-Z0-9]+)+)\s+(?P<rest>.+)$",
        line,
        re.IGNORECASE,
    )
    if match is None:
        return None
    tag = _normalize_tag(match.group("tag"))
    rest = match.group("rest")
    item = _cover_item_from_text(rest)
    if not _is_cover_coil_row(tag, item):
        return None
    handing_match = re.search(r"\b(?P<handing>LH|RH|Left|Right|L|R)\b\s*$", rest, re.IGNORECASE)
    return _expand_cover_row(
        page_number=page.page_number,
        row_number=line_number,
        qty=_extract_qty(match.group("qty")),
        tag=tag,
        item=item,
        model=_model_code_from_row_text(rest),
        handing="" if handing_match is None else handing_match.group("handing"),
    )


def _add_cover_page_lines(
    extracted: dict[str, SanitizedSubmittalLine],
    cover_detection: _CoverPageDetection,
    order: int,
) -> int:
    selected_row = _select_cover_coil_row(cover_detection.rows)
    if selected_row is None:
        return order
    return _add_cover_row_lines(extracted, selected_row, order)


def _add_cover_row_lines(
    extracted: dict[str, SanitizedSubmittalLine],
    row: _CoverRow,
    order: int,
) -> int:
    page = _TextPage(page_number=row.page_number, text="")
    reason = "Cover-page Qty/Tag table row"
    if row.qty is not None:
        order = _add_line(extracted, "COIL_QUANTITY", str(row.qty), order, page, row.row_number, reason)
    order = _add_line(extracted, "COIL_TAG", row.tag, order, page, row.row_number, reason)
    coil_type = _derive_coil_type(row.tag, row.item)
    if coil_type:
        order = _add_line(extracted, "COIL_TYPE", coil_type, order, page, row.row_number, reason)
    order = _add_line(
        extracted,
        "PRODUCT_TYPE",
        _derive_product_type(row.tag, row.item),
        order,
        page,
        row.row_number,
        reason,
    )
    if row.handing:
        order = _add_line(extracted, "HANDING", _normalize_handing(row.handing), order, page, row.row_number, reason)
    return order


# Circuit count is sometimes stated only inside the "Coil Style" prose, e.g.
# "Interlaced 2 Circuits" or "Dual Circuit", with no discrete "Circuits:" cell. Parse
# the count out so multi-circuit coils resolve their second/Nth header instead of
# silently defaulting to 1. A bare "Intertwined"/"Interlaced" with no number is NOT
# counted -- we never guess a count that the source does not state.
_COIL_STYLE_CIRCUIT_NUM_RE = re.compile(r"(\d+)\s*[- ]?\s*Circuit", re.IGNORECASE)
_COIL_STYLE_CIRCUIT_WORDS: dict[str, int] = {
    "single": 1, "dual": 2, "double": 2, "triple": 3, "quad": 4,
}
# A word-stated count attaches to whichever circuiting descriptor the document uses --
# Oxygen8 prints all four, and R-086 names two of them itself (DX "Interlaced N
# Circuits", HGRH "Face Split N Circuits"). Project 3095 writes "Dual Face Split" /
# "Dual Interlaced", where the count is a word and the line carries no "Circuit" at all;
# gating the word map on the literal substring "circuit" therefore read those as no
# count and let them fall to circuits=1, i.e. a silently single-header drawing.
# Adjacency is required on purpose: the "Single" in "Single Row" counts rows, not
# circuits, so a count word only counts when it sits against a descriptor.
_COIL_STYLE_WORD_COUNT_RE = re.compile(
    r"\b(single|dual|double|triple|quad)\b[\s-]*"
    r"(?:face[\s-]*split|interlaced|intertwined|circuit)",
    re.IGNORECASE,
)


def _circuits_from_coil_style(text: str | None) -> int | None:
    """Circuit count embedded in a 'Coil Style' value.

    'Interlaced 2 Circuits' / '2-Circuit' -> 2; 'Dual Circuit' -> 2; 'Dual Face Split'
    -> 2; 'Dual Interlaced' -> 2; 'Single Circuit' -> 1. Returns None when no count is
    stated (a bare 'Intertwined'/'Interlaced'/'Face Split' is never assumed to be 2).
    """
    s = str(text or "")
    if (match := _COIL_STYLE_CIRCUIT_NUM_RE.search(s)):
        n = int(match.group(1))
        return n if 1 <= n <= 8 else None
    if (match := _COIL_STYLE_WORD_COUNT_RE.search(s)):
        return _COIL_STYLE_CIRCUIT_WORDS[match.group(1).lower()]
    return None


def _circuits_cell_count(
    extracted: dict[str, SanitizedSubmittalLine],
) -> int | None:
    """The circuit count stated by an extracted CIRCUITS line, or None when the line
    is absent or holds circuiting prose instead of a count."""
    line = extracted.get("CIRCUITS")
    return circuits_count_or_none(line.source_value) if line else None


def _candidate_from_cover_row(
    row: _CoverRow,
    *,
    source_id: str,
    index: int,
    detail_lines: tuple[SanitizedSubmittalLine, ...] = (),
    package_hgbp_pages: tuple[int, ...] = (),
    package_coating: str | None = None,
) -> SubmittalCoilCandidate:
    extracted: dict[str, SanitizedSubmittalLine] = {}
    order = _add_cover_row_lines(extracted, row, 1)
    order = _append_detail_lines(extracted, detail_lines, order)
    # Cover-quoted coating, applied ONLY where the coil said nothing itself -- the coil's
    # own detail block is the more specific statement and must win, which is why this runs
    # AFTER the detail lines rather than riding in with the shared unit lines (those are
    # prepended, and would outrank the block). Water coils are excluded outright: a water
    # coil is never coated, so a package coating simply is not about them.
    if (
        package_coating
        and normalize_source_key("COIL_COATING") not in extracted
        and _derive_coil_format(row.tag, row.item) not in _WATER_COIL_FORMATS
    ):
        order = _add_default_line(
            extracted,
            "COIL_COATING",
            package_coating,
            order,
            "Coating quoted as a cover-page line item for the package",
        )
    # Derive the circuit count from the "Coil Style" prose when no discrete "Circuits"
    # cell was extracted (e.g. "Coil Style: Interlaced 2 Circuits"). Inferred ->
    # review-required; the explicit CIRCUITS label, when present, wins -- but only when
    # it states a COUNT. A Circuits cell holding circuiting prose ("3 Feeds/26 Passes/
    # 2DT") is blocked in extract.py, so it must not suppress the Coil Style rescue.
    if _circuits_cell_count(extracted) is None and "COIL_STYLE" in extracted:
        style_line = extracted["COIL_STYLE"]
        circuits_from_style = _circuits_from_coil_style(style_line.source_value)
        if circuits_from_style is not None:
            order = _add_line(
                extracted,
                "CIRCUITS_FROM_STYLE",
                str(circuits_from_style),
                order,
                _TextPage(page_number=style_line.source_page or 0, text=""),
                style_line.line_number,
                f"Circuit count derived from Coil Style '{style_line.source_value}'",
            )
    order = _add_default_line(
        extracted,
        "HEADER_TYPE",
        "Header 1",
        order,
        "Default current CoilForge Header 1 workflow candidate",
    )
    if "PRODUCT_TYPE" not in extracted:
        order = _add_default_line(
            extracted,
            "PRODUCT_TYPE",
            _derive_product_type(row.tag, row.item),
            order,
            "Cover-page product type fallback",
        )
    if "COIL_TYPE" not in extracted:
        order = _add_default_line(
            extracted,
            "COIL_TYPE",
            _derive_coil_type(row.tag, row.item) or "DX_HEADER1_WORKFLOW_CANDIDATE",
            order,
            "Cover-page coil type fallback",
        )
    if "HEADER_WALL_SCHEDULE" not in extracted:
        order = _add_default_line(
            extracted,
            "HEADER_WALL_SCHEDULE",
            "",
            order,
            "Direct Coil software default header wall schedule (L)",
        )
    candidate = extract_submittal_candidate_from_structured(
        list(extracted.values()),
        source_id=f"{source_id}-{_candidate_slug(row.tag, index)}",
        field_rules=PDF_INTAKE_FIELD_RULES,
    )
    # Carry the cover-page product/model code forward so the drawing context can
    # derive the CoilForge product line + unit size from it (e.g. "TR_C_040" ->
    # Terra H / 040) and run the rule engine. Review-aid; overridable in the picker.
    model_notes = (
        [f"Cover product/model code: {row.model}"] if row.model else []
    )
    # Hot gas bypass is quoted once for the whole project, so carry the package-level
    # fact onto each DX coil -- DX ONLY. _entry_for_dx_hgbp is the sole producer of HGBP
    # template buckets and it is DX-only, so tagging an HGRH/CWC/HWC coil HGBP would find
    # no bucket and blank its drawing silently. Leaving water/reheat coils alone routes
    # them to their normal Header N bucket, unchanged.
    #
    # The note is the transport: workflows.submittal_to_drawing._detect_hgbp reads the
    # joined candidate notes and matches the literal "HGBP" token below. Keep both sides
    # in step -- rewording this string without that regex silently drops the routing.
    hgbp_notes = (
        [
            "Cover option: hot-gas bypass (HGBP) adder stated on cover page "
            + ", ".join(str(p) for p in package_hgbp_pages)
        ]
        if package_hgbp_pages and _is_dx_cover_row(row)
        else []
    )
    return candidate.model_copy(
        update={
            "candidate_id": f"SCC-{source_id}-{_candidate_slug(row.tag, index)}",
            "notes": [
                *candidate.notes,
                "Created from one cover-page coil row for separate review page generation.",
                *model_notes,
                *hgbp_notes,
            ],
        }
    )


def _is_cover_page_text_row(
    line: str,
    page: _TextPage,
    cover_detection: _CoverPageDetection,
) -> bool:
    if not cover_detection.detected:
        return False
    if _has_cover_header_signature(line):
        return True
    rows = _cover_row_from_text_line(page, 0, line)
    if rows is None:
        return False
    known_tags = {row.tag for row in cover_detection.rows}
    return any(row.tag in known_tags for row in rows)


def _detail_lines_by_cover_row(
    pages: list[_TextPage],
    cover_detection: _CoverPageDetection,
) -> dict[str, tuple[SanitizedSubmittalLine, ...]]:
    rows = tuple(cover_detection.rows)
    if not rows:
        return {}

    detail_lines: dict[str, list[SanitizedSubmittalLine]] = {row.tag: [] for row in rows}
    known_tags = tuple(detail_lines)
    blocks_by_format: dict[str, list[tuple[_TextPage, _DetailSectionBlock]]] = {}
    for page in pages:
        ordered_blocks = _ordered_detail_blocks_from_page(page, cover_detection)
        if ordered_blocks:
            for block in ordered_blocks:
                blocks_by_format.setdefault(block.coil_format, []).append((page, block))
            continue
        page_tags = _detail_page_tags(page.text, known_tags)
        if not page_tags:
            continue
        extracted = _extract_detail_lines_from_page(page)
        for tag in page_tags:
            detail_lines[tag].extend(extracted)

    for row in rows:
        coil_format = _derive_coil_format(row.tag, row.item)
        matching_blocks = blocks_by_format.get(coil_format, [])
        if not matching_blocks:
            continue
        page, block = matching_blocks.pop(0)
        detail_lines[row.tag].extend(
            _extract_detail_lines_from_block(
                page, block.lines, coil_format=block.coil_format
            )
        )

    return {tag: tuple(lines) for tag, lines in detail_lines.items()}


def _shared_unit_lines_for_cover_candidates(
    pages: list[_TextPage],
) -> tuple[SanitizedSubmittalLine, ...]:
    extracted: dict[str, SanitizedSubmittalLine] = {}
    order = 1
    shared_keys = {"ALTITUDE_FT"}
    for page in pages:
        for line_number, line in enumerate(page.text.splitlines(), start=1):
            normalized_line = _clean_line(line)
            if not normalized_line:
                continue
            for field_pattern in _FIELD_PATTERNS:
                if field_pattern.source_key not in shared_keys:
                    continue
                if normalize_source_key(field_pattern.source_key) in extracted:
                    continue
                value = _match_field_value(normalized_line, field_pattern)
                if value is None:
                    continue
                order = _add_line(
                    extracted,
                    field_pattern.source_key,
                    value,
                    order,
                    page,
                    line_number,
                    "unit-level shared PDF value",
                )
    return tuple(extracted.values())


def _ordered_detail_blocks_from_page(
    page: _TextPage,
    cover_detection: _CoverPageDetection,
) -> tuple[_DetailSectionBlock, ...]:
    blocks: list[_DetailSectionBlock] = []
    active_block: list[tuple[int, str]] | None = None
    active_format: str | None = None
    for line_number, line in enumerate(page.text.splitlines(), start=1):
        normalized_line = _clean_line(line)
        if not normalized_line or _is_cover_page_text_row(normalized_line, page, cover_detection):
            continue
        if _DETAIL_SECTION_STOP_PATTERN.search(normalized_line):
            if active_format is not None and active_block:
                blocks.append(_DetailSectionBlock(active_format, tuple(active_block)))
            active_block = None
            active_format = None
            continue
        section_format = _detail_section_format(normalized_line)
        if section_format is not None:
            if active_format is not None and active_block:
                blocks.append(_DetailSectionBlock(active_format, tuple(active_block)))
            active_block = []
            active_format = section_format
            continue
        if active_block is not None:
            active_block.append((line_number, normalized_line))
    if active_format is not None and active_block:
        blocks.append(_DetailSectionBlock(active_format, tuple(active_block)))
    return tuple(blocks)


def _detail_page_tags(text: str, known_tags: tuple[str, ...]) -> tuple[str, ...]:
    normalized_text = _normalize_tag_search_text(text)
    matched = tuple(
        tag for tag in known_tags if _normalize_tag_search_text(tag) in normalized_text
    )
    if matched:
        return matched
    if len(known_tags) == 1 and _DETAIL_SECTION_HEADER_PATTERN.search(text):
        return known_tags
    return ()


def _detail_section_format(line: str) -> str | None:
    normalized = _normalize_header_token(line)
    if normalized in {"coolingdx", "condensingcoildata"}:
        return "dx"
    if normalized in {"reheathotgasreheatcoil", "hgrhcoildata", "hgrccoildata"}:
        return "condensing"
    if normalized in {"coolingcwc", "chilledwatercoildata", "fluidcoildata"}:
        return "cooling_chilled_water"
    if normalized in {"preheathwc", "preheathotwatercoildata"}:
        return "preheat_hot_water"
    if normalized in {"heatinghwc", "heatinghotwatercoildata", "hotwatercoildata"}:
        return "heating_hot_water"
    return None


def _extract_detail_lines_from_page(page: _TextPage) -> tuple[SanitizedSubmittalLine, ...]:
    block = tuple(
        (line_number, _clean_line(line))
        for line_number, line in enumerate(page.text.splitlines(), start=1)
        if _clean_line(line)
    )
    return _extract_detail_lines_from_block(page, block)


# The submittal states a custom coil coating as an ASTERISK-DELIMITED annotation inside the
# coil detail block -- "*Finkote2 Epoxy Coil Coating*" -- either standalone (2968 HTS Houston
# / College of the Mainland p.26, Cooling DX) or trailing another label/value line ("Coil
# Weight (lbs) 32.94 *Finkote2 Epoxy Coil Coating*", p.27, Reheat HGRH). It is NOT a
# "Coil Coating: <value>" label line, so the COIL_COATING _FieldPattern never matched it:
# every coated coil read as the "Plain" Direct Coil default AND lost the R-080/R-081
# "Do Not Coat Last 5-6 inches..." drawing note, which fires `only_when: coating_set`
# (John 2026-07-31).
#
# BOTH asterisks are required. The same blocks carry UNTERMINATED footnote markers --
# "*Separate electrical connection required for heater" (p.27, inside the condensing block,
# whose boundary runs on into the Backup Heating section) -- so the closing "*" plus the
# literal "coating" token is what keeps those out.
_DETAIL_COATING_ANNOTATION_RE = re.compile(
    r"\*\s*(?P<value>[^*]*\bcoating\b[^*]*?)\s*\*", re.IGNORECASE
)


def _extract_detail_lines_from_block(
    page: _TextPage,
    block: tuple[tuple[int, str], ...],
    *,
    coil_format: str | None = None,
) -> tuple[SanitizedSubmittalLine, ...]:
    extracted: dict[str, SanitizedSubmittalLine] = {}
    order = 1
    # Tables-first: pdfplumber preserves the submittal's side-by-side label/value
    # columns, so reading the structured cells maps each value to the right field
    # (e.g. Fin Height -> 12, Entering DB/WB -> 95/80) instead of letting the
    # flattened text line bleed columns together. `_add_line` is first-wins, so the
    # text-line parser below only fills source_keys the tables did not supply.
    order = _seed_detail_lines_from_tables(
        extracted, order, page, coil_format=coil_format
    )
    contexts: tuple[str, ...] = ()
    for line_number, normalized_line in block:
        if not normalized_line:
            continue
        next_contexts = _detail_subsection_contexts(normalized_line)
        if next_contexts:
            contexts = next_contexts
            continue
        value_line, trailing_contexts = _strip_trailing_detail_contexts(normalized_line)
        for source_key, value in _contextual_detail_values(value_line, contexts):
            order = _add_line(
                extracted,
                source_key,
                value,
                order,
                page,
                line_number,
                "detail page section label match",
            )
        if trailing_contexts:
            contexts = trailing_contexts
        # Read off `normalized_line`, not `value_line`: the annotation is not a label/value
        # pair, and this must not consume the line -- p.27 carries the coating annotation
        # and a Coil Weight reading on the SAME line, and both are wanted.
        coating_match = _DETAIL_COATING_ANNOTATION_RE.search(normalized_line)
        if coating_match:
            order = _add_line(
                extracted,
                "COIL_COATING",
                _clean_line(coating_match.group("value")),
                order,
                page,
                line_number,
                "detail page coating annotation",
            )
        for field_pattern in _FIELD_PATTERNS:
            if field_pattern.source_key in {"COIL_TAG", "COIL_QUANTITY"}:
                continue
            if normalize_source_key(field_pattern.source_key) in extracted:
                continue
            value = _match_field_value(value_line, field_pattern)
            if value is None:
                continue
            order = _add_line(
                extracted,
                field_pattern.source_key,
                value,
                order,
                page,
                line_number,
                "detail page label match",
            )
    _drop_coating_from_water_coil(extracted, coil_format)
    return tuple(extracted.values())


# A water coil is NEVER coated (John 2026-08-05). So a coating reading on a CWC/HWC/PHWC
# block is not that coil's coating -- it belongs to a neighbouring coil. The detail blocks
# genuinely bleed: `_DETAIL_COATING_ANNOTATION_RE`'s own comment records a condensing block
# whose boundary "runs on into the Backup Heating section", and the annotation is a free
# footnote rather than a label/value pair anchored to a coil.
#
# Dropped at the END of extraction rather than at each reader, because COIL_COATING has
# THREE sources here (the structured table seed, the asterisk annotation, and the
# "Coil Coating: <value>" label pattern) and gating them one by one would leave the next
# reader to re-open the hole. Un-formatted blocks (coil_format None) are left alone -- we
# only suppress where the coil is KNOWN to be a water coil.
#
# This is a suppression, not a silent data loss: the value would have been wrong, and the
# Direct Coil "Coil Coating" field falls back to its declared default. R-080/R-081 are
# already DX/HGRH-only, so no drawing note depended on it.
_WATER_COIL_FORMATS = frozenset(
    {"heating_hot_water", "preheat_hot_water", "cooling_chilled_water"}
)


def _drop_coating_from_water_coil(
    extracted: dict[str, SanitizedSubmittalLine], coil_format: str | None
) -> None:
    if coil_format in _WATER_COIL_FORMATS:
        extracted.pop(normalize_source_key("COIL_COATING"), None)


# --------------------------------------------------------------------------- #
# Structured-table detail extraction
# --------------------------------------------------------------------------- #
# pdfplumber already returns the submittal's detail grid as structured cells
# (`_TextPage.tables`). The detail grid lays sections out side by side in
# columns -- e.g. col0/1 = "Coil" (Fin Height, Fin Length, FPI, Rows...),
# col4/5 = "Entering" (Airflow, DB (F), WB (F), Refrigerant...), col7/8 =
# "Coil Operating Setpoint" / "Max Coil Performance". Reading the cells maps each
# value to the right field; the flattened text line cannot (it concatenates the
# columns, so a greedy label capture swallows the neighbouring section's text).
# These helpers reuse the existing context detection and label maps; only the
# read mechanism differs.


def _table_coil_format(table: tuple[tuple[str, ...], ...]) -> str | None:
    """Identify which coil_format a detail table describes from its title cells,
    mirroring `_detail_section_format` (the text-block path) so table fields
    attach to the same coil on multi-coil pages."""
    for row in table[:4]:
        for cell in row:
            fmt = _detail_section_format(_clean_cell(cell))
            if fmt is not None:
                return fmt
    return None


def _detail_table_section_columns(
    table: tuple[tuple[str, ...], ...],
) -> tuple[tuple[int, tuple[tuple[int, str], ...]], ...]:
    """Per section column, the ordered ``(row_index, context)`` switches in it.

    The COLUMN LAYOUT still comes from the first row carrying any section token
    (e.g. col0/col4/col7), because those columns are also the value-range
    boundaries. What changed (John 2026-07-28) is that a column may hold SEVERAL
    sections stacked vertically -- the Oxygen8 detail grid puts "Coil Operating
    Setpoint" and "Max Coil Performance" one above the other in the same column
    (p8 col7 r2/r7 on DX, p9 col7 r2/r5 on HWC). Returning one context per column
    matched every later row against the FIRST section's label map, so the whole
    "Max Coil Performance" block (Capacity / Air Vel / Fluid Flow Rate / Fluid PD
    / leaving DB) was silently dropped. On DX the text-line parser happened to
    rescue those rows because they sat on otherwise-empty lines; on a water coil
    the denser "Coil" column collides with them, so nothing rescued them.

    Falls back to a single label column at col0 with the 'coil' context for plain
    label/value tables with no section header."""
    layout: list[int] = []
    for row in table:
        layout = [
            col
            for col, cell in enumerate(row)
            if _detail_subsection_contexts(_clean_cell(cell))
        ]
        if layout:
            break
    if not layout:
        return ((0, ((0, "coil"),)),)

    sections: list[tuple[int, tuple[tuple[int, str], ...]]] = []
    for col in layout:
        switches: list[tuple[int, str]] = []
        for row_index, row in enumerate(table):
            if col >= len(row):
                continue
            contexts = _detail_subsection_contexts(_clean_cell(row[col]))
            if contexts:
                switches.append((row_index, contexts[0]))
        if switches:
            sections.append((col, tuple(switches)))
    return tuple(sections)


def _context_at_row(switches: tuple[tuple[int, str], ...], row_index: int) -> str:
    """The section context in force at ``row_index`` -- the last switch at or above
    it. Rows ABOVE the column's first section header keep that first context, which
    is exactly what the old one-context-per-column code did for them, so only the
    stacked-section rows change behaviour."""
    context = switches[0][1]
    for switch_row, switch_context in switches:
        if switch_row > row_index:
            break
        context = switch_context
    return context


def _match_detail_label(label_cell: str, context: str) -> str | None:
    """Resolve a label cell to a source_key within a context (longest label first),
    reusing `_CONTEXTUAL_DETAIL_LABELS`. Exact (normalized) match only -- the value
    lives in a separate cell, so there is no greedy remainder to guess at."""
    norm = _clean_cell(label_cell).rstrip(":").strip().lower()
    if not norm:
        return None
    candidates = sorted(
        _CONTEXTUAL_DETAIL_LABELS.get(context, ()),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for label, source_key in candidates:
        if norm == label.rstrip(":").strip().lower():
            return source_key
    return None


def _detail_table_field_pairs(
    table: tuple[tuple[str, ...], ...],
) -> tuple[tuple[str, str, int, int], ...]:
    """Extract (source_key, value, row_index, col_index) from a structured detail
    table: per section column, the label cell maps to the first non-empty cell to
    its right (up to the next section column), so spacer columns and 2-column
    label/value tables are handled uniformly. The label map used for a cell is the
    section in force at THAT ROW of THAT COLUMN, so a column stacking several
    sections (Coil Operating Setpoint above Max Coil Performance) reads each block
    against its own labels."""
    sections = _detail_table_section_columns(table)
    cols = [col for col, _ in sections]
    pairs: list[tuple[str, str, int, int]] = []
    for row_index, row in enumerate(table):
        for section_index, (col, switches) in enumerate(sections):
            if col >= len(row):
                continue
            label_cell = _clean_cell(row[col])
            if not label_cell:
                continue
            source_key = _match_detail_label(
                label_cell, _context_at_row(switches, row_index)
            )
            if source_key is None:
                continue
            next_col = cols[section_index + 1] if section_index + 1 < len(cols) else len(row)
            value = ""
            for value_col in range(col + 1, min(next_col, len(row))):
                cell = _clean_cell(row[value_col])
                if cell:
                    value = cell
                    break
            if value:
                pairs.append((source_key, value, row_index, col))
    return tuple(pairs)


def _seed_detail_lines_from_tables(
    extracted: dict[str, SanitizedSubmittalLine],
    order: int,
    page: _TextPage,
    *,
    coil_format: str | None,
) -> int:
    """Seed `extracted` from the page's structured tables before the text-line
    parser runs. When a coil_format is known (multi-coil pages), only tables whose
    own title matches that format are consumed, preventing cross-coil bleed."""
    for table_index, table in enumerate(page.tables):
        if coil_format is not None and _table_coil_format(table) != coil_format:
            continue
        for source_key, value, row_index, col_index in _detail_table_field_pairs(table):
            order = _add_line(
                extracted,
                source_key,
                value,
                order,
                page,
                row_index + 1,
                f"detail table[{table_index}] r{row_index} c{col_index} cell match",
            )
    return order


_CONTEXTUAL_DETAIL_LABELS: dict[str, tuple[tuple[str, str], ...]] = {
    "coil": (
        ("Model", "COIL_MODEL"),
        ("Fin Height (in)", "FINNED_HEIGHT"),
        ("Fin Length (in)", "FINNED_LENGTH"),
        ("Face Area (sq.ft)", "FACE_AREA_SQFT"),
        ("Face Area(sq.ft)", "FACE_AREA_SQFT"),
        ("FPI", "FINS_PER_INCH"),
        ("Rows", "ROWS_DEEP"),
        ("Circuits", "CIRCUITS"),
        ("Total Feeds", "NUMBER_OF_FEEDS_TOTAL"),
        ("Fin Surface", "FIN_SURFACE"),
        ("Fin Material", "FIN_MATERIAL"),
        ("Tube Material", "TUBE_MATERIAL"),
        ("Tube Surface", "TUBE_SURFACE"),
        ("Coil Weight (lbs)", "COIL_WEIGHT_LBS"),
        ("Suction Size (in)", "RETURN_CONNECTION_SIZE"),
        # Oxygen8 submittals consistently mis-spell "Suction" as "Sunction";
        # match the typo (and the unit-less form) so the connection size is read.
        ("Sunction Size (in)", "RETURN_CONNECTION_SIZE"),
        ("Sunction Size", "RETURN_CONNECTION_SIZE"),
        # "Suntion" is a further mis-spelling seen on the HGRH reheat coil tables
        # (John 2026-06-25); without it the connection size (and thus drawing "R")
        # is dropped because the label match is exact.
        ("Suntion Size (in)", "RETURN_CONNECTION_SIZE"),
        ("Suntion Size", "RETURN_CONNECTION_SIZE"),
        ("Suction Size", "RETURN_CONNECTION_SIZE"),
        # The HGRH (Reheat Hot Gas Reheat) coil block labels its single connection
        # plainly "Connection Size (in)" — not "Suction/Suntion Size" — so without
        # this the connection size (and thus drawing "R" via R-052) is dropped
        # (2766 Olympic RHHGRH-2; John 2026-06-27). Exact-match only (see
        # `_match_contextual_detail_label`), so it cannot swallow
        # "Supply/Return Connection Size".
        ("Connection Size (in)", "RETURN_CONNECTION_SIZE"),
        ("Connection Size", "RETURN_CONNECTION_SIZE"),
        ("Inlet Conn. Size (in)", "INLET_CONNECTION_SIZE"),
        ("Inlet Conn. Size", "INLET_CONNECTION_SIZE"),
        ("Outlet Conn. Size (in)", "OUTLET_CONNECTION_SIZE"),
        ("Outlet Conn. Size", "OUTLET_CONNECTION_SIZE"),
        ("Fin Thickness (in)", "FIN_THICKNESS_IN"),
        ("Coil Depth (in)", "COIL_DEPTH_IN"),
        ("Coil Style", "COIL_STYLE"),
        ("Qty Conn. / Header", "QUANTITY_CONNECTIONS_PER_HEADER"),
    ),
    "entering": (
        ("Airflow (CFM)", "TOTAL_AIR_FLOW_CFM"),
        ("DB (F)", "ENTERING_DRY_BULB_F"),
        ("WB (F)", "ENTERING_WET_BULB_F"),
        ("Refrigerant", "REFRIGERANT"),
        ("Fluid Type", "FLUID_TYPE"),
        ("Fluid Percent (%)", "FLUID_PERCENT"),
        ("Fluid Ent Temp (F)", "FLUID_ENTERING_TEMP_F"),
        ("Fluid Lvg Temp (F)", "FLUID_LEAVING_TEMP_F"),
        ("Refrig. Suction Temp (F)", "EVAPORATING_TEMPERATURE_F"),
        ("Refrig. Liquid Temp (F)", "LIQUID_TEMPERATURE_F"),
        ("Refrig. Superheat Temp (F)", "SUPERHEAT_F"),
        ("Refrig. Cond. Temp (F)", "CONDENSING_TEMPERATURE_F"),
        ("Refrig. Subcooling Temp (F)", "SUBCOOLING_F"),
        ("Refrig. Vapor Temp (F)", "VAPOR_TEMPERATURE_F"),
    ),
    "operating_setpoint": (
        ("Nominal Cooling Capacity (MBH)", "NOMINAL_COOLING_CAPACITY_MBH"),
        ("Design Capacity Sensible (MBH)", "SENSIBLE_CAPACITY_MBH"),
        ("Nominal Capacity Sensible (MBH)", "NOMINAL_COOLING_CAPACITY_MBH"),
        ("DB (F)", "OPERATING_SETPOINT_DB_F"),
    ),
    "max_performance": (
        ("Capacity Sensible (MBH)", "SENSIBLE_CAPACITY_MBH"),
        ("Capacity (MBH)", "TOTAL_CAPACITY_MBH"),
        # "Max Coil Performance" DB/WB is the coil's LEAVING air (John 2026-07-22): the coil
        # output at max load. Mapped to airside leaving_* so it surfaces as Leaving Dry/Wet
        # Bulb, not the vestigial performance.max_*_bulb_f (which nothing consumed downstream).
        ("DB (F)", "LEAVING_DRY_BULB_F"),
        ("WB (F)", "LEAVING_WET_BULB_F"),
        ("Air Vel (FPM)", "FACE_VELOCITY_FPM"),
        ("Air PD (IWG)", "AIR_PRESSURE_DROP_IWG"),
        ("Air PD (inWG)", "AIR_PRESSURE_DROP_IWG"),
        ("Fluid Flow Rate (GPM)", "FLUID_FLOW_RATE_GPM"),
        ("Fluid PD (ftWG)", "FLUID_PRESSURE_DROP_FTWG"),
        ("Fluid Vel (fps)", "FLUID_VELOCITY_FPS"),
        ("Internal Vol (cu.in)", "INTERNAL_VOLUME_CUIN"),
        ("Refrig. PD (psi)", "REFRIGERANT_PRESSURE_DROP_PSI"),
    ),
    "valve": (
        ("Valve Spec", "VALVE_SPEC"),
        ("Actuator", "VALVE_ACTUATOR"),
        ("Valve Size (in)", "VALVE_SIZE"),
        ("Control Valve (Cv)", "CONTROL_VALVE_CV"),
        ("Description", "VALVE_DESCRIPTION"),
    ),
    "vrv": (
        ("Type", "VRV_KIT_TYPE"),
        ("Manufacturer", "VRV_KIT_MANUFACTURER"),
        ("Daikin System Type", "VRV_SYSTEM_TYPE"),
        ("Model", "VRV_KIT_MODEL"),
        ("Qty of Valves", "VRV_QUANTITY_OF_VALVES"),
        ("Nominal Tonnage", "VRV_NOMINAL_TONNAGE"),
    ),
}


_DETAIL_SUBSECTION_CONTEXT_TOKENS: tuple[tuple[str, str], ...] = (
    ("coiloperatingsetpoint", "operating_setpoint"),
    ("maxcoilperformance", "max_performance"),
    ("valveactuator", "valve"),
    ("vrvintegrationkit", "vrv"),
    ("entering", "entering"),
    ("coil", "coil"),
)


_TRAILING_DETAIL_CONTEXT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?P<value>.*?)(?:\s*)Coil\s+Operating\s+Setpoint\s*$", re.IGNORECASE), "operating_setpoint"),
    (re.compile(r"(?P<value>.*?)(?:\s*)Max\s+Coil\s+Performance\s*$", re.IGNORECASE), "max_performance"),
    (re.compile(r"(?P<value>.*?)(?:\s*)Valve\s*&?\s*Actuator\s*$", re.IGNORECASE), "valve"),
    (re.compile(r"(?P<value>.*?)(?:\s*)VRV\s+Integration\s+Kit\s*$", re.IGNORECASE), "vrv"),
    (re.compile(r"(?P<value>.*?)(?:\s*)Entering\s*$", re.IGNORECASE), "entering"),
)


def _detail_subsection_context(line: str) -> str | None:
    contexts = _detail_subsection_contexts(line)
    return contexts[0] if contexts else None


def _detail_subsection_contexts(line: str) -> tuple[str, ...]:
    normalized = _normalize_header_token(line)
    if not normalized:
        return ()
    contexts: list[str] = []
    cursor = 0
    while cursor < len(normalized):
        match = next(
            (
                (token, context)
                for token, context in _DETAIL_SUBSECTION_CONTEXT_TOKENS
                if normalized.startswith(token, cursor)
            ),
            None,
        )
        if match is None:
            return ()
        token, context = match
        contexts.append(context)
        cursor += len(token)
    return tuple(contexts)


def _strip_trailing_detail_contexts(line: str) -> tuple[str, tuple[str, ...]]:
    current_line = line
    contexts: list[str] = []
    while current_line:
        match = next(
            (
                (pattern_match, context)
                for pattern, context in _TRAILING_DETAIL_CONTEXT_PATTERNS
                if (pattern_match := pattern.match(current_line)) is not None
            ),
            None,
        )
        if match is None:
            break
        pattern_match, context = match
        stripped_line = _clean_line(pattern_match.group("value"))
        if stripped_line == current_line:
            break
        current_line = stripped_line
        contexts.insert(0, context)
    return current_line, tuple(contexts)


def _contextual_detail_values(line: str, contexts: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    if not contexts:
        return ()
    matches: list[tuple[str, str]] = []
    for context in contexts:
        for label, source_key in sorted(
            _CONTEXTUAL_DETAIL_LABELS.get(context, ()),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            value = _value_after_label(line, label)
            if value is None:
                continue
            matches.append((source_key, value))
            return tuple(matches)
    return tuple(matches)


def _value_after_label(line: str, label: str) -> str | None:
    label_pattern = re.escape(label).replace(r"\ ", r"\s+")
    match = re.match(
        rf"^{label_pattern}\s*:?\s*(?P<value>.+?)\s*$",
        line,
        re.IGNORECASE,
    )
    if match is None:
        return None
    value = _clean_value(match.group("value"))
    return value or None


def _append_detail_lines(
    extracted: dict[str, SanitizedSubmittalLine],
    detail_lines: tuple[SanitizedSubmittalLine, ...],
    order: int,
) -> int:
    for line in detail_lines:
        normalized_key = normalize_source_key(line.source_key)
        if normalized_key in extracted:
            continue
        extracted[normalized_key] = replace(line, line_number=order)
        order += 1
    return order


def _cover_row_summary(row: _CoverRow) -> PdfCoverRowSummary:
    product_line, unit_size = _derive_product_line_and_size(row.model, row.tag, row.item)
    return PdfCoverRowSummary(
        page_number=row.page_number,
        row_number=row.row_number,
        quantity=row.qty,
        tag=row.tag,
        item=row.item,
        model=row.model,
        voltage=row.voltage,
        controls_preference=row.controls_preference,
        installation=row.installation,
        duct_connection=row.duct_connection,
        handing=_normalize_handing(row.handing) if row.handing else "",
        product_type=_derive_product_type(row.tag, row.item),
        coil_format=_derive_coil_format(row.tag, row.item),
        product_line=product_line,
        unit_size=unit_size,
    )


def _candidate_slug(tag: str, index: int) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "-", _normalize_tag(tag)).strip("-")
    return slug or f"COVER-ROW-{index}"


def _add_default_line(
    extracted: dict[str, SanitizedSubmittalLine],
    source_key: str,
    source_value: str,
    order: int,
    reason: str,
) -> int:
    return _add_line(
        extracted,
        source_key,
        source_value,
        order,
        _TextPage(page_number=0, text=""),
        0,
        reason,
    )


def _contains_required_cover_headers(normalized_text: str) -> bool:
    cursor = 0
    for key in COVER_PAGE_HEADER_KEYS:
        position = normalized_text.find(key, cursor)
        if position < 0:
            return False
        cursor = position + len(key)
    return True


def _has_cover_header_signature(value: str) -> bool:
    return _contains_required_cover_headers(_normalize_header_token(value))


def _normalize_header_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _cell_at(row: tuple[str, ...], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return _clean_cell(row[index])


def _extract_qty(raw: Any) -> int | None:
    match = re.search(r"\d+", str(raw or ""))
    return int(match.group(0)) if match else None


def _is_cover_coil_row(tag: str, item: str) -> bool:
    normalized_tag = _normalize_tag(tag)
    tag_prefix = normalized_tag.split("-", 1)[0]
    normalized_item = _normalize_header_token(item)
    # Reject valves / EEV kits / accessories before the coil-keyword fallthrough so a
    # description like "EKEXV Valve (DX Coil)" can't sneak through on the "dxcoil" token.
    if tag_prefix in _NON_COIL_TAG_PREFIXES:
        return False
    if any(token in normalized_item for token in _NON_COIL_ITEM_TOKENS):
        return False
    if tag_prefix in _COIL_TAG_PREFIXES:
        return True
    return any(
        token in normalized_item
        for token in (
            "dxccooling",
            "coolingcoil",
            "hgrcreheat",
            "hgrhreheat",
            "reheatcoil",
            "dxcoil",
            "hotwatercoil",
            "chilledwatercoil",
        )
    )


def _expand_cover_row(
    *,
    page_number: int,
    row_number: int,
    qty: int | None,
    tag: str,
    item: str = "",
    model: str = "",
    voltage: str = "",
    controls_preference: str = "",
    installation: str = "",
    duct_connection: str = "",
    handing: str = "",
) -> list[_CoverRow]:
    tags = _expand_cover_tags(tag, qty)
    split_qty = len(tags) > 1
    return [
        _CoverRow(
            page_number=page_number,
            row_number=row_number,
            qty=1 if split_qty else qty,
            tag=unit_tag,
            item=item,
            model=model,
            voltage=voltage,
            controls_preference=controls_preference,
            installation=installation,
            duct_connection=duct_connection,
            handing=handing,
        )
        for unit_tag in tags
    ]


def _expand_cover_tags(raw_tag: str, qty: int | None) -> list[str]:
    if "," not in str(raw_tag or ""):
        return [_normalize_tag(raw_tag)] if _normalize_tag(raw_tag) else []
    tags = [_normalize_tag(part) for part in str(raw_tag).split(",") if _normalize_tag(part)]
    if len(tags) < 2 or qty != len(tags):
        return [_normalize_tag(raw_tag)]
    return tags


def _select_cover_coil_row(rows: tuple[_CoverRow, ...]) -> _CoverRow | None:
    if not rows:
        return None
    for row in rows:
        if row.tag.startswith("CDXC-"):
            return row
    return rows[0]


def _cover_item_from_text(value: str) -> str:
    for pattern in (
        "DXC Cooling",
        "HGRC Reheat",
        "HGRH Reheat",
        "Pre Hot Water Coil",
        "Post Hot Water Coil",
        "Chilled Water Coil",
        "Hot Water Coil",
        "CCW Coil",
        "HHW Coil",
        "CW Coil",
        "HW Coil",
        "DX Coil",
        "Cooling Coil",
        "Reheat Coil",
    ):
        if re.search(re.escape(pattern), value, re.IGNORECASE):
            return pattern
    return ""


def _derive_product_line_and_size(*texts: str) -> tuple[str, str]:
    """Derive the CoilForge product line + unit size from the cover product/model
    code using the existing R-076-validated rule (e.g. "TR_C_040" -> ("TERRA H",
    "040")). Returns ("", "") when no code in `texts` validates. Review-aid only."""
    from coilforge.submittal.coilmaster_drawing_extract import detect_product_and_size

    blob = " ".join(t for t in texts if t)
    line, size = detect_product_and_size(blob)
    return line or "", size or ""


def _derive_product_type(tag: str, item: str) -> str:
    tag_prefix = _normalize_tag(tag).split("-", 1)[0]
    if tag_prefix in _PRODUCT_TYPE_BY_PREFIX:
        return _PRODUCT_TYPE_BY_PREFIX[tag_prefix]
    normalized = f"{tag} {item}".upper()
    if "CDXC" in normalized or "DXC" in normalized or "DX COIL" in normalized:
        return "DX"
    if "HGRH" in normalized or "HGRC" in normalized or "REHEAT" in normalized:
        return "HGRC"
    if "CHW" in normalized or "CHILLED WATER" in normalized or "CW" in normalized:
        return "CHW"
    if "HOT WATER" in normalized or "HW" in normalized:
        return "HW"
    return "DX"


def _derive_coil_format(tag: str, item: str) -> str:
    tag_prefix = _normalize_tag(tag).split("-", 1)[0]
    if tag_prefix in _COIL_FORMAT_BY_PREFIX:
        return _COIL_FORMAT_BY_PREFIX[tag_prefix]
    normalized = f"{tag} {item}".upper()
    if "PRE HOT WATER" in normalized or "PREHEAT" in normalized or "PRE HEAT" in normalized:
        return "preheat_hot_water"
    if "HEATING HWC" in normalized or "HWC HEATING" in normalized:
        return "heating_hot_water"
    if "HOT WATER" in normalized or "HW" in normalized:
        return "heating_hot_water"
    if "CHILLED WATER" in normalized or "CHW" in normalized or "CCWC" in normalized:
        return "cooling_chilled_water"
    if "HGRH" in normalized or "HGRC" in normalized or "REHEAT" in normalized:
        return "condensing"
    return "dx"


def _derive_coil_type(tag: str, item: str) -> str:
    tag_prefix = _normalize_tag(tag).split("-", 1)[0]
    if tag_prefix in _COIL_TYPE_BY_PREFIX:
        return _COIL_TYPE_BY_PREFIX[tag_prefix]
    normalized_item = _normalize_header_token(item)
    if "chilledwater" in normalized_item or "ccwcoil" in normalized_item or "cwcoil" in normalized_item:
        return "Chilled Water Coil"
    if "hotwater" in normalized_item or "hhwcoil" in normalized_item or "hwcoil" in normalized_item:
        return "Hot Water Coil"
    if "hgrh" in normalized_item or "hgrc" in normalized_item or "reheat" in normalized_item:
        return "HGRH COIL"
    if "dxc" in normalized_item or "dxcoil" in normalized_item or "coolingcoil" in normalized_item:
        return "DX COIL"
    return _clean_value(item)


def _is_dx_cover_row(row: _CoverRow) -> bool:
    """True when a cover row is a DX coil -- the only category with an HGBP bucket.
    Reuses _derive_coil_type so "is DX" has one definition and inherits its tag-alias
    fixes."""
    return _derive_coil_type(row.tag, row.item) == "DX COIL"


def _match_field_value(line: str, field_pattern: _FieldPattern) -> str | None:
    for label in field_pattern.labels:
        label_pattern = re.escape(label).replace(r"\ ", r"\s+")
        pattern = re.compile(
            rf"(?<!\w){label_pattern}(?!\w)\s*(?:[:=]\s*)?{field_pattern.value_pattern}",
            re.IGNORECASE,
        )
        match = pattern.search(line)
        if match is None:
            continue
        value = _clean_value(match.group("value"))
        if value:
            if field_pattern.source_key in {"HANDING", "HAND", "COIL_HAND"}:
                return _normalize_handing(value)
            if field_pattern.source_key == "FIN_SURFACE":
                return _normalize_fin_surface(value)
            if field_pattern.source_key == "HEADER_WALL_SCHEDULE":
                # Recognized source -> "(L)"/"(K)"; unknown returns the raw value (kept
                # non-empty so the guard below doesn't drop it) and is blocked downstream
                # in extract._build_field_value.
                return _normalize_header_wall_schedule(value) or value
            return value
    return None


def _add_line(
    extracted: dict[str, SanitizedSubmittalLine],
    source_key: str,
    source_value: str,
    order: int,
    page: _TextPage,
    source_line_number: int,
    reason: str,
) -> int:
    normalized_key = normalize_source_key(source_key)
    if normalized_key in extracted:
        return order
    location = (
        f"pdf-page-{page.page_number}-line-{source_line_number}"
        if page.page_number > 0
        else "pdf-intake-default"
    )
    extracted[normalized_key] = SanitizedSubmittalLine(
        source_key=normalized_key,
        source_value=source_value,
        line_number=order,
        source_page=None if page.page_number <= 0 else page.page_number,
        source_section="pdf_text_intake",
        source_location=f"{location}; {reason}",
    )
    return order + 1


def _set_line(
    extracted: dict[str, SanitizedSubmittalLine],
    source_key: str,
    source_value: str,
    order: int,
    page: _TextPage,
    source_line_number: int,
    reason: str,
) -> int:
    """Like `_add_line`, but overwrites an existing key in place.

    Used when a higher-priority source (an actual coil component row) must replace a
    value captured earlier from a lower-priority source (a parent unit's Qty/Tag row).
    The line's position is preserved on overwrite so downstream ordering is stable; a
    genuinely new key advances ``order`` exactly as `_add_line` would.
    """
    normalized_key = normalize_source_key(source_key)
    existing = extracted.get(normalized_key)
    line_order = existing.line_number if existing is not None else order
    location = (
        f"pdf-page-{page.page_number}-line-{source_line_number}"
        if page.page_number > 0
        else "pdf-intake-default"
    )
    extracted[normalized_key] = SanitizedSubmittalLine(
        source_key=normalized_key,
        source_value=source_value,
        line_number=line_order,
        source_page=None if page.page_number <= 0 else page.page_number,
        source_section="pdf_text_intake",
        source_location=f"{location}; {reason}",
    )
    return order if existing is not None else order + 1


def _tag_prefix_is_coil(tag: str) -> bool:
    return _normalize_tag(tag).split("-", 1)[0] in _COIL_TAG_PREFIXES


def _normalize_tag(raw: str) -> str:
    tag = raw.upper().strip()
    tag = re.sub(r"[\s\-]+", "-", tag)
    return tag.strip("-")


def _normalize_tag_search_text(raw: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(raw or "").upper())


def _normalize_handing(value: str) -> str:
    normalized = value.strip().upper()
    if normalized in {"L", "LH", "LEFT HAND", "LEFT HANDING"}:
        return "Left"
    if normalized in {"R", "RH", "RIGHT HAND", "RIGHT HANDING"}:
        return "Right"
    return value.strip().title()


# Submittal fin-surface terms -> Direct Coil dropdown candidate. Case-insensitive
# keyword match so compound source values ("Sine Wave") resolve; unknown surfaces
# fail closed to a review flag rather than being guessed.
_FIN_SURFACE_KEYWORD_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("sine", "wavy", "wave", "sinusoidal", "corrugat"), "Corrugated"),
    (("lanced", "louver"), "Lanced"),
    (("flat", "plain"), "Flat"),
)


def _normalize_fin_surface(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return value
    for keywords, mapped in _FIN_SURFACE_KEYWORD_MAP:
        if any(keyword in normalized for keyword in keywords):
            return mapped
    return "Manual Review Required"


# Submittal header-wall-schedule terms -> Direct Coil dropdown candidate. Source rarely
# states this field, so the blank case (the dominant path) yields the company default "(L)".
# An unrecognized value returns None so the caller can block it rather than guess.
_HW_SCHEDULE_L_TERMS = frozenset({"l", "type l", "copper type l", "(l)"})
_HW_SCHEDULE_K_TERMS = frozenset({"k", "type k", "copper type k", "heavy wall", "(k)"})
_HW_SCHEDULE_DEFAULT = "(L)"


def _normalize_header_wall_schedule(value: str | None) -> str | None:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if not normalized:
        return _HW_SCHEDULE_DEFAULT
    if normalized in _HW_SCHEDULE_L_TERMS:
        return "(L)"
    if normalized in _HW_SCHEDULE_K_TERMS:
        return "(K)"
    return None  # unknown -> caller blocks


def header_wall_schedule_confidence(value: str | None) -> str:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if not normalized:
        return "inferred"
    if normalized in _HW_SCHEDULE_L_TERMS or normalized in _HW_SCHEDULE_K_TERMS:
        return "confirmed"
    return "ambiguous"


def _clean_line(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_cell(value: Any) -> str:
    return _clean_line(value)


def _clean_value(value: Any) -> str:
    return str(value or "").strip().strip(":=").strip()


def _field_value(group: dict[str, Any], key: str) -> Any:
    field_value = group.get(key)
    return None if field_value is None else field_value.value
