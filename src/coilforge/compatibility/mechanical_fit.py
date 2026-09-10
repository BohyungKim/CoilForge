"""Mechanical fit / coil-stability checks (review aid).

Pure, side-effect-free evaluation of whether a coil physically fits its casing,
mirroring the WIDTH FIT / HEIGHT FIT / INSTALL FIT verdicts in the Coil Checklist
workbook. The clearance constants live in rule ``R-078`` of
``coil_header_rules.yaml`` (transcribed from the four CHK FIT formulas); this
module only reads that table and compares — it never invents a value.

Confidence gate: the casing dimensions these checks depend on come from ``R-074``
at MEDIUM confidence (always review-required). Therefore every verdict carries
``review_required=True`` — a ``PASS`` means "passes the review-aid check, still
needs engineering sign-off", never an unqualified approval. A missing input
(unresolved casing dim, FH/FL/CH/OAL) degrades to ``CANNOT_EVALUATE`` with a
reason rather than guessing.

Drain-pan / install fit (the DX+HGRH and CWC+HWC pairing check) is added in a
later phase; this module currently covers the per-coil width/height checks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Literal

from coilforge.schemas.header_prepopulate import ProductFamily, VENTUM_PLUS_CLASS_VALUES
from coilforge.services.header_prepopulate_engine import _rule_index

FitVerdict = Literal["PASS", "FAIL", "CANNOT_EVALUATE"]
DrainPanVerdict = Literal["PASS", "FAIL", "CANNOT_EVALUATE", "NOT_APPLICABLE"]
WidthBasis = Literal["FL", "OAL"]
HeightBasis = Literal["FH", "CH"]

_R077 = "R-077"
_R078 = "R-078"

# The DX/HGRH/CWC casing column in R-074 has exactly ONE application per product
# family — the CHK CASING WIDTH/HEIGHT XLOOKUP `AND(product, application)` branches
# (DX!E9:E10 / CWC!E7:E8 / HGRH!E7:E8): NOVA->DECOUPLED, TERRA->INTEGRATED,
# VENTUM_H->CPLD EXT, VENTUM+->INTEGRATED. So a DX/HGRH/CWC coil's application is
# derivable from its family (the workbook's own logic, not a guess). HWC offers
# several applications (HORZ/VERT/STANDALONE/CPLD W COOLING) so it is NOT derivable
# and stays review-required when the application is unknown.
_DX_CWC_APPLICATION = {
    "NOVA": "DECOUPLED",
    "TERRA": "INTEGRATED",
    "VENTUM_H": "CPLD EXT",
    "VENTUM_PLUS": "INTEGRATED",
    "OMNIA": "INTEGRATED",  # inherits Ventum+ (assumption, John 2026-08-25)
}


def _coarse_terra_family(product_family: str) -> str:
    """Collapse the split Terra families onto the coarse ``TERRA`` used as the key in
    the R-077 / R-078 / application lookup tables. Terra split phase 2 emits the
    first-class ``TERRA_H`` / ``TERRA_V`` product families; those tables are still
    keyed by coarse ``TERRA``, so normalize ONLY for the lookup. The mechanical-fit
    report keeps displaying the split family (``entry.product_family``)."""
    return "TERRA" if product_family in ("TERRA_H", "TERRA_V") else product_family


@dataclass(frozen=True)
class FitCheck:
    """One directional fit verdict (width or height)."""

    dimension: Literal["width", "height"]
    verdict: FitVerdict
    casing_dimension: float | None  # the casing W/H used (or None if unresolved)
    available: float | None  # casing dim (halved for VENTUM+) minus clearance
    required: float | None  # the coil basis value (FL/OAL/FH/CH)
    margin: float | None  # available - required (>= 0 => PASS)
    basis: str  # which coil value was the requirement: FL | OAL | FH | CH
    clearance: float | None  # the subtracted clearance from R-078
    half: bool  # casing dim was halved (VENTUM+ stacked construction)
    detail: str  # English explanation / evidence
    review_required: bool


@dataclass(frozen=True)
class CoilFitResult:
    """Per-coil mechanical fit result (width + height)."""

    coil_type: str
    product_family: str
    size_class: str | None
    width: FitCheck
    height: FitCheck
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class DrainPanColumnFit:
    """Pair-CD fit against ONE drain-pan/install width column."""

    column: str  # coil_module_only | with_access | install_width | drain_pan_width
    width: float
    verdict: DrainPanVerdict  # PASS iff combined_cd < width (strict)
    combined_cd: float | None  # this_cd + partner_cd
    margin: float | None  # width - combined_cd (> 0 => PASS)
    detail: str


@dataclass(frozen=True)
class DrainPanFitResult:
    """INSTALL FIT for a coil pair sharing one drain pan (DX+HGRH / CWC+HWC)."""

    verdict: DrainPanVerdict  # aggregate over evaluated basis columns
    product_family: str
    unit_size: str | None
    this_cd: float | None
    partner_cd: float | None
    partner_tag: str | None
    columns: tuple[DrainPanColumnFit, ...]
    review_required: bool
    detail: str
    evidence_refs: tuple[str, ...]


def _drain_pan_row(
    product_family: str, unit_size: str | None, drain_pan_option: str | None
) -> dict | None:
    """Look up the R-077 drain-pan/install width row.

    TERRA is keyed by the drain-pan OPTION (D1/D2/D3), not unit size; every other
    family is keyed by unit size. Returns ``None`` when the key is absent (Terra V
    is TBD, Terra H C without an option, or an unknown size).
    """
    lookup = _rule_index()[_R077]["lookup"]
    # Terra V FIRST, and inside this helper rather than at either call site. Both callers
    # (`_install_widths` for the .xlsx, `evaluate_drain_pan_fit` for the report) reach the
    # R-077 table through here, so a guard placed in one of them leaves the other open —
    # and the checklist path is the dangerous one, because its number is WRITTEN to the
    # workbook that ships with the order.
    #
    # R-077's `TERRA|D1..D3` rows are Terra **H** widths. Terra V's pan is keyed by unit
    # SIZE and that data is still TBD, so there is nothing to look up — and its model code
    # does carry a two-digit token at the D-option position, which is exactly why the
    # refusal has to be explicit rather than relying on the option coming back empty.
    if product_family == ProductFamily.TERRA_V.value:
        return None
    if _coarse_terra_family(product_family) == ProductFamily.TERRA.value:
        if not drain_pan_option:
            return None
        return lookup.get(f"TERRA|{drain_pan_option}")
    if not unit_size:
        return None
    return lookup.get(f"{product_family}|{unit_size}")


def _fit_clearance_row(
    coil_type: str, product_family: str, size_class: str | None
) -> dict | None:
    """Look up the R-078 clearance row for ``coil_type``/family/size_class.

    NOVA splits on the R-075 size_class (NOVA_1IN/NOVA_2IN); every other family
    is keyed by the family token directly. Returns ``None`` when the key is
    absent (e.g. NOVA without a resolved size_class) so the caller can degrade to
    CANNOT_EVALUATE.
    """
    if product_family == ProductFamily.NOVA.value:
        if not size_class:
            return None
        cls = size_class
    else:
        cls = _coarse_terra_family(product_family)
    return _rule_index()[_R078]["lookup"].get(f"{coil_type}|{cls}")


def _evaluate_dimension(
    *,
    dimension: Literal["width", "height"],
    casing_dimension: float | None,
    clearance: float,
    half: bool,
    basis: str,
    required: float | None,
    review_required: bool,
) -> FitCheck:
    """Compute one directional verdict: PASS iff (available - required) >= 0."""
    if casing_dimension is None:
        return FitCheck(
            dimension=dimension,
            verdict="CANNOT_EVALUATE",
            casing_dimension=None,
            available=None,
            required=required,
            margin=None,
            basis=basis,
            clearance=clearance,
            half=half,
            detail=(
                f"casing {dimension} unresolved (needs product family + "
                "application + unit size via R-074) — cannot evaluate fit"
            ),
            review_required=True,
        )
    available = round(casing_dimension / 2 - clearance, 4) if half else round(
        casing_dimension - clearance, 4
    )
    casing_expr = (
        f"{casing_dimension}/2" if half else f"{casing_dimension}"
    )
    if required is None:
        return FitCheck(
            dimension=dimension,
            verdict="CANNOT_EVALUATE",
            casing_dimension=casing_dimension,
            available=available,
            required=None,
            margin=None,
            basis=basis,
            clearance=clearance,
            half=half,
            detail=(
                f"{basis} unresolved — available {available} = {casing_expr} - "
                f"{clearance}, but no {basis} to compare against"
            ),
            review_required=True,
        )
    margin = round(available - required, 4)
    verdict: FitVerdict = "PASS" if margin >= 0 else "FAIL"
    return FitCheck(
        dimension=dimension,
        verdict=verdict,
        casing_dimension=casing_dimension,
        available=available,
        required=required,
        margin=margin,
        basis=basis,
        clearance=clearance,
        half=half,
        detail=(
            f"available {available} = {casing_expr} - {clearance}; "
            f"required {basis}={required}; margin {margin} "
            f"({'fits' if margin >= 0 else 'DOES NOT FIT'})"
        ),
        review_required=review_required,
    )


def evaluate_coil_fit(
    *,
    coil_type: str,
    product_family: str,
    size_class: str | None,
    casing_width: float | None,
    casing_height: float | None,
    fl: float | None,
    fh: float | None,
    ch: float | None,
    oal: float | None,
) -> CoilFitResult:
    """Evaluate WIDTH and HEIGHT fit for a single coil.

    ``coil_type`` / ``product_family`` are the engine enum string values
    (``DX``/``HGRH``/``CWC``/``HWC`` and ``NOVA``/``TERRA``/``VENTUM_H``/
    ``VENTUM_PLUS``). ``size_class`` is the R-075 token for NOVA (else ``None``).
    Casing dims and FH/FL/CH/OAL are the resolved review-aid values (or ``None``
    when unresolved upstream).
    """
    evidence = tuple(_rule_index()[_R078]["evidence_refs"])
    row = _fit_clearance_row(coil_type, product_family, size_class)
    if row is None:
        reason = (
            f"no R-078 clearance row for {coil_type}|"
            f"{size_class or product_family} — fit cannot be evaluated"
        )
        blocked = FitCheck(
            dimension="width",
            verdict="CANNOT_EVALUATE",
            casing_dimension=casing_width,
            available=None,
            required=None,
            margin=None,
            basis="FL",
            clearance=None,
            half=False,
            detail=reason,
            review_required=True,
        )
        return CoilFitResult(
            coil_type=coil_type,
            product_family=product_family,
            size_class=size_class,
            width=blocked,
            height=FitCheck(
                dimension="height",
                verdict="CANNOT_EVALUATE",
                casing_dimension=casing_height,
                available=None,
                required=None,
                margin=None,
                basis="CH",
                clearance=None,
                half=False,
                detail=reason,
                review_required=True,
            ),
            evidence_refs=evidence,
        )

    width_basis: str = row["w_basis"]
    height_basis: str = row["h_basis"]
    width = _evaluate_dimension(
        dimension="width",
        casing_dimension=casing_width,
        clearance=row["w_sub"],
        half=False,
        basis=width_basis,
        required=fl if width_basis == "FL" else oal,
        review_required=True,
    )
    height = _evaluate_dimension(
        dimension="height",
        casing_dimension=casing_height,
        clearance=row["h_sub"],
        half=bool(row["h_half"]),
        basis=height_basis,
        required=fh if height_basis == "FH" else ch,
        review_required=True,
    )
    return CoilFitResult(
        coil_type=coil_type,
        product_family=product_family,
        size_class=size_class,
        width=width,
        height=height,
        evidence_refs=evidence,
    )


@dataclass(frozen=True)
class CoilFitEntry:
    """Per-coil fit entry in the report (width/height now, drain_pan after pairing)."""

    tag: str | None
    coil_type: str
    product_family: str
    unit_size: str
    size_class: str | None
    casing_width: float | None
    casing_height: float | None
    fh: float | None
    fl: float | None
    ch: float | None
    oal: float | None
    cd: float | None
    width: FitCheck | None
    height: FitCheck | None
    drain_pan: "DrainPanFitResult | None"
    partner_tag: str | None
    note: str | None  # set when the coil could not be evaluated at all


@dataclass(frozen=True)
class MechanicalFitReport:
    """Full stability report for 1..N coils (per-coil + drain-pan pairs)."""

    coils: tuple[CoilFitEntry, ...]
    review_required: bool = True
    # Safety contract — a review aid, never a production sign-off.
    export_allowed: bool = False
    production_drawing_approval_claimed: bool = False


def _slot_number(slots: dict, key: str) -> float | None:
    value = slots.get(key)
    return value if isinstance(value, (int, float)) else None


def build_coil_fit(
    *,
    tag: str | None,
    coil_type: str,
    product_type: str,
    unit_size: str,
    finned_height: float | None,
    finned_length: float | None,
    rows: int | None = None,
    feeds: int | None = None,
    circuits: int | None = None,
    suction_conn_size: float | None = None,
    conn_size: float | None = None,
    qty_conn_per_header: int | None = None,
    application: str | None = None,
) -> CoilFitEntry:
    """Resolve one coil's casing dims + CD/CH/OAL via the engine, then width/height fit.

    Re-runs the pure engine (``prepopulate``) and slot layer (``build_drawing_slots``)
    — no I/O — so the report composes resolved values rather than recomputing
    geometry. ``drain_pan``/``partner_tag`` are filled later by the pairing pass.
    """
    # Local imports avoid an import cycle (services -> compatibility is one-way).
    from coilforge.services.direct_coil_drawing_pipeline import (
        build_drawing_slots,
        build_header_request,
    )
    from coilforge.services.header_prepopulate_engine import prepopulate

    try:
        request = build_header_request(
            coil_type=coil_type,
            product_type=product_type,
            unit_size=unit_size,
            rows=rows,
            feeds=feeds,
            circuits=circuits,
            suction_conn_size=suction_conn_size,
            conn_size=conn_size,
            qty_conn_per_header=qty_conn_per_header,
        )
        family = request.product_type.value
        engine_coil_type = request.type_of_coil.value
        # DX/HGRH/CWC application is deterministic per family (see _DX_CWC_APPLICATION);
        # derive it so R-074 casing dims resolve. HWC is ambiguous -> left as given.
        if application is None and engine_coil_type in ("DX", "HGRH", "CWC"):
            application = _DX_CWC_APPLICATION.get(_coarse_terra_family(family))
        if application is not None:
            request = request.model_copy(update={"application": application})
        response = prepopulate(request)
    except Exception as exc:  # noqa: BLE001 — never raise into the report
        return CoilFitEntry(
            tag=tag, coil_type=coil_type, product_family=product_type,
            unit_size=unit_size, size_class=None, casing_width=None,
            casing_height=None, fh=finned_height, fl=finned_length, ch=None,
            oal=None, cd=None, width=None, height=None, drain_pan=None,
            partner_tag=None, note=f"could not run engine: {exc}",
        )

    def engine_value(field: str):  # type: ignore[no-untyped-def]
        if field in response.values:
            return response.values[field].value
        if field in response.suggestions:
            return response.suggestions[field].value
        return None

    casing_width = engine_value("casing_width")
    casing_height = engine_value("casing_height")
    size_class = engine_value("size_class")

    slots, _ = build_drawing_slots(
        coil_type=coil_type,
        product_type=product_type,
        unit_size=unit_size,
        rows=rows,
        feeds=feeds,
        circuits=circuits,
        suction_conn_size=suction_conn_size,
        conn_size=conn_size,
        qty_conn_per_header=qty_conn_per_header,
        finned_height=finned_height,
        finned_length=finned_length,
    )
    ch = _slot_number(slots, "slot.CH")
    oal = _slot_number(slots, "slot.OAL")
    cd = _slot_number(slots, "slot.CD")
    fh = _slot_number(slots, "slot.FH") if finned_height is None else finned_height
    fl = _slot_number(slots, "slot.FL") if finned_length is None else finned_length

    fit = evaluate_coil_fit(
        coil_type=engine_coil_type,
        product_family=family,
        size_class=size_class,
        casing_width=casing_width,
        casing_height=casing_height,
        fl=fl, fh=fh, ch=ch, oal=oal,
    )
    return CoilFitEntry(
        tag=tag, coil_type=engine_coil_type, product_family=family,
        unit_size=unit_size, size_class=size_class, casing_width=casing_width,
        casing_height=casing_height, fh=fh, fl=fl, ch=ch, oal=oal, cd=cd,
        width=fit.width, height=fit.height, drain_pan=None, partner_tag=None,
        note=None,
    )


def build_mechanical_fit_report(
    coils: list[dict], *, installed_on_drain_pan: bool = False
) -> MechanicalFitReport:
    """Per-coil width/height fit for every coil, then drain-pan fit for each pair.

    Each ``coils`` entry: ``{tag, coil_type, product_type, unit_size,
    finned_height, finned_length, circuits?, suction_conn_size?, conn_size?,
    qty_conn_per_header?, application?, drain_pan_option?}``. Coils missing
    product_type/unit_size are reported with a ``note`` rather than dropped.
    Pairing (DX+HGRH / CWC+HWC by tag sequence) is resolved across the whole list
    so the drain-pan INSTALL FIT evaluates for real when a partner is present.
    """
    from coilforge.submittal.pdf_intake import drain_pan_partner_tag

    entries: list[CoilFitEntry] = []
    for coil in coils:
        product_type = coil.get("product_type")
        unit_size = coil.get("unit_size")
        coil_type = coil.get("coil_type")
        if not (product_type and unit_size and coil_type):
            entries.append(
                CoilFitEntry(
                    tag=coil.get("tag"), coil_type=coil_type or "?",
                    product_family=product_type or "?", unit_size=unit_size or "?",
                    size_class=None, casing_width=None, casing_height=None,
                    fh=coil.get("finned_height"), fl=coil.get("finned_length"),
                    ch=None, oal=None, cd=None, width=None, height=None,
                    drain_pan=None, partner_tag=None,
                    note="needs coil type + product line + unit size to evaluate fit",
                )
            )
            continue
        entries.append(
            build_coil_fit(
                tag=coil.get("tag"),
                coil_type=coil_type,
                product_type=product_type,
                unit_size=unit_size,
                finned_height=coil.get("finned_height"),
                finned_length=coil.get("finned_length"),
                rows=coil.get("rows"),
                feeds=coil.get("feeds"),
                circuits=coil.get("circuits"),
                suction_conn_size=coil.get("suction_conn_size"),
                conn_size=coil.get("conn_size"),
                qty_conn_per_header=coil.get("qty_conn_per_header"),
                application=coil.get("application"),
            )
        )

    # Pairing pass: drain-pan INSTALL FIT for each coil that has a partner.
    all_tags = [c.get("tag") for c in coils if c.get("tag")]
    option_by_tag = {c.get("tag"): c.get("drain_pan_option") for c in coils}
    # Carried alongside the option, not derived here: the reason belongs to whoever read
    # the model code, and re-deriving it in this module would be a second interpretation
    # that could disagree with the first.
    option_reason_by_tag = {
        c.get("tag"): str(c.get("drain_pan_option_reason") or "") for c in coils
    }
    cd_by_tag = {e.tag: e.cd for e in entries if e.tag}
    size_by_tag = {e.tag: e.unit_size for e in entries if e.tag}
    paired: list[CoilFitEntry] = []
    for entry in entries:
        partner = drain_pan_partner_tag(entry.tag, all_tags) if entry.tag else None

        # A DX+HGRH / CWC+HWC pair is two coils in the SAME unit, so they must report the
        # same unit size. When they do not, the detection is wrong for at least one of
        # them -- and unit size selects the R-074 casing AND the R-077 pan width, so every
        # verdict downstream is computed from a size we have just decided not to trust.
        # Degrade all three rather than let a confident PASS/FAIL stand on it. The note
        # states BOTH sizes and does not pick one: the system cannot know which detection
        # failed, and quietly choosing would be the guess this guard exists to prevent.
        partner_size = size_by_tag.get(partner) if partner else None
        size_conflict = bool(
            partner and partner_size and entry.unit_size and partner_size != entry.unit_size
        )
        if size_conflict:
            note = (
                f"{entry.tag} detected as unit size {entry.unit_size} but its drain-pan "
                f"partner {partner} detected as {partner_size}. A DX+HGRH / CWC+HWC pair "
                "shares one unit, so one of these is wrong — check the unit model code on "
                "both coils. Fit verdicts are withheld because casing and drain-pan widths "
                "are both keyed by unit size."
            )
            # The card already shows `note` once, as its own banner. Repeating the full
            # sentence as the detail of all three checks turned one warning into four
            # copies of itself — noise that buries the numbers underneath. The per-check
            # line says only what is specific to it and points at the banner.
            short = f"withheld — unit size disputed with {partner} (see note above)"
            paired.append(
                CoilFitEntry(
                    **{
                        **entry.__dict__,
                        "width": _cannot_evaluate_fit(entry.width, short),
                        "height": _cannot_evaluate_fit(entry.height, short),
                        # The original plan degraded width/height only. The drain-pan
                        # check reads entry.unit_size through the SAME lookup, so leaving
                        # it live would keep a PASS/FAIL standing on the distrusted size.
                        "drain_pan": _cannot_evaluate_drain_pan(
                            entry, partner, short
                        ),
                        "partner_tag": partner,
                        "note": note if not entry.note else f"{entry.note} {note}",
                    }
                )
            )
            continue

        drain_pan = evaluate_drain_pan_fit(
            product_family=entry.product_family,
            unit_size=entry.unit_size,
            this_cd=entry.cd,
            partner_cd=cd_by_tag.get(partner) if partner else None,
            partner_tag=partner,
            installed_on_drain_pan=installed_on_drain_pan,
            drain_pan_option=option_by_tag.get(entry.tag),
            drain_pan_option_reason=option_reason_by_tag.get(entry.tag, ""),
        )
        paired.append(
            CoilFitEntry(
                **{**entry.__dict__, "drain_pan": drain_pan, "partner_tag": partner}
            )
        )
    return MechanicalFitReport(coils=tuple(paired))


def _cannot_evaluate_fit(original: "FitCheck | None", reason: str) -> "FitCheck | None":
    """Degrade a width/height verdict to CANNOT_EVALUATE, keeping its inputs visible.

    ``replace`` rather than a rebuilt constructor: FitCheck carries casing/clearance/half
    provenance that the engineer still wants to see while chasing the size conflict, and a
    hand-listed constructor would silently drop whichever field is added next. Only the
    verdict, the margin (meaningless without a trusted casing dim) and the detail change.
    """
    if original is None:
        return None
    return replace(
        original, verdict="CANNOT_EVALUATE", margin=None, review_required=True,
        detail=reason,
    )


def _cannot_evaluate_drain_pan(
    entry: CoilFitEntry, partner_tag: str | None, reason: str
) -> DrainPanFitResult:
    return DrainPanFitResult(
        verdict="CANNOT_EVALUATE",
        product_family=entry.product_family,
        unit_size=entry.unit_size,
        this_cd=entry.cd,
        partner_cd=None,
        partner_tag=partner_tag,
        columns=(),
        review_required=True,
        detail=reason,
        evidence_refs=tuple(_rule_index()[_R077]["evidence_refs"]),
    )


def mechanical_fit_report_dict(report: MechanicalFitReport) -> dict[str, Any]:
    """JSON-serializable view of the report (frozen dataclasses -> dicts/lists)."""
    return asdict(report)


def _basis_columns(product_family: str, row: dict) -> list[str]:
    """Which width column(s) the INSTALL FIT compares against, per family.

    VENTUM+ compares the pair-CD against ``install_width`` (CHK HWC!C38 /
    HGRH!C70 branch); its ``drain_pan_width`` is informational. Nova/Ventum H
    surface BOTH ``coil_module_only`` and ``with_access`` (John). Terra uses the
    single ``drain_pan_width``.
    """
    if product_family in VENTUM_PLUS_CLASS_VALUES:
        cols = ["install_width"]
        if "drain_pan_width" in row:
            cols.append("drain_pan_width")
        return cols
    if "coil_module_only" in row or "with_access" in row:
        return [c for c in ("coil_module_only", "with_access") if c in row]
    return [c for c in ("drain_pan_width",) if c in row]


def evaluate_drain_pan_fit(
    *,
    product_family: str,
    unit_size: str | None,
    this_cd: float | None,
    partner_cd: float | None,
    partner_tag: str | None,
    installed_on_drain_pan: bool,
    drain_pan_option: str | None = None,
    drain_pan_option_reason: str = "",
) -> DrainPanFitResult:
    """INSTALL FIT for a coil pair sharing one drain pan.

    ``drain_pan_option_reason`` is the model-code reader's own account of why there is (or
    is not) an option for THIS coil. It is used verbatim when the option is missing,
    because this function cannot reconstruct it: "no option" has several causes and they
    send the engineer to different places. Without it the card falls back to a generic
    "provide the drain-pan option", which on a multi-unit submittal is an instruction that
    cannot be followed — the option it asks for is not printed anywhere in the document.

    PASS iff ``this_cd + partner_cd < width`` (strict, per the CHK INSTALL FIT).
    Only meaningful when the coil is installed on a shared drain pan AND a partner
    coil (with a resolved CD) was found; otherwise ``NOT_APPLICABLE`` /
    ``CANNOT_EVALUATE``. Never guesses a missing width or CD.
    """
    evidence = tuple(_rule_index()[_R077]["evidence_refs"])

    def result(verdict, columns, detail):  # type: ignore[no-untyped-def]
        return DrainPanFitResult(
            verdict=verdict,
            product_family=product_family,
            unit_size=unit_size,
            this_cd=this_cd,
            partner_cd=partner_cd,
            partner_tag=partner_tag,
            columns=tuple(columns),
            review_required=True,
            detail=detail,
            evidence_refs=evidence,
        )

    if not installed_on_drain_pan:
        return result(
            "NOT_APPLICABLE", [], "coil is not installed on a shared drain pan — "
            "INSTALL FIT skipped"
        )
    if partner_cd is None or partner_tag is None:
        return result(
            "CANNOT_EVALUATE", [],
            "no paired coil (DX+HGRH / CWC+HWC) with a resolved CD found — "
            "cannot evaluate shared drain-pan fit",
        )
    if this_cd is None:
        return result(
            "CANNOT_EVALUATE", [], "this coil's CD is unresolved — cannot evaluate "
            "shared drain-pan fit"
        )
    row = _drain_pan_row(product_family, unit_size, drain_pan_option)
    if row is None:
        # Terra V is checked BEFORE the generic Terra branch. It also satisfies
        # "coarse TERRA and no option", so the shared message would tell the engineer to
        # supply a D1/D2/D3 option — advice that can never be acted on, because Terra V's
        # pan is size-keyed and no option would change the outcome. A permanently
        # unfollowable instruction is worse than saying nothing.
        if product_family == ProductFamily.TERRA_V.value:
            reason = (
                "Terra V drain-pan width is keyed by unit size, and the Install sheet has "
                "no Terra V rows yet — blocked pending that data. It deliberately does NOT "
                "borrow the Terra H D1/D2/D3 widths"
            )
        elif _coarse_terra_family(product_family) == ProductFamily.TERRA.value and not drain_pan_option:
            # Prefer the reader's account. "No option" is not one situation: the code may
            # be absent entirely, or belong to a DIFFERENT unit in the same submittal (in
            # which case we deliberately refuse to borrow it), or disagree with a second
            # code for the same size. Only the reader knows which, and the generic text
            # below reads as "supply the option" in every one of them — advice that is
            # actionable in the first case and impossible in the others.
            reason = drain_pan_option_reason.strip() or (
                "Terra drain-pan width is keyed by option D1/D2/D3, which was not read "
                "from the unit model code — provide the drain-pan option to evaluate"
            )
            if drain_pan_option_reason.strip():
                reason = f"Terra drain-pan width is keyed by option D1/D2/D3: {reason}"
        else:
            reason = (
                f"no drain-pan width for {product_family}|{unit_size} "
                "(e.g. Terra V is TBD in the Install sheet) — blocked"
            )
        return result("CANNOT_EVALUATE", [], reason)

    combined = round(this_cd + partner_cd, 4)
    columns: list[DrainPanColumnFit] = []
    for col in _basis_columns(product_family, row):
        width = row[col]
        margin = round(width - combined, 4)
        verdict: DrainPanVerdict = "PASS" if margin > 0 else "FAIL"
        columns.append(
            DrainPanColumnFit(
                column=col,
                width=width,
                verdict=verdict,
                combined_cd=combined,
                margin=margin,
                detail=(
                    f"{col}={width}; this_CD {this_cd} + partner_CD {partner_cd} "
                    f"= {combined}; margin {margin} "
                    f"({'fits' if margin > 0 else 'DOES NOT FIT'})"
                ),
            )
        )

    # Aggregate verdict over the basis columns: PASS only if every column passes.
    # (Ventum+ drain_pan_width is informational but still folded in conservatively.)
    if any(c.verdict == "FAIL" for c in columns):
        agg: DrainPanVerdict = "FAIL"
    elif columns:
        agg = "PASS"
    else:
        agg = "CANNOT_EVALUATE"
    detail = (
        f"partner {partner_tag}: combined CD {combined} vs "
        + ", ".join(f"{c.column} {c.width} ({c.verdict})" for c in columns)
        if columns
        else "no width column available"
    )
    return result(agg, columns, detail)
