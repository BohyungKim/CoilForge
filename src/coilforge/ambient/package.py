"""Pure builder for a submittal -> Ambient "performance page + drawing" package (no I/O).

Transcribes the performance numbers ALREADY extracted onto a baseline
``SubmittalCoilCandidate`` into an Ambient-sendable per-coil sheet, plus the
Coil-Utilities acceptance band for context. The drawing itself is attached by the I/O
layer (Track B generated SVG, or an EZ Coil selection drawing) — this module is drawing-
agnostic and only carries the fields the caller fills in.

Boundary contract (load-bearing):
- Transcription only. Every value is copied verbatim from an existing ``FieldValue``;
  nothing is calculated or selected. The one derived artifact — the acceptance band —
  is a pure table lookup over ``coil_utilities.ranges`` (the same primitives the existing
  ``range_provider`` uses), never a performance calculation. So this stays outside the
  gated selection-calculation engine (AGENTS.md).
- Never invent. An absent essential field is surfaced in ``missing_fields``; it is never
  defaulted or guessed. Present values keep their review posture (review aid only).
- No imports of the header/selection engine, ``drawing_param_resolver``, or
  ``direct_coil_drawing_pipeline`` — only ``FieldValue`` reads and ranges lookups.

Mirrors ``ambient/model.py``'s frozen-dataclass + ``as_dict()`` style. Review aid only:
``export_allowed=False``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from coilforge.coil_utilities.ranges import kit_for_btuh, ranges_for_kit, tons_for_kit
from coilforge.submittal.candidate import SubmittalCoilCandidate
from coilforge.submittal.pdf_intake import PDF_INTAKE_FIELD_RULES, coil_category_of_tag

# Groups whose keys are performance/spec numbers worth transcribing onto the Ambient
# sheet. Identity/config/drawing groups are deliberately excluded so a performance page
# never renders ``product_type``/``coil_hand``/valve/VRV or a drawing dimension as a
# "performance line": ``tag``/``product_type``/``coil_type``/``header_type`` are top-level
# candidate attributes (not in these group dicts), and ``connections`` /
# ``manufacturing_options`` / ``drawing_parameters`` are simply not listed here.
_ALLOWED_GROUPS: frozenset[str] = frozenset(
    {"geometry", "airside_conditions", "refrigerant_conditions", "materials_construction", "performance"}
)
# Keys inside an allowed group that are NOT performance data.
_EXCLUDED_KEYS: frozenset[tuple[str, str]] = frozenset({("geometry", "airflow_direction")})

_HGRH_CATEGORIES: frozenset[str] = frozenset({"HGRH COIL"})

# Design capacity may arrive under either label depending on the submittal's source
# wording; both are real populated keys (see PDF_INTAKE_FIELD_RULES). Read whichever is
# present, preferring the cooling-capacity label the rest of the ambient module uses.
_CAPACITY_KEYS: tuple[str, ...] = ("nominal_cooling_capacity_mbh", "total_capacity_mbh")

# The headline duty-point/envelope fields shown as a compact ``targets`` summary and the
# ones whose absence is genuinely "missing" (vs a cross-category field that is merely
# not-applicable, e.g. a fluid flow on a DX coil — those stay out of ``missing_fields``).
_ESSENTIAL_FIELDS: tuple[tuple[str, str], ...] = (
    ("geometry", "rows_deep"),
    ("geometry", "fins_per_inch"),
    ("geometry", "finned_height"),
    ("geometry", "finned_length"),
    ("airside_conditions", "total_air_flow_cfm"),
    ("airside_conditions", "entering_dry_bulb_f"),
)


def _performance_field_specs() -> tuple[tuple[str, str, str | None], ...]:
    """``(group, key, unit)`` for every transcribable performance field, derived from the
    real submittal field-rule table so the surface stays in sync with what the parser
    actually produces (invents no key). Deduped by ``(group, key)`` with first occurrence
    winning display order."""
    specs: list[tuple[str, str, str | None]] = []
    seen: set[tuple[str, str]] = set()
    for rule in PDF_INTAKE_FIELD_RULES.values():
        group = rule.target
        if group not in _ALLOWED_GROUPS:
            continue
        ident = (group, rule.target_key)
        if ident in _EXCLUDED_KEYS or ident in seen:
            continue
        seen.add(ident)
        specs.append((group, rule.target_key, rule.unit))
    return tuple(specs)


_PERFORMANCE_FIELDS: tuple[tuple[str, str, str | None], ...] = _performance_field_specs()


def _label(key: str) -> str:
    return key.replace("_", " ").strip().title()


@dataclass(frozen=True)
class PerformanceLine:
    """One transcribed performance number. Always review_required (a vendor-facing target
    the engineer must confirm), never an approved value."""

    label: str
    group: str
    key: str
    value: Any
    unit: str | None
    review_required: bool = True


@dataclass(frozen=True)
class AmbientCoilPage:
    """One coil's Ambient-sendable performance page + its drawing slot (filled by I/O)."""

    tag: str | None
    category: str | None
    lines: tuple[PerformanceLine, ...] = ()
    targets: dict[str, Any] = field(default_factory=dict)
    acceptance_band: dict[str, Any] | None = None
    missing_fields: tuple[str, ...] = ()
    drawing_source: str | None = None  # "ez_coil" | "track_b_generated" | None
    drawing_svg: str | None = None
    drawing_omitted_reason: str | None = None


@dataclass(frozen=True)
class AmbientPackage:
    """Project-level submittal->Ambient package — a review aid, never an export."""

    coils: tuple[AmbientCoilPage, ...] = ()
    warnings: tuple[str, ...] = ()
    # Safety contract — mirrors every other CoilForge result payload.
    export_allowed: bool = False
    production_drawing_approval_claimed: bool = False
    review_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        """JSON-friendly payload for the web layer."""
        return {
            "coils": [
                {
                    "tag": c.tag,
                    "category": c.category,
                    "performance_lines": [asdict(line) for line in c.lines],
                    "targets": c.targets,
                    "acceptance_band": c.acceptance_band,
                    "missing_fields": list(c.missing_fields),
                    "drawing": {
                        "source": c.drawing_source,
                        "svg": c.drawing_svg,
                        "omitted_reason": c.drawing_omitted_reason,
                    },
                }
                for c in self.coils
            ],
            "warnings": list(self.warnings),
            "export_allowed": self.export_allowed,
            "production_drawing_approval_claimed": self.production_drawing_approval_claimed,
            "review_required": self.review_required,
        }


def _fv(cand: SubmittalCoilCandidate, group: str, key: str):
    return getattr(cand, group, {}).get(key)


def _capacity_mbh(cand: SubmittalCoilCandidate) -> float | None:
    for key in _CAPACITY_KEYS:
        fv = _fv(cand, "performance", key)
        if fv is not None and fv.value is not None:
            try:
                return float(fv.value)
            except (TypeError, ValueError):
                return None
    return None


def _circuits(cand: SubmittalCoilCandidate) -> tuple[int, bool]:
    """``(circuits, assumed)``. ``assumed=True`` when no parseable circuit count was found —
    the band then assumes 1 circuit, which is surfaced (never a silent scale error). The
    acceptance band flows to an external supplier, so this assumption must be visible."""
    fv = _fv(cand, "geometry", "circuits")
    if fv is not None and fv.value:
        try:
            return max(1, int(fv.value)), False
        except (TypeError, ValueError):
            pass
    return 1, True


def _acceptance_band(cand: SubmittalCoilCandidate, category: str | None) -> dict[str, Any] | None:
    """Kit acceptance band from the design capacity — a review reference, never invented.

    Pure table lookup over ``coil_utilities.ranges`` (same primitives as ``range_provider``);
    returns ``None`` when capacity or the chart entry is absent (no fabricated band)."""
    cap = _capacity_mbh(cand)
    if cap is None:
        return None
    circuits, circuits_assumed = _circuits(cand)
    band = "heating" if category in _HGRH_CATEGORIES else "cooling"
    kit = kit_for_btuh(cap * 1000.0, circuits, band=band)
    if kit is None:
        return None
    r = ranges_for_kit(kit, circuits)
    if r is None:
        return None
    lo, hi = (
        (r.heating_min_mbh, r.heating_max_mbh) if band == "heating" else (r.cooling_min_mbh, r.cooling_max_mbh)
    )
    return {
        "ekexva_kit": f"EKEXVA{kit}U",
        "nominal_tons": tons_for_kit(kit),
        "capacity_band_mbh": [round(lo, 1), round(hi, 1)],
        "coil_volume_band_cuin": [r.volume_min_cuin, r.volume_max_cuin],
        "band_basis": band,
        # The band scales by circuits; if the submittal never stated a circuit count the
        # band assumes 1 — surfaced so a wrong scale can't slip out to Ambient silently.
        "circuits": circuits,
        "circuits_assumed": circuits_assumed,
    }


def _targets(cand: SubmittalCoilCandidate) -> dict[str, Any]:
    """Compact headline duty-point/envelope summary (a subset of the full lines) that an
    Ambient RFQ header shows first. Present fields only; capacity under either label."""
    out: dict[str, Any] = {}
    for group, key in _ESSENTIAL_FIELDS:
        fv = _fv(cand, group, key)
        if fv is not None and fv.value is not None:
            out[key] = {"value": fv.value, "unit": fv.unit}
    for key in _CAPACITY_KEYS:
        fv = _fv(cand, "performance", key)
        if fv is not None and fv.value is not None:
            out["capacity_mbh"] = {"value": fv.value, "unit": fv.unit or "MBH"}
            break
    return out


def _missing_essentials(cand: SubmittalCoilCandidate) -> tuple[str, ...]:
    """Essential headline fields that are genuinely absent (never lists a cross-category
    not-applicable field, so the callout stays meaningful rather than noisy)."""
    missing: list[str] = []
    for group, key in _ESSENTIAL_FIELDS:
        fv = _fv(cand, group, key)
        if fv is None or fv.value is None:
            missing.append(f"{group}.{key}")
    if _capacity_mbh(cand) is None:
        missing.append("performance.capacity_mbh")
    return tuple(missing)


def build_ambient_package(baseline: list[SubmittalCoilCandidate]) -> AmbientPackage:
    """Per-coil Ambient-sendable performance page (transcription + acceptance band).

    Drawing slots are left unset here; the I/O layer fills ``drawing_*``. A coil with no
    tag is kept (its performance lines are still useful) but gets no targets/band — that
    is surfaced as a warning, never a silent drop."""
    coils: list[AmbientCoilPage] = []
    warnings: list[str] = []
    for cand in baseline:
        tag = cand.tag.value if cand.tag is not None else None
        tag = str(tag) if tag not in (None, "") else None
        category = coil_category_of_tag(tag) if tag else None

        lines: list[PerformanceLine] = []
        for group, key, unit in _PERFORMANCE_FIELDS:
            fv = _fv(cand, group, key)
            if fv is not None and fv.value is not None:
                lines.append(
                    PerformanceLine(
                        label=_label(key),
                        group=group,
                        key=key,
                        value=fv.value,
                        unit=fv.unit or unit,
                    )
                )

        if tag is None:
            warnings.append(
                f"Coil candidate {cand.candidate_id!r} has no tag — targets and acceptance "
                f"band omitted (review required)."
            )

        coils.append(
            AmbientCoilPage(
                tag=tag,
                category=category,
                lines=tuple(lines),
                targets=_targets(cand) if tag else {},
                acceptance_band=_acceptance_band(cand, category) if tag else None,
                missing_fields=_missing_essentials(cand),
            )
        )

        for note in cand.notes:
            low = note.lower()
            if low.startswith("ambient") or "review" in low:
                warnings.append(note)

    return AmbientPackage(coils=tuple(coils), warnings=tuple(dict.fromkeys(warnings)))
