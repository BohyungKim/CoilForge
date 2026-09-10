"""Coverage gate: every drawing slot used in a template must be classified.

This makes "is every drawing parameter mapped to the PDF/engine logic?" a CI
gate rather than a one-time audit. Each `{{slot.X}}` token found across the
coilmaster templates must fall into exactly one bucket:

  - engine_rule / recovered_formula  -> logic-derived dimension (PDF -> rule
    engine + recovered formulas). Classified by the runtime `_slot_source`.
  - material_title                   -> material / title-block string from the
    Direct Coil draft or EZ JSON (material_title_slots).
  - review_required (documented)     -> genuinely not derivable from the rule
    engine (mass-properties, secondary materials); intentionally REVIEW REQUIRED.

A NEW template slot that is none of these fails the test, surfacing an
unmapped drawing parameter instead of letting it silently render REVIEW
REQUIRED forever.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.submittal.pdf_to_template_drawing import _slot_source  # noqa: E402

_TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates" / "drawing" / "coilmaster"
_SLOT_TOKEN_RE = re.compile(r"\{\{(slot\.[A-Za-z0-9_]+)\}\}")

# Material / title-block strings sourced from the draft or EZ JSON (see
# direct_coil_drawing_pipeline.material_title_slots).
_MATERIAL_TITLE_SLOTS = {
    "slot.TUBE_MATERIAL", "slot.FIN_MATERIAL", "slot.CASING_MATERIAL",
    "slot.HEADER_MATERIAL", "slot.RETURN_CONN_SIZE", "slot.CIRCUITING",
    "slot.DISTRIBUTORS", "slot.COIL_TUBE_FACE", "slot.MODEL_NUMBER", "slot.TAG",
    # The coil's own coating instruction ("HERESITE COATING REQUIRED"). Sourced from the
    # submittal's manufacturing_options.coil_coating, not the rule engine, and filled by
    # workflows.submittal_to_drawing._apply_coating_note_to_drawing on both the analyze and
    # the derive path. Uncoated coils render it as empty rather than REVIEW REQUIRED --
    # "no coating" is a known state, not a pending decision.
    "slot.COATING_NOTE",
}

# Genuinely NOT derivable from the rule engine -> intentionally REVIEW REQUIRED.
# Mass-properties (weight/volume) need a separate calc; secondary material /
# circuiting lines and supply-conn come from the Direct Coil draft, not logic.
_DOCUMENTED_REVIEW_SLOTS = {
    "slot.DRY_WEIGHT", "slot.INTERNAL_VOLUME", "slot.FASTENER_TYPE",
    "slot.SUPPLY_CONN_SIZE", "slot.SUPPLY_CONN_SIZE_2",
    "slot.TUBE_MATERIAL_2", "slot.FIN_MATERIAL_2", "slot.FIN_MATERIAL_3",
    "slot.CASING_MATERIAL_2", "slot.CIRCUITING_2", "slot.CIRCUITING_3",
    "slot.DISTRIBUTORS_2", "slot.RETURN_CONN_SIZE_2",
    # slot.X is the drawing's X column. Its VALUE rule is unknown: the working reading
    # (header-stack depth (h+1)*D + (h-1)*1.5) explains only 52% of the real drawings that
    # carry a value, measured over 328 pages on 2026-09-05 -- see
    # docs/wiki/concepts/x-header-stack-depth.md. The older "tube projection" label was wrong.
    #
    # It was redacted from the HG_1_LH reference (2026-06-23) so that ONE drawing no
    # longer hardcodes it -- the other seven HGRH buckets still print their seed's value
    # (pinned by tests/test_template_hardcoded_dims.py). No engine rule emits it yet:
    # the arithmetic is settled (R-073 already emits the same term HIGH as casing_depth)
    # but the 8 seeded references are all Nova/Ventum-H class, while the shared HGRH
    # templates are also borrowed by Terra H/V, and no Terra reference exists to scope
    # the family branch. So it intentionally renders REVIEW REQUIRED (fail-closed, never
    # invented) until a Terra RHHGRC reference lets the rule be written.
    "slot.X",
}


def _all_template_slots() -> set[str]:
    slots: set[str] = set()
    for svg in _TEMPLATE_ROOT.rglob("template.svg"):
        slots.update(_SLOT_TOKEN_RE.findall(svg.read_text(encoding="utf-8")))
    return slots


def _classify(slot: str) -> str:
    source = _slot_source(slot)
    if source in {"engine_rule", "recovered_formula"}:
        return source
    if slot in _MATERIAL_TITLE_SLOTS:
        return "material_title"
    if slot in _DOCUMENTED_REVIEW_SLOTS:
        return "review_required"
    return "UNCLASSIFIED"


def test_templates_exist() -> None:
    assert _all_template_slots(), "no template slots found — check template root"


def test_every_template_slot_is_classified() -> None:
    """No drawing parameter may be silently unmapped."""
    unclassified = {s for s in _all_template_slots() if _classify(s) == "UNCLASSIFIED"}
    assert not unclassified, (
        "Unmapped template slots (neither logic-derived, material, nor documented "
        f"review-required): {sorted(unclassified)}. Either wire the slot into the "
        "rule engine / formulas, or add it to the documented review-required list."
    )


def test_per_header_positions_are_logic_derived() -> None:
    """All per-header position slots in templates classify as engine/formula,
    not material or review — the multi-header gap stays closed."""
    per_header = {
        s for s in _all_template_slots()
        if re.match(r"^slot\.(HDx|I|O|HD|SL|R|S)\d+$", s)
    }
    assert per_header, "expected per-header position slots in templates"
    for slot in per_header:
        assert _classify(slot) in {"engine_rule", "recovered_formula"}, (
            f"{slot} is a per-header position but classified {_classify(slot)}"
        )


def test_known_buckets_are_nonempty() -> None:
    """Sanity: the audit actually exercises each derivation path."""
    by_bucket: dict[str, list[str]] = {}
    for slot in _all_template_slots():
        by_bucket.setdefault(_classify(slot), []).append(slot)
    for bucket in ("engine_rule", "recovered_formula", "material_title", "review_required"):
        assert by_bucket.get(bucket), f"no slots classified as {bucket}"
