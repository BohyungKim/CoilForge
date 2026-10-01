"""Parse CCSI coil selection reports — the PDFs filed in each PO folder — into harvest-shaped records.

The source of truth for the coil-data cross-check (John 2026-09-30): a CCSI report is what CCSI
printed AFTER calculating, so it never carries the half-edited state a live form can show (the
live form read LDB 90/55 before Calculate; the report prints the real 70.88/50.75). One report
page = one coil; the text is "label line, value line" pairs laid out in two columns — the pair
itself never splits, only whole pairs interleave between the columns.

Pure: page texts in, records out (the caller reads the PDF). A record has the harvest shape
(``{tag, component_type, fields: {ccsi_id: {label, kind, value, raw}}}``) so
``ccsi.crosscheck.crosscheck_coil`` compares it unchanged. Four rules carry it:

* **Closed label vocabulary.** A known label takes the next line as its value unless that line
  is itself a label, a section header or ``Notes:`` (then it has none). An unknown line is
  reported in ``unknown_labels`` and parsing re-synchronises on the next known label.
* **Map-driven values.** Only ids present in that coil type's map are emitted. A select is
  resolved to the map's own option text through one comparison key applied to BOTH sides
  (the userscript's rule); no key match -> the raw text plus a flag, never the nearest option.
* **Model-number self-check.** ``3DX-04-21.0-13-32.0-8`` encodes rows / fin height / FPI /
  fin length; a coil whose parsed values disagree is flagged ``parse_inconsistent``.
* **Revision choice from content, not file names** (``pick_revisions``): the highest REV is the
  truth (the ordered state); a REV0 is kept as the auxiliary original selection.

Review aid only; nothing here reads or writes CCSI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from coilforge.ccsi.coil_data_map import load_coil_data_map

# Report page title -> coil-data map type / CCSI component type. HEAT PUMP has no map.
REPORT_TYPES: dict[str, str] = {"DX": "DX", "CONDENSER": "HGRH", "HOT WATER": "HWC", "CHILLED WATER": "CWC"}
COMPONENT_TYPES: dict[str, str] = {
    "DX": "DXCoil", "HGRH": "CondenserCoil", "HWC": "HotWaterCoil", "CWC": "ColdWaterCoil",
}
SECTION_HEADERS: frozenset[str] = frozenset(
    {"Physical Data", "Air Data", "Refrigerant Data", "Fluid Data", "Capacity"}
)
_TITLE_RE = re.compile(r"^([A-Z ]+) COIL REPORT$")

# (ccsi_id, how) — how: number | total (the bracketed all-coils figure) | select | refrigerant |
# header (Copper (L) -> material + wall) | connection (Sweat Copper -> type + material) | fouling.
_Spec = tuple[str, str]
_PHYSICAL_AND_AIR: dict[str, _Spec] = {
    "Number Of Coils": ("CoilQuantity", "number"),
    "Tube Diameter": ("TubeDiameter", "select"),
    "Fin Height (Per Coil)": ("FinnedHeight", "number"),
    "Fin Length (Per Coil)": ("FinnedLength", "number"),
    "Tube Material": ("TubeMaterial", "select"),
    "Fin Material": ("FinMaterial", "select"),
    "Number Of Rows Deep": ("RowsDeep", "select"),
    "Fin Style": ("FinSurface", "select"),
    "Fins Per Inch": ("FinsPerInch", "select"),
    "Casing Style": ("CasingStyle", "select"),
    "Casing Material": ("CasingMaterial", "select"),
    "Header Material": ("HeaderMaterial", "header"),
    "Total Air Flow (All Coils)": ("TotalAirFlow", "number"),
    "Air Flow (Per Coil)": ("AirFlowPerCoil", "number"),
    "Face Velocity": ("FaceVelocity", "number"),
    "Altitude": ("Altitude", "number"),
    "Entering Dry Bulb": ("EnteringDryBulb", "number"),
    "Leaving Dry Bulb": ("LeavingDryBulb", "number"),
}
_REFRIGERANT_COMMON: dict[str, _Spec] = {
    "System Type": ("RefrigerationSystemType", "select"),
    "Connection Type": ("RefrigerantConnectionType", "connection"),
    "Refrigerant": ("Refrigerant", "refrigerant"),
    "Fouling Factor": ("AirSideFoulingFactor", "number"),
}
_WATER_COMMON: dict[str, _Spec] = {
    "Tube Turbulators": ("TubeTurbulators", "select"),
    "Supply Connection Size": ("ConnectionSize", "select"),
    "Connection Type": ("ConnectionType", "connection"),
    "Fluid Type": ("FluidType", "select"),
    "Fluid Ratio": ("GlycolRatio", "number"),
    "Entering Fluid Temp": ("EnteringFluidTemp", "number"),
    "Leaving Fluid Temp": ("LeavingFluidTemp", "number"),
    # "6.83 GPM (6.83)" is per coil, then (all coils); the map's FluidFlowRate is All Coils.
    "Fluid Flow Rate Per Coil (Total)": ("FluidFlowRate", "total"),
    "Fouling Factor": ("AirSideFoulingFactor", "fouling"),
}
LABEL_TABLE: dict[str, dict[str, _Spec]] = {
    "DX": {
        **_PHYSICAL_AND_AIR, **_REFRIGERANT_COMMON,
        "Number Of Feeds": ("NumberOfFeeds", "number"),
        "Return Connection Size": ("DXReturnConnectionSize", "select"),
        # The report's saturated suction temperature is the form's evaporating temperature.
        "Suction Temperature": ("EvaporatingTemperature", "number"),
        "Liquid Temperature": ("LiquidTemperature", "number"),
        "Superheat": ("Superheat", "number"),
        "Entering Wet Bulb": ("EnteringWetBulb", "number"),
        "Total Capacity Per Coil (Total)": ("Capacity", "number"),
    },
    "HGRH": {
        **_PHYSICAL_AND_AIR, **_REFRIGERANT_COMMON,
        "Supply Connection Size": ("CondenserSupplyConnectionSize", "select"),
        "Return Connection Size": ("CondenserReturnConnectionSize", "select"),
        "Vapor Temperature": ("VaporTemperature", "number"),
        "Condensing Temperature": ("CondensingTemperature", "number"),
        "Subcooling": ("Subcooling", "number"),
        # Q1 ruled (John 2026-09-30): CCSI's Capacity is the TOTAL line, not the condenser line.
        "Total Capacity /Coil (Total)": ("Capacity", "number"),
    },
    "CWC": {
        **_PHYSICAL_AND_AIR, **_WATER_COMMON,
        "Entering Wet Bulb": ("EnteringWetBulb", "number"),
        "Total Capacity Per Coil (Total)": ("Capacity", "number"),
    },
    "HWC": {
        **_PHYSICAL_AND_AIR, **_WATER_COMMON,
        "Capacity Per Coil (Total)": ("Capacity", "number"),
    },
}
# Printed on reports but not a coil-data input the map compares (results, or no map entry).
# Known so the pair walk stays in sync; reported under ``unmapped_labels``.
KNOWN_UNMAPPED_LABELS: frozenset[str] = frozenset({
    "Coil Weight (Per Coil)[operating]", "Coil Internal Volume (Per Coil)", "Circuit Ratio",
    "Supply Connection Size", "Return Connection Size", "Refrigerant Pressure Drop",
    "Refrigerant Velocity", "Refrigerant Mass Flow (All Coils)", "Leaving Wet Bulb",
    "Refrigerant Charge (Per Coil)", "Refrigerant Charge (All Coils)", "Air Pressure Drop",
    "Condensate Rate (Per Coil)", "Sensible Capacity Per Coil (Total)",
    "Latent Capacity Per Coil (Total)", "Condenser Pressure Drop", "Subcooling Pressure Drop",
    "Total Pressure Drop", "Condenser Capacity /Coil (Total)", "Subcooling Capacity /Coil (Total)",
    "Tube Velocity",
    # A calculated result — deliberately NOT the form's MaxFluidPressureDrop input limit.
    "Fluid Pressure Drop",
})
VOCABULARY: frozenset[str] = frozenset(
    label for table in LABEL_TABLE.values() for label in table
) | KNOWN_UNMAPPED_LABELS

_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")
_BRACKET_RE = re.compile(r"\(\s*([-+]?\d[\d,]*\.?\d*)\s*\)")
_BASE_TAG_RE = re.compile(r"\b(CDXC|CCDX|RHHGRC|RHHGRH|HGRC|HGRH|HHWC|PHWC|CCWC)-(\d+)\b", re.I)
_MODEL_RE = re.compile(r"^\w+-(\d+)-(\d+(?:\.\d+)?)-(\d+)-(\d+(?:\.\d+)?)-\d+$")
_DATE_RES = (
    (re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4}, \d{1,2}:\d{2}:\d{2} [AP]M)\b"), "%m/%d/%Y, %I:%M:%S %p"),
    (re.compile(r"\b(\d{4}-\d{2}-\d{2}, \d{1,2}:\d{2}:\d{2} [ap]\.m\.)"), "%Y-%m-%d, %I:%M:%S %p"),
)


# ------------------------------------------------------------------ value normalisation
def option_key(text: Any, *, refrigerant: bool = False) -> str:
    """One comparison key for a report value AND a map option (``Copper - 0.016 Plain`` ==
    ``Copper 0.016 Plain``; ``2 x 7/8"`` == ``7/8"``; refrigerant ``R-410A`` == ``R410A``)."""
    key = " ".join(str(text).split()).casefold()
    key = re.sub(r"\s-\s", " ", key)
    key = re.sub(r"^\d+\s*x\s*", "", key)
    if refrigerant:
        key = key.replace("-", "").replace(" ", "")
    return key


def match_option(text: Any, options: list[str], *, refrigerant: bool = False) -> str | None:
    """The single map option whose key equals the value's key; None when zero or ambiguous."""
    want = option_key(text, refrigerant=refrigerant)
    hits = [o for o in options if option_key(o, refrigerant=refrigerant) == want]
    return hits[0] if len(hits) == 1 else None


def first_number(text: Any) -> float | None:
    m = _NUMBER_RE.search(str(text))
    return float(m.group().replace(",", "")) if m else None


def bracket_number(text: Any) -> float | None:
    m = _BRACKET_RE.search(str(text))
    return float(m.group(1).replace(",", "")) if m else None


def number_text(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def base_tag(raw: str | None) -> tuple[str | None, bool]:
    """(the coil tag inside a CCSI tag, is-multi-tag). ``CDXC-1 (107A)`` -> CDXC-1;
    ``CDXC-1, CDXC-2`` / ``HGRH-1,2 (qty2)`` are selections covering several coils."""
    text = raw or ""
    found = {f"{m.group(1).upper()}-{int(m.group(2))}" for m in _BASE_TAG_RE.finditer(text)}
    multi = "," in text or bool(re.search(r"qty\s*\d", text, re.I)) or len(found) > 1
    return (next(iter(found)) if len(found) == 1 else None), multi


def report_date(text: str) -> datetime | None:
    for pattern, fmt in _DATE_RES:
        m = pattern.search(text)
        if m:
            value = m.group(1).replace("a.m.", "AM").replace("p.m.", "PM")
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                return None
    return None


# ------------------------------------------------------------------ page parsing
def _pairs(body: list[str]) -> list[tuple[str, str | None]]:
    """Walk label/value pairs; a wrapped ``Dist-1/…/Dist-4`` + ``(feeds)`` label is one label."""
    def is_label(line: str) -> bool:
        return line in VOCABULARY or line.startswith("Dist-")

    out: list[tuple[str, str | None]] = []
    i = 0
    while i < len(body):
        line = body[i]
        if line in SECTION_HEADERS:
            i += 1
            continue
        label = line
        if line.startswith("Dist-") and i + 1 < len(body) and body[i + 1] == "(feeds)":
            label, i = f"{line} (feeds)", i + 1
        nxt = body[i + 1] if i + 1 < len(body) else None
        if nxt is None or nxt in SECTION_HEADERS or is_label(nxt):
            out.append((label, None))
            i += 1
        else:
            out.append((label, nxt))
            i += 2
    return out


def _emit_select(fields: dict, flags: list, label: str, ccsi_id: str, raw: str, options: list[str], *,
                 refrigerant: bool = False) -> None:
    picked = match_option(raw, options, refrigerant=refrigerant)
    if picked is None:
        flags.append(f"unmatched_option:{ccsi_id}")
    fields[ccsi_id] = {"label": label, "kind": "select", "value": picked if picked is not None else raw, "raw": raw}


def parse_report_page(text: str) -> dict[str, Any] | None:
    """One report page -> one coil record; None for a page that is not a coil report."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    title = _TITLE_RE.match(lines[0])
    if not title:
        return None
    report_type = title.group(1)
    coil_type = REPORT_TYPES.get(report_type)
    record: dict[str, Any] = {
        "schema": "coilforge.ccsi.report/1", "report_type": report_type, "coil_type": coil_type,
        "component_type": COMPONENT_TYPES.get(coil_type or ""), "tag": None, "base_tag": None,
        "multi_tag": False, "model_number": None, "date": None, "fields": {}, "unmapped_labels": {},
        "unknown_labels": {}, "flags": [], "notes": None,
    }
    if coil_type is None:
        record["flags"].append(f"unsupported_type:{report_type}")
        return record
    date = report_date(text)
    record["date"] = date.isoformat() if date else None
    for line in lines:
        if line.startswith("Coil Tag:"):
            record["tag"] = line.split(":", 1)[1].strip()
        elif line.startswith("Coil Model Number:"):
            record["model_number"] = line.split(":", 1)[1].strip()
    record["base_tag"], record["multi_tag"] = base_tag(record["tag"])
    try:
        start = lines.index("Physical Data") + 1
    except ValueError:
        record["flags"].append("no_physical_data")
        return record
    end = next((i for i, line in enumerate(lines) if line.startswith("Notes:")), len(lines))
    record["notes"] = " ".join(lines[end:])[:500] if end < len(lines) else None

    cmap = load_coil_data_map(coil_type)
    table = LABEL_TABLE[coil_type]
    fields: dict[str, Any] = record["fields"]
    flags: list[str] = record["flags"]
    fouling: list[str] = []
    for label, raw in _pairs(lines[start:end]):
        spec = table.get(label)
        if spec is None:
            bucket = "unmapped_labels" if (label in VOCABULARY or label.startswith("Dist-")) else "unknown_labels"
            record[bucket][label] = raw
            continue
        ccsi_id, how = spec
        entry = cmap.fields.get(ccsi_id)
        if entry is None or raw is None:
            record["unmapped_labels"][label] = raw
            continue
        if how == "fouling":
            fouling.append(raw)
        elif how in ("number", "total"):
            x = bracket_number(raw) if how == "total" else first_number(raw)
            if x is None:
                flags.append(f"unparsed_number:{ccsi_id}")
            fields[ccsi_id] = {"label": label, "kind": "number",
                               "value": number_text(x) if x is not None else None, "raw": raw}
        elif how == "header":
            m = re.match(r"^(.*?)\s*(\([A-Z]\))$", raw)
            material, wall = (m.group(1), m.group(2)) if m else (raw, None)
            _emit_select(fields, flags, label, "HeaderMaterial", material, entry.options or [])
            wall_entry = cmap.fields.get("HeaderWallSchedule")
            if wall is not None and wall_entry is not None:
                _emit_select(fields, flags, label, "HeaderWallSchedule", wall, wall_entry.options or [])
        elif how == "connection":
            material_entry = cmap.fields.get("ConnectionMaterial")
            types = sorted(entry.options or [], key=len, reverse=True)
            kind = next((t for t in types if option_key(raw).startswith(option_key(t))), None)
            rest = raw[len(kind):].strip() if kind else ""
            material = match_option(rest, material_entry.options or []) if (kind and material_entry) else None
            if kind is None or material is None:
                flags.append(f"unparsed_composite:{label}")
                fields[ccsi_id] = {"label": label, "kind": "select", "value": raw, "raw": raw}
            else:
                fields[ccsi_id] = {"label": label, "kind": "select", "value": kind, "raw": raw}
                fields["ConnectionMaterial"] = {"label": label, "kind": "select", "value": material, "raw": raw}
        else:  # select / refrigerant
            _emit_select(fields, flags, label, ccsi_id, raw, entry.options or [], refrigerant=how == "refrigerant")
    if fouling:
        # Water reports print air-side then tube-side under the same label; order is not
        # evidence of which is which, so both ids are filled only when the values agree.
        values = {first_number(v) for v in fouling}
        if len(values) == 1 and None not in values:
            x = number_text(next(iter(values)))  # type: ignore[arg-type]
            for ccsi_id in ("AirSideFoulingFactor", "TubeSideFoulingFactor"):
                if ccsi_id in cmap.fields:
                    fields[ccsi_id] = {"label": "Fouling Factor", "kind": "number", "value": x, "raw": fouling[0]}
        else:
            flags.append("ambiguous_duplicate:Fouling Factor")
    hand = next((line.split(":", 1)[1].strip() for line in lines if line.startswith("Hand:")), None)
    if hand and "CoilHand" in cmap.fields:
        _emit_select(fields, flags, "Hand", "CoilHand", hand, cmap.fields["CoilHand"].options or [])
    if record["base_tag"]:
        fields["Tag"] = {"label": "Coil Tag", "kind": "text", "value": record["base_tag"], "raw": record["tag"]}
    if _model_disagrees(record["model_number"], fields):
        flags.append("parse_inconsistent")
    return record


def _model_disagrees(model: str | None, fields: Mapping[str, Any]) -> bool:
    """True when the model number's rows / FH / FPI / FL contradict the parsed values."""
    m = _MODEL_RE.match(model or "")
    if not m:
        return False
    expected = {"RowsDeep": float(m.group(1)), "FinnedHeight": float(m.group(2)),
                "FinsPerInch": float(m.group(3)), "FinnedLength": float(m.group(4))}
    for ccsi_id, want in expected.items():
        got = first_number((fields.get(ccsi_id) or {}).get("value"))
        # FH/FL print with one decimal in the model (14.25 -> 14.3).
        if got is not None and abs(got - want) > 0.051:
            return True
    return False


def parse_report_pages(pages: list[str]) -> list[dict[str, Any]]:
    """Every coil report page of one PDF, in page order (page number kept on each record)."""
    out = []
    for number, text in enumerate(pages, start=1):
        record = parse_report_page(text)
        if record is not None:
            record["page"] = number
            out.append(record)
    # Fields the report page never prints but the same PDF's quote / drawing / notes do
    # (John 2026-09-30: capture them). Never overwrites what the report page printed.
    from coilforge.ccsi.report_extras import merge_extras

    return merge_extras(out, pages)


# ------------------------------------------------------------------ revision choice
_REV_NAME_RE = re.compile(r"^(?P<stem>.+?)_REV(?P<rev>\d+)(?=[_.\s])", re.I)
_EXCLUDED_NAME_RE = re.compile(r"revised|revi\b|copy", re.I)
_ALLOWED_DIRS = ("accessory order forms", "accessory order forms/directcoil", "accessory order forms/direct coil")


@dataclass(frozen=True)
class ReportFile:
    """One CCSI report PDF as seen by ``pick_revisions`` (paths relative to the project folder)."""

    rel_path: str
    rev: int
    stem: str
    sha256: str
    date: datetime | None
    coil_pages: int


def classify_report_path(rel_path: str) -> tuple[int, str] | str:
    """``(rev, stem)`` for a usable report file name, else the skip reason."""
    parts = rel_path.replace("\\", "/").split("/")
    folder, name = "/".join(parts[:-1]).casefold(), parts[-1]
    if folder not in _ALLOWED_DIRS:
        return "archived_subfolder"
    if _EXCLUDED_NAME_RE.search(name):
        return "coilforge_output_or_copy"
    m = _REV_NAME_RE.match(name)
    if not m:
        return "not_a_rev_report"
    stem = re.sub(r"\s*\(\d+\)$", "", m.group("stem")).casefold()
    return int(m.group("rev")), stem


def pick_revisions(files: list[ReportFile]) -> dict[str, Any]:
    """Truth = highest REV (latest in-PDF date among its exports); REV0 kept as the auxiliary
    original selection. Byte-identical exports collapse; a same-time different-content pair,
    or more than one CCSI project stem, is ambiguous and skipped rather than guessed."""
    usable = [f for f in files if f.coil_pages > 0]
    if not usable:
        return {"truth": None, "rev0": None, "kind": None, "skip": "no_text_layer"}
    if len({f.stem for f in usable}) > 1:
        return {"truth": None, "rev0": None, "kind": None, "skip": "multiple_ccsi_projects"}
    unique = {f.sha256: f for f in sorted(usable, key=lambda f: f.rel_path)}.values()

    def latest(rev: int) -> ReportFile | str | None:
        group = [f for f in unique if f.rev == rev]
        if not group:
            return None
        group.sort(key=lambda f: f.date or datetime.min)
        if len(group) > 1 and group[-1].date == group[-2].date:
            return "ambiguous_export"
        return group[-1]

    top = max(f.rev for f in unique)
    truth = latest(top)
    if isinstance(truth, str):
        return {"truth": None, "rev0": None, "kind": None, "skip": truth}
    rev0 = latest(0) if top > 0 else None
    return {"truth": truth, "rev0": rev0 if isinstance(rev0, ReportFile) else None,
            "kind": "order" if top >= 1 else "quote_only", "skip": None}
