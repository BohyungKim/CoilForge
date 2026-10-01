"""CCSI coil-data mapping contract: Direct Coil draft values -> CCSI form inputs.

The drawing-dimension push (``ccsi_dx_field_map.json``) fills the 13+ dimension cells;
this module covers the rest of the form — geometry, options, air and refrigerant
conditions — so CCSI can rate a coil from CoilForge's extraction instead of an
application engineer re-typing it (Rating mode, John 2026-09-24).

Pure. Three rules carry it:

* **Role.** ``input`` entries may be pushed; ``computed`` (CCSI derives it) and
  ``locked`` (read-only on the live form) are read back only, never written.
* **Exact vocabulary.** A select is filled only when the source value lands exactly on
  one of the option texts captured live. The transforms are spelling/format
  normalizations (``R-32`` -> ``R32``, ``1.125`` -> ``1 1/8"``), never engineering
  inference — a fin thickness with no material, or an FPI of 8.5 against an
  integer-only list, is ``CCSI_OPTION_UNMAPPED``, not the nearest option.
* **Mapping status.** Every entry starts ``captured`` (inferred from label + key name,
  review-required). Only ``validated``/``confirmed`` entries are pushable; a captured
  entry still resolves its value so validation can compare it (``CCSI_NOT_VALIDATED``).
  A promotion carries its ``evidence`` (the cross-checked projects + John's approval).

**Geometry re-selection gate (D7, John 2026-09-29).** When the submittal's fin is one CCSI
cannot build — a fin surface off CCSI's list (``Sine``) or a fin gauge no CCSI fin option has
(``0.0075``) — the application engineer substitutes the fin and re-optimises rows/FPI in CCSI
(observed on 3183). Pushing the submittal's rows/FPI/fin would then rate a different coil, so
for such a coil those fields are withheld (``CCSI_GEOMETRY_RESELECT``) whatever their mapping
status; FH/FL/feeds and the conditions still go.

**Oxygen8 default profile (D2, John 2026-09-29).** Fields the submittal never states but every
finished CCSI selection sets identically (header Copper / (L), casing Standard / Galv 16 ga, …)
carry a ``default``. It is used ONLY when the source is absent — a stated value always wins and a
stated value off the CCSI list stays blocked (a Finkote coating never becomes ``Plain``); a source
blocked for any reason other than absence is never defaulted over (``CCSI_DEFAULT_PROFILE``).

**Value maps (D6).** ``value_map`` translates a source value to a CCSI option (circuits 1 ->
``Single-Circuit``); an unmapped value is ``CCSI_OPTION_UNMAPPED``, never the nearest option.

**Tube / fin material (D1, John 2026-09-30).** The submittal states ``0.016 Copper`` /
``0.0075 Aluminium``; the intake's number/unit split keeps the gauge as the value and parks the
material word in the field's ``unit``, which ``option_material_gauge`` reads. The tube surface is
its own canonical field (``Smooth`` = CCSI ``Plain``, John's ruling). A gauge with no material,
or a tube with no stated surface, is ``CCSI_OPTION_UNMAPPED`` — never assumed.

Review aid only: nothing here writes to CCSI or approves anything.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

MAP_DIR = Path(__file__).resolve().parents[3] / "web" / "ccsi"

Role = Literal["input", "computed", "locked"]
Transform = Literal[
    "text", "number", "number_times_quantity", "option_exact", "option_number", "option_inch_fraction",
    "option_refrigerant", "value_map", "option_material_gauge", "option_coating", "option_fluid_type",
    "glycol_ratio",
]
MappingStatus = Literal["captured", "validated", "confirmed"]
ReasonCode = Literal[
    "CCSI_OK",
    "CCSI_NOT_VALIDATED",
    "CCSI_READ_BACK_ONLY",
    "CCSI_NO_SOURCE",
    "CCSI_SOURCE_MISSING",
    "CCSI_SOURCE_BLOCKED",
    "CCSI_OPTION_UNMAPPED",
    "CCSI_VALUE_UNPARSEABLE",
    "CCSI_GEOMETRY_RESELECT",
    "CCSI_DEFAULT_PROFILE",
]

PUSHABLE_STATUSES: frozenset[str] = frozenset({"validated", "confirmed"})
# A blocked source whose only reason is absence may take the default profile; any other block
# (a conflict, an ambiguous read) must stay visible and is never defaulted over.
_ABSENCE_BLOCK_REASONS: frozenset[str | None] = frozenset({None, "required canonical field missing"})
# Withheld when the submittal fin cannot be built in CCSI (D7). FH/FL/feeds are not here:
# on 3183 they survived the re-selection unchanged.
GEOMETRY_RESELECT_IDS: frozenset[str] = frozenset({"RowsDeep", "FinsPerInch", "FinSurface", "FinMaterial"})
# Coil identity the caller supplies next to the draft fields (not draft field keys).
IDENTITY_KEYS: frozenset[str] = frozenset({"tag", "coil_quantity"})
CANONICAL_GROUPS: tuple[str, ...] = (
    "geometry", "airside_conditions", "refrigerant_conditions", "materials_construction",
    "connections", "manufacturing_options", "performance",
)
# The tube's surface (D1) — a canonical field, not a draft field; read only for TubeMaterial.
TUBE_SURFACE_SOURCE = "materials_construction.tube_surface"
# The fluid the submittal's "Fluid Percent (%)" is a percentage OF — read only for GlycolRatio.
FLUID_TYPE_SOURCE = "airside_conditions.fluid_type"
# Submittal tube-surface word -> CCSI's. Smooth = Plain is John's ruling (2026-09-30; 6/6 harvested
# DX/HGRH coils: submittal Smooth, CCSI Plain). CCSI's own words map to themselves; nothing else does.
_TUBE_SURFACE_TO_CCSI: dict[str, str] = {"smooth": "plain", "plain": "plain", "rifled": "rifled"}


class CcsiCoilDataEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str
    ccsi_label: str
    role: Role
    type: Literal["text", "number", "select"]
    unit: str | None = None
    draft_key: str | None
    transform: Transform
    mapping_status: MappingStatus
    options: list[str] | None = None
    no_source_reason: str | None = None
    evidence: str | None = None
    # A canonical-record field ("group.key") read when the value is not a Direct Coil draft
    # field — HGRH vapor/condensing/subcooling and the water fluid block (plan Step A).
    canonical_path: str | None = None
    default: str | None = None
    value_map: dict[str, str] | None = None


class CcsiCoilDataMap(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    form: str
    coil_type: str
    version: str
    captured_from: str
    note: str = Field(alias="_note")
    fields: dict[str, CcsiCoilDataEntry]


class CoilDataPushEntry(BaseModel):
    """One CCSI field's resolution for one coil. ``value`` is CCSI-formatted text."""

    model_config = ConfigDict(extra="forbid")

    ccsi_id: str
    ccsi_label: str
    section: str
    role: Role
    source_key: str | None
    source_value: Any = None
    value: str | None = None
    reason_code: ReasonCode
    reason: str
    pushable: bool
    review_required: bool


@lru_cache(maxsize=None)
def load_coil_data_map(coil_type: str = "DX") -> CcsiCoilDataMap:
    path = MAP_DIR / f"ccsi_coil_data_map.{coil_type.lower()}.json"
    return CcsiCoilDataMap.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _unwrap(source: Any) -> tuple[Any, str | None, str | None]:
    """(value, status, blocked_reason) from a DirectCoilDraftField, its dict form, or a bare value."""
    if source is None:
        return None, None, None
    if hasattr(source, "model_dump"):
        source = source.model_dump()
    if isinstance(source, Mapping) and "value" in source:
        return source.get("value"), source.get("status"), source.get("blocked_reason")
    return source, None, None


def _unit(source: Any) -> str | None:
    """The ``unit`` of a draft field / FieldValue (or its dict form); None for a bare value."""
    if hasattr(source, "model_dump"):
        source = source.model_dump()
    if not isinstance(source, Mapping) or source.get("unit") is None:
        return None
    return str(source["unit"]).strip() or None


def _as_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _number_text(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def _inch_fraction(x: float) -> str | None:
    """1.125 -> '1 1/8"'. Only exact sixteenths; anything else is not a CCSI size."""
    sixteenths = x * 16
    if abs(sixteenths - round(sixteenths)) > 1e-6 or x <= 0:
        return None
    frac = Fraction(round(sixteenths), 16)
    whole, rem = divmod(frac.numerator, frac.denominator)
    rem_text = f"{Fraction(rem, frac.denominator)}" if rem else ""
    text = " ".join(part for part in (str(whole) if whole else "", rem_text) if part)
    return f'{text}"'


def _pick_option(candidate: str | None, options: list[str]) -> str | None:
    if candidate is None:
        return None
    wanted = candidate.strip().casefold()
    for option in options:
        if option.casefold() == wanted:
            return option
    return None


def _transform(
    entry: CcsiCoilDataEntry, value: Any, quantity: Any = None, *, unit: str | None = None, surface: Any = None,
    fluid: Any = None,
) -> tuple[str | None, ReasonCode | None, str]:
    """Return (ccsi_text, failure_code, explanation). failure_code None = resolved.

    ``number_times_quantity``: the submittal states airflow PER COIL, while CCSI's Total Air
    Flow covers every coil of the tag (3154 HHWC-1: 400 CFM x qty 3 = 1200). Both factors are
    submittal values; an unknown quantity is never assumed to be 1.
    ``option_material_gauge``: ``unit`` carries the material, ``surface`` the tube surface (D1).
    """
    options = entry.options or []
    if entry.transform == "glycol_ratio":
        return _glycol_ratio(value, fluid)
    if entry.transform == "option_fluid_type":
        picked = _fluid_type_option(value, options)
        return (picked, None, "") if picked is not None else (
            None, "CCSI_OPTION_UNMAPPED", f"{value!r} is not a CCSI fluid ({', '.join(options)})")
    if entry.transform == "option_coating":
        picked, why = _coating_option(value, options)
        return (picked, None, why) if picked is not None else (None, "CCSI_OPTION_UNMAPPED", why)
    if entry.transform == "option_material_gauge":
        picked, why = _material_gauge_option(value, unit, surface, options)
        return (picked, None, "") if picked is not None else (None, "CCSI_OPTION_UNMAPPED", why)
    if entry.transform == "number_times_quantity":
        x, q = _as_float(value), _as_float(quantity)
        if x is None:
            return None, "CCSI_VALUE_UNPARSEABLE", f"{value!r} is not a number"
        if q is None or q <= 0 or not float(q).is_integer():
            return None, "CCSI_SOURCE_MISSING", (
                f"coil quantity {quantity!r} unknown — CCSI total = per-coil {_number_text(x)} x quantity"
            )
        return _number_text(round(x * q, 6)), None, ""
    if entry.transform == "text":
        text = str(value).strip()
        return (text, None, "") if text else (None, "CCSI_SOURCE_MISSING", "empty text")
    if entry.transform in ("number", "option_number", "option_inch_fraction"):
        x = _as_float(value)
        if x is None:
            return None, "CCSI_VALUE_UNPARSEABLE", f"{value!r} is not a number"
        if entry.transform == "number":
            return _number_text(x), None, ""
        candidate = _number_text(x) if entry.transform == "option_number" else _inch_fraction(x)
    elif entry.transform == "option_refrigerant":
        candidate = str(value).replace("-", "").replace(" ", "")
    elif entry.transform == "value_map":
        x = _as_float(value)
        key = _number_text(x) if x is not None else str(value).strip()
        candidate = (entry.value_map or {}).get(key)
        if candidate is None:
            return None, "CCSI_OPTION_UNMAPPED", f"{value!r} has no value_map entry ({', '.join(entry.value_map or {})})"
    else:  # option_exact
        candidate = str(value)
    picked = _pick_option(candidate, options)
    if picked is None:
        return None, "CCSI_OPTION_UNMAPPED", f"{value!r} has no exact CCSI option (tried {candidate!r})"
    return picked, None, ""


def _fluid_type_option(value: Any, options: list[str]) -> str | None:
    """The submittal's fluid on CCSI's list: ``Water`` as is, ``Propylene`` -> ``Propylene Glycol``
    (Oxygen8 submittals name the glycol without the word). Nothing else is guessed."""
    text = " ".join(str(value).split())
    exact = _pick_option(text, options)
    if exact is not None:
        return exact
    return _pick_option(f"{text} Glycol", options)


def _glycol_ratio(value: Any, fluid: Any) -> tuple[str | None, ReasonCode | None, str]:
    """CCSI Fluid Ratio (%) = the GLYCOL share; the submittal's Fluid Percent (%) is the share of the
    fluid it names (2026-09-30: "Water" + 100 read as 100 % glycol on 3154 / 2954).

    Water -> 0 (only at 100 %, anything else contradicts itself); a glycol -> its percent; no stated
    fluid -> unresolved, since the same number means opposite things for water and glycol.
    """
    x = _as_float(value)
    if x is None:
        return None, "CCSI_VALUE_UNPARSEABLE", f"{value!r} is not a percent"
    name = " ".join(str(fluid or "").split()).casefold()
    if not name:
        return None, "CCSI_SOURCE_MISSING", "fluid type not stated — a fluid percent cannot be read as glycol without it"
    if name == "water":
        if abs(x - 100) > 1e-9:
            return None, "CCSI_VALUE_UNPARSEABLE", f"Water at {_number_text(x)} % contradicts itself"
        return "0", None, ""
    if "glycol" in name or name in ("propylene", "ethylene", "tri ethylene"):
        return _number_text(x), None, ""
    return None, "CCSI_OPTION_UNMAPPED", f"fluid {fluid!r} is neither water nor a glycol"


_NO_COATING = frozenset({"none", "plain", "standard", "std", "n/a"})


def _coating_key(text: str) -> str:
    return re.sub(r"\s+coating$", "", " ".join(str(text).split()).casefold())


def _coating_option(value: Any, options: list[str]) -> tuple[str | None, str]:
    """(CCSI option, note) for a stated coil coating (John 2026-09-30).

    A coating the dropdown offers is selected by name (``AA`` -> ``AA Coating``). A stated
    coating the dropdown lacks (ElectroFin, Finkote, Heresite ...) selects the dropdown's one
    coating option, and the Drawing Notes carry the actual coating name
    (``submittal_to_drawing._engine_drawing_notes``). No coating -> ``Plain``.
    """
    from coilforge.submittal.pdf_intake import coating_family

    text = str(value).strip()
    plain = next((o for o in options if o.casefold() == "plain"), None)
    if not text or text.casefold() in _NO_COATING:
        return (plain, "") if plain else (None, "no Plain option on this form")
    family = coating_family(text) or text
    named = [o for o in options if _coating_key(o) == _coating_key(family)]
    if len(named) == 1:
        return named[0], ""
    coated = [o for o in options if o is not plain]
    if len(coated) != 1:
        return None, f"{text!r} is not a CCSI option and the form offers {len(coated)} coating options"
    return coated[0], f"{family} is not a CCSI option — {coated[0]} selected; Drawing Notes name the coating"


_GAUGE_RE = re.compile(r"\d*\.\d+")


def _material_key(text: str) -> str:
    """Whole-material comparison key: case/space folded, ``Aluminium`` spelled ``Aluminum``."""
    return re.sub(r"\baluminium\b", "aluminum", " ".join(text.split()).casefold())


def _material_gauge_option(
    value: Any, material: str | None, surface: Any, options: list[str]
) -> tuple[str | None, str]:
    """(CCSI option, explanation) for a gauge + material (+ tube surface) — D1.

    An option reads as ``<material> <gauge> [<surface>]`` around its gauge (``_GAUGE_RE``, the D7
    gate's own definition). The material must equal the option's WHOLE material (``Aluminum`` is
    not ``Coated aluminum``), the gauge must be numerically equal (``0.0075`` never becomes
    ``0.008``; ``0.01`` is ``0.010``), and when the option names a surface the submittal must state
    one that maps — even a lone ``Plain`` candidate is never assumed.
    """
    exact = _pick_option(str(value), options)
    if exact is not None:  # already a CCSI option text (a manual entry)
        return exact, ""
    gauge = _as_float(value)
    if gauge is None:
        return None, f"{value!r} is not a gauge"
    if not material:
        return None, f"gauge {value} with no material — never assumed"
    surface_text = str(surface).strip() if surface not in (None, "") else None
    wanted_surface = _TUBE_SURFACE_TO_CCSI.get(surface_text.casefold()) if surface_text else None
    hits: list[str] = []
    surface_required = False
    for option in options:
        m = _GAUGE_RE.search(option)
        if m is None or abs(float(m.group()) - gauge) > 1e-9:
            continue
        if _material_key(option[: m.start()].rstrip(" -")) != _material_key(material):
            continue
        option_surface = option[m.end():].strip().casefold()
        if option_surface:
            surface_required = True
            if option_surface != wanted_surface:
                continue
        hits.append(option)
    stated = f"{material} {value}" + (f" {surface_text}" if surface_required and surface_text else "")
    if surface_required and wanted_surface is None:
        if surface_text is None:
            return None, f"{stated}: tube surface not stated — Plain/Rifled is never assumed"
        return None, f"{stated}: tube surface {surface_text!r} has no CCSI equivalent"
    if len(hits) != 1:
        return None, f"{stated} has no exact CCSI option"
    return hits[0], ""


def geometry_reselect_reason(sources: Mapping[str, Any], cmap: CcsiCoilDataMap) -> str | None:
    """Why this coil's fin cannot be built in CCSI (D7), or None when it can.

    Judged against the map's own captured options, so each coil type uses its form's list.
    An absent fin value is not evidence either way and never triggers the gate.
    """
    surface_entry = cmap.fields.get("FinSurface")
    surface = _unwrap(sources.get("fin_surface"))[0]
    if surface_entry and surface_entry.options and surface not in (None, ""):
        if _pick_option(str(surface), surface_entry.options) is None:
            return f"fin surface {surface!r} is not a CCSI option ({', '.join(surface_entry.options)})"
    material_entry = cmap.fields.get("FinMaterial")
    gauge_match = _GAUGE_RE.search(str(_unwrap(sources.get("fin_material"))[0] or ""))
    if material_entry and material_entry.options and gauge_match:
        gauge = float(gauge_match.group())
        offered = {float(m.group()) for o in material_entry.options if (m := _GAUGE_RE.search(o))}
        if not any(abs(gauge - g) < 1e-9 for g in offered):
            return f"fin gauge {gauge} is not offered by CCSI ({', '.join(str(g) for g in sorted(offered))})"
    return None


def canonical_sources(record: Any) -> dict[str, Any]:
    """``{"group.key": FieldValue}`` from a SubmittalCoilCandidate / CanonicalCoilRecord.

    Merged next to the draft fields so a map entry's ``canonical_path`` can find its value;
    the FieldValue keeps its own status, so a blocked extraction stays blocked.
    """
    out: dict[str, Any] = {}
    quantity = getattr(record, "quantity", None)
    if quantity is not None:
        out["coil_quantity"] = quantity
    for group in CANONICAL_GROUPS:
        for key, field in (getattr(record, group, None) or {}).items():
            out[f"{group}.{key}"] = field
    return out


def resolve_coil_data(
    sources: Mapping[str, Any], *, coil_type: str = "DX"
) -> list[CoilDataPushEntry]:
    """Resolve every CCSI coil-data field for one coil.

    ``sources`` maps draft field keys (plus ``tag`` / ``coil_quantity``, and the canonical
    ``TUBE_SURFACE_SOURCE`` that TubeMaterial reads) to a ``DirectCoilDraftField``, its dict
    dump, or a bare value.
    """
    out: list[CoilDataPushEntry] = []
    cmap = load_coil_data_map(coil_type)
    reselect = geometry_reselect_reason(sources, cmap)
    surface, surface_status, _ = _unwrap(sources.get(TUBE_SURFACE_SOURCE))
    tube_surface = None if surface_status == "blocked" else surface
    fluid, fluid_status, _ = _unwrap(sources.get(FLUID_TYPE_SOURCE))
    fluid_type = None if fluid_status == "blocked" else fluid
    for ccsi_id, entry in cmap.fields.items():
        source_key = entry.draft_key or entry.canonical_path
        raw = sources.get(source_key) if source_key else None
        value, status, blocked_reason = _unwrap(raw)
        def emit(code: ReasonCode, reason: str, text: str | None = None, pushable: bool = False) -> None:
            out.append(
                CoilDataPushEntry(
                    ccsi_id=ccsi_id,
                    ccsi_label=entry.ccsi_label,
                    section=entry.section,
                    role=entry.role,
                    source_key=source_key,
                    source_value=value,
                    value=text,
                    reason_code=code,
                    reason=reason,
                    pushable=pushable,
                    review_required=True,
                )
            )

        absent = value is None or (isinstance(value, str) and not value.strip())
        if entry.default is not None and absent and (status != "blocked" or blocked_reason in _ABSENCE_BLOCK_REASONS):
            pushable = entry.role == "input" and entry.mapping_status in PUSHABLE_STATUSES
            emit("CCSI_DEFAULT_PROFILE", "not stated by the submittal — Oxygen8 CCSI default profile (review)",
                 entry.default, pushable=pushable)
            continue
        if source_key is None:
            emit("CCSI_NO_SOURCE", entry.no_source_reason or "CoilForge has no source for this field")
            continue
        if status == "blocked":
            emit("CCSI_SOURCE_BLOCKED", blocked_reason or "source field is blocked")
            continue
        if value is None or (isinstance(value, str) and not value.strip()):
            emit("CCSI_SOURCE_MISSING", f"{source_key} is empty in the source")
            continue
        text, failure, why = _transform(
            entry, value, _unwrap(sources.get("coil_quantity"))[0], unit=_unit(raw),
            surface=tube_surface if entry.draft_key == "tube_material" else None,
            fluid=fluid_type if entry.transform == "glycol_ratio" else None,
        )
        if failure is not None:
            emit(failure, why)
        elif reselect and ccsi_id in GEOMETRY_RESELECT_IDS:
            emit("CCSI_GEOMETRY_RESELECT", f"withheld — the coil needs re-selection in CCSI: {reselect}", text)
        elif entry.role != "input":
            emit("CCSI_READ_BACK_ONLY", f"{entry.role} on the CCSI form; compared on read-back, never pushed", text)
        elif entry.mapping_status not in PUSHABLE_STATUSES:
            emit("CCSI_NOT_VALIDATED", "mapping is captured, not yet validated against past CCSI selections", text)
        else:
            # ``why`` on a resolved value is a caveat the reviewer must see (a coating the
            # dropdown lacks, pushed as its one coating option).
            emit("CCSI_OK", "ready to push (review before Calculate)" + (f" — {why}" if why else ""),
                 text, pushable=True)
    return out


def summarize(entries: list[CoilDataPushEntry]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.reason_code] = counts.get(e.reason_code, 0) + 1
    return {
        "reason_counts": counts,
        "pushable": sum(e.pushable for e in entries),
        "resolved": sum(e.value is not None for e in entries),
        "total": len(entries),
        "review_aid_only": True,
        "export_allowed": False,
    }


_TYPE_BY_CATEGORY = {"DX COIL": "DX", "HGRH COIL": "HGRH", "Chilled Water Coil": "CWC", "Hot Water Coil": "HWC"}


def coil_type_for_tag(tag: str | None) -> str | None:
    """Map a coil tag (CDXC-1, RHHGRH-2, CCWC-1, PHWC-1 …) to its coil-data map type."""
    from coilforge.submittal.pdf_intake import coil_category_of_tag

    return _TYPE_BY_CATEGORY.get(coil_category_of_tag(tag or "") or "")


def _as_candidate_and_draft(candidate: Any, draft: Any) -> tuple[Any, dict[str, Any]]:
    from coilforge.submittal.candidate import SubmittalCoilCandidate

    if isinstance(candidate, Mapping):
        candidate = SubmittalCoilCandidate.model_validate(candidate)
    if hasattr(draft, "model_dump"):
        draft = draft.model_dump()
    return candidate, draft or {}


def _coil_tag(candidate: Any, draft: Mapping[str, Any]) -> str | None:
    tag = _unwrap(candidate.tag)[0] if candidate is not None and candidate.tag is not None else None
    return tag or _unwrap((draft.get("fields") or {}).get("tag"))[0]


def coil_data_sources(candidate: Any = None, draft: Any = None) -> dict[str, Any]:
    """The ``resolve_coil_data`` sources for one coil — shared by the push payload and the
    selection-report cross-check so the two can never resolve a coil differently.

    The candidate's canonical groups (``group.key``) + the Direct Coil draft fields (the draft
    wins on a shared key) + its coil quantity + the coil tag.
    """
    candidate, draft = _as_candidate_and_draft(candidate, draft)
    sources: dict[str, Any] = dict(canonical_sources(candidate)) if candidate is not None else {}
    sources.update(draft.get("fields") or {})
    if draft.get("coil_quantity") is not None:
        sources["coil_quantity"] = draft["coil_quantity"]
    sources.setdefault("tag", _coil_tag(candidate, draft))
    return sources


def build_coil_data_payload(
    *, candidate: Any = None, draft: Any = None, coil_type: str | None = None
) -> dict[str, Any]:
    """The ``coil_data`` block of the CCSI push payload for one coil.

    Sources come from ``coil_data_sources``. Every entry — pushable or not — is returned with
    its reason so the userscript and the review panel show why a field is held.

    ``performance_consistency`` says whether the coil's own performance values agree with each
    other (airflow x air delta-T vs capacity, GPM x fluid delta-T vs capacity, face velocity).
    It reads the same ``sources`` BEFORE any transform — per-coil values, fluid as the submittal
    names it — and changes no entry: an ``inconsistent`` finding is a warning for the engineer,
    never a reason to hold a field or stop the push (John 2026-10-01).
    """
    from coilforge.coil_utilities.performance_consistency import check_performance_consistency

    candidate, draft = _as_candidate_and_draft(candidate, draft)
    sources = coil_data_sources(candidate, draft)
    tag = _coil_tag(candidate, draft)
    resolved_type = coil_type or coil_type_for_tag(tag)
    if resolved_type is None:
        return {"coil_type": None, "tag": tag, "entries": [], "error": f"no coil-data map for tag {tag!r}",
                "review_aid_only": True, "export_allowed": False}
    cmap = load_coil_data_map(resolved_type)
    entries = resolve_coil_data(sources, coil_type=resolved_type)
    return {
        "schema": "coilforge.ccsi.coil_data/1",
        "coil_type": resolved_type,
        "tag": tag,
        "geometry_reselect_reason": geometry_reselect_reason(sources, cmap),
        "entries": [{**e.model_dump(), "selector": f"#{e.ccsi_id}", "type": cmap.fields[e.ccsi_id].type}
                    for e in entries],
        "summary": summarize(entries),
        "performance_consistency": _performance_consistency(sources, resolved_type, check_performance_consistency),
        "review_aid_only": True,
        "export_allowed": False,
    }


def _performance_consistency(sources: Mapping[str, Any], coil_type: str, check: Any) -> dict[str, Any]:
    """The self-consistency report, or an explicit ``error`` in its place.

    A warning must never be the reason the push payload fails: without this guard an exception
    in the check would turn the whole route into a 500, the page would drop the block, and the
    one-button flow would refuse to run. The failure is reported, not hidden.
    """
    try:
        return check(sources, coil_type=coil_type).model_dump()
    except Exception as exc:  # noqa: BLE001 — any failure here must stay a warning
        return {"coil_type": coil_type, "findings": [], "counts": {},
                "error": f"{type(exc).__name__}: {exc}", "review_aid_only": True, "export_allowed": False}
