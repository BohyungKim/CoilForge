"""Parse an Ambient Dynamics "Coils Performance & Drawings" PDF into candidates.

Ambient's returned PDF format DIFFERS from Coilmaster/Oxygen8 submittals: each coil
gets a "DX Coil Report" / "Condensing Coil Report" page with clean ``Label  Value``
lines grouped into *Coil Data / Air Data / Refrigerant Data* sections, plus a
Coilmaster-branded drawing page ("LAYOUT TO MATCH BY AMBIENT DYNAMICS"). Capacity is
stated in **Btu/hr** (vs the baseline's MBH).

This module reuses ``submittal.pdf_intake``'s supplier-agnostic text extraction (and
its degraded-font auto-OCR defense), then maps the Ambient labels into the SAME
``SubmittalCoilCandidate`` group/key shape the baseline uses, so the Phase-4
comparison can pair fields directly. Every value is a **vendor claim**: wrapped in a
``FieldValue`` with real ``SourceEvidence``, ``confidence="inferred"``,
``status="review_required"``. Unparseable fields are omitted, never invented.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from coilforge.ambient.units import btuh_to_mbh
from coilforge.contracts import FieldValue, SourceEvidence
from coilforge.submittal.candidate import SubmittalCoilCandidate
from coilforge.submittal.pdf_intake import (
    _auto_ocr_degraded_pages,
    _degraded_page_numbers,
    _pages_with_replaced_text,
    coil_category_of_tag,
    extract_text_pages_from_pdf_bytes,
)

# A performance page announces itself with one of these headers.
_REPORT_HEADER_RE = re.compile(r"^(DX|Condensing|Chilled Water|Hot Water) Coil Report", re.M)
# "Model Number: <model> Tag: <coil_id> / <coil_tag>"
_TAG_RE = re.compile(r"Tag:\s*\S+\s*/\s*([A-Za-z0-9\-]+)")


@dataclass(frozen=True)
class AmbientIntakeResult:
    """Ambient PDF parse outcome: the per-coil candidates + loud doc-level warnings."""

    coils: list[SubmittalCoilCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    engine: str = ""


# ---------------------------------------------------------------------------
# Field pattern table — one entry per single-value label. Order matters only for
# the special-cased lines handled separately below (capacity, tube/fin material).
# Each line yields at most ONE field (first matching pattern wins), so prefix
# collisions (e.g. "Coil Weight" vs "Coil Weight (Wet)") are avoided by anchoring.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _NumField:
    pattern: re.Pattern[str]
    group: str
    key: str
    unit: str | None


_NUM_FIELDS: tuple[_NumField, ...] = (
    _NumField(re.compile(r"^Finned Height\s+([\d.]+)"), "geometry", "finned_height_in", "in"),
    _NumField(re.compile(r"^Finned Length\s+([\d.]+)"), "geometry", "finned_length_in", "in"),
    _NumField(re.compile(r"^Rows Deep\s+(\d+)"), "geometry", "rows_deep", None),
    _NumField(re.compile(r"^Number Of Feeds\s+(\d+)"), "geometry", "number_of_feeds", "feeds"),
    _NumField(re.compile(r"^Fins Per Inch\s+(\d+)"), "geometry", "fins_per_inch", "fpi"),
    _NumField(re.compile(r"^Face Area\s+([\d.]+)"), "geometry", "face_area_sqft", "sqft"),
    _NumField(re.compile(r"^Coil Weight \(Wet\)\s+([\d.]+)"), "performance", "coil_weight_wet_lbs", "lbs"),
    _NumField(re.compile(r"^Coil Weight\s+([\d.]+)"), "performance", "coil_weight_lbs", "lbs"),
    _NumField(re.compile(r"^Total Air Flow\s+([\d.]+)"), "airside_conditions", "total_air_flow_cfm", "cfm"),
    _NumField(re.compile(r"^Standard Face Velocity\s+([\d.]+)"), "airside_conditions", "face_velocity_fpm", "fpm"),
    _NumField(re.compile(r"^Altitude\s+([\d.]+)"), "airside_conditions", "altitude_ft", "ft"),
    _NumField(re.compile(r"^Entering Dry Bulb\s+([\d.]+)"), "airside_conditions", "entering_dry_bulb_f", "degF"),
    _NumField(re.compile(r"^Entering Wet Bulb\s+([\d.]+)"), "airside_conditions", "entering_wet_bulb_f", "degF"),
    _NumField(re.compile(r"^Leaving Dry Bulb\s+([\d.]+)"), "airside_conditions", "leaving_dry_bulb_f", "degF"),
    _NumField(re.compile(r"^Leaving Wet Bulb\s+([\d.]+)"), "airside_conditions", "leaving_wet_bulb_f", "degF"),
    _NumField(re.compile(r"^Air Pressure Drop\s+([\d.]+)"), "performance", "air_pressure_drop_iwg", "iwg"),
    _NumField(re.compile(r"^Evaporating Temperature\s+([\d.]+)"), "refrigerant_conditions", "evaporating_temp_f", "degF"),
    _NumField(re.compile(r"^Liquid Temperature\s+([\d.]+)"), "refrigerant_conditions", "liquid_temp_f", "degF"),
    _NumField(re.compile(r"^Superheat\s+([\d.]+)"), "refrigerant_conditions", "superheat_f", "degF"),
    _NumField(re.compile(r"^Vapor Temperature\s+([\d.]+)"), "refrigerant_conditions", "vapor_temp_f", "degF"),
    _NumField(re.compile(r"^Condensing Temperature\s+([\d.]+)"), "refrigerant_conditions", "condensing_temp_f", "degF"),
    _NumField(re.compile(r"^Subcooling\s+([\d.]+)"), "refrigerant_conditions", "subcooling_f", "degF"),
    _NumField(re.compile(r"^Refrigerant Pressure Drop\s+([\d.]+)"), "performance", "refrigerant_pressure_drop_psi", "psi"),
)


@dataclass(frozen=True)
class _StrField:
    pattern: re.Pattern[str]
    group: str
    key: str


_STR_FIELDS: tuple[_StrField, ...] = (
    _StrField(re.compile(r"^Fin Surface\s+(.+)$"), "materials_construction", "fin_surface"),
    _StrField(re.compile(r"^Coil Coating\s+(.+)$"), "manufacturing_options", "coil_coating"),
    _StrField(re.compile(r"^Connection Type\s+(.+)$"), "connections", "connection_type"),
    _StrField(re.compile(r"^System Type\s+(.+)$"), "manufacturing_options", "system_type"),
    _StrField(re.compile(r"^Supply Connection Size\s+(.+)$"), "connections", "supply_connection_size"),
    _StrField(re.compile(r"^Return Connection Size\s+(.+)$"), "connections", "return_connection_size"),
    # Refrigerant TYPE only (anchored to R+digit so it never eats "Refrigerant
    # Pressure Drop" / "Refrigerant Mass Flow").
    _StrField(re.compile(r"^Refrigerant\s+(R\d\w*)\s*$"), "refrigerant_conditions", "refrigerant"),
)

# "Tube Material Copper 0.016" / "Fin Material Aluminum 0.0075" -> material + thickness.
_TUBE_MAT_RE = re.compile(r"^Tube Material\s+(\S+)\s+([\d.]+)")
_FIN_MAT_RE = re.compile(r"^Fin Material\s+(\S+)\s+([\d.]+)")
# "Tube Diameter 3/8 (1 x 0.866)" -> OD as a float (3/8 -> 0.375).
_TUBE_DIA_RE = re.compile(r"^Tube Diameter\s+(\d+)\s*/\s*(\d+)")
# "Capacity(All Coils) 171514 Btu/hr" / "Sensible Capacity(All Coils) 86625 Btu/hr"
_SENS_CAP_RE = re.compile(r"^Sensible Capacity\(All Coils\)\s+([\d.]+)\s*(\S+)?")
_CAP_RE = re.compile(r"^Capacity\(All Coils\)\s+([\d.]+)\s*(\S+)?")


def _slug(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-").lower()


def _evidence(
    *, page: int, label: str, raw: object, normalized: object, unit: str | None, source_id: str
) -> SourceEvidence:
    return SourceEvidence(
        evidence_id=f"AMBIENT-{source_id}-p{page}-{_slug(label)}",
        source_type="ambient_pdf",
        source_id=source_id,
        source_location=f"page {page}: {label}",
        source_page=page,
        source_key=label,
        source_value=raw,
        normalized_value=normalized,
        unit=unit,
        confidence="inferred",
    )


def _fv(
    *, page: int, label: str, raw: object, value: object, unit: str | None, source_id: str, notes: list[str] | None = None
) -> FieldValue:
    return FieldValue(
        value=value,
        unit=unit,
        source_evidence=[_evidence(page=page, label=label, raw=raw, normalized=value, unit=unit, source_id=source_id)],
        confidence="inferred",
        status="review_required",
        review_required=True,
        notes=notes or [],
    )


def _num(raw: str) -> float:
    return float(raw)


def _parse_report_page(
    text: str, *, page_number: int, source_id: str
) -> SubmittalCoilCandidate | None:
    """Parse ONE Ambient report page's text into a candidate, or None if not a report."""
    if not text or not _REPORT_HEADER_RE.search(text):
        return None

    tag_match = _TAG_RE.search(text)
    tag_value = tag_match.group(1) if tag_match else None
    category = coil_category_of_tag(tag_value) if tag_value else None

    groups: dict[str, dict[str, FieldValue]] = {
        "geometry": {},
        "airside_conditions": {},
        "refrigerant_conditions": {},
        "materials_construction": {},
        "connections": {},
        "manufacturing_options": {},
        "performance": {},
    }

    def put(group: str, key: str, fv: FieldValue) -> None:
        groups[group][key] = fv

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # --- special-cased lines first (multi-field / unit-bearing) ---
        m = _TUBE_MAT_RE.match(line)
        if m:
            put("materials_construction", "tube_material", _fv(page=page_number, label="Tube Material", raw=m.group(1), value=m.group(1), unit=None, source_id=source_id))
            put("geometry", "tube_thickness_in", _fv(page=page_number, label="Tube Thickness", raw=m.group(2), value=_num(m.group(2)), unit="in", source_id=source_id))
            continue
        m = _FIN_MAT_RE.match(line)
        if m:
            put("materials_construction", "fin_material", _fv(page=page_number, label="Fin Material", raw=m.group(1), value=m.group(1), unit=None, source_id=source_id))
            put("geometry", "fin_thickness_in", _fv(page=page_number, label="Fin Thickness", raw=m.group(2), value=_num(m.group(2)), unit="in", source_id=source_id))
            continue
        m = _TUBE_DIA_RE.match(line)
        if m:
            od = float(m.group(1)) / float(m.group(2))
            put("geometry", "tube_od_in", _fv(page=page_number, label="Tube Diameter", raw=line, value=od, unit="in", source_id=source_id))
            continue
        m = _SENS_CAP_RE.match(line)
        if m:
            put("performance", "sensible_capacity_mbh", _capacity_fv(m, page_number, "Sensible Capacity", source_id))
            continue
        m = _CAP_RE.match(line)
        if m:
            put("performance", "nominal_cooling_capacity_mbh", _capacity_fv(m, page_number, "Capacity", source_id))
            continue

        # --- generic numeric fields ---
        matched = False
        for f in _NUM_FIELDS:
            m = f.pattern.match(line)
            if m:
                put(f.group, f.key, _fv(page=page_number, label=f.key, raw=m.group(1), value=_num(m.group(1)), unit=f.unit, source_id=source_id))
                matched = True
                break
        if matched:
            continue

        # --- generic string fields ---
        for f in _STR_FIELDS:
            m = f.pattern.match(line)
            if m:
                put(f.group, f.key, _fv(page=page_number, label=f.key, raw=m.group(1).strip(), value=m.group(1).strip(), unit=None, source_id=source_id))
                break

    parsed_count = sum(len(g) for g in groups.values())

    tag_fv = None
    if tag_value:
        tag_fv = _fv(page=page_number, label="Tag", raw=tag_value, value=tag_value, unit=None, source_id=source_id)
    coil_type_fv = None
    if category:
        coil_type_fv = _fv(page=page_number, label="Category", raw=category, value=category, unit=None, source_id=source_id)

    notes: list[str] = []
    if parsed_count == 0:
        # Non-empty report page yielded zero fields -> degraded/unsupported. Surface
        # loudly; NEVER return a silent empty candidate.
        notes.append(
            "ambient_ocr_blocked: report page parsed 0 performance fields "
            "(possible degraded font or unsupported Ambient format)"
        )

    candidate = SubmittalCoilCandidate(
        candidate_id=f"AMBIENT-{tag_value or 'UNKNOWN'}-p{page_number}",
        tag=tag_fv,
        coil_type=coil_type_fv,
        geometry=groups["geometry"],
        airside_conditions=groups["airside_conditions"],
        refrigerant_conditions=groups["refrigerant_conditions"],
        materials_construction=groups["materials_construction"],
        connections=groups["connections"],
        manufacturing_options=groups["manufacturing_options"],
        performance=groups["performance"],
        notes=notes,
        review_status="review_required",
    )
    return candidate


def _capacity_fv(m: re.Match[str], page: int, label: str, source_id: str) -> FieldValue:
    """Build a capacity FieldValue, normalizing Btu/hr -> MBH (conditional on the unit)."""
    raw_val = m.group(1)
    unit_raw = (m.group(2) or "").strip()
    val = float(raw_val)
    low = unit_raw.lower()
    if "btu" in low:  # Ambient's native unit -> normalize to MBH
        return _fv(page=page, label=label, raw=f"{raw_val} {unit_raw}", value=btuh_to_mbh(val), unit="MBH", source_id=source_id, notes=[f"converted from {raw_val} Btu/hr"])
    if "mbh" in low:  # already MBH -> do NOT divide
        return _fv(page=page, label=label, raw=f"{raw_val} {unit_raw}", value=val, unit="MBH", source_id=source_id)
    # Unknown/absent unit -> keep raw magnitude, flag the ambiguity, do not guess.
    return _fv(page=page, label=label, raw=f"{raw_val} {unit_raw}".strip(), value=val, unit=unit_raw or None, source_id=source_id, notes=["capacity unit not recognized — value NOT converted"])


def parse_ambient_pdf(
    pdf_bytes: bytes, *, source_id: str = "AMBIENT-INTAKE-001", source_filename: str | None = None
) -> AmbientIntakeResult:
    """Full Ambient PDF -> candidates + warnings (reuses baseline text extraction + OCR)."""
    pages, engine = extract_text_pages_from_pdf_bytes(pdf_bytes)

    # Degraded-font defense: OCR degraded pages before pattern-matching (graceful
    # no-op when OPENAI_API_KEY is absent — the OCR helper returns empty text).
    warnings: list[str] = []
    degraded = _degraded_page_numbers(pages)
    if degraded:
        replacements, _results = _auto_ocr_degraded_pages(pdf_bytes, degraded_pages=degraded)
        pages = _pages_with_replaced_text(pages, replacements)
        still_degraded = [p for p in degraded if p not in replacements]
        if still_degraded:
            warnings.append(
                f"ambient_ocr_blocked: pages {still_degraded} had degraded text that could "
                "not be OCR-recovered (set OPENAI_API_KEY or provide a clean PDF)"
            )

    coils: list[SubmittalCoilCandidate] = []
    for page in pages:
        candidate = _parse_report_page(page.text or "", page_number=page.page_number, source_id=source_id)
        if candidate is not None:
            coils.append(candidate)
            warnings.extend(n for n in candidate.notes if n.startswith("ambient_ocr_blocked"))

    if not coils:
        warnings.append(
            "ambient_no_report_pages: no 'DX/Condensing Coil Report' page found — "
            "not an Ambient Dynamics performance PDF, or fully degraded"
        )

    return AmbientIntakeResult(coils=coils, warnings=warnings, engine=engine)


def extract_ambient_coils_from_pdf_bytes(
    pdf_bytes: bytes, *, source_id: str = "AMBIENT-INTAKE-001", source_filename: str | None = None
) -> list[SubmittalCoilCandidate]:
    """Ambient PDF -> per-coil candidates (the list-only convenience wrapper)."""
    return parse_ambient_pdf(pdf_bytes, source_id=source_id, source_filename=source_filename).coils
