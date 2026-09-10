"""Inventory guard: no template may grow a NEW frozen as-built dimension.

The defect this pins (John 2026-08-30, found on 3095 Harrison): a dimension callout that
the seeder failed to redact stays in `template.svg` as a literal number and is printed on
EVERY coil that renders through that bucket. `coilmaster_hgrh_rh_header2` printed
`-0.25 S1` and `6.56 SL3` -- the seed coil's own values -- while the Drawing Parameters
panel beside it said S = 3.25. Two surfaces, two different numbers, no warning.

Substitution is gated by `slot_map.json`, not by the SVG (CLAUDE.md *Redaction gotcha*),
so a hardcoded callout is invisible to every existing test: the drawing renders, the
template is "populated", and nothing is missing. Only an inventory catches it.

`template.svg` is DO-NOT-TOUCH (CLAUDE.md). The four buckets redacted in 27d1ef9 carry John's
explicit, in-advance approval for exactly those files -- see the "Approved exception" note in
CLAUDE.md beside the DO-NOT-TOUCH rule. Nothing here authorises the next one.

The list below is the REMAINING inventory, and the assertion is equality, not subset:
- a new hardcoded dim fails (the regression this file exists for);
- clearing one also fails, so the list shrinks deliberately rather than drifting.
"""

from __future__ import annotations

import re
from pathlib import Path

_TEMPLATES = Path(__file__).resolve().parents[1] / "templates" / "drawing" / "coilmaster"

#: `<number> <DIMLABEL>` as a whole text node, i.e. a callout whose value never became a
#: slot. A redacted callout reads `{{slot.S1}} S1` and cannot match.
_HARDCODED = re.compile(r"-?\d+(?:\.\d+)?\s+[A-Za-z]{1,4}\d*")

#: Known-open, each with the reason it was NOT redacted in the 2026-08-30 pass. Redacting
#: a dimension the engine cannot produce is a downgrade, not a fix: the drawing would show
#: a withheld marker where it currently shows a number that is at least right for one real
#: coil. So the bar for clearing a row here is evidence, not effort.
_KNOWN_OPEN: dict[tuple[str, str], str] = {
    # `X` is the drawing's X column. A 328-page measurement of real HGRH drawings
    # (2026-09-05, docs/wiki/concepts/x-header-stack-depth.md) settled WHEN it exists --
    # only on header-connected coils -- but NOT what sets the value: the working reading
    # (header-stack depth (h+1)*D + (h-1)*1.5) explains 96 of the 186 valued pages, the
    # misses fall between the formula's steps at every integer h, and two coils identical
    # across FH/FL/CH/CL/CD/OAL/SL/I/S/O differ in X. The older "tube-projection" label
    # was wrong too.
    #
    # So redaction stays blocked, and for a stronger reason than before: with no rule,
    # slotting these seven blanks `X` for EVERY family, which John forbade on 2026-09-05.
    # Gate: an SOP/CoilMaster definition of the column -- not another reference drawing
    # (three were read on 2026-09-05 and they refuted the formula instead).
    ("coilmaster_hgrh_lh_header2", "3.38 X"): "no engine rule for X",
    ("coilmaster_hgrh_rh_header2", "3.38 X"): "no engine rule for X",
    ("coilmaster_hgrh_lh_header3", "5.50 X"): "no engine rule for X",
    ("coilmaster_hgrh_rh_header3", "5.50 X"): "no engine rule for X",
    ("coilmaster_hgrh_lh_header4", "7.63 X"): "no engine rule for X",
    ("coilmaster_hgrh_rh_header4", "7.63 X"): "no engine rule for X",
    ("coilmaster_hgrh_rh_header1", "1.25 X"): "no engine rule for X",
    # Header 3 LH / Header 4: the seed's own engine inputs could not be reconstructed
    # from `seed_evidence.json` (its recorded CD does not follow from its recorded ROWS
    # and connection size), so there is no proof the engine reproduces these numbers.
    # Redacting on an unverified basis is how a wrong value gets drawn confidently.
    ("coilmaster_hgrh_lh_header3", "5.63 SL5"): "seed inputs not reconstructible",
    ("coilmaster_hgrh_lh_header4", "5.50 SL7"): "seed inputs not reconstructible",
    ("coilmaster_hgrh_rh_header4", "5.38 SL7"): "seed inputs not reconstructible",
    # Ventum+ Header 1 supply SL: the reference prints 5.69 (the geometric position) but
    # the engine emits 6 -- John's single-feed SL1 ruling (RP-002 / KD-006..009). Redacting
    # changes the drawn value, which is his call to make, not a side effect of this pass.
    ("coilmaster_vplus_hgrh_lh_header1", "5.69 SL1"): "open SL1=6 vs 5.69 ruling",
    ("coilmaster_vplus_hgrh_rh_header1", "5.69 SL1"): "open SL1=6 vs 5.69 ruling",
    # Water HD1/SL1: the engine's water branch did not reproduce the seeded 4.00 / 8.00 /
    # 10.00 under the inputs recovered from `seed_evidence.json`, and water coils are
    # outside the HGRH multi-header scope this pass was approved for.
    ("coilmaster_cwc_lh", "4.00 HD1"): "water out of scope; value unverified",
    ("coilmaster_cwc_lh", "8.00 SL1"): "water out of scope; value unverified",
    ("coilmaster_cwc_rh", "4.00 HD1"): "water out of scope; value unverified",
    ("coilmaster_cwc_rh", "8.00 SL1"): "water out of scope; value unverified",
    ("coilmaster_vplus_cwc_lh", "4.00 HD1"): "water out of scope; value unverified",
    ("coilmaster_vplus_cwc_lh", "10.00 SL1"): "water out of scope; value unverified",
    ("coilmaster_vplus_hwc_lh", "4.00 HD1"): "water out of scope; value unverified",
    ("coilmaster_vplus_hwc_lh", "10.00 SL1"): "water out of scope; value unverified",
    ("coilmaster_vplus_hwc_rh", "4.00 HD1"): "water out of scope; value unverified",
    ("coilmaster_vplus_hwc_rh", "10.00 SL1"): "water out of scope; value unverified",
}


def _inventory() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for svg_path in sorted(_TEMPLATES.glob("*/*/template.svg")):
        template_id = svg_path.parent.name
        svg = svg_path.read_text(encoding="utf-8")
        for node in re.findall(r">([^<>]{1,40})<", svg):
            text = node.strip()
            if _HARDCODED.fullmatch(text):
                found.add((template_id, text))
    return found


def test_no_new_frozen_as_built_dimension() -> None:
    found = _inventory()
    known = set(_KNOWN_OPEN)
    assert found - known == set(), (
        "a template grew a frozen as-built dimension: "
        f"{sorted(found - known)} -- redact it to a slot in BOTH template.svg and "
        "slot_map.json, or add it here with the reason it cannot be"
    )
    assert known - found == set(), (
        f"these are no longer hardcoded: {sorted(known - found)} -- remove them from "
        "_KNOWN_OPEN so the guard keeps its exact shape"
    )


def test_the_multi_header_hgrh_supply_dims_are_redacted() -> None:
    """The buckets 3095 renders through, named explicitly so a revert is loud."""
    for template_id, slots in (
        ("coilmaster_hgrh_lh_header2", ("slot.S1", "slot.SL3")),
        ("coilmaster_hgrh_rh_header2", ("slot.S1", "slot.SL3")),
        ("coilmaster_hgrh_rh_header3", ("slot.S1", "slot.SL5")),
        ("coilmaster_vplus_hgrh_rh_header2", ("slot.SL3",)),
    ):
        svg = (_TEMPLATES / "hgrh" / template_id / "template.svg").read_text(encoding="utf-8")
        smap = (_TEMPLATES / "hgrh" / template_id / "slot_map.json").read_text(encoding="utf-8")
        for slot in slots:
            # Both halves are required: the SVG placeholder alone renders literally,
            # and the slot_map entry alone leaves the frozen number in place.
            assert "{{" + slot + "}}" in svg, f"{template_id}: {slot} missing from SVG"
            assert f'"{slot}"' in smap, f"{template_id}: {slot} missing from slot_map"
