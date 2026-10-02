"""Coil-data fields a CCSI report PDF states OUTSIDE its coil report pages.

The coil report page never prints coating, the distributor capillary, the water vent / drain size
or an HGRH coil's circuit count — but the same PDF's quote and drawing pages do (survey of 187 local
report PDFs, 2026-09-30). John asked (2026-09-30) that these be captured so the order cross-check
can test the mappings that feed them. (The report's "OPPOSITE END COIL REQUIRED" note was first
read as Connection Ends; calibration against the live forms disproved it — see below.)

* **Positive evidence only.** A field is emitted where the PDF states it. Absence is never read as
  the CCSI default: no Coating line does not prove Plain.
* **Map options, one key.** A value resolves to the map's own option text through
  ``selection_report.match_option``; no unique option -> the raw text plus
  ``unmatched_option:<id>`` (the cross-check's coverage flag), never the nearest option.
* **Circuits from the model number, corroborated.** The model number's last group is the feed
  count (``3DX-04-21.0-13-32.0-8`` -> 8; 6/6 coils checked against the drawing, 2026-09-30). The
  drawing's detail block ends ``rows, tubes high, circuits`` right before ``DIRECT COIL``; when it
  names this coil and its rows agree, its circuits must equal the model's, else
  ``extras_inconsistent:NumberOfFeeds`` and nothing is emitted.

Pure: page texts in, per-tag fields out. ``merge_extras`` adds them to ``parse_report_pages``
records without overwriting anything the report page itself printed.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from coilforge.ccsi.coil_data_map import load_coil_data_map

_TAG_LINE_RE = re.compile(r"^(CDXC|CCDX|RHHGRC|RHHGRH|HGRC|HGRH|HHWC|PHWC|CCWC)-(\d+)$", re.I)
_ITEM_RE = re.compile(r"^\d+\.$")
# "QTY 2 x 1620-4-1/4-J1/9-5/8 (18" LEADS)" / "1622-6-1/4-J1/9-5/8 (16" LEADS)": body-circuits-tube OD.
_DISTRIBUTOR_RE = re.compile(r"\b\d{4}-\d+-(\d+/\d+)-")
_VENT_DRAIN_RE = re.compile(r"([\d/]+)\"\s*FPT\s*VENT\s*\+\s*([\d/]+)\"\s*FPT\s*DRAIN", re.I)
_CIRCUITS_RE = re.compile(r"^\((\d+(?:\+\d+)*)INT\)$|^(\d+)$")
# rows-FH-FPI-FL-feeds, the same shape selection_report's model self-check reads.
_MODEL_FEEDS_RE = re.compile(r"^\w+-(\d+)-\d+(?:\.\d+)?-\d+-\d+(?:\.\d+)?-(\d+)$")


def _tag(line: str) -> str | None:
    m = _TAG_LINE_RE.match(line.strip())
    return f"{m.group(1).upper()}-{int(m.group(2))}" if m else None


def _field(label: str, value: str, raw: str, source: str) -> dict[str, Any]:
    return {"label": label, "kind": "select", "value": value, "raw": raw, "source": source}


def _number(text: str) -> float | None:
    try:
        return float(str(text).replace('"', "").strip())
    except ValueError:
        return None


def _circuits(token: str) -> int | None:
    m = _CIRCUITS_RE.match(token.strip())
    if not m:
        return None
    return sum(int(x) for x in m.group(1).split("+")) if m.group(1) else int(m.group(2))


def extract_extras(pages: list[str]) -> dict[str, dict[str, dict[str, Any]]]:
    """``{base tag: {ccsi_id: raw field}}`` from quote / drawing pages and report notes.

    Values here are raw PDF text; ``merge_extras`` resolves them to map options per coil type.
    Internal ``_rows`` / ``_fh`` keys carry the drawing's own rows and FH for the circuits check.
    """
    out: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for number, text in enumerate(pages, start=1):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            continue
        where = f"page {number}"
        if lines[0].endswith("COIL REPORT"):
            # The report's "OPPOSITE END COIL REQUIRED" note is NOT the form's Connection Ends: the
            # same four coils (2954 CCWC-1, 3183 RHHGRC-1, 3154 HHWC-1/2) carry that note while
            # their live forms read "Same End Only" — the calibration caught it (2026-09-30). The
            # note stays unmapped until John says which field, if any, it reflects.
            continue
        elif lines[0].startswith("COIL QUOTE"):
            tag, block = None, []
            for line in lines + ["1."]:  # sentinel closes the last item
                if _ITEM_RE.match(line) or line.startswith("Total Cost"):
                    if tag and "Coating:" in block:
                        i = block.index("Coating:")
                        if i + 1 < len(block):
                            out[tag]["CoilCoating"] = _field("Coating", block[i + 1], block[i + 1], f"{where} quote")
                    tag, block = None, []
                    continue
                if block and block[-1] == "Tagged:":
                    tag = _tag(line)
                block.append(line)
        else:
            tags = {t for t in (_tag(l) for l in lines) if t}
            if len(tags) != 1:
                continue  # a drawing that names no coil, or several, is never attributed
            tag = tags.pop()
            joined = " ".join(lines)
            m = _DISTRIBUTOR_RE.search(joined)
            if m:
                out[tag]["DXDistCapillarySize"] = _field("Distributor", m.group(1), m.group(0).rstrip("-"),
                                                         f"{where} drawing")
            m = _VENT_DRAIN_RE.search(joined)
            if m:
                out[tag]["DrainAndVent"] = _field("Vent + Drain", f'{m.group(1)}"' if m.group(1) == m.group(2) else
                                                  m.group(0), m.group(0), f"{where} drawing")
            end = next((i for i, l in enumerate(lines) if l.startswith("DIRECT COIL")), None)
            if end is not None and end >= 3:
                circuits = _circuits(lines[end - 1])
                if circuits is not None:
                    out[tag]["_drawing_circuits"] = {"value": str(circuits), "raw": lines[end - 1],
                                                     "rows": lines[end - 3], "source": f"{where} drawing"}
    return dict(out)


_AIRFLOW_UNIT_RE = re.compile(r"\b(ACFM|SCFM)\b")


def _airflow_basis(fields: dict[str, Any]) -> tuple[str, str] | None:
    """(CCSI Air flow basis, raw) from the unit the report prints on its airflow ("2,000 ACFM").

    The submittal always states SCFM, yet ordered selections often ran Actual (harvest 7 of 12),
    so the basis is a choice made in CCSI — readable only here (John 2026-09-30, decision A).
    """
    for ccsi_id in ("TotalAirFlow", "AirFlowPerCoil"):
        raw = str((fields.get(ccsi_id) or {}).get("raw") or "")
        m = _AIRFLOW_UNIT_RE.search(raw)
        if m:
            return ("Actual" if m.group(1) == "ACFM" else "Standard"), raw
    return None


def _model_feeds(model: str | None) -> str | None:
    """The feed count a CCSI model number ends with (``3DC-01-21.0-11-32.0-2`` -> ``2``)."""
    m = _MODEL_FEEDS_RE.match(model or "")
    return str(int(m.group(2))) if m else None


def _feeds(record: dict[str, Any], drawing: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
    """(NumberOfFeeds field, flag). The model number states it; the drawing only corroborates."""
    model = record.get("model_number")
    feeds = _model_feeds(model)
    rows = (record["fields"].get("RowsDeep") or {}).get("value")
    if feeds is None:
        return None, None
    if drawing is not None and _number(drawing["rows"]) == _number(rows or "") and drawing["value"] != feeds:
        return None, "extras_inconsistent:NumberOfFeeds"
    return {"label": "Coil Model Number", "kind": "number", "value": feeds, "raw": model,
            "source": "model number" + (f" + {drawing['source']}" if drawing else "")}, None


def _option(value: str, options: list[str]) -> str | None:
    from coilforge.ccsi.selection_report import match_option, option_key

    exact = match_option(value, options)
    if exact is not None:
        return exact
    # A bare size ("1/4") against "1/4 x 0.025"-style options: the size must lead exactly one option.
    want = option_key(value)
    hits = [o for o in options if option_key(o).startswith(f"{want} x ")]
    return hits[0] if len(hits) == 1 else None


def merge_extras(records: list[dict[str, Any]], pages: list[str]) -> list[dict[str, Any]]:
    """Add the PDF's extra fields to each coil record of that PDF (in place; returns ``records``).

    Only ids in the coil type's map, only where the report page itself printed nothing for them.
    """
    extras = extract_extras(pages)
    for record in records:
        coil_type, tag = record.get("coil_type"), record.get("base_tag")
        if not coil_type or not tag:
            continue
        cmap = load_coil_data_map(coil_type)
        fields, flags = record["fields"], record["flags"]
        mine = extras.get(tag, {})
        basis = _airflow_basis(fields)
        if basis and "ACFM" in cmap.fields and "ACFM" not in fields:
            picked = _option(basis[0], cmap.fields["ACFM"].options or [])
            if picked is None:
                flags.append("unmatched_option:ACFM")
            else:
                fields["ACFM"] = {"label": "Air flow basis", "kind": "select", "value": picked, "raw": basis[1],
                                  "source": "airflow unit on the report page"}
        if "NumberOfFeeds" in cmap.fields and "NumberOfFeeds" not in fields:
            field, flag = _feeds(record, mine.get("_drawing_circuits"))
            if flag:
                flags.append(flag)
            elif field:
                fields["NumberOfFeeds"] = field
        for ccsi_id, extra in mine.items():
            entry = cmap.fields.get(ccsi_id)
            if ccsi_id.startswith("_") or entry is None or ccsi_id in fields:
                continue
            field = dict(extra)
            if entry.options:
                picked = _option(field["value"], entry.options)
                if picked is None:
                    flags.append(f"unmatched_option:{ccsi_id}")
                else:
                    field["value"] = picked
            fields[ccsi_id] = field
    return records
