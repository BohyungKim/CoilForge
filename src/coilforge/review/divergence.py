"""Known-divergence registry: John's rulings on checklist-vs-engine disagreements.

A divergence is a dimension where the Coil Checklist's Excel formula and CoilForge's
engine disagree. Phase C put that disagreement on the drawing-parameter row in red;
this module lets a ruling be recorded ONCE so the same known gap stops re-asking.

**What a ruling does NOT do.** It never changes a value, never widens the confidence
gate, and never touches ``coil_header_rules.yaml``. It only re-labels the review row —
red ("look at this") becomes amber ("adjudicated, here is why"). The project gate is
deliberately untouched (D5): the ledger's ``gate_verdict`` label must keep one meaning
across the corpus, so a suppression that lowered ``exceptions_K`` would corrupt every
measurement taken before it.

Identity
--------
``divergence_key = (coil_category, product_family, terra_variant, unit_size_scope, slot)``

* ``terra_variant`` is load-bearing: a Terra V ruling must not silence Terra H. Both
  resolve to ``product_family TERRA``, so without this axis they are the same key.
* ``unit_size_scope`` is **declared by John**, not inferred -- ``"*"`` (every size) or a
  specific size token. Machine-inferring the scope from one observation would be exactly
  the never-invent violation the registry exists to prevent.
* ``slot`` keeps its full parity form (``S1``/``O4``), because the header index is
  semantically meaningful -- R-046 rules on Supply 1 and declines Supply 2+.
* **Numbers are NOT in the identity.** CD varies with rows/circuits/conn on every coil, so
  a numeric key would never match twice and the ruling would never apply. The magnitude is
  policed by a ``delta_band`` instead.

The band
--------
``delta = coilforge - checklist``. A ruling suppresses only while the observed delta stays
inside the band it was granted for. Outside it -- wrong sign, or larger than the band --
the row **re-escalates** rather than staying amber, because a divergence that changed
character is a new question. **The band never widens without a human**: nothing in this
module or the route writes a wider band than the one submitted.

Storage
-------
Two files, both read here:

* ``rules/known_divergences.yaml`` -- the **promoted** registry. Tracked in git; John's
  commit IS the approval step.
* ``outputs/divergence_staging.yaml`` -- the **working** file the HTTP route appends to.
  Gitignored. The route never writes to a tracked path (a concurrent session auto-commits
  this tree), so a ruling made in the browser can never smuggle itself into a commit.

Staging **wins** on a key collision -- it is the more recent human ruling (a re-adjudication
of an already-promoted key lands there). When both sides carry the same key with a DIFFERENT
band, the loader raises a warning onto the annotation: the band decides suppression, so a
non-deterministic band is D5's "suppression corruption" with extra steps.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from coilforge.submittal.coilmaster_drawing_extract import resolve_product_line

_PROMOTED_PATH = Path(__file__).resolve().parents[1] / "rules" / "known_divergences.yaml"
_STAGING_PATH = (
    Path(__file__).resolve().parents[3] / "outputs" / "divergence_staging.yaml"
)

ANY_SIZE = "*"

#: Verdicts a human may record. ``unresolved`` is recorded in the ledger but never enters
#: the registry -- "I looked and could not decide" must not suppress anything.
VERDICTS = ("checklist_wrong", "coilforge_wrong", "both_defensible", "unresolved")

#: Verdicts that produce a registry entry (i.e. that can annotate a row).
REGISTERABLE = ("checklist_wrong", "coilforge_wrong", "both_defensible")

#: How an annotated row should read. ``known_defect`` deliberately stays RED: a ruling of
#: "CoilForge is wrong" is an open bug, and dimming it would hide the one class of
#: divergence that most needs fixing. Only a gap in the OTHER implementation goes amber.
_SEVERITY_BY_VERDICT = {
    "checklist_wrong": "known_gap",
    "both_defensible": "known_gap",
    "coilforge_wrong": "known_defect",
}

_ALLOWED_ENTRY_KEYS = frozenset(
    {
        "id", "coil_category", "product_family", "terra_variant", "unit_size_scope",
        "slot", "verdict", "reason", "evidence_refs", "delta_band", "adjudicated_by",
        "adjudicated_utc", "expires_utc", "status", "rule_proposal",
    }
)


def divergence_enabled() -> bool:
    """Kill switch mirroring ``COILFORGE_MANUAL_FILL`` -- roll the feature back without
    reverting the commit. Off means no annotation and a closed adjudication route."""
    return os.environ.get("COILFORGE_DIVERGENCE", "1").strip() not in ("0", "false", "False")


# --------------------------------------------------------------------------- #
# identity
# --------------------------------------------------------------------------- #
def _norm(value: Any) -> str:
    """Axis token. ``None``/blank -> ``-`` so a missing axis is a real, matchable value
    rather than a wildcard -- a coil whose product line never resolved must not collide
    with a ruling made about a known line."""
    text = str(value or "").strip().upper()
    return text or "-"


def divergence_key(
    coil_category: Any,
    product_family: Any,
    terra_variant: Any,
    unit_size_scope: Any,
    slot: Any,
) -> str:
    """The five identity axes, pipe-joined. Stable string form for the ledger column."""
    return "|".join(
        (
            _norm(coil_category),
            _norm(product_family),
            _norm(terra_variant),
            _norm(unit_size_scope) if unit_size_scope != ANY_SIZE else ANY_SIZE,
            _norm(slot),
        )
    )


def coil_identity(coil: dict[str, Any]) -> tuple[str, str, str, str]:
    """``(coil_category, product_family, terra_variant, unit_size)`` for one checklist coil.

    Resolves the product line through ``resolve_product_line`` -- the SAME helper
    ``build_header_request`` uses -- so the registry axis and the engine's own notion of the
    family can never drift apart. Re-deriving "is this Terra V" locally is how the two would
    disagree on exactly the coils under investigation.

    **The family token here is the SPLIT one** (``TERRA_H`` / ``TERRA_V``), not the coarse
    ``TERRA`` the engine folds back to internally. That is the resolver's raw output since
    the Terra-split Phase 2, and it is what the registry keys on. Note the deliberate
    contrast with ``mechanical_fit``, which normalises back to coarse ``TERRA`` via
    ``_coarse_terra_family`` -- it must, because R-077/R-078 are keyed ``TERRA|...``. Nothing
    keys this registry but this registry, so it stays on the finer token: a ruling naming
    ``TERRA_V`` cannot then be read as covering Terra H by a later coarsening.
    """
    family, variant = resolve_product_line(
        coil.get("product_label") or coil.get("product_type")
    )
    return (
        _norm(coil.get("coil_type") or coil.get("category")),
        _norm(family),
        _norm(variant),
        _norm(coil.get("unit_size") or coil.get("unit_size_token")),
    )


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DivergenceEntry:
    """One adjudicated divergence. ``promoted`` is the FILE it came from, not its
    ``status`` field -- a staging entry is un-promoted no matter what it claims."""

    id: str
    coil_category: str
    product_family: str
    terra_variant: str
    unit_size_scope: str
    slot: str
    verdict: str
    reason: str
    evidence_refs: tuple[str, ...] = ()
    delta_band: tuple[float, float] | None = None
    adjudicated_by: str | None = None
    adjudicated_utc: str | None = None
    expires_utc: str | None = None
    status: str = "proposed"
    rule_proposal: str | None = None
    promoted: bool = False

    @property
    def key(self) -> str:
        return divergence_key(
            self.coil_category, self.product_family, self.terra_variant,
            self.unit_size_scope, self.slot,
        )

    @property
    def severity(self) -> str:
        return _SEVERITY_BY_VERDICT.get(self.verdict, "known_gap")


@dataclass(frozen=True)
class DivergenceRegistry:
    """Merged promoted + staging view. ``warnings`` are surfaced to the browser, not
    logged and forgotten -- a band conflict silently resolved is the failure mode."""

    entries: tuple[DivergenceEntry, ...] = ()
    warnings: tuple[str, ...] = ()
    by_key: dict[str, DivergenceEntry] = field(default_factory=dict)


def _band(raw: Any) -> tuple[float, float] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        lo, hi = raw.get("min"), raw.get("max")
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        lo, hi = raw
    else:
        raise ValueError(f"delta_band must be {{min, max}} or [min, max], got {raw!r}")
    lo, hi = float(lo), float(hi)
    if lo > hi:
        raise ValueError(f"delta_band min {lo} exceeds max {hi}")
    return (lo, hi)


def _entry_from_dict(raw: dict[str, Any], *, promoted: bool) -> DivergenceEntry:
    unknown = set(raw) - _ALLOWED_ENTRY_KEYS
    if unknown:
        raise ValueError(f"unknown divergence keys: {sorted(unknown)}")
    for required in ("id", "coil_category", "slot", "verdict", "reason"):
        if not str(raw.get(required) or "").strip():
            raise ValueError(f"divergence entry missing required field {required!r}")
    if raw["verdict"] not in REGISTERABLE:
        raise ValueError(
            f"registry verdict must be one of {REGISTERABLE}, got {raw['verdict']!r}"
        )
    scope = raw.get("unit_size_scope") or ANY_SIZE
    return DivergenceEntry(
        id=str(raw["id"]),
        coil_category=_norm(raw["coil_category"]),
        product_family=_norm(raw.get("product_family")),
        terra_variant=_norm(raw.get("terra_variant")),
        unit_size_scope=ANY_SIZE if scope == ANY_SIZE else _norm(scope),
        slot=_norm(raw["slot"]),
        verdict=str(raw["verdict"]),
        reason=str(raw["reason"]),
        evidence_refs=tuple(raw.get("evidence_refs") or ()),
        delta_band=_band(raw.get("delta_band")),
        adjudicated_by=raw.get("adjudicated_by"),
        adjudicated_utc=raw.get("adjudicated_utc"),
        expires_utc=raw.get("expires_utc"),
        status=str(raw.get("status") or "proposed"),
        rule_proposal=raw.get("rule_proposal"),
        promoted=promoted,
    )


def _read(path: Path, *, promoted: bool) -> tuple[list[DivergenceEntry], list[str]]:
    if not path.exists():
        return [], []
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001 -- a broken file must not 500 the review
        return [], [f"{path.name} could not be parsed: {exc}"]
    entries, warnings = [], []
    for raw in doc.get("divergences") or []:
        try:
            entries.append(_entry_from_dict(dict(raw), promoted=promoted))
        except Exception as exc:  # noqa: BLE001 -- skip the bad row, keep the rest
            warnings.append(f"{path.name}: skipped an entry -- {exc}")
    return entries, warnings


def load_registry(
    *, promoted_path: Path | None = None, staging_path: Path | None = None
) -> DivergenceRegistry:
    """Merge the promoted registry with the working file.

    **Staging wins** -- it holds the more recent human ruling. When the same key appears on
    both sides with a DIFFERENT band, that is surfaced as a warning rather than resolved
    silently: the band is what decides suppression vs re-escalation, so a key whose band
    depends on load order would suppress inconsistently run to run.
    """
    promoted, w1 = _read(promoted_path or _PROMOTED_PATH, promoted=True)
    staged, w2 = _read(staging_path or _STAGING_PATH, promoted=False)
    warnings = list(w1) + list(w2)

    by_key: dict[str, DivergenceEntry] = {}
    for entry in promoted:
        if entry.key in by_key:
            warnings.append(
                f"duplicate key {entry.key} in the promoted registry "
                f"({by_key[entry.key].id} and {entry.id}); kept {entry.id}"
            )
        by_key[entry.key] = entry
    for entry in staged:
        prior = by_key.get(entry.key)
        if prior is not None and prior.delta_band != entry.delta_band:
            warnings.append(
                f"{entry.id} re-adjudicates {prior.id} ({entry.key}) with a different "
                f"delta band {entry.delta_band} vs {prior.delta_band}; the un-promoted "
                f"band is in force -- promote or withdraw one of them"
            )
        by_key[entry.key] = entry

    return DivergenceRegistry(
        entries=tuple(by_key.values()), warnings=tuple(warnings), by_key=by_key
    )


# --------------------------------------------------------------------------- #
# annotation
# --------------------------------------------------------------------------- #
def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _lookup(
    registry: DivergenceRegistry, category: str, family: str, variant: str,
    unit_size: str, slot: str,
) -> DivergenceEntry | None:
    """Exact size first, then the all-sizes ruling. A ruling scoped to one size must not be
    shadowed by a broader one, and vice versa -- the narrower declaration is the later,
    better-informed statement."""
    for scope in (unit_size, ANY_SIZE):
        entry = registry.by_key.get(
            divergence_key(category, family, variant, scope, slot)
        )
        if entry is not None:
            return entry
    return None


def _annotation(
    entry: DivergenceEntry, coilforge: Any, checklist: Any, *, now_utc: str | None
) -> dict[str, Any]:
    delta = None
    cf, cl = _num(coilforge), _num(checklist)
    if cf is not None and cl is not None:
        delta = round(cf - cl, 4)

    expired = bool(entry.expires_utc and now_utc and now_utc >= entry.expires_utc)
    # A ruling MAY be granted without a band, and that is not a missing measurement. Some
    # divergences are structural rather than numeric -- when the sheet has no branch for
    # this product line at all, every number its else-branch produces is wrong and no
    # magnitude makes it right. Such a ruling is unconditional BY DECLARATION, and the
    # annotation says so rather than implying the magnitude was checked and passed.
    if entry.delta_band is None:
        in_band = True
    elif delta is None:
        in_band = False  # non-numeric divergence cannot be checked against a band
    else:
        in_band = entry.delta_band[0] <= delta <= entry.delta_band[1]

    applies = in_band and not expired
    if expired:
        note = "this ruling has expired -- re-adjudicate or extend it"
    elif entry.delta_band is None:
        note = "adjudicated on structural grounds -- the magnitude is not what makes it wrong"
    elif delta is None:
        note = "the values are not numeric, so the delta band cannot be checked"
    elif not in_band:
        note = (
            f"delta {delta} is outside the adjudicated band "
            f"{entry.delta_band[0]}..{entry.delta_band[1]} -- this divergence changed "
            "character and needs a fresh ruling"
        )
    else:
        note = None

    return {
        "id": entry.id,
        "verdict": entry.verdict,
        # An out-of-band or expired ruling reverts to the raw comparison's severity: it
        # stops applying rather than silently downgrading to a weaker amber.
        "severity": entry.severity if applies else "re_escalated",
        "applies": applies,
        "reason": entry.reason,
        "evidence_refs": list(entry.evidence_refs),
        "delta": delta,
        "delta_band": list(entry.delta_band) if entry.delta_band else None,
        "unconditional": entry.delta_band is None,
        "in_band": in_band,
        "expired": expired,
        "promoted": entry.promoted,
        "status": entry.status,
        "adjudicated_by": entry.adjudicated_by,
        "adjudicated_utc": entry.adjudicated_utc,
        "expires_utc": entry.expires_utc,
        "rule_proposal": entry.rule_proposal,
        "note": note,
    }


def identities_by_tag(coils: Any) -> dict[str, tuple[str, str, str, str]]:
    """``{tag: identity}`` for a checklist coil list. Small enough to cache alongside the
    review, which is what lets the cache-hit path annotate without re-running the
    workflow -- a ruling recorded in the browser must change the NEXT render, and the
    checklist result is memoized by PDF bytes.

    Anything that is not a tagged dict is skipped rather than raising. This layer only
    RE-LABELS rows; it must never be the reason a checklist fill fails, because the fill
    is what John is actually there for.
    """
    out: dict[str, tuple[str, str, str, str]] = {}
    for coil in coils or []:
        if not isinstance(coil, dict):
            continue
        tag = coil.get("tag")
        if tag:
            out[tag] = coil_identity(coil)
    return out


def annotate_known_divergences(
    review: dict[str, Any] | None,
    coils: list[dict[str, Any]] | None = None,
    *,
    identities: dict[str, tuple[str, str, str, str]] | None = None,
    registry: DivergenceRegistry | None = None,
    now_utc: str | None = None,
) -> dict[str, Any] | None:
    """Add an additive ``divergence`` key to every comparison row a ruling covers.

    Annotation is done **server-side on purpose**: the scope-matching rules (variant axis,
    exact-size-before-wildcard, band arithmetic) would otherwise be re-implemented in JS and
    drift. ``compare.py`` stays pure -- this runs after it.

    Pass ``coils`` on the fresh path, ``identities`` on the cache-hit path (where the coil
    dicts were never rebuilt). Mutates and returns ``review`` -- the caller annotates its
    own deepcopy, so the cached entry stays un-annotated and a later ruling is picked up
    instead of being frozen at first-fill time.
    """
    if not review or not divergence_enabled():
        return review

    reg = registry if registry is not None else load_registry()
    identity_by_tag = {**(identities or {}), **identities_by_tag(coils)}

    counts = {"known_gap": 0, "known_defect": 0, "re_escalated": 0}
    matched_by_id: dict[str, int] = {}

    for sheet in review.get("sheets") or []:
        if not isinstance(sheet, dict):
            continue
        identity = identity_by_tag.get(sheet.get("tag"))
        if identity is None:
            continue
        category, family, variant, unit_size = identity
        # The sheet's own category is the authority for its rows; the coil dict's
        # coil_type is the same token, but a sheet is generated per category and a
        # mismatch would mean the join is wrong, not that the ruling is broader.
        category = _norm(sheet.get("category") or category)
        for row in sheet.get("comparisons") or []:
            if not isinstance(row, dict):
                continue
            # `match` and `overridden` are not open questions -- annotating them would
            # attach a ruling to a row that is not asking anything.
            if row.get("verdict") in (None, "match", "overridden", "both_missing"):
                continue
            entry = _lookup(reg, category, family, variant, unit_size, _norm(row.get("slot")))
            if entry is None:
                continue
            note = _annotation(entry, row.get("coilforge"), row.get("checklist"), now_utc=now_utc)
            row["divergence"] = note
            counts[note["severity"]] = counts.get(note["severity"], 0) + 1
            if note["applies"]:
                matched_by_id[entry.id] = matched_by_id.get(entry.id, 0) + 1

    review["divergence_summary"] = {
        **counts,
        # D5 "suppression outliving its cause": how much each ruling is silencing, exposed
        # rather than inferred. Per-review, not lifetime -- a lifetime counter this module
        # cannot maintain honestly would be worse than an accurate local one.
        "suppressed_by_entry": matched_by_id,
        "registry_warnings": list(reg.warnings),
        "registry_entries": len(reg.entries),
    }
    return review
