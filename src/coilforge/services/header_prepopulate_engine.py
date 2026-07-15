"""Deterministic header prepopulation rule engine.

Pure function ``prepopulate(request) -> HeaderPrepopulateResponse``. The only
I/O is loading ``coil_header_rules.yaml`` once (module-level cache). No Epicor,
export, BOM, or quoting calls. Header prepopulation only.

Confidence/review gate (constraint #3):

* ``HIGH``     -> ``values``        (auto-prepopulate)
* ``MEDIUM``   -> ``suggestions``   (always ``review_required``)
* ``LOW`` / ``CONFLICT`` -> ``blocked`` (``value=None``, ``blocked_reason`` set)

Formula evaluation uses explicit safe helpers (no ``eval``).
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from coilforge.schemas.header_prepopulate import (
    Confidence,
    CoilType,
    FieldResult,
    HeaderPrepopulateRequest,
    HeaderPrepopulateResponse,
    ProductFamily,
    TerraVariant,
)

_RULES_PATH = Path(__file__).resolve().parents[1] / "rules" / "coil_header_rules.yaml"

# Rule IDs handled by dedicated phases rather than the generic constant emitter.
_NOTES_BASE_IDS = {"R-007", "R-008"}
_NOTES_APPEND_IDS = {"R-080", "R-081", "R-035a", "R-035b"}
_CASING_DEPTH_IDS = {"R-070", "R-071", "R-072", "R-073"}
_RETURN_SPACING_IDS = {"R-022", "R-023", "R-052"}
_CWC_IO_HD_SL_IDS = {
    "R-060", "R-061", "R-061v", "R-062", "R-063a", "R-063b",
    "R-064-sl", "R-064-io", "R-064-hd", "R-065", "R-065v",
}
_OTHER_SPECIAL_IDS = {
    "R-034",  # DX distributor S placement (formula)
    "R-034v",  # DX distributor S, Terra V (Sn = CD - Rn)
    "R-048",  # HGRH S/R positions (formula)
    "R-049",  # HGRH single-feed note — suppressed (treated as standard one-header)
    "R-051",  # cross-coil validation (no value rule)
    "R-068",  # CWC/HWC S/R "leave defaults" no-op
    "R-074",  # casing dims lookup
    "R-075",  # size_class
    "R-076",  # unit-size validation
    "R-090",  # copper straps required (header_count * per-header multiplier)
}
# Data-only rules: lookup tables consumed by compatibility/mechanical_fit.py, NOT
# emitted as engine fields. Listed here so the generic emitter skips them (they
# carry value=null and would otherwise place a spurious None suggestion).
_FIT_DATA_IDS = {
    "R-077",  # drain-pan / install width lookup
    "R-078",  # WIDTH/HEIGHT fit clearances
}
_SPECIAL_IDS = (
    _NOTES_BASE_IDS
    | _NOTES_APPEND_IDS
    | _CASING_DEPTH_IDS
    | _RETURN_SPACING_IDS
    | _CWC_IO_HD_SL_IDS
    | _OTHER_SPECIAL_IDS
    | _FIT_DATA_IDS
)

# Feature flags. R-086 (coil_style) is intentionally disabled by default.
_ENABLED_FEATURE_FLAGS: frozenset[str] = frozenset()


# --------------------------------------------------------------------------- #
# Rule table loading
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def load_rule_table() -> list[dict[str, Any]]:
    """Load and cache the YAML rule list."""
    with _RULES_PATH.open(encoding="utf-8") as handle:
        doc = yaml.safe_load(handle)
    return list(doc["rules"])


def _rule_index() -> dict[str, dict[str, Any]]:
    return {rule["rule_id"]: rule for rule in load_rule_table()}


def _refs(*rule_ids: str) -> list[str]:
    """Collect verbatim evidence_refs for the given rule IDs (deduped)."""
    index = _rule_index()
    out: list[str] = []
    for rid in rule_ids:
        for ref in index[rid]["evidence_refs"]:
            if ref not in out:
                out.append(ref)
    return out


# --------------------------------------------------------------------------- #
# Safe formula helpers
# --------------------------------------------------------------------------- #
def roundup_eighth(value: float) -> float:
    """Round ``value`` UP to the nearest eighth (1/8 = 0.125)."""
    eighths = math.ceil(round(value * 8, 6))
    return eighths / 8


def cd_dx_hgrh(rows: int) -> float:
    """DX/HGRH casing depth: ROUNDUP(rows * 0.866 to 1/8) + 2 (SOP-OLE1..4)."""
    return roundup_eighth(rows * 0.866) + 2


def cd_cwc_hwc(rows: int) -> float:
    """CWC/HWC casing depth: ROUNDUP(rows * 1.299 to 1/8) + 2 (SOP-OLE5)."""
    return roundup_eighth(rows * 1.299) + 2


def _return_spacing(suction_conn_size: float, circuits: int) -> list[float]:
    """R-022: Rn = n*D + (n-1)*1.5 for n in 1..circuits."""
    return [n * suction_conn_size + (n - 1) * 1.5 for n in range(1, circuits + 1)]


def _terra_v_return_spacing(suction_conn_size: float, circuits: int) -> list[float]:
    """R-023 Terra V: Rn = (n-0.5)*D + (n-1)*1.5 + 0.75 for n in 1..circuits.
    (R1=0.5D+0.75, R2=1.5D+2.25, R3=2.5D+3.75, R4=3.5D+5.25.)"""
    return [
        (n - 0.5) * suction_conn_size + (n - 1) * 1.5 + 0.75
        for n in range(1, circuits + 1)
    ]


def _hgrh_return_spacing(
    conn_size: float, n_conn: int, product: ProductFamily
) -> list[float]:
    """R-052: HGRH return spacing for n_conn connections per header.

    VENTUM+ uses the connection size as a flat location for every R (CHK branch);
    all other families use the running-edge formula Rn = n*D + (n-1)*1.5. At n=1
    both reduce to D, so a single-connection header is identical either way.
    """
    if product == ProductFamily.VENTUM_PLUS:
        return [conn_size for _ in range(1, n_conn + 1)]
    return [n * conn_size + (n - 1) * 1.5 for n in range(1, n_conn + 1)]


def _excel_round(value: float) -> int:
    """Excel ROUND to nearest integer (half away from zero)."""
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def _dx_cd_value(request: HeaderPrepopulateRequest) -> float:
    """DX casing depth (R-070 base, R-072 multi-circuit). Assumes rows set."""
    base = cd_dx_hgrh(request.rows)  # type: ignore[arg-type]
    if request.circuits is not None and request.suction_conn_size is not None:
        d = request.suction_conn_size
        c = request.circuits
        if request.with_hgrh and request.hgrh_conn_size is not None:
            multi = c * (d + 1.5) + (d - request.hgrh_conn_size) / 2
        else:
            multi = (c + 1) * d + (c - 1) * 1.5
        return max(base, multi)
    return base


def copper_strap_requirement(
    coil_type: CoilType, header_count: int | None
) -> FieldResult | None:
    """R-090: copper straps required = ``header_count * multiplier(coil_type)``.

    DX -> 1 strap/header, HGRH -> 2 straps/header (John, 2026-06-23). Coil types
    with no confirmed multiplier (CWC/HWC) return a LOW/blocked ``FieldResult``
    rather than a guess. ``header_count`` absent returns ``None`` so the caller
    can report it as a missing input. Single source of the R-090 logic shared by
    the full engine and the drawing-package route.
    """
    rule = _rule_index()["R-090"]
    multiplier = rule.get("strap_multiplier", {}).get(coil_type.value)
    if multiplier is None:
        return FieldResult(
            value=None,
            confidence=Confidence.LOW,
            evidence_refs=rule["evidence_refs"],
            review_required=True,
            blocked_reason=rule["blocked_reason"],
        )
    if header_count is None:
        return None
    return FieldResult(
        value=header_count * multiplier,
        confidence=Confidence.HIGH,
        evidence_refs=rule["evidence_refs"],
    )


# --------------------------------------------------------------------------- #
# Confidence routing (constraint #3 — exercised directly by the invariant test)
# --------------------------------------------------------------------------- #
def bucket_for_confidence(confidence: Confidence) -> str:
    if confidence == Confidence.HIGH:
        return "values"
    if confidence == Confidence.MEDIUM:
        return "suggestions"
    return "blocked"  # LOW | CONFLICT


# --------------------------------------------------------------------------- #
# applies_to / condition matching
# --------------------------------------------------------------------------- #
def _matches_list(token: str, allowed: Any) -> bool:
    if allowed is None:
        return True
    if isinstance(allowed, str):
        allowed = [allowed]
    return "*" in allowed or token in allowed


def _applies(rule: dict[str, Any], req: HeaderPrepopulateRequest) -> bool:
    applies_to = rule["applies_to"]
    if not _matches_list(req.type_of_coil.value, applies_to.get("coil_type")):
        return False
    if not _matches_list(req.product_type.value, applies_to.get("product_family")):
        return False
    # size_pattern scopes a rule to specific unit sizes (e.g. [H05, H10]). Declared on every
    # rule but null by default; _matches_list(token, None) -> True, so null keeps matching all
    # sizes (backward-compatible). Activated 2026-06-26 for the Ventum H H05/H10 SL override.
    if not _matches_list(req.unit_size, applies_to.get("size_pattern")):
        return False
    variant = applies_to.get("terra_variant")
    if variant is not None:
        if req.terra_variant is None or req.terra_variant.value not in variant:
            return False
    return True


def _coating_set(req: HeaderPrepopulateRequest) -> bool:
    return req.coating is not None and req.coating.strip().upper() != "NONE"


def _condition_met(only_when: str, req: HeaderPrepopulateRequest) -> bool:
    if only_when == "feeds_eq_1":
        return req.feeds == 1
    if only_when == "feeds_gt_1":
        return req.feeds is not None and req.feeds > 1
    if only_when == "coating_set":
        return _coating_set(req)
    if only_when == "hot_gas_bypass":
        return bool(req.hot_gas_bypass)
    if only_when == "with_hgrh":
        return bool(req.with_hgrh)
    if only_when == "back_to_back":
        return bool(req.back_to_back)
    if only_when == "qty_valves_set":
        return req.qty_valves is not None
    if only_when == "installed_on_drain_pan":
        return bool(req.installed_on_drain_pan)
    return True


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
def prepopulate(request: HeaderPrepopulateRequest) -> HeaderPrepopulateResponse:
    rules = load_rule_table()
    index = _rule_index()
    product = request.product_type
    coil = request.type_of_coil

    # --- R-076: unit-size validation (global gate) ---
    # Terra H and Terra V resolve to the same product_family (TERRA) but have
    # different size sets (Terra V adds 060/072/084/100), so the gate selects the
    # variant-scoped enumeration for Terra V. Casing (R-074) still keys on TERRA.
    enumerations = index["R-076"]["enumerations"]
    size_key = "TERRA_V" if request.terra_variant == TerraVariant.TERRA_V else product.value
    valid_sizes = enumerations.get(size_key, [])
    if request.unit_size not in valid_sizes:
        return HeaderPrepopulateResponse(blocked_reason="unknown_unit_size")

    values: dict[str, FieldResult] = {}
    suggestions: dict[str, FieldResult] = {}
    blocked: dict[str, FieldResult] = {}
    missing: list[str] = []

    def add_missing(inputs: list[str]) -> None:
        for inp in inputs:
            if inp not in missing:
                missing.append(inp)

    def place(field: str, result: FieldResult) -> None:
        bucket = bucket_for_confidence(result.confidence)
        {"values": values, "suggestions": suggestions, "blocked": blocked}[bucket][
            field
        ] = result

    # --- Generic constant / conflict emitter ---
    for rule in rules:
        rid = rule["rule_id"]
        if rid in _SPECIAL_IDS:
            continue
        if not _applies(rule, request):
            continue
        flag = rule.get("feature_flag")
        if flag is not None and flag not in _ENABLED_FEATURE_FLAGS:
            continue
        only_when = rule.get("only_when")
        if only_when is not None and not _condition_met(only_when, request):
            continue

        confidence = Confidence(rule["confidence"])
        # Terra is resolved to Terra H C with reliable checklist values
        # (John, 2026-06-11), so there is no longer a terra_variant gate.
        review_reason = None
        # Field/value resolution: `field_values` (per-field values) takes
        # precedence; otherwise `field` (str or list) + `value`/`value_map`.
        field_values = rule.get("field_values")
        if field_values is not None:
            field_value_pairs = list(field_values.items())
        else:
            fields = rule["field"]
            if isinstance(fields, str):
                fields = [fields]
            value = rule.get("value")
            value_map = rule.get("value_map")
            if value_map is not None:
                value = value_map.get(product.value)
            field_value_pairs = [(field, value) for field in fields]

        if confidence in (Confidence.LOW, Confidence.CONFLICT):
            for field, _ in field_value_pairs:
                place(
                    field,
                    FieldResult(
                        value=None,
                        confidence=confidence,
                        evidence_refs=rule["evidence_refs"],
                        review_required=True,
                        review_required_reason=review_reason,
                        blocked_reason=rule.get("blocked_reason"),
                    ),
                )
            continue

        review_required = confidence == Confidence.MEDIUM
        for field, field_value in field_value_pairs:
            place(
                field,
                FieldResult(
                    value=field_value,
                    confidence=confidence,
                    evidence_refs=rule["evidence_refs"],
                    review_required=review_required,
                    review_required_reason=review_reason if review_required else None,
                ),
            )

    # --- Notes assembly: base (R-007/R-008) then coating append (R-080/R-081) ---
    # Direct Coil selection has no coating trigger field, so the coating note is
    # always appended to the drawing notes (per John, 2026-06-11).
    note_lines: list[str] = []
    note_refs: list[str] = []
    for rid in ("R-007", "R-008", "R-080", "R-081", "R-035a", "R-035b"):
        rule = index[rid]
        if _applies(rule, request):
            note_lines.append(rule["value"])
            for ref in rule["evidence_refs"]:
                if ref not in note_refs:
                    note_refs.append(ref)
    if note_lines:
        place(
            "notes",
            FieldResult(
                value=note_lines,
                confidence=Confidence.HIGH,
                evidence_refs=note_refs,
            ),
        )

    # --- size_class (R-075, NOVA only) ---
    rule = index["R-075"]
    if _applies(rule, request):
        size_class = None
        for cls, sizes in rule["size_class_map"].items():
            if request.unit_size in sizes:
                size_class = cls
                break
        if size_class is not None:
            place(
                "size_class",
                FieldResult(
                    value=size_class,
                    confidence=Confidence.HIGH,
                    evidence_refs=rule["evidence_refs"],
                ),
            )

    # --- casing_depth (R-070 / R-071 / R-072 / R-073) ---
    _emit_casing_depth(request, place, add_missing)

    # --- return_spacing (R-022 / R-023) ---
    # R-022 (product_family ["*"]) applies to every DX family EXCEPT Terra V, which uses
    # its own SOP formula R-023 (Rn = (n-0.5)*D + (n-1)*1.5 + 0.75). Terra H/Terra H C
    # keep the generic R-022. (R-023 was promoted LOW->HIGH, John 2026-06-28, SOP-confirmed.)
    if coil == CoilType.DX:
        is_terra_v = request.terra_variant == TerraVariant.TERRA_V
        if is_terra_v and _applies(index["R-023"], request):
            if request.suction_conn_size is not None and request.circuits is not None:
                place(
                    "return_spacing",
                    FieldResult(
                        value=_terra_v_return_spacing(
                            request.suction_conn_size, request.circuits
                        ),
                        confidence=Confidence.HIGH,
                        evidence_refs=index["R-023"]["evidence_refs"],
                    ),
                )
            else:
                add_missing(["suction_conn_size", "circuits"])
        else:
            rule = index["R-022"]
            if _applies(rule, request):
                if request.suction_conn_size is not None and request.circuits is not None:
                    place(
                        "return_spacing",
                        FieldResult(
                            value=_return_spacing(
                                request.suction_conn_size, request.circuits
                            ),
                            confidence=Confidence.HIGH,
                            evidence_refs=rule["evidence_refs"],
                        ),
                    )
                else:
                    add_missing(["suction_conn_size", "circuits"])

    # --- DX distributor S placement (R-034 even-spacing; R-034v Terra V = CD - Rn) ---
    if coil == CoilType.DX:
        if request.rows is not None and request.circuits is not None:
            cd = _dx_cd_value(request)
            c = request.circuits
            is_terra_v = request.terra_variant == TerraVariant.TERRA_V
            if is_terra_v and request.suction_conn_size is not None:
                # Terra V: Sn = CD - Rn (Rn = R-023 Terra V return spacing). SOP-confirmed.
                r = _terra_v_return_spacing(request.suction_conn_size, c)
                place(
                    "dist_s",
                    FieldResult(
                        value=[round(cd - r[k - 1], 4) for k in range(1, c + 1)],
                        confidence=Confidence.HIGH,
                        evidence_refs=index["R-034v"]["evidence_refs"],
                    ),
                )
            else:
                place(
                    "dist_s",
                    FieldResult(
                        value=[_excel_round(k * cd / (c + 1)) for k in range(1, c + 1)],
                        confidence=Confidence.HIGH,
                        evidence_refs=index["R-034"]["evidence_refs"],
                    ),
                )
        else:
            add_missing(["rows", "circuits"])

    # --- CWC/HWC io / hd / sl resolvers ---
    if coil in (CoilType.CWC, CoilType.HWC):
        _emit_cwc_io_hd_sl(request, place)

    # --- casing dims lookup (R-074) ---
    rule = index["R-074"]
    if request.application is None:
        add_missing(["application"])
    else:
        # Terra V has its own casing table (vertical units are far taller than
        # Terra H), so key off TERRA_V and never borrow Terra H's TERRA|... rows.
        # Mirrors the R-076 size-set gate above.
        casing_fam = (
            "TERRA_V"
            if request.terra_variant == TerraVariant.TERRA_V
            else product.value
        )
        key = f"{casing_fam}|{request.application}|{request.unit_size}"
        entry = rule.get("lookup", {}).get(key)
        if entry is not None:
            for field, val in entry.items():
                place(
                    field,
                    FieldResult(
                        value=val,
                        confidence=Confidence.MEDIUM,
                        evidence_refs=rule["evidence_refs"],
                        review_required=True,
                    ),
                )

    # --- HGRH single-feed note (R-049): intentionally NOT emitted ---
    # John decision 2026-06-15: a single-feed HGRH is treated the same as a
    # standard one-header HGRH, so the advisory single-feed header/stubout note
    # is suppressed. R-049 stays in _SPECIAL_IDS so the generic emitter skips it
    # (no value is produced for `single_feed_note`).

    # --- HGRH S/R positions (R-048) ---
    if coil == CoilType.HGRH:
        rule = index["R-048"]
        if (
            request.circuits is not None
            and request.conn_size is not None
            and request.rows is not None
        ):
            positions = [
                x * request.conn_size + (x - 1) * 1.5
                for x in range(1, request.circuits + 1)
            ]
            for field in ("supply_position", "return_position"):
                place(
                    field,
                    FieldResult(
                        value=positions,
                        confidence=Confidence.HIGH,
                        evidence_refs=rule["evidence_refs"],
                    ),
                )
        else:
            add_missing(["circuits", "conn_size", "rows"])

    # --- HGRH return spacing R (R-052) ---
    # Product-branched per John 2026-06-25 / CHK HGRH. MEDIUM -> suggestions, so
    # the confidence gate is preserved (the review-aid drawing reads it as a
    # review-required value; it is never auto-promoted to a HIGH `values` entry).
    # The per-header connection count gates how many R slots fill; absent it we
    # fall back to `circuits` so a single emission still occurs.
    if coil == CoilType.HGRH:
        rule = index["R-052"]
        n_conn = request.qty_conn_per_header or request.circuits
        if request.conn_size is not None and n_conn is not None:
            place(
                "return_spacing",
                FieldResult(
                    value=_hgrh_return_spacing(request.conn_size, n_conn, product),
                    confidence=Confidence.MEDIUM,
                    evidence_refs=rule["evidence_refs"],
                    review_required=True,
                ),
            )
        else:
            add_missing(["conn_size", "qty_conn_per_header"])

    # --- copper straps required (R-090) ---
    _emit_copper_straps(request, place, add_missing)

    review_required = bool(suggestions) or bool(blocked)

    return HeaderPrepopulateResponse(
        values=values,
        suggestions=suggestions,
        blocked=blocked,
        missing_inputs=missing,
        review_required=review_required,
        blocked_reason=None,
    )


def assemble_drawing_notes(request: HeaderPrepopulateRequest) -> list[str]:
    """Return the engine-assembled drawing notes for a coil, or ``[]``.

    Wraps :func:`prepopulate` so callers (the paste-ready "Drawing Notes" field and
    the SVG title block) share ONE source with the drawing. The ``notes`` field is only
    placed when at least one note rule fires (R-007/008/080/081/035a/035b), so read it
    with ``.get`` — an unknown product line yields no distributor note (never invented).
    """
    result = prepopulate(request).values.get("notes")
    return [str(v) for v in result.value] if result else []


# --------------------------------------------------------------------------- #
# Phase helpers
# --------------------------------------------------------------------------- #
def _emit_copper_straps(request, place, add_missing) -> None:  # type: ignore[no-untyped-def]
    """R-090: copper straps = header_count * per-header multiplier.

    DX -> 1 strap/header, HGRH -> 2 straps/header (John, 2026-06-23). CWC/HWC
    have no confirmed multiplier, so they route to the blocked bucket rather
    than guessing. ``header_count`` absent -> reported as a missing input.

    Confidence here is HIGH for the deterministic DX/HGRH case; if the upstream
    coil_type / header_count were themselves inferred, the contract layer that
    wraps this output re-gates it to review_required (same pattern as the rest
    of the engine — the pure function only sees confirmed enum inputs).
    """
    result = copper_strap_requirement(request.type_of_coil, request.header_count)
    if result is None:
        add_missing(["header_count"])
    else:
        place("copper_straps_required", result)


def _emit_casing_depth(request, place, add_missing) -> None:  # type: ignore[no-untyped-def]
    coil = request.type_of_coil
    index = _rule_index()

    if coil in (CoilType.DX, CoilType.HGRH):
        if request.rows is None:
            add_missing(["rows"])
            return
        base = cd_dx_hgrh(request.rows)
        if coil == CoilType.DX:
            multi_circuit = (
                request.circuits is not None and request.suction_conn_size is not None
            )
            place(
                "casing_depth",
                FieldResult(
                    value=_dx_cd_value(request),
                    confidence=Confidence.HIGH,
                    evidence_refs=(
                        _refs("R-070", "R-072")
                        if multi_circuit
                        else index["R-070"]["evidence_refs"]
                    ),
                ),
            )
        else:  # HGRH
            # Casing depth is the rows-based base depth (R-070, HIGH) for ALL HGRH, single
            # or multi-circuit (John 2026-07-03). The R-073 multi-circuit formula
            # ((c+1)*D+(c-1)*1.5) is NOT a physical casing depth (e.g. 1.0"/1.25" for a
            # single circuit) and must never replace R-070: doing so flipped casing_depth to
            # MEDIUM once conn_size was routed, blanking slot.CD and corrupting Terra V's
            # S = CD - Rn. R-073 stays a YAML data rule but is no longer emitted for drawing.
            place(
                "casing_depth",
                FieldResult(
                    value=base,
                    confidence=Confidence.HIGH,
                    evidence_refs=index["R-070"]["evidence_refs"],
                ),
            )
    else:  # CWC / HWC
        if request.rows is None:
            add_missing(["rows"])
            return
        place(
            "casing_depth",
            FieldResult(
                value=cd_cwc_hwc(request.rows),
                confidence=Confidence.HIGH,
                evidence_refs=index["R-071"]["evidence_refs"],
            ),
        )


def _emit_cwc_io_hd_sl(request, place) -> None:  # type: ignore[no-untyped-def]
    """CWC/HWC io / hd / sl, accounting for feeds and product family.

    feeds == 1   -> single-feed overrides (R-064): sl=12/14 HIGH, io=TBD/hd=N/A MEDIUM
    feeds  > 1   -> R-060 io=2.3125 HIGH, R-062 hd=4 HIGH, R-063 sl HIGH
    feeds absent -> io/hd MEDIUM suggestions (missing feeds); sl HIGH default
    TERRA        -> io=3.25 HIGH (R-061), sl=10 HIGH (R-065) [checklist, John 2026-06-11]
    TERRA V      -> io=2.75 HIGH (R-061v), sl=12 HIGH (R-065v) [SOP, John 2026-06-28]
                    (return I/O = CH-2.75 is applied at the slot layer, needs casing height)
    """
    index = _rule_index()
    product = request.product_type
    is_terra_v = request.terra_variant == TerraVariant.TERRA_V
    feeds_one = request.feeds == 1
    feeds_multi = request.feeds is not None and request.feeds > 1

    # --- io ---
    if product == ProductFamily.TERRA:
        rule = index["R-061v"] if is_terra_v else index["R-061"]
        place(
            "io",
            FieldResult(
                value=rule["value"],
                confidence=Confidence.HIGH,
                evidence_refs=rule["evidence_refs"],
            ),
        )
    elif feeds_one:
        rule = index["R-064-io"]
        place(
            "io",
            FieldResult(
                value="TBD",
                confidence=Confidence.MEDIUM,
                evidence_refs=rule["evidence_refs"],
                review_required=True,
            ),
        )
    else:
        rule = index["R-060"]
        if feeds_multi:
            place(
                "io",
                FieldResult(
                    value=2.3125,
                    confidence=Confidence.HIGH,
                    evidence_refs=rule["evidence_refs"],
                ),
            )
        else:  # feeds absent
            place(
                "io",
                FieldResult(
                    value=2.3125,
                    confidence=Confidence.MEDIUM,
                    evidence_refs=rule["evidence_refs"],
                    review_required=True,
                    missing_inputs=["feeds"],
                ),
            )

    # --- hd ---
    if feeds_one:
        rule = index["R-064-hd"]
        place(
            "hd",
            FieldResult(
                value="N/A",
                confidence=Confidence.MEDIUM,
                evidence_refs=rule["evidence_refs"],
                review_required=True,
            ),
        )
    else:
        rule = index["R-062"]
        if feeds_multi:
            place(
                "hd",
                FieldResult(
                    value=4,
                    confidence=Confidence.HIGH,
                    evidence_refs=rule["evidence_refs"],
                ),
            )
        else:  # feeds absent
            place(
                "hd",
                FieldResult(
                    value=4,
                    confidence=Confidence.MEDIUM,
                    evidence_refs=rule["evidence_refs"],
                    review_required=True,
                    missing_inputs=["feeds"],
                ),
            )

    # --- sl ---
    if product == ProductFamily.TERRA:
        rule = index["R-065v"] if is_terra_v else index["R-065"]
        place(
            "sl",
            FieldResult(
                value=rule["value"],
                confidence=Confidence.HIGH,
                evidence_refs=rule["evidence_refs"],
            ),
        )
    elif feeds_one:
        rule = index["R-064-sl"]
        value = rule["value_map"][product.value]
        place(
            "sl",
            FieldResult(
                value=value,
                confidence=Confidence.HIGH,
                evidence_refs=rule["evidence_refs"],
            ),
        )
    else:
        rid = "R-063b" if product == ProductFamily.VENTUM_PLUS else "R-063a"
        rule = index[rid]
        place(
            "sl",
            FieldResult(
                value=rule["value"],
                confidence=Confidence.HIGH,
                evidence_refs=rule["evidence_refs"],
            ),
        )


